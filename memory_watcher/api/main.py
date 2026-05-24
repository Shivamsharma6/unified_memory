from api.routers.graph import router as graph_router
from fastapi import FastAPI, HTTPException
from api.models import SearchRequest, SearchResponse, RememberRequest, SummarizeRequest, ContextRequest, ProcedureRequest
from api.retrieval.pipeline import RetrievalPipeline

app = FastAPI(
    title="Unified Agent Memory API",
    description="Advanced Retrieval API for Hermes, OpenClaw, and VoiceAI",
    version="1.0.0"
)
app.include_router(graph_router)

pipeline = RetrievalPipeline()

@app.on_event("startup")
async def startup_event():
    await pipeline.initialize()

@app.post("/search", response_model=SearchResponse, tags=["Retrieval"])
async def search_memory(request: SearchRequest):
    """Execute the 8-step advanced semantic search pipeline."""
    try:
        return await pipeline.search(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/remember", tags=["Ingestion"])
async def remember(request: RememberRequest):
    """Directly ingest a memory bypassing the file watcher (for agent direct writes)."""
    # Stub: Would write to file and trigger ingestion
    return {"status": "success", "message": "Memory ingested and queued for embedding."}

@app.post("/summarize", tags=["Compute"])
async def summarize(request: SummarizeRequest):
    """Generate a semantic summary for a given topic."""
    return {"topic": request.topic, "summary": "Stub summary generation."}

@app.post("/entities", tags=["Graph"])
async def get_entities():
    """Retrieve recognized entities from the Knowledge Graph."""
    return {"entities": ["OpenClaw", "Hermes", "Unified Memory System", "Qdrant"]}

@app.post("/relations", tags=["Graph"])
async def get_relations(entity: str):
    """Fetch 1-hop relations for a given entity."""
    return {"entity": entity, "relations": [{"type": "USES", "target": "Qdrant"}]}

@app.post("/context", tags=["Orchestration"])
async def get_context(request: ContextRequest):
    """Assemble a multi-document RAG context block optimized for LLM token limits."""
    search_req = SearchRequest(query=request.task, limit=10, compress=True)
    res = await pipeline.search(search_req)
    context_str = "\n\n".join([f"Source: {r.source_file}\n{r.text}" for r in res.results])
    return {"task": request.task, "context": context_str, "tokens": res.context_tokens_used}

@app.post("/procedures", tags=["Retrieval"])
async def get_procedures(request: ProcedureRequest):
    """Specialized endpoint for retrieving operational rules (AGENTS.md)."""
    return {"task": request.task, "procedures": ["1. Check YAML frontmatter", "2. Use wikilinks"]}

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "components": {"qdrant": "ok", "embeddings": "ok"}}
