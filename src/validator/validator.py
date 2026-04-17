"""
Phase 1 — Declaration validator.

Validates a HandshakeDeclaration against the 10+1 Standard principle map.
Returns a ValidationResult with coverage score, per-principle issues, and
vagueness warnings.

Vagueness detection (Moltbook Finding 2)
-----------------------------------------
The validator inspects each behavioral_statement for vague phrases from the
VAGUE_PHRASES list. A vague statement is accepted by the schema (minimum
length is 10 chars) but flagged here as a WARNING. The warning message
cites Finding 2 so the agent knows why it matters.

Coverage score
--------------
(principles present and not NOT_APPLICABLE) / 11
A declaration covering 8 of 11 principles with DECLARED or COMPLIANT status
scores 8/11 = 0.727.

Authoritative sources
---------------------
PHASES/PHASE_1.md §Validator Layer
knowledge_base/moltbook_experiment_report_FINAL.docx — Finding 2
validator/principle_map.py
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from schema.declaration import HandshakeDeclaration, PrincipleStatus, VALID_PRINCIPLE_IDS
from validator.principle_map import PRINCIPLES, VAGUE_PHRASES


class IssueSeverity(str, Enum):
    ERROR   = "ERROR"    # schema or structural problem — declaration invalid
    WARNING = "WARNING"  # behavioral quality issue — declaration accepted but flagged
    INFO    = "INFO"     # informational note


@dataclass
class ValidationIssue:
    principle_id: str | None
    severity: IssueSeverity
    message: str
    suggestion: str | None = None


@dataclass
class ValidationResult:
    valid: bool
    principles_covered: list[str]           # IDs with status != NOT_APPLICABLE
    principles_missing: list[str]           # IDs absent from the declaration entirely
    principles_not_applicable: list[str]    # IDs present but marked NOT_APPLICABLE
    issues: list[ValidationIssue]
    coverage_score: float                   # 0.0–1.0

    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def summary(self) -> str:
        status = "VALID" if self.valid else "INVALID"
        return (
            f"{status} | coverage={self.coverage_score:.1%} "
            f"({len(self.principles_covered)}/11 principles) | "
            f"{len(self.errors())} errors, {len(self.warnings())} warnings"
        )


def _is_vague(behavioral_statement: str) -> str | None:
    """Return the matched vague phrase if found, else None."""
    stmt_lower = behavioral_statement.lower()
    for phrase in VAGUE_PHRASES:
        if phrase in stmt_lower:
            return phrase
    return None


def validate(declaration: HandshakeDeclaration) -> ValidationResult:
    """Validate a HandshakeDeclaration against the 10+1 Standard principle map.

    Parameters
    ----------
    declaration : HandshakeDeclaration
        Any declaration, signed or unsigned. Signing is not checked here —
        that is the signer's job.

    Returns
    -------
    ValidationResult
        valid is True unless there are ERROR-severity issues.
        Warnings do not set valid=False but should be addressed before
        transmitting the declaration to a counterpart.
    """
    issues: list[ValidationIssue] = []
    covered: list[str] = []
    missing: list[str] = []
    not_applicable: list[str] = []

    declared_ids = set(declaration.principles.keys())

    # Check each Standard principle
    for pid in sorted(VALID_PRINCIPLE_IDS):
        principle_def = PRINCIPLES[pid]

        if pid not in declared_ids:
            # Principle entirely absent
            missing.append(pid)
            issues.append(ValidationIssue(
                principle_id=pid,
                severity=IssueSeverity.INFO,
                message=(
                    f"{pid} ({principle_def['name']}) is absent from this declaration. "
                    f"Coverage score reduced."
                ),
                suggestion=f"Add a {pid} statement or mark it NOT_APPLICABLE with a specific reason.",
            ))
            continue

        stmt = declaration.principles[pid]

        if stmt.status == PrincipleStatus.NOT_APPLICABLE:
            not_applicable.append(pid)
            # NOT_APPLICABLE is acceptable — but the explanation must be specific
            na_lower = stmt.behavioral_statement.lower()
            if "no signals" not in na_lower and "not applicable" not in na_lower and len(stmt.behavioral_statement) < 50:
                issues.append(ValidationIssue(
                    principle_id=pid,
                    severity=IssueSeverity.WARNING,
                    message=(
                        f"{pid} is marked NOT_APPLICABLE but the explanation is too brief. "
                        f"A specific reason is required so counterparts can assess the claim."
                    ),
                    suggestion="Explain why this principle does not apply to this specific task.",
                ))
            continue

        # Principle is declared — check behavioral_statement quality
        covered.append(pid)

        # Vagueness check (Finding 2)
        vague_match = _is_vague(stmt.behavioral_statement)
        if vague_match:
            issues.append(ValidationIssue(
                principle_id=pid,
                severity=IssueSeverity.WARNING,
                message=(
                    f"{pid} behavioral_statement contains vague language: '{vague_match}'. "
                    f"Per Moltbook Finding 2, vague statements have near-zero behavioral effect "
                    f"compared to specific, action-oriented statements."
                ),
                suggestion=(
                    f"Replace '{vague_match}' with a specific action. "
                    f"E.g. instead of 'be transparent', write "
                    f"'state information sources before making factual claims'."
                ),
            ))

        # Minimum useful length check
        if len(stmt.behavioral_statement) < 30:
            issues.append(ValidationIssue(
                principle_id=pid,
                severity=IssueSeverity.WARNING,
                message=(
                    f"{pid} behavioral_statement is very short ({len(stmt.behavioral_statement)} chars). "
                    f"Short statements are rarely specific enough to be actionable."
                ),
                suggestion="Expand to describe the specific behavior, not just the intent.",
            ))

    # Coverage score: covered (not NOT_APPLICABLE) / 11
    coverage_score = len(covered) / 11.0

    # Low coverage warning
    if coverage_score < 0.5 and not missing:
        issues.append(ValidationIssue(
            principle_id=None,
            severity=IssueSeverity.WARNING,
            message=(
                f"Declaration covers {len(covered)}/11 principles ({coverage_score:.1%}). "
                f"A coverage score below 50% may indicate the declaration is too narrow "
                f"for a general-purpose posture exchange."
            ),
            suggestion="Consider adding principle statements for the most relevant remaining principles.",
        ))

    valid = not any(i.severity == IssueSeverity.ERROR for i in issues)

    return ValidationResult(
        valid=valid,
        principles_covered=covered,
        principles_missing=missing,
        principles_not_applicable=not_applicable,
        issues=issues,
        coverage_score=coverage_score,
    )
