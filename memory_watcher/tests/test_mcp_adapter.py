import unittest

from uams_sdk.mcp_server import mcp


class TestMCPAdapter(unittest.IsolatedAsyncioTestCase):
    async def test_mcp_tool_discovery(self):
        tools = await mcp.list_tools()
        resources = await mcp.list_resources()
        prompts = await mcp.list_prompts()

        tool_names = {tool.name for tool in tools}
        self.assertIn("get_context", tool_names)
        self.assertIn("remember", tool_names)
        self.assertIn("store_fix_summary", tool_names)
        self.assertIn("uams://memory-policy", {str(resource.uri) for resource in resources})
        self.assertIn("use_uams_memory", {prompt.name for prompt in prompts})


if __name__ == "__main__":
    unittest.main()
