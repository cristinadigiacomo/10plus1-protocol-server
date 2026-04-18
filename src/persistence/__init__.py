"""Persistence abstraction for 10+1 Protocol events.

Two backends implement the same ``EventStore`` interface:

* ``EventViewerBackend`` — wraps the existing ``event_viewer.writer``
  module (requires pywin32; Windows-only). Default on Windows.
* ``SQLiteBackend``       — cross-platform SQLite backend. Preserves
  append-only behaviour (UPDATE/DELETE triggers), HMAC fields,
  dual-channel layout (message + data_json), same EventID categories
  (7000–7499). Default on non-Windows or when
  ``PERSISTENCE_BACKEND=sqlite``.

Selection order
---------------
1. ``PERSISTENCE_BACKEND`` env var — ``"event_viewer"`` or ``"sqlite"``.
2. Windows default → ``"event_viewer"``.
3. All other platforms → ``"sqlite"``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from .base import EventStore
from .sqlite_backend import SQLiteBackend

__all__ = [
    "EventStore",
    "SQLiteBackend",
    "get_backend",
    "default_backend_name",
]


def default_backend_name() -> str:
    """Return the backend name that would be selected with no override."""
    explicit = os.environ.get("PERSISTENCE_BACKEND", "").strip().lower()
    if explicit:
        return explicit
    return "event_viewer" if sys.platform == "win32" else "sqlite"


def get_backend(
    *,
    backend: str | None = None,
    sqlite_path: str | Path | None = None,
) -> EventStore:
    """Build and return an ``EventStore`` for the current environment.

    Parameters
    ----------
    backend : str | None
        Force a specific backend: ``"event_viewer"`` or ``"sqlite"``.
        Overrides the ``PERSISTENCE_BACKEND`` env var.
    sqlite_path : str | Path | None
        SQLite file path. Falls back to ``PROTOCOL_SQLITE_PATH`` env var,
        then to ``./protocol_events.db``.
    """
    name = (backend or default_backend_name()).strip().lower()

    if name == "event_viewer":
        from .event_viewer_backend import EventViewerBackend
        return EventViewerBackend()

    if name == "sqlite":
        path = (
            sqlite_path
            or os.environ.get("PROTOCOL_SQLITE_PATH")
            or "protocol_events.db"
        )
        return SQLiteBackend(Path(path))

    raise ValueError(
        f"Unknown PERSISTENCE_BACKEND {name!r}; "
        f"expected 'event_viewer' or 'sqlite'."
    )
