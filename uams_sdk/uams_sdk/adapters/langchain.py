"""
LangChain Adapter for UAMS.
Provides UAMSLangChainRetriever and UAMSLangChainChatMessageHistory.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

try:
    from uams_sdk.client import UAMSClient
except ImportError:
    from ..client import UAMSClient


class UAMSLangChainDocument:
    """Lightweight representation of LangChain Document (duck-typed to avoid strict dependency)."""

    def __init__(self, page_content: str, metadata: Optional[Dict[str, Any]] = None):
        self.page_content = page_content
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return f"Document(page_content='{self.page_content[:40]}...', metadata={self.metadata})"


class UAMSLangChainRetriever:
    """LangChain-compatible retriever powered by UAMS Hybrid Retrieval."""

    def __init__(
        self,
        client: Optional[UAMSClient] = None,
        base_url: str = "http://localhost:8000",
        source_agent: str = "LangChainAgent",
        project: Optional[str] = None,
        limit: int = 5,
        compress: bool = False,
    ):
        self.client = client or UAMSClient(base_url=base_url, source_agent=source_agent, project=project)
        self.limit = limit
        self.compress = compress

    async def aget_relevant_documents(self, query: str) -> List[UAMSLangChainDocument]:
        """Async retrieval of documents matching query."""
        res = await self.client.search(
            query=query,
            limit=self.limit,
            compress=self.compress,
        )
        docs = []
        for item in res.get("results", []):
            text = item.get("text", "")
            meta = {
                "source_file": item.get("source_file"),
                "score": item.get("score"),
                "category": item.get("category"),
                "tags": item.get("tags", []),
                "evidence_revision_id": item.get("evidence_revision_id"),
            }
            docs.append(UAMSLangChainDocument(page_content=text, metadata=meta))
        return docs

    def get_relevant_documents(self, query: str) -> List[UAMSLangChainDocument]:
        """Synchronous wrapper for get_relevant_documents."""
        return asyncio.run(self.aget_relevant_documents(query))


class UAMSLangChainChatMessageHistory:
    """LangChain BaseChatMessageHistory adapter writing into UAMS."""

    def __init__(
        self,
        session_id: str,
        client: Optional[UAMSClient] = None,
        base_url: str = "http://localhost:8000",
        source_agent: str = "LangChainAgent",
        project: Optional[str] = None,
    ):
        self.session_id = session_id
        self.client = client or UAMSClient(base_url=base_url, source_agent=source_agent, project=project)
        self.messages: List[Dict[str, str]] = []

    async def aadd_message(self, role: str, content: str, sync: bool = False):
        """Add a message and store distilled episodic memory."""
        self.messages.append({"role": role, "content": content})
        text = f"# Session {self.session_id}\n\n**{role.title()}**: {content}\n"
        await self.client.store_memory(
            text=text,
            category="episodic",
            tags=["chat_history", f"session_{self.session_id}"],
            sync=sync,
        )

    def add_message(self, role: str, content: str):
        asyncio.run(self.aadd_message(role, content))

    def clear(self):
        self.messages.clear()
