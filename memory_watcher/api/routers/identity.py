from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/identity", tags=["Identity"])


class ProfileRequest(BaseModel):
    entity_id: str

class ExtractRequest(BaseModel):
    entity_id: str
    entity_name: str = "Unknown"
    memories: List[Dict[str, Any]] = Field(default_factory=list)

class InjectRequest(BaseModel):
    entity_id: str
    query: str = ""
    task_type: str = "general"

class StabilityRequest(BaseModel):
    entity_id: str

class ContradictionRequest(BaseModel):
    entity_id: str


def _get_store():
    from api.main import identity_store
    return identity_store


@router.post("/profile")
async def get_profile(request: ProfileRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    return profile.to_payload()

@router.post("/extract")
async def extract_identity(request: ExtractRequest):
    store = _get_store()
    if not request.memories:
        return {"message": "No memories provided", "entity_id": request.entity_id}
    return store.extract_from_memories(request.entity_id, request.entity_name, request.memories)

@router.post("/inject")
async def inject_identity(request: InjectRequest):
    store = _get_store()
    return store.inject_identity(request.entity_id, request.query, request.task_type)

@router.post("/inject-text")
async def inject_identity_text(request: InjectRequest):
    store = _get_store()
    text = store.inject_as_text(request.entity_id, request.query, request.task_type)
    return {"entity_id": request.entity_id, "injection_text": text}

@router.post("/stability")
async def update_stability(request: StabilityRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    profile = store.stability.apply_stability(profile)
    store.save_profile(profile)
    return {"entity_id": request.entity_id, "global_confidence": profile.global_confidence}

@router.post("/contradictions")
async def contradiction_report(request: ContradictionRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    return store.contradiction.get_contradiction_report(profile)

@router.post("/entities")
async def list_entities():
    store = _get_store()
    return {"entities": store.list_entities()}