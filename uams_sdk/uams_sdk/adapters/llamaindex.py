"""
LlamaIndex Adapter for UAMS.
Provides UAMSLlamaIndexRetriever for querying UAMS hybrid knowledge graphs.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from uams_sdk.client import UAMSClient
except ImportError:
    from ..client import UAMSClient


class UAMSNodeWithScore:
    """Lightweight representation of LlamaIndex NodeWithScore (duck-typed)."""

    def __init__(self, text: str, score: float, metadata: Optional[Dict[str, Any]] = None):
        self.text = text
        self.score = score
        self.metadata = metadata or {}

    def get_text(self) -> str:
        return self.text

    def __repr__(self) -> str:
        return f"NodeWithScore(score={self.score:.3f}, text='{self.text[:40]}...')"


class UAMSLlamaIndexRetriever:
    """LlamaIndex-compatible retriever backed by UAMS hybrid search."""

    def __init__(
        self,
        client: Optional[UAMSClient] = None,
        base_url: str = "http://localhost:8000",
        source_agent: str = "LlamaIndexAgent",
        project: Optional[str] = None,
        limit: int = 5,
        compress: bool = False,
    ):
        self.client = client or UAMSClient(base_url=base_url, source_agent=source_agent, project=project)
        self.limit = limit
        self.compress = compress

    async def aretrieve(self, str_or_query_bundle: Any) -> List[UAMSNodeWithScore]:
        """Async retrieve nodes matching query."""
        query_str = (
            str_or_query_bundle.query_str
            if hasattr(str_or_query_bundle, "query_str")
            else str(str_or_query_bundle)
        )
        res = await self.client.search(
            query=query_str,
            limit=self.limit,
            compress=self.compress,
        )
        nodes = []
        for item in res.get("results", []):
            text = item.get("text", "")
            score = float(item.get("score", 0.0))
            meta = {
                "source_file": item.get("source_file"),
                "category": item.get("category"),
                "tags": item.get("tags", []),
                "evidence_revision_id": item.get("evidence_revision_id"),
            }
            nodes.append(UAMSNodeWithScore(text=text, score=score, metadata=meta))
        return nodes

    def retrieve(self, str_or_query_bundle: Any) -> List[UAMSNodeWithScore]:
        """Synchronous retrieval."""
        return asyncio.run(self.aretrieve(str_or_query_bundle))
