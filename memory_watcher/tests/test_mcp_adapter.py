import unittest
from unittest.mock import AsyncMock, patch

from uams_sdk.mcp_server import mcp


class TestMCPAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_tool_discovery(self):
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        prompts = await mcp.list_prompts()

        tool_names = {tool.name for tool in tools}
        self.assertIn("begin_task", tool_names)
        self.assertIn("end_task", tool_names)
        self.assertIn("get_context", tool_names)
        self.assertIn("remember", tool_names)
        self.assertIn("store_fix_summary", tool_names)
        self.assertIn("uams://memory-policy", {str(resource.uri) for resource in resources})
        self.assertIn("use_uams_memory", {prompt.name for prompt in prompts})

    async def test_begin_task_tool_returns_default_memory_packet(self):
        fake_client = AsyncMock()
        fake_client.begin_task.return_value = {
            "task": "Fix login timeout",
            "procedures": ["Use AGENTS.md"],
            "context": "Prior memory",
            "memory_policy": "Always use UAMS.",
            "status": "ready",
        }

        with patch("uams_sdk.mcp_server._client", return_value=fake_client):
            result = await mcp.call_tool("begin_task", {"task": "Fix login timeout", "max_tokens": 500})

        fake_client.begin_task.assert_awaited_once_with(task="Fix login timeout", max_tokens=500)
        self.assertEqual(result[1]["status"], "ready")
        self.assertIn("Prior memory", result[1]["context"])

    async def test_end_task_tool_stores_distilled_outcome(self):
        fake_client = AsyncMock()
        fake_client.end_task.return_value = {
            "ok": True,
            "category": "episodic",
            "tags": ["#auto-distilled"],
        }

        with patch("uams_sdk.mcp_server._client", return_value=fake_client):
            result = await mcp.call_tool(
                "end_task",
                {
                    "task": "Fix login timeout",
                    "outcome": "Added regression test and fixed timeout handling.",
                    "files": ["auth/session.py"],
                    "decisions": ["Keep local-first memory"],
                    "fixes": ["Adjusted timeout handling"],
                    "entities": ["Login Timeout"],
                },
            )

        fake_client.end_task.assert_awaited_once()
        self.assertTrue(result[1]["ok"])

    async def test_prompt_use_uams_memory_without_and_with_args(self):
        prompt_no_args = await mcp.get_prompt("use_uams_memory")
        self.assertIn("You have access to Unified Agent Memory System tools", prompt_no_args.messages[0].content.text)

        prompt_with_args = await mcp.get_prompt("use_uams_memory", {"task": "Refactor auth"})
        self.assertIn("Task: Refactor auth", prompt_with_args.messages[0].content.text)


if __name__ == "__main__":
    unittest.main()

