# PHASE 3 — Protocol Exchange Loop

## Goal

Deliver the full AI↔AI handshake session: a stateful, two-step exchange where
agent A initiates with its own declaration, agent B responds with theirs, and
the Protocol engine computes the disposition and closes the session.

This is the complete loop the Finite Agent Protocol describes.

## New capabilities over Phase 2

| Tool | Phase 2 | Phase 3 |
|------|---------|---------|
| `get_disposition` | ✓ stateless | unchanged |
| `initiate_handshake` | — | ✓ new |
| `respond_to_handshake` | — | ✓ new |
| `get_handshake_result` | — | ✓ new |
| `list_sessions` | — | ✓ new |

## Session State Machine

```
INITIATED → RESPONDED → COMPLETE
     ↓            ↓
   FAILED       FAILED
```

- **INITIATED**: Agent A has submitted its declaration and received a session_id.
  Waiting for counterpart response.
- **RESPONDED**: Agent B has submitted their declaration. Disposition computed.
  Equivalent to COMPLETE — kept separate for event logging clarity.
- **COMPLETE**: Disposition finalized. Session closed.
- **FAILED**: Something went wrong (invalid declaration, hard override triggered,
  session not found). Session cannot advance.

## HandshakeSession model

```
HandshakeSession
  session_id: str          # uuid4
  state: SessionState
  initiator_id: str        # agent_id of initiating agent
  initiator_declaration: HandshakeDeclaration
  counterpart_id: str | None
  counterpart_declaration: HandshakeDeclaration | None
  disposition: DispositionSignal | None
  alignment_report: AlignmentReport | None
  initiated_at: str        # ISO 8601
  responded_at: str | None
  completed_at: str | None
  error: str | None        # populated on FAILED
```

## HandshakeManager

In-memory store (dict[session_id → HandshakeSession]).
Phase 4 will add JSON file persistence.

Methods:
- `create(initiator_declaration) → HandshakeSession`
- `respond(session_id, counterpart_declaration, require_signature) → HandshakeSession`
- `get(session_id) → HandshakeSession`
- `list_recent(n) → list[HandshakeSession]`

## New event IDs (within SERVER range 7400-7499)

| ID | Event |
|----|-------|
| 7410 | HANDSHAKE_INITIATED |
| 7411 | HANDSHAKE_RESPONDED |
| 7412 | HANDSHAKE_COMPLETE |
| 7413 | HANDSHAKE_FAILED |

## Build order

1. `src/handshake/__init__.py`
2. `src/handshake/session.py` — SessionState enum, HandshakeSession model
3. `src/handshake/manager.py` — HandshakeManager
4. Extend `src/schema/event.py` — add 7410–7413 event ID constants
5. Extend `src/mcp_server/service.py` — 4 new methods
6. Extend `src/mcp_server/app.py` — 4 new tools
7. `tests/unit/test_handshake.py`
8. Extend `tests/unit/test_mcp_tools.py`
9. Run tests, commit

## Phase 3 done when

- [ ] All unit tests pass
- [ ] `initiate_handshake` creates a session and returns session_id
- [ ] `respond_to_handshake` advances state and returns disposition
- [ ] FAILED state populated on hard overrides and bad input
- [ ] `list_sessions` returns sessions most-recent-first
- [ ] Git commit tagged `phase-3-complete`
