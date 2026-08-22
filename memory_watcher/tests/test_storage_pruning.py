import pytest
from unittest.mock import AsyncMock, MagicMock

try:
    from storage.postgres_store import PostgresStore
except ImportError:
    from memory_watcher.storage.postgres_store import PostgresStore


@pytest.mark.asyncio
async def test_prune_superseded_storage_executes_deletions():
    store = PostgresStore()
    mock_cursor = AsyncMock()
    mock_cursor.rowcount = 12

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_cursor), __aexit__=AsyncMock()))
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.transaction = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(), __aexit__=AsyncMock()))

    mock_pool = MagicMock()
    mock_pool.connection = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_conn), __aexit__=AsyncMock()))
    store.pool = mock_pool

    stats = await store.prune_superseded_storage(max_age_days=14)

    assert "pruned_outbox" in stats
    assert "pruned_jobs" in stats
    assert "pruned_audit_events" in stats
    assert stats["pruned_outbox"] == 12
