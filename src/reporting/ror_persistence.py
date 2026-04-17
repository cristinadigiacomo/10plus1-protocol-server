"""
Phase 4 — ROR snapshot persistence.

Writes a timestamped snapshot of ROR metrics after every disposition so that
trend data accumulates across server restarts.

File format: JSON array of snapshot objects.
  [{timestamp, ror_rate, total, counts: {PROCEED, REROUTE, COMPLETE_AND_FLAG, REFUSE}}, ...]

The file grows without bound in Phase 4. Archiving is an operator concern.
Phase 5 (if built) could add rolling archive.

Authoritative sources
---------------------
PHASES/PHASE_4.md §ROR persistence
DECISIONS.md DEC-005 (ROR as primary health metric)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_ROR_PATH = ".protocol_ror.json"


class RORPersistence:
    """Timestamped ROR snapshot store.

    Parameters
    ----------
    path : str | Path
        Path to the JSON snapshot file. Created on first write if absent.
    """

    def __init__(self, path: str | Path = DEFAULT_ROR_PATH) -> None:
        self._path = Path(path)

    def _load(self) -> list[dict]:
        if not self._path.is_file():
            return []
        try:
            return json.loads(self._path.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("ROR snapshot load failed: %s", exc)
            return []

    def _save(self, snapshots: list[dict]) -> None:
        try:
            self._path.write_text(
                json.dumps(snapshots, indent=2),
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("ROR snapshot save failed: %s", exc)

    def record(
        self,
        ror_rate: float,
        total: int,
        counts: dict[str, int],
    ) -> None:
        """Append a new snapshot. Best-effort — never raises."""
        snapshot = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "ror_rate":  ror_rate,
            "total":     total,
            "counts":    counts,
        }
        snapshots = self._load()
        snapshots.append(snapshot)
        self._save(snapshots)

    def read_all(self) -> list[dict]:
        """Return all snapshots, oldest first."""
        return self._load()

    def read_recent(self, n: int = 20) -> list[dict]:
        """Return the n most recent snapshots, newest first."""
        all_snaps = self._load()
        return list(reversed(all_snaps))[:n]

    def trend_summary(self) -> dict:
        """Compute basic trend statistics across all snapshots.

        Returns
        -------
        dict with keys:
            snapshot_count, first_timestamp, latest_timestamp,
            ror_min, ror_max, ror_mean, ror_latest,
            total_dispositions_cumulative
        """
        snapshots = self._load()
        if not snapshots:
            return {
                "snapshot_count": 0,
                "first_timestamp": None,
                "latest_timestamp": None,
                "ror_min": None,
                "ror_max": None,
                "ror_mean": None,
                "ror_latest": None,
                "total_dispositions_cumulative": 0,
            }

        rates = [s["ror_rate"] for s in snapshots]
        return {
            "snapshot_count":              len(snapshots),
            "first_timestamp":             snapshots[0]["timestamp"],
            "latest_timestamp":            snapshots[-1]["timestamp"],
            "ror_min":                     min(rates),
            "ror_max":                     max(rates),
            "ror_mean":                    sum(rates) / len(rates),
            "ror_latest":                  rates[-1],
            "total_dispositions_cumulative": snapshots[-1]["total"],
        }

    @property
    def path(self) -> Path:
        return self._path
