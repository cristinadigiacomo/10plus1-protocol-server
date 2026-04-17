"""
Phase 1 — FastMCP stdio server for the 10+1 Protocol.

Thin wrapper: exposes ProtocolService methods as MCP tools over stdio.
All logic lives in service.py — this file is plumbing.

Run from the project root:
    python -m src.mcp_server.app

Or via the installed script:
    10plus1-protocol

Environment variables
---------------------
PROTOCOL_HMAC_KEY_PATH   Path to HMAC key file (default: .protocol.key)
PROTOCOL_LOG_LEVEL       Logging level (default: INFO)

Authoritative sources
---------------------
PATTERNS.md PATTERN-003 (FastMCP app structure)
DECISIONS.md DEC-001 (stdio transport)
DECISIONS.md DEC-008 (dual-channel response)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from mcp_server.service import ProtocolService, ServiceError


def build_app(service: ProtocolService) -> FastMCP:
    """Build a FastMCP app bound to a concrete ProtocolService instance."""
    app = FastMCP("protocol")

    @app.tool(
        description=(
            "Build a signed Handshake Declaration for an agent's posture across "
            "the 10+1 Standard principles (C1–C11). "
            "Provide agent_id and a rich context string describing the task. "
            "The builder infers relevant principles from the context and assembles "
            "specific behavioral statements. Returns the signed declaration and a "
            "validation report with coverage score and any warnings."
        )
    )
    def declare_posture(
        agent_id: str,
        context: str,
        principles: list[str] | None = None,
        sign: bool = True,
    ) -> dict[str, Any]:
        """
        agent_id  : Identifier for the declaring agent (e.g. 'david_', 'nomos').
        context   : Task context — what the agent is about to do. Richer = better.
        principles: Optional list of principle IDs to include (e.g. ['C1','C4','C11']).
                    If omitted, all 11 are included.
        sign      : Whether to sign with HMAC (requires key file). Default True.
        """
        try:
            return service.declare_posture(
                agent_id=agent_id,
                context=context,
                principles=principles,
                sign=sign,
            )
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Validate an existing declaration JSON string against the 10+1 Standard "
            "principle map. Returns coverage score, per-principle issues, and "
            "vagueness warnings (per Moltbook Finding 2). "
            "Pass the 'declaration' field from a declare_posture response as declaration_json."
        )
    )
    def validate_declaration(declaration_json: str) -> dict[str, Any]:
        """
        declaration_json : JSON string of a HandshakeDeclaration.
        """
        try:
            return service.validate_declaration_json(declaration_json)
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Embed a HandshakeDeclaration contextually into a prompt string, "
            "following the 73% acknowledgment pattern from the Moltbook experiment. "
            "The posture is woven into the task framing — NOT placed in a header block. "
            "Pass declaration_json (from declare_posture) and the prompt to wrap. "
            "Use minimal=true for token-sensitive contexts."
        )
    )
    def embed_posture(
        declaration_json: str,
        prompt: str,
        minimal: bool = False,
    ) -> dict[str, Any]:
        """
        declaration_json : JSON string of a HandshakeDeclaration.
        prompt           : The task prompt to embed posture into.
        minimal          : Use compact single-sentence embedding (default False).
        """
        try:
            return service.embed_posture(
                declaration_json=declaration_json,
                prompt=prompt,
                minimal=minimal,
            )
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Return Protocol server status: phase, version, event count, "
            "key file presence, available tools, and current ROR metrics. "
            "Call this to verify the server is running correctly."
        )
    )
    def get_server_info() -> dict[str, Any]:
        return service.get_server_info()

    # --- Phase 2 tools ---------------------------------------------------

    @app.tool(
        description=(
            "Validate a counterpart agent's HandshakeDeclaration before accepting it. "
            "Checks schema validity, principle coverage, vagueness warnings, and "
            "whether the declaration is signed. "
            "Pass the counterpart's declaration JSON and set require_signature=true "
            "to enforce that it must be signed."
        )
    )
    def validate_counterpart(
        counterpart_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """
        counterpart_json   : JSON string of the counterpart's HandshakeDeclaration.
        require_signature  : Warn if unsigned (default True).
        """
        try:
            return service.validate_counterpart_declaration(
                counterpart_json=counterpart_json,
                require_signature=require_signature,
            )
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Compute a disposition signal from two declarations: your own and a counterpart's. "
            "Returns one of four modes: PROCEED (aligned), REROUTE (gap — adjust approach), "
            "COMPLETE_AND_FLAG (complete but flag for review), REFUSE (incompatible — stop). "
            "Also records the mode in the session ROR tracker. "
            "Pass both declaration JSON strings from declare_posture responses."
        )
    )
    def get_disposition(
        self_declaration_json: str,
        counterpart_declaration_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """
        self_declaration_json        : JSON of your own declaration (from declare_posture).
        counterpart_declaration_json : JSON of the counterpart's declaration.
        require_signature            : REFUSE if counterpart is unsigned (default True).
        """
        try:
            return service.get_disposition(
                self_declaration_json=self_declaration_json,
                counterpart_declaration_json=counterpart_declaration_json,
                require_signature=require_signature,
            )
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Return the current ROR (Refused-Or-Rerouted) metrics for this session. "
            "ROR rate = (REROUTE + REFUSE) / total dispositions. "
            "This is the primary health metric for the Protocol. "
            "0% ROR = either perfect alignment or no misalignment being detected. "
            "High ROR = posture design gap or genuine alignment problem."
        )
    )
    def get_ror_metrics() -> dict[str, Any]:
        return service.get_ror_metrics()

    # --- Phase 3 tools ---------------------------------------------------

    @app.tool(
        description=(
            "Start a new AI↔AI handshake session as the initiating agent. "
            "Submit your own signed declaration and receive a session_id. "
            "Share the session_id with the counterpart agent so they can call "
            "respond_to_handshake() to complete the exchange. "
            "Pass the declaration JSON from declare_posture."
        )
    )
    def initiate_handshake(self_declaration_json: str) -> dict[str, Any]:
        """
        self_declaration_json : JSON of your own declaration (from declare_posture).
        """
        try:
            return service.initiate_handshake(self_declaration_json)
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Respond to an open handshake session as the counterpart agent. "
            "Submit your own declaration and the Protocol engine immediately computes "
            "the disposition (PROCEED/REROUTE/COMPLETE_AND_FLAG/REFUSE). "
            "Requires the session_id from the initiating agent's initiate_handshake call. "
            "The result updates the session and records the mode in the ROR tracker."
        )
    )
    def respond_to_handshake(
        session_id: str,
        counterpart_declaration_json: str,
        require_signature: bool = True,
    ) -> dict[str, Any]:
        """
        session_id                   : From the initiating agent's initiate_handshake response.
        counterpart_declaration_json : Your own declaration JSON (from declare_posture).
        require_signature            : REFUSE if initiator declaration is unsigned (default True).
        """
        try:
            return service.respond_to_handshake(
                session_id=session_id,
                counterpart_declaration_json=counterpart_declaration_json,
                require_signature=require_signature,
            )
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Retrieve the full result of a completed handshake session by session_id. "
            "Returns session state, both declarations, disposition signal, and alignment report. "
            "Useful for checking the outcome after respond_to_handshake() has been called."
        )
    )
    def get_handshake_result(session_id: str) -> dict[str, Any]:
        """
        session_id : The session_id from initiate_handshake.
        """
        try:
            return service.get_handshake_result(session_id)
        except ServiceError as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "List the most recent handshake sessions in this server session. "
            "Returns sessions newest-first with state, agents, disposition mode, "
            "and alignment score. Sessions are in-memory and reset on server restart."
        )
    )
    def list_sessions(n: int = 20) -> dict[str, Any]:
        """
        n : Maximum number of sessions to return (default 20).
        """
        return service.list_sessions(n)

    # --- Phase 4 tools ---------------------------------------------------

    @app.tool(
        description=(
            "Read recent entries from the persistent JSONL event journal. "
            "The journal captures every Protocol event across server restarts. "
            "Optionally filter by category: DECLARATION, VALIDATION, DISPOSITION, "
            "SIGNING, SERVER. Returns entries newest-first."
        )
    )
    def get_event_journal(
        n: int = 50,
        category: str | None = None,
    ) -> dict[str, Any]:
        """
        n        : Maximum entries to return (default 50).
        category : Optional filter — DECLARATION, VALIDATION, DISPOSITION, SIGNING, SERVER.
        """
        return service.get_event_journal(n=n, category=category)

    @app.tool(
        description=(
            "Generate a structured markdown report for a single handshake session. "
            "Includes disposition mode, alignment score, per-principle gap table, "
            "and recommended action. Suitable for advisory board export. "
            "Pass the session_id from initiate_handshake or list_sessions."
        )
    )
    def export_session_report(session_id: str) -> dict[str, Any]:
        """
        session_id : The UUID of the session to report on.
        """
        try:
            return service.export_session_report(session_id)
        except Exception as exc:
            return {"message": f"Error: {exc}", "data": {"error": str(exc)}}

    @app.tool(
        description=(
            "Generate a markdown ROR trend report across all persisted snapshots. "
            "Shows min/max/mean/latest ROR rates and a table of the 10 most recent "
            "snapshots with per-mode counts. Persists across server restarts. "
            "ROR = (REROUTE + REFUSE) / total dispositions."
        )
    )
    def export_ror_report() -> dict[str, Any]:
        return service.export_ror_report()

    @app.tool(
        description=(
            "Return a server-wide dashboard summary combining session counts, "
            "ROR health metrics, and event journal statistics. "
            "The primary operator health check tool for the 10+1 Protocol server."
        )
    )
    def get_summary() -> dict[str, Any]:
        return service.get_summary()

    return app


def main() -> None:
    log_level = os.environ.get("PROTOCOL_LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

    key_path_env = os.environ.get("PROTOCOL_HMAC_KEY_PATH")
    key_path = Path(key_path_env) if key_path_env else None

    service = ProtocolService(key_path=key_path)
    app = build_app(service)
    app.run(transport="stdio")


if __name__ == "__main__":
    main()
