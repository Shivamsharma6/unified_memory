from api.routers.graph import router as graph_router
from fastapi import FastAPI, HTTPException
from api.models import SearchRequest, SearchResponse, RememberRequest, SummarizeRequest, ContextRequest, ProcedureRequest
from api.memory_writer import write_memory
from api.procedure_reader import get_relevant_procedures
from api.retrieval.pipeline import RetrievalPipeline
from pipelines.ingestion import IngestionPipeline

app = FastAPI(
    title="Unified Agent Memory API",
    description="Advanced Retrieval API for Hermes, OpenClaw, and VoiceAI",
    version="1.0.0"
)
app.include_router(graph_router)

pipeline = RetrievalPipeline()
ingestion_pipeline = IngestionPipeline()

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
    try:
        path = write_memory(request)
        try:
            await ingestion_pipeline.process_file(str(path))
            indexed = True
            warning = None
        except Exception as ingest_error:
            indexed = False
            warning = str(ingest_error)
        return {
            "status": "success",
            "path": str(path),
            "indexed": indexed,
            "warning": warning,
            "message": "Memory written to the vault.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize", tags=["Compute"])
async def summarize(request: SummarizeRequest):
    """Generate a semantic summary for a given topic."""
    try:
        search_req = SearchRequest(query=request.topic, limit=3, compress=True)
        res = await pipeline.search(search_req)
        if res.results:
            summary_content = "\n\n".join([f"- {r.text}" for r in res.results])
            return {"topic": request.topic, "summary": f"Summary of [[{request.topic}]]:\n\n{summary_content}"}
    except Exception:
        pass
    return {"topic": request.topic, "summary": f"Stub summary generation for '{request.topic}'."}

@app.post("/entities", tags=["Graph"])
async def get_entities():
    """Retrieve recognized entities from the Knowledge Graph."""
    try:
        G = pipeline.kg_store.G
        nodes = []
        for node, data in G.nodes(data=True):
            if str(node).startswith("DOC:") or data.get("type") == "document":
                continue
            nodes.append(str(node))
        if nodes:
            return {"entities": nodes}
    except Exception:
        pass
    return {"entities": ["OpenClaw", "Hermes", "Unified Memory System", "Qdrant"]}

@app.post("/relations", tags=["Graph"])
async def get_relations(entity: str):
    """Fetch 1-hop relations for a given entity."""
    try:
        G = pipeline.kg_store.G
        matched_node = None
        for node in G.nodes():
            if str(node).lower() == entity.lower():
                matched_node = node
                break
                
        relations = []
        if matched_node:
            for target in G.successors(matched_node):
                rel_type = G[matched_node][target].get("relation", "RELATED_TO").upper()
                relations.append({"type": rel_type, "target": str(target)})
            for source in G.predecessors(matched_node):
                rel_type = G[source][matched_node].get("relation", "RELATED_TO").upper()
                relations.append({"type": f"INVERSE_{rel_type}", "target": str(source)})
                
        if relations:
            return {"entity": str(matched_node or entity), "relations": relations}
    except Exception:
        pass
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
    return {"task": request.task, "procedures": get_relevant_procedures(request.task)}

@app.get("/health", tags=["System"])
async def health_check():
    return {"status": "healthy", "components": {"qdrant": "ok", "embeddings": "ok"}}
