"""HTML page routes for the 10+1 Protocol dashboard."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter()


def _ctx(request: Request, active_page: str) -> dict:
    dl = request.app.state.data_layer
    ov = dl.network_overview()
    return {
        "active_page": active_page,
        "ror_status":  ov["ror_status"],
        "ror_pct":     ov["ror_pct"],
    }


def _tmpl(request: Request):
    return request.app.state.templates


@router.get("/", response_class=HTMLResponse)
async def overview(request: Request):
    dl  = request.app.state.data_layer
    ctx = _ctx(request, "overview")
    ctx["overview"] = dl.network_overview()
    ctx["recent"]   = dl.recent_events(n=8)
    return _tmpl(request).TemplateResponse(request, "index.html", ctx)


@router.get("/activity", response_class=HTMLResponse)
async def activity(request: Request):
    dl  = request.app.state.data_layer
    ctx = _ctx(request, "activity")
    ctx["events"] = dl.recent_events(n=50)
    return _tmpl(request).TemplateResponse(request, "activity.html", ctx)


@router.get("/handshakes", response_class=HTMLResponse)
async def handshakes(request: Request):
    dl  = request.app.state.data_layer
    ctx = _ctx(request, "handshakes")
    ctx["handshakes"] = dl.list_handshakes()
    return _tmpl(request).TemplateResponse(request, "handshakes.html", ctx)


@router.get("/handshakes/{session_id}", response_class=HTMLResponse)
async def handshake_detail(request: Request, session_id: str):
    dl      = request.app.state.data_layer
    ctx     = _ctx(request, "handshakes")
    session = dl.get_handshake(session_id)
    if session is None:
        from fastapi.responses import Response
        return Response(status_code=404, content="Session not found")
    ctx["session"] = session
    return _tmpl(request).TemplateResponse(request, "handshake_detail.html", ctx)


@router.get("/agents", response_class=HTMLResponse)
async def agents(request: Request):
    dl  = request.app.state.data_layer
    ctx = _ctx(request, "agents")
    ctx["agents"]  = dl.list_agents()
    ctx["heatmap"] = dl.principle_heatmap()
    return _tmpl(request).TemplateResponse(request, "agents.html", ctx)
