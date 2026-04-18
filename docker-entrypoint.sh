#!/bin/sh
set -e

DATA_DIR="${PROTOCOL_DATA_DIR:-/data}"
mkdir -p "$DATA_DIR"

# Set resolved paths
export PROTOCOL_HMAC_KEY_PATH="${PROTOCOL_HMAC_KEY_PATH:-$DATA_DIR/.protocol.key}"
export PROTOCOL_JOURNAL_PATH="${PROTOCOL_JOURNAL_PATH:-$DATA_DIR/.protocol_journal.jsonl}"
export PROTOCOL_ROR_PATH="${PROTOCOL_ROR_PATH:-$DATA_DIR/.protocol_ror.json}"
export PROTOCOL_SQLITE_PATH="${PROTOCOL_SQLITE_PATH:-$DATA_DIR/protocol_events.db}"
export PERSISTENCE_BACKEND="${PERSISTENCE_BACKEND:-sqlite}"

PORT="${PORT:-8000}"
echo "[entrypoint] Starting 10+1 Protocol dashboard on 0.0.0.0:${PORT}"
exec uvicorn dashboard_main:app --host 0.0.0.0 --port "$PORT"
