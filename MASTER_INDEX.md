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
| `PHASES/PHASE_1.md` | Phase 1 specification — Declaration + Validation + Signing |

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

## Source — Declaration Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/declaration/__init__.py` | Package init |
| `src/declaration/builder.py` | HandshakeDeclaration builder — assembles declaration from agent context |
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
| `src/signer/signer.py` | HMAC-SHA256 posture signing (adapted from governance) |

---

## Source — Dispositioner Layer (Phase 2)

| File | Purpose |
|------|---------|
| `src/dispositioner/__init__.py` | Package init |
| `src/dispositioner/engine.py` | Four-mode disposition logic (PROCEED/REROUTE/COMPLETE_AND_FLAG/REFUSE) |
| `src/dispositioner/ror_tracker.py` | ROR metric tracker |

---

## Source — Event Viewer Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/event_viewer/__init__.py` | Package init |
| `src/event_viewer/writer.py` | Windows Event Log writer (adapted from governance, IDs 7000–7499) |

---

## Source — Schema Layer (Phase 1)

| File | Purpose |
|------|---------|
| `src/schema/__init__.py` | Package init |
| `src/schema/declaration.py` | Pydantic v2 model: HandshakeDeclaration |
| `src/schema/disposition.py` | Pydantic v2 model: DispositionSignal |
| `src/schema/event.py` | Pydantic v2 model: ProtocolEvent (adapted from governance) |

---

## Source — MCP Server (Phase 1)

| File | Purpose |
|------|---------|
| `src/mcp_server/__init__.py` | Package init |
| `src/mcp_server/app.py` | FastMCP("protocol") app, tool registration, app.run(transport="stdio") |
| `src/mcp_server/service.py` | Service layer — orchestrates declaration, validation, signing, disposition |
| `src/mcp_server/tools.py` | MCP tool definitions (declare_posture, validate_counterpart, get_disposition, get_ror_metrics) |

---

## Tests

| File | Purpose |
|------|---------|
| `tests/__init__.py` | Package init |
| `tests/unit/__init__.py` | Unit test package |
| `tests/unit/test_declaration.py` | Declaration builder and schema tests |
| `tests/unit/test_validator.py` | Validator principle mapping tests |
| `tests/unit/test_signer.py` | HMAC signing/verification tests |
| `tests/unit/test_dispositioner.py` | Four-mode disposition logic tests |
| `tests/integration/__init__.py` | Integration test package |
| `tests/integration/test_mcp_tools.py` | End-to-end MCP tool tests |

---

## Config

| File | Purpose |
|------|---------|
| `pyproject.toml` | Hatchling build, dependencies, project metadata |
| `.env.example` | Environment variable template (HMAC key, log level) |
| `.gitignore` | Standard Python + .env ignores |

---

*Last updated: 2026-04-17 — Phase 1 planning*
