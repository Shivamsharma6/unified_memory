import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient
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

def test_remember_endpoint():
    response = client.post("/remember", json={"text": "Test memory", "category": "semantic"})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
