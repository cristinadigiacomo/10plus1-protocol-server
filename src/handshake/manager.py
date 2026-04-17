"""
Phase 3 — Handshake session manager.

In-memory store for the current server session. Sessions are lost on restart;
Phase 4 will add JSON file persistence.

The manager is responsible for state transitions only. Disposition logic lives
in dispositioner.engine — the manager calls it and records the result.

Authoritative sources
---------------------
PHASES/PHASE_3.md §HandshakeManager
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone

from dispositioner.engine import compute_disposition
from handshake.session import HandshakeSession, SessionState
from schema.declaration import HandshakeDeclaration
from schema.disposition import DispositionSignal


class SessionNotFoundError(Exception):
    """Raised when a session_id does not exist in the store."""


class SessionStateError(Exception):
    """Raised when an operation is invalid for the session's current state."""


class HandshakeManager:
    """In-memory handshake session manager.

    Parameters
    ----------
    max_sessions : int
        Maximum sessions kept in memory. Oldest sessions are evicted when
        the store is full. Default 500.
    """

    def __init__(self, max_sessions: int = 500) -> None:
        # OrderedDict preserves insertion order; we evict from the front.
        self._store: OrderedDict[str, HandshakeSession] = OrderedDict()
        self._max = max_sessions

    # --- internal --------------------------------------------------------

    def _save(self, session: HandshakeSession) -> None:
        if session.session_id in self._store:
            # Move to end to keep it fresh (LRU-like)
            self._store.move_to_end(session.session_id)
        else:
            if len(self._store) >= self._max:
                self._store.popitem(last=False)  # evict oldest
        self._store[session.session_id] = session

    # --- public API ------------------------------------------------------

    def create(self, initiator_declaration: HandshakeDeclaration) -> HandshakeSession:
        """Create a new INITIATED session.

        Parameters
        ----------
        initiator_declaration : HandshakeDeclaration
            The initiating agent's own declaration.

        Returns
        -------
        HandshakeSession in INITIATED state.
        """
        session = HandshakeSession(
            initiator_id=initiator_declaration.agent_id,
            initiator_declaration=initiator_declaration,
        )
        self._save(session)
        return session

    def respond(
        self,
        session_id: str,
        counterpart_declaration: HandshakeDeclaration,
        require_signature: bool = True,
    ) -> HandshakeSession:
        """Advance a session from INITIATED → RESPONDED by submitting the
        counterpart's declaration. Computes disposition immediately.

        Parameters
        ----------
        session_id : str
            The session_id returned by create().
        counterpart_declaration : HandshakeDeclaration
            The counterpart agent's declaration.
        require_signature : bool
            Passed to compute_disposition(). Default True.

        Returns
        -------
        HandshakeSession in RESPONDED state (or FAILED on hard override).

        Raises
        ------
        SessionNotFoundError
            If session_id does not exist.
        SessionStateError
            If the session is not in INITIATED state (already responded or failed).
        """
        session = self.get(session_id)

        if not session.is_open():
            raise SessionStateError(
                f"Session {session_id[:8]}… is in state {session.state.value}; "
                f"only INITIATED sessions can receive a response."
            )

        now = datetime.now(timezone.utc).isoformat()

        try:
            signal, report = compute_disposition(
                session.initiator_declaration,
                counterpart_declaration,
                require_signature=require_signature,
            )
        except Exception as exc:
            # Any unexpected error from the engine → FAILED
            failed = session.model_copy(update={
                "state": SessionState.FAILED,
                "error": f"Disposition engine error: {exc}",
                "responded_at": now,
                "completed_at": now,
            })
            self._save(failed)
            return failed

        # Serialise AlignmentReport to plain dict
        report_dict = {
            "alignment_score": report.alignment_score,
            "scored_count":    report.scored_count,
            "gaps": [
                {
                    "principle_id":      g.principle_id,
                    "self_status":       g.self_status,
                    "counterpart_status": g.counterpart_status,
                    "score":             g.score,
                    "note":              g.note,
                }
                for g in report.gaps
            ],
            "skipped": report.skipped,
        }

        completed = session.model_copy(update={
            "state":                   SessionState.RESPONDED,
            "counterpart_id":          counterpart_declaration.agent_id,
            "counterpart_declaration": counterpart_declaration,
            "disposition":             signal,
            "alignment_report":        report_dict,
            "responded_at":            now,
            "completed_at":            now,
        })
        self._save(completed)
        return completed

    def close(self, session_id: str) -> HandshakeSession:
        """Explicitly mark a RESPONDED session as COMPLETE."""
        session = self.get(session_id)
        if session.state != SessionState.RESPONDED:
            raise SessionStateError(
                f"Session {session_id[:8]}… must be RESPONDED to close; "
                f"current state: {session.state.value}"
            )
        closed = session.model_copy(update={
            "state": SessionState.COMPLETE,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save(closed)
        return closed

    def get(self, session_id: str) -> HandshakeSession:
        """Retrieve a session by ID.

        Raises
        ------
        SessionNotFoundError
        """
        session = self._store.get(session_id)
        if session is None:
            raise SessionNotFoundError(
                f"Session '{session_id}' not found. "
                f"It may have been evicted or never created."
            )
        return session

    def list_recent(self, n: int = 20) -> list[HandshakeSession]:
        """Return the n most recently active sessions, newest first."""
        sessions = list(self._store.values())
        return list(reversed(sessions))[:n]

    def total(self) -> int:
        return len(self._store)
