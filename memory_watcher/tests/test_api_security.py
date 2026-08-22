import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException

try:
    from api.security import verify_agent_auth, extract_caller_agent
except ImportError:
    from memory_watcher.api.security import verify_agent_auth, extract_caller_agent


@pytest.mark.asyncio
async def test_auth_not_required_by_default():
    request = MagicMock()
    request.headers = {"X-Agent-Id": "Hermes"}
    request.query_params = {}
    agent = await verify_agent_auth(request, credentials=None)
    assert agent == "Hermes"


@pytest.mark.asyncio
async def test_api_key_auth_succeeds_with_valid_key(monkeypatch):
    monkeypatch.setenv("UAMS_API_KEY", "secret-agent-key-123")

    credentials = MagicMock()
    credentials.credentials = "secret-agent-key-123"

    request = MagicMock()
    request.headers = {"X-Agent-Id": "OpenClaw"}
    request.query_params = {}

    agent = await verify_agent_auth(request, credentials=credentials)
    assert agent == "OpenClaw"


@pytest.mark.asyncio
async def test_api_key_auth_rejects_with_invalid_or_missing_key(monkeypatch):
    monkeypatch.setenv("UAMS_API_KEY", "secret-agent-key-123")

    # Missing credentials
    request = MagicMock()
    request.headers = {}
    request.query_params = {}
    with pytest.raises(HTTPException) as exc_info:
        await verify_agent_auth(request, credentials=None)
    assert exc_info.value.status_code == 401

    # Invalid credentials
    bad_credentials = MagicMock()
    bad_credentials.credentials = "wrong-key"
    with pytest.raises(HTTPException) as exc_info:
        await verify_agent_auth(request, credentials=bad_credentials)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_agent_whitelist_enforcement(monkeypatch):
    monkeypatch.setenv("UAMS_ALLOWED_AGENTS", "Hermes,OpenClaw,VoiceAI")

    # Allowed agent
    request = MagicMock()
    request.headers = {"X-Agent-Id": "Hermes"}
    request.query_params = {}
    agent = await verify_agent_auth(request, credentials=None)
    assert agent == "Hermes"

    # Unauthorized rogue agent
    request.headers = {"X-Agent-Id": "MaliciousBot"}
    with pytest.raises(HTTPException) as exc_info:
        await verify_agent_auth(request, credentials=None)
    assert exc_info.value.status_code == 403
    assert "MaliciousBot" in exc_info.value.detail
