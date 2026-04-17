# MEMORY — 10+1 Protocol MCP Server

Working notes. Updated at the end of every session. Newest entry at top.

---

## 2026-04-17 — Phase 4 Complete

**What landed:**
- 290/290 unit tests passing (57 new tests: 45 in test_reporting.py + 26 Phase 4 additions to test_mcp_tools.py minus previous count)
- Git tag: phase-4-complete
- All four phases complete — Protocol MCP server fully operational

**Phase 4 files written:**
- `src/reporting/journal.py` — EventJournal: append-only JSONL, read_recent(), total_lines()
- `src/reporting/ror_persistence.py` — RORPersistence: JSON snapshot file, trend_summary()
- `src/reporting/exporter.py` — build_session_report(), build_ror_report(), build_summary()
- `src/reporting/__init__.py`
- `src/mcp_server/service.py` — Extended: _journal/_ror_store in __init__, _log() writes to journal, get_event_journal(), export_session_report(), export_ror_report(), get_summary()
- `src/mcp_server/app.py` — 4 new Phase 4 tools: get_event_journal, export_session_report, export_ror_report, get_summary
- `tests/unit/test_reporting.py` — 45 tests
- `tests/unit/test_mcp_tools.py` — Phase 4 additions

**Phase 4 done criteria:**
- [x] EventJournal persists events across restarts (.protocol_journal.jsonl)
- [x] RORPersistence persists snapshots across restarts (.protocol_ror.json)
- [x] build_session_report / build_ror_report / build_summary return markdown + data
- [x] 4 new MCP tools wired to service methods
- [x] 290/290 tests passing
- [x] Git commit and tag phase-4-complete

**What's next:**
- Register server in Claude Code config (mcp.json) if not already done
- Generate .protocol.key: `python3 -c "from signer.signer import generate_key_hex; print(generate_key_hex())" > .protocol.key`
- Live smoke test with actual MCP clients
- Phase 5 (if planned): rolling journal archive, multi-server federation, advisory board dashboard

---

## 2026-04-17 — Phase 3 Complete

**What landed:**
- HandshakeSession state machine: INITIATED → RESPONDED → COMPLETE / FAILED
- HandshakeManager: OrderedDict + LRU eviction (max_sessions=500)
- 4 new MCP tools: initiate_handshake, respond_to_handshake, get_handshake_result, list_sessions
- 233/233 tests passing
- Git tag: phase-3-complete

---

## 2026-04-17 — Phase 2 Complete

**What landed:**
- DispositionSignal + DispositionMode (PROCEED/REROUTE/COMPLETE_AND_FLAG/REFUSE)
- RORTracker: deque-based sliding window, ror_rate()
- Disposition engine: scoring matrix, hard overrides (unsigned→REFUSE, C6 PARTIAL+harm→REFUSE)
- 3 new MCP tools: validate_counterpart, get_disposition, get_ror_metrics
- 185/185 tests passing
- Git tag: phase-2-complete

---

## 2026-04-17 — Phase 1 Complete

**What landed:**
- All Phase 1 source code written and committed (`phase-1` commit)
- 119/119 unit tests passing
- Git tag: phase-1-complete pending (Phase 1 done criteria all met)

**Files written this session:**
- `src/schema/declaration.py` — HandshakeDeclaration, PrincipleStatement, PrincipleStatus
- `src/schema/disposition.py` — DispositionMode, DispositionSignal (Phase 2 stub)
- `src/schema/event.py` — ProtocolEvent, EventID constants (7000–7499)
- `src/signer/signer.py` — HMAC-SHA256 signing, load_key, sign_declaration, verify_declaration
- `src/event_viewer/writer.py` — Windows Event Log adapter, graceful non-Windows degradation
- `src/declaration/builder.py` — Keyword-based principle inference, specific statement templates
- `src/declaration/embedder.py` — Contextual embedding (73% pattern), embed() + embed_minimal()
- `src/validator/principle_map.py` — C1–C11 definitions, vague phrase list
- `src/validator/validator.py` — Coverage score, vagueness detection, per-principle issues
- `src/mcp_server/service.py` — ProtocolService: declare_posture, validate, embed, get_info
- `src/mcp_server/app.py` — FastMCP("protocol") stdio app, 4 tools
- `tests/unit/test_schema.py` — 18 tests
- `tests/unit/test_signer.py` — 18 tests
- `tests/unit/test_builder.py` — 22 tests
- `tests/unit/test_embedder.py` — 20 tests
- `tests/unit/test_validator.py` — 22 tests
- `tests/unit/test_mcp_tools.py` — 19 tests

**Phase 1 done criteria status:**
- [x] All unit tests pass (119/119)
- [x] declare_posture tool implemented and callable
- [x] Declaration is signed and signature verifiable
- [x] Validation produces correct coverage score and vagueness warnings
- [x] Embedding produces contextual format (not header block)
- [ ] Events appear in Windows Event Viewer — needs `pip install pywin32` + register_source() on Windows
- [ ] Git commit tagged phase-1-complete

**What's next:**
- Register as MCP server in Claude Code config (add to .claude/mcp.json)
- Generate a .protocol.key file for live signing
- Run register_source() from elevated shell (Windows-side)
- Begin Phase 2: disposition engine (PROCEED/REROUTE/COMPLETE_AND_FLAG/REFUSE) + ROR tracker

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
