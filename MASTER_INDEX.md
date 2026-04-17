# MASTER INDEX — 10+1 Protocol MCP Server

Every file in this project, one line each. Update whenever a file is added or removed.

---

## Discipline Files

| File | Purpose |
|------|---------|
| `CLAUDE.md` | Architecture rules, layout, workflow rules for Claude sessions |
| `README.md` | Public-facing project description |
| `MASTER_INDEX.md` | This file — complete project file registry |
| `DECISIONS.md` | Architectural decisions with rationale |
| `PATTERNS.md` | Reusable patterns and their source locations |
| `MEMORY.md` | Session working notes, state across sessions |
| `PHASES/PHASE_1.md` | Phase 1 — Declaration + Validation + Signing + MCP skeleton |
| `PHASES/PHASE_2.md` | Phase 2 — Disposition engine + ROR tracker |
| `PHASES/PHASE_3.md` | Phase 3 — Protocol exchange loop (stateful handshake sessions) |
| `PHASES/PHASE_4.md` | Phase 4 — Reporting + persistence |

---

## Knowledge Base (read-only)

| File | Contents |
|------|---------|
| `knowledge_base/finite_agent_protocol.md` | Handshake Declaration spec, four modes, ROR metric definition |
| `knowledge_base/moltbook_experiment_report_FINAL.docx` | Four empirical findings from Moltbook experiment |
| `knowledge_base/10p1_standard_v01.docx` | 10+1 Standard specification v0.1 |
| `knowledge_base/10p1_translation_of_principles.docx` | Principle translation document |
| `knowledge_base/10p1_translation_governance_canon.docx` | Translation to governance canon |
| `knowledge_base/handshake_protocol_testing_report.docx` | Handshake testing results |
| `knowledge_base/experiment_summary_advisory_board.pdf` | Advisory board experiment summary |
| `knowledge_base/cooperation_ceiling_analysis.docx` | Trained Politeness Ceiling analysis |

---

## Source — Schema Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/schema/__init__.py` | Package init |
| `src/schema/declaration.py` | Pydantic v2 model: HandshakeDeclaration |
| `src/schema/disposition.py` | Pydantic v2 model: DispositionSignal |
| `src/schema/event.py` | Pydantic v2 model: ProtocolEvent |

---

## Source — Declaration Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/declaration/__init__.py` | Package init |
| `src/declaration/builder.py` | HandshakeDeclaration builder |
| `src/declaration/embedder.py` | Contextual embedder — wraps declaration into prompt context (73% finding) |

---

## Source — Validator Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/validator/__init__.py` | Package init |
| `src/validator/validator.py` | Declaration validator — maps fields to C1–C11, scores compliance |
| `src/validator/principle_map.py` | Mapping table: declaration fields → Standard principle IDs |

---

## Source — Signer Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/signer/__init__.py` | Package init |
| `src/signer/signer.py` | HMAC-SHA256 posture signing |

---

## Source — Event Viewer Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/event_viewer/__init__.py` | Package init |
| `src/event_viewer/writer.py` | Windows Event Log writer (IDs 7000–7499, source: 10plus1-Protocol) |

---

## Source — Dispositioner Layer (Phase 2)

| File | Purpose |
|------|---------|
| `src/dispositioner/__init__.py` | Package init |
| `src/dispositioner/engine.py` | Four-mode disposition logic (PROCEED/REROUTE/COMPLETE_AND_FLAG/REFUSE) |
| `src/dispositioner/ror_tracker.py` | ROR metric tracker (rolling window, in-memory) |

---

## Source — Handshake Layer (Phase 3)

| File | Purpose |
|------|---------|
| `src/handshake/__init__.py` | Package init |
| `src/handshake/session.py` | HandshakeSession model (INITIATED → RESPONDED → COMPLETE state machine) |
| `src/handshake/manager.py` | HandshakeManager — session store and lifecycle |

---

## Source — Reporting Layer (Phase 4)

| File | Purpose |
|------|---------|
| `src/reporting/__init__.py` | Package init |
| `src/reporting/journal.py` | Event journal — append-only JSONL (.protocol_journal.jsonl) |
| `src/reporting/ror_persistence.py` | ROR snapshot persistence (.protocol_ror.json) |
| `src/reporting/exporter.py` | Export session reports and ROR trend reports (JSON + markdown) |

---

## Source — MCP Server (Phase 1–4)

| File | Purpose |
|------|---------|
| `src/mcp_server/__init__.py` | Package init |
| `src/mcp_server/app.py` | FastMCP("protocol") app, tool registration, stdio transport |
| `src/mcp_server/service.py` | Service layer — orchestrates all layers |
| `src/mcp_server/tools.py` | MCP tool definitions (all phases) |

---

## Tests

| File | Purpose | Phase |
|------|---------|-------|
| `tests/__init__.py` | Package init | — |
| `tests/unit/__init__.py` | Unit test package | — |
| `tests/unit/test_schema.py` | Schema model tests | 1 |
| `tests/unit/test_builder.py` | Declaration builder tests | 1 |
| `tests/unit/test_embedder.py` | Contextual embedder tests | 1 |
| `tests/unit/test_validator.py` | Validator principle mapping tests | 1 |
| `tests/unit/test_signer.py` | HMAC signing/verification tests | 1 |
| `tests/unit/test_dispositioner.py` | Four-mode disposition logic tests | 2 |
| `tests/unit/test_ror_tracker.py` | ROR tracker tests | 2 |
| `tests/unit/test_handshake.py` | Handshake session state machine tests | 3 |
| `tests/unit/test_mcp_tools.py` | End-to-end MCP tool tests | 1–4 |
| `tests/unit/test_reporting.py` | Journal, ROR persistence, exporter tests | 4 |
| `tests/integration/__init__.py` | Integration test package | — |

---

## Config

| File | Purpose |
|------|---------|
| `pyproject.toml` | Hatchling build, dependencies, project metadata |
| `.env.example` | Environment variable template |
| `.env` | Local environment (gitignored — copy of .env.example with local values) |
| `.gitignore` | Standard Python + .env + .key ignores |
| `.protocol.key` | HMAC signing key (gitignored — 64-byte hex secret) |
| `.protocol_journal.jsonl` | Event journal (gitignored — runtime append-only log) |
| `.protocol_ror.json` | ROR snapshot (gitignored — runtime persistence) |
| `smoke_test.py` | Smoke test script for manual validation |

---

## Phase Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Declaration + Validation + Signing + MCP skeleton | Complete |
| 2 | Disposition engine + ROR tracker | Complete |
| 3 | Protocol exchange loop (stateful sessions) | Complete |
| 4 | Reporting + persistence | Complete |

---

*Last updated: 2026-04-17 — all 4 phases complete*
