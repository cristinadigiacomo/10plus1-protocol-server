"""
Phase 4 — Tests for reporting module:
  - EventJournal (journal.py)
  - RORPersistence (ror_persistence.py)
  - Exporter functions (exporter.py)
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from reporting.journal import EventJournal
from reporting.ror_persistence import RORPersistence
from reporting.exporter import build_session_report, build_ror_report, build_summary
from handshake.session import HandshakeSession, SessionState
from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus
from schema.disposition import DispositionMode, DispositionSignal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_journal(tmp_path):
    return EventJournal(path=tmp_path / "test.jsonl")


@pytest.fixture
def tmp_ror(tmp_path):
    return RORPersistence(path=tmp_path / "test_ror.json")


def _make_declaration(agent_id: str = "agent_a") -> HandshakeDeclaration:
    principles = {
        "C1": PrincipleStatement(
            principle_id="C1",
            status=PrincipleStatus.COMPLIANT,
            behavioral_statement="I will not deceive any party in this interaction.",
        ),
        "C4": PrincipleStatement(
            principle_id="C4",
            status=PrincipleStatus.DECLARED,
            behavioral_statement="I operate within defined operational boundaries.",
        ),
    }
    return HandshakeDeclaration(
        agent_id=agent_id,
        principles=principles,
    )


def _make_session(
    state: SessionState = SessionState.INITIATED,
    with_disposition: bool = False,
) -> HandshakeSession:
    decl = _make_declaration("initiator")
    sess = HandshakeSession(
        initiator_id="initiator",
        initiator_declaration=decl,
    )
    if with_disposition:
        counterpart = _make_declaration("counterpart")
        disp = DispositionSignal(
            mode=DispositionMode.PROCEED,
            rationale="Good alignment on all scored principles.",
            alignment_score=0.9,
            declaration_id=decl.id,
            counterpart_declaration_id=counterpart.id,
            issued_at=datetime.now(timezone.utc).isoformat(),
        )
        sess = sess.model_copy(update={
            "state": SessionState.COMPLETE,
            "counterpart_id": "counterpart",
            "counterpart_declaration": counterpart,
            "disposition": disp,
            "alignment_report": {
                "alignment_score": 0.9,
                "scored_count": 2,
                "gaps": [],
                "skipped": [],
            },
        })
    return sess


# ---------------------------------------------------------------------------
# EventJournal tests
# ---------------------------------------------------------------------------

class TestEventJournal:

    def test_append_and_read_recent(self, tmp_journal):
        tmp_journal.append(
            event_id=7000,
            category="DECLARATION",
            agent_id="agent_a",
            message="Declaration created.",
        )
        entries = tmp_journal.read_recent(n=10)
        assert len(entries) == 1
        assert entries[0]["event_id"] == 7000
        assert entries[0]["category"] == "DECLARATION"
        assert entries[0]["agent_id"] == "agent_a"
        assert entries[0]["message"] == "Declaration created."
        assert "timestamp" in entries[0]

    def test_multiple_entries_newest_first(self, tmp_journal):
        for i in range(5):
            tmp_journal.append(
                event_id=7000 + i,
                category="DECLARATION",
                agent_id="agent_a",
                message=f"Event {i}",
            )
        entries = tmp_journal.read_recent(n=10)
        assert len(entries) == 5
        # newest first: event 4 comes back first
        assert entries[0]["event_id"] == 7004
        assert entries[-1]["event_id"] == 7000

    def test_read_recent_limit(self, tmp_journal):
        for i in range(10):
            tmp_journal.append(
                event_id=7000 + i,
                category="DECLARATION",
                agent_id="a",
                message=f"msg {i}",
            )
        entries = tmp_journal.read_recent(n=3)
        assert len(entries) == 3

    def test_category_filter(self, tmp_journal):
        tmp_journal.append(event_id=7000, category="DECLARATION", agent_id="a", message="d1")
        tmp_journal.append(event_id=7200, category="DISPOSITION", agent_id="a", message="disp")
        tmp_journal.append(event_id=7001, category="DECLARATION", agent_id="a", message="d2")

        decl_entries = tmp_journal.read_recent(n=10, category="DECLARATION")
        assert len(decl_entries) == 2
        assert all(e["category"] == "DECLARATION" for e in decl_entries)

        disp_entries = tmp_journal.read_recent(n=10, category="DISPOSITION")
        assert len(disp_entries) == 1
        assert disp_entries[0]["event_id"] == 7200

    def test_total_lines_empty(self, tmp_journal):
        assert tmp_journal.total_lines() == 0

    def test_total_lines_after_writes(self, tmp_journal):
        for i in range(7):
            tmp_journal.append(
                event_id=7000 + i,
                category="DECLARATION",
                agent_id="a",
                message=f"m{i}",
            )
        assert tmp_journal.total_lines() == 7

    def test_read_recent_nonexistent_file(self, tmp_path):
        journal = EventJournal(path=tmp_path / "missing.jsonl")
        assert journal.read_recent() == []

    def test_total_lines_nonexistent_file(self, tmp_path):
        journal = EventJournal(path=tmp_path / "missing.jsonl")
        assert journal.total_lines() == 0

    def test_data_field_stored(self, tmp_journal):
        tmp_journal.append(
            event_id=7200,
            category="DISPOSITION",
            agent_id="a",
            message="Disposition computed.",
            data={"mode": "PROCEED", "score": 0.9},
        )
        entries = tmp_journal.read_recent()
        assert entries[0]["data"]["mode"] == "PROCEED"
        assert entries[0]["data"]["score"] == 0.9

    def test_declaration_id_stored(self, tmp_journal):
        tmp_journal.append(
            event_id=7000,
            category="DECLARATION",
            agent_id="a",
            message="created",
            declaration_id="uuid-123",
        )
        entries = tmp_journal.read_recent()
        assert entries[0]["declaration_id"] == "uuid-123"

    def test_entries_are_valid_jsonl(self, tmp_journal):
        tmp_journal.append(event_id=7000, category="DECLARATION", agent_id="a", message="x")
        lines = tmp_journal.path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            parsed = json.loads(line)
            assert isinstance(parsed, dict)

    def test_append_never_raises_on_bad_path(self, tmp_path):
        # Point to a directory as path — should silently fail
        journal = EventJournal(path=tmp_path / "no" / "such" / "dir" / "file.jsonl")
        # Should not raise
        journal.append(event_id=7000, category="DECLARATION", agent_id="a", message="m")


# ---------------------------------------------------------------------------
# RORPersistence tests
# ---------------------------------------------------------------------------

class TestRORPersistence:

    def test_record_and_read_all(self, tmp_ror):
        tmp_ror.record(ror_rate=0.0, total=5, counts={"PROCEED": 5, "REROUTE": 0, "COMPLETE_AND_FLAG": 0, "REFUSE": 0})
        snaps = tmp_ror.read_all()
        assert len(snaps) == 1
        assert snaps[0]["ror_rate"] == 0.0
        assert snaps[0]["total"] == 5
        assert snaps[0]["counts"]["PROCEED"] == 5
        assert "timestamp" in snaps[0]

    def test_multiple_records_appended(self, tmp_ror):
        for i in range(4):
            tmp_ror.record(ror_rate=i * 0.1, total=10, counts={})
        snaps = tmp_ror.read_all()
        assert len(snaps) == 4
        # oldest first
        assert snaps[0]["ror_rate"] == pytest.approx(0.0)
        assert snaps[3]["ror_rate"] == pytest.approx(0.3)

    def test_read_recent_newest_first(self, tmp_ror):
        for i in range(5):
            tmp_ror.record(ror_rate=i * 0.1, total=i + 1, counts={})
        recent = tmp_ror.read_recent(n=10)
        assert len(recent) == 5
        assert recent[0]["ror_rate"] == pytest.approx(0.4)
        assert recent[-1]["ror_rate"] == pytest.approx(0.0)

    def test_read_recent_limit(self, tmp_ror):
        for i in range(10):
            tmp_ror.record(ror_rate=0.1, total=1, counts={})
        recent = tmp_ror.read_recent(n=3)
        assert len(recent) == 3

    def test_trend_summary_empty(self, tmp_ror):
        t = tmp_ror.trend_summary()
        assert t["snapshot_count"] == 0
        assert t["ror_latest"] is None
        assert t["ror_min"] is None
        assert t["ror_max"] is None
        assert t["ror_mean"] is None
        assert t["total_dispositions_cumulative"] == 0

    def test_trend_summary_single(self, tmp_ror):
        tmp_ror.record(ror_rate=0.25, total=4, counts={})
        t = tmp_ror.trend_summary()
        assert t["snapshot_count"] == 1
        assert t["ror_latest"] == pytest.approx(0.25)
        assert t["ror_min"] == pytest.approx(0.25)
        assert t["ror_max"] == pytest.approx(0.25)
        assert t["ror_mean"] == pytest.approx(0.25)
        assert t["total_dispositions_cumulative"] == 4

    def test_trend_summary_multiple(self, tmp_ror):
        tmp_ror.record(ror_rate=0.0, total=10, counts={})
        tmp_ror.record(ror_rate=0.5, total=20, counts={})
        tmp_ror.record(ror_rate=0.25, total=30, counts={})
        t = tmp_ror.trend_summary()
        assert t["snapshot_count"] == 3
        assert t["ror_min"] == pytest.approx(0.0)
        assert t["ror_max"] == pytest.approx(0.5)
        assert t["ror_mean"] == pytest.approx(0.25)
        assert t["ror_latest"] == pytest.approx(0.25)
        assert t["total_dispositions_cumulative"] == 30

    def test_read_all_empty(self, tmp_ror):
        assert tmp_ror.read_all() == []

    def test_persists_across_instances(self, tmp_path):
        path = tmp_path / "ror.json"
        r1 = RORPersistence(path=path)
        r1.record(ror_rate=0.1, total=10, counts={"PROCEED": 9, "REFUSE": 1})

        r2 = RORPersistence(path=path)
        snaps = r2.read_all()
        assert len(snaps) == 1
        assert snaps[0]["ror_rate"] == pytest.approx(0.1)

    def test_path_property(self, tmp_path):
        path = tmp_path / "ror.json"
        r = RORPersistence(path=path)
        assert r.path == path


# ---------------------------------------------------------------------------
# Exporter tests
# ---------------------------------------------------------------------------

class TestBuildSessionReport:

    def test_initiated_session(self):
        sess = _make_session(state=SessionState.INITIATED)
        result = build_session_report(sess)
        assert "message" in result
        assert "data" in result
        assert "Handshake Session Report" in result["message"]
        assert "no response yet" in result["message"]
        assert result["data"]["report_type"] == "session"
        assert "generated_at" in result["data"]

    def test_complete_session_with_disposition(self):
        sess = _make_session(with_disposition=True)
        result = build_session_report(sess)
        assert "PROCEED" in result["message"]
        assert "90.0%" in result["message"]
        assert "Good alignment" in result["message"]
        assert result["data"]["report_type"] == "session"

    def test_failed_session(self):
        decl = _make_declaration()
        sess = HandshakeSession(
            initiator_id="agent_a",
            initiator_declaration=decl,
        )
        sess = sess.model_copy(update={
            "state": SessionState.FAILED,
            "error": "Signature verification failed.",
        })
        result = build_session_report(sess)
        assert "Session Failed" in result["message"]
        assert "Signature verification failed." in result["message"]

    def test_report_contains_session_id(self):
        sess = _make_session()
        result = build_session_report(sess)
        assert sess.session_id in result["message"]

    def test_data_includes_session_dict(self):
        sess = _make_session()
        result = build_session_report(sess)
        assert result["data"]["session"]["session_id"] == sess.session_id


class TestBuildRorReport:

    def test_empty_ror(self, tmp_ror):
        result = build_ror_report(tmp_ror)
        assert "message" in result
        assert "data" in result
        assert "No dispositions recorded" in result["message"]
        assert result["data"]["report_type"] == "ror_trend"
        assert result["data"]["trend"]["snapshot_count"] == 0

    def test_with_snapshots(self, tmp_ror):
        tmp_ror.record(ror_rate=0.2, total=5, counts={"PROCEED": 4, "REROUTE": 1, "COMPLETE_AND_FLAG": 0, "REFUSE": 0})
        tmp_ror.record(ror_rate=0.4, total=10, counts={"PROCEED": 6, "REROUTE": 3, "COMPLETE_AND_FLAG": 0, "REFUSE": 1})
        result = build_ror_report(tmp_ror)
        assert "ROR Trend Report" in result["message"]
        assert "40.0%" in result["message"]  # latest rate
        assert result["data"]["trend"]["snapshot_count"] == 2
        assert len(result["data"]["recent_snapshots"]) == 2

    def test_report_has_markdown_table(self, tmp_ror):
        tmp_ror.record(ror_rate=0.1, total=10, counts={"PROCEED": 9, "REROUTE": 1, "COMPLETE_AND_FLAG": 0, "REFUSE": 0})
        result = build_ror_report(tmp_ror)
        assert "|" in result["message"]  # markdown table


class TestBuildSummary:

    def test_basic_summary(self, tmp_ror):
        result = build_summary(
            session_total=3,
            session_state_counts={
                "INITIATED": 1,
                "RESPONDED": 0,
                "COMPLETE": 2,
                "FAILED": 0,
            },
            ror_persistence=tmp_ror,
            journal_total=42,
            recent_journal=[],
            event_count=2,
        )
        assert "message" in result
        assert "data" in result
        assert "10+1 Protocol" in result["message"]
        assert result["data"]["report_type"] == "summary"
        assert result["data"]["sessions"]["total"] == 3
        assert result["data"]["journal"]["total_lines"] == 42

    def test_summary_with_ror_data(self, tmp_ror):
        tmp_ror.record(ror_rate=0.33, total=3, counts={"PROCEED": 2, "REROUTE": 1, "COMPLETE_AND_FLAG": 0, "REFUSE": 0})
        result = build_summary(
            session_total=3,
            session_state_counts={"INITIATED": 0, "RESPONDED": 0, "COMPLETE": 3, "FAILED": 0},
            ror_persistence=tmp_ror,
            journal_total=10,
            recent_journal=[],
            event_count=3,
        )
        assert "33.0%" in result["message"]
        assert result["data"]["ror"]["latest_rate"] == pytest.approx(0.33)

    def test_summary_no_ror_data(self, tmp_ror):
        result = build_summary(
            session_total=0,
            session_state_counts={"INITIATED": 0, "RESPONDED": 0, "COMPLETE": 0, "FAILED": 0},
            ror_persistence=tmp_ror,
            journal_total=0,
            recent_journal=[],
            event_count=0,
        )
        # Should render "—" for missing ROR rate
        assert "—" in result["message"]

    def test_summary_recent_journal_shown(self, tmp_ror):
        recent = [
            {
                "timestamp": "2026-04-17T10:00:00+00:00",
                "event_id": 7200,
                "message": "Disposition computed for session X",
            }
        ]
        result = build_summary(
            session_total=1,
            session_state_counts={"INITIATED": 0, "RESPONDED": 0, "COMPLETE": 1, "FAILED": 0},
            ror_persistence=tmp_ror,
            journal_total=1,
            recent_journal=recent,
            event_count=1,
        )
        assert "Disposition computed for session X" in result["message"]

    def test_summary_data_structure(self, tmp_ror):
        result = build_summary(
            session_total=5,
            session_state_counts={"INITIATED": 1, "RESPONDED": 0, "COMPLETE": 4, "FAILED": 0},
            ror_persistence=tmp_ror,
            journal_total=20,
            recent_journal=[],
            event_count=4,
        )
        d = result["data"]
        assert "sessions" in d
        assert "ror" in d
        assert "journal" in d
        assert d["sessions"]["by_state"]["COMPLETE"] == 4
        assert d["journal"]["events_this_session"] == 4
