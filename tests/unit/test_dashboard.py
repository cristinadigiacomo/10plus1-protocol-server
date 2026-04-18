"""Dashboard route tests.

Verifies all five pages and the four JSON API endpoints return 200 and
contain expected content. Uses an in-memory DataLayer backed by a seeded
temporary journal so tests are self-contained and never touch real files.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_journal(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _write_ror(path: Path, snapshots: list[dict]) -> None:
    path.write_text(json.dumps(snapshots), encoding="utf-8")


def _make_decl_event(agent_id: str, principles: dict, ts: str) -> dict:
    return {
        "timestamp":      ts,
        "event_id":       7000,
        "category":       "DECLARATION",
        "agent_id":       agent_id,
        "declaration_id": f"decl-{agent_id}",
        "message":        f"Declaration created for '{agent_id}'",
        "data": {
            "declaration_id":  f"decl-{agent_id}",
            "principle_count": len(principles),
            "principles":      principles,
            "coverage_score":  len(principles) / 11.0,
            "context_summary": f"Test context for {agent_id}",
        },
    }


def _make_handshake_events(
    session_id: str,
    initiator: str,
    counterpart: str,
    mode: str,
    score: float,
    ts_init: str,
    ts_resp: str,
) -> list[dict]:
    initiated = {
        "timestamp": ts_init,
        "event_id":  7410,
        "category":  "SERVER",
        "agent_id":  initiator,
        "declaration_id": f"decl-{initiator}",
        "message":   f"Handshake initiated by {initiator}",
        "data": {"session_id": session_id, "initiator_id": initiator},
    }
    responded = {
        "timestamp": ts_resp,
        "event_id":  7411,
        "category":  "SERVER",
        "agent_id":  counterpart,
        "declaration_id": f"decl-{counterpart}",
        "message":   f"Handshake responded by {counterpart} → {mode}",
        "data": {
            "session_id":      session_id,
            "initiator_id":    initiator,
            "counterpart_id":  counterpart,
            "mode":            mode,
            "alignment_score": score,
            "rationale":       f"Test rationale for {mode}",
            "alignment_report": {
                "alignment_score": score,
                "scored_count": 3,
                "gaps": [
                    {
                        "principle_id": "C1",
                        "principle_name": "Own AI's Outcomes",
                        "self_status": "COMPLIANT",
                        "counterpart_status": "DECLARED",
                        "score": 0.8,
                        "note": "Test gap",
                        "self_color": "emerald",
                        "counterpart_color": "blue",
                    }
                ],
                "skipped": [],
            },
        },
    }
    return [initiated, responded]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ALL_COMPLIANT = {f"C{i}": "COMPLIANT" for i in range(1, 12)}
_PARTIAL_MIX   = {f"C{i}": ("COMPLIANT" if i % 2 == 0 else "DECLARED") for i in range(1, 8)}


@pytest.fixture()
def client(tmp_path):
    """TestClient backed by a seeded in-memory-style journal on disk."""
    journal = tmp_path / ".protocol_journal.jsonl"
    ror     = tmp_path / ".protocol_ror.json"

    entries = [
        _make_decl_event("alpha-agent", _ALL_COMPLIANT,  "2026-04-18T10:00:00Z"),
        _make_decl_event("beta-agent",  _PARTIAL_MIX,    "2026-04-18T10:01:00Z"),
        _make_decl_event("gamma-agent", {"C1": "COMPLIANT", "C3": "PARTIAL"}, "2026-04-18T10:02:00Z"),
    ]
    entries += _make_handshake_events(
        "sess-aaa", "alpha-agent", "beta-agent", "PROCEED", 0.88,
        "2026-04-18T10:10:00Z", "2026-04-18T10:10:05Z",
    )
    entries += _make_handshake_events(
        "sess-bbb", "beta-agent", "gamma-agent", "REROUTE", 0.60,
        "2026-04-18T10:11:00Z", "2026-04-18T10:11:05Z",
    )
    entries += _make_handshake_events(
        "sess-ccc", "alpha-agent", "gamma-agent", "REFUSE", 0.10,
        "2026-04-18T10:12:00Z", "2026-04-18T10:12:05Z",
    )
    # One pending (initiated only)
    entries.append({
        "timestamp": "2026-04-18T10:13:00Z",
        "event_id":  7410,
        "category":  "SERVER",
        "agent_id":  "gamma-agent",
        "declaration_id": "decl-gamma-agent",
        "message":   "Handshake initiated by gamma-agent",
        "data": {"session_id": "sess-ddd", "initiator_id": "gamma-agent"},
    })

    _write_journal(journal, entries)
    _write_ror(ror, [{"timestamp": "2026-04-18T10:12:05Z", "ror_rate": 0.33, "total": 3,
                      "counts": {"PROCEED": 1, "REROUTE": 1, "COMPLETE_AND_FLAG": 0, "REFUSE": 1}}])

    import sys
    from pathlib import Path as P
    src = P(__file__).parent.parent.parent / "src"
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))

    from dashboard.data import DataLayer
    from dashboard.app import create_app

    dl  = DataLayer(journal_path=journal, ror_path=ror)
    app = create_app(data_layer=dl)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Page tests
# ---------------------------------------------------------------------------

def test_overview_200(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Network Overview" in r.text
    assert "alpha-agent" in r.text or "Handshakes" in r.text


def test_overview_shows_stats(client):
    r = client.get("/")
    assert r.status_code == 200
    # 3 completed handshakes in fixture
    assert "3" in r.text


def test_activity_200(client):
    r = client.get("/activity")
    assert r.status_code == 200
    assert "Activity Feed" in r.text


def test_activity_shows_events(client):
    r = client.get("/activity")
    assert "alpha-agent" in r.text or "DECLARATION" in r.text


def test_handshakes_200(client):
    r = client.get("/handshakes")
    assert r.status_code == 200
    assert "Handshake Explorer" in r.text


def test_handshakes_shows_sessions(client):
    r = client.get("/handshakes")
    # sess-aaa short form
    assert "sess-aaa"[:8] in r.text or "PROCEED" in r.text


def test_handshake_detail_200(client):
    r = client.get("/handshakes/sess-aaa")
    assert r.status_code == 200
    assert "alpha-agent" in r.text
    assert "beta-agent" in r.text
    assert "PROCEED" in r.text


def test_handshake_detail_shows_alignment(client):
    r = client.get("/handshakes/sess-aaa")
    assert "88%" in r.text or "Alignment" in r.text


def test_handshake_detail_shows_gaps(client):
    r = client.get("/handshakes/sess-aaa")
    assert "C1" in r.text


def test_handshake_detail_404(client):
    r = client.get("/handshakes/nonexistent-session-id")
    assert r.status_code == 404


def test_agents_200(client):
    r = client.get("/agents")
    assert r.status_code == 200
    assert "Agent Registry" in r.text


def test_agents_shows_agents(client):
    r = client.get("/agents")
    assert "alpha-agent" in r.text
    assert "beta-agent" in r.text


def test_agents_shows_heatmap(client):
    r = client.get("/agents")
    assert "Principle Coverage Heatmap" in r.text
    assert "C1" in r.text


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def test_api_overview(client):
    r = client.get("/api/overview")
    assert r.status_code == 200
    d = r.json()
    assert "total_handshakes" in d
    assert "ror_rate" in d
    assert d["total_handshakes"] == 3
    assert d["pending_handshakes"] == 1
    assert d["agent_count"] == 3


def test_api_events(client):
    r = client.get("/api/events")
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list)
    assert len(events) > 0
    assert "event_id" in events[0]
    assert "agent_id" in events[0]


def test_api_events_n_param(client):
    r = client.get("/api/events?n=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_api_handshakes(client):
    r = client.get("/api/handshakes")
    assert r.status_code == 200
    hs = r.json()
    assert isinstance(hs, list)
    assert len(hs) == 4  # 3 responded + 1 initiated
    modes = {h["mode"] for h in hs if h["mode"]}
    assert "PROCEED" in modes
    assert "REROUTE" in modes
    assert "REFUSE"  in modes


def test_api_agents(client):
    r = client.get("/api/agents")
    assert r.status_code == 200
    agents = r.json()
    assert isinstance(agents, list)
    agent_ids = {a["agent_id"] for a in agents}
    assert "alpha-agent" in agent_ids
    assert "beta-agent"  in agent_ids


# ---------------------------------------------------------------------------
# DataLayer unit tests
# ---------------------------------------------------------------------------

def test_data_layer_overview(client):
    dl = client.app.state.data_layer
    ov = dl.network_overview()
    assert ov["total_handshakes"]   == 3
    assert ov["pending_handshakes"] == 1
    assert ov["agent_count"]        == 3
    assert ov["ror_rate"]           == pytest.approx(0.33)
    assert ov["ror_status"] in ("green", "amber", "red")
    assert ov["disposition_counts"]["PROCEED"] == 1
    assert ov["disposition_counts"]["REFUSE"]  == 1


def test_data_layer_heatmap(client):
    dl      = client.app.state.data_layer
    heatmap = dl.principle_heatmap()
    assert len(heatmap) == 11
    c1 = next(p for p in heatmap if p["id"] == "C1")
    assert c1["name"] == "Own AI's Outcomes"
    # All three agents declared C1 (alpha: COMPLIANT, beta: DECLARED, gamma: COMPLIANT)
    assert c1["counts"]["COMPLIANT"] >= 1


def test_data_layer_list_agents(client):
    dl     = client.app.state.data_layer
    agents = dl.list_agents()
    assert len(agents) == 3
    alpha = next(a for a in agents if a["agent_id"] == "alpha-agent")
    assert alpha["coverage_score"] == pytest.approx(1.0)
    assert len(alpha["principle_pills"]) == 11


def test_data_layer_get_handshake(client):
    dl      = client.app.state.data_layer
    session = dl.get_handshake("sess-aaa")
    assert session is not None
    assert session["initiator_id"]   == "alpha-agent"
    assert session["counterpart_id"] == "beta-agent"
    assert session["mode"]           == "PROCEED"
    assert session["alignment_score"] == pytest.approx(0.88)
    assert session["alignment_report"] is not None


def test_data_layer_get_handshake_missing(client):
    dl = client.app.state.data_layer
    assert dl.get_handshake("does-not-exist") is None


def test_data_layer_is_empty_false(client):
    assert not client.app.state.data_layer.is_empty()
