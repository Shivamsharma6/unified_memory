import pytest
from datetime import datetime, timezone
from pathlib import Path

try:
    from api.retrieval.hybrid import HybridRetrieval
    from api.models import SearchRequest, SearchResult
except ImportError:
    from memory_watcher.api.retrieval.hybrid import HybridRetrieval
    from memory_watcher.api.models import SearchRequest, SearchResult


def test_temporal_boost_dynamic_scaling():
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    old_str = "2025-01-01"

    boost_recent = HybridRetrieval._temporal_boost({"date": now_str})
    boost_old = HybridRetrieval._temporal_boost({"date": old_str})
    boost_unknown = HybridRetrieval._temporal_boost({})

    assert boost_recent > boost_old
    assert boost_recent >= 0.10
    assert boost_old <= 0.05
    assert boost_unknown == 0.0

