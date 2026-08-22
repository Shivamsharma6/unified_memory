import os
from pathlib import Path

from api.routers.graph import router as graph_router
from api.routers.identity import router as identity_router
from api.routers.quality import router as quality_router
from api.routers.memory_edit import router as memory_edit_router
from api.routers.profiles import router as profiles_router
from api.routers.validation import router as validation_router
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from api.models import SearchRequest, SearchResponse, RememberRequest, SummarizeRequest, ContextRequest, ProcedureRequest
from api.memory_writer import write_memory
from api.procedure_reader import get_relevant_procedures
from api.retrieval.pipeline import RetrievalPipeline
from llm.provider import LLMProvider, LLMConfig, MODEL_ROLES, get_llm_config
from pipelines.ingestion import IngestionPipeline
from identity.store import IdentityStore
from api.readiness import assess_readiness, assess_lightweight_readiness, assess_deep_projection_drift

app = FastAPI(
    title="Unified Agent Memory API",
    description="Advanced Retrieval API for Hermes, OpenClaw, and VoiceAI",
    version="1.1.2"
)
app.include_router(graph_router)
app.include_router(identity_router)
app.include_router(quality_router)
app.include_router(memory_edit_router)
app.include_router(profiles_router)
app.include_router(validation_router)

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
    app.state.control_store = pipeline.control_store if pipeline.hybrid is not None else None

@app.on_event("shutdown")
async def shutdown_event():
    global _llm
    if _llm is not None:
        await _llm.shutdown()
        _llm = None
    await pipeline.shutdown()

@app.post("/search", response_model=SearchResponse, tags=["Retrieval"])
async def search_memory(request: SearchRequest):
    """Execute the 8-step advanced semantic search pipeline."""
    try:
        return await pipeline.search(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

WRITE_DISTILLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string", "description": "Concise, descriptive title"},
        "summary": {"type": "string", "description": "Distilled atomic summary"},
        "category": {"type": "string", "enum": ["semantic", "episodic", "procedural", "identity", "goal", "reflection", "relationship"]},
        "entities": {"type": "array", "items": {"type": "string"}, "description": "Key entities extracted"},
        "tags": {"type": "array", "items": {"type": "string"}, "description": "Key tags"},
        "facts": {"type": "array", "items": {"type": "string"}, "description": "Atomic facts or lessons"},
        "action": {"type": "string", "enum": ["ADD", "UPDATE", "NOOP"]},
    },
    "required": ["title", "summary", "category", "entities", "tags"],
}

WRITE_DISTILLATION_SYSTEM = (
    "You are the UAMS Write-Path Memory Distiller. Distill raw user/agent interactions into structured, atomic knowledge "
    "following AGENTS.md conventions. Extract key entities, assign the canonical memory category, format facts, and decide action."
)


@app.post("/remember", tags=["Ingestion"])
async def remember(request: RememberRequest):
    """Directly ingest a memory bypassing the file watcher (for agent direct writes)."""
    try:
        vault_path = Path(os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2])))
        final_req = request
        if request.distill:
            try:
                llm = _get_llm()
                prompt = f"Distill this memory into structured knowledge:\n\n{request.text}"
                distilled = await llm.generate_structured(
                    prompt, schema=WRITE_DISTILLATION_SCHEMA, system=WRITE_DISTILLATION_SYSTEM
                )
                if isinstance(distilled, dict) and distilled.get("summary"):
                    title = distilled.get("title") or "Memory"
                    summary = distilled.get("summary")
                    cat = distilled.get("category") or request.category
                    entities = distilled.get("entities", [])
                    tags = distilled.get("tags", [])
                    facts = distilled.get("facts", [])

                    entities_wikilinks = [f"[[{e.strip('[]')}]]" for e in entities if e]
                    tags_formatted = [f"#{t.lstrip('#')}" for t in tags if t]
                    facts_lines = "\n".join(f"- {f}" for f in facts) if facts else ""

                    structured_body = f"# {title}\n\n## Summary\n{summary}\n"
                    if facts_lines:
                        structured_body += f"\n## Key Facts & Lessons\n{facts_lines}\n"
                    if entities_wikilinks:
                        structured_body += f"\n## Related Entities\n" + "\n".join(f"- {e}" for e in entities_wikilinks) + "\n"

                    final_req = RememberRequest(
                        text=structured_body,
                        category=cat,
                        tags=list(set(request.tags + tags_formatted)),
                        source_agent=request.source_agent,
                        project=request.project,
                        entities=entities,
                    )
            except Exception as e:
                logger.warning(f"Write-path distillation fallback to raw text: {e}")

        write_result = write_memory(final_req, vault_root=vault_path)
        path = getattr(write_result, "path", write_result)
        try:
            if pipeline.reconciler is not None:
                reconcile_result = await pipeline.reconciler.reconcile_path(path)
                indexed = reconcile_result.status in {"staged", "unchanged"}
                warning = reconcile_result.error
            else:
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
    """Retrieve entities evidenced by current active memories."""
    store = getattr(app.state, "control_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PostgreSQL control plane is unavailable")
    return {"entities": await store.list_entities()}

