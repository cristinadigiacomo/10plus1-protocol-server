"""Unit tests — ROR tracker (src/dispositioner/ror_tracker.py)."""

from __future__ import annotations

import pytest

from dispositioner.ror_tracker import RORTracker
from schema.disposition import DispositionMode


P  = DispositionMode.PROCEED
R  = DispositionMode.REROUTE
CF = DispositionMode.COMPLETE_AND_FLAG
RF = DispositionMode.REFUSE


class TestRORTrackerBasic:
    def test_empty_rate_is_zero(self):
        t = RORTracker()
        assert t.ror_rate() == 0.0

    def test_empty_total_is_zero(self):
        t = RORTracker()
        assert t.total() == 0

    def test_record_increments_total(self):
        t = RORTracker()
        t.record(P)
        assert t.total() == 1

    def test_all_proceed_ror_zero(self):
        t = RORTracker()
        for _ in range(10):
            t.record(P)
        assert t.ror_rate() == 0.0

    def test_all_refuse_ror_one(self):
        t = RORTracker()
        for _ in range(5):
            t.record(RF)
        assert t.ror_rate() == 1.0

    def test_mixed_ror_rate(self):
        t = RORTracker()
        t.record(P)
        t.record(P)
        t.record(R)
        t.record(RF)
        # 2 ROR out of 4 = 0.5
        assert t.ror_rate() == pytest.approx(0.5)

    def test_complete_and_flag_not_counted_in_ror(self):
        t = RORTracker()
        for _ in range(4):
            t.record(CF)
        assert t.ror_rate() == 0.0

    def test_reroute_counts_as_ror(self):
        t = RORTracker()
        t.record(P)
        t.record(R)   # ROR
        assert t.ror_rate() == pytest.approx(0.5)

    def test_refuse_counts_as_ror(self):
        t = RORTracker()
        t.record(P)
        t.record(RF)  # ROR
        assert t.ror_rate() == pytest.approx(0.5)


class TestRORTrackerCounts:
    def test_counts_all_zero_initially(self):
        t = RORTracker()
        c = t.counts()
        assert all(v == 0 for v in c.values())

    def test_counts_keys_are_mode_values(self):
        t = RORTracker()
        c = t.counts()
        assert set(c.keys()) == {m.value for m in DispositionMode}

    def test_counts_correct_after_recording(self):
        t = RORTracker()
        t.record(P)
        t.record(P)
        t.record(R)
        t.record(RF)
        t.record(CF)
        c = t.counts()
        assert c["PROCEED"] == 2
        assert c["REROUTE"] == 1
        assert c["REFUSE"] == 1
        assert c["COMPLETE_AND_FLAG"] == 1


class TestRORTrackerWindow:
    def test_window_size_respected(self):
        t = RORTracker(window_size=5)
        for _ in range(10):
            t.record(P)
        assert t.total() == 5

    def test_rolling_window_drops_oldest(self):
        t = RORTracker(window_size=3)
        # Fill with ROR
        t.record(RF)
        t.record(RF)
        t.record(RF)
        assert t.ror_rate() == 1.0
        # Push in PROCEEDs — oldest RF gets dropped
        t.record(P)
        t.record(P)
        t.record(P)
        # Now window is [P, P, P] — ROR should be 0
        assert t.ror_rate() == 0.0

    def test_window_size_reported(self):
        t = RORTracker(window_size=42)
        assert t.window_size() == 42


class TestRORTrackerSummary:
    def test_summary_empty(self):
        t = RORTracker()
        s = t.summary()
        assert "No dispositions" in s

    def test_summary_has_rate(self):
        t = RORTracker()
        t.record(P)
        t.record(R)
        s = t.summary()
        assert "ROR=" in s
        assert "50.0%" in s

    def test_summary_has_all_modes(self):
        t = RORTracker()
        t.record(P)
        s = t.summary()
        assert "PROCEED" in s
        assert "REROUTE" in s
        assert "REFUSE" in s
