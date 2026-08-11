"""Exact current-profile endpoints backed by PostgreSQL."""

from fastapi import APIRouter, HTTPException, Request


router = APIRouter(prefix="/profiles", tags=["Profiles"])


@router.get("/{profile_id}")
async def get_profile(
    profile_id: str,
    request: Request,
    include_historical: bool = False,
):
    store = getattr(request.app.state, "control_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PostgreSQL control plane is unavailable")
    profile = await store.get_profile(
        profile_id,
        include_historical=include_historical,
    )
    if profile is None:
        raise HTTPException(status_code=404, detail=f"Profile not found: {profile_id}")
    return profile
