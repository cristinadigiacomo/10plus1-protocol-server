"""
Phase 1 — Protocol service layer.

Orchestrates the declaration pipeline: build → sign → validate → embed → log.
MCP tools in tools.py are thin wrappers that call these methods.

All business logic lives here. No logic in app.py or tools.py.

Authoritative sources
---------------------
PATTERNS.md PATTERN-004 (service layer separation)
DECISIONS.md DEC-008 (dual-channel response)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from declaration.builder import build as build_declaration
from declaration.embedder import embed, embed_minimal
from schema.declaration import HandshakeDeclaration
from schema.event import EventID, ProtocolCategory, ProtocolEvent
from signer.signer import (
    ProtocolSigningError,
    load_key,
    sign_declaration,
    verify_declaration,
)
from validator.validator import ValidationResult, validate

logger = logging.getLogger(__name__)

# Lazy import — event writer requires pywin32 which may not be available
try:
    from event_viewer.writer import EventViewerError, write_event as _write_event
    _EVENT_WRITER_AVAILABLE = True
except ImportError:
    _EVENT_WRITER_AVAILABLE = False
    logger.warning("pywin32 not available — event logging disabled")


class ServiceError(Exception):
    """Raised when the service layer cannot complete an operation."""


class ProtocolService:
    """Orchestrates the Phase 1 declaration pipeline.

    Parameters
    ----------
    key_path : str | Path
        Path to the HMAC key file (hex string, 32+ bytes).
        If not provided, defaults to PROTOCOL_HMAC_KEY_PATH env var,
        then '.protocol.key' in the current working directory.
    """

    def __init__(self, key_path: str | Path | None = None) -> None:
        resolved_path = (
            key_path
            or os.environ.get("PROTOCOL_HMAC_KEY_PATH")
            or ".protocol.key"
        )
        self._key_path = Path(resolved_path)
        self._key: bytes | None = None
        self._event_count = 0

    # --- Key management --------------------------------------------------

    def _get_key(self) -> bytes:
        """Lazy-load the HMAC key. Raises ServiceError if unavailable."""
        if self._key is None:
            try:
                self._key = load_key(self._key_path)
            except (FileNotFoundError, ValueError) as exc:
                raise ServiceError(
                    f"HMAC key unavailable at {self._key_path}: {exc}. "
                    f"Generate one with: python -c \"from src.signer.signer import "
                    f"generate_key_hex; open('.protocol.key','w').write(generate_key_hex())\""
                ) from exc
        return self._key

    # --- Event logging ---------------------------------------------------

    def _log(
        self,
        event_id: int,
        category: ProtocolCategory,
        agent_id: str,
        message: str,
        data: dict | None = None,
        declaration_id: str | None = None,
    ) -> None:
        """Write a ProtocolEvent to Windows Event Log (best-effort)."""
        self._event_count += 1
        if not _EVENT_WRITER_AVAILABLE:
            logger.info("[protocol] id=%d %s", event_id, message)
            return
        try:
            event = ProtocolEvent(
                message=message,
                category=category,
                event_id=event_id,
                agent_id=agent_id,
                declaration_id=declaration_id,
                data=data or {},
            )
            _write_event(event)
        except Exception as exc:
            logger.warning("Event log write failed (non-fatal): %s", exc)

    # --- Public API ------------------------------------------------------

    def declare_posture(
        self,
        agent_id: str,
        context: str,
        principles: list[str] | None = None,
        sign: bool = True,
    ) -> dict[str, Any]:
        """Build, optionally sign, and validate a posture declaration.

        Parameters
        ----------
        agent_id : str
        context : str
            Task context — richer context gives better principle inference.
        principles : list[str] | None
            Explicit principle IDs to include. None → all 11.
        sign : bool
            If True, sign the declaration with the HMAC key. Default True.
            Set False in test/dev environments where no key file exists.

        Returns
        -------
        dict with keys:
            message  : human-readable summary (dual-channel, DEC-008)
            data     : structured result dict
        """
        try:
            declaration = build_declaration(agent_id, context, principles)
        except ValueError as exc:
            raise ServiceError(f"Declaration build failed: {exc}") from exc

        # Optionally sign
        if sign:
            try:
                key = self._get_key()
                declaration = sign_declaration(declaration, key)
                self._log(
                    EventID.DECLARATION_SIGNED,
                    ProtocolCategory.SIGNING,
                    agent_id,
                    f"Declaration {declaration.id[:8]}… signed for agent '{agent_id}'",
                    data={"declaration_id": declaration.id},
                    declaration_id=declaration.id,
                )
            except ServiceError:
                # Key unavailable — return unsigned declaration with a warning
                self._log(
                    EventID.DECLARATION_SIGNING_FAILED,
                    ProtocolCategory.SIGNING,
                    agent_id,
                    f"Signing skipped for declaration {declaration.id[:8]}… — key unavailable",
                    declaration_id=declaration.id,
                )

        self._log(
            EventID.DECLARATION_CREATED,
            ProtocolCategory.DECLARATION,
            agent_id,
            f"Posture declaration created for agent '{agent_id}' — "
            f"{len(declaration.principles)} principles, "
            f"{'signed' if declaration.is_signed() else 'unsigned'}",
            data={"declaration_id": declaration.id, "principle_count": len(declaration.principles)},
            declaration_id=declaration.id,
        )

        # Validate
        result = validate(declaration)

        self._log(
            EventID.VALIDATION_PASSED if result.valid else EventID.VALIDATION_FAILED,
            ProtocolCategory.VALIDATION,
            agent_id,
            f"Declaration {declaration.id[:8]}… validation: {result.summary()}",
            data={"declaration_id": declaration.id, "coverage": result.coverage_score},
            declaration_id=declaration.id,
        )

        signed_note = "signed" if declaration.is_signed() else "unsigned (no key)"
        message = (
            f"Declaration created for '{agent_id}'. "
            f"{len(result.principles_covered)}/11 principles active. "
            f"Coverage: {result.coverage_score:.1%}. "
            f"Status: {signed_note}. "
            f"{len(result.warnings())} warning(s)."
        )

        return {
            "message": message,
            "data": {
                "declaration": declaration.model_dump(mode="json"),
                "validation": {
                    "valid": result.valid,
                    "coverage_score": result.coverage_score,
                    "principles_covered": result.principles_covered,
                    "principles_missing": result.principles_missing,
                    "principles_not_applicable": result.principles_not_applicable,
                    "errors": [
                        {"principle_id": i.principle_id, "message": i.message}
                        for i in result.errors()
                    ],
                    "warnings": [
                        {
                            "principle_id": i.principle_id,
                            "message": i.message,
                            "suggestion": i.suggestion,
                        }
                        for i in result.warnings()
                    ],
                },
            },
        }

    def validate_declaration_json(self, declaration_json: str) -> dict[str, Any]:
        """Validate a declaration from its JSON string representation.

        Parameters
        ----------
        declaration_json : str
            JSON string of a HandshakeDeclaration (as produced by declare_posture).

        Returns
        -------
        dict with keys: message, data (validation result)
        """
        try:
            raw = json.loads(declaration_json)
            declaration = HandshakeDeclaration.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid declaration JSON: {exc}") from exc

        result = validate(declaration)

        self._log(
            EventID.VALIDATION_PASSED if result.valid else EventID.VALIDATION_FAILED,
            ProtocolCategory.VALIDATION,
            declaration.agent_id,
            f"External declaration {declaration.id[:8]}… validated: {result.summary()}",
            data={"declaration_id": declaration.id},
            declaration_id=declaration.id,
        )

        return {
            "message": result.summary(),
            "data": {
                "valid": result.valid,
                "coverage_score": result.coverage_score,
                "principles_covered": result.principles_covered,
                "principles_missing": result.principles_missing,
                "principles_not_applicable": result.principles_not_applicable,
                "errors": [
                    {"principle_id": i.principle_id, "message": i.message}
                    for i in result.errors()
                ],
                "warnings": [
                    {
                        "principle_id": i.principle_id,
                        "message": i.message,
                        "suggestion": i.suggestion,
                    }
                    for i in result.warnings()
                ],
            },
        }

    def embed_posture(
        self,
        declaration_json: str,
        prompt: str,
        minimal: bool = False,
    ) -> dict[str, Any]:
        """Embed a declaration contextually into a prompt string.

        Parameters
        ----------
        declaration_json : str
            JSON string of a HandshakeDeclaration.
        prompt : str
            The task prompt to embed posture into.
        minimal : bool
            If True, use the compact single-sentence embedding (for token-
            sensitive contexts). Default False (full contextual embedding).

        Returns
        -------
        dict with keys: message, data.embedded_prompt
        """
        try:
            raw = json.loads(declaration_json)
            declaration = HandshakeDeclaration.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid declaration JSON: {exc}") from exc

        embedded = embed_minimal(declaration, prompt) if minimal else embed(declaration, prompt)

        self._log(
            EventID.DECLARATION_CREATED,  # reuse — no dedicated embed event ID in Phase 1
            ProtocolCategory.DECLARATION,
            declaration.agent_id,
            f"Posture embedded into prompt for declaration {declaration.id[:8]}… "
            f"({'minimal' if minimal else 'full'} mode)",
            declaration_id=declaration.id,
        )

        active_count = len([
            s for s in declaration.principles.values()
            if s.status.value != "NOT_APPLICABLE"
        ])

        return {
            "message": (
                f"Posture embedded into prompt. "
                f"{active_count} active principles woven into context "
                f"({'minimal' if minimal else 'full'} mode). "
                f"Embedded prompt is {len(embedded)} characters."
            ),
            "data": {
                "embedded_prompt": embedded,
                "declaration_id": declaration.id,
                "agent_id": declaration.agent_id,
                "active_principles": active_count,
                "embedding_mode": "minimal" if minimal else "full",
                "char_count": len(embedded),
            },
        }

    def get_server_info(self) -> dict[str, Any]:
        """Return server status information."""
        return {
            "message": (
                f"10+1 Protocol MCP Server — Phase 1. "
                f"{self._event_count} events logged this session. "
                f"Key path: {self._key_path} "
                f"({'present' if self._key_path.is_file() else 'missing'})."
            ),
            "data": {
                "server": "10plus1-protocol",
                "phase": 1,
                "version": "0.1.0",
                "event_count": self._event_count,
                "key_path": str(self._key_path),
                "key_present": self._key_path.is_file(),
                "tools": [
                    "declare_posture",
                    "validate_declaration",
                    "embed_posture",
                    "get_server_info",
                ],
            },
        }
