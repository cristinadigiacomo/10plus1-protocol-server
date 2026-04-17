"""
Phase 3 — Handshake session model and state machine.

A HandshakeSession represents a single two-agent protocol exchange.
State transitions: INITIATED → RESPONDED → COMPLETE, or any → FAILED.

Authoritative sources
---------------------
PHASES/PHASE_3.md
knowledge_base/finite_agent_protocol.md §Handshake Declaration
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from schema.declaration import HandshakeDeclaration
from schema.disposition import DispositionSignal

if TYPE_CHECKING:
    from dispositioner.engine import AlignmentReport


class SessionState(str, Enum):
    INITIATED  = "INITIATED"   # A declared; waiting for B
    RESPONDED  = "RESPONDED"   # B declared; disposition computed
    COMPLETE   = "COMPLETE"    # session closed
    FAILED     = "FAILED"      # unrecoverable error


class HandshakeSession(BaseModel):
    """A single stateful two-agent handshake exchange."""

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    session_id:               str          = Field(default_factory=lambda: str(uuid.uuid4()))
    state:                    SessionState = SessionState.INITIATED
    initiator_id:             str
    initiator_declaration:    HandshakeDeclaration
    counterpart_id:           str | None                = None
    counterpart_declaration:  HandshakeDeclaration | None = None
    disposition:              DispositionSignal | None  = None
    # alignment_report stored as plain dict to avoid non-serialisable dataclass
    alignment_report:         dict | None               = None
    initiated_at:             str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    responded_at:             str | None = None
    completed_at:             str | None = None
    error:                    str | None = None

    # --- helpers ---------------------------------------------------------

    def is_open(self) -> bool:
        return self.state == SessionState.INITIATED

    def is_complete(self) -> bool:
        return self.state in (SessionState.RESPONDED, SessionState.COMPLETE)

    def is_failed(self) -> bool:
        return self.state == SessionState.FAILED

    def summary(self) -> str:
        mode = self.disposition.mode.value if self.disposition else "—"
        score = (
            f"{self.disposition.alignment_score:.1%}"
            if self.disposition else "—"
        )
        return (
            f"session={self.session_id[:8]}… "
            f"state={self.state.value} "
            f"initiator={self.initiator_id} "
            f"counterpart={self.counterpart_id or '?'} "
            f"mode={mode} score={score}"
        )

    def to_dict(self) -> dict:
        """Serialise to a plain dict suitable for MCP tool responses."""
        return {
            "session_id":    self.session_id,
            "state":         self.state.value,
            "initiator_id":  self.initiator_id,
            "counterpart_id": self.counterpart_id,
            "disposition": (
                {
                    "mode":            self.disposition.mode.value,
                    "alignment_score": self.disposition.alignment_score,
                    "rationale":       self.disposition.rationale,
                    "recommended_action": self.disposition.recommended_action,
                }
                if self.disposition else None
            ),
            "alignment_report": self.alignment_report,
            "initiated_at":  self.initiated_at,
            "responded_at":  self.responded_at,
            "completed_at":  self.completed_at,
            "error":         self.error,
        }