@app.post("/relations", tags=["Graph"])
async def get_relations(entity: str):
    """Fetch current, evidenced one-hop relations for an entity."""
    store = getattr(app.state, "control_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="PostgreSQL control plane is unavailable")
    graph = await store.graph_neighborhood(entity, radius=1)
    if graph is None:
        raise HTTPException(status_code=404, detail=f"Entity not found: {entity}")
    relations = []
    for link in graph["links"]:
        outgoing = link["source"].casefold() == entity.casefold()
        relation = {
            "type": link["predicate"].upper() if outgoing else f"INVERSE_{link['predicate'].upper()}",
            "target": link["target"] if outgoing else link["source"],
            **{
                key: value
                for key, value in link.items()
                if key not in {"source", "target", "relation", "predicate"}
            },
        }
        relations.append(relation)
    return {"entity": entity, "relations": relations}

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


@app.get("/live", tags=["System"])
async def liveness_check():
    """Ultra-lightweight liveness probe checking process responsiveness (<1ms)."""
    return {"status": "alive"}


@app.get("/ready", tags=["System"])
async def readiness_check():
    """Fast readiness probe validating DB connection pool and queue backlog (<10ms)."""
    if pipeline.hybrid is None:
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "components": {
                    "postgresql": {
                        "status": "unavailable",
                        "detail": "control plane is not initialized",
                    }
                },
                "jobs": {},
            },
        )
    report = await assess_lightweight_readiness(
        pipeline.control_store,
        pipeline.vector_store,
    )
    return JSONResponse(status_code=200 if report["ready"] else 503, content=report)


@app.get("/projection-status", tags=["System"])
async def projection_status_check():
    """Deep diagnostic assessment verifying derived state consistency, drift, and orphaned vectors."""
    if pipeline.hybrid is None:
        return JSONResponse(
            status_code=503,
            content={"ready": False, "detail": "control plane is not initialized"},
        )
    vault_root = Path(
        os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2]))
    )
    report = await assess_deep_projection_drift(
        vault_root,
        pipeline.control_store,
        pipeline.vector_store,
        pipeline.embedder,
        pipeline.reranker,
    )
    return JSONResponse(status_code=200 if report["ready"] else 503, content=report)


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

        result = await reflector.reflect_and_persist(memories, vault_path=str(vault_path))
        if pipeline.reconciler is not None:
            try:
                await pipeline.reconciler.scan()
            except Exception as e:
                logger.warning(f"Reconciliation after reflection had warning: {e}")
        return result
    finally:
        await reflector.shutdown()



@app.post("/consolidate", tags=["Intelligence"])
async def consolidate_memories():
    """Consolidate episodic experiences into abstract concepts and reduce redundancy."""
    from memory_types.consolidation import MemoryConsolidator
    vault_path = Path(os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2])))
    consolidator = MemoryConsolidator(vault_path=str(vault_path))
    result = consolidator.consolidate_vault()
    if pipeline.reconciler is not None:
        try:
            await pipeline.reconciler.scan()
        except Exception as e:
            logger.warning(f"Reconciliation after consolidation had warning: {e}")
    return {
        "status": "success",
        "processed": result.memories_processed,
        "retained": result.memories_retained,
        "pruned": result.memories_pruned,
        "clusters": result.clusters_created,
        "abstractions": result.abstractions_generated,
        "redundancy_reduced": result.redundancy_reduced,
        "summary": result.summary,
    }

