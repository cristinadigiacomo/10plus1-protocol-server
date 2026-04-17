"""
Phase 1 stub — Disposition schema.

Full implementation is Phase 2. This module defines the DispositionMode enum
and a stub DispositionSignal model so Phase 1 code can reference them without
depending on Phase 2 business logic.

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
    """Output of the disposition engine (Phase 2).

    Phase 1: this model exists so other modules can type-hint against it.
    The engine that produces it is not yet implemented.
    """

    model_config = ConfigDict(extra="forbid")

    mode: DispositionMode
    rationale: str = Field(..., description="Human-readable explanation of the disposition.")
    recommended_action: str | None = Field(
        default=None,
        description="Suggested next step for the receiving agent.",
    )
    declaration_id: str = Field(..., description="ID of the declaration this signal responds to.")
    issued_at: str = Field(..., description="ISO 8601 UTC timestamp.")
