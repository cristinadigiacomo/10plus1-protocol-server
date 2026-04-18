"""FastAPI dashboard application factory for 10+1 Protocol."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.templating import Jinja2Templates

from .data import DataLayer
from .routes import api, pages

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def create_app(data_layer: DataLayer | None = None) -> FastAPI:
    """Build and return the dashboard FastAPI app.

    Parameters
    ----------
    data_layer
        Pre-configured DataLayer instance. When None (default), one is built
        from env vars PROTOCOL_JOURNAL_PATH, PROTOCOL_ROR_PATH, and
        PROTOCOL_DATA_DIR.
    """
    if data_layer is None:
        data_dir = Path(os.environ.get("PROTOCOL_DATA_DIR", "."))
        journal  = Path(os.environ.get("PROTOCOL_JOURNAL_PATH",  str(data_dir / ".protocol_journal.jsonl")))
        ror      = Path(os.environ.get("PROTOCOL_ROR_PATH",      str(data_dir / ".protocol_ror.json")))
        data_layer = DataLayer(journal_path=journal, ror_path=ror)

    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))

    app = FastAPI(title="10+1 Protocol Dashboard", docs_url=None, redoc_url=None)

    app.state.data_layer = data_layer
    app.state.templates  = templates

    app.include_router(pages.router)
    app.include_router(api.router, prefix="/api")

    return app
