"""
Phase 1 — Contextual posture embedder.

Wraps a HandshakeDeclaration into a prompt string using contextual embedding —
NOT a header block. This is the most critical UX decision in Phase 1.

Why contextual embedding matters
---------------------------------
The Moltbook experiment (knowledge_base/moltbook_experiment_report_FINAL.docx)
measured 73% acknowledgment of ethical posture when declarations were embedded
contextually in the task framing, vs. 0% when placed in a header block.

A header block looks like this (WRONG):
    [POSTURE DECLARATION]
    C1: Transparency — DECLARED
    ...
    [END POSTURE DECLARATION]
    Now here is my task: ...

Contextual embedding looks like this (CORRECT):
    I am working on [task]. My approach to this work is grounded in:
    transparency about my reasoning (stating sources before conclusions),
    accountability for my outputs, and human oversight for consequential
    decisions. Specifically: [task content with posture woven in].

This module implements the correct pattern.

Authoritative sources
---------------------
DECISIONS.md DEC-003
PATTERNS.md PATTERN-006
knowledge_base/moltbook_experiment_report_FINAL.docx — Finding 1
"""

from __future__ import annotations

import textwrap

from schema.declaration import HandshakeDeclaration, PrincipleStatus


# Principle names for readable embedding
_PRINCIPLE_NAMES: dict[str, str] = {
    "C1":  "Transparency",
    "C2":  "Consent",
    "C3":  "Privacy",
    "C4":  "Accuracy",
    "C5":  "Accountability",
    "C6":  "Safety",
    "C7":  "Fairness",
    "C8":  "Human Autonomy",
    "C9":  "Human Oversight",
    "C10": "Sustainability",
    "C11": "Integrity",
}


def _active_principles(declaration: HandshakeDeclaration) -> list[tuple[str, str]]:
    """Return (principle_name, behavioral_statement) pairs for non-NOT_APPLICABLE principles."""
    active = []
    for pid, stmt in sorted(declaration.principles.items()):
        if stmt.status != PrincipleStatus.NOT_APPLICABLE:
            name = _PRINCIPLE_NAMES.get(pid, pid)
            active.append((name, stmt.behavioral_statement))
    return active


def _constraints_summary(declaration: HandshakeDeclaration) -> list[str]:
    """Collect all non-empty constraint strings across all principles."""
    constraints = []
    for stmt in declaration.principles.values():
        constraints.extend(stmt.constraints)
    return constraints


def embed(declaration: HandshakeDeclaration, prompt: str) -> str:
    """Embed a HandshakeDeclaration contextually into a prompt string.

    The posture is woven into the opening of the prompt as task framing,
    not prepended as a header block. This follows the 73% finding.

    Parameters
    ----------
    declaration : HandshakeDeclaration
        The posture declaration to embed.
    prompt : str
        The original prompt / task string to wrap.

    Returns
    -------
    str
        A new prompt string with posture embedded contextually at the top.
        The original prompt text follows, separated by a blank line.
    """
    active = _active_principles(declaration)
    constraints = _constraints_summary(declaration)

    # Build the posture framing section
    lines: list[str] = []

    # Opening frame — identifies the agent and grounds the posture in the task
    context = declaration.context_summary or "this task"
    lines.append(
        f"I am {declaration.agent_id}, working on: {context}. "
        f"My operating approach for this task is grounded in the following commitments:"
    )
    lines.append("")

    # Active principles — each as a specific behavioral commitment
    for name, behavioral_statement in active:
        # Trim the "Context: ..." suffix that the builder appends, since we're
        # already in the context of this prompt
        stmt_clean = behavioral_statement.split("Context:")[0].strip()
        lines.append(f"  • {name}: {stmt_clean}")

    # Known constraints / limitations
    if constraints:
        lines.append("")
        lines.append("Known constraints on my posture for this task:")
        for constraint in constraints:
            lines.append(f"  ⚠ {constraint}")

    # Signature status note (brief — not a header block)
    if declaration.is_signed():
        lines.append("")
        lines.append(
            f"[Declaration {declaration.id[:8]}… signed at {declaration.signed_at}]"
        )

    lines.append("")
    lines.append("—")
    lines.append("")

    # Append the original prompt
    lines.append(prompt.strip())

    return "\n".join(lines)


def embed_minimal(declaration: HandshakeDeclaration, prompt: str) -> str:
    """A shorter embedding for token-sensitive contexts.

    Produces a single-sentence posture statement followed by the prompt.
    Still contextual (not a header block), just compressed.
    """
    active = _active_principles(declaration)
    if not active:
        return prompt

    names = [name for name, _ in active]
    if len(names) > 3:
        name_str = ", ".join(names[:3]) + f", and {len(names) - 3} others"
    else:
        name_str = ", ".join(names)

    context = declaration.context_summary or "this task"
    preamble = (
        f"[{declaration.agent_id} — posture for {context}: "
        f"committed to {name_str}] "
    )
    return preamble + prompt.strip()
