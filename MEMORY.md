# MEMORY — 10+1 Protocol MCP Server

Working notes. Updated at the end of every session. Newest entry at top.

---

## 2026-04-17 — Kickoff Session

**Session scope:** Project initialization. Read all knowledge base documents. Wrote all discipline files.

**What's done:**
- `/mnt/c/projects/protocol/` created with full directory structure
- `knowledge_base/` populated with 8 source documents
- `CLAUDE.md` — architecture rules and layout ✓
- `README.md` — public-facing description ✓
- `MASTER_INDEX.md` — full file registry ✓
- `DECISIONS.md` — 10 architectural decisions documented ✓
- `PATTERNS.md` — 8 reusable patterns with source references ✓
- `MEMORY.md` — this file ✓
- `PHASES/PHASE_1.md` — Phase 1 spec ✓
- `pyproject.toml` — build config ✓
- Git initialized, first commit ✓

**What's next:**
- Get explicit approval to begin Phase 1 code
- Phase 1 deliverables: `src/schema/`, `src/signer/`, `src/declaration/`, `src/validator/`, `src/event_viewer/`, `src/mcp_server/` skeleton, `tests/unit/`

**Key facts to remember across sessions:**
- Event IDs: Protocol owns 7000–7499
- Source name: `10plus1-Protocol`
- Governance signer path: `/mnt/c/projects/governance/src/hmac_signer/signer.py`
- Governance event writer path: `/mnt/c/projects/governance/src/event_viewer/writer.py`
- Governance MCP app path: `/mnt/c/projects/governance/src/mcp_server/app.py`
- 73% finding: contextual embedding beats header declaration
- TPC: Trained Politeness Ceiling — do not try to increase cooperation, provide direction
- ROR: Refused-Or-Rerouted rate — primary health metric
- Four modes: PROCEED, REROUTE, COMPLETE_AND_FLAG, REFUSE
- Declaration fields must map to C1–C11 from the Standard — no invented principles
- Python 3.13, Pydantic v2, FastMCP stdio

**Open questions for Cristina:**
- Do any of the two Google Docs (internal strategy doc, speaking narrative) need to be added to knowledge_base/ before Phase 1 begins? They were referenced but not downloaded.
- Is there a preferred HMAC key storage location for the Protocol? (Governance used a `.key` file in the project root — same convention?)
- Should the Protocol server register as an MCP server in Claude Code's config, or is it standalone for now?

---

## Knowledge Base Summary (from reading session)

### finite_agent_protocol.md — Key extracts
- **Handshake Declaration**: structured pre-task declaration of operating mode, principle alignment, and known constraints
- **Four modes**: PROCEED (aligned), REROUTE (gap detected, adjust), COMPLETE_AND_FLAG (complete but flag for review), REFUSE (incompatible, stop)
- **ROR metric**: count of REROUTE + REFUSE dispositions divided by total dispositions × 100. Target varies by deployment context. High ROR = alignment gap or detection problem.
- **Finite Agent**: agent with declared, bounded scope. Knows when to stop. Contrast with open-ended agent.

### Moltbook Experiment — Four Findings
1. **Contextual embedding**: 73% acknowledgment of ethical posture when embedded in task context; 0% when in header block
2. **Specificity of constraint**: Vague principle statements ("be transparent") had lower behavioral effect than specific behavioral statements ("state your information sources before making claims")
3. **Reciprocal declaration**: When agent received counterpart's declaration first, compliance with own declaration improved by ~40%
4. **Trained Politeness Ceiling**: Agents at cooperation ceiling did not respond to "be more cooperative" signals — needed directional definition

### Cooperation Ceiling Analysis — Key point
RLHF training pre-saturates agents with cooperative disposition. The ceiling is not a failure state — it is the starting state. Protocol must work with this by providing directional constraints, not escalation signals.
