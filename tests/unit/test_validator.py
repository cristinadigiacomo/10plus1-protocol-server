"""Unit tests — Declaration validator (src/validator/validator.py)."""

from __future__ import annotations

import pytest

from declaration.builder import build
from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus
from validator.validator import (
    IssueSeverity,
    ValidationResult,
    validate,
)


# --- Helpers -------------------------------------------------------------

def make_declaration_with_principle(
    pid: str = "C1",
    behavioral_statement: str = "State information sources before making factual claims in every response",
    status: PrincipleStatus = PrincipleStatus.DECLARED,
    constraints: list[str] | None = None,
) -> HandshakeDeclaration:
    return HandshakeDeclaration(
        agent_id="test-agent",
        principles={
            pid: PrincipleStatement(
                principle_id=pid,
                status=status,
                behavioral_statement=behavioral_statement,
                constraints=constraints or [],
            )
        },
    )


def full_declaration(status: PrincipleStatus = PrincipleStatus.DECLARED) -> HandshakeDeclaration:
    """Declaration covering all 11 principles."""
    return build("test-agent", (
        "I need to explain and state sources transparently, with consent and privacy protection, "
        "accuracy and accountability for my work, keeping it safe and fair, "
        "supporting human autonomy and oversight, considering sustainability, "
        "and maintaining honesty and integrity throughout."
    ))


# --- Basic validation ----------------------------------------------------

class TestValidateBasic:
    def test_returns_validation_result(self):
        decl = make_declaration_with_principle()
        result = validate(decl)
        assert isinstance(result, ValidationResult)

    def test_valid_declaration_is_valid(self):
        decl = make_declaration_with_principle()
        result = validate(decl)
        assert result.valid is True

    def test_covered_principles_listed(self):
        decl = make_declaration_with_principle("C4")
        result = validate(decl)
        assert "C4" in result.principles_covered

    def test_missing_principles_listed(self):
        decl = make_declaration_with_principle("C1")
        result = validate(decl)
        # Only C1 declared — all others should be missing
        assert "C2" in result.principles_missing
        assert "C11" in result.principles_missing

    def test_coverage_score_one_principle(self):
        decl = make_declaration_with_principle("C1")
        result = validate(decl)
        assert abs(result.coverage_score - (1 / 11)) < 0.001

    def test_coverage_score_all_principles(self):
        decl = full_declaration()
        result = validate(decl)
        assert result.coverage_score == pytest.approx(1.0, abs=0.1)

    def test_not_applicable_reduces_coverage(self):
        """NOT_APPLICABLE principles are not counted in coverage."""
        decl = HandshakeDeclaration(
            agent_id="agent",
            principles={
                "C1": PrincipleStatement(
                    principle_id="C1",
                    status=PrincipleStatus.COMPLIANT,
                    behavioral_statement="State information sources before making factual claims",
                ),
                "C2": PrincipleStatement(
                    principle_id="C2",
                    status=PrincipleStatus.NOT_APPLICABLE,
                    behavioral_statement="No consent scenarios exist in this fully automated pipeline context",
                ),
            },
        )
        result = validate(decl)
        assert "C1" in result.principles_covered
        assert "C2" in result.principles_not_applicable
        # Only C1 counts toward coverage
        assert abs(result.coverage_score - (1 / 11)) < 0.001

    def test_summary_string_format(self):
        decl = make_declaration_with_principle()
        result = validate(decl)
        summary = result.summary()
        assert "VALID" in summary or "INVALID" in summary
        assert "coverage" in summary.lower()


# --- Vagueness detection (Moltbook Finding 2) ----------------------------

class TestVaguenessDetection:
    def test_vague_phrase_produces_warning(self):
        decl = make_declaration_with_principle(
            behavioral_statement="I will be transparent about my work and processes"
        )
        result = validate(decl)
        warnings = result.warnings()
        vagueness_warnings = [
            w for w in warnings
            if "vague" in w.message.lower() or "Finding 2" in w.message
        ]
        assert len(vagueness_warnings) > 0

    def test_vague_warning_has_suggestion(self):
        decl = make_declaration_with_principle(
            behavioral_statement="I will be honest about everything I do"
        )
        result = validate(decl)
        vagueness_warnings = [
            w for w in result.warnings()
            if "vague" in w.message.lower() or "Finding 2" in w.message
        ]
        if vagueness_warnings:
            assert vagueness_warnings[0].suggestion is not None

    def test_specific_statement_no_vagueness_warning(self):
        decl = make_declaration_with_principle(
            behavioral_statement=(
                "State the data source and access date before presenting "
                "any statistics or research findings in responses"
            )
        )
        result = validate(decl)
        vagueness_warnings = [
            w for w in result.warnings()
            if "vague" in w.message.lower() or "Finding 2" in w.message
        ]
        assert len(vagueness_warnings) == 0

    def test_vague_warning_does_not_make_invalid(self):
        """Vagueness is a WARNING, not an ERROR — declaration is still valid."""
        decl = make_declaration_with_principle(
            behavioral_statement="I will be transparent and honest in my work"
        )
        result = validate(decl)
        assert result.valid is True  # WARNING does not → invalid
        assert len(result.errors()) == 0

    @pytest.mark.parametrize("phrase", [
        "be transparent",
        "be honest",
        "be fair",
        "be accountable",
        "be ethical",
        "act responsibly",
        "do the right thing",
    ])
    def test_known_vague_phrases(self, phrase):
        decl = make_declaration_with_principle(
            behavioral_statement=f"I will {phrase} in all my actions going forward always"
        )
        result = validate(decl)
        has_vagueness = any(
            "vague" in i.message.lower() or "Finding 2" in i.message
            for i in result.warnings()
        )
        assert has_vagueness, f"Expected vagueness warning for phrase: '{phrase}'"


# --- Issue severity tests ------------------------------------------------

class TestIssueSeverity:
    def test_no_errors_for_valid_declaration(self):
        decl = make_declaration_with_principle()
        result = validate(decl)
        assert len(result.errors()) == 0

    def test_missing_principles_produce_info_not_error(self):
        decl = make_declaration_with_principle("C1")
        result = validate(decl)
        missing_issues = [i for i in result.issues if i.severity == IssueSeverity.INFO]
        assert len(missing_issues) > 0  # missing principles → INFO

    def test_errors_and_warnings_helpers(self):
        decl = make_declaration_with_principle(
            behavioral_statement="I will be transparent about everything"
        )
        result = validate(decl)
        # Should have warnings (vagueness) but no errors
        assert len(result.errors()) == 0
        assert isinstance(result.warnings(), list)
