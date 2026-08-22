"""
CrewAI Adapter for UAMS.
Provides UAMSCrewAIMemoryStorage for multi-agent teams.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from uams_sdk.client import UAMSClient
except ImportError:
    from ..client import UAMSClient


class UAMSCrewAIMemoryStorage:
    """CrewAI-compatible memory storage backend connected to UAMS."""

    def __init__(
        self,
        client: Optional[UAMSClient] = None,
        base_url: str = "http://localhost:8000",
        source_agent: str = "CrewAIAgent",
        project: str = "CrewAIProject",
    ):
        self.client = client or UAMSClient(base_url=base_url, source_agent=source_agent, project=project)
        self.source_agent = source_agent
        self.project = project

    async def asave(self, value: Any, metadata: Optional[Dict[str, Any]] = None, sync: bool = False) -> Dict[str, Any]:
        """Save a task outcome or agent output to UAMS shared brain."""
        meta = metadata or {}
        agent_name = meta.get("agent_name", self.source_agent)
        task_name = meta.get("task", "CrewAITask")

        content = f"# CrewAI Memory: {task_name}\n\n**Agent**: {agent_name}\n\n## Content\n{value}\n"
        return await self.client.store_memory(
            text=content,
            category="episodic",
            source_agent=agent_name,
            project=self.project,
            tags=["crewai", agent_name.lower().replace(" ", "_")],
            sync=sync,
        )

    def save(self, value: Any, metadata: Optional[Dict[str, Any]] = None):
        """Synchronous wrapper for save."""
        return asyncio.run(self.asave(value, metadata))

    async def asearch(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search UAMS memory for past context."""
        res = await self.client.search(query=query, limit=limit)
        return res.get("results", [])

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Synchronous wrapper for search."""
        return asyncio.run(self.asearch(query, limit))
