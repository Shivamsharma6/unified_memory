from typing import List
from models.document import Document

class VectorStore:
    async def store(self, doc: Document) -> None:
        """
        Upsert chunks into Qdrant/local storage.
        """
        pass
