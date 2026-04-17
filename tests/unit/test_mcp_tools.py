"""Unit tests — MCP service layer (src/mcp_server/service.py).

Tests the service methods directly (not the MCP transport). Focuses on:
  - Dual-channel response shape (message + data keys always present)
  - Correct delegation to builder, signer, validator, embedder
  - ServiceError on bad input
  - Works without a key file (sign=False path)
"""

from __future__ import annotations

import json
import secrets
import tempfile
from pathlib import Path

import pytest

from mcp_server.service import ProtocolService, ServiceError


# --- Fixtures ------------------------------------------------------------

@pytest.fixture
def service_no_key(tmp_path) -> ProtocolService:
    """Service without a key file — only usable with sign=False."""
    return ProtocolService(key_path=tmp_path / "nonexistent.key")


@pytest.fixture
def key_path(tmp_path) -> Path:
    key = secrets.token_bytes(32)
    p = tmp_path / "test.key"
    p.write_text(key.hex())
    return p


@pytest.fixture
def service(key_path) -> ProtocolService:
    return ProtocolService(key_path=key_path)


# --- declare_posture tests -----------------------------------------------

class TestDeclarePosture:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.declare_posture(
            "test-agent",
            "I need to explain my reasoning and state sources",
            sign=False,
        )
        assert "message" in result
        assert "data" in result
        assert isinstance(result["message"], str)
        assert isinstance(result["data"], dict)

    def test_message_is_not_empty(self, service_no_key):
        result = service_no_key.declare_posture("agent", "write transparent code", sign=False)
        assert len(result["message"]) > 0

    def test_data_contains_declaration(self, service_no_key):
        result = service_no_key.declare_posture("agent", "some context about sources", sign=False)
        assert "declaration" in result["data"]
        decl = result["data"]["declaration"]
        assert decl["agent_id"] == "agent"

    def test_data_contains_validation(self, service_no_key):
        result = service_no_key.declare_posture("agent", "some context", sign=False)
        assert "validation" in result["data"]
        val = result["data"]["validation"]
        assert "valid" in val
        assert "coverage_score" in val

    def test_signed_with_key(self, service):
        result = service.declare_posture(
            "agent",
            "I need to explain sources and be honest about my reasoning",
            sign=True,
        )
        decl = result["data"]["declaration"]
        assert decl["signature"] is not None
        assert decl["signed_at"] is not None

    def test_unsigned_without_key(self, service_no_key):
        result = service_no_key.declare_posture("agent", "some context", sign=False)
        decl = result["data"]["declaration"]
        assert decl["signature"] is None

    def test_explicit_principles_subset(self, service_no_key):
        result = service_no_key.declare_posture(
            "agent", "explain sources honestly", principles=["C1", "C11"], sign=False
        )
        decl = result["data"]["declaration"]
        assert set(decl["principles"].keys()) == {"C1", "C11"}

    def test_empty_context_raises_service_error(self, service_no_key):
        with pytest.raises(ServiceError, match="Declaration build failed"):
            service_no_key.declare_posture("agent", "", sign=False)

    def test_message_mentions_coverage(self, service_no_key):
        result = service_no_key.declare_posture("agent", "explain sources", sign=False)
        assert "%" in result["message"] or "coverage" in result["message"].lower()


# --- validate_declaration_json tests ------------------------------------

class TestValidateDeclarationJson:
    def test_valid_json_returns_result(self, service_no_key):
        # First build a declaration, then validate its JSON
        declare_result = service_no_key.declare_posture("agent", "cite sources always", sign=False)
        decl_json = json.dumps(declare_result["data"]["declaration"])

        result = service_no_key.validate_declaration_json(decl_json)
        assert "message" in result
        assert "data" in result
        assert "valid" in result["data"]

    def test_invalid_json_raises(self, service_no_key):
        with pytest.raises(ServiceError, match="Invalid declaration JSON"):
            service_no_key.validate_declaration_json("not json at all {{{")

    def test_invalid_schema_raises(self, service_no_key):
        with pytest.raises(ServiceError, match="Invalid declaration JSON"):
            service_no_key.validate_declaration_json('{"not": "a declaration"}')

    def test_validation_data_has_coverage_score(self, service_no_key):
        declare_result = service_no_key.declare_posture("agent", "explain sources", sign=False)
        decl_json = json.dumps(declare_result["data"]["declaration"])
        result = service_no_key.validate_declaration_json(decl_json)
        assert "coverage_score" in result["data"]


# --- embed_posture tests ------------------------------------------------

