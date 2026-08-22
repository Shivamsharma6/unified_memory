from datetime import datetime, timezone, timedelta
import pytest

try:
    from api.retrieval.pipeline import RetrievalPipeline
    from api.retrieval.hybrid import HybridRetrieval
except ImportError:
    from memory_watcher.api.retrieval.pipeline import RetrievalPipeline
    from memory_watcher.api.retrieval.hybrid import HybridRetrieval


def test_temporal_boost_bounded_scaling_and_decay():
    pipeline = RetrievalPipeline()
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    two_weeks_ago_iso = (now - timedelta(days=14)).isoformat()
    old_iso = (now - timedelta(days=120)).isoformat()

    boost_now = pipeline._temporal_boost(now_iso)
    boost_2w = pipeline._temporal_boost(two_weeks_ago_iso)
    boost_old = pipeline._temporal_boost(old_iso)
    boost_invalid = pipeline._temporal_boost("not-a-date")

    # Bounded to 0.15 max
    assert 0.14 <= boost_now <= 0.15
    # Half-life of 14 days should yield ~0.075
    assert 0.06 <= boost_2w <= 0.09
    # Old memory should decay towards 0
    assert boost_old < 0.01
    assert boost_invalid == 0.0
