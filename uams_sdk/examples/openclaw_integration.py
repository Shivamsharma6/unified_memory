import asyncio
from uams_sdk import UAMSClient

class OpenClawMCPTool:
    """Example of an OpenClaw MCP Tool integration."""
    def __init__(self):
        self.memory = UAMSClient()

    async def execute_search_tool(self, query: str) -> str:
        """OpenClaw Tool: search_memory"""
        print(f"[OpenClaw] Tool called: search_memory(query='{query}')")
        
        # OpenClaw needs the raw search results for its own context assembly
        results = await self.memory.search(query, limit=3)
        
        # Expand graph to see if we missed anything
        if results.get("expanded_entities"):
            print(f"[OpenClaw] Graph expanded query to include: {results['expanded_entities']}")
            
        formatted = []
        for r in results.get("results", []):
            formatted.append(f"- {r['text']} (Importance: {r['importance']:.2f})")
            
        return "\n".join(formatted) if formatted else "No memories found."

if __name__ == "__main__":
    tool = OpenClawMCPTool()
    # Assuming FastAPI is mocked or running, we catch the connection error if it's not
    try:
        res = asyncio.run(tool.execute_search_tool("Why is the pipeline failing?"))
        print(res)
    except Exception as e:
        print(f"Expected failure if UAMS API is not running: {e}")
