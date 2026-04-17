"""
Phase 3 — Protocol service layer.

Extends Phase 2 with handshake session methods:
  initiate_handshake()
  respond_to_handshake()
  get_handshake_result()
  list_sessions()

All business logic lives here. No logic in app.py.

Authoritative sources
---------------------
PATTERNS.md PATTERN-004 (service layer separation)
DECISIONS.md DEC-008 (dual-channel response)
PHASES/PHASE_3.md
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
from dispositioner.engine import compute_disposition
from dispositioner.ror_tracker import RORTracker
from handshake.manager import (
    HandshakeManager,
    SessionNotFoundError,
    SessionStateError,
)
from handshake.session import SessionState
from schema.declaration import HandshakeDeclaration
from schema.disposition import DispositionMode
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
    """Orchestrates the full Protocol pipeline (Phases 1 + 2).

    Parameters
    ----------
    key_path : str | Path
        Path to the HMAC key file (hex string, 32+ bytes).
        If not provided, defaults to PROTOCOL_HMAC_KEY_PATH env var,
        then '.protocol.key' in the current working directory.
    ror_window : int
        Rolling window size for the ROR tracker. Default 100.
    """

    def __init__(
        self,
        key_path: str | Path | None = None,
        ror_window: int = 100,
    ) -> None:
        resolved_path = (
            key_path
            or os.environ.get("PROTOCOL_HMAC_KEY_PATH")
            or ".protocol.key"
        )
        self._key_path = Path(resolved_path)
        self._key: bytes | None = None
        self._event_count = 0
        self._ror = RORTracker(window_size=ror_window)
        self._handshake = HandshakeManager()

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
                    ProtocolCategory.DECLARATION,   # 7001 is in 7000–7099 range
                    agent_id,
                    f"Declaration {declaration.id[:8]}… signed for agent '{agent_id}'",
                    data={"declaration_id": declaration.id},
                    declaration_id=declaration.id,
                )
            except ServiceError:
                # Key unavailable — return unsigned declaration with a warning
                self._log(
                    EventID.DECLARATION_SIGNING_FAILED,
                    ProtocolCategory.DECLARATION,   # 7002 is in 7000–7099 range
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
        """Return server status information including ROR metrics."""
        ror_counts = self._ror.counts()
        return {
            "message": (
                f"10+1 Protocol MCP Server — Phase 2. "
                f"{self._event_count} events logged this session. "
                f"ROR rate: {self._ror.ror_rate():.1%} "
                f"({self._ror.total()} dispositions). "
                f"Key: {'present' if self._key_path.is_file() else 'missing'}."
            ),
            "data": {
                "server": "10plus1-protocol",
                "phase": 2,
                "version": "0.2.0",
                "event_count": self._event_count,
                "key_path": str(self._key_path),
                "key_present": self._key_path.is_file(),
                "ror": {
                    "rate": self._ror.ror_rate(),
                    "total": self._ror.total(),
                    "window_size": self._ror.window_size(),
                    "counts": ror_counts,
                },
                "tools": [
                    "declare_posture",
                    "validate_declaration",
                    "embed_posture",
                    "validate_counterpart",
                    "get_disposition",
                    "get_ror_metrics",
                    "initiate_handshake",
                    "respond_to_handshake",
                    "get_handshake_result",
                    "list_sessions",
                    "get_server_info",
                ],
            },
        }

    # --- Phase 2: Disposition methods ------------------------------------

    def validate_counterpart_declaration(
        self,
        counterpart_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """Validate a counterpart's declaration JSON.

        Checks schema validity, principle coverage, vagueness, and optionally
        signature presence. Does NOT verify the HMAC (no key exchange at this
        layer) — only checks that the signature field is populated.

        Parameters
        ----------
        counterpart_json : str
            JSON string of the counterpart's HandshakeDeclaration.
        require_signature : bool
            If True, an unsigned declaration produces a WARNING. Default True.

        Returns
        -------
        dict with keys: message, data
        """
        try:
            raw = json.loads(counterpart_json)
            counterpart = HandshakeDeclaration.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid counterpart declaration JSON: {exc}") from exc

        result = validate(counterpart)

        # Signature presence check
        sig_present = counterpart.is_signed()
        sig_warning = None
        if require_signature and not sig_present:
            sig_warning = (
                "Counterpart declaration is unsigned. require_signature=True — "
                "an unsigned declaration cannot be treated as a binding posture commitment."
            )

        self._log(
            EventID.VALIDATION_PASSED if result.valid else EventID.VALIDATION_FAILED,
            ProtocolCategory.VALIDATION,
            counterpart.agent_id,
            (
                f"Counterpart declaration {counterpart.id[:8]}… validated: "
                f"{result.summary()} | signed={sig_present}"
            ),
            data={"declaration_id": counterpart.id, "signed": sig_present},
            declaration_id=counterpart.id,
        )

        warnings_data = [
            {"principle_id": i.principle_id, "message": i.message, "suggestion": i.suggestion}
            for i in result.warnings()
        ]
        if sig_warning:
            warnings_data.insert(0, {
                "principle_id": None,
                "message": sig_warning,
                "suggestion": "Ask counterpart to sign their declaration before proceeding.",
            })

        message = (
            f"Counterpart '{counterpart.agent_id}': {result.summary()} | "
            f"signed={'yes' if sig_present else 'NO'}."
        )

        return {
            "message": message,
            "data": {
                "valid": result.valid,
                "signed": sig_present,
                "agent_id": counterpart.agent_id,
                "declaration_id": counterpart.id,
                "coverage_score": result.coverage_score,
                "principles_covered": result.principles_covered,
                "principles_missing": result.principles_missing,
                "errors": [
                    {"principle_id": i.principle_id, "message": i.message}
                    for i in result.errors()
                ],
                "warnings": warnings_data,
            },
        }

    def get_disposition(
        self,
        self_declaration_json: str,
        counterpart_declaration_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """Compute a DispositionSignal from two declarations.

        Parameters
        ----------
        self_declaration_json : str
            JSON of the initiating agent's own declaration.
        counterpart_declaration_json : str
            JSON of the counterpart's declaration.
        require_signature : bool
            If True, unsigned counterpart → REFUSE. Default True.

        Returns
        -------
        dict with keys: message, data (disposition signal + alignment report)
        """
        try:
            self_decl = HandshakeDeclaration.model_validate(
                json.loads(self_declaration_json)
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid self declaration JSON: {exc}") from exc

        try:
            counterpart = HandshakeDeclaration.model_validate(
                json.loads(counterpart_declaration_json)
            )
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid counterpart declaration JSON: {exc}") from exc

        signal, report = compute_disposition(self_decl, counterpart, require_signature)

        # Record in ROR tracker
        self._ror.record(signal.mode)

        # Map mode to event ID
        _DISPOSITION_EVENT_IDS = {
            DispositionMode.PROCEED:           EventID.DISPOSITION_PROCEED,
            DispositionMode.REROUTE:           EventID.DISPOSITION_REROUTE,
            DispositionMode.COMPLETE_AND_FLAG: EventID.DISPOSITION_COMPLETE_FLAG,
            DispositionMode.REFUSE:            EventID.DISPOSITION_REFUSE,
        }
        ev_id = _DISPOSITION_EVENT_IDS[signal.mode]

        self._log(
            ev_id,
            ProtocolCategory.DISPOSITION,
            self_decl.agent_id,
            (
                f"Disposition: {signal.mode.value} | "
                f"score={signal.alignment_score:.2f} | "
                f"self={self_decl.id[:8]}… counterpart={counterpart.id[:8]}…"
            ),
            data={
                "mode": signal.mode.value,
                "alignment_score": signal.alignment_score,
                "self_declaration_id": self_decl.id,
                "counterpart_declaration_id": counterpart.id,
                "ror_rate_after": self._ror.ror_rate(),
            },
            declaration_id=self_decl.id,
        )

        gaps_data = [
            {
                "principle_id": g.principle_id,
                "self_status": g.self_status,
                "counterpart_status": g.counterpart_status,
                "score": g.score,
                "note": g.note,
            }
            for g in report.gaps
        ]

        message = (
            f"Disposition: {signal.mode.value} "
            f"(alignment {signal.alignment_score:.1%}, "
            f"{report.scored_count} principles scored, "
            f"{len(report.gaps)} gap(s)). "
            f"ROR rate: {self._ror.ror_rate():.1%}."
        )
        if signal.recommended_action:
            message += f" Action: {signal.recommended_action}"

        return {
            "message": message,
            "data": {
                "mode": signal.mode.value,
                "alignment_score": signal.alignment_score,
                "rationale": signal.rationale,
                "recommended_action": signal.recommended_action,
                "self_declaration_id": signal.declaration_id,
                "counterpart_declaration_id": signal.counterpart_declaration_id,
                "issued_at": signal.issued_at,
                "report": {
                    "scored_count": report.scored_count,
                    "gaps": gaps_data,
                    "skipped": report.skipped,
                },
                "ror_after": {
                    "rate": self._ror.ror_rate(),
                    "total": self._ror.total(),
                },
            },
        }

    def get_ror_metrics(self) -> dict[str, Any]:
        """Return the current ROR (Refused-Or-Rerouted) metrics for this session."""
        summary = self._ror.summary()
        counts = self._ror.counts()
        rate = self._ror.ror_rate()
        total = self._ror.total()

        return {
            "message": f"ROR metrics — {summary}",
            "data": {
                "ror_rate": rate,
                "total_dispositions": total,
                "window_size": self._ror.window_size(),
                "counts": counts,
                "interpretation": (
                    "0% ROR: perfect alignment or no misalignment detected. "
                    "High ROR: posture design gap or genuine alignment problem. "
                    "Both extremes warrant investigation."
                ),
            },
        }

    # --- Phase 3: Handshake session methods ------------------------------

    def initiate_handshake(
        self,
        self_declaration_json: str,
    ) -> dict[str, Any]:
        """Create a new handshake session as the initiating agent.

        Agent A submits its own signed declaration. A session_id is returned
        that Agent B must use when calling respond_to_handshake().

        Parameters
        ----------
        self_declaration_json : str
            JSON string of the initiating agent's HandshakeDeclaration.

        Returns
        -------
        dict with keys: message, data (session_id, session state)
        """
        try:
            raw = json.loads(self_declaration_json)
            initiator_decl = HandshakeDeclaration.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid initiator declaration JSON: {exc}") from exc

        session = self._handshake.create(initiator_decl)

        self._log(
            EventID.HANDSHAKE_INITIATED,
            ProtocolCategory.SERVER,
            initiator_decl.agent_id,
            f"Handshake initiated by '{initiator_decl.agent_id}' — "
            f"session {session.session_id[:8]}… | "
            f"declaration coverage: {initiator_decl.coverage():.1%}",
            data={
                "session_id": session.session_id,
                "initiator_id": initiator_decl.agent_id,
            },
            declaration_id=initiator_decl.id,
        )

        return {
            "message": (
                f"Handshake initiated by '{initiator_decl.agent_id}'. "
                f"Session ID: {session.session_id}. "
                f"Share this session_id with the counterpart agent and ask them "
                f"to call respond_to_handshake()."
            ),
            "data": {
                "session_id":   session.session_id,
                "state":        session.state.value,
                "initiator_id": session.initiator_id,
                "initiated_at": session.initiated_at,
                "initiator_declaration_id": initiator_decl.id,
                "initiator_coverage": initiator_decl.coverage(),
            },
        }

    def respond_to_handshake(
        self,
        session_id: str,
        counterpart_declaration_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """Respond to an open handshake session as the counterpart agent.

        Agent B submits its declaration. The engine computes disposition
        immediately and the session advances to RESPONDED.

        Parameters
        ----------
        session_id : str
            The session_id from initiate_handshake().
        counterpart_declaration_json : str
            JSON string of the counterpart's HandshakeDeclaration.
        require_signature : bool
            If True, unsigned counterpart declaration → disposition REFUSE.

        Returns
        -------
        dict with keys: message, data (full session with disposition)
        """
        try:
            raw = json.loads(counterpart_declaration_json)
            counterpart_decl = HandshakeDeclaration.model_validate(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise ServiceError(f"Invalid counterpart declaration JSON: {exc}") from exc

        try:
            session = self._handshake.respond(
                session_id, counterpart_decl, require_signature=require_signature
            )
        except SessionNotFoundError as exc:
            raise ServiceError(str(exc)) from exc
        except SessionStateError as exc:
            raise ServiceError(str(exc)) from exc

        # Record in ROR tracker
        if session.disposition:
            self._ror.record(session.disposition.mode)

        ev_id = (
            EventID.HANDSHAKE_FAILED
            if session.is_failed()
            else EventID.HANDSHAKE_RESPONDED
        )
        mode_str = session.disposition.mode.value if session.disposition else "FAILED"

        self._log(
            ev_id,
            ProtocolCategory.SERVER,
            counterpart_decl.agent_id,
            (
                f"Handshake {session.session_id[:8]}… responded by "
                f"'{counterpart_decl.agent_id}' → {mode_str} | "
                f"score={session.disposition.alignment_score:.2f}"
                if session.disposition
                else f"Handshake {session.session_id[:8]}… FAILED: {session.error}"
            ),
            data={
                "session_id":   session.session_id,
                "mode":         mode_str,
                "counterpart_id": counterpart_decl.agent_id,
            },
            declaration_id=counterpart_decl.id,
        )

        if session.is_failed():
            return {
                "message": (
                    f"Handshake {session.session_id[:8]}… FAILED. "
                    f"Error: {session.error}"
                ),
                "data": session.to_dict(),
            }

        disp = session.disposition
        message = (
            f"Handshake {session.session_id[:8]}… complete. "
            f"Disposition: {disp.mode.value} "
            f"(alignment {disp.alignment_score:.1%}). "
            f"ROR rate: {self._ror.ror_rate():.1%}."
        )
        if disp.recommended_action:
            message += f" Action: {disp.recommended_action}"

        return {
            "message": message,
            "data": session.to_dict(),
        }

    def get_handshake_result(self, session_id: str) -> dict[str, Any]:
        """Retrieve a handshake session by ID.

        Parameters
        ----------
        session_id : str

        Returns
        -------
        dict with keys: message, data (full session record)
        """
        try:
            session = self._handshake.get(session_id)
        except SessionNotFoundError as exc:
            raise ServiceError(str(exc)) from exc

        self._log(
            EventID.HANDSHAKE_COMPLETE,
            ProtocolCategory.SERVER,
            session.initiator_id,
            f"Handshake {session.session_id[:8]}… retrieved — state={session.state.value}",
            data={"session_id": session.session_id, "state": session.state.value},
        )

        return {
            "message": f"Session {session.session_id[:8]}…: {session.summary()}",
            "data": session.to_dict(),
        }

    def list_sessions(self, n: int = 20) -> dict[str, Any]:
        """List the most recent handshake sessions.

        Parameters
        ----------
        n : int
            Maximum number of sessions to return (default 20).

        Returns
        -------
        dict with keys: message, data (list of session summaries)
        """
        sessions = self._handshake.list_recent(n)
        total = self._handshake.total()

        state_counts: dict[str, int] = {s.value: 0 for s in SessionState}
        for sess in sessions:
            state_counts[sess.state.value] += 1

        return {
            "message": (
                f"{total} session(s) in store. "
                f"Showing {len(sessions)} most recent. "
                f"INITIATED={state_counts['INITIATED']} "
                f"RESPONDED={state_counts['RESPONDED']} "
                f"COMPLETE={state_counts['COMPLETE']} "
                f"FAILED={state_counts['FAILED']}."
            ),
            "data": {
                "total_in_store": total,
                "sessions": [s.to_dict() for s in sessions],
            },
        }
