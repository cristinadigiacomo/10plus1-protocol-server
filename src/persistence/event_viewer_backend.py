"""Event Viewer backend — thin adapter over ``event_viewer.writer``.

Delegates to the existing pywin32-based implementation. Only available
on Windows; importing this module on other platforms is safe because
``event_viewer.writer`` defers pywin32 imports to the point of use.
"""

from __future__ import annotations

from schema.event import ProtocolCategory, ProtocolEvent

from .base import EventStore


class EventViewerBackend(EventStore):
    """Persists Protocol events to the Windows Application log."""

    def __init__(self) -> None:
        # Bind the callables at construction so the import error surfaces
        # to the caller that chose this backend, not at write time.
        from event_viewer.writer import read_events, write_event
        self._write = write_event
        self._read = read_events

    def write_event(self, event: ProtocolEvent) -> None:
        self._write(event)

    def read_events(
        self,
        max_records: int = 100,
        category: ProtocolCategory | None = None,
    ) -> list[ProtocolEvent]:
        return self._read(max_records=max_records, category=category)
