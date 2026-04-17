# PATTERNS — 10+1 Protocol MCP Server

Reusable patterns and exactly where to find them. Before writing new code, check here first.

---

## PATTERN-001 — HMAC-SHA256 Signing

**Source:** `/mnt/c/projects/governance/src/hmac_signer/signer.py`

**Functions:**
- `load_key(path: str) -> bytes` — load HMAC key from file
- `compute_hmac(key: bytes, payload: str) -> str` — compute hex digest
- `sign(payload: dict, key: bytes) -> dict` — add `signature` and `signed_at` fields to payload
- `verify(payload: dict, key: bytes) -> bool` — verify signature, raise `HMACVerificationError` on failure
- `HMACVerificationError` — exception class

**Adaptation for Protocol:**
- Copy to `src/signer/signer.py`
- Change context strings from "governance" to "protocol" in log messages
- Keep algorithm identical

---

## PATTERN-002 — Windows Event Log Writer

**Source:** `/mnt/c/projects/governance/src/event_viewer/writer.py`

**Functions:**
- `register_source(source_name: str)` — register event source in registry (requires admin first run)
- `write_event(source: str, event_id: int, message: str, level: str)` — write to Windows Event Log
- `read_events(source: str, count: int) -> list[dict]` — read recent events from log

**Adaptation for Protocol:**
- Copy to `src/event_viewer/writer.py`
- Change `SOURCE_NAME = "10plus1-Governance"` → `SOURCE_NAME = "10plus1-Protocol"`
- Change event ID base: Governance uses 5000–5499 and 6000–6499; Protocol uses **7000–7499**
- Keep pywin32 import pattern and error handling identical

**Event ID Allocation for Protocol:**

| Range | Category |
|-------|---------|
| 7000–7099 | Declaration events (created, signed, failed) |
| 7100–7199 | Validation events (passed, failed, schema error) |
| 7200–7299 | Disposition events (PROCEED, REROUTE, COMPLETE_AND_FLAG, REFUSE) |
| 7300–7399 | Signing events (signed, verified, HMAC error) |
| 7400–7499 | Server/session events (startup, shutdown, tool errors) |

---

## PATTERN-003 — FastMCP App Structure

**Source:** `/mnt/c/projects/governance/src/mcp_server/app.py`

**Pattern:**
```python
from mcp.server.fastmcp import FastMCP
from .service import ProtocolService

def build_app(service: ProtocolService) -> FastMCP:
    app = FastMCP("protocol")

    @app.tool()
    def declare_posture(...) -> dict:
        ...

    return app

if __name__ == "__main__":
    service = ProtocolService()
    app = build_app(service)
    app.run(transport="stdio")
```

**Rules:**
- `FastMCP("protocol")` — server name must be "protocol"
- Service layer is injected, not instantiated inside tools
- `app.run(transport="stdio")` — no HTTP transport
- Every tool returns `{"message": str, "data": dict}` dual-channel response

---

## PATTERN-004 — Service Layer Separation

**Source:** `/mnt/c/projects/governance/src/mcp_server/service.py`

**Pattern:**
- MCP tools are thin wrappers that call service methods
- Service methods contain all business logic
- Service is instantiated once, passed to `build_app()`
- No business logic lives in `app.py` or `tools.py`

---

## PATTERN-005 — Pydantic v2 Model Pattern

**Source:** `/mnt/c/projects/governance/src/schema/event.py`

**Pattern:**
```python
from pydantic import BaseModel, field_validator, model_validator
from enum import Enum

class DispositionMode(str, Enum):
    PROCEED = "PROCEED"
    REROUTE = "REROUTE"
    COMPLETE_AND_FLAG = "COMPLETE_AND_FLAG"
    REFUSE = "REFUSE"

class HandshakeDeclaration(BaseModel):
    agent_id: str
    principles: dict[str, PrincipleStatement]
    signed_at: str | None = None
    signature: str | None = None

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("agent_id cannot be empty")
        return v.strip()
```

**Rules:**
- Use `str, Enum` base for all string enums
- `model_dump()` not `.dict()`
- `model_validate()` not `parse_obj()`
- No `Optional[X]` — use `X | None`

---

## PATTERN-006 — Contextual Embedding (73% Finding)

**Source:** `knowledge_base/moltbook_experiment_report_FINAL.docx`, Finding 1

**Pattern:** Do NOT do this:
```
[POSTURE DECLARATION]
Principle C1: Transparency - compliant
...
[END POSTURE DECLARATION]
Now, here is my task: ...
```

**Do this instead:**
```
I am working on [task]. As part of this work, my operating approach is 
grounded in the following: [transparency about my process], [consent 
in how I handle decisions], [accountability for outcomes]. 

Specifically: [task content woven with posture context]
```

**Implementation:** `src/declaration/embedder.py` — `embed(declaration: HandshakeDeclaration, prompt: str) -> str`

---

## PATTERN-007 — Dual-Channel Tool Response

**Pattern:**
```python
def declare_posture(agent_id: str, context: str) -> dict:
    declaration = service.build_declaration(agent_id, context)
    return {
        "message": f"Posture declaration created for agent '{agent_id}'. "
                   f"Principles covered: {len(declaration.principles)}/11. "
                   f"Signature: {declaration.signature[:16]}...",
        "data": {
            "declaration_id": declaration.id,
            "agent_id": agent_id,
            "principles": declaration.model_dump()["principles"],
            "signed_at": declaration.signed_at,
            "signature": declaration.signature,
        }
    }
```

**Rules:**
- `message` is always a complete sentence(s) a human can read without looking at `data`
- `data` always has typed, stable field names that code can rely on
- Never return a bare string or a dict without both keys

---

## PATTERN-008 — pyproject.toml Structure

**Source:** `/mnt/c/projects/governance/pyproject.toml`

**Key dependencies to carry forward:**
```toml
[project]
name = "10plus1-protocol"
requires-python = ">=3.13"

[project.dependencies]
pydantic = ">=2.0"
mcp = { extras = ["cli"] }
pywin32 = ">=306"  # Windows Event Log
python-dotenv = ">=1.0"
```

**Scripts:**
```toml
[project.scripts]
10plus1-protocol = "src.mcp_server.app:main"
```
