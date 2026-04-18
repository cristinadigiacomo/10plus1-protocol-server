"""Unit tests — Contextual embedder (src/declaration/embedder.py)."""

from __future__ import annotations

import pytest

from declaration.builder import build
from declaration.embedder import embed, embed_minimal
from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus


# --- Helpers -------------------------------------------------------------

def make_declaration(agent_id: str = "test-agent", context: str = "write transparent code with sources") -> HandshakeDeclaration:
    return build(agent_id, context, principles=["C1", "C4", "C11"])


# --- embed() tests -------------------------------------------------------

class TestEmbed:
    def test_returns_string(self):
        decl = make_declaration()
        result = embed(decl, "Please analyze this dataset.")
        assert isinstance(result, str)

    def test_original_prompt_included(self):
        decl = make_declaration()
        prompt = "Please analyze this dataset with full citations."
        result = embed(decl, prompt)
        assert "Please analyze this dataset with full citations." in result

    def test_not_a_header_block(self):
        """Critical: must not produce a header block pattern."""
        decl = make_declaration()
        result = embed(decl, "some task")
        assert "[POSTURE DECLARATION]" not in result
        assert "[END POSTURE DECLARATION]" not in result
        assert "POSTURE DECLARATION" not in result

    def test_agent_id_present(self):
        decl = make_declaration(agent_id="my-agent")
        result = embed(decl, "do something")
        assert "my-agent" in result

    def test_principle_names_present(self):
        decl = make_declaration()
        result = embed(decl, "task")
        # At least one active principle name should appear
        assert any(
            name in result
            for name in ["Own AI's Outcomes", "Never Use AI for Conflict", "Be the Steward, Not the Master"]
        )

    def test_separator_present(self):
        decl = make_declaration()
        result = embed(decl, "task")
        assert "—" in result  # separator between posture framing and prompt

    def test_not_applicable_principles_not_listed(self):
        """Principles with NOT_APPLICABLE status should not appear as bullet points."""
        # Build with explicit principles where C10 (sustainability) is unlikely to fire
        decl = build("agent", "write transparent code with citations", principles=["C1", "C10"])
        result = embed(decl, "analyze data")
        # C10 (Honor and Care for Potential Sentience) should not appear as a bullet if NOT_APPLICABLE
        if decl.principles["C10"].status == PrincipleStatus.NOT_APPLICABLE:
            # The name might appear in context_summary but not as a bullet commitment
            lines = result.split("\n")
            bullet_lines = [l for l in lines if l.strip().startswith("•")]
            bullet_text = " ".join(bullet_lines)
            assert "Honor and Care for Potential Sentience" not in bullet_text

    def test_signed_declaration_shows_signature_note(self):
        from signer.signer import sign_declaration
        import secrets
        key = secrets.token_bytes(32)
        decl = make_declaration()
        signed = sign_declaration(decl, key)
        result = embed(signed, "do something")
        assert "signed at" in result.lower() or "Declaration" in result

    def test_constraints_appear_when_present(self):
        from schema.declaration import HandshakeDeclaration
        decl = HandshakeDeclaration(
            agent_id="agent",
            principles={
                "C1": PrincipleStatement(
                    principle_id="C1",
                    status=PrincipleStatus.DECLARED,
                    behavioral_statement="State information sources before making factual claims",
                    constraints=["No access to real-time data sources"],
                )
            },
        )
        result = embed(decl, "task")
        assert "No access to real-time data sources" in result

    def test_empty_declaration_still_works(self):
        """A declaration with all NOT_APPLICABLE principles should still embed cleanly."""
        from schema.declaration import HandshakeDeclaration
        decl = HandshakeDeclaration(
            agent_id="agent",
            principles={
                "C1": PrincipleStatement(
                    principle_id="C1",
                    status=PrincipleStatus.NOT_APPLICABLE,
                    behavioral_statement="Not applicable to this task context",
                )
            },
        )
        result = embed(decl, "just write a hello world program")
        assert "just write a hello world program" in result


# --- embed_minimal() tests -----------------------------------------------

class TestEmbedMinimal:
    def test_shorter_than_full(self):
        decl = make_declaration()
        prompt = "do something"
        full = embed(decl, prompt)
        minimal = embed_minimal(decl, prompt)
        assert len(minimal) < len(full)

    def test_prompt_included(self):
        decl = make_declaration()
        prompt = "analyze the data carefully"
        result = embed_minimal(decl, prompt)
        assert "analyze the data carefully" in result

    def test_agent_id_present(self):
        decl = make_declaration(agent_id="compact-agent")
        result = embed_minimal(decl, "task")
        assert "compact-agent" in result

    def test_all_not_applicable_returns_prompt_unchanged(self):
        from schema.declaration import HandshakeDeclaration
        decl = HandshakeDeclaration(
            agent_id="agent",
            principles={
                "C1": PrincipleStatement(
                    principle_id="C1",
                    status=PrincipleStatus.NOT_APPLICABLE,
                    behavioral_statement="Not applicable to this context at all",
                )
            },
        )
        result = embed_minimal(decl, "original prompt text")
        assert result == "original prompt text"
