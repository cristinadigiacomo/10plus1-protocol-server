"""Unit tests — Handshake session + manager (src/handshake/)."""

from __future__ import annotations

import pytest

from handshake.manager import (
    HandshakeManager,
    SessionNotFoundError,
    SessionStateError,
)
from handshake.session import HandshakeSession, SessionState
from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus
from schema.disposition import DispositionMode


# --- Helpers -------------------------------------------------------------

def make_decl(
    agent_id: str,
    status: PrincipleStatus = PrincipleStatus.COMPLIANT,
) -> HandshakeDeclaration:
    return HandshakeDeclaration(
        agent_id=agent_id,
        principles={
            "C1": PrincipleStatement(
                principle_id="C1",
                status=status,
                behavioral_statement=(
                    "State information sources before making any factual claims in responses"
                ),
            ),
            "C11": PrincipleStatement(
                principle_id="C11",
                status=status,
                behavioral_statement=(
                    "Refuse requests that require deception or misrepresentation of identity"
                ),
            ),
        },
    )


# --- HandshakeSession tests ---------------------------------------------

class TestHandshakeSession:
    def test_initial_state_is_initiated(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert session.state == SessionState.INITIATED

    def test_is_open_when_initiated(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert session.is_open()

    def test_is_not_complete_when_initiated(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert not session.is_complete()

    def test_session_id_is_uuid(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert len(session.session_id) == 36  # uuid4 format

    def test_unique_session_ids(self):
        decl = make_decl("agent-a")
        s1 = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        s2 = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert s1.session_id != s2.session_id

    def test_summary_contains_state(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert "INITIATED" in session.summary()

    def test_to_dict_has_required_keys(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        d = session.to_dict()
        for key in ["session_id", "state", "initiator_id", "counterpart_id",
                    "disposition", "initiated_at", "error"]:
            assert key in d

    def test_to_dict_disposition_none_when_not_complete(self):
        decl = make_decl("agent-a")
        session = HandshakeSession(initiator_id="agent-a", initiator_declaration=decl)
        assert session.to_dict()["disposition"] is None


# --- HandshakeManager tests ---------------------------------------------

class TestHandshakeManagerCreate:
    def test_create_returns_session(self):
        mgr = HandshakeManager()
        decl = make_decl("agent-a")
        session = mgr.create(decl)
        assert isinstance(session, HandshakeSession)

    def test_create_state_is_initiated(self):
        mgr = HandshakeManager()
        session = mgr.create(make_decl("agent-a"))
        assert session.state == SessionState.INITIATED

    def test_create_stores_session(self):
        mgr = HandshakeManager()
        session = mgr.create(make_decl("agent-a"))
        retrieved = mgr.get(session.session_id)
        assert retrieved.session_id == session.session_id

    def test_create_increments_total(self):
        mgr = HandshakeManager()
        assert mgr.total() == 0
        mgr.create(make_decl("a"))
        assert mgr.total() == 1
        mgr.create(make_decl("b"))
        assert mgr.total() == 2

    def test_max_sessions_evicts_oldest(self):
        mgr = HandshakeManager(max_sessions=2)
        s1 = mgr.create(make_decl("a"))
        s2 = mgr.create(make_decl("b"))
        s3 = mgr.create(make_decl("c"))
        assert mgr.total() == 2
        with pytest.raises(SessionNotFoundError):
            mgr.get(s1.session_id)


class TestHandshakeManagerRespond:
    def test_respond_advances_to_responded(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.state == SessionState.RESPONDED

    def test_respond_sets_counterpart_id(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.counterpart_id == "agent-b"

    def test_respond_sets_disposition(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.disposition is not None

    def test_respond_sets_alignment_report(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.alignment_report is not None
        assert "alignment_score" in updated.alignment_report

    def test_respond_sets_responded_at(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.responded_at is not None

    def test_respond_not_found_raises(self):
        mgr = HandshakeManager()
        with pytest.raises(SessionNotFoundError):
            mgr.respond("nonexistent-id", make_decl("b"), require_signature=False)

    def test_respond_twice_raises_state_error(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        with pytest.raises(SessionStateError):
            mgr.respond(s.session_id, make_decl("agent-c"), require_signature=False)

    def test_unsigned_counterpart_refused_when_required(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        # counterpart is unsigned (no signature field)
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=True)
        # Should still respond (REFUSE disposition), not raise
        assert updated.disposition is not None
        assert updated.disposition.mode == DispositionMode.REFUSE

    def test_aligned_declarations_produce_proceed(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a", PrincipleStatus.COMPLIANT))
        updated = mgr.respond(
            s.session_id,
            make_decl("agent-b", PrincipleStatus.COMPLIANT),
            require_signature=False,
        )
        assert updated.disposition.mode == DispositionMode.PROCEED

    def test_is_complete_after_respond(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("agent-a"))
        updated = mgr.respond(s.session_id, make_decl("agent-b"), require_signature=False)
        assert updated.is_complete()


class TestHandshakeManagerGet:
    def test_get_existing_session(self):
        mgr = HandshakeManager()
        s = mgr.create(make_decl("a"))
        retrieved = mgr.get(s.session_id)
        assert retrieved.session_id == s.session_id

    def test_get_nonexistent_raises(self):
        mgr = HandshakeManager()
        with pytest.raises(SessionNotFoundError):
            mgr.get("does-not-exist")


class TestHandshakeManagerListRecent:
    def test_list_empty(self):
        mgr = HandshakeManager()
        assert mgr.list_recent() == []

    def test_list_returns_newest_first(self):
        mgr = HandshakeManager()
        s1 = mgr.create(make_decl("a"))
        s2 = mgr.create(make_decl("b"))
        s3 = mgr.create(make_decl("c"))
        recent = mgr.list_recent()
        # Newest (c) should be first
        assert recent[0].session_id == s3.session_id
        assert recent[1].session_id == s2.session_id
        assert recent[2].session_id == s1.session_id

    def test_list_respects_n_limit(self):
        mgr = HandshakeManager()
        for i in range(10):
            mgr.create(make_decl(f"agent-{i}"))
        assert len(mgr.list_recent(n=3)) == 3

    def test_list_n_larger_than_store(self):
        mgr = HandshakeManager()
        mgr.create(make_decl("a"))
        result = mgr.list_recent(n=100)
        assert len(result) == 1
