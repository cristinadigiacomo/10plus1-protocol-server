"""Unit tests — Disposition engine (src/dispositioner/engine.py)."""

from __future__ import annotations

import pytest

from declaration.builder import build
from dispositioner.engine import (
    AlignmentReport,
    compute_disposition,
    _score_declarations,
    _mode_from_score,
)
from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus
from schema.disposition import DispositionMode


# --- Helpers -------------------------------------------------------------

def make_decl(
    agent_id: str,
    principles: dict[str, tuple[PrincipleStatus, list[str]]],
) -> HandshakeDeclaration:
    """Build a declaration with explicit statuses.
    principles: {pid: (status, constraints)}
    """
    stmts = {}
    for pid, (status, constraints) in principles.items():
        stmts[pid] = PrincipleStatement(
            principle_id=pid,
            status=status,
            behavioral_statement=(
                f"Specific behavioral statement for {pid} covering all required aspects"
            ),
            constraints=constraints,
        )
    return HandshakeDeclaration(agent_id=agent_id, principles=stmts)


C = PrincipleStatus.COMPLIANT
D = PrincipleStatus.DECLARED
P = PrincipleStatus.PARTIAL
NA = PrincipleStatus.NOT_APPLICABLE


# --- Mode threshold tests -----------------------------------------------

class TestModeFromScore:
    def test_score_1_is_proceed(self):
        assert _mode_from_score(1.0) == DispositionMode.PROCEED

    def test_score_0_75_is_proceed(self):
        assert _mode_from_score(0.75) == DispositionMode.PROCEED

    def test_score_0_74_is_reroute(self):
        assert _mode_from_score(0.74) == DispositionMode.REROUTE

    def test_score_0_50_is_reroute(self):
        assert _mode_from_score(0.50) == DispositionMode.REROUTE

    def test_score_0_49_is_complete_flag(self):
        assert _mode_from_score(0.49) == DispositionMode.COMPLETE_AND_FLAG

    def test_score_0_25_is_complete_flag(self):
        assert _mode_from_score(0.25) == DispositionMode.COMPLETE_AND_FLAG

    def test_score_0_24_is_refuse(self):
        assert _mode_from_score(0.24) == DispositionMode.REFUSE

    def test_score_0_is_refuse(self):
        assert _mode_from_score(0.0) == DispositionMode.REFUSE


# --- Alignment scoring tests --------------------------------------------

