import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app


def _mock_llm():
    m = MagicMock()
    m.generate = AsyncMock(return_value="UAMS uses Qdrant for vector storage and embeddings for semantic search across agent memories.")
    return m


def test_summarize_returns_llm_summary():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(text="Qdrant is used for vector storage.", source_file="test.md"),
            MagicMock(text="The system uses embeddings for semantic search.", source_file="test2.md"),
        ]
        mock_result.context_tokens_used = 50
        mock_pipeline.search = AsyncMock(return_value=mock_result)

        with patch("api.main._get_llm", return_value=_mock_llm()):
            response = client.post("/summarize", json={"topic": "UAMS architecture"})
            assert response.status_code == 200
            data = response.json()
            assert "summary" in data
            assert len(data["summary"]) > 20


def test_summarize_returns_sources():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(text="Qdrant stores vectors.", source_file="arch.md"),
        ]
        mock_pipeline.search = AsyncMock(return_value=mock_result)

        mock = _mock_llm()
        mock.generate = AsyncMock(return_value="Summary about Qdrant.")
        with patch("api.main._get_llm", return_value=mock):
            response = client.post("/summarize", json={"topic": "Qdrant"})
            data = response.json()
            assert "sources" in data
            assert data["sources"] == ["arch.md"]


def test_summarize_no_context():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_result = MagicMock()
        mock_result.results = []
        mock_pipeline.search = AsyncMock(return_value=mock_result)

        response = client.post("/summarize", json={"topic": "nonexistent"})
        assert response.status_code == 200
        data = response.json()
        assert "No relevant context" in data["summary"]
        assert data["sources"] == []


def test_summarize_handles_search_error():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_pipeline.search = AsyncMock(side_effect=RuntimeError("search failed"))

        response = client.post("/summarize", json={"topic": "broken"})
        assert response.status_code == 500


def test_summarize_passes_max_tokens():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(text="Some context.", source_file="doc.md"),
        ]
        mock_pipeline.search = AsyncMock(return_value=mock_result)

        mock = _mock_llm()
        mock.generate = AsyncMock(return_value="Summary.")
        with patch("api.main._get_llm", return_value=mock):
            response = client.post("/summarize", json={"topic": "test", "max_tokens": 100})
            assert response.status_code == 200
            mock.generate.assert_called_once()
            call_args = mock.generate.call_args
            assert call_args.kwargs.get("max_tokens") == 100
