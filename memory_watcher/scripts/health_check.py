import asyncio
import sys
import logging
from pathlib import Path

# Add parent to path
sys.path.append(str(Path(__file__).parent.parent))
from storage.qdrant_store import QdrantStore

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_health():
    store = QdrantStore()
    try:
        # Check connection and initialize collections
        await store.initialize_collections()
        logger.info("✅ Qdrant connection successful!")
        
        # List collections
        collections = await store.client.get_collections()
        col_names = [c.name for c in collections.collections]
        logger.info(f"✅ Active Collections: {col_names}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Qdrant health check failed: {e}")
        return False

if __name__ == "__main__":
    success = asyncio.run(check_health())
    sys.exit(0 if success else 1)
