import logging
from pathlib import Path
from models.document import Document
from chunkers.semantic import SemanticChunker
from embeddings.generator import EmbeddingGenerator
from storage.vector_store import VectorStore
from graph.updater import GraphUpdater
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)

class IngestionPipeline:
    def __init__(self):
        self.chunker = SemanticChunker()
        self.embedder = EmbeddingGenerator()
        self.vector_store = VectorStore()
        self.graph_updater = GraphUpdater()

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def process_file(self, file_path: str):
        logger.info(f"Processing pipeline for: {file_path}")
        
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File {file_path} deleted before processing.")
            return

        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return

        # 2. Parse Markdown & 3. Extract metadata
        # TODO: integrate yaml frontmatter parsing
        doc = Document(path=file_path, raw_content=content)

        # 4. Split semantically
        doc = self.chunker.chunk(doc)

        # 5. Generate embeddings
        doc = await self.embedder.embed(doc)

        # 6. Store embeddings
        await self.vector_store.store(doc)

        # 7. Update graph relations
        await self.graph_updater.update_relations(doc)
        
        # 8. Generate summaries (Stub)
        
        logger.info(f"Pipeline complete for {file_path}")
