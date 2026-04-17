"""
Phase 4 — Append-only JSONL event journal.

Every Protocol event is written to a local .jsonl file in addition to Windows
Event Viewer. This gives operators a readable, grep-able, restart-persistent
event log that works on any platform.

Format: one JSON object per line (newline-delimited JSON).
Fields: timestamp, event_id, category, agent_id, declaration_id, message, data.

The journal is append-only. Lines are never modified or deleted by this module.
Rotation and archiving are operator responsibilities.

Authoritative sources
---------------------
PHASES/PHASE_4.md §Event journal
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_JOURNAL_PATH = ".protocol_journal.jsonl"


class EventJournal:
    """Append-only JSONL event journal.

    Parameters
    ----------
    path : str | Path
        Path to the journal file. Created on first write if absent.
    """

    def __init__(self, path: str | Path = DEFAULT_JOURNAL_PATH) -> None:
        self._path = Path(path)

    def append(
        self,
        *,
        event_id: int,
        category: str,
        agent_id: str,
        message: str,
        data: dict | None = None,
        declaration_id: str | None = None,
    ) -> None:
        """Append one event to the journal. Best-effort — never raises."""
        entry = {
            "timestamp":      datetime.now(timezone.utc).isoformat(),
            "event_id":       event_id,
            "category":       category,
            "agent_id":       agent_id,
            "declaration_id": declaration_id,
            "message":        message,
            "data":           data or {},
        }
        try:
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, separators=(",", ":")) + "\n")
        except Exception as exc:
            logger.warning("Journal write failed (non-fatal): %s", exc)

    def read_recent(
        self,
        n: int = 50,
        category: str | None = None,
    ) -> list[dict]:
        """Read the n most recent journal entries, newest first.

        Parameters
        ----------
        n : int
            Maximum number of entries to return.
        category : str | None
            If set, only return entries whose category matches.

        Returns
        -------
        list[dict]  newest first.
        """
        if not self._path.is_file():
            return []

        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
        except Exception as exc:
            logger.warning("Journal read failed: %s", exc)
            return []

        entries: list[dict] = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if category is not None and entry.get("category") != category:
                continue
            entries.append(entry)
            if len(entries) >= n:
                break

        return entries

    def total_lines(self) -> int:
        """Return the total number of lines in the journal file."""
        if not self._path.is_file():
            return 0
        try:
            return sum(1 for _ in self._path.open("r", encoding="utf-8"))
        except Exception:
            return 0

    @property
    def path(self) -> Path:
        return self._path
