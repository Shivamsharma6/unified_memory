import json
import hashlib
import logging
import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)

class EmbeddingCache:
    def __init__(self, db_path: str = "embeddings_cache.db"):
        # Store cache inside the memory_watcher directory
        self.db_path = str(Path(__file__).parent.parent / db_path)

    async def init_db(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS embeddings (
                    text_hash TEXT,
                    model_name TEXT,
                    embedding TEXT,
                    PRIMARY KEY (text_hash, model_name)
                )
            ''')
            await db.commit()

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    async def get(self, text: str, model_name: str) -> list[float] | None:
        text_hash = self._hash_text(text)
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                'SELECT embedding FROM embeddings WHERE text_hash = ? AND model_name = ?',
                (text_hash, model_name)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return json.loads(row[0])
        return None

    async def set(self, text: str, model_name: str, embedding: list[float]):
        text_hash = self._hash_text(text)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                'INSERT OR REPLACE INTO embeddings (text_hash, model_name, embedding) VALUES (?, ?, ?)',
                (text_hash, model_name, json.dumps(embedding))
            )
            await db.commit()
