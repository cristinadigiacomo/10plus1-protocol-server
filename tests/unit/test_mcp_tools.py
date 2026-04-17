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

    def test_phase_is_1(self, service_no_key):
        result = service_no_key.get_server_info()
        assert result["data"]["phase"] == 1

    def test_tools_listed(self, service_no_key):
        result = service_no_key.get_server_info()
        tools = result["data"]["tools"]
        assert "declare_posture" in tools
        assert "validate_declaration" in tools
        assert "embed_posture" in tools

    def test_event_count_increments(self, service_no_key):
        initial = service_no_key.get_server_info()["data"]["event_count"]
        service_no_key.declare_posture("agent", "some context with sources", sign=False)
        after = service_no_key.get_server_info()["data"]["event_count"]
        assert after > initial
