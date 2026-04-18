"""SQLite backend for 10+1 Protocol events.

Preserves every property of the Event Viewer backend:

* **Append-only.** ``UPDATE`` and ``DELETE`` on the events table are
  blocked by database triggers.
* **HMAC preserved.** The full data channel
  ``event.model_dump_json(exclude={"message"})`` is stored as
  ``data_json``, and the ``hmac`` column is also indexed separately.
* **Dual-channel.** ``message`` (human-readable) and ``data_json``
  (machine-readable) live in separate columns — mirroring the
  Event Viewer split between StringInserts[0] and the Data blob.
* **Category ranges.** Protocol uses EventIDs 7000–7499 across five
  categories (DECLARATION, VALIDATION, DISPOSITION, SIGNING, SERVER).
  ``read_events(category=...)`` filters by event_id range, matching the
  Event Viewer reader's policy.
* **Newest-first.** ``read_events`` returns rows ``ORDER BY id DESC``.

The schema matches the governance layer's SQLite schema so the tooling
and patterns remain consistent across the 10+1 stack.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

from schema.event import CATEGORY_EVENT_ID_RANGES, ProtocolCategory, ProtocolEvent

from .base import EventStore


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category    TEXT    NOT NULL,
    event_id    INTEGER NOT NULL,
    agent_id    TEXT    NOT NULL,
    message     TEXT    NOT NULL,
    data_json   TEXT    NOT NULL,
    hmac        TEXT,
    timestamp   TEXT    NOT NULL,
    inserted_at TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
CREATE INDEX IF NOT EXISTS idx_events_event_id ON events(event_id);
CREATE INDEX IF NOT EXISTS idx_events_agent_id ON events(agent_id);

CREATE TRIGGER IF NOT EXISTS events_no_update
BEFORE UPDATE ON events
BEGIN
    SELECT RAISE(ABORT, 'events table is append-only');
END;

CREATE TRIGGER IF NOT EXISTS events_no_delete
BEFORE DELETE ON events
BEGIN
    SELECT RAISE(ABORT, 'events table is append-only');
END;
"""


class SQLiteBackendError(Exception):
    """Raised when a read or write against the SQLite store fails."""


class SQLiteBackend(EventStore):
    """Persists Protocol events to a SQLite file on disk.

    Thread-safe via an internal re-entrant lock. Pass ``":memory:"``
    for an in-memory database (useful in tests).
    """

    def __init__(self, path: str | Path) -> None:
        self._path = str(path)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            self._path,
            check_same_thread=False,
            isolation_level=None,
        )
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
            pass
        self._conn.executescript(_SCHEMA)

    @property
    def path(self) -> str:
        return self._path

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # --- write --------------------------------------------------------

    def write_event(self, event: ProtocolEvent) -> None:
        data_blob = event.model_dump_json(exclude={"message"})
        try:
            with self._lock:
                self._conn.execute(
                    "INSERT INTO events "
                    "(category, event_id, agent_id, message, data_json, "
                    " hmac, timestamp) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        event.category.value,
                        event.event_id,
                        event.agent_id,
                        event.message,
                        data_blob,
                        event.hmac,
                        event.timestamp.isoformat(),
                    ),
                )
        except sqlite3.DatabaseError as exc:
            raise SQLiteBackendError(
                f"Failed to write event to SQLite store at {self._path}: {exc}"
            ) from exc

    # --- read ---------------------------------------------------------

    def read_events(
        self,
        max_records: int = 100,
        category: ProtocolCategory | None = None,
    ) -> list[ProtocolEvent]:
        """Return stored events newest-first.

        When ``category`` is given, filters by event_id range (matching
        ``CATEGORY_EVENT_ID_RANGES``), which is the authoritative
        boundary per spec.
        """
        if max_records <= 0:
            return []

        if category is not None:
            lo, hi = CATEGORY_EVENT_ID_RANGES[category]
            sql = (
                "SELECT message, data_json FROM events "
                "WHERE event_id BETWEEN ? AND ? "
                "ORDER BY id DESC LIMIT ?"
            )
            params: tuple = (lo, hi, max_records)
        else:
            sql = (
                "SELECT message, data_json FROM events "
                "ORDER BY id DESC LIMIT ?"
            )
            params = (max_records,)

        try:
            with self._lock:
                rows = self._conn.execute(sql, params).fetchall()
        except sqlite3.DatabaseError as exc:
            raise SQLiteBackendError(
                f"Failed to read events from SQLite store at {self._path}: {exc}"
            ) from exc

        out: list[ProtocolEvent] = []
        for row in rows:
            ev = _row_to_event(row["message"], row["data_json"])
            if ev is not None:
                out.append(ev)
        return out

    def count_events(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) FROM events")
            return int(cur.fetchone()[0])


def _row_to_event(message: str, data_json: str) -> ProtocolEvent | None:
    """Reconstruct a ``ProtocolEvent`` from its stored channels.

    Returns ``None`` if the row cannot be re-validated. Matches the
    "skip suspicious records, don't crash the reader" policy used by
    the Event Viewer backend (writer._record_to_event).
    """
    try:
        fields = json.loads(data_json)
    except json.JSONDecodeError:
        return None
    try:
        return ProtocolEvent(message=message, **fields)
    except Exception:
        return None
