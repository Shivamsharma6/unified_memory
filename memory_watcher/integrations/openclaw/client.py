import httpx
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class UAMSClient:
    """Async client for the Unified Agent Memory System API."""
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.timeout = httpx.Timeout(10.0, connect=5.0)

    async def _post(self, endpoint: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(f"{self.base_url}{endpoint}", json=json_data or {})
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error {e.response.status_code} for {endpoint}: {e.response.text}")
                return {"error": str(e), "details": e.response.text}
            except Exception as e:
                logger.error(f"Connection error to UAMS {endpoint}: {e}")
                return {"error": str(e)}

    async def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        return await self._post("/search", {"query": query, "limit": limit, "compress": True})

    async def get_context(self, task: str, max_tokens: int = 2000) -> Dict[str, Any]:
        return await self._post("/context", {"task": task, "max_tokens": max_tokens})

    async def remember(self, text: str, category: str = "episodic", tags: List[str] = None) -> Dict[str, Any]:
        return await self._post("/remember", {"text": text, "category": category, "tags": tags or []})

    async def summarize(self, topic: str) -> Dict[str, Any]:
        return await self._post("/summarize", {"topic": topic})

    async def get_procedures(self, task: str) -> Dict[str, Any]:
        return await self._post("/procedures", {"task": task})
                
    async def get_entities(self) -> Dict[str, Any]:
        return await self._post("/entities")

    async def get_relations(self, entity: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                res = await client.post(f"{self.base_url}/relations?entity={entity}")
                res.raise_for_status()
                return res.json()
            except Exception as e:
                return {"error": str(e)}
