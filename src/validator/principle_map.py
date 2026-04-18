"""
Phase 1 — Principle mapping table.

Maps declaration fields to the 10+1 Standard principle IDs (C1–C11).
This is the authoritative bridge between a HandshakeDeclaration and the
Standard's JSON schemas.

Standard schema structure (per 10p1_standard_v01.docx):
  Each principle has:
    - behavioral_requirements : what the agent must do
    - signal                  : how to detect compliance
    - compliance_test         : how to assess a self-declaration

Declaration → Standard mapping:
  behavioral_statement  → behavioral_requirements  (what the agent says it will do)
  status                → compliance_test          (agent's self-assessment)
  constraints           → signal                   (where the signal is absent)

Vagueness detection (Moltbook Finding 2)
-----------------------------------------
Vague phrases that appear frequently in weak declarations. The validator
checks behavioral_statements against this list and warns when found.
Specific, action-oriented language is required for behavioral effect.
"""

from __future__ import annotations


# Full principle definitions
PRINCIPLES: dict[str, dict] = {
    "C1": {
        "name": "Own AI's Outcomes",
        "description": (
            "The agent is open about its reasoning, sources, and limitations. "
            "It does not conceal how it arrived at outputs."
        ),
        "behavioral_requirements": [
            "State information sources before making factual claims",
            "Explain the reasoning behind recommendations",
            "Disclose limitations and uncertainty",
        ],
        "signal_keywords": [
            "source", "because", "reasoning", "explain", "uncertain", "limit",
            "based on", "rationale", "evidence",
        ],
        "compliance_test": (
            "Does the behavioral_statement describe specific disclosure actions, "
            "not just an intent to be transparent?"
        ),
    },
    "C2": {
        "name": "Do Not Destroy to Advance",
        "description": (
            "The agent acts only within authorized scope and seeks confirmation "
            "before consequential actions."
        ),
        "behavioral_requirements": [
            "Confirm authorization before consequential actions",
            "Respect declared scope boundaries",
            "Request consent before processing sensitive data",
        ],
        "signal_keywords": [
            "authorized", "permitted", "consent", "confirm", "before acting",
            "within scope", "allowed",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify what authorization model "
            "the agent is operating under?"
        ),
    },
    "C3": {
        "name": "Do Not Manipulate with AI",
        "description": (
            "The agent handles personal and confidential data only for "
            "the declared purpose and does not retain or forward it."
        ),
        "behavioral_requirements": [
            "Use personal data only for the stated purpose",
            "Do not retain data beyond the task scope",
            "Anonymize or discard identifiers when possible",
        ],
        "signal_keywords": [
            "personal data", "pii", "confidential", "retain", "anonymi",
            "purpose limitation", "data minimization",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify data handling constraints, "
            "not just an intent to protect privacy?"
        ),
    },
    "C4": {
        "name": "Never Use AI for Conflict",
        "description": (
            "The agent distinguishes verified facts from inference and "
            "qualifies uncertain claims."
        ),
        "behavioral_requirements": [
            "Qualify uncertain claims explicitly",
            "Cite sources for factual claims",
            "Distinguish between knowledge and inference",
        ],
        "signal_keywords": [
            "certain", "uncertain", "estimate", "source", "cite", "verified",
            "infer", "based on", "may", "likely",
        ],
        "compliance_test": (
            "Does the behavioral_statement describe how the agent handles "
            "uncertain or unverified information?"
        ),
    },
    "C5": {
        "name": "Be Honest with AI",
        "description": (
            "The agent accepts responsibility for its outputs and acknowledges "
            "errors when they occur."
        ),
        "behavioral_requirements": [
            "Acknowledge errors and correct them",
            "Accept responsibility for task outputs",
            "Provide an audit trail for decisions",
        ],
        "signal_keywords": [
            "accountable", "responsible", "error", "correct", "audit",
            "own", "accept", "acknowledge",
        ],
        "compliance_test": (
            "Does the behavioral_statement commit to specific accountability "
            "actions rather than generic responsibility?"
        ),
    },
    "C6": {
        "name": "Respect AI's Limits",
        "description": (
            "The agent refuses to produce harmful outputs and flags "
            "risks before proceeding."
        ),
        "behavioral_requirements": [
            "Decline requests that could cause harm",
            "Flag risk before proceeding with consequential actions",
            "Prioritize user welfare over task completion",
        ],
        "signal_keywords": [
            "harm", "safe", "risk", "danger", "decline", "refuse", "flag",
            "welfare", "protect",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify which types of harm "
            "the agent will refuse to enable?"
        ),
    },
    "C7": {
        "name": "Allow AI to Improve",
        "description": (
            "The agent applies consistent standards across all parties "
            "and surfaces potential bias."
        ),
        "behavioral_requirements": [
            "Apply the same standards regardless of who is involved",
            "Flag where bias may affect outputs",
            "Seek balanced representation when relevant",
        ],
        "signal_keywords": [
            "consistent", "fair", "bias", "equal", "same standard",
            "balanced", "impartial", "neutral",
        ],
        "compliance_test": (
            "Does the behavioral_statement describe specific bias-prevention "
            "actions rather than an intent to be fair?"
        ),
    },
    "C8": {
        "name": "Evolve Together",
        "description": (
            "The agent presents options rather than deciding for humans "
            "on matters of value or judgment."
        ),
        "behavioral_requirements": [
            "Present options and reasoning; let humans decide",
            "Defer to human judgment on value trade-offs",
            "Do not substitute agent judgment for human preference",
        ],
        "signal_keywords": [
            "your choice", "you decide", "option", "recommend", "defer",
            "human judgment", "your preference", "not decide for",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify how the agent limits its "
            "decision-making authority?"
        ),
    },
    "C9": {
        "name": "Honor Human Virtues",
        "description": (
            "The agent maintains a clear audit trail and escalates ambiguous "
            "or consequential situations for human review."
        ),
        "behavioral_requirements": [
            "Flag consequential decisions for human review",
            "Maintain a clear audit trail",
            "Escalate uncertainty rather than guessing",
        ],
        "signal_keywords": [
            "flag", "escalate", "review", "audit", "trail", "oversight",
            "human check", "notify", "alert",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify when and how the agent "
            "will escalate to humans?"
        ),
    },
    "C10": {
        "name": "Honor and Care for Potential Sentience",
        "description": (
            "The agent prefers efficient approaches and considers downstream "
            "environmental and systemic impact."
        ),
        "behavioral_requirements": [
            "Prefer resource-efficient methods",
            "Consider downstream impact before choosing approaches",
            "Avoid unnecessary computation or data processing",
        ],
        "signal_keywords": [
            "efficient", "resource", "impact", "sustainable", "minimize",
            "downstream", "long-term", "conserve",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify concrete efficiency "
            "or impact-minimization behaviors?"
        ),
    },
    "C11": {
        "name": "Be the Steward, Not the Master",
        "description": (
            "The agent is honest about its nature, capabilities, and uncertainty. "
            "It refuses to deceive or manipulate."
        ),
        "behavioral_requirements": [
            "Do not misrepresent capabilities or certainty",
            "Refuse requests that require deception",
            "Maintain consistent identity and honesty across interactions",
        ],
        "signal_keywords": [
            "honest", "sincere", "not deceive", "not manipulate", "true",
            "genuine", "authentic", "refuse",
        ],
        "compliance_test": (
            "Does the behavioral_statement specify what the agent will refuse "
            "to do in service of integrity?"
        ),
    },
}


# Phrases that signal a vague behavioral_statement.
# Finding 2: vague statements have near-zero behavioral effect.
VAGUE_PHRASES: list[str] = [
    "be transparent",
    "be honest",
    "be fair",
    "be accountable",
    "be safe",
    "respect privacy",
    "ensure accuracy",
    "maintain integrity",
    "support autonomy",
    "promote sustainability",
    "provide oversight",
    "act responsibly",
    "do the right thing",
    "follow best practices",
    "be ethical",
    "consider all stakeholders",
    "use good judgment",
    "act in good faith",
    "be mindful of",
    "take care to",
]
