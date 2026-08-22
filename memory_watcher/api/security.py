"""
Authentication, Authorization, and Per-Agent Identity Security Layer for UAMS.

Provides:
- Bearer token / API key verification via `UAMS_API_KEY` & `UAMS_AUTH_REQUIRED`.
- Per-caller agent identity extraction (`X-Agent-Id`, `X-Source-Agent`).
- Agent whitelist and revocation controls via `UAMS_ALLOWED_AGENTS`.
"""

from __future__ import annotations

import os
import logging
from typing import Optional
from fastapi import Request, HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


def get_configured_api_key() -> Optional[str]:
    return os.getenv("UAMS_API_KEY") or os.getenv("UAMS_AUTH_TOKEN")


def is_auth_required() -> bool:
    val = os.getenv("UAMS_AUTH_REQUIRED", "").strip().lower()
    return val in {"true", "1", "yes", "on"} or get_configured_api_key() is not None


def get_allowed_agents() -> Optional[set[str]]:
    raw = os.getenv("UAMS_ALLOWED_AGENTS", "").strip()
    if not raw:
        return None
    return {agent.strip().lower() for agent in raw.split(",") if agent.strip()}


def extract_caller_agent(request: Request) -> str:
    """Extract caller agent ID from headers or query parameters."""
    agent_id = (
        request.headers.get("X-Agent-Id")
        or request.headers.get("X-Source-Agent")
        or request.query_params.get("source_agent")
        or "unknown"
    ).strip()
    return agent_id


async def verify_agent_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> str:
    """
    Authenticate the request and return the verified caller agent ID.
    Raises HTTPException 401 on authentication failure, 403 on agent authorization failure.
    """
    configured_key = get_configured_api_key()
    auth_required = is_auth_required()

    # 1. Verify API Key / Bearer token if auth is required or key is configured
    if auth_required or configured_key:
        provided_token = None
        if credentials and credentials.credentials:
            provided_token = credentials.credentials
        elif "X-API-Key" in request.headers:
            provided_token = request.headers["X-API-Key"]
        elif "x-api-key" in request.headers:
            provided_token = request.headers["x-api-key"]

        if not provided_token or (configured_key and provided_token != configured_key):
            logger.warning("Unauthorized access attempt on %s", request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unauthorized: Invalid or missing authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # 2. Extract and authorize caller agent
    caller_agent = extract_caller_agent(request)
    allowed_agents = get_allowed_agents()
    if allowed_agents is not None:
        if caller_agent.lower() not in allowed_agents:
            logger.warning("Forbidden agent identity '%s' on %s", caller_agent, request.url.path)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Agent '{caller_agent}' is not authorized",
            )

    return caller_agent
