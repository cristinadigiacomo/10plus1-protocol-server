"""JSON API endpoints — consumed by Alpine.js for live polling."""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/overview")
async def api_overview(request: Request) -> dict:
    return request.app.state.data_layer.network_overview()


@router.get("/events")
async def api_events(request: Request, n: int = 50) -> list:
    return request.app.state.data_layer.recent_events(n=min(n, 200))


@router.get("/handshakes")
async def api_handshakes(request: Request) -> list:
    return request.app.state.data_layer.list_handshakes()


@router.get("/agents")
async def api_agents(request: Request) -> list:
    return request.app.state.data_layer.list_agents()
