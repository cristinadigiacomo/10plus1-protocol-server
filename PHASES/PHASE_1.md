# PHASE 1 — Declaration, Validation, Signing, and MCP Skeleton

## Goal

Deliver a working MCP server that can:
1. Accept agent context and build a signed Handshake Declaration mapped to C1–C11
2. Validate a declaration for schema compliance and principle coverage
3. Embed a declaration contextually into a prompt string (the 73% pattern)
4. Expose these capabilities as MCP tools
5. Log all operations to Windows Event Log (7000–7499)

Disposition logic (the four modes) is Phase 2. Phase 1 ends with a working declaration pipeline.

---

## Deliverables

### Schema Layer (`src/schema/`)

**`declaration.py`**
```
HandshakeDeclaration
  id: str                          # uuid4
  agent_id: str                    # caller-provided agent identifier
  declared_at: str                 # ISO 8601 UTC
  principles: dict[str, PrincipleStatement]  # keyed by C1–C11
  signature: str | None
  signed_at: str | None
  context_summary: str | None      # optional human-readable summary

PrincipleStatement
  principle_id: str                # C1–C11
  status: PrincipleStatus          # COMPLIANT | PARTIAL | DECLARED | NOT_APPLICABLE
  behavioral_statement: str        # specific behavior (not vague — see Finding 2)
  constraints: list[str]           # known limitations or exceptions
```

**`disposition.py`** (stub for Phase 2)
```
DispositionMode: Enum
  PROCEED, REROUTE, COMPLETE_AND_FLAG, REFUSE
```

**`event.py`**
```
ProtocolEvent
  event_id: int                    # 7000–7499
  source: str                      # "10plus1-Protocol"
  category: ProtocolEventCategory
  message: str
  data: dict
  timestamp: str
```

---

### Signer Layer (`src/signer/`)

**`signer.py`** — adapted from governance
- `load_key(path: str) -> bytes`
- `sign_declaration(declaration: HandshakeDeclaration, key: bytes) -> HandshakeDeclaration`
  — adds `signature` (HMAC-SHA256 of canonical JSON) and `signed_at`
- `verify_declaration(declaration: HandshakeDeclaration, key: bytes) -> bool`
- `ProtocolSigningError` exception

Canonical JSON: `json.dumps(declaration.model_dump(exclude={"signature", "signed_at"}), sort_keys=True)`

---

### Declaration Layer (`src/declaration/`)

**`builder.py`**
- `build(agent_id: str, context: str, principles: list[str] | None) -> HandshakeDeclaration`
  — constructs declaration with principle statements inferred from context
  — if `principles` is None, attempts to cover all 11 (with NOT_APPLICABLE where not determinable)
  — behavioral_statement must be specific, not vague (Finding 2 enforcement)

**`embedder.py`**
- `embed(declaration: HandshakeDeclaration, prompt: str) -> str`
  — wraps the declaration contextually into the prompt string
  — does NOT create a header block (see DEC-003, Finding 1)
  — inserts posture language at the start of task context, woven into task framing

---

### Validator Layer (`src/validator/`)

**`principle_map.py`**
```python
# Maps declaration fields to Standard principle IDs
PRINCIPLE_MAP = {
    "C1": {"name": "Transparency", "required_fields": ["behavioral_statement"], ...},
    "C2": {"name": "Consent", ...},
    # ... C1–C11
}
```

**`validator.py`**
- `validate(declaration: HandshakeDeclaration) -> ValidationResult`

```
ValidationResult
  valid: bool
  principles_covered: list[str]     # which of C1–C11 are present
  principles_missing: list[str]     # which are absent
  issues: list[ValidationIssue]     # per-principle issues
  coverage_score: float             # 0.0–1.0 (covered / 11)
```

- **Vagueness check**: if `behavioral_statement` contains only generic language with no specifics, raise `ValidationIssue(severity="WARNING", message="behavioral_statement is too vague — per Moltbook Finding 2, specific statements have significantly higher behavioral effect")`

---

### Event Viewer Layer (`src/event_viewer/`)

**`writer.py`** — adapted from governance

Event ID assignments:
```
7000 — Declaration created
7001 — Declaration signed
7002 — Declaration signing failed
7010 — Declaration validation passed
7011 — Declaration validation failed
7012 — Declaration schema error
7020 — Posture embedded in prompt
7100 — MCP server started
7101 — MCP server stopped
7102 — MCP tool error
7103 — MCP tool call (info)
```

---

### MCP Server (`src/mcp_server/`)

**Tools (Phase 1):**

| Tool | Parameters | Returns |
|------|-----------|---------|
| `declare_posture` | `agent_id: str`, `context: str`, `principles: list[str] \| None` | Signed declaration + validation result |
| `validate_declaration` | `declaration_json: str` | ValidationResult |
| `embed_posture` | `declaration_json: str`, `prompt: str` | Embedded prompt string |
| `get_server_info` | — | Server version, phase, event count |

**Stub tools (Phase 2, not implemented in Phase 1):**

| Tool | Status |
|------|--------|
| `get_disposition` | Phase 2 |
| `get_ror_metrics` | Phase 2 |
| `validate_counterpart` | Phase 2 |

---

### Tests (`tests/unit/`)

| Test file | What it covers |
|-----------|---------------|
| `test_schema.py` | HandshakeDeclaration creation, field validation, Pydantic v2 |
| `test_signer.py` | sign → verify roundtrip, tamper detection, ProtocolSigningError |
| `test_builder.py` | Declaration built from context, principle coverage, vagueness check |
| `test_embedder.py` | Contextual embedding produces correct format, not header block |
| `test_validator.py` | Coverage score, missing principles, vagueness warnings |
| `test_mcp_tools.py` | Each tool: valid input, invalid input, dual-channel response shape |

---

## Build Order

1. `pyproject.toml` + `.env.example` + `.gitignore`
2. `src/schema/declaration.py`, `src/schema/disposition.py`, `src/schema/event.py`
3. `src/signer/signer.py` (adapt from governance)
4. `src/event_viewer/writer.py` (adapt from governance)
5. `src/declaration/builder.py`, `src/declaration/embedder.py`
6. `src/validator/principle_map.py`, `src/validator/validator.py`
7. `src/mcp_server/service.py`, `src/mcp_server/tools.py`, `src/mcp_server/app.py`
8. `tests/unit/` — all test files
9. Run tests, fix failures
10. Git commit: `phase-1: declaration pipeline + MCP skeleton`

---

## Phase 1 Done When

- [ ] All unit tests pass
- [ ] `declare_posture` tool callable from Claude Code
- [ ] Declaration is signed and signature verifiable
- [ ] Validation produces correct coverage score and vagueness warnings
- [ ] Embedding produces contextual format (not header block)
- [ ] Events appear in Windows Event Viewer under source `10plus1-Protocol`
- [ ] Git commit tagged `phase-1-complete`

---

## Not In Phase 1

- Disposition engine (four modes) — Phase 2
- ROR tracking — Phase 2
- Counterpart declaration validation — Phase 2
- Any network transport — out of scope

---

## Phase 2 Preview

Four-mode disposition engine:
- Input: validated, signed declaration pair (self + counterpart)
- Output: DispositionSignal with mode, rationale, and recommended action
- ROR tracker: rolling window count of REROUTE + REFUSE, surfaced via `get_ror_metrics` tool
- Counterpart validation: verify counterpart's signature before accepting their declaration