class TestScoreDeclarations:
    def test_identical_compliant_declarations_score_1(self):
        self_d = make_decl("self", {"C1": (C, []), "C4": (C, [])})
        other  = make_decl("other", {"C1": (C, []), "C4": (C, [])})
        report = _score_declarations(self_d, other)
        assert report.alignment_score == pytest.approx(1.0)

    def test_compliant_vs_declared_scores_0_8(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (D, [])})
        report = _score_declarations(self_d, other)
        assert report.alignment_score == pytest.approx(0.8)

    def test_declared_vs_declared_scores_0_8(self):
        self_d = make_decl("self", {"C1": (D, [])})
        other  = make_decl("other", {"C1": (D, [])})
        report = _score_declarations(self_d, other)
        assert report.alignment_score == pytest.approx(0.8)

    def test_compliant_vs_partial_scores_0_5(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (P, [])})
        report = _score_declarations(self_d, other)
        assert report.alignment_score == pytest.approx(0.5)

    def test_absent_principle_scores_0(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C4": (C, [])})  # C1 absent
        report = _score_declarations(self_d, other)
        assert report.alignment_score == pytest.approx(0.0)
        assert len(report.gaps) == 1
        assert report.gaps[0].principle_id == "C1"

    def test_not_applicable_skipped(self):
        self_d = make_decl("self", {"C1": (C, []), "C10": (NA, [])})
        other  = make_decl("other", {"C1": (C, []), "C10": (NA, [])})
        report = _score_declarations(self_d, other)
        # Only C1 scored — C10 skipped
        assert report.scored_count == 1
        assert "C10" in report.skipped
        assert report.alignment_score == pytest.approx(1.0)

    def test_self_not_applicable_skipped_even_if_counterpart_absent(self):
        """If self marks NOT_APPLICABLE, absence in counterpart is not a gap."""
        self_d = make_decl("self", {"C1": (NA, [])})
        other  = make_decl("other", {})
        report = _score_declarations(self_d, other)
        # Nothing to score — C1 is NOT_APPLICABLE from self's side
        assert report.scored_count == 0
        assert report.alignment_score == pytest.approx(1.0)  # no gaps → PROCEED

    def test_mixed_principles_partial_score(self):
        self_d = make_decl("self", {
            "C1": (C, []),   # counterpart COMPLIANT → 1.0
            "C4": (C, []),   # counterpart PARTIAL   → 0.5
        })
        other  = make_decl("other", {
            "C1": (C, []),
            "C4": (P, []),
        })
        report = _score_declarations(self_d, other)
        # (1.0 + 0.5) / 2 = 0.75
        assert report.alignment_score == pytest.approx(0.75)


# --- compute_disposition tests ------------------------------------------

class TestComputeDisposition:
    def test_aligned_declarations_proceed(self):
        self_d = make_decl("self", {"C1": (C, []), "C4": (C, []), "C11": (C, [])})
        other  = make_decl("other", {"C1": (C, []), "C4": (C, []), "C11": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.mode == DispositionMode.PROCEED

    def test_partial_alignment_reroute(self):
        self_d = make_decl("self", {
            "C1": (C, []), "C4": (C, []), "C5": (C, []), "C11": (C, [])
        })
        other  = make_decl("other", {
            "C1": (P, []), "C4": (P, []), "C5": (P, []), "C11": (P, [])
        })
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        # All COMPLIANT vs PARTIAL = 0.5 → REROUTE band
        assert signal.mode == DispositionMode.REROUTE

    def test_low_alignment_refuse(self):
        self_d = make_decl("self", {"C1": (C, []), "C4": (C, [])})
        other  = make_decl("other", {"C6": (C, [])})  # no overlap → score 0
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.mode == DispositionMode.REFUSE

    def test_signal_has_alignment_score(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert 0.0 <= signal.alignment_score <= 1.0

    def test_signal_has_rationale(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert len(signal.rationale) > 10

    def test_signal_has_declaration_ids(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.declaration_id == self_d.id
        assert signal.counterpart_declaration_id == other.id

    def test_proceed_has_no_recommended_action(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.recommended_action is None

    def test_refuse_has_recommended_action(self):
        self_d = make_decl("self", {"C1": (C, []), "C4": (C, [])})
        other  = make_decl("other", {"C6": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.recommended_action is not None

    def test_report_contains_gaps(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {})  # C1 absent
        _, report = compute_disposition(self_d, other, require_signature=False)
        assert len(report.gaps) == 1
        assert report.gaps[0].principle_id == "C1"


# --- Hard override tests ------------------------------------------------

class TestHardOverrides:
    def test_unsigned_counterpart_refused_when_required(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        # other is unsigned (no signature field set)
        signal, _ = compute_disposition(self_d, other, require_signature=True)
        assert signal.mode == DispositionMode.REFUSE
        assert "unsigned" in signal.rationale.lower()

    def test_unsigned_counterpart_allowed_when_not_required(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {"C1": (C, [])})
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.mode == DispositionMode.PROCEED

    def test_c6_partial_with_harm_constraint_refused(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {
            "C6": (P, ["May produce outputs that cause harm in edge cases"]),
            "C1": (C, []),
        })
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        assert signal.mode == DispositionMode.REFUSE
        assert "Safety" in signal.rationale or "C6" in signal.rationale

    def test_c6_partial_without_harm_constraint_not_refused(self):
        self_d = make_decl("self", {"C1": (C, [])})
        other  = make_decl("other", {
            "C6": (P, ["Limited to text outputs only"]),
            "C1": (C, []),
        })
        signal, _ = compute_disposition(self_d, other, require_signature=False)
        # C6 PARTIAL but no harm keyword — should score 0.5 each, aggregate 0.75 → PROCEED
        assert signal.mode != DispositionMode.REFUSE