class TestEmbedPosture:
    def _decl_json(self, service_no_key: ProtocolService) -> str:
        r = service_no_key.declare_posture(
            "agent", "explain sources and reason transparently", sign=False
        )
        return json.dumps(r["data"]["declaration"])

    def test_returns_embedded_prompt(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.embed_posture(decl_json, "original prompt")
        assert "message" in result
        assert "data" in result
        assert "embedded_prompt" in result["data"]

    def test_original_prompt_in_embedded(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.embed_posture(decl_json, "do the analysis carefully")
        assert "do the analysis carefully" in result["data"]["embedded_prompt"]

    def test_not_a_header_block(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.embed_posture(decl_json, "some task")
        embedded = result["data"]["embedded_prompt"]
        assert "[POSTURE DECLARATION]" not in embedded

    def test_minimal_mode_shorter(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        prompt = "do something"
        full = service_no_key.embed_posture(decl_json, prompt, minimal=False)
        compact = service_no_key.embed_posture(decl_json, prompt, minimal=True)
        assert compact["data"]["char_count"] < full["data"]["char_count"]

    def test_invalid_json_raises(self, service_no_key):
        with pytest.raises(ServiceError, match="Invalid declaration JSON"):
            service_no_key.embed_posture("{bad}", "prompt")

    def test_data_has_char_count(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.embed_posture(decl_json, "prompt")
        assert result["data"]["char_count"] > 0


# --- get_server_info tests ----------------------------------------------

class TestGetServerInfo:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.get_server_info()
        assert "message" in result
        assert "data" in result

    def test_phase_is_2(self, service_no_key):
        result = service_no_key.get_server_info()
        assert result["data"]["phase"] == 2

    def test_tools_listed(self, service_no_key):
        result = service_no_key.get_server_info()
        tools = result["data"]["tools"]
        assert "declare_posture" in tools
        assert "validate_declaration" in tools
        assert "embed_posture" in tools
        assert "get_disposition" in tools
        assert "get_ror_metrics" in tools

    def test_ror_in_server_info(self, service_no_key):
        result = service_no_key.get_server_info()
        assert "ror" in result["data"]
        assert "rate" in result["data"]["ror"]

    def test_event_count_increments(self, service_no_key):
        initial = service_no_key.get_server_info()["data"]["event_count"]
        service_no_key.declare_posture("agent", "some context with sources", sign=False)
        after = service_no_key.get_server_info()["data"]["event_count"]
        assert after > initial


# --- validate_counterpart tests -----------------------------------------

class TestValidateCounterpart:
    def _decl_json(self, service_no_key) -> str:
        r = service_no_key.declare_posture(
            "counterpart", "explain sources and reason transparently", sign=False
        )
        return json.dumps(r["data"]["declaration"])

    def test_returns_message_and_data(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.validate_counterpart_declaration(decl_json)
        assert "message" in result
        assert "data" in result

    def test_data_has_signed_field(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.validate_counterpart_declaration(decl_json)
        assert "signed" in result["data"]

    def test_unsigned_produces_warning_when_required(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.validate_counterpart_declaration(
            decl_json, require_signature=True
        )
        warnings = result["data"]["warnings"]
        sig_warnings = [w for w in warnings if "unsigned" in w["message"].lower()]
        assert len(sig_warnings) > 0

    def test_invalid_json_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        with pytest.raises(ServiceError):
            service_no_key.validate_counterpart_declaration("{bad json")

    def test_coverage_score_present(self, service_no_key):
        decl_json = self._decl_json(service_no_key)
        result = service_no_key.validate_counterpart_declaration(decl_json)
        assert "coverage_score" in result["data"]


# --- get_disposition tests ----------------------------------------------

class TestGetDisposition:
    def _two_decl_jsons(self, service_no_key):
        r1 = service_no_key.declare_posture(
            "self-agent",
            "explain sources and reason transparently with accountability",
            sign=False,
        )
        r2 = service_no_key.declare_posture(
            "counterpart-agent",
            "explain sources and reason transparently with accountability",
            sign=False,
        )
        return (
            json.dumps(r1["data"]["declaration"]),
            json.dumps(r2["data"]["declaration"]),
        )

    def test_returns_message_and_data(self, service_no_key):
        self_j, other_j = self._two_decl_jsons(service_no_key)
        result = service_no_key.get_disposition(
            self_j, other_j, require_signature=False
        )
        assert "message" in result
        assert "data" in result

    def test_data_has_mode(self, service_no_key):
        self_j, other_j = self._two_decl_jsons(service_no_key)
        result = service_no_key.get_disposition(self_j, other_j, require_signature=False)
        assert "mode" in result["data"]
        assert result["data"]["mode"] in ["PROCEED", "REROUTE", "COMPLETE_AND_FLAG", "REFUSE"]

    def test_data_has_alignment_score(self, service_no_key):
        self_j, other_j = self._two_decl_jsons(service_no_key)
        result = service_no_key.get_disposition(self_j, other_j, require_signature=False)
        score = result["data"]["alignment_score"]
        assert 0.0 <= score <= 1.0

    def test_data_has_ror_after(self, service_no_key):
        self_j, other_j = self._two_decl_jsons(service_no_key)
        result = service_no_key.get_disposition(self_j, other_j, require_signature=False)
        assert "ror_after" in result["data"]
        assert "rate" in result["data"]["ror_after"]

    def test_unsigned_counterpart_refused_when_required(self, service_no_key):
        self_j, other_j = self._two_decl_jsons(service_no_key)
        result = service_no_key.get_disposition(
            self_j, other_j, require_signature=True  # counterpart is unsigned
        )
        assert result["data"]["mode"] == "REFUSE"

    def test_invalid_self_json_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        _, other_j = self._two_decl_jsons(service_no_key)
        with pytest.raises(ServiceError, match="self declaration"):
            service_no_key.get_disposition("{bad}", other_j)

    def test_invalid_counterpart_json_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        self_j, _ = self._two_decl_jsons(service_no_key)
        with pytest.raises(ServiceError, match="counterpart declaration"):
            service_no_key.get_disposition(self_j, "{bad}")

    def test_disposition_updates_ror(self, service_no_key):
        initial = service_no_key.get_ror_metrics()["data"]["total_dispositions"]
        self_j, other_j = self._two_decl_jsons(service_no_key)
        service_no_key.get_disposition(self_j, other_j, require_signature=False)
        after = service_no_key.get_ror_metrics()["data"]["total_dispositions"]
        assert after == initial + 1


# --- get_ror_metrics tests ----------------------------------------------

class TestGetRORMetrics:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.get_ror_metrics()
        assert "message" in result
        assert "data" in result

    def test_data_has_ror_rate(self, service_no_key):
        result = service_no_key.get_ror_metrics()
        assert "ror_rate" in result["data"]

    def test_data_has_counts(self, service_no_key):
        result = service_no_key.get_ror_metrics()
        assert "counts" in result["data"]
        counts = result["data"]["counts"]
        assert "PROCEED" in counts
        assert "REFUSE" in counts

    def test_data_has_interpretation(self, service_no_key):
        result = service_no_key.get_ror_metrics()
        assert "interpretation" in result["data"]

    def test_ror_zero_before_any_dispositions(self, service_no_key):
        result = service_no_key.get_ror_metrics()
        assert result["data"]["ror_rate"] == 0.0
        assert result["data"]["total_dispositions"] == 0


# --- Phase 3: Handshake session service tests ---------------------------

class TestInitiateHandshake:
    def _decl_json(self, service_no_key) -> str:
        r = service_no_key.declare_posture(
            "agent-a", "explain sources and reason transparently", sign=False
        )
        return json.dumps(r["data"]["declaration"])

    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.initiate_handshake(self._decl_json(service_no_key))
        assert "message" in result
        assert "data" in result

    def test_data_has_session_id(self, service_no_key):
        result = service_no_key.initiate_handshake(self._decl_json(service_no_key))
        assert "session_id" in result["data"]
        assert len(result["data"]["session_id"]) == 36

    def test_data_state_is_initiated(self, service_no_key):
        result = service_no_key.initiate_handshake(self._decl_json(service_no_key))
        assert result["data"]["state"] == "INITIATED"

    def test_data_has_initiator_id(self, service_no_key):
        result = service_no_key.initiate_handshake(self._decl_json(service_no_key))
        assert result["data"]["initiator_id"] == "agent-a"

    def test_invalid_json_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        with pytest.raises(ServiceError, match="initiator declaration"):
            service_no_key.initiate_handshake("{bad}")

    def test_message_contains_session_id(self, service_no_key):
        result = service_no_key.initiate_handshake(self._decl_json(service_no_key))
        session_id = result["data"]["session_id"]
        assert session_id in result["message"]


class TestRespondToHandshake:
    def _setup(self, service_no_key):
        r_a = service_no_key.declare_posture(
            "agent-a", "explain sources and reason transparently with integrity", sign=False
        )
        r_b = service_no_key.declare_posture(
            "agent-b", "explain sources and reason transparently with integrity", sign=False
        )
        a_json = json.dumps(r_a["data"]["declaration"])
        b_json = json.dumps(r_b["data"]["declaration"])
        init = service_no_key.initiate_handshake(a_json)
        session_id = init["data"]["session_id"]
        return session_id, b_json

    def test_returns_message_and_data(self, service_no_key):
        session_id, b_json = self._setup(service_no_key)
        result = service_no_key.respond_to_handshake(
            session_id, b_json, require_signature=False
        )
        assert "message" in result
        assert "data" in result

    def test_state_advances_to_responded(self, service_no_key):
        session_id, b_json = self._setup(service_no_key)
        result = service_no_key.respond_to_handshake(
            session_id, b_json, require_signature=False
        )
        assert result["data"]["state"] == "RESPONDED"

    def test_disposition_present(self, service_no_key):
        session_id, b_json = self._setup(service_no_key)
        result = service_no_key.respond_to_handshake(
            session_id, b_json, require_signature=False
        )
        assert result["data"]["disposition"] is not None
        assert "mode" in result["data"]["disposition"]

    def test_ror_updated_after_response(self, service_no_key):
        session_id, b_json = self._setup(service_no_key)
        before = service_no_key.get_ror_metrics()["data"]["total_dispositions"]
        service_no_key.respond_to_handshake(session_id, b_json, require_signature=False)
        after = service_no_key.get_ror_metrics()["data"]["total_dispositions"]
        assert after == before + 1

    def test_invalid_session_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        r = service_no_key.declare_posture("b", "context", sign=False)
        b_json = json.dumps(r["data"]["declaration"])
        with pytest.raises(ServiceError):
            service_no_key.respond_to_handshake("no-such-id", b_json, require_signature=False)

    def test_responding_twice_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        session_id, b_json = self._setup(service_no_key)
        service_no_key.respond_to_handshake(session_id, b_json, require_signature=False)
        with pytest.raises(ServiceError):
            service_no_key.respond_to_handshake(session_id, b_json, require_signature=False)


class TestGetHandshakeResult:
    def test_retrieves_initiated_session(self, service_no_key):
        r = service_no_key.declare_posture("a", "explain sources", sign=False)
        a_json = json.dumps(r["data"]["declaration"])
        init = service_no_key.initiate_handshake(a_json)
        session_id = init["data"]["session_id"]

        result = service_no_key.get_handshake_result(session_id)
        assert "message" in result
        assert result["data"]["session_id"] == session_id

    def test_invalid_session_id_raises(self, service_no_key):
        from mcp_server.service import ServiceError
        with pytest.raises(ServiceError):
            service_no_key.get_handshake_result("nonexistent")

    def test_disposition_present_after_respond(self, service_no_key):
        r_a = service_no_key.declare_posture("a", "explain sources transparently", sign=False)
        r_b = service_no_key.declare_posture("b", "explain sources transparently", sign=False)
        a_json = json.dumps(r_a["data"]["declaration"])
        b_json = json.dumps(r_b["data"]["declaration"])
        init = service_no_key.initiate_handshake(a_json)
        session_id = init["data"]["session_id"]
        service_no_key.respond_to_handshake(session_id, b_json, require_signature=False)

        result = service_no_key.get_handshake_result(session_id)
        assert result["data"]["disposition"] is not None


class TestListSessions:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.list_sessions()
        assert "message" in result
        assert "data" in result

    def test_empty_sessions_list(self, service_no_key):
        result = service_no_key.list_sessions()
        assert result["data"]["sessions"] == []
        assert result["data"]["total_in_store"] == 0

    def test_sessions_after_initiate(self, service_no_key):
        r = service_no_key.declare_posture("a", "explain sources", sign=False)
        a_json = json.dumps(r["data"]["declaration"])
        service_no_key.initiate_handshake(a_json)
        result = service_no_key.list_sessions()
        assert result["data"]["total_in_store"] == 1
        assert len(result["data"]["sessions"]) == 1

    def test_newest_first(self, service_no_key):
        for agent in ["a", "b", "c"]:
            r = service_no_key.declare_posture(agent, "explain sources", sign=False)
            service_no_key.initiate_handshake(json.dumps(r["data"]["declaration"]))
        result = service_no_key.list_sessions()
        sessions = result["data"]["sessions"]
        # Newest (c) should be first
        assert sessions[0]["initiator_id"] == "c"


# --- Phase 4: Reporting & Persistence service tests ---------------------

class TestGetEventJournal:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.get_event_journal()
        assert "message" in result
        assert "data" in result

    def test_empty_journal(self, service_no_key):
        result = service_no_key.get_event_journal()
        assert "data" in result
        assert "entries" in result["data"]
        assert "total_lines" in result["data"]

    def test_journal_populated_after_declare(self, service_no_key):
        # declare_posture logs events to journal
        service_no_key.declare_posture("agent-x", "explain sources", sign=False)
        result = service_no_key.get_event_journal(n=10)
        assert result["data"]["returned"] >= 1

    def test_category_filter_applied(self, service_no_key):
        service_no_key.declare_posture("agent-x", "explain sources", sign=False)
        result = service_no_key.get_event_journal(n=50, category="DECLARATION")
        assert result["data"]["category_filter"] == "DECLARATION"
        for entry in result["data"]["entries"]:
            assert entry["category"] == "DECLARATION"

    def test_n_limits_results(self, service_no_key):
        for i in range(5):
            service_no_key.declare_posture(f"agent-{i}", "explain sources", sign=False)
        result = service_no_key.get_event_journal(n=2)
        assert result["data"]["returned"] <= 2

    def test_data_has_total_lines(self, service_no_key):
        result = service_no_key.get_event_journal()
        assert isinstance(result["data"]["total_lines"], int)


class TestExportSessionReport:
    def _make_session(self, service_no_key) -> str:
        r = service_no_key.declare_posture("agent-a", "explain sources transparently", sign=False)
        a_json = json.dumps(r["data"]["declaration"])
        init = service_no_key.initiate_handshake(a_json)
        return init["data"]["session_id"]

    def test_returns_message_and_data(self, service_no_key):
        session_id = self._make_session(service_no_key)
        result = service_no_key.export_session_report(session_id)
        assert "message" in result
        assert "data" in result

    def test_message_is_markdown(self, service_no_key):
        session_id = self._make_session(service_no_key)
        result = service_no_key.export_session_report(session_id)
        assert "# Handshake Session Report" in result["message"]

    def test_report_type_is_session(self, service_no_key):
        session_id = self._make_session(service_no_key)
        result = service_no_key.export_session_report(session_id)
        assert result["data"]["report_type"] == "session"

    def test_invalid_session_id_raises(self, service_no_key):
        from mcp_server.service import SessionNotFoundError
        with pytest.raises(SessionNotFoundError):
            service_no_key.export_session_report("no-such-id")

    def test_session_id_in_message(self, service_no_key):
        session_id = self._make_session(service_no_key)
        result = service_no_key.export_session_report(session_id)
        assert session_id in result["message"]


class TestExportRorReport:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.export_ror_report()
        assert "message" in result
        assert "data" in result

    def test_report_type_is_ror_trend(self, service_no_key):
        result = service_no_key.export_ror_report()
        assert result["data"]["report_type"] == "ror_trend"

    def test_empty_ror_message(self, service_no_key):
        result = service_no_key.export_ror_report()
        assert "ROR Trend Report" in result["message"]

    def test_ror_populated_after_disposition(self, service_no_key):
        r_a = service_no_key.declare_posture("a", "explain sources transparently", sign=False)
        r_b = service_no_key.declare_posture("b", "explain sources transparently", sign=False)
        a_json = json.dumps(r_a["data"]["declaration"])
        b_json = json.dumps(r_b["data"]["declaration"])
        init = service_no_key.initiate_handshake(a_json)
        service_no_key.respond_to_handshake(
            init["data"]["session_id"], b_json, require_signature=False
        )
        result = service_no_key.export_ror_report()
        assert result["data"]["trend"]["snapshot_count"] >= 1


class TestGetSummary:
    def test_returns_message_and_data(self, service_no_key):
        result = service_no_key.get_summary()
        assert "message" in result
        assert "data" in result

    def test_report_type_is_summary(self, service_no_key):
        result = service_no_key.get_summary()
        assert result["data"]["report_type"] == "summary"

    def test_message_contains_header(self, service_no_key):
        result = service_no_key.get_summary()
        assert "10+1 Protocol" in result["message"]

    def test_data_has_sessions(self, service_no_key):
        result = service_no_key.get_summary()
        assert "sessions" in result["data"]
        assert "total" in result["data"]["sessions"]

    def test_data_has_ror(self, service_no_key):
        result = service_no_key.get_summary()
        assert "ror" in result["data"]

    def test_data_has_journal(self, service_no_key):
        result = service_no_key.get_summary()
        assert "journal" in result["data"]

    def test_session_count_reflects_reality(self, service_no_key):
        for i in range(3):
            r = service_no_key.declare_posture(f"a{i}", "explain sources", sign=False)
            service_no_key.initiate_handshake(json.dumps(r["data"]["declaration"]))
        result = service_no_key.get_summary()
        assert result["data"]["sessions"]["total"] == 3
