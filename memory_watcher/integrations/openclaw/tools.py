from typing import Dict, Any, List
try:
    from .client import UAMSClient
except ImportError:
    from client import UAMSClient

# These functions are designed to be exposed as tools/MCP for OpenClaw/Hermes

client = UAMSClient()

async def search_memory(query: str, limit: int = 5) -> str:
    """
    Search the agent's long-term and semantic memory.
    Use this to recall facts, previous conversations, or project context.
    """
    res = await client.search(query, limit)
    if "error" in res: return f"Error accessing memory: {res['error']}"
    
    results = res.get("results", [])
    if not results: return "No relevant memories found."
    
    formatted = "\n\n".join([f"- (Score: {r['score']:.2f}) {r['text']}" for r in results])
    return f"Found {len(results)} memories:\n{formatted}"

async def store_memory(text: str, tags: List[str]) -> str:
    """
    Store an important fact, decision, or user preference into long-term memory.
    """
    res = await client.remember(text=text, tags=tags)
    if "error" in res: return f"Failed to store memory: {res['error']}"
    return "Memory successfully stored."

async def summarize_topic(topic: str) -> str:
    """
    Generate a concise summary of all memories related to a specific topic.
    """
    res = await client.summarize(topic)
    return res.get("summary", str(res))

async def retrieve_procedures(task: str) -> str:
    """
    Retrieve operational protocols or standard operating procedures for a task.
    """
    res = await client.get_procedures(task)
    procedures = res.get("procedures", [])
    if not procedures: return f"No specific procedures found for '{task}'."
    return "\n".join(procedures)

async def retrieve_graph_relations(entity: str) -> str:
    """
    Explore the knowledge graph by retrieving relationships for a specific entity.
    """
    res = await client.get_relations(entity)
    relations = res.get("relations", [])
    if not relations: return "No relations found."
    return str(relations)
