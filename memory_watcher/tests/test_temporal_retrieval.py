import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

import pytest
from api.retrieval.pipeline import RetrievalPipeline


def test_temporal_boost_calculates_recency():
    pipeline = RetrievalPipeline()
    from datetime import datetime, timedelta
    now = datetime.now()
    recent = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=90)).isoformat()
    assert pipeline._temporal_boost(recent) > pipeline._temporal_boost(old)


def test_temporal_boost_returns_zero_for_unknown():
    pipeline = RetrievalPipeline()
    assert pipeline._temporal_boost("") == 0.0
    assert pipeline._temporal_boost("not-a-date") == 0.0


def test_temporal_boost_recent_is_high():
    pipeline = RetrievalPipeline()
    from datetime import datetime, timedelta
    now = datetime.now()
    yesterday = (now - timedelta(days=1)).isoformat()
    boost = pipeline._temporal_boost(yesterday)
    assert boost > 0.9  # 1 day ago should be very high
