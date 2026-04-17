# PHASE 4 — Reporting & Persistence

## Goal

Survive restarts. Export data. Give operators a clear picture of what the
Protocol is doing across sessions.

Three concerns:
1. **Event journal** — local JSONL file that persists all Protocol events so
   they are readable without Windows Event Viewer and survive server restarts.
2. **ROR persistence** — ROR snapshots saved with timestamps so trend data
   accumulates across sessions.
3. **Export** — structured reports for the advisory board and operators:
   per-session, per-server, and ROR trend.

## New source files

```
src/reporting/__init__.py
src/reporting/journal.py        — append-only JSONL event journal
src/reporting/ror_persistence.py — timestamped ROR snapshot store
src/reporting/exporter.py       — report builder (JSON + markdown summary)
```

## File formats

**Event journal** — `.protocol_journal.jsonl`
One JSON object per line. Fields: timestamp, event_id, category, agent_id,
declaration_id, message, data. Appended on every _log() call.

**ROR snapshots** — `.protocol_ror.json`
JSON array of `{timestamp, ror_rate, total, counts}`. A snapshot is written
after every get_disposition() or respond_to_handshake() call.

## New MCP tools

| Tool | Description |
|------|-------------|
| `get_event_journal` | Read recent journal entries (n, category filter) |
| `export_session_report` | Full session report: declarations, disposition, gaps |
| `export_ror_report` | ROR trend over all snapshots + markdown summary |
| `get_summary` | Server-wide dashboard: sessions, ROR, recent events |

## Export format

All exports return dual-channel:
- `data` — structured JSON (machine-consumable, advisory board ingest)
- `message` — markdown summary string (paste into a doc, send to a human)

## Build order

1. `src/reporting/__init__.py`
2. `src/reporting/journal.py`
3. `src/reporting/ror_persistence.py`
4. `src/reporting/exporter.py`
5. Extend `src/mcp_server/service.py` — wire journal into _log(), 4 new methods
6. Extend `src/mcp_server/app.py` — 4 new tools
7. `tests/unit/test_reporting.py`
8. Extend `tests/unit/test_mcp_tools.py`
9. Run tests, commit, tag phase-4-complete

## Phase 4 done when

- [ ] All unit tests pass
- [ ] Events written to JSONL journal on every _log() call
- [ ] ROR snapshot written after every disposition
- [ ] `get_event_journal` returns parseable entries
- [ ] `export_session_report` includes declaration details, gaps, recommended action
- [ ] `export_ror_report` shows trend across snapshots
- [ ] `get_summary` gives dashboard view in one call
- [ ] Git commit tagged `phase-4-complete`
