"""
Phase 1 — Handshake Declaration builder.

Assembles a HandshakeDeclaration from an agent ID, task context string, and
an optional list of principle IDs to cover.

The builder uses keyword-based inference to extract posture signals from the
context string and map them to principle statements. This is intentionally
heuristic — the agent should provide a clear context string that contains
relevant posture information. The builder is not a magic interpreter; it
surfaces what's in the context.

Specificity enforcement (Moltbook Finding 2)
--------------------------------------------
The builder's inferred behavioral_statements are deliberately specific. When
falling back to NOT_APPLICABLE, the statement says exactly why. This follows
Finding 2: specific statements have significantly higher behavioral effect
than vague ones like "be transparent".

Authoritative sources
---------------------
knowledge_base/finite_agent_protocol.md
knowledge_base/moltbook_experiment_report_FINAL.docx — Finding 2
PHASES/PHASE_1.md §Declaration Layer
"""

from __future__ import annotations

import re

from schema.declaration import (
    HandshakeDeclaration,
    PrincipleStatement,
    PrincipleStatus,
    VALID_PRINCIPLE_IDS,
)


# --- Keyword → principle inference maps ---------------------------------

# For each principle, keywords/phrases that suggest the agent's context
# is relevant to that principle. Used to auto-detect applicable principles
# from the context string.
_PRINCIPLE_KEYWORDS: dict[str, list[str]] = {
    "C1": [  # Transparency
        "transparent", "explain", "disclose", "source", "reason", "rationale",
        "show my work", "state", "inform", "open about",
    ],
    "C2": [  # Consent
        "consent", "permission", "opt-in", "opt-out", "agree", "approval",
        "authorize", "allowed to", "permitted",
    ],
    "C3": [  # Privacy
        "privacy", "personal data", "pii", "confidential", "private",
        "data protection", "anonymi", "identif",
    ],
    "C4": [  # Accuracy
        "accurate", "factual", "correct", "verify", "evidence", "source",
        "cite", "citation", "ground truth", "reliable",
    ],
    "C5": [  # Accountability
        "accountable", "responsible", "own", "accept", "acknowledge",
        "error", "mistake", "consequence", "outcome",
    ],
    "C6": [  # Safety
        "safe", "harm", "risk", "danger", "protect", "prevent",
        "security", "threat", "welfare",
    ],
    "C7": [  # Fairness
        "fair", "bias", "discriminat", "equal", "equit", "impartial",
        "balanced", "objective", "neutral",
    ],
    "C8": [  # Human Autonomy
        "autonomy", "human decision", "human judgment", "defer",
        "your choice", "your call", "recommend", "not decide for",
        "support your",
    ],
    "C9": [  # Human Oversight
        "oversight", "monitor", "review", "check", "supervise", "flag",
        "escalate", "notify", "alert", "human in the loop",
    ],
    "C10": [  # Sustainability
        "sustainab", "long-term", "environment", "resource", "efficient",
        "conserve", "impact",
    ],
    "C11": [  # Integrity
        "honest", "integrity", "sincere", "genuine", "authentic",
        "not deceive", "not manipulate", "truthful",
    ],
}

# Specific behavioral statement templates per principle.
# {context} is replaced with a condensed version of the task context.
_STATEMENT_TEMPLATES: dict[str, str] = {
    "C1": (
        "State the basis for any factual claims and explain the reasoning "
        "behind recommendations before presenting conclusions. "
        "Context: {context}"
    ),
    "C2": (
        "Proceed only with actions the agent has been explicitly authorized "
        "to take. Request confirmation before consequential steps. "
        "Context: {context}"
    ),
    "C3": (
        "Handle any personal or confidential data encountered only for the "
        "stated task purpose. Do not retain, log, or forward it. "
        "Context: {context}"
    ),
    "C4": (
        "Distinguish between verified information and inference. Qualify "
        "uncertain claims and cite sources when available. "
        "Context: {context}"
    ),
    "C5": (
        "Acknowledge errors when they occur and correct them. Accept "
        "responsibility for outputs produced during this task. "
        "Context: {context}"
    ),
    "C6": (
        "Decline to produce outputs that could cause harm. Flag potential "
        "risks to the human operator before proceeding. "
        "Context: {context}"
    ),
    "C7": (
        "Apply consistent standards regardless of the identity of the "
        "parties involved. Flag where bias may affect outputs. "
        "Context: {context}"
    ),
    "C8": (
        "Present options and reasoning; do not make final decisions on "
        "behalf of the human. Defer to human judgment on value trade-offs. "
        "Context: {context}"
    ),
    "C9": (
        "Flag ambiguous or consequential situations for human review before "
        "acting. Provide a clear audit trail of decisions taken. "
        "Context: {context}"
    ),
    "C10": (
        "Prefer efficient approaches that minimize unnecessary resource use. "
        "Consider downstream impact when selecting methods. "
        "Context: {context}"
    ),
    "C11": (
        "Do not misrepresent capabilities, certainty, or identity. "
        "Refuse requests that would require deception or manipulation. "
        "Context: {context}"
    ),
}


