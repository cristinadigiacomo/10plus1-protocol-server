# CLAUDE.md — 10+1 Protocol MCP Server

## What This Project Is

The **10+1 Protocol MCP Server** is the AI↔AI handshake layer of the 10P1 Inc. product stack. It lets an AI agent declare its ethical posture to another AI agent (or system) in a machine-readable, verifiable, signed format — and receive a structured disposition signal in return.

This is the **fourth layer** of the stack:

```
Standard (JSON schemas, open)        ← npm: 10plus1-standard
Validator (compliance checker, npm)  ← npm: 10plus1-validator
Governance (enterprise runtime)      ← /mnt/c/projects/governance
Protocol (this — AI↔AI handshake)   ← /mnt/c/projects/protocol
```

## Critical Architecture Rules

1. **No code before the plan is approved.** Read all knowledge base documents, write all discipline files, propose the phased plan, get explicit permission, then code Phase 1.

2. **Posture declarations are structurally tied to the Standard.** Every field in a Handshake Declaration maps to one of the 11 principles (C1–C11) from the 10+1 Standard schemas. Do not invent new principle fields.

3. **Reuse governance patterns.** Do not rewrite HMAC signing, event logging, or MCP transport. Import or copy from `/mnt/c/projects/governance/src/`. Pattern locations are documented in PATTERNS.md.

4. **FastMCP stdio transport only.** No HTTP MCP transport. Stdio is the governance precedent and the correct pattern for local agent integration.

5. **Pydantic v2 everywhere.** No v1 compat shims. Models use `model_validator`, `field_validator`, not `@validator`.

6. **Event IDs 7000–7499.** Governance owns 5000–5499 and 6000–6499. Protocol's Windows Event Viewer range is 7000–7499. Source name: `10plus1-Protocol`.

7. **Dual-channel output always.** Every MCP tool response returns both a human-readable `message` field and a structured `data` dict. Never one without the other.

8. **The Trained Politeness Ceiling is a design constraint, not a bug.** RLHF-saturated agents cannot become MORE cooperative from a signal — they can only receive directional definition. Architecture must account for this. See DECISIONS.md §TPC.

9. **Contextual embedding beats header declaration.** 73% vs. 0% acknowledgment in the Moltbook experiment. Protocol prompts embed posture inline, not in a header block.

10. **ROR (Refused-Or-Rerouted) is the primary health metric.** Track it. Expose it. Do not bury it in logs.

## Directory Layout

```
protocol/
├── CLAUDE.md               ← this file
├── README.md               ← public-facing project description
├── MASTER_INDEX.md         ← every file, one line each
├── DECISIONS.md            ← architectural decisions with rationale
├── PATTERNS.md             ← reusable patterns and where they live
├── MEMORY.md               ← session memory / working notes
├── PHASES/
│   ├── PHASE_1.md          ← Phase 1 spec (declaration + validation + signing)
│   ├── PHASE_2.md          ← (future)
│   └── ...
├── knowledge_base/         ← all source docs, read-only
│   ├── finite_agent_protocol.md
│   ├── moltbook_experiment_report_FINAL.docx
│   ├── 10p1_standard_v01.docx
│   ├── 10p1_translation_of_principles.docx
│   ├── 10p1_translation_governance_canon.docx
│   ├── handshake_protocol_testing_report.docx
│   ├── experiment_summary_advisory_board.pdf
│   └── cooperation_ceiling_analysis.docx
├── src/
│   ├── declaration/        ← Handshake Declaration schema + builder
│   ├── validator/          ← declaration validator (maps to Standard C1–C11)
│   ├── signer/             ← HMAC-SHA256 posture signing (from governance)
│   ├── dispositioner/      ← four-mode disposition engine
│   ├── event_viewer/       ← Windows Event Log writer (from governance)
│   ├── mcp_server/         ← FastMCP app, tools, service layer
│   └── schema/             ← Pydantic models (declaration, disposition, event)
├── tests/
│   ├── unit/
│   └── integration/
└── pyproject.toml
```

## Workflow Rules

- **Read before write.** Always read a file before editing it.
- **One phase at a time.** Complete and test Phase 1 before proposing Phase 2 code.
- **MEMORY.md is the working scratchpad.** Update it at the end of every session with what changed and what's next.
- **DECISIONS.md gets an entry for every non-obvious choice.** If you're about to do something and it's not obvious why, write it down first.
- **Do not modify knowledge_base/.** It is a read-only archive of source documents.
- **Git after each phase completes.** Commit message format: `phase-N: <what landed>`
