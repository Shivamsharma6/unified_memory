import os
import pytest
from unittest.mock import AsyncMock, patch

try:
    from uams_sdk.client import UAMSClient
    from uams_sdk.mcp_server import search_memory, remember, begin_task, end_task
except ImportError:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "uams_sdk"))
    from uams_sdk.client import UAMSClient
    from uams_sdk.mcp_server import search_memory, remember, begin_task, end_task


def test_uams_client_environment_defaults():
    with patch.dict(os.environ, {"UAMS_AGENT_NAME": "Hermes", "UAMS_PROJECT": "UnifiedMemory"}):
        client = UAMSClient()
        assert client.source_agent == "Hermes"
        assert client.project == "UnifiedMemory"


@pytest.mark.asyncio
async def test_client_store_memory_propagates_attribution():
    client = UAMSClient(source_agent="OpenClaw", project="Apollo")
    client._request = AsyncMock(return_value={"status": "success", "memory_id": "mem-123", "decision": "ADD", "index_status": "active"})

    res = await client.store_memory(
        text="Sample memory text",
        category="semantic",
        tags=["#apollo"],
        source_agent="CustomAgent",
        project="CustomProject",
    )

    assert res["ok"] is True
    client._request.assert_called_once()
    call_payload = client._request.call_args[0][2]
    assert call_payload["source_agent"] == "CustomAgent"
    assert call_payload["project"] == "CustomProject"
    assert call_payload["category"] == "semantic"


@pytest.mark.asyncio
async def test_client_search_propagates_attribution_filters():
    client = UAMSClient(source_agent="VoiceAI", project="SpeechCore")
    client._request = AsyncMock(return_value={"results": []})

    await client.search(
        query="wake word detection",
        limit=5,
        source_agents=["VoiceAI"],
        projects=["SpeechCore"],
    )

    client._request.assert_called_once()
    call_payload = client._request.call_args[0][2]
    assert call_payload["source_agents"] == ["VoiceAI"]
    assert call_payload["projects"] == ["SpeechCore"]
