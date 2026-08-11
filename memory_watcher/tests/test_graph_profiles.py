import sys
import uuid
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.routers.graph import router as graph_router
from api.routers.memory_edit import router as memory_router
from api.routers.profiles import router as profiles_router


class FakeStore:
    def __init__(self):
        self.graph_calls = []
        self.profile_calls = []

    async def graph_neighborhood(
        self,
        entity,
        radius=1,
        include_candidates=False,
        include_historical=False,
    ):
        self.graph_calls.append((entity, radius, include_candidates, include_historical))
        links = [
            {
                "key": "claim-explicit",
                "source": "Unified Memory",
                "target": "PostgreSQL",
                "relation": "uses",
                "predicate": "uses",
                "claim_id": "claim-explicit",
                "evidence_memory_id": "memory-1",
                "evidence_revision_id": "revision-1",
                "confidence": 1.0,
                "status": "explicit",
            }
        ]
        if include_candidates:
            links.append(
                {
                    "key": "claim-candidate",
                    "source": "Unified Memory",
                    "target": "Redis",
                    "relation": "uses",
                    "predicate": "uses",
                    "claim_id": "claim-candidate",
                    "evidence_memory_id": "memory-2",
                    "evidence_revision_id": "revision-2",
                    "confidence": 0.4,
                    "status": "candidate",
                }
            )
        return {
            "directed": True,
            "multigraph": True,
            "graph": {},
            "nodes": [
                {"id": "Unified Memory", "label": "Unified Memory", "type": "architecture"},
                {"id": "PostgreSQL", "label": "PostgreSQL", "type": "concept"},
            ],
            "links": links,
        }

    async def export_claim_graph(self, include_candidates=False, include_historical=False):
        return await self.graph_neighborhood(
            "Unified Memory",
            radius=99,
            include_candidates=include_candidates,
            include_historical=include_historical,
        )

    async def get_profile(self, profile_id, include_historical=False):
        self.profile_calls.append((profile_id, include_historical))
        if profile_id == "archived" and not include_historical:
            return None
        return {
            "profile_id": "profile-1",
            "profile_type": "user",
            "canonical_key": profile_id,
            "display_name": "Shivam Sharma",
            "metadata": {"path": "People/Shivam Sharma.md"},
            "facts": [
                {
                    "fact_id": "fact-1",
                    "key": "preferred_database",
                    "value": "PostgreSQL",
                    "status": "active",
                    "evidence_memory_id": "memory-1",
                    "evidence_revision_id": "revision-1",
                    "source_file": "People/Shivam Sharma.md",
                }
            ],
        }

    async def get_memory_status(self, memory_id):
        return {
            "memory_id": str(memory_id),
            "path": "Concepts/Test.md",
            "document_status": "active",
            "current_revision_id": None,
            "latest_revision_id": "revision-1",
            "revision_state": "staged",
            "index_status": "pending",
            "job_status": "pending",
        }


def client_and_store():
    app = FastAPI()
    store = FakeStore()
    app.state.control_store = store
    app.include_router(graph_router)
    app.include_router(profiles_router)
    app.include_router(memory_router)
    return TestClient(app), store


def test_graph_links_include_evidence_and_hide_candidates_by_default():
    client, store = client_and_store()

    response = client.get("/graph/neighborhood/Unified%20Memory")

    assert response.status_code == 200
    links = response.json()["links"]
    assert [link["status"] for link in links] == ["explicit"]
    assert links[0]["claim_id"]
    assert links[0]["predicate"] == "uses"
    assert links[0]["evidence_revision_id"] == "revision-1"
    assert store.graph_calls[0] == ("Unified Memory", 1, False, False)


def test_graph_candidate_and_historical_access_are_explicit():
    client, store = client_and_store()

    response = client.get(
        "/graph/neighborhood/Unified%20Memory?include_candidates=true&include_historical=true"
    )

    assert {link["status"] for link in response.json()["links"]} == {"explicit", "candidate"}
    assert store.graph_calls[0] == ("Unified Memory", 1, True, True)


def test_profile_returns_current_facts_with_evidence():
    client, _ = client_and_store()

    response = client.get("/profiles/shivam%20sharma")

    assert response.status_code == 200
    fact = response.json()["facts"][0]
    assert fact["value"] == "PostgreSQL"
    assert fact["evidence_memory_id"] == "memory-1"
    assert fact["evidence_revision_id"] == "revision-1"


def test_archived_profile_requires_historical_opt_in():
    client, _ = client_and_store()

    assert client.get("/profiles/archived").status_code == 404
    assert client.get("/profiles/archived?include_historical=true").status_code == 200


def test_memory_write_status_reports_pending_projection():
    client, _ = client_and_store()
    memory_id = uuid.uuid4()

    response = client.get(f"/memory/status/{memory_id}")

    assert response.status_code == 200
    assert response.json()["index_status"] == "pending"
    assert response.json()["revision_state"] == "staged"
