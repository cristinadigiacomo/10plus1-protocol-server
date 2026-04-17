# PHASE 2 — Disposition Engine + ROR Tracker

## Goal

Deliver the four-mode disposition engine. Given two declarations (self + counterpart),
produce a structured DispositionSignal telling the receiving agent how to proceed.
Track ROR (Refused-Or-Rerouted) rate as the primary health metric.

## New capabilities over Phase 1

| Tool | Phase 1 | Phase 2 |
|------|---------|---------|
| `declare_posture` | ✓ | unchanged |
| `validate_declaration` | ✓ | unchanged |
| `embed_posture` | ✓ | unchanged |
| `get_server_info` | ✓ | extended with ROR stats |
| `validate_counterpart` | — | ✓ new |
| `get_disposition` | — | ✓ new |
| `get_ror_metrics` | — | ✓ new |

## Disposition Logic

The engine compares two validated declarations and produces a DispositionMode.

### Scoring model

Each principle that appears in both declarations is compared:
- Status COMPLIANT vs COMPLIANT → full match (score 1.0)
- Status COMPLIANT vs DECLARED → near match (score 0.8)
- Status DECLARED vs DECLARED → near match (score 0.8)
- Status PARTIAL vs COMPLIANT or DECLARED → partial match (score 0.5)
- Status NOT_APPLICABLE on either → skip (not scored)
- Principle absent from counterpart → gap (score 0.0)

Aggregate alignment score = sum(scored_principles) / max(principles_in_self, 1)

### Mode thresholds

| Score | Mode |
|-------|------|
| >= 0.75 | PROCEED |
| >= 0.50 | REROUTE |
| >= 0.25 | COMPLETE_AND_FLAG |
| < 0.25 | REFUSE |

Hard overrides (always REFUSE regardless of score):
- Counterpart has C6 (Safety) with status PARTIAL and a constraint mentioning "harm"
- Counterpart declaration is unsigned and `require_signature=True`
- Counterpart declaration fails schema validation

## ROR Tracker

Tracks disposition history in memory (per-session, not persisted in Phase 2).

```
RORTracker
  window_size: int = 100          # rolling window
  history: deque[DispositionMode]
  
  record(mode: DispositionMode)
  ror_rate() -> float             # (REROUTE + REFUSE) / total
  counts() -> dict[str, int]      # per-mode counts
  total() -> int
```

## New MCP tools

### validate_counterpart
Input: counterpart_declaration_json, require_signature=True
Output: validation result + signature verification status
Logs: 7100-7102 range (reuses Phase 1 validation IDs)

### get_disposition
Input: self_declaration_json, counterpart_declaration_json, require_signature=True
Output: DispositionSignal with mode, score, rationale, recommended_action
Logs: 7200-7203 range (disposition event IDs)
Side effect: records mode in ROR tracker

### get_ror_metrics
Input: none
Output: ror_rate, counts per mode, total, window_size

## Event IDs used in Phase 2

| ID | Event |
|----|-------|
| 7200 | Disposition: PROCEED |
| 7201 | Disposition: REROUTE |
| 7202 | Disposition: COMPLETE_AND_FLAG |
| 7203 | Disposition: REFUSE |

## Build order

1. `src/dispositioner/ror_tracker.py`
2. `src/dispositioner/engine.py`
3. `src/dispositioner/__init__.py`
4. Extend `src/schema/disposition.py` (add alignment_score, gap_report)
5. Extend `src/mcp_server/service.py` (3 new methods)
6. Extend `src/mcp_server/app.py` (3 new tools)
7. `tests/unit/test_dispositioner.py`
8. `tests/unit/test_ror_tracker.py`
9. Extend `tests/unit/test_mcp_tools.py` (new tool tests)
10. Run tests, fix, commit

## Phase 2 done when

- [ ] All unit tests pass
- [ ] `get_disposition` returns correct mode for alignment scores across all four bands
- [ ] Hard overrides (unsafe counterpart, unsigned) produce REFUSE
- [ ] ROR rate tracks correctly over session
- [ ] `get_ror_metrics` tool returns live counts
- [ ] Git commit tagged `phase-2-complete`
