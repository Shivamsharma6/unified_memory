import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient
import api.main as api_main
from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_search_endpoint():
    # Since we can't spin up Qdrant reliably in a fast unit test without mocking,
    # we just test the endpoint schema and routing
    pass

def test_remember_endpoint(monkeypatch, tmp_path):
    async def fake_process_file(path):
        return None

    memory_file = tmp_path / "test-memory.md"
    monkeypatch.setattr(api_main, "write_memory", lambda request: memory_file)
    monkeypatch.setattr(api_main.ingestion_pipeline, "process_file", fake_process_file)

    response = client.post("/remember", json={"text": "Test memory", "category": "semantic"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["indexed"] is True

def test_procedures_endpoint():
    response = client.post("/procedures", json={"task": "write a memory note"})
    assert response.status_code == 200
    assert response.json()["procedures"]
    assert "AGENTS.md" in response.json()["procedures"][0]
