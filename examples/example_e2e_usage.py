import asyncio
import sys
import json
import logging
import httpx

# Add SDK to path
sys.path.insert(0, "./uams_sdk")
from uams_sdk.client import UAMSClient

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

async def test_endpoints():
    client = UAMSClient("http://127.0.0.1:8000")
    
    # 1. Health
    logging.info("--- Testing /health ---")
    async with httpx.AsyncClient() as http:
        resp = await http.get("http://127.0.0.1:8000/health")
        logging.info(f"Status {resp.status_code}: {json.dumps(resp.json())[:200]}...")

    # 2. Remember
    logging.info("\n--- Testing /remember ---")
    mem_id = await client.store_memory(
        text="The main database was migrated to Qdrant because Pinecone was too expensive for local dev.",
        category="procedural",
        tags=["#database", "#qdrant"]
    )
    logging.info(f"Memory stored successfully. Return ID: {mem_id}")

    # 3. Search
    logging.info("\n--- Testing /search ---")
    search_results = await client.search("Why did we migrate the database?")
    logging.info(f"Found {len(search_results)} results.")
    if search_results and "results" in search_results:
        results = search_results["results"]
        if results:
            logging.info(f"Top result: {results[0].get('text', '')[:100]}...")

    # 4. Context
    logging.info("\n--- Testing /context ---")
    context = await client.retrieve_context("database migration")
    logging.info(f"Context retrieved ({len(context)} chars). Snippet: {context[:100]}...")
    
    # 5. Reflection
    logging.info("\n--- Testing /reflect ---")
    try:
        async with httpx.AsyncClient(timeout=120) as http:
            resp = await http.post("http://127.0.0.1:8000/reflect", json={
                "task_description": "We migrated the database to Qdrant",
                "outcomes": ["Speed increased", "Cost decreased"],
                "challenges_faced": ["Had to re-index embeddings"]
            })
            logging.info(f"Reflection status {resp.status_code}: {json.dumps(resp.json())[:100]}...")
    except Exception as e:
        logging.error(f"Reflection failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_endpoints())
