"""Abstract ``EventStore`` interface for 10+1 Protocol events.

Every backend must implement:

* ``write_event(event)``        — persist one ``ProtocolEvent`` (append-only).
* ``read_events(...)``          — return events newest-first, optionally
                                  filtered by ``ProtocolCategory``.
* ``query_events(...)``         — alias for ``read_events``; matches the
                                  deployment-spec naming.
* ``verify_event(event, key)``  — HMAC-verify a recovered ``ProtocolEvent``
                                  using the project's signing key.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from schema.event import ProtocolCategory, ProtocolEvent


class EventStore(ABC):
    """Storage-backend-agnostic interface for the Protocol event log."""

    @abstractmethod
    def write_event(self, event: "ProtocolEvent") -> None:
        """Persist one Protocol event. MUST be append-only."""

    @abstractmethod
    def read_events(
        self,
        max_records: int = 100,
        category: "ProtocolCategory | None" = None,
    ) -> list["ProtocolEvent"]:
        """Return the most recent events (newest first), optionally filtered
        by ``ProtocolCategory``."""

    def query_events(
        self,
        max_records: int = 100,
        category: "ProtocolCategory | None" = None,
    ) -> list["ProtocolEvent"]:
        """Alias for :meth:`read_events` — matches the deployment-spec
        naming (write_event / query_events / verify_event)."""
        return self.read_events(max_records=max_records, category=category)

    def verify_event(self, event: "ProtocolEvent", key: bytes) -> bool:
        """HMAC-verify a recovered ``ProtocolEvent``.

        Uses ``event.signing_payload()`` (same as :mod:`signer.signer`)
        but applied to the event rather than a declaration. Returns True
        on match; raises :class:`ValueError` on mismatch or missing hmac.
        """
        import hmac as _hmac
        import hashlib
        if event.hmac is None:
            raise ValueError("event has no hmac field set")
        payload = event.signing_payload()
        expected = _hmac.new(key, payload, hashlib.sha256).hexdigest()
        if not _hmac.compare_digest(expected, event.hmac.lower()):
            raise ValueError("HMAC mismatch — event data does not match signature")
        return True
