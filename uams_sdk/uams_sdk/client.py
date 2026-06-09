import httpx
import logging
import json
from datetime import date
from typing import Dict, Any, List, Optional
from .cache import SDKCache
from .exceptions import UAMSError, UAMSConnectionError, UAMSAPIError

logger = logging.getLogger(__name__)

class UAMSClient:
    """
    Unified Agent Memory System (UAMS) SDK Client.
    Shared across Hermes, OpenClaw, and VoiceAI.
    """
    def __init__(self, base_url: str = "http://localhost:8000", cache_ttl: int = 300):
        self.base_url = base_url
        self.timeout = httpx.Timeout(15.0, connect=5.0)
        self.cache = SDKCache(ttl=cache_ttl)

    async def _request(self, method: str, endpoint: str, json_data: Dict[str, Any] = None, use_cache: bool = False) -> Dict[str, Any]:
        if use_cache and method == "POST":
            cached = self.cache.get(endpoint, json_data or {})
            if cached:
                logger.debug(f"Cache hit for {endpoint}")
                return cached

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                if method == "POST":
                    response = await client.post(f"{self.base_url}{endpoint}", json=json_data or {})
                elif method == "GET":
                    response = await client.get(f"{self.base_url}{endpoint}", params=json_data)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                    
                response.raise_for_status()
                data = response.json()
                
                if use_cache and method == "POST":
                    self.cache.set(endpoint, json_data or {}, data)
                    
                return data
                
            except httpx.HTTPStatusError as e:
                raise UAMSAPIError(f"API Error: {e.response.status_code}", status_code=e.response.status_code, details=e.response.text)
            except httpx.RequestError as e:
                raise UAMSConnectionError(f"Connection error to UAMS {endpoint}: {str(e)}")

    async def search(self, query: str, limit: int = 5, entities: List[str] = None, compress: bool = True) -> Dict[str, Any]:
        """Semantic + Graph hybrid retrieval."""
        payload = {
            "query": query,
            "limit": limit,
            "entities": entities or [],
            "compress": compress
        }
        return await self._request("POST", "/search", payload, use_cache=True)

    async def retrieve_context(self, task: str, max_tokens: int = 2000) -> str:
        """Highly compressed context assembly for LLM prompting."""
        res = await self._request("POST", "/context", {"task": task, "max_tokens": max_tokens}, use_cache=True)
        return res.get("context", "")

    async def retrieve_procedures(self, task: str) -> List[str]:
        """Fetch procedural memories (AGENTS.md / SOPs)."""
        res = await self._request("POST", f"/procedures", {"task": task}, use_cache=True)
        return res.get("procedures", [])

    async def begin_task(self, task: str, max_tokens: int = 2000) -> Dict[str, Any]:
        """Default memory preflight agents should call before doing work."""
        procedures = await self.retrieve_procedures(task)
        context = await self.retrieve_context(task, max_tokens=max_tokens)
        return {
            "task": task,
            "status": "ready",
            "procedures": procedures,
            "context": context,
            "max_tokens": max_tokens,
            "memory_policy": (
                "Always call begin_task before non-trivial work. Use the procedures and "
                "context as grounding. Call search_memory when recall is needed during "
                "the task. Call end_task after durable work to store distilled outcomes."
            ),
        }

    async def store_memory(self, text: str, category: str = "episodic", tags: List[str] = None) -> bool:
        """Agent memory write support. Clears cache to ensure fresh reads."""
        payload = {"text": text, "category": category, "tags": tags or []}
        try:
            await self._request("POST", "/remember", payload, use_cache=False)
            self.cache.clear() # Invalidate cache on write
            return True
        except UAMSError as e:
            logger.error(f"Failed to store memory: {e}")
            return False

    async def end_task(
        self,
        task: str,
        outcome: str,
        files: Optional[List[str]] = None,
        decisions: Optional[List[str]] = None,
        fixes: Optional[List[str]] = None,
        entities: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        category: str = "episodic",
    ) -> Dict[str, Any]:
        """Store a distilled task outcome after durable work completes."""
        all_tags = list(dict.fromkeys((tags or []) + ["#auto-distilled", "#task-outcome"]))
        entity_links = " ".join(f"[[{entity}]]" for entity in entities or [])
        file_lines = "\n".join(f"- `{path}`" for path in files or []) or "- Not specified"
        decision_lines = "\n".join(f"- {item}" for item in decisions or []) or "- None recorded"
        fix_lines = "\n".join(f"- {item}" for item in fixes or []) or "- None recorded"
        today = date.today().isoformat()

        tags_json = json.dumps(all_tags)
        text = f"""---
type: {category}
date: {today}
tags: {tags_json}
---
# Task Outcome: {task}

## TL;DR
{outcome.strip()}

## Entities
{entity_links or f"[[{task}]]"}

## Files
{file_lines}

## Decisions
{decision_lines}

## Fixes
{fix_lines}

## Retrieval Notes
Future agents should search for [[{task}]], the listed entities, and the listed files before repeating related work.
"""
        ok = await self.store_memory(text=text, category=category, tags=all_tags)
        return {"ok": ok, "category": category, "tags": all_tags}

    async def distill_memory(self, topic: str) -> str:
        """Trigger summarization/distillation of a topic."""
        res = await self._request("POST", "/summarize", {"topic": topic}, use_cache=False)
        return res.get("summary", "")

    async def related_entities(self, entity: str, radius: int = 1) -> Dict[str, Any]:
        """Graph retrieval: neighborhood expansion."""
        try:
            return await self._request("GET", f"/graph/neighborhood/{entity}", {"radius": radius}, use_cache=True)
        except UAMSAPIError as e:
            if getattr(e, 'status_code', None) == 404:
                return {"error": f"Entity '{entity}' not found in knowledge graph.", "nodes": [], "links": []}
            raise
