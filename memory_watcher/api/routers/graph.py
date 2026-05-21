from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from graph.store import KnowledgeGraphStore

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])
kg_store = KnowledgeGraphStore()

# Load existing JSON if available on startup
try:
    import json
    import networkx as nx
    with open("knowledge_graph.json", "r") as f:
        kg_store.G = nx.node_link_graph(json.load(f))
except Exception:
    pass

@router.get("/neighborhood/{entity}")
async def get_neighborhood(entity: str, radius: int = 1):
    """Generate semantic neighborhoods (n-hop traversal)."""
    res = kg_store.get_semantic_neighborhood(entity, radius)
    if "error" in res:
        raise HTTPException(status_code=404, detail=res["error"])
    return res

@router.get("/export")
async def export_graph():
    """Trigger graph JSON export."""
    kg_store.export_json()
    return {"status": "success", "file": "knowledge_graph.json"}
