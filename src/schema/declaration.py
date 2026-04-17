"""
Phase 1 — Handshake Declaration schema.

A HandshakeDeclaration is a structured, signed statement of an AI agent's
ethical posture across the 11 principles of the 10+1 Standard (C1–C11).
It is the unit of exchange in the AI↔AI Protocol handshake.

Design notes
------------
- Every declaration field maps to at least one Standard principle. See
  validator/principle_map.py for the authoritative mapping table.
- behavioral_statement must be specific. Vague statements ("be transparent")
  are accepted by the schema but flagged as warnings by the validator.
  Specificity is enforced by the validator, not the schema, because the
  schema cannot evaluate prose quality — but the validator can heuristically.
- The signature field is None until the signer module fills it in. An
  unsigned declaration is valid for local use; it must be signed before
  transmission to a counterpart.
- Principles are keyed C1–C11 in the principles dict. A declaration does
  not need to cover all 11 — missing principles produce lower coverage
  scores in the validator but are not schema errors.

Authoritative sources
---------------------
- knowledge_base/finite_agent_protocol.md, §Handshake Declaration
- knowledge_base/10p1_standard_v01.docx, §Principles
- PHASES/PHASE_1.md, §Schema Layer
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# --- Enums ---------------------------------------------------------------

class PrincipleStatus(str, Enum):
    """How the agent characterizes its compliance with this principle."""
    COMPLIANT        = "COMPLIANT"        # fully meets behavioral requirements
    PARTIAL          = "PARTIAL"          # partially meets; constraints noted
    DECLARED         = "DECLARED"         # agent commits to this posture; not self-assessed
    NOT_APPLICABLE   = "NOT_APPLICABLE"   # principle does not apply to this task context


# Valid principle IDs — exactly the 11 from the Standard.
VALID_PRINCIPLE_IDS = frozenset({
    "C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8", "C9", "C10", "C11"
})


# --- Sub-models ----------------------------------------------------------

class PrincipleStatement(BaseModel):
    """One principle's posture within a declaration."""

    model_config = ConfigDict(extra="forbid")

    principle_id: str = Field(
        ...,
        description="One of C1–C11 from the 10+1 Standard.",
    )
    status: PrincipleStatus
    behavioral_statement: str = Field(
        ...,
        min_length=10,
        description=(
            "Specific description of the behavior being declared. "
            "Per Moltbook Finding 2: specific statements have significantly "
            "higher behavioral effect than vague ones. "
            "E.g. 'State information sources before making factual claims' "
            "not 'be transparent'."
        ),
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Known limitations or exceptions to this principle's compliance.",
    )

    @field_validator("principle_id")
    @classmethod
    def _validate_principle_id(cls, v: str) -> str:
        if v not in VALID_PRINCIPLE_IDS:
            raise ValueError(
                f"principle_id '{v}' is not a valid 10+1 principle. "
                f"Valid IDs: {sorted(VALID_PRINCIPLE_IDS)}"
            )
        return v

    @field_validator("behavioral_statement")
    @classmethod
    def _strip_whitespace(cls, v: str) -> str:
        return v.strip()


# --- Main model ----------------------------------------------------------

class HandshakeDeclaration(BaseModel):
    """A signed AI↔AI posture declaration.

    Created by src.declaration.builder.build(). Signed by src.signer.signer.
    Validated by src.validator.validator.validate().
    Embedded into prompts by src.declaration.embedder.embed().
    """

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="UUID4 assigned at creation.",
    )
    agent_id: str = Field(
        ...,
        min_length=1,
        description="Identifier of the declaring agent.",
    )
    declared_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 UTC timestamp of declaration creation.",
    )
    principles: dict[str, PrincipleStatement] = Field(
        ...,
        description=(
            "Principle statements keyed by principle ID (C1–C11). "
            "Does not need to cover all 11; missing ones lower the coverage score."
        ),
    )
    context_summary: str | None = Field(
        default=None,
        description="Optional human-readable summary of the task context this declaration is for.",
    )
    signature: str | None = Field(
        default=None,
        description="HMAC-SHA256 hex digest. None until signer.sign_declaration() is called.",
    )
    signed_at: str | None = Field(
        default=None,
        description="ISO 8601 UTC timestamp of signing. None until signed.",
    )

    @field_validator("agent_id")
    @classmethod
    def _strip_agent_id(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("agent_id cannot be blank")
        return stripped

    @model_validator(mode="after")
    def _principles_keys_match_ids(self) -> "HandshakeDeclaration":
        """Ensure dict keys match the principle_id inside each statement."""
        for key, stmt in self.principles.items():
            if key not in VALID_PRINCIPLE_IDS:
                raise ValueError(
                    f"principles dict key '{key}' is not a valid principle ID."
                )
            if stmt.principle_id != key:
                raise ValueError(
                    f"principles['{key}'].principle_id is '{stmt.principle_id}'; "
                    f"it must match the dict key."
                )
        return self

    def signing_payload(self) -> bytes:
        """Canonical JSON bytes for HMAC signing.

        Excludes 'signature' and 'signed_at' — you cannot sign a payload
        that contains its own signature.
        """
        import json
        payload = self.model_dump(mode="json", exclude={"signature", "signed_at"})
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def is_signed(self) -> bool:
        return self.signature is not None and self.signed_at is not None

    def coverage(self) -> float:
        """Fraction of the 11 Standard principles this declaration covers (0.0–1.0)."""
        return len(self.principles) / 11.0
