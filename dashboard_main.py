"""Uvicorn entry point for the 10+1 Protocol dashboard.

Responsibilities on startup (before serving):
  1. Ensure data directory exists.
  2. Generate HMAC key if missing.
  3. Seed demo data if the journal is empty.
  4. Start uvicorn on $PORT (default 8000).

Environment variables
---------------------
PROTOCOL_DATA_DIR        Where to store journal, ROR snapshots, SQLite db.
                         Default: current working directory.
PROTOCOL_HMAC_KEY_PATH   Path to HMAC key file.
                         Default: $PROTOCOL_DATA_DIR/.protocol.key
PROTOCOL_JOURNAL_PATH    Path to JSONL journal.
                         Default: $PROTOCOL_DATA_DIR/.protocol_journal.jsonl
PROTOCOL_ROR_PATH        Path to ROR JSON snapshot file.
                         Default: $PROTOCOL_DATA_DIR/.protocol_ror.json
PERSISTENCE_BACKEND      'sqlite' or 'event_viewer'. Default: sqlite on non-Windows.
PROTOCOL_SQLITE_PATH     SQLite DB path. Default: $PROTOCOL_DATA_DIR/protocol_events.db
PORT                     HTTP port. Default: 8000.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure src/ is importable
# ---------------------------------------------------------------------------
_SRC = Path(__file__).parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
DATA_DIR    = Path(os.environ.get("PROTOCOL_DATA_DIR", "."))
KEY_PATH    = Path(os.environ.get("PROTOCOL_HMAC_KEY_PATH",  str(DATA_DIR / ".protocol.key")))
JOURNAL     = Path(os.environ.get("PROTOCOL_JOURNAL_PATH",   str(DATA_DIR / ".protocol_journal.jsonl")))
ROR         = Path(os.environ.get("PROTOCOL_ROR_PATH",       str(DATA_DIR / ".protocol_ror.json")))
SQLITE_PATH = Path(os.environ.get("PROTOCOL_SQLITE_PATH",    str(DATA_DIR / "protocol_events.db")))
PORT        = int(os.environ.get("PORT", "8000"))

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------

def _bootstrap() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    # All CWD-relative paths in ProtocolService (EventJournal, RORPersistence)
    # must resolve inside DATA_DIR, not /app.
    os.chdir(DATA_DIR)

    # Generate HMAC key if missing
    if not KEY_PATH.is_file() or KEY_PATH.stat().st_size == 0:
        import secrets
        KEY_PATH.write_text(secrets.token_hex(32))
        print(f"[bootstrap] Generated HMAC key at {KEY_PATH}")
    else:
        print(f"[bootstrap] HMAC key present at {KEY_PATH}")

    # Propagate resolved paths for ProtocolService and SQLite backend
    os.environ.setdefault("PROTOCOL_HMAC_KEY_PATH", str(KEY_PATH))
    os.environ.setdefault("PROTOCOL_SQLITE_PATH",   str(SQLITE_PATH))
    os.environ.setdefault("PERSISTENCE_BACKEND",    "sqlite")

    # Seed demo data if journal is empty
    from scripts.seed_demo import seed_if_empty
    seed_if_empty(
        journal_path=JOURNAL,
        ror_path=ROR,
        key_path=KEY_PATH,
    )


# ---------------------------------------------------------------------------
# Build the FastAPI app (called by uvicorn)
# ---------------------------------------------------------------------------

def _make_app():
    from dashboard.data import DataLayer
    from dashboard.app import create_app

    dl = DataLayer(journal_path=JOURNAL, ror_path=ROR)
    return create_app(data_layer=dl)


# Bootstrap runs at import time so uvicorn workers share the same state.
_bootstrap()
app = _make_app()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "dashboard_main:app",
        host="0.0.0.0",
        port=PORT,
        reload=False,
    )
