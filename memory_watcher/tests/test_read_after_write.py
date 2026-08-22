import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock

try:
    from api.models import RememberRequest
    from uams_sdk.client import UAMSClient
except ImportError:
    from memory_watcher.api.models import RememberRequest
    from uams_sdk.client import UAMSClient


def test_remember_request_sync_field():
    req = RememberRequest(text="Synchronous test memory", sync=True)
    assert req.sync is True


@pytest.mark.asyncio
async def test_sdk_wait_for_indexing_polls_status_until_active():
    client = UAMSClient()
    client._request = AsyncMock()

    # Sequence: 1st check "staged", 2nd check "active"
    client._request.side_effect = [
        {"memory_id": "mem-1", "revision_status": "staged"},
        {"memory_id": "mem-1", "revision_status": "active"},
    ]

    is_active = await client.wait_for_indexing("mem-1", timeout=1.0, poll_interval=0.01)
    assert is_active is True
    assert client._request.call_count == 2


@pytest.mark.asyncio
async def test_sdk_wait_for_indexing_timeout():
    client = UAMSClient()
    client._request = AsyncMock(return_value={"memory_id": "mem-1", "revision_status": "staged"})

    is_active = await client.wait_for_indexing("mem-1", timeout=0.05, poll_interval=0.01)
    assert is_active is False
