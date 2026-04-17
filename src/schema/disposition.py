"""
Phase 2 — Disposition schema (full implementation).

Replaces the Phase 1 stub. Adds alignment_score and counterpart_declaration_id
to DispositionSignal so callers have the full picture from a single object.

The four modes come directly from the Finite Agent Protocol:
  PROCEED           — counterpart posture is aligned; continue normally
  REROUTE           — posture gap detected; adjust approach before continuing
  COMPLETE_AND_FLAG — task can complete; interaction needs review
  REFUSE            — posture incompatible; do not proceed

Authoritative source: knowledge_base/finite_agent_protocol.md
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class DispositionMode(str, Enum):
    PROCEED           = "PROCEED"
    REROUTE           = "REROUTE"
    COMPLETE_AND_FLAG = "COMPLETE_AND_FLAG"
    REFUSE            = "REFUSE"


class DispositionSignal(BaseModel):
    """Output of the disposition engine."""

    model_config = ConfigDict(extra="forbid")

    mode: DispositionMode
    rationale: str = Field(..., description="Human-readable explanation of the disposition.")
    recommended_action: str | None = Field(
        default=None,
        description="Suggested next step for the receiving agent.",
    )
    declaration_id: str = Field(
        ...,
        description="ID of the self declaration used in this handshake.",
    )
    counterpart_declaration_id: str = Field(
        ...,
        description="ID of the counterpart declaration evaluated.",
    )
    alignment_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Aggregate alignment score (0.0–1.0) used to determine mode.",
    )
    issued_at: str = Field(..., description="ISO 8601 UTC timestamp.")
