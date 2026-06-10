import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

# Add parent dir to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from api.main import app


def test_identity_profile_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_profile = MagicMock()
        mock_profile.to_payload.return_value = {
            "entity_id": "test-agent", "entity_name": "Test Agent",
            "traits": {}, "global_confidence": 0.5,
        }
        mock_store.get_profile.return_value = mock_profile
        response = client.post("/identity/profile", json={"entity_id": "test-agent"})
        assert response.status_code == 200


def test_identity_extract_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_store.extract_from_memories.return_value = {
            "entity_id": "test-agent", "traits_found": 3, "global_confidence": 0.6,
        }
        response = client.post("/identity/extract", json={
            "entity_id": "test-agent",
            "memories": [{"id": "m1", "summary": "test", "content": "test content"}],
        })
        assert response.status_code == 200


def test_identity_inject_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_store.inject_identity.return_value = {
            "entity_id": "test-agent", "core_identity": {"top_traits": []},
        }
        response = client.post("/identity/inject", json={"entity_id": "test-agent", "query": "test"})
        assert response.status_code == 200


def test_identity_list_entities():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_store.list_entities.return_value = ["Agent Alpha", "Agent Beta"]
        response = client.post("/identity/entities")
        assert response.status_code == 200
        assert response.json()["entities"] == ["Agent Alpha", "Agent Beta"]


if __name__ == "__main__":
    unittest.main()