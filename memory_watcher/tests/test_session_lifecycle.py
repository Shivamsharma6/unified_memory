import pytest
from unittest.mock import AsyncMock

try:
    from api.models import SessionBeginRequest, SessionEndRequest
    from uams_sdk.client import UAMSClient
except ImportError:
    from memory_watcher.api.models import SessionBeginRequest, SessionEndRequest
    from uams_sdk.client import UAMSClient


def test_session_models_instantiation():
    begin_req = SessionBeginRequest(
        task="Refactor vector indexing",
        source_agent="Hermes",
        project="UnifiedMemory",
    )
    assert begin_req.task == "Refactor vector indexing"
    assert begin_req.source_agent == "Hermes"

    end_req = SessionEndRequest(
        session_id="sess-123",
        task="Refactor vector indexing",
        outcome="Completed refactor with zero downtime.",
        source_agent="Hermes",
        project="UnifiedMemory",
        files=["api/retrieval/hybrid.py"],
        decisions=["Use asyncio.to_thread for cross-encoder"],
    )
    assert end_req.session_id == "sess-123"
    assert end_req.decisions[0] == "Use asyncio.to_thread for cross-encoder"


@pytest.mark.asyncio
async def test_sdk_begin_and_end_task_session_flow():
    client = UAMSClient(source_agent="OpenClaw", project="DevBot")
    client._request = AsyncMock()

    # Mock responses
    client._request.side_effect = [
        {"procedures": ["SOP: Follow AGENTS.md"]},
        {"context": "Grounding context from vault"},
        {"status": "success", "memory_id": "mem-456", "decision": "ADD", "index_status": "active"},
    ]

    begin_res = await client.begin_task("Implement optimistic concurrency")
    session_id = begin_res["session_id"]
    assert session_id is not None
    assert begin_res["status"] == "ready"
    assert begin_res["source_agent"] == "OpenClaw"

    end_res = await client.end_task(
        task="Implement optimistic concurrency",
        outcome="Added expected_revision_id check to /memory/edit",
        session_id=session_id,
        files=["api/routers/memory_edit.py"],
        decisions=["Return HTTP 409 Conflict on revision mismatch"],
    )

    assert end_res["ok"] is True
    assert end_res["session_id"] == session_id
    assert end_res["memory_id"] == "mem-456"
    assert end_res["error"] is None


@pytest.mark.asyncio
async def test_sdk_end_task_surfaces_diagnostic_errors_on_failure():
    client = UAMSClient(source_agent="OpenClaw")
    from uams_sdk.exceptions import UAMSAPIError
    client._request = AsyncMock(side_effect=UAMSAPIError("Database connection lost", status_code=500, details="Postgres timeout"))

    end_res = await client.end_task(
        task="Failed operation task",
        outcome="Attempted write",
    )

    assert end_res["ok"] is False
    assert "Database connection lost" in str(end_res["error"])
