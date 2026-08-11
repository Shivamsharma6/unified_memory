import asyncio
import logging
import hashlib
import math
from typing import List, Optional
from tenacity import retry, wait_exponential, stop_after_attempt
from models.document import Document
from embeddings.cache import EmbeddingCache
import os
import httpx
from typing import List, Optional

logger = logging.getLogger(__name__)

class EmbeddingGenerator:
    def __init__(self, provider: str = None, model_name: str = None):
        """
        provider: "fastembed" or "ollama"
        model_name: e.g. "nomic-ai/nomic-embed-text-v1.5", "BAAI/bge-m3" (for fastembed)
                    or "nomic-embed-text", "bge-m3" (for ollama)
        """
        self.provider = provider or os.getenv("UAMS_EMBED_PROVIDER", "ollama")
        self.model_name = model_name or os.getenv("UAMS_EMBED_MODEL", "mxbai-embed-large:335m")
        self.api_key = os.getenv("UAMS_EMBED_API_KEY")
        self.cache = EmbeddingCache()
        self._fastembed_model = None
        self.ollama_client = None
        
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        await self.cache.init_db()
        if self.provider == "fastembed":
            from fastembed import TextEmbedding
            # Fastembed automatically leverages Apple Silicon (MPS/CoreML) via ONNX Runtime if available
            self._fastembed_model = TextEmbedding(model_name=self.model_name)
        elif self.provider == "ollama":
            from ollama import AsyncClient as OllamaClient
            self.ollama_client = OllamaClient()
        elif self.provider == "openai":
            if not self.api_key:
                raise ValueError("UAMS_EMBED_API_KEY is required for OpenAI embeddings")
        elif self.provider == "fake":
            pass
        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")
        self._initialized = True

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _generate_ollama(self, texts: List[str]) -> List[List[float]]:
        async def _embed_single(text: str) -> List[float]:
            try:
                response = await self.ollama_client.embeddings(
                    model=self.model_name,
                    prompt=text,
                )
                return response["embedding"]
            except Exception as error:
                message = str(error).casefold()
                context_overflow = (
                    "input length" in message and "context length" in message
                )
                if not context_overflow or len(text) < 2:
                    raise

                midpoint = len(text) // 2
                whitespace = text.rfind(" ", len(text) // 4, midpoint + 1)
                split_at = whitespace if whitespace > 0 else midpoint
                left = text[:split_at].strip()
                right = text[split_at:].strip()
                if not left or not right:
                    left, right = text[:midpoint], text[midpoint:]
                left_vector, right_vector = await asyncio.gather(
                    _embed_single(left),
                    _embed_single(right),
                )
                total_weight = len(left) + len(right)
                combined = [
                    (
                        left_value * len(left)
                        + right_value * len(right)
                    )
                    / total_weight
                    for left_value, right_value in zip(left_vector, right_vector)
                ]
                magnitude = math.sqrt(sum(value * value for value in combined))
                return (
                    [value / magnitude for value in combined]
                    if magnitude
                    else combined
                )

        return await asyncio.gather(*(_embed_single(t) for t in texts))

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _generate_openai(self, texts: List[str]) -> List[List[float]]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"input": texts, "model": self.model_name}
            )
            response.raise_for_status()
            data = response.json()
            # OpenAI returns results in order
            return [item['embedding'] for item in data['data']]

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def _generate_fastembed(self, texts: List[str]) -> List[List[float]]:
        # fastembed is synchronous and returns a generator
        def _embed():
            return list(self._fastembed_model.embed(texts))
        
        embeddings = await asyncio.to_thread(_embed)
        return [e.tolist() for e in embeddings]

    async def _generate_fake(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        for text in texts:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            values = [((digest[i % len(digest)] / 255.0) * 2.0) - 1.0 for i in range(384)]
            embeddings.append(values)
        return embeddings

    async def embed(self, doc: Document) -> Document:
        await self.initialize()
        
        texts_to_embed = []
        chunk_indices = []
        
        # Check cache first for low memory usage and high speed
        for i, chunk in enumerate(doc.chunks):
            cached = await self.cache.get(chunk.content, self.model_name)
            if cached:
                chunk.embedding = cached
            else:
                texts_to_embed.append(chunk.content)
                chunk_indices.append(i)
                
        if not texts_to_embed:
            logger.debug(f"All {len(doc.chunks)} chunks found in cache.")
            return doc
            
        logger.info(f"Generating {len(texts_to_embed)} embeddings using {self.provider} ({self.model_name})...")
        
        if self.provider == "fastembed":
            new_embeddings = await self._generate_fastembed(texts_to_embed)
        elif self.provider == "openai":
            new_embeddings = await self._generate_openai(texts_to_embed)
        elif self.provider == "fake":
            new_embeddings = await self._generate_fake(texts_to_embed)
        else:
            new_embeddings = await self._generate_ollama(texts_to_embed)
            
        # Update chunks and cache
        for idx, embedding in zip(chunk_indices, new_embeddings):
            doc.chunks[idx].embedding = embedding
            await self.cache.set(doc.chunks[idx].content, self.model_name, embedding)
            
        return doc
