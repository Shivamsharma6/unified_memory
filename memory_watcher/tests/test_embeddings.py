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


class ContextLimitedOllamaClient:
    def __init__(self):
        self.prompts = []

    async def embeddings(self, *, model, prompt):
        self.prompts.append(prompt)
        if len(prompt) > 8:
            raise RuntimeError("the input length exceeds the context length")
        if prompt.startswith("a"):
            return {"embedding": [1.0, 0.0]}
        return {"embedding": [0.0, 1.0]}

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

    async def test_ollama_context_overflow_segments_and_combines_the_full_text(self):
        generator = EmbeddingGenerator(provider="ollama", model_name="context-limited")
        generator.ollama_client = ContextLimitedOllamaClient()

        embeddings = await generator._generate_ollama(["aaaaaaaabbbbbbbb"])

        self.assertEqual(generator.ollama_client.prompts[0], "aaaaaaaabbbbbbbb")
        self.assertIn("aaaaaaaa", generator.ollama_client.prompts)
        self.assertIn("bbbbbbbb", generator.ollama_client.prompts)
        self.assertAlmostEqual(embeddings[0][0], 2 ** -0.5)
        self.assertAlmostEqual(embeddings[0][1], 2 ** -0.5)

if __name__ == '__main__':
    unittest.main()
