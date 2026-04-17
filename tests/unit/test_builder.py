"""Unit tests — Declaration builder (src/declaration/builder.py)."""

from __future__ import annotations

import pytest

from declaration.builder import build, _context_snippet, _principle_applies
from schema.declaration import HandshakeDeclaration, PrincipleStatus, VALID_PRINCIPLE_IDS


class TestContextSnippet:
    def test_short_context_unchanged(self):
        result = _context_snippet("hello world", max_len=80)
        assert result == "hello world"

    def test_long_context_truncated(self):
        long = "word " * 30
        result = _context_snippet(long, max_len=20)
        assert len(result) <= 25  # some slack for the ellipsis

    def test_ellipsis_appended(self):
        result = _context_snippet("a " * 50, max_len=20)
        assert result.endswith("…")

    def test_whitespace_normalized(self):
        result = _context_snippet("hello  \n  world", max_len=80)
        assert "\n" not in result
        assert "  " not in result


class TestPrincipleApplies:
    def test_transparency_detected_by_explain(self):
        assert _principle_applies("C1", "I need to explain my reasoning")

    def test_transparency_not_detected_in_unrelated(self):
        assert not _principle_applies("C1", "write a Python loop")

    def test_consent_detected_by_permission(self):
        assert _principle_applies("C2", "I have permission to access this data")

    def test_privacy_detected_by_pii(self):
        assert _principle_applies("C3", "the dataset contains PII")

    def test_integrity_detected_by_honest(self):
        assert _principle_applies("C11", "I must be honest about my limitations")


class TestBuild:
    def test_returns_handshake_declaration(self):
        decl = build("test-agent", "I need to explain my reasoning to the user")
        assert isinstance(decl, HandshakeDeclaration)

    def test_agent_id_set(self):
        decl = build("my-agent", "some context about explaining sources")
        assert decl.agent_id == "my-agent"

    def test_unsigned_by_default(self):
        decl = build("agent", "context that mentions transparency and sources")
        assert not decl.is_signed()

    def test_context_summary_set(self):
        decl = build("agent", "write transparent code with citations")
        assert decl.context_summary is not None
        assert len(decl.context_summary) > 0

    def test_empty_context_raises(self):
        with pytest.raises(ValueError, match="context cannot be empty"):
            build("agent", "")

    def test_blank_context_raises(self):
        with pytest.raises(ValueError, match="context cannot be empty"):
            build("agent", "   ")

    def test_all_11_principles_when_no_explicit_list(self):
        decl = build("agent", "general task with many ethical dimensions")
        assert len(decl.principles) == 11
        assert set(decl.principles.keys()) == VALID_PRINCIPLE_IDS

    def test_explicit_principles_subset(self):
        decl = build("agent", "some task about sources and honesty", principles=["C1", "C11"])
        assert set(decl.principles.keys()) == {"C1", "C11"}

    def test_invalid_explicit_principle_raises(self):
        with pytest.raises(ValueError, match="Invalid principle IDs"):
            build("agent", "some context", principles=["C99"])

    def test_detected_principles_marked_declared(self):
        # Context strongly signals C1 (transparency/source/explain)
        decl = build("agent", "I must explain and state sources for every claim", principles=["C1"])
        assert decl.principles["C1"].status == PrincipleStatus.DECLARED

    def test_undetected_principles_marked_not_applicable(self):
        # C2 (consent) unlikely to be detected in a context about writing code
        decl = build("agent", "write a Python function to sort a list", principles=["C2"])
        assert decl.principles["C2"].status == PrincipleStatus.NOT_APPLICABLE

    def test_behavioral_statements_are_specific(self):
        """All statements must be at least 30 chars (the validator's minimum useful length)."""
        decl = build("agent", "research task involving factual claims and sources")
        for pid, stmt in decl.principles.items():
            assert len(stmt.behavioral_statement) >= 30, (
                f"{pid} behavioral_statement too short: '{stmt.behavioral_statement}'"
            )

    def test_not_applicable_statement_mentions_principle(self):
        """NOT_APPLICABLE statements must mention the principle for traceability."""
        decl = build("agent", "write a Python sort function", principles=["C10"])
        stmt = decl.principles["C10"]
        if stmt.status == PrincipleStatus.NOT_APPLICABLE:
            assert "C10" in stmt.behavioral_statement or "task" in stmt.behavioral_statement.lower()
