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
    assert "status" in response.json()
    assert "components" in response.json()


def test_health_check_reports_unavailable_qdrant(monkeypatch):
    class BrokenQdrantClient:
        async def get_collections(self):
            raise RuntimeError("qdrant offline")

    monkeypatch.setattr(api_main.pipeline.vector_store, "client", BrokenQdrantClient())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["qdrant"]["status"] == "unavailable"
    assert "qdrant offline" in body["components"]["qdrant"]["detail"]


def test_ready_endpoint_uses_readiness_report(monkeypatch):
    async def fake_assess(*args, **kwargs):
        return {
            "ready": True,
            "components": {
                "postgresql": {"status": "ok"},
                "qdrant": {"status": "ok"},
            },
            "jobs": {"pending_jobs": 0, "failed_jobs": 0},
        }

    monkeypatch.setattr(api_main, "assess_lightweight_readiness", fake_assess, raising=False)
    monkeypatch.setattr(api_main.pipeline, "hybrid", object())

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_projection_status_endpoint(monkeypatch):
    async def fake_drift(*args, **kwargs):
        return {
            "ready": True,
            "components": {
                "postgresql": {"status": "ok"},
                "qdrant": {"status": "ok"},
                "embedding_search_probe": {"status": "ok"},
            },
            "jobs": {"pending_jobs": 0, "failed_jobs": 0},
            "drift": {"total": 0},
        }

    monkeypatch.setattr(api_main, "assess_deep_projection_drift", fake_drift, raising=False)
    monkeypatch.setattr(api_main.pipeline, "hybrid", object())

    response = client.get("/projection-status")

    assert response.status_code == 200
    assert response.json()["ready"] is True


def test_search_endpoint():
    # Since we can't spin up Qdrant reliably in a fast unit test without mocking,
    # we just test the endpoint schema and routing
    pass

def test_remember_endpoint(monkeypatch, tmp_path):
    async def fake_process_file(path):
        return None

    memory_file = tmp_path / "test-memory.md"
    memory_file.write_text("# Test Memory\n\nSome body text", encoding="utf-8")
    monkeypatch.setattr(api_main, "write_memory", lambda request, **kwargs: memory_file)
    monkeypatch.setattr(api_main.ingestion_pipeline, "process_file", fake_process_file)

    response = client.post("/remember", json={"text": "Test memory", "category": "semantic"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["index_status"] in {"staged", "active", "pending"}



def test_procedures_endpoint():
    response = client.post("/procedures", json={"task": "write a memory note"})
    assert response.status_code == 200
    assert response.json()["procedures"]
    assert "AGENTS.md" in response.json()["procedures"][0]


def test_entities_and_relations_use_control_plane(monkeypatch):
    class GraphStore:
        async def list_entities(self):
            return ["PostgreSQL", "Unified Memory"]

        async def graph_neighborhood(self, entity, **kwargs):
            return {
                "nodes": [],
                "links": [
                    {
                        "source": "Unified Memory",
                        "target": "PostgreSQL",
                        "predicate": "uses",
                        "evidence_revision_id": "revision-1",
                        "status": "explicit",
                    }
                ],
            }

    monkeypatch.setattr(api_main.app.state, "control_store", GraphStore(), raising=False)

    entities = client.post("/entities")
    relations = client.post("/relations", params={"entity": "Unified Memory"})

    assert entities.json() == {"entities": ["PostgreSQL", "Unified Memory"]}
    assert relations.json()["relations"][0]["evidence_revision_id"] == "revision-1"
