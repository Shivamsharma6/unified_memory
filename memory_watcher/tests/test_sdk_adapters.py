import pytest
from unittest.mock import AsyncMock, MagicMock

try:
    from uams_sdk.adapters.langchain import UAMSLangChainRetriever, UAMSLangChainChatMessageHistory
    from uams_sdk.adapters.llamaindex import UAMSLlamaIndexRetriever
    from uams_sdk.adapters.crewai import UAMSCrewAIMemoryStorage
except ImportError:
    from adapters.langchain import UAMSLangChainRetriever, UAMSLangChainChatMessageHistory
    from adapters.llamaindex import UAMSLlamaIndexRetriever
    from adapters.crewai import UAMSCrewAIMemoryStorage


@pytest.mark.asyncio
async def test_langchain_retriever_formats_documents():
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value={
        "results": [
            {"text": "Memory text 1", "score": 0.95, "source_file": "Concepts/doc1.md", "category": "semantic"},
            {"text": "Memory text 2", "score": 0.88, "source_file": "Concepts/doc2.md", "category": "procedural"},
        ]
    })

    retriever = UAMSLangChainRetriever(client=mock_client, limit=2)
    docs = await retriever.aget_relevant_documents("test query")

    assert len(docs) == 2
    assert docs[0].page_content == "Memory text 1"
    assert docs[0].metadata["score"] == 0.95
    assert docs[1].page_content == "Memory text 2"
    mock_client.search.assert_called_once_with(query="test query", limit=2, compress=False)


@pytest.mark.asyncio
async def test_langchain_chat_message_history():
    mock_client = MagicMock()
    mock_client.store_memory = AsyncMock(return_value={"status": "success"})

    history = UAMSLangChainChatMessageHistory(session_id="session-42", client=mock_client)
    await history.aadd_message("user", "Hello agent", sync=True)

    assert len(history.messages) == 1
    assert history.messages[0]["content"] == "Hello agent"
    mock_client.store_memory.assert_called_once()


@pytest.mark.asyncio
async def test_llamaindex_retriever_formats_nodes():
    mock_client = MagicMock()
    mock_client.search = AsyncMock(return_value={
        "results": [
            {"text": "Llama node text", "score": 0.92, "source_file": "Tasks/deploy.md"},
        ]
    })

    retriever = UAMSLlamaIndexRetriever(client=mock_client, limit=1)
    nodes = await retriever.aretrieve("how to deploy")

    assert len(nodes) == 1
    assert nodes[0].get_text() == "Llama node text"
    assert nodes[0].score == 0.92


@pytest.mark.asyncio
async def test_crewai_memory_storage_save_and_search():
    mock_client = MagicMock()
    mock_client.store_memory = AsyncMock(return_value={"status": "success", "memory_id": "crew-1"})
    mock_client.search = AsyncMock(return_value={"results": [{"text": "Found task outcome"}]})

    storage = UAMSCrewAIMemoryStorage(client=mock_client, source_agent="Researcher")
    save_res = await storage.asave("Final report generated", metadata={"task": "MarketResearch"})

    assert save_res["status"] == "success"
    mock_client.store_memory.assert_called_once()

    search_res = await storage.asearch("MarketResearch", limit=2)
    assert len(search_res) == 1
    assert search_res[0]["text"] == "Found task outcome"
