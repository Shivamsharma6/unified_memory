import pytest
from unittest.mock import AsyncMock, MagicMock

try:
    from api.readiness import assess_lightweight_readiness
except ImportError:
    from memory_watcher.api.readiness import assess_lightweight_readiness


@pytest.mark.asyncio
async def test_readiness_probe_is_resilient_to_isolated_failed_outbox_rows():
    mock_store = AsyncMock()
    mock_store.ping.return_value = True
    mock_store.readiness_metrics.return_value = {
        "pending_jobs": 0,
        "failed_jobs": 1,
        "pending_outbox": 0,
        "failed_outbox": 1,  # 1 poison row
        "oldest_pending_seconds": 0.0,
    }

    mock_vector = AsyncMock()
    mock_vector.v2_collection = "memory_chunks_v2"
    mock_vector.client = AsyncMock()
    mock_vector.client.collection_exists.return_value = True

    result = await assess_lightweight_readiness(mock_store, mock_vector)

    # Readiness should still be True (healthy services) with degraded flag indicating failed outbox
    assert result["ready"] is True
    assert result["jobs"]["failed_outbox"] == 1
    assert result["degraded"] is True
