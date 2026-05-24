import unittest
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class TestMCPAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_tool_discovery(self):
        repo_root = Path(__file__).resolve().parents[2]
        params = StdioServerParameters(
            command=str(repo_root / "uams"),
            args=["mcp"],
            env={"UAMS_API_URL": "http://localhost:8000"},
        )

        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = await session.list_tools()
                resources = await session.list_resources()
                prompts = await session.list_prompts()

        tool_names = {tool.name for tool in tools.tools}
        self.assertIn("get_context", tool_names)
        self.assertIn("remember", tool_names)
        self.assertIn("store_fix_summary", tool_names)
        self.assertIn("uams://memory-policy", {str(resource.uri) for resource in resources.resources})
        self.assertIn("use_uams_memory", {prompt.name for prompt in prompts.prompts})


if __name__ == "__main__":
    unittest.main()
