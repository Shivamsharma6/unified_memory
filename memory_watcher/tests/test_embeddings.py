import sys
import asyncio
import unittest
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from embeddings.generator import EmbeddingGenerator
from embeddings.cache import EmbeddingCache
from embeddings.utils import cosine_similarity
from models.document import Document, Chunk, ChunkMetadata
import os

class TestEmbeddings(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Use a test db
        self.cache_path = "test_cache.db"
        self.generator = EmbeddingGenerator(provider="fake", model_name="test-embedding")
        self.generator.cache.db_path = str(Path(__file__).parent.parent / self.cache_path)
        await self.generator.initialize()
        
    async def asyncTearDown(self):
        db_file = Path(__file__).parent.parent / self.cache_path
        if db_file.exists():
            os.remove(db_file)

    async def test_caching_and_batching(self):
        doc = Document(path="test.md", raw_content="test")
        meta = ChunkMetadata(chunk_id="1", source_file="test.md")
        doc.chunks.append(Chunk(content="Hello world", metadata=meta))
        
        # Uncached
        doc = await self.generator.embed(doc)
        self.assertIsNotNone(doc.chunks[0].embedding)
        embed1 = list(doc.chunks[0].embedding)
        
        # Clear it
        doc.chunks[0].embedding = None
        
        # Cached
        doc = await self.generator.embed(doc)
        embed2 = list(doc.chunks[0].embedding)
        
        self.assertEqual(embed1, embed2)
        
    def test_cosine_similarity(self):
        v1 = [1.0, 0.0, 0.0]
        v2 = [1.0, 0.0, 0.0]
        v3 = [0.0, 1.0, 0.0]
        
        self.assertAlmostEqual(cosine_similarity(v1, v2), 1.0)
        self.assertAlmostEqual(cosine_similarity(v1, v3), 0.0)

if __name__ == '__main__':
    unittest.main()
