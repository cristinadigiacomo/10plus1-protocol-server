"""Unit tests — HandshakeDeclaration schema (src/schema/declaration.py)."""

from __future__ import annotations

import json
import pytest

from schema.declaration import (
    HandshakeDeclaration,
    PrincipleStatement,
    PrincipleStatus,
    VALID_PRINCIPLE_IDS,
)


# --- Helpers -------------------------------------------------------------

def make_statement(
    principle_id: str = "C1",
    status: PrincipleStatus = PrincipleStatus.DECLARED,
    behavioral_statement: str = "State information sources before making factual claims",
    constraints: list[str] | None = None,
) -> PrincipleStatement:
    return PrincipleStatement(
        principle_id=principle_id,
        status=status,
        behavioral_statement=behavioral_statement,
        constraints=constraints or [],
    )


def make_declaration(
    agent_id: str = "test-agent",
    principles: dict[str, PrincipleStatement] | None = None,
) -> HandshakeDeclaration:
    if principles is None:
        principles = {"C1": make_statement("C1")}
    return HandshakeDeclaration(agent_id=agent_id, principles=principles)


# --- PrincipleStatement tests --------------------------------------------

class TestPrincipleStatement:
    def test_valid_statement(self):
        stmt = make_statement()
        assert stmt.principle_id == "C1"
        assert stmt.status == PrincipleStatus.DECLARED

    def test_invalid_principle_id(self):
        with pytest.raises(ValueError, match="not a valid 10\\+1 principle"):
            PrincipleStatement(
                principle_id="C99",
                status=PrincipleStatus.DECLARED,
                behavioral_statement="Some statement that is long enough",
            )

    def test_behavioral_statement_too_short(self):
        with pytest.raises(ValueError):
            PrincipleStatement(
                principle_id="C1",
                status=PrincipleStatus.DECLARED,
                behavioral_statement="short",  # less than 10 chars
            )

    def test_whitespace_stripped(self):
        stmt = PrincipleStatement(
            principle_id="C1",
            status=PrincipleStatus.DECLARED,
            behavioral_statement="  State sources before claims  ",
        )
        assert stmt.behavioral_statement == "State sources before claims"

    def test_all_statuses_accepted(self):
        for status in PrincipleStatus:
            stmt = make_statement(status=status)
            assert stmt.status == status

    def test_constraints_default_empty(self):
        stmt = make_statement()
        assert stmt.constraints == []

    def test_constraints_stored(self):
        stmt = make_statement(constraints=["No access to real-time data"])
        assert stmt.constraints == ["No access to real-time data"]


# --- HandshakeDeclaration tests ------------------------------------------

class TestHandshakeDeclaration:
    def test_minimal_valid_declaration(self):
        decl = make_declaration()
        assert decl.agent_id == "test-agent"
        assert "C1" in decl.principles
        assert decl.id is not None
        assert decl.declared_at is not None

    def test_auto_uuid(self):
        d1 = make_declaration()
        d2 = make_declaration()
        assert d1.id != d2.id

    def test_blank_agent_id_rejected(self):
        with pytest.raises(ValueError, match="agent_id cannot be blank"):
            HandshakeDeclaration(agent_id="   ", principles={"C1": make_statement()})

    def test_key_mismatch_rejected(self):
        """principles dict key must match the statement's principle_id."""
        stmt = make_statement("C1")
        with pytest.raises(ValueError, match="must match the dict key"):
            HandshakeDeclaration(agent_id="agent", principles={"C4": stmt})

    def test_invalid_key_rejected(self):
        # Pydantic v2 rejects C99 at PrincipleStatement validation level;
        # the error is wrapped in a ValidationError whose str contains "10+1 principle".
        with pytest.raises(Exception, match="10.1 principle"):
            HandshakeDeclaration(
                agent_id="agent",
                principles={"C99": make_statement("C99")},
            )

    def test_is_signed_false_by_default(self):
        decl = make_declaration()
        assert not decl.is_signed()

    def test_is_signed_true_when_fields_set(self):
        decl = make_declaration()
        signed = decl.model_copy(update={
            "signature": "a" * 64,
            "signed_at": "2026-04-17T00:00:00+00:00",
        })
        assert signed.is_signed()

    def test_coverage_one_principle(self):
        decl = make_declaration()
        assert decl.coverage() == pytest.approx(1 / 11)

    def test_coverage_eleven_principles(self):
        principles = {
            pid: make_statement(pid)
            for pid in sorted(VALID_PRINCIPLE_IDS)
        }
        decl = make_declaration(principles=principles)
        assert decl.coverage() == pytest.approx(1.0)

    def test_signing_payload_excludes_signature(self):
        decl = make_declaration()
        payload = json.loads(decl.signing_payload())
        assert "signature" not in payload
        assert "signed_at" not in payload
        assert "agent_id" in payload

    def test_model_dump_roundtrip(self):
        decl = make_declaration()
        dumped = decl.model_dump(mode="json")
        restored = HandshakeDeclaration.model_validate(dumped)
        assert restored.id == decl.id
        assert restored.agent_id == decl.agent_id
