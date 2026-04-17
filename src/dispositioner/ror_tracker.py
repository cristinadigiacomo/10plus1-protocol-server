"""
Phase 2 — ROR (Refused-Or-Rerouted) rate tracker.

ROR is the primary health metric for any Protocol deployment.
A session with 0% ROR either has perfect alignment or is failing to detect
misalignment. High ROR indicates either a posture design problem or a genuine
alignment gap worth investigating. Track it. Surface it. Do not bury it.

This tracker is in-memory and per-session. Phase 3 will add persistence.

Authoritative sources
---------------------
DECISIONS.md DEC-005
PHASES/PHASE_2.md §ROR Tracker
knowledge_base/finite_agent_protocol.md §ROR Metric
"""

from __future__ import annotations

from collections import deque

from schema.disposition import DispositionMode


class RORTracker:
    """Rolling-window tracker for disposition mode history.

    Parameters
    ----------
    window_size : int
        Maximum number of dispositions tracked. Once full, oldest entries
        are dropped. Default 100.
    """

    def __init__(self, window_size: int = 100) -> None:
        self._window_size = window_size
        self._history: deque[DispositionMode] = deque(maxlen=window_size)

    def record(self, mode: DispositionMode) -> None:
        """Record a disposition mode into the rolling window."""
        self._history.append(mode)

    def ror_rate(self) -> float:
        """Return the Refused-Or-Rerouted rate as a fraction 0.0–1.0.

        Returns 0.0 if no dispositions have been recorded yet.
        """
        if not self._history:
            return 0.0
        ror_count = sum(
            1 for m in self._history
            if m in (DispositionMode.REFUSE, DispositionMode.REROUTE)
        )
        return ror_count / len(self._history)

    def counts(self) -> dict[str, int]:
        """Return per-mode counts across the current window."""
        result = {mode.value: 0 for mode in DispositionMode}
        for m in self._history:
            result[m.value] += 1
        return result

    def total(self) -> int:
        """Total dispositions recorded in the current window."""
        return len(self._history)

    def window_size(self) -> int:
        return self._window_size

    def summary(self) -> str:
        """Human-readable one-line summary."""
        if not self._history:
            return "No dispositions recorded yet."
        c = self.counts()
        return (
            f"ROR={self.ror_rate():.1%} | "
            f"total={self.total()} | "
            f"PROCEED={c['PROCEED']} "
            f"REROUTE={c['REROUTE']} "
            f"COMPLETE_AND_FLAG={c['COMPLETE_AND_FLAG']} "
            f"REFUSE={c['REFUSE']}"
        )
