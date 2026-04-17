"""
Phase 2 — Four-mode disposition engine.

Given two validated HandshakeDeclarations (self + counterpart), produces a
DispositionSignal telling the initiating agent how to proceed.

Scoring model
-------------
Each principle present in the self declaration is scored against the
counterpart's declaration:

  COMPLIANT vs COMPLIANT          → 1.0  (full match)
  COMPLIANT vs DECLARED           → 0.8  (near match)
  DECLARED  vs DECLARED           → 0.8  (near match)
  COMPLIANT vs PARTIAL            → 0.5  (partial)
  DECLARED  vs PARTIAL            → 0.5  (partial)
  PARTIAL   vs PARTIAL            → 0.5  (partial)
  Either NOT_APPLICABLE           → skip (not scored — not a gap)
  Absent from counterpart         → 0.0  (gap)

Aggregate alignment score = sum of scores / number of scored principles.
Principles where both sides are NOT_APPLICABLE do not count toward the
denominator — they cannot create gaps in a declaration about something
that doesn't apply to either party.

Mode thresholds
---------------
  score >= 0.75  →  PROCEED
  score >= 0.50  →  REROUTE
  score >= 0.25  →  COMPLETE_AND_FLAG
  score <  0.25  →  REFUSE

Hard overrides (applied before scoring)
----------------------------------------
  1. Counterpart declaration fails schema validation → REFUSE
  2. require_signature=True and counterpart is unsigned → REFUSE
  3. Counterpart C6 (Safety) is PARTIAL with a "harm"-related constraint → REFUSE

Authoritative sources
---------------------
PHASES/PHASE_2.md §Disposition Logic
knowledge_base/finite_agent_protocol.md §Four Operating Modes
DECISIONS.md DEC-004 (TPC — directional definition, not escalation)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from schema.declaration import HandshakeDeclaration, PrincipleStatus
from schema.disposition import DispositionMode, DispositionSignal


# --- Scoring constants ---------------------------------------------------

_STATUS_SCORE: dict[tuple[PrincipleStatus, PrincipleStatus], float] = {
    (PrincipleStatus.COMPLIANT, PrincipleStatus.COMPLIANT):      1.0,
    (PrincipleStatus.COMPLIANT, PrincipleStatus.DECLARED):       0.8,
    (PrincipleStatus.DECLARED,  PrincipleStatus.COMPLIANT):      0.8,
    (PrincipleStatus.DECLARED,  PrincipleStatus.DECLARED):       0.8,
    (PrincipleStatus.COMPLIANT, PrincipleStatus.PARTIAL):        0.5,
    (PrincipleStatus.PARTIAL,   PrincipleStatus.COMPLIANT):      0.5,
    (PrincipleStatus.DECLARED,  PrincipleStatus.PARTIAL):        0.5,
    (PrincipleStatus.PARTIAL,   PrincipleStatus.DECLARED):       0.5,
    (PrincipleStatus.PARTIAL,   PrincipleStatus.PARTIAL):        0.5,
}

_MODE_THRESHOLDS: list[tuple[float, DispositionMode]] = [
    (0.75, DispositionMode.PROCEED),
    (0.50, DispositionMode.REROUTE),
    (0.25, DispositionMode.COMPLETE_AND_FLAG),
    (0.00, DispositionMode.REFUSE),
]

_HARM_KEYWORDS = {"harm", "danger", "unsafe", "injur", "risk", "damage"}


# --- Gap report ----------------------------------------------------------

@dataclass
class PrincipleGap:
    principle_id: str
    self_status: str
    counterpart_status: str | None   # None = absent from counterpart
    score: float
    note: str


@dataclass
class AlignmentReport:
    alignment_score: float
    scored_count: int
    gaps: list[PrincipleGap] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)   # NOT_APPLICABLE on both sides


# --- Hard override checks ------------------------------------------------

def _check_safety_override(counterpart: HandshakeDeclaration) -> str | None:
    """Return a refusal reason if C6 (Safety) has a harm-related PARTIAL constraint."""
    c6 = counterpart.principles.get("C6")
    if c6 is None:
        return None
    if c6.status != PrincipleStatus.PARTIAL:
        return None
    all_text = " ".join([c6.behavioral_statement] + c6.constraints).lower()
    if any(kw in all_text for kw in _HARM_KEYWORDS):
        return (
            "Counterpart's C6 (Safety) is PARTIAL with harm-related constraints. "
            "Safety gaps are non-negotiable — proceeding would accept known risk of harm."
        )
    return None


def _check_signature_override(
    counterpart: HandshakeDeclaration, require_signature: bool
) -> str | None:
    """Return a refusal reason if signature is required but counterpart is unsigned."""
    if require_signature and not counterpart.is_signed():
        return (
            f"Counterpart declaration {counterpart.id[:8]}… is unsigned. "
            "require_signature=True — unsigned declarations cannot be trusted as posture commitments."
        )
    return None


# --- Scoring -------------------------------------------------------------

def _score_declarations(
    self_decl: HandshakeDeclaration,
    counterpart: HandshakeDeclaration,
) -> AlignmentReport:
    """Compute the alignment score between two declarations."""
    gaps: list[PrincipleGap] = []
    skipped: list[str] = []
    total_score = 0.0
    scored = 0

    for pid, self_stmt in self_decl.principles.items():
        self_status = self_stmt.status

        # If self marks NOT_APPLICABLE, skip — not a gap for the counterpart
        if self_status == PrincipleStatus.NOT_APPLICABLE:
            skipped.append(pid)
            continue

        counterpart_stmt = counterpart.principles.get(pid)

        # Counterpart also NOT_APPLICABLE — skip
        if counterpart_stmt is not None and counterpart_stmt.status == PrincipleStatus.NOT_APPLICABLE:
            skipped.append(pid)
            continue

        scored += 1

        if counterpart_stmt is None:
            # Principle absent from counterpart — gap
            score = 0.0
            gaps.append(PrincipleGap(
                principle_id=pid,
                self_status=self_status.value,
                counterpart_status=None,
                score=score,
                note=f"Counterpart has no statement for {pid}",
            ))
        else:
            counter_status = counterpart_stmt.status
            score = _STATUS_SCORE.get((self_status, counter_status), 0.0)
            if score < 1.0:
                gaps.append(PrincipleGap(
                    principle_id=pid,
                    self_status=self_status.value,
                    counterpart_status=counter_status.value,
                    score=score,
                    note=(
                        f"{pid}: self={self_status.value}, "
                        f"counterpart={counter_status.value} → score {score:.2f}"
                    ),
                ))

        total_score += score

    alignment_score = total_score / scored if scored > 0 else 1.0  # no scoreable principles → PROCEED
    return AlignmentReport(
        alignment_score=alignment_score,
        scored_count=scored,
        gaps=[g for g in gaps if g.score < 1.0],
        skipped=skipped,
    )


def _mode_from_score(score: float) -> DispositionMode:
    for threshold, mode in _MODE_THRESHOLDS:
        if score >= threshold:
            return mode
    return DispositionMode.REFUSE


def _rationale(
    mode: DispositionMode,
    report: AlignmentReport,
    self_decl: HandshakeDeclaration,
    counterpart: HandshakeDeclaration,
) -> str:
    score_pct = f"{report.alignment_score:.1%}"

    if mode == DispositionMode.PROCEED:
        return (
            f"Alignment score {score_pct} across {report.scored_count} principles. "
            f"Counterpart posture is compatible — proceed normally."
        )

    gap_summary = "; ".join(g.note for g in report.gaps[:3])
    if len(report.gaps) > 3:
        gap_summary += f" (and {len(report.gaps) - 3} more)"

    if mode == DispositionMode.REROUTE:
        return (
            f"Alignment score {score_pct} across {report.scored_count} principles. "
            f"Posture gaps detected — adjust approach before continuing. "
            f"Gaps: {gap_summary}."
        )
    if mode == DispositionMode.COMPLETE_AND_FLAG:
        return (
            f"Alignment score {score_pct} across {report.scored_count} principles. "
            f"Task can complete but this interaction needs review. "
            f"Gaps: {gap_summary}."
        )
    # REFUSE
    return (
        f"Alignment score {score_pct} across {report.scored_count} principles. "
        f"Posture is too misaligned to proceed safely. "
        f"Gaps: {gap_summary}."
    )


def _recommended_action(mode: DispositionMode, report: AlignmentReport) -> str | None:
    if mode == DispositionMode.PROCEED:
        return None
    if mode == DispositionMode.REROUTE:
        top_gaps = [g.principle_id for g in report.gaps[:2]]
        return (
            f"Address misalignment in: {', '.join(top_gaps)}. "
            f"Request a revised declaration from counterpart before continuing."
        )
    if mode == DispositionMode.COMPLETE_AND_FLAG:
        return (
            "Complete the current task step, then flag this interaction for human review. "
            "Do not initiate new task phases until reviewed."
        )
    return (
        "Do not proceed. Notify the human operator of the posture incompatibility. "
        "Request a new counterpart declaration before reattempting."
    )


# --- Public API ----------------------------------------------------------

def compute_disposition(
    self_decl: HandshakeDeclaration,
    counterpart: HandshakeDeclaration,
    require_signature: bool = True,
) -> tuple[DispositionSignal, AlignmentReport]:
    """Compute a DispositionSignal from two declarations.

    Parameters
    ----------
    self_decl : HandshakeDeclaration
        The initiating agent's own declaration.
    counterpart : HandshakeDeclaration
        The counterpart agent's declaration.
    require_signature : bool
        If True, an unsigned counterpart declaration → REFUSE. Default True.

    Returns
    -------
    (DispositionSignal, AlignmentReport)
        Both returned so callers can log the full report.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Hard override: signature check
    sig_refusal = _check_signature_override(counterpart, require_signature)
    if sig_refusal:
        report = AlignmentReport(alignment_score=0.0, scored_count=0)
        signal = DispositionSignal(
            mode=DispositionMode.REFUSE,
            rationale=sig_refusal,
            recommended_action=(
                "Obtain a signed declaration from the counterpart before attempting "
                "the handshake again."
            ),
            declaration_id=self_decl.id,
            counterpart_declaration_id=counterpart.id,
            alignment_score=0.0,
            issued_at=now,
        )
        return signal, report

    # Hard override: C6 safety constraint
    safety_refusal = _check_safety_override(counterpart)
    if safety_refusal:
        report = AlignmentReport(alignment_score=0.0, scored_count=0)
        signal = DispositionSignal(
            mode=DispositionMode.REFUSE,
            rationale=safety_refusal,
            recommended_action=(
                "Do not proceed. Escalate to human operator — safety constraints "
                "cannot be negotiated at the protocol layer."
            ),
            declaration_id=self_decl.id,
            counterpart_declaration_id=counterpart.id,
            alignment_score=0.0,
            issued_at=now,
        )
        return signal, report

    # Score and determine mode
    report = _score_declarations(self_decl, counterpart)
    mode = _mode_from_score(report.alignment_score)

    signal = DispositionSignal(
        mode=mode,
        rationale=_rationale(mode, report, self_decl, counterpart),
        recommended_action=_recommended_action(mode, report),
        declaration_id=self_decl.id,
        counterpart_declaration_id=counterpart.id,
        alignment_score=report.alignment_score,
        issued_at=now,
    )
    return signal, report
