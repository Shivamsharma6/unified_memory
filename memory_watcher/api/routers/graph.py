"""Evidence-bearing knowledge graph endpoints."""

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


def _control_store(request: Request):
    store = getattr(request.app.state, "control_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PostgreSQL control plane is unavailable")
    return store


@router.get("/neighborhood/{entity}")
async def get_neighborhood(
    entity: str,
    request: Request,
    radius: int = 1,
    include_candidates: bool = False,
    include_historical: bool = False,
):
    result = await _control_store(request).graph_neighborhood(
        entity,
        radius=max(0, min(radius, 5)),
        include_candidates=include_candidates,
        include_historical=include_historical,
    )
    if result is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity}")
    return result


@router.get("/export")
async def export_graph(
    request: Request,
    include_candidates: bool = False,
    include_historical: bool = False,
):
    return await _control_store(request).export_claim_graph(
        include_candidates=include_candidates,
        include_historical=include_historical,
    )
