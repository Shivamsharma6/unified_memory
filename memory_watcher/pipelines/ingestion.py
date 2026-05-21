import logging
from pathlib import Path
from models.document import Document
from chunkers.semantic import SemanticChunker
from embeddings.generator import EmbeddingGenerator
from storage.qdrant_store import QdrantStore
from graph.updater import GraphUpdater
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(self):
        self.chunker = SemanticChunker()
        self.embedder = EmbeddingGenerator()
        self.vector_store = QdrantStore()
        self.graph_updater = GraphUpdater()

    async def initialize(self):
        await self.vector_store.initialize_collections()

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def process_file(self, file_path: str):
        logger.info(f"Processing pipeline for: {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            return

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return

        doc = Document(path=file_path, raw_content=content)
        doc = self.chunker.chunk(doc)
        doc = await self.embedder.embed(doc)
        
        # Batch store in Qdrant
        await self.vector_store.store_batch(doc)
        
        await self.graph_updater.update_relations(doc)
        logger.info(f"Pipeline complete for {file_path}")