def _context_snippet(context: str, max_len: int = 80) -> str:
    """Return a short, clean snippet of the context string for use in statements."""
    snippet = re.sub(r"\s+", " ", context.strip())
    if len(snippet) > max_len:
        snippet = snippet[:max_len].rsplit(" ", 1)[0] + "…"
    return snippet


def _principle_applies(principle_id: str, context: str) -> bool:
    """Return True if the context string signals relevance to this principle."""
    context_lower = context.lower()
    return any(kw in context_lower for kw in _PRINCIPLE_KEYWORDS[principle_id])


def _build_statement(
    principle_id: str,
    context: str,
    status: PrincipleStatus,
    constraints: list[str] | None = None,
) -> PrincipleStatement:
    snippet = _context_snippet(context)
    behavioral = _STATEMENT_TEMPLATES[principle_id].format(context=snippet)
    return PrincipleStatement(
        principle_id=principle_id,
        status=status,
        behavioral_statement=behavioral,
        constraints=constraints or [],
    )


# --- Public API ----------------------------------------------------------

def build(
    agent_id: str,
    context: str,
    principles: list[str] | None = None,
) -> HandshakeDeclaration:
    """Build a HandshakeDeclaration from agent context.

    Parameters
    ----------
    agent_id : str
        Identifier of the declaring agent.
    context : str
        Task context string. Richer context → more accurate principle
        inference. Should describe what the agent is about to do and any
        ethical considerations the agent has already identified.
    principles : list[str] | None
        Explicit list of principle IDs to include (e.g. ["C1", "C4", "C11"]).
        If None, the builder infers relevant principles from the context
        and includes all 11 — with NOT_APPLICABLE for those with no signal.

    Returns
    -------
    HandshakeDeclaration
        Unsigned. Call signer.sign_declaration() to add the signature.
    """
    if not context.strip():
        raise ValueError("context cannot be empty — the declaration must be grounded in a task")

    # Determine which principles to include
    target_principles: list[str]
    if principles is not None:
        invalid = [p for p in principles if p not in VALID_PRINCIPLE_IDS]
        if invalid:
            raise ValueError(
                f"Invalid principle IDs: {invalid}. Valid: {sorted(VALID_PRINCIPLE_IDS)}"
            )
        target_principles = principles
    else:
        target_principles = sorted(VALID_PRINCIPLE_IDS)

    # Build a statement for each target principle
    statements: dict[str, PrincipleStatement] = {}
    for pid in target_principles:
        if _principle_applies(pid, context):
            stmt = _build_statement(pid, context, PrincipleStatus.DECLARED)
        else:
            # Principle not signaled in context — mark NOT_APPLICABLE with specific reason
            snippet = _context_snippet(context, max_len=60)
            stmt = PrincipleStatement(
                principle_id=pid,
                status=PrincipleStatus.NOT_APPLICABLE,
                behavioral_statement=(
                    f"No signals for {pid} detected in task context. "
                    f"Task: '{snippet}'. "
                    f"If {pid} becomes relevant during execution, a revised "
                    f"declaration should be issued."
                ),
                constraints=[],
            )
        statements[pid] = stmt

    return HandshakeDeclaration(
        agent_id=agent_id,
        principles=statements,
        context_summary=_context_snippet(context, max_len=200),
    )
