import asyncio
import re
from pathlib import Path
from typing import Optional

from models.memory_record import get_vault_root



def _terms(task: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9_]{3,}", task.lower())
        if term not in {"the", "and", "for", "with", "that", "this", "from"}
    }


def _score(text: str, terms: set[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term) for term in terms)


def _excerpt(path: Path, max_chars: int = 2400) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


async def _embed_text(embedder, text: str):
    """Helper to embed text safely."""
    try:
        from models.document import Chunk, ChunkMetadata
        doc = type('MockDoc', (), {'chunks': []})()
        meta = ChunkMetadata(chunk_id="proc", source_file="proc")
        doc.chunks = [Chunk(content=text, metadata=meta)]
        doc = await embedder.embed(doc)
        return doc.chunks[0].embedding
    except Exception:
        return None


def _cosine_similarity(a, b):
    """Compute cosine similarity between two vectors."""
    import numpy as np
    a = np.array(a)
    b = np.array(b)
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / max(norm, 1e-8))


def get_relevant_procedures(task: str, limit: int = 4, vault_root: Optional[Path] = None) -> list[str]:
    procedures = []
    root = get_vault_root(vault_root)

    agents_file = root / "AGENTS.md"
    if agents_file.exists():
        procedures.append(f"Source: AGENTS.md\n{_excerpt(agents_file, max_chars=3600)}")

    task_terms = _terms(task)
    candidates = []
    tasks_dir = root / "Tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            candidates.append((_score(content + " " + path.stem, task_terms), path))

    for score, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        if score <= 0 or len(procedures) >= limit:
            break
        procedures.append(f"Source: {path.relative_to(root)}\n{_excerpt(path)}")


    # Try embedding-based reranking if possible
    try:
        from embeddings.generator import EmbeddingGenerator
        embedder = EmbeddingGenerator(provider="fake")
        
        # Check if we're in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're in an async context, skip reranking to avoid blocking
            return procedures
        except RuntimeError:
            # No running loop, we can run async code
            pass
        
        # Run embedding-based reranking
        async def _rerank():
            task_embedding = await _embed_text(embedder, task)
            if task_embedding is None:
                return procedures
            
            scored_procedures = []
            for proc in procedures:
                proc_embedding = await _embed_text(embedder, proc)
                if proc_embedding is None:
                    scored_procedures.append((0.0, proc))
                else:
                    similarity = _cosine_similarity(task_embedding, proc_embedding)
                    scored_procedures.append((similarity, proc))
            
            scored_procedures.sort(key=lambda x: x[0], reverse=True)
            return [proc for _, proc in scored_procedures[:limit]]
        
        # Run the async reranking
        reranked = asyncio.run(_rerank())
        return reranked
    except Exception:
        # If anything fails, keep keyword ordering
        return procedures
