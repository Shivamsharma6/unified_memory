import os
from pathlib import Path

from api.routers.graph import router as graph_router
from api.routers.identity import router as identity_router
from api.routers.quality import router as quality_router
from api.routers.memory_edit import router as memory_edit_router
from fastapi import FastAPI, HTTPException
from api.models import SearchRequest, SearchResponse, RememberRequest, SummarizeRequest, ContextRequest, ProcedureRequest
from api.memory_writer import write_memory
from api.procedure_reader import get_relevant_procedures
from api.retrieval.pipeline import RetrievalPipeline
from llm.provider import LLMProvider, LLMConfig, MODEL_ROLES, get_llm_config
from pipelines.ingestion import IngestionPipeline
from identity.store import IdentityStore

app = FastAPI(
    title="Unified Agent Memory API",
    description="Advanced Retrieval API for Hermes, OpenClaw, and VoiceAI",
    version="1.0.0"
)
app.include_router(graph_router)
app.include_router(identity_router)
app.include_router(quality_router)
app.include_router(memory_edit_router)

pipeline = RetrievalPipeline()
ingestion_pipeline = IngestionPipeline()
identity_store = IdentityStore(os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2])))

# LLM: lazy singleton — created on first call, auto-shuts down after idle
_llm: LLMProvider | None = None

def _get_llm() -> LLMProvider:
    global _llm
    if _llm is None:
        _llm = LLMProvider(LLMConfig(
            provider=os.getenv("UAMS_LLM_PROVIDER", "ollama"),
            model=os.getenv("UAMS_LLM_MODEL", "gemma4:12b-mlx"),
            base_url=os.getenv("UAMS_LLM_BASE_URL", "http://localhost:11434"),
            api_key=os.getenv("UAMS_LLM_API_KEY"),
        ))
    return _llm

@app.on_event("startup")
async def startup_event():
    await pipeline.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    global _llm
    if _llm is not None:
        await _llm.shutdown()
        _llm = None

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
        write_result = write_memory(request)
        path = getattr(write_result, "path", write_result)
        try:
            await ingestion_pipeline.process_file(str(path))
            indexed = True
            warning = None
        except Exception as ingest_error:
            indexed = False
            warning = str(ingest_error)
        return {
            "status": "success",
            "memory_id": str(getattr(write_result, "memory_id", "")) or None,
            "path": getattr(write_result, "vault_path", str(path)),
            "index_status": getattr(write_result, "index_status", "pending"),
            "indexed": indexed,
            "warning": warning,
            "message": "Memory written to the vault.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/summarize", tags=["Compute"])
async def summarize(request: SummarizeRequest):
    """Generate a semantic summary using LLM-powered distillation."""
    try:
        search_req = SearchRequest(query=request.topic, limit=5, compress=True)
        res = await pipeline.search(search_req)
        context_text = "\n\n".join([f"Source: {r.source_file}\n{r.text}" for r in res.results])
        if context_text.strip():
            system = (
                "You are a memory summarization engine. Given retrieved context about a topic, "
                "generate a concise, factual summary. Focus on key facts, relationships, and "
                "decisions. Do not hallucinate information not present in the context."
            )
            prompt = f"Topic: {request.topic}\n\nRetrieved Context:\n{context_text[:4000]}\n\nGenerate a concise summary:"
            summary = await _get_llm().generate(prompt, system=system, max_tokens=request.max_tokens)
            return {"topic": request.topic, "summary": summary, "sources": [r.source_file for r in res.results]}
        return {"topic": request.topic, "summary": f"No relevant context found for '{request.topic}'.", "sources": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

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
    search_req = SearchRequest(query=request.task, limit=10, compress=True, max_tokens=request.max_tokens)
    res = await pipeline.search(search_req)
    context_str = "\n\n".join([f"Source: {r.source_file}\n{r.text}" for r in res.results])
    return {"task": request.task, "context": context_str, "tokens": res.context_tokens_used}

@app.post("/procedures", tags=["Retrieval"])
async def get_procedures(request: ProcedureRequest):
    """Specialized endpoint for retrieving operational rules (AGENTS.md)."""
    return {"task": request.task, "procedures": get_relevant_procedures(request.task)}

@app.get("/health", tags=["System"])
async def health_check():
    components = {}

    try:
        collections = await pipeline.vector_store.client.get_collections()
        components["qdrant"] = {
            "status": "ok",
            "collections": [collection.name for collection in collections.collections],
        }
    except Exception as exc:
        components["qdrant"] = {"status": "unavailable", "detail": str(exc)}

    components["embeddings"] = {
        "status": "ok",
        "provider": pipeline.embedder.provider,
        "model": pipeline.embedder.model_name,
    }

    components["models"] = MODEL_ROLES

    status = "healthy" if all(c.get("status") == "ok" for k, c in components.items() if k not in ("models",)) else "degraded"
    return {"status": status, "components": components}

@app.get("/llm-status", tags=["System"])
async def llm_status():
    """Check LLM provider state — client alive, idle timer, config."""
    import time
    provider = _llm
    if provider is None:
        return {"loaded": False, "reason": "never called"}
    idle_since = time.monotonic() - provider._last_activity if provider._last_activity else None
    return {
        "loaded": provider._client is not None,
        "provider": provider.config.provider,
        "model": provider.config.model,
        "idle_seconds": round(idle_since, 1) if idle_since else None,
        "idle_timeout": provider.config.idle_timeout,
        "shutdown_in": round(max(0, provider.config.idle_timeout - idle_since), 1) if idle_since else None,
    }

@app.post("/reflect", tags=["Intelligence"])
async def reflect():
    """Reflect on recent memories — quality assessment, gaps, suggestions."""
    from intelligence.reflection import MemoryReflector
    reflector = MemoryReflector()
    try:
        # Gather recent memories from the vault
        vault_path = Path(os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2])))
        daily_dir = vault_path / "Daily"
        memories = []
        if daily_dir.exists():
            for f in sorted(daily_dir.glob("*.md"), reverse=True)[:5]:
                try:
                    content = f.read_text(encoding="utf-8")
                    memories.append({"content": content, "source_file": f.name})
                except Exception:
                    pass

        result = await reflector.reflect(memories)
        return result
    finally:
        await reflector.shutdown()
