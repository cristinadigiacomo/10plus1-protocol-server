"""
Phase 1 — Protocol event schema.

Adapted from governance/src/schema/event.py. Protocol-specific changes:
  - SOURCE_NAME = "10plus1-Protocol"
  - Event ID range 7000–7499 (Protocol owns this range)
  - Category enum is Protocol-specific (declaration, validation, disposition,
    signing, server) rather than governance categories

Event ID allocation:
  7000–7099  DECLARATION  — declaration created, signed, signing failed
  7100–7199  VALIDATION   — validation passed, failed, schema error
  7200–7299  DISPOSITION  — PROCEED, REROUTE, COMPLETE_AND_FLAG, REFUSE (Phase 2)
  7300–7399  SIGNING      — signed, verified, HMAC error
  7400–7499  SERVER       — startup, shutdown, tool calls, errors

Authoritative sources:
  DECISIONS.md DEC-002 (event ID allocation)
  PATTERNS.md PATTERN-002 (event viewer pattern)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SOURCE_NAME = "10plus1-Protocol"
LOG_NAME    = "Application"

MAX_MESSAGE_BYTES = 32 * 1024   # 32 KB
MAX_DATA_BYTES    = 64 * 1024   # 64 KB


class ProtocolCategory(str, Enum):
    DECLARATION = "declaration"
    VALIDATION  = "validation"
    DISPOSITION = "disposition"
    SIGNING     = "signing"
    SERVER      = "server"


CATEGORY_EVENT_ID_RANGES: dict[ProtocolCategory, tuple[int, int]] = {
    ProtocolCategory.DECLARATION: (7000, 7099),
    ProtocolCategory.VALIDATION:  (7100, 7199),
    ProtocolCategory.DISPOSITION: (7200, 7299),
    ProtocolCategory.SIGNING:     (7300, 7399),
    ProtocolCategory.SERVER:      (7400, 7499),
}

# Named event IDs for use throughout the codebase
class EventID:
    # Declaration
    DECLARATION_CREATED        = 7000
    DECLARATION_SIGNED         = 7001
    DECLARATION_SIGNING_FAILED = 7002

    # Validation
    VALIDATION_PASSED          = 7100
    VALIDATION_FAILED          = 7101
    VALIDATION_SCHEMA_ERROR    = 7102

    # Disposition (Phase 2 — reserved)
    DISPOSITION_PROCEED        = 7200
    DISPOSITION_REROUTE        = 7201
    DISPOSITION_COMPLETE_FLAG  = 7202
    DISPOSITION_REFUSE         = 7203

    # Signing
    SIGNING_SIGNED             = 7300
    SIGNING_VERIFIED           = 7301
    SIGNING_HMAC_ERROR         = 7302

    # Server
    SERVER_STARTED             = 7400
    SERVER_STOPPED             = 7401
    SERVER_TOOL_ERROR          = 7402
    SERVER_TOOL_CALL           = 7403

    # Handshake sessions (within SERVER range)
    HANDSHAKE_INITIATED        = 7410
    HANDSHAKE_RESPONDED        = 7411
    HANDSHAKE_COMPLETE         = 7412
    HANDSHAKE_FAILED           = 7413


class ProtocolEvent(BaseModel):
    """A single dual-channel Protocol event for Windows Event Log."""

    model_config = ConfigDict(
        extra="forbid",
        use_enum_values=False,
    )

    # Channel 1 — human readable
    message: str = Field(..., description="Human-readable event description; <= 32 KB.")

    # Channel 2 — structured
    category:   ProtocolCategory
    event_id:   int    = Field(..., description="Must lie within CATEGORY_EVENT_ID_RANGES[category].")
    agent_id:   str    = Field(..., min_length=1)
    declaration_id: str | None = Field(default=None, description="Declaration this event relates to.")
    data:       dict   = Field(default_factory=dict, description="Arbitrary structured payload.")
    timestamp:  datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    hmac:       str | None = Field(default=None, description="HMAC-SHA256 hex. None until signed.")

    @field_validator("message")
    @classmethod
    def _message_size(cls, v: str) -> str:
        size = len(v.encode("utf-8"))
        if size > MAX_MESSAGE_BYTES:
            raise ValueError(f"message is {size} bytes; max is {MAX_MESSAGE_BYTES}")
        return v

    @field_validator("timestamp")
    @classmethod
    def _timestamp_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("hmac")
    @classmethod
    def _hmac_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if len(v) != 64 or any(c not in "0123456789abcdefABCDEF" for c in v):
            raise ValueError("hmac must be a 64-character hex string")
        return v.lower()

    @model_validator(mode="after")
    def _event_id_in_range(self) -> "ProtocolEvent":
        lo, hi = CATEGORY_EVENT_ID_RANGES[self.category]
        if not (lo <= self.event_id <= hi):
            raise ValueError(
                f"event_id {self.event_id} is outside range [{lo}, {hi}] "
                f"for category '{self.category.value}'"
            )
        return self

    def signing_payload(self) -> bytes:
        """Canonical bytes for HMAC — excludes hmac field itself."""
        payload = self.model_dump(mode="json", exclude={"hmac"})
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
