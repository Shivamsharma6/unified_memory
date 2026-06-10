"""
Configurable LLM Provider for UAMS intelligence layer.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    provider: str = "ollama"
    model: str = "gemma4:12b-mlx"
    base_url: str = "http://localhost:11434"
    api_key: Optional[str] = None
    temperature: float = 0.3
    max_tokens: int = 2048
    timeout: float = 60.0


class LLMProvider:
    """Unified LLM provider with fallback to mock for testing."""

    def __init__(self, config: Optional[LLMConfig] = None):
        self.config = config or LLMConfig()
        self._client = None

    async def _get_client(self):
        if self._client is not None:
            return self._client

        if self.config.provider == "ollama":
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                timeout=self.config.timeout,
            )
        elif self.config.provider == "openai":
            import httpx
            self._client = httpx.AsyncClient(
                base_url="https://api.openai.com/v1",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                timeout=self.config.timeout,
            )

        return self._client

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        if self.config.provider == "mock":
            return self._mock_generate(prompt)

        client = await self._get_client()
        temp = temperature if temperature is not None else self.config.temperature
        tokens = max_tokens if max_tokens is not None else self.config.max_tokens

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        if self.config.provider == "ollama":
            resp = await client.post(
                "/api/chat",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temp, "num_predict": tokens},
                },
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

        elif self.config.provider == "openai":
            resp = await client.post(
                "/chat/completions",
                json={
                    "model": self.config.model,
                    "messages": messages,
                    "temperature": temp,
                    "max_tokens": tokens,
                },
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]

        raise ValueError(f"Unknown provider: {self.config.provider}")

    async def generate_structured(
        self,
        prompt: str,
        schema: Dict[str, Any],
        system: Optional[str] = None,
    ) -> Dict[str, Any]:
        if self.config.provider == "mock":
            return self._mock_structured(prompt, schema)

        json_schema = json.dumps(schema)
        full_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json_schema}"
        result = await self.generate(full_prompt, system=system)

        try:
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            return json.loads(result.strip())
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM JSON response")
            return {}

    async def batch_generate(
        self,
        prompts: List[str],
        system: Optional[str] = None,
    ) -> List[str]:
        results = []
        for prompt in prompts:
            result = await self.generate(prompt, system=system)
            results.append(result)
        return results

    def _mock_generate(self, prompt: str) -> str:
        lower = prompt.lower()
        if "summarize" in lower or "summary" in lower:
            return "This is a generated summary of the provided content. The system processes information through a multi-stage pipeline involving embedding, storage, and retrieval."
        if "extract" in lower and "lesson" in lower:
            return "1. Use environment variables for configuration\n2. Verify port mappings before deploying\n3. Run tests before committing changes"
        if "extract" in lower and "entit" in lower:
            return json.dumps({"entities": [{"name": "UAMS", "type": "system"}, {"name": "Qdrant", "type": "technology"}]})
        if "distill" in lower:
            return "Key insight: The memory system uses a hybrid approach combining vector similarity with knowledge graph traversal for context-aware retrieval."
        return "Generated response based on the provided context and instructions."

    def _mock_structured(self, prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        props = schema.get("properties", {})
        result = {}
        for key, prop_schema in props.items():
            if prop_schema.get("type") == "array":
                result[key] = ["item1", "item2"]
            elif prop_schema.get("type") == "string":
                result[key] = "generated_value"
            elif prop_schema.get("type") == "number":
                result[key] = 0.5
            elif prop_schema.get("type") == "boolean":
                result[key] = True
            else:
                result[key] = {}
        return result