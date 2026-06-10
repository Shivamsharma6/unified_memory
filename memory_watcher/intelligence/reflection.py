"""
Memory Reflection Engine.

Uses the reflection model (gemma4:12b-mlx) to self-assess memory quality,
identify gaps, and suggest improvements. Called after significant work.

Pipeline:
  New memories stored
  ↓
  Reflection: "What did we learn? What's missing?"
  ↓
  Quality assessment
  ↓
  Suggestions for follow-up
"""

import logging
from typing import Any, Dict, List, Optional

from llm.provider import LLMProvider, get_llm_config

logger = logging.getLogger(__name__)

REFLECTION_SYSTEM = (
    "You are a memory reflection engine. Given a set of recent memories, "
    "analyze them for: (1) completeness — are key facts captured? "
    "(2) consistency — do memories contradict each other? "
    "(3) gaps — what important context is missing? "
    "(4) actionability — can future agents act on these memories? "
    "Be concise and specific."
)

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "quality_score": {
            "type": "number",
            "description": "Overall quality score 0.0-1.0",
        },
        "completeness": {
            "type": "string",
            "description": "Assessment of how complete the memories are",
        },
        "gaps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Missing context or information",
        },
        "contradictions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Any contradictions found between memories",
        },
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Actionable suggestions to improve memory quality",
        },
    },
    "required": ["quality_score", "completeness", "gaps", "suggestions"],
}


class MemoryReflector:
    """
    Reflects on recent memories to assess quality and identify gaps.
    Uses the dedicated reflection model (gemma4:12b-mlx by default).
    """

    def __init__(self):
        self._llm: Optional[LLMProvider] = None

    @property
    def llm(self) -> LLMProvider:
        if self._llm is None:
            self._llm = LLMProvider(get_llm_config("reflection"))
        return self._llm

    async def reflect(self, memories: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Reflect on a set of memories and return quality assessment.

        Args:
            memories: List of memory dicts with 'content', 'source_file', etc.

        Returns:
            Dict with quality_score, completeness, gaps, contradictions, suggestions
        """
        if not memories:
            return {
                "quality_score": 0.0,
                "completeness": "No memories to reflect on",
                "gaps": [],
                "contradictions": [],
                "suggestions": ["Store some memories first"],
            }

        # Build context from memories
        memory_text = "\n\n---\n\n".join([
            f"Source: {m.get('source_file', 'unknown')}\n{m.get('content', '')[:500]}"
            for m in memories[:10]  # Limit to 10 memories
        ])

        prompt = f"Reflect on these recent memories:\n\n{memory_text[:6000]}\n\nProvide your assessment:"

        try:
            result = await self.llm.generate_structured(
                prompt,
                schema=REFLECTION_SCHEMA,
                system=REFLECTION_SYSTEM,
            )
            return result
        except Exception as e:
            logger.error(f"Reflection failed: {e}")
            return {
                "quality_score": 0.5,
                "completeness": f"Reflection failed: {e}",
                "gaps": [],
                "contradictions": [],
                "suggestions": [],
            }

    async def reflect_on_file(self, file_path: str) -> Dict[str, Any]:
        """Reflect on a single memory file."""
        from pathlib import Path
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        content = path.read_text(encoding="utf-8")
        return await self.reflect([{
            "content": content,
            "source_file": str(path.name),
        }])

    async def shutdown(self):
        if self._llm is not None:
            await self._llm.shutdown()
            self._llm = None
