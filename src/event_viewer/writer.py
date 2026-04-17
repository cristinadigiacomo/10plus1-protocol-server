"""
Phase 1 — Windows Event Log writer for Protocol events.

Adapted from governance/src/event_viewer/writer.py. Changes:
  - SOURCE_NAME = "10plus1-Protocol"
  - Uses ProtocolEvent and ProtocolCategory from schema.event
  - Event ID range 7000–7499 (DECISIONS.md DEC-002)
  - Severity mapping uses Protocol categories

Category → Windows event severity:
  DECLARATION  → Information
  VALIDATION   → Information (failures logged as Warning via event_id)
  DISPOSITION  → Information / Warning / Error (per mode — Phase 2)
  SIGNING      → Information (errors → Warning)
  SERVER       → Information (errors → Error)

Source registration
-------------------
The "10plus1-Protocol" source must be registered in the Windows registry
under HKLM\\SYSTEM\\CurrentControlSet\\Services\\EventLog\\Application\\10plus1-Protocol
for events to render cleanly in Event Viewer. Registration requires Admin.
Call register_source() once from an elevated terminal. Writes succeed without
registration but show "The description for Event ID X cannot be found."

Authoritative sources
---------------------
PATTERNS.md PATTERN-002
DECISIONS.md DEC-002
"""

from __future__ import annotations

import json
import logging
import platform
from datetime import datetime, timezone

from schema.event import (
    LOG_NAME,
    SOURCE_NAME,
    CATEGORY_EVENT_ID_RANGES,
    ProtocolCategory,
    ProtocolEvent,
)

logger = logging.getLogger(__name__)

# Graceful degradation on non-Windows (tests run on any platform)
_WINDOWS = platform.system() == "Windows"

if _WINDOWS:
    import win32evtlog
    import win32evtlogutil
    _INFO    = win32evtlog.EVENTLOG_INFORMATION_TYPE
    _WARNING = win32evtlog.EVENTLOG_WARNING_TYPE
    _ERROR   = win32evtlog.EVENTLOG_ERROR_TYPE
else:
    _INFO = _WARNING = _ERROR = 0  # stubs for non-Windows environments


_CATEGORY_EVENT_TYPE: dict[ProtocolCategory, int] = {
    ProtocolCategory.DECLARATION: _INFO,
    ProtocolCategory.VALIDATION:  _INFO,    # failures logged as Warning via event_id range
    ProtocolCategory.DISPOSITION: _INFO,    # Phase 2 will differentiate REFUSE → Warning
    ProtocolCategory.SIGNING:     _INFO,    # HMAC errors bump to Warning in write_event()
    ProtocolCategory.SERVER:      _INFO,    # tool errors bump to Error in write_event()
}

# Event IDs that should be logged at Warning or Error level
_WARNING_EVENT_IDS = {7002, 7101, 7102, 7302}   # signing failed, validation failed, schema error
_ERROR_EVENT_IDS   = {7402}                      # server tool error


class EventViewerError(Exception):
    """Raised when a read or write against the Windows Event Log fails."""


# --- Source registration (admin-only) ------------------------------------

def register_source() -> None:
    """Register the '10plus1-Protocol' event source in the Windows registry.

    Requires Administrator privileges. Safe to call repeatedly. Raises
    EventViewerError on failure (typically a permissions error).
    """
    if not _WINDOWS:
        logger.warning("register_source() called on non-Windows platform — no-op")
        return
    try:
        win32evtlogutil.AddSourceToRegistry(
            appName=SOURCE_NAME,
            msgDLL=None,
            eventLogType=LOG_NAME,
        )
        logger.info("Registered event source: %s", SOURCE_NAME)
    except Exception as exc:
        raise EventViewerError(
            f"Could not register source '{SOURCE_NAME}'. "
            f"Run from an elevated (Administrator) shell. Error: {exc}"
        ) from exc


# --- Write ---------------------------------------------------------------

def write_event(event: ProtocolEvent) -> None:
    """Write a ProtocolEvent to the Windows Application log.

    On non-Windows platforms, logs to the Python logger instead (for test
    and dev environments). The event should already be signed when writing
    in production; unsigned writes are allowed but logged at DEBUG level.
    """
    if not event.is_signed() if hasattr(event, 'is_signed') else event.hmac is None:
        logger.debug("Writing unsigned event %d (%s)", event.event_id, event.category.value)

    if not _WINDOWS:
        logger.info(
            "[Protocol Event] id=%d category=%s agent=%s: %s",
            event.event_id, event.category.value, event.agent_id, event.message
        )
        return

    # Determine severity
    if event.event_id in _ERROR_EVENT_IDS:
        event_type = _ERROR
    elif event.event_id in _WARNING_EVENT_IDS:
        event_type = _WARNING
    else:
        event_type = _CATEGORY_EVENT_TYPE[event.category]

    data_blob = event.model_dump_json(exclude={"message"}).encode("utf-8")

    try:
        win32evtlogutil.ReportEvent(
            appName=SOURCE_NAME,
            eventID=event.event_id,
            eventCategory=0,
            eventType=event_type,
            strings=[event.message],
            data=data_blob,
        )
    except Exception as exc:
        raise EventViewerError(
            f"Failed to write event {event.event_id} to '{LOG_NAME}' log: {exc}"
        ) from exc


# --- Read ----------------------------------------------------------------

def _record_to_event(record) -> ProtocolEvent | None:
    """Convert a pywin32 EventLogRecord to a ProtocolEvent. Returns None on failure."""
    if record.SourceName != SOURCE_NAME:
        return None
    raw = bytes(record.Data) if record.Data else b""
    if not raw:
        return None
    try:
        fields = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    strings = record.StringInserts or []
    message = strings[0] if strings else ""

    try:
        return ProtocolEvent(message=message, **fields)
    except Exception:
        return None


def read_events(
    max_records: int = 100,
    category: ProtocolCategory | None = None,
) -> list[ProtocolEvent]:
    """Read recent Protocol events from the Windows Application log.

    Parameters
    ----------
    max_records : int
        Upper bound on events returned.
    category : ProtocolCategory | None
        If set, only events in that category's ID range are returned.

    Returns
    -------
    list[ProtocolEvent]
        Most recent first. Unparseable records are skipped.
    """
    if not _WINDOWS:
        logger.warning("read_events() called on non-Windows platform — returning []")
        return []

    handle = None
    out: list[ProtocolEvent] = []
    try:
        handle = win32evtlog.OpenEventLog(None, LOG_NAME)
        flags = (
            win32evtlog.EVENTLOG_BACKWARDS_READ
            | win32evtlog.EVENTLOG_SEQUENTIAL_READ
        )
        while len(out) < max_records:
            records = win32evtlog.ReadEventLog(handle, flags, 0)
            if not records:
                break
            for rec in records:
                ev = _record_to_event(rec)
                if ev is None:
                    continue
                if category is not None:
                    lo, hi = CATEGORY_EVENT_ID_RANGES[category]
                    if not (lo <= ev.event_id <= hi):
                        continue
                out.append(ev)
                if len(out) >= max_records:
                    break
        return out
    except Exception as exc:
        raise EventViewerError(f"Failed to read events: {exc}") from exc
    finally:
        if handle is not None:
            win32evtlog.CloseEventLog(handle)
