import asyncio
import logging
import math
from typing import List, Any, Optional

logger = logging.getLogger(__name__)


def _sigmoid(x: float) -> float:
    try:
        return 1.0 / (1.0 + math.exp(-float(x)))
    except OverflowError:
        return 1.0 if x > 0 else 0.0


class CrossEncoderReranker:
    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._available = False
        self._initialized = False

    async def _ensure_model(self):
        if self._initialized:
            return
        self._initialized = True
        try:
            from sentence_transformers import CrossEncoder

            self._model = await asyncio.to_thread(CrossEncoder, self.model_name, max_length=512)
            self._available = True
            logger.info(f"Loaded cross-encoder model: {self.model_name}")
        except ImportError:
            logger.warning("sentence-transformers not installed. Falling back to heuristic reranking.")
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}. Using heuristic fallback.")
            self._available = False

    async def score(self, pairs: List[tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        await self._ensure_model()
        if self._available and self._model:
            raw_scores = await asyncio.to_thread(self._model.predict, pairs)
            return [_sigmoid(s) for s in raw_scores]

        # Heuristic fallback
        import re as _re

        scores = []
        for query, doc in pairs:
            q_words = set(_re.findall(r"\w+", query.lower()))
            d_words = set(_re.findall(r"\w+", doc.lower()))
            overlap = len(q_words & d_words) / max(len(q_words), 1)
            length_penalty = min(1.0, 200 / max(len(doc), 1))
            scores.append(min(1.0, max(0.0, overlap * 0.7 + length_penalty * 0.3)))
        return scores

    async def rerank(self, query: str, results: List[Any], top_k: Optional[int] = None) -> List[Any]:
        if not results:
            return results
        pairs = [(query, getattr(r, "text", "") or "") for r in results]
        scores = await self.score(pairs)
        for result, ce_score in zip(results, scores):
            original = getattr(result, "score", 0.5)
            result.score = min(1.0, max(0.0, ce_score * 0.60 + original * 0.40))
        results.sort(key=lambda r: r.score, reverse=True)
        if top_k:
            results = results[:top_k]
        return results

