import pytest
from uams_sdk.mcp_server import mcp


@pytest.mark.asyncio
async def test_get_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_identity" in tool_names


@pytest.mark.asyncio
async def test_inject_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "inject_identity" in tool_names


@pytest.mark.asyncio
async def test_extract_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "extract_identity" in tool_names


@pytest.mark.asyncio
async def test_memory_quality_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "memory_quality" in tool_names