from typing import List
from models.document import Document

class EmbeddingGenerator:
    async def embed(self, doc: Document) -> Document:
        """
        Generate embeddings for all chunks in a document.
        """
        for chunk in doc.chunks:
            # Placeholder for actual API/local model call (e.g., local fastembed or OpenAI)
            chunk.embedding = [0.0] * 384 
        return doc
