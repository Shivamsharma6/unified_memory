# UAMS SOTA Memory System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform UAMS from a well-structured prototype into the SOTA persistent memory system for agents by wiring the identity kernel into the API, replacing all heuristic/keyword layers with LLM-powered intelligence, adding cross-encoder reranking, and exposing identity-aware retrieval.

**Architecture:** 8 major changes across 3 layers (Intelligence, API, SDK). Each task is self-contained and testable. The core philosophy: replace every `_extract_lessons`, `_generate_summary`, keyword match, and regex heuristic with real LLM calls or proper neural models. Wire the isolated identity kernel into the serving path.

**Tech Stack:** Python 3.11+, FastAPI, Qdrant, NetworkX, Pydantic 2.11+, httpx, tenacity, fastembed (BAAI/bge-small-en-v1.5), cross-encoder (sentence-transformers/ms-marco-MiniLM-L-6-v2), optional OpenAI/Ollama for LLM calls

---

## Task 1: Add LLM Provider Abstraction

The foundation for all LLM-powered intelligence. Currently everything is keyword/heuristic. This creates a configurable LLM client that all downstream components use.

**Files:**
- Create: `memory_watcher/llm/provider.py`
- Create: `memory_watcher/llm/__init__.py`
- Create: `tests/test_llm_provider.py`

- [ ] **Step 1: Write the LLM provider interface and tests**

```python
# tests/test_llm_provider.py
import pytest
from unittest.mock import AsyncMock, patch
from llm.provider import LLMProvider, LLMConfig


@pytest.mark.asyncio
async def test_llm_provider_config():
    config = LLMConfig(
        provider="ollama",
        model="llama3.2",
        base_url="http://localhost:11434",
        temperature=0.3,
        max_tokens=2048,
    )
    provider = LLMProvider(config)
    assert provider.config.model == "llama3.2"
    assert provider.config.temperature == 0.3


@pytest.mark.asyncio
async def test_llm_provider_mock_generate():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    result = await provider.generate("Summarize this text: The system uses Qdrant for vectors.")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_llm_provider_structured_output():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    result = await provider.generate_structured(
        "Extract entities from: Shivam built the UAMS system.",
        schema={"type": "object", "properties": {"entities": {"type": "array"}}},
    )
    assert isinstance(result, dict)
    assert "entities" in result


@pytest.mark.asyncio
async def test_llm_provider_batch():
    config = LLMConfig(provider="mock", model="test")
    provider = LLMProvider(config)
    results = await provider.batch_generate([
        "Summarize A",
        "Summarize B",
        "Extract lessons from C",
    ])
    assert len(results) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_llm_provider.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement the LLM provider**

```python
# memory_watcher/llm/__init__.py
from llm.provider import LLMProvider, LLMConfig

__all__ = ["LLMProvider", "LLMConfig"]
```

```python
# memory_watcher/llm/provider.py
"""
Configurable LLM Provider for UAMS intelligence layer.

Supports:
  - Ollama (local, default)
  - OpenAI-compatible APIs
  - Mock (for tests)
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    provider: str = "ollama"
    model: str = "llama3.2"
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
        # mock provider uses no client

        return self._client

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text from a prompt."""
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
        """Generate structured JSON output."""
        if self.config.provider == "mock":
            return self._mock_structured(prompt, schema)

        json_schema = json.dumps(schema)
        full_prompt = f"{prompt}\n\nRespond with valid JSON matching this schema:\n{json_schema}"

        result = await self.generate(full_prompt, system=system)

        # Try to extract JSON from the response
        try:
            # Handle markdown code blocks
            if "```json" in result:
                result = result.split("```json")[1].split("```")[0]
            elif "```" in result:
                result = result.split("```")[1].split("```")[0]
            return json.loads(result.strip())
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse LLM JSON response, returning empty")
            return {}

    async def batch_generate(
        self,
        prompts: List[str],
        system: Optional[str] = None,
    ) -> List[str]:
        """Generate responses for multiple prompts."""
        results = []
        for prompt in prompts:
            result = await self.generate(prompt, system=system)
            results.append(result)
        return results

    def _mock_generate(self, prompt: str) -> str:
        """Mock generation for testing."""
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
        """Mock structured generation for testing."""
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_llm_provider.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/llm/ tests/test_llm_provider.py
git commit -m "feat(llm): add configurable LLM provider abstraction"
```

---

## Task 2: LLM-Powered Memory Distiller

Replace the heuristic `_extract_lessons` and `_generate_summary` in `distiller.py` with real LLM calls.

**Files:**
- Modify: `memory_watcher/intelligence/distiller.py`
- Create: `tests/test_llm_distiller.py`

- [ ] **Step 1: Write failing tests for LLM distillation**

```python
# tests/test_llm_distiller.py
import pytest
import tempfile
from pathlib import Path
from intelligence.distiller import MemoryDistiller
from llm.provider import LLMConfig


@pytest.fixture
def vault_with_daily(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()
    tasks = tmp_path / "Tasks"
    tasks.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()

    # Create a sample daily note
    note = daily / "2026-06-01-Test-Work.md"
    note.write_text("""---
type: episodic
date: 2026-06-01
tags: ["#testing"]
---

# Test Work Session

Today I worked on the [[Qdrant]] integration. The [[Embedding Generator]] was producing wrong vectors.

## Error
Got a ConnectionRefused error when connecting to Qdrant on port 6333.

## Fix
Started the Qdrant container with `docker compose up -d`. Verified with health check endpoint.

## Decision
Chose to use fastembed for local embeddings instead of API calls to reduce latency.
""")
    return tmp_path


@pytest.mark.asyncio
async def test_llm_summary_generation(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(str(vault_with_daily), llm_config=config)
    daily_file = vault_with_daily / "Daily" / "2026-06-01-Test-Work.md"
    summary = await distiller._generate_summary_llm(daily_file.read_text())
    assert isinstance(summary, str)
    assert len(summary) > 20
    assert "summary" in summary.lower() or len(summary) > 50


@pytest.mark.asyncio
async def test_llm_lesson_extraction(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(str(vault_with_daily), llm_config=config)
    content = (vault_with_daily / "Daily" / "2026-06-01-Test-Work.md").read_text()
    lessons = await distiller._extract_lessons_llm(content)
    assert isinstance(lessons, list)
    assert len(lessons) > 0
    assert all(isinstance(l, str) for l in lessons)


@pytest.mark.asyncio
async def test_distill_cycle_uses_llm(vault_with_daily):
    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(str(vault_with_daily), llm_config=config)
    await distiller.distill_cycle()
    # The file should have been processed (lifecycle changed)
    daily_file = vault_with_daily / "Daily" / "2026-06-01-Test-Work.md"
    content = daily_file.read_text()
    assert "lifecycle" in content
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_llm_distiller.py -v`
Expected: FAIL (distiller doesn't accept llm_config)

- [ ] **Step 3: Implement LLM-powered distiller**

Replace the entire `distiller.py` content:

```python
# memory_watcher/intelligence/distiller.py
import logging
import os
import re
import yaml
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional
from pathlib import Path

from llm.provider import LLMProvider, LLMConfig

logger = logging.getLogger(__name__)


class MemoryDistiller:
    """
    Autonomous Memory Intelligence Engine.
    Handles the lifecycle: raw -> summarized -> distilled -> proceduralized

    Uses LLM for:
      - Summarization (replaces heuristic sentence truncation)
      - Lesson extraction (replaces keyword matching)
      - Importance assessment (replaces formula-only scoring)
    """

    def __init__(self, vault_path: str, llm_config: Optional[LLMConfig] = None):
        self.vault_path = Path(vault_path)
        self.daily_dir = self.vault_path / "Daily"
        self.concepts_dir = self.vault_path / "Concepts"
        self.procedures_dir = self.vault_path / "Tasks"
        self.archive_dir = self.vault_path / "Archive"
        self.llm = LLMProvider(llm_config)

        for d in [self.daily_dir, self.concepts_dir, self.procedures_dir, self.archive_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _parse_file(self, filepath: Path) -> Dict[str, Any]:
        """Parse frontmatter and content."""
        if not filepath.exists():
            return {}
        content = filepath.read_text(encoding="utf-8")
        match = re.match(r'^---\n(.*?)\n---\n(.*)', content, re.DOTALL | re.MULTILINE)

        if match:
            try:
                fm = yaml.safe_load(match.group(1)) or {}
                return {"frontmatter": fm, "content": match.group(2).strip(), "path": filepath}
            except yaml.YAMLError:
                pass
        return {"frontmatter": {}, "content": content, "path": filepath}

    def _write_file(self, filepath: Path, frontmatter: dict, content: str):
        """Write back to vault with frontmatter."""
        fm_str = yaml.dump(frontmatter, sort_keys=False)
        filepath.write_text(f"---\n{fm_str}---\n{content}", encoding="utf-8")

    def _calculate_importance(self, frontmatter: dict, content: str, age_days: int) -> float:
        """Score based on entities, backlinks, and age."""
        base = frontmatter.get("importance", 0.5)
        entities = len(re.findall(r'\[\[(.*?)\]\]', content))
        entity_boost = min(entities * 0.05, 0.3)
        decay = 0.5 ** (age_days / 30.0)
        score = (base + entity_boost) * decay
        return max(0.0, min(score, 1.0))

    async def _generate_summary_llm(self, content: str) -> str:
        """LLM-powered summarization."""
        system = (
            "You are a memory distillation engine. Summarize the following content "
            "into a concise, actionable 2-4 sentence summary. Focus on key facts, "
            "decisions, and outcomes. Do not include pleasantries or filler."
        )
        prompt = f"Summarize this memory note:\n\n{content[:4000]}"
        try:
            return await self.llm.generate(prompt, system=system, max_tokens=300)
        except Exception as e:
            logger.warning(f"LLM summary failed, falling back to heuristic: {e}")
            sentences = [s for s in re.split(r'(?<=[.!?])\s+', content) if s]
            if len(sentences) <= 2:
                return content
            return f"{sentences[0]} ... {sentences[-1]}"

    async def _extract_lessons_llm(self, content: str) -> List[str]:
        """LLM-powered lesson extraction."""
        system = (
            "Extract actionable lessons, procedures, or rules from this content. "
            "Return as a JSON array of strings. Each lesson should be a reusable "
            "instruction or insight that future agents can follow."
        )
        prompt = f"Extract lessons from this content:\n\n{content[:4000]}"
        try:
            result = await self.llm.generate_structured(
                prompt,
                schema={"type": "object", "properties": {"lessons": {"type": "array"}}},
                system=system,
            )
            lessons = result.get("lessons", [])
            if lessons:
                return [str(l) for l in lessons]
        except Exception as e:
            logger.warning(f"LLM lesson extraction failed, falling back to heuristic: {e}")

        # Heuristic fallback
        lessons = []
        if "error" in content.lower() or "fail" in content.lower():
            lessons.append("Identified error pattern requiring structural patch.")
        if "docker" in content.lower():
            lessons.append("Docker environments require port mapping verification.")
        if "step" in content.lower():
            lessons.append("Sequence of operations detected.")
        return lessons

    async def distill_cycle(self):
        """
        Run the autonomous distillation loop.
        Scans raw daily logs, scores them, ages them, and promotes them.
        """
        logger.info("Starting Autonomous Memory Distillation Cycle...")
        now = datetime.now()

        for file in self.daily_dir.glob("*.md"):
            if file.name == "README.md":
                continue

            doc = self._parse_file(file)
            fm = doc["frontmatter"]
            content = doc["content"]

            # Determine Age
            date_val = fm.get("date", now.strftime("%Y-%m-%d"))
            if isinstance(date_val, date) and not isinstance(date_val, datetime):
                doc_date = datetime.combine(date_val, datetime.min.time())
            elif isinstance(date_val, datetime):
                doc_date = date_val
            else:
                try:
                    doc_date = datetime.strptime(str(date_val), "%Y-%m-%d")
                except ValueError:
                    doc_date = now

            age_days = (now - doc_date).days
            state = fm.get("lifecycle", "raw")

            importance = self._calculate_importance(fm, content, age_days)
            logger.info(f"Evaluating {file.name} | State: {state} | Age: {age_days}d | Score: {importance:.2f}")

            # A. Archive low-value old memories
            if age_days > 14 and importance < 0.3 and state in ["raw", "summarized"]:
                logger.info(f"  -> Archiving {file.name} (Low value, aged)")
                new_path = self.archive_dir / file.name
                file.rename(new_path)
                fm["lifecycle"] = "archived"
                self._write_file(new_path, fm, content)
                continue

            # B. Summarize aging raw memories (LLM-powered)
            if age_days > 2 and state == "raw":
                logger.info(f"  -> LLM-Summarizing {file.name} (Aging raw memory)")
                summary = await self._generate_summary_llm(content)
                fm["lifecycle"] = "summarized"
                fm["importance"] = importance
                self._write_file(file, fm, f"# Distilled Summary\n{summary}\n\n## Raw Logs\n{content}")

            # C. Promote highly important memories to Procedural/Conceptual (LLM-powered)
            if importance >= 0.75 and state in ["raw", "summarized"]:
                logger.info(f"  -> LLM-Distilling & Promoting {file.name} to Procedural Knowledge!")

                lessons = await self._extract_lessons_llm(content)
                lessons_text = "\n".join([f"- {l}" for l in lessons])

                proc_name = f"PROC_{file.stem.replace('-', '_')}.md"
                proc_path = self.procedures_dir / proc_name

                proc_fm = {
                    "type": "procedural",
                    "lifecycle": "proceduralized",
                    "origin": f"[[{file.stem}]]",
                    "date": now.strftime("%Y-%m-%d"),
                }

                proc_content = f"# Extracted Procedure\n\n## Lessons Learned\n{lessons_text}\n\n## Context\nGenerated autonomously from [[{file.stem}]]."
                self._write_file(proc_path, proc_fm, proc_content)

                fm["lifecycle"] = "distilled"
                fm["distilled_to"] = f"[[{proc_path.stem}]]"
                self._write_file(file, fm, content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_llm_distiller.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/intelligence/distiller.py tests/test_llm_distiller.py
git commit -m "feat(distiller): replace heuristic distillation with LLM-powered intelligence"
```

---

## Task 3: LLM-Powered Summarization Endpoint

Replace the stub `/summarize` endpoint with real LLM summarization.

**Files:**
- Modify: `memory_watcher/api/main.py`
- Create: `tests/test_llm_summarize.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_summarize.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app


@pytest.mark.asyncio
async def test_summarize_returns_llm_summary():
    client = TestClient(app)
    with patch("api.main.pipeline") as mock_pipeline:
        mock_result = MagicMock()
        mock_result.results = [
            MagicMock(text="Qdrant is used for vector storage.", source_file="test.md"),
            MagicMock(text="The system uses embeddings for semantic search.", source_file="test2.md"),
        ]
        mock_result.context_tokens_used = 50
        mock_pipeline.search = AsyncMock(return_value=mock_result)

        with patch("api.main.llm") as mock_llm:
            mock_llm.generate = AsyncMock(return_value="UAMS uses Qdrant for vector storage and embeddings for semantic search across agent memories.")

            response = client.post("/summarize", json={"topic": "UAMS architecture"})
            assert response.status_code == 200
            data = response.json()
            assert "summary" in data
            assert len(data["summary"]) > 20
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd memory_watcher && python -m pytest tests/test_llm_summarize.py -v`
Expected: FAIL (no `llm` in api.main)

- [ ] **Step 3: Wire LLM into the API**

Add to `api/main.py` after the pipeline initialization:

```python
from llm.provider import LLMProvider, LLMConfig
# ... existing imports ...

llm = LLMProvider(LLMConfig(
    provider=os.getenv("UAMS_LLM_PROVIDER", "ollama"),
    model=os.getenv("UAMS_LLM_MODEL", "llama3.2"),
    base_url=os.getenv("UAMS_LLM_BASE_URL", "http://localhost:11434"),
    api_key=os.getenv("UAMS_LLM_API_KEY"),
))

@app.post("/summarize", tags=["Compute"])
async def summarize(request: SummarizeRequest):
    """Generate a semantic summary using LLM-powered distillation."""
    try:
        search_req = SearchRequest(query=request.topic, limit=5, compress=True)
        res = await pipeline.search(search_req)

        context_text = "\n\n".join([f"Source: {r.source_file}\n{r.text}" for r in res.results])

        if context_text.strip():
            system = (
                "You are a memory summarization engine. Given retrieved context about a topic, "
                "generate a concise, factual summary. Focus on key facts, relationships, and "
                "decisions. Do not hallucinate information not present in the context."
            )
            prompt = f"Topic: {request.topic}\n\nRetrieved Context:\n{context_text[:4000]}\n\nGenerate a concise summary:"
            summary = await llm.generate(prompt, system=system, max_tokens=request.max_tokens)
            return {"topic": request.topic, "summary": summary, "sources": [r.source_file for r in res.results]}

        return {"topic": request.topic, "summary": f"No relevant context found for '{request.topic}'.", "sources": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

Also add `import os` at the top of `main.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_llm_summarize.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/api/main.py tests/test_llm_summarize.py
git commit -m "feat(api): replace stub /summarize with LLM-powered summarization"
```

---

## Task 4: Cross-Encoder Reranker

Replace the simple `base_importance + graph_boost` reranking with a proper cross-encoder neural reranker. This is a key SOTA differentiator.

**Files:**
- Create: `memory_watcher/api/retrieval/reranker.py`
- Modify: `memory_watcher/api/retrieval/pipeline.py`
- Create: `tests/test_reranker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_reranker.py
import pytest
from api.retrieval.reranker import CrossEncoderReranker


@pytest.mark.asyncio
async def test_reranker_initializes():
    reranker = CrossEncoderReranker()
    assert reranker is not None


@pytest.mark.asyncio
async def test_reranker_scores_pairs():
    reranker = CrossEncoderReranker()
    pairs = [
        ("How to deploy with Docker", "Use docker compose up to start services"),
        ("How to deploy with Docker", "The weather is sunny today"),
    ]
    scores = await reranker.score(pairs)
    assert len(scores) == 2
    assert scores[0] > scores[1]  # Relevant doc should score higher


@pytest.mark.asyncio
async def test_reranker_reranks_results():
    reranker = CrossEncoderReranker()

    class MockResult:
        def __init__(self, text, score, source_file):
            self.text = text
            self.score = score
            self.source_file = source_file
            self.chunk_id = "mock"
            self.importance = 1.0
            self.entities = []

    results = [
        MockResult("The weather is nice today", 0.9, "weather.md"),
        MockResult("Docker compose starts the Qdrant container", 0.7, "docker.md"),
    ]
    query = "How do I start Qdrant?"
    reranked = await reranker.rerank(query, results)
    assert len(reranked) == 2
    # Docker result should be promoted
    assert reranked[0].source_file == "docker.md"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_reranker.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement cross-encoder reranker**

```python
# memory_watcher/api/retrieval/reranker.py
"""
Cross-Encoder Reranker for UAMS retrieval.

Uses a pretrained cross-encoder model (ms-marco-MiniLM-L-6-v2) to
re-score query-document pairs for more accurate ranking than
bi-encoder similarity alone.
"""

import logging
from typing import List, Any, Optional

logger = logging.getLogger(__name__)


class CrossEncoderReranker:
    """
    Neural reranker using sentence-transformers cross-encoder.
    Falls back to heuristic scoring if model is unavailable.
    """

    MODEL_NAME = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or self.MODEL_NAME
        self._model = None
        self._available = False

    async def _ensure_model(self):
        if self._model is not None:
            return

        try:
            from sentence_transformers import CrossEncoder
            self._model = CrossEncoder(self.model_name, max_length=512)
            self._available = True
            logger.info(f"Loaded cross-encoder model: {self.model_name}")
        except ImportError:
            logger.warning(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers. "
                "Falling back to heuristic reranking."
            )
            self._available = False
        except Exception as e:
            logger.warning(f"Failed to load cross-encoder: {e}. Using heuristic fallback.")
            self._available = False

    async def score(self, pairs: List[tuple[str, str]]) -> List[float]:
        """Score query-document pairs."""
        await self._ensure_model()

        if self._available and self._model:
            import numpy as np
            scores = self._model.predict(pairs)
            return [float(s) for s in scores]

        # Heuristic fallback: keyword overlap + length penalty
        scores = []
        for query, doc in pairs:
            q_words = set(query.lower().split())
            d_words = set(doc.lower().split())
            overlap = len(q_words & d_words) / max(len(q_words), 1)
            length_penalty = min(1.0, 200 / max(len(doc), 1))
            scores.append(overlap * 0.7 + length_penalty * 0.3)
        return scores

    async def rerank(
        self,
        query: str,
        results: List[Any],
        top_k: Optional[int] = None,
    ) -> List[Any]:
        """Rerank search results using cross-encoder scoring."""
        if not results:
            return results

        pairs = [(query, getattr(r, "text", "") or "") for r in results]
        scores = await self.score(pairs)

        # Combine cross-encoder score with existing score
        for result, ce_score in zip(results, scores):
            original = getattr(result, "score", 0.5)
            importance = getattr(result, "importance", 1.0)
            # Weighted combination: cross-encoder dominates
            result.score = ce_score * 0.6 + original * 0.2 + (importance - 1.0) * 0.2

        results.sort(key=lambda r: r.score, reverse=True)

        if top_k:
            results = results[:top_k]

        return results
```

- [ ] **Step 4: Wire reranker into the retrieval pipeline**

In `memory_watcher/api/retrieval/pipeline.py`, add the import and use it in `_step6_rerank`:

```python
# Add at top of file:
from api.retrieval.reranker import CrossEncoderReranker

# In __init__:
self.reranker = CrossEncoderReranker()

# Replace _step6_rerank entirely:
async def _step6_rerank(self, results: List[Any], query_entities: List[str], query: str = "") -> List[SearchResult]:
    """Graph-Aware + Cross-Encoder Reranking."""
    ranked = []
    for r in results:
        if isinstance(r, dict):
            score = r.get('score', 0.5)
            payload = r.get('payload', {})
            r_id = r.get('id', 'mock_id')
        else:
            score = getattr(r, 'score', 0.5)
            payload = getattr(r, 'payload', {}) or {}
            r_id = getattr(r, 'id', 'mock_id')

        result_entities = payload.get("entities", [])

        # Graph boost (existing logic)
        graph_boost = 0.0
        for q_ent in query_entities:
            q_node = next((n for n in self.kg_store.G.nodes() if str(n).lower() == q_ent.lower()), None)
            if not q_node:
                continue
            for r_ent in result_entities:
                r_node = next((n for n in self.kg_store.G.nodes() if str(n).lower() == r_ent.lower()), None)
                if not r_node:
                    continue
                if self.kg_store.G.has_edge(r_node, q_node):
                    rel = self.kg_store.G[r_node][q_node].get("relation", "")
                    if rel in ["fixes", "resolves"]:
                        graph_boost += 0.4
                    elif rel in ["caused_by"]:
                        graph_boost += 0.25
                    elif rel in ["depends_on"]:
                        graph_boost += 0.15
                    else:
                        graph_boost += 0.1

        ranked.append(SearchResult(
            chunk_id=str(r_id),
            text=payload.get("text", ""),
            score=score,
            importance=1.0 + graph_boost,
            source_file=payload.get("source_file", "unknown"),
            entities=result_entities,
        ))

    # Apply cross-encoder reranking
    ranked = await self.reranker.rerank(query, ranked)

    return ranked
```

Update `_step8_assemble` to pass the query to `_step6_rerank`:

```python
# In _step8_assemble, change:
ranked_results = await self._step6_rerank(raw_results, all_query_entities)
# To:
ranked_results = await self._step6_rerank(raw_results, all_query_entities, query=norm_query)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_reranker.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add memory_watcher/api/retrieval/reranker.py memory_watcher/api/retrieval/pipeline.py tests/test_reranker.py
git commit -m "feat(retrieval): add cross-encoder neural reranker"
```

---

## Task 5: Wire Identity Kernel into API + Retrieval

Connect the isolated identity kernel to the serving path. Add `/identity` endpoints and use identity weights in retrieval ranking.

**Files:**
- Create: `memory_watcher/api/routers/identity.py`
- Modify: `memory_watcher/api/main.py`
- Modify: `memory_watcher/api/retrieval/pipeline.py`
- Create: `tests/test_identity_api.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_identity_api.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from api.main import app


def test_identity_profile_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_profile = MagicMock()
        mock_profile.to_payload.return_value = {
            "entity_id": "test-agent",
            "entity_name": "Test Agent",
            "traits": {},
            "global_confidence": 0.5,
        }
        mock_store.get_profile.return_value = mock_profile
        response = client.post("/identity/profile", json={"entity_id": "test-agent"})
        assert response.status_code == 200


def test_identity_extract_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_store.extract_from_memories.return_value = {
            "entity_id": "test-agent",
            "traits_found": 3,
            "global_confidence": 0.6,
        }
        response = client.post("/identity/extract", json={"entity_id": "test-agent"})
        assert response.status_code == 200


def test_identity_inject_endpoint():
    client = TestClient(app)
    with patch("api.main.identity_store") as mock_store:
        mock_store.inject_identity.return_value = {
            "entity_id": "test-agent",
            "core_identity": {"top_traits": []},
        }
        response = client.post("/identity/inject", json={"entity_id": "test-agent", "query": "test"})
        assert response.status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_identity_api.py -v`
Expected: FAIL (no identity_store in api.main)

- [ ] **Step 3: Create identity store that bridges identity kernel to API**

```python
# memory_watcher/identity/store.py
"""
Identity Store - Persistence layer for identity profiles.
Loads/saves profiles from YAML files in the vault.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from identity.models import IdentityProfile, IDENTITY_DOMAINS
from identity.extraction import IdentityExtractionEngine
from identity.stability import StabilityEngine
from identity.contradiction import ContradictionEngine
from identity.weighting import IdentityWeightingEngine
from identity.versioning import IdentityVersioningEngine
from identity.injection import IdentityInjector

logger = logging.getLogger(__name__)


class IdentityStore:
    """Manages identity profiles with file-based persistence."""

    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self.identity_dir = self.vault_path / "Identity"
        self.identity_dir.mkdir(parents=True, exist_ok=True)

        self.extraction = IdentityExtractionEngine()
        self.stability = StabilityEngine()
        self.contradiction = ContradictionEngine()
        self.weighting = IdentityWeightingEngine()
        self.versioning = IdentityVersioningEngine()
        self.injection = IdentityInjector(self.weighting)

    def _profile_path(self, entity_id: str) -> Path:
        safe_id = entity_id.replace(" ", "_").replace("/", "_")
        return self.identity_dir / f"{safe_id}.json"

    def get_profile(self, entity_id: str) -> Optional[IdentityProfile]:
        path = self._profile_path(entity_id)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
            return IdentityProfile(**data)
        except Exception as e:
            logger.error(f"Failed to load identity profile: {e}")
            return None

    def save_profile(self, profile: IdentityProfile) -> None:
        path = self._profile_path(profile.entity_id)
        path.write_text(json.dumps(profile.to_payload(), indent=2))
        logger.info(f"Saved identity profile for '{profile.entity_name}' to {path}")

    def extract_from_memories(
        self,
        entity_id: str,
        entity_name: str,
        memories: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        profile = self.extraction.extract_from_memories(memories, entity_id, entity_name)

        # Run stability
        profile = self.stability.apply_stability(profile)

        # Check contradictions
        findings = self.contradiction.check_profile(profile)

        # Create version
        self.versioning.create_version(profile, trigger="extraction")

        # Save
        self.save_profile(profile)

        return {
            "entity_id": entity_id,
            "traits_found": len(profile.traits),
            "active_traits": len([t for t in profile.traits.values() if t.confidence >= 0.3]),
            "global_confidence": profile.global_confidence,
            "contradictions": len(findings),
            "version": profile.version,
        }

    def inject_identity(
        self,
        entity_id: str,
        query: str = "",
        task_type: str = "general",
    ) -> Dict[str, Any]:
        profile = self.get_profile(entity_id)
        if not profile:
            return {"error": f"No profile found for '{entity_id}'"}
        return self.injection.inject(profile, query, task_type)

    def inject_as_text(
        self,
        entity_id: str,
        query: str = "",
        task_type: str = "general",
    ) -> str:
        profile = self.get_profile(entity_id)
        if not profile:
            return ""
        return self.injection.inject_as_text(profile, query, task_type)

    def get_retrieval_boosts(self, entity_id: str, query: str) -> Dict[str, float]:
        profile = self.get_profile(entity_id)
        if not profile:
            return {}
        return self.weighting.get_retrieval_boost(profile, query)

    def list_entities(self) -> List[str]:
        return [p.stem.replace("_", " ") for p in self.identity_dir.glob("*.json")]
```

- [ ] **Step 4: Create identity router**

```python
# memory_watcher/api/routers/identity.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

router = APIRouter(prefix="/identity", tags=["Identity"])


class ProfileRequest(BaseModel):
    entity_id: str


class ExtractRequest(BaseModel):
    entity_id: str
    entity_name: str = "Unknown"
    memories: List[Dict[str, Any]] = Field(default_factory=list)


class InjectRequest(BaseModel):
    entity_id: str
    query: str = ""
    task_type: str = "general"


class UpdateStabilityRequest(BaseModel):
    entity_id: str


class ContradictionReportRequest(BaseModel):
    entity_id: str


class DriftRequest(BaseModel):
    entity_id: str
    version_a: int
    version_b: int


def _get_store():
    from api.main import identity_store
    return identity_store


@router.post("/profile")
async def get_profile(request: ProfileRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    return profile.to_payload()


@router.post("/extract")
async def extract_identity(request: ExtractRequest):
    store = _get_store()
    if not request.memories:
        return {"message": "No memories provided for extraction", "entity_id": request.entity_id}
    result = store.extract_from_memories(
        request.entity_id, request.entity_name, request.memories
    )
    return result


@router.post("/inject")
async def inject_identity(request: InjectRequest):
    store = _get_store()
    result = store.inject_identity(request.entity_id, request.query, request.task_type)
    return result


@router.post("/inject-text")
async def inject_identity_text(request: InjectRequest):
    store = _get_store()
    text = store.inject_as_text(request.entity_id, request.query, request.task_type)
    return {"entity_id": request.entity_id, "injection_text": text}


@router.post("/stability")
async def update_stability(request: UpdateStabilityRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    profile = store.stability.apply_stability(profile)
    store.save_profile(profile)
    return {"entity_id": request.entity_id, "global_confidence": profile.global_confidence}


@router.post("/contradictions")
async def contradiction_report(request: ContradictionReportRequest):
    store = _get_store()
    profile = store.get_profile(request.entity_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"No profile for '{request.entity_id}'")
    return store.contradiction.get_contradiction_report(profile)


@router.post("/drift")
async def detect_drift(request: DriftRequest):
    store = _get_store()
    return store.versioning.detect_drift(request.entity_id)


@router.post("/entities")
async def list_entities():
    store = _get_store()
    return {"entities": store.list_entities()}
```

- [ ] **Step 5: Wire identity into API main.py**

Add to `api/main.py`:

```python
# Add imports:
import os
from api.routers.identity import router as identity_router
from identity.store import IdentityStore

# After other includes:
app.include_router(identity_router)

# After pipeline initialization:
identity_store = IdentityStore(os.getenv("UAMS_VAULT_PATH", str(Path(__file__).resolve().parents[2])))

# Add Path import at top
from pathlib import Path
```

- [ ] **Step 6: Wire identity boosts into retrieval pipeline**

In `pipeline.py` `_step5_vector_retrieval`, after getting results, apply identity boosts:

```python
# Add to __init__:
self.identity_store = None  # Set after initialization

# In initialize(), add:
try:
    from identity.store import IdentityStore
    self.identity_store = IdentityStore(os.getenv("UAMS_VAULT_PATH", "."))
except Exception:
    logger.warning("Identity store unavailable for retrieval boosts")

# In _step6_rerank, after computing graph_boost, add identity boost:
identity_boost = 0.0
if self.identity_store:
    try:
        boosts = self.identity_store.get_retrieval_boosts("default", query)
        if boosts:
            identity_boost = sum(boosts.values()) * 0.1  # Modest boost
    except Exception:
        pass

# Add identity_boost to final_importance:
final_importance = base_importance + graph_boost + identity_boost
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_identity_api.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add memory_watcher/identity/store.py memory_watcher/api/routers/identity.py memory_watcher/api/main.py memory_watcher/api/retrieval/pipeline.py tests/test_identity_api.py
git commit -m "feat(identity): wire identity kernel into API and retrieval pipeline"
```

---

## Task 6: Semantic Procedure Matching

Replace keyword-only procedure matching with embedding-based semantic search.

**Files:**
- Modify: `memory_watcher/api/procedure_reader.py`
- Create: `tests/test_semantic_procedures.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_semantic_procedures.py
import pytest
from api.procedure_reader import get_relevant_procedures


def test_semantic_procedures_returns_list():
    result = get_relevant_procedures("How do I deploy to production?")
    assert isinstance(result, list)
    assert len(result) > 0


def test_semantic_procedures_ranks_relevant_higher():
    # Procedures about git should rank higher for git-related queries
    result = get_relevant_procedures("How to commit code with git")
    assert isinstance(result, list)
    # At minimum, AGENTS.md should be included
    assert any("AGENTS.md" in r for r in result)
```

- [ ] **Step 2: Run tests to verify they pass (existing behavior)**

Run: `cd memory_watcher && python -m pytest tests/test_semantic_procedures.py -v`
Expected: PASS (keyword matching still works)

- [ ] **Step 3: Upgrade procedure reader with embedding fallback**

```python
# memory_watcher/api/procedure_reader.py
import logging
import re
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

VAULT_ROOT = Path(__file__).resolve().parents[2]


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


def get_relevant_procedures(task: str, limit: int = 4) -> List[str]:
    """Get relevant procedures using keyword matching + optional embedding reranking."""
    procedures = []

    agents_file = VAULT_ROOT / "AGENTS.md"
    if agents_file.exists():
        procedures.append(f"Source: AGENTS.md\n{_excerpt(agents_file, max_chars=3600)}")

    task_terms = _terms(task)
    candidates = []
    tasks_dir = VAULT_ROOT / "Tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            candidates.append((_score(content + " " + path.stem, task_terms), path, content))

    # Sort by keyword score
    candidates.sort(key=lambda item: item[0], reverse=True)

    for score, path, content in candidates:
        if score <= 0 or len(procedures) >= limit:
            break
        procedures.append(f"Source: {path.relative_to(VAULT_ROOT)}\n{_excerpt(path)}")

    # Try embedding-based reranking for better ordering
    try:
        from embeddings.generator import EmbeddingGenerator
        import asyncio

        embedder = EmbeddingGenerator()

        # Get embeddings for task and each procedure
        async def _rerank():
            task_embedding = await _embed_text(embedder, task)
            if task_embedding is None:
                return

            scored_procs = []
            for proc_text in procedures:
                proc_embedding = await _embed_text(embedder, proc_text[:500])
                if proc_embedding is not None:
                    similarity = _cosine_similarity(task_embedding, proc_embedding)
                    scored_procs.append((similarity, proc_text))
                else:
                    scored_procs.append((0.0, proc_text))

            scored_procs.sort(key=lambda x: x[0], reverse=True)
            return [text for _, text in scored_procs[:limit]]

        # Only rerank if we have candidates beyond AGENTS.md
        if len(procedures) > 1:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # We're in an async context, skip embedding rerank
                    # to avoid blocking. Use keyword ordering.
                    pass
                else:
                    reranked = loop.run_until_complete(_rerank())
                    if reranked:
                        procedures = reranked
            except RuntimeError:
                pass  # No event loop, keep keyword ordering

    except Exception as e:
        logger.debug(f"Embedding rerank unavailable: {e}")

    return procedures


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_semantic_procedures.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/api/procedure_reader.py tests/test_semantic_procedures.py
git commit -m "feat(procedures): add embedding-based semantic procedure matching"
```

---

## Task 7: Memory Quality Scoring

Add a `/memory/quality` endpoint that rates memories by completeness, link density, and metadata richness. This is unique to UAMS and a differentiator.

**Files:**
- Create: `memory_watcher/api/routers/quality.py`
- Modify: `memory_watcher/api/main.py`
- Create: `tests/test_memory_quality.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_memory_quality.py
import pytest
from fastapi.testclient import TestClient
from api.main import app


def test_quality_endpoint_returns_scores():
    client = TestClient(app)
    response = client.post("/memory/quality", json={"path": "Daily/2026-06-01-Test.md"})
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "checks" in data


def test_quality_scoring_checks_frontmatter():
    from api.routers.quality import score_memory
    content = """---
type: episodic
date: 2026-06-01
tags: ["#test"]
---
# Test Note

This is a [[test]] note with [[wikilinks]].
"""
    result = score_memory(content)
    assert result["checks"]["has_frontmatter"] is True
    assert result["checks"]["has_type"] is True
    assert result["checks"]["has_date"] is True
    assert result["checks"]["has_tags"] is True
    assert result["checks"]["wikilink_count"] >= 2


def test_quality_scoring penalizes_bare_notes():
    from api.routers.quality import score_memory
    content = "Just a plain note with no frontmatter or links."
    result = score_memory(content)
    assert result["checks"]["has_frontmatter"] is False
    assert result["score"] < 0.5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_memory_quality.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement memory quality scoring**

```python
# memory_watcher/api/routers/quality.py
"""
Memory Quality Scoring for UAMS.

Rates memories on:
  - Frontmatter completeness (type, date, tags, entities)
  - Link density (wikilinks per paragraph)
  - Structural quality (headers, code blocks, lists)
  - Content length (not too short, not a wall of text)
"""

import re
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["Quality"])


class QualityRequest(BaseModel):
    path: str
    content: str = ""


def score_memory(content: str) -> Dict[str, Any]:
    """Score a memory note and return detailed checks."""
    checks = {}

    # Frontmatter check
    fm_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    has_frontmatter = fm_match is not None
    checks["has_frontmatter"] = has_frontmatter

    fm_content = fm_match.group(1) if has_frontmatter else ""
    checks["has_type"] = "type:" in fm_content
    checks["has_date"] = "date:" in fm_content
    checks["has_tags"] = "tags:" in fm_content

    # Entity extraction
    wikilinks = re.findall(r'\[\[(.*?)\]\]', content)
    checks["wikilink_count"] = len(wikilinks)
    checks["unique_entities"] = len(set(wikilinks))

    # Content after frontmatter
    body = content[fm_match.end():] if has_frontmatter else content

    # Structure checks
    headers = re.findall(r'^#{1,3}\s+', body, re.MULTILINE)
    checks["has_headers"] = len(headers) > 0
    checks["header_count"] = len(headers)

    code_blocks = re.findall(r'```', body)
    checks["has_code_blocks"] = len(code_blocks) >= 2

    bullet_points = re.findall(r'^[-*]\s+', body, re.MULTILINE)
    checks["has_bullet_points"] = len(bullet_points) > 0

    # Length checks
    word_count = len(body.split())
    checks["word_count"] = word_count
    checks["appropriate_length"] = 50 <= word_count <= 1500

    # Calculate score
    score = 0.0
    max_score = 10.0

    if has_frontmatter:
        score += 1.5
    if checks["has_type"]:
        score += 0.5
    if checks["has_date"]:
        score += 0.5
    if checks["has_tags"]:
        score += 0.5
    if checks["wikilink_count"] >= 1:
        score += min(1.5, checks["wikilink_count"] * 0.3)
    if checks["has_headers"]:
        score += 0.5
    if checks["has_bullet_points"]:
        score += 0.5
    if checks["has_code_blocks"]:
        score += 0.5
    if checks["appropriate_length"]:
        score += 1.0
    elif word_count < 20:
        score += 0.0  # Too short
    else:
        score += 0.3  # Too long but has content

    # Penalty for walls of text (no headers, >300 words)
    if word_count > 300 and not checks["has_headers"]:
        score -= 1.0

    score = max(0.0, min(1.0, score / max_score))

    return {
        "score": round(score, 3),
        "checks": checks,
        "grade": (
            "A" if score >= 0.8 else
            "B" if score >= 0.6 else
            "C" if score >= 0.4 else
            "D" if score >= 0.2 else
            "F"
        ),
    }


@router.post("/quality")
async def memory_quality(request: QualityRequest):
    """Score a memory note's quality and completeness."""
    if request.content:
        return score_memory(request.content)

    # Read from file
    vault_root = Path(__file__).resolve().parents[3]
    file_path = vault_root / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    result = score_memory(content)
    result["path"] = request.path
    return result


@router.post("/quality/batch")
async def batch_quality(paths: list[str]):
    """Score multiple memory notes at once."""
    results = []
    for path in paths:
        vault_root = Path(__file__).resolve().parents[3]
        file_path = vault_root / path
        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                result = score_memory(content)
                result["path"] = path
                results.append(result)
            except Exception:
                results.append({"path": path, "score": 0.0, "error": "read_failed"})
        else:
            results.append({"path": path, "score": 0.0, "error": "not_found"})
    return {"results": results}
```

- [ ] **Step 4: Wire into main.py**

Add to `api/main.py`:

```python
from api.routers.quality import router as quality_router
app.include_router(quality_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_memory_quality.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add memory_watcher/api/routers/quality.py memory_watcher/api/main.py tests/test_memory_quality.py
git commit -m "feat(quality): add memory quality scoring endpoint"
```

---

## Task 8: Identity-Aware MCP Tools

Add identity tools to the MCP server so agents can query and update identity.

**Files:**
- Modify: `uams_sdk/uams_sdk/mcp_server.py`
- Modify: `uams_sdk/uams_sdk/client.py`
- Create: `tests/test_mcp_identity.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_mcp_identity.py
import pytest
from unittest.mock import AsyncMock, patch
from uams_sdk.mcp_server import mcp


@pytest.mark.asyncio
async def test_get_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "get_identity" in tool_names


@pytest.mark.asyncio
async def test_inject_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "inject_identity" in tool_names


@pytest.mark.asyncio
async def test_extract_identity_tool_exists():
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    assert "extract_identity" in tool_names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd uams_sdk && python -m pytest tests/test_mcp_identity.py -v`
Expected: FAIL (tools don't exist)

- [ ] **Step 3: Add identity tools to MCP server**

Add to `uams_sdk/uams_sdk/mcp_server.py`:

```python
@mcp.tool()
async def get_identity(entity_id: str = "default") -> dict[str, Any]:
    """Get the identity profile for an entity (traits, confidence, version)."""
    return await _client().get_identity(entity_id=entity_id)


@mcp.tool()
async def inject_identity(
    entity_id: str = "default",
    query: str = "",
    task_type: str = "general",
) -> dict[str, Any]:
    """Inject identity context into agent reasoning for personalized responses."""
    return await _client().inject_identity(
        entity_id=entity_id, query=query, task_type=task_type
    )


@mcp.tool()
async def extract_identity(
    entity_id: str = "default",
    entity_name: str = "Agent",
    memories: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Extract identity traits from episodic memories."""
    return await _client().extract_identity(
        entity_id=entity_id,
        entity_name=entity_name,
        memories=memories or [],
    )


@mcp.tool()
async def memory_quality(path: str) -> dict[str, Any]:
    """Score a memory note's quality and completeness."""
    return await _client().memory_quality(path=path)
```

- [ ] **Step 4: Add identity methods to SDK client**

Add to `uams_sdk/uams_sdk/client.py`:

```python
async def get_identity(self, entity_id: str = "default") -> Dict[str, Any]:
    """Get identity profile."""
    return await self._request("POST", "/identity/profile", {"entity_id": entity_id}, use_cache=True)

async def inject_identity(
    self, entity_id: str = "default", query: str = "", task_type: str = "general"
) -> Dict[str, Any]:
    """Inject identity into reasoning."""
    return await self._request("POST", "/identity/inject", {
        "entity_id": entity_id, "query": query, "task_type": task_type
    }, use_cache=False)

async def extract_identity(
    self, entity_id: str = "default", entity_name: str = "Agent",
    memories: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Extract identity from memories."""
    return await self._request("POST", "/identity/extract", {
        "entity_id": entity_id, "entity_name": entity_name, "memories": memories or []
    }, use_cache=False)

async def memory_quality(self, path: str) -> Dict[str, Any]:
    """Score memory quality."""
    return await self._request("POST", "/memory/quality", {"path": path}, use_cache=True)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd uams_sdk && python -m pytest tests/test_mcp_identity.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add uams_sdk/uams_sdk/mcp_server.py uams_sdk/uams_sdk/client.py tests/test_mcp_identity.py
git commit -m "feat(mcp): add identity-aware tools to MCP server"
```

---

## Task 9: Temporal Awareness in Retrieval

Add time-based relevance scoring so recent memories are boosted. This prevents stale context from dominating retrieval.

**Files:**
- Modify: `memory_watcher/api/retrieval/pipeline.py`
- Create: `tests/test_temporal_retrieval.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_temporal_retrieval.py
import pytest
from api.retrieval.pipeline import RetrievalPipeline


def test_temporal_boost_calculates_recency():
    pipeline = RetrievalPipeline()
    from datetime import datetime, timedelta
    now = datetime.now()
    recent = (now - timedelta(days=1)).isoformat()
    old = (now - timedelta(days=90)).isoformat()
    assert pipeline._temporal_boost(recent) > pipeline._temporal_boost(old)


def test_temporal_boost_returns_zero_for_unknown():
    pipeline = RetrievalPipeline()
    assert pipeline._temporal_boost("") == 0.0
    assert pipeline._temporal_boost("not-a-date") == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_temporal_retrieval.py -v`
Expected: FAIL (method doesn't exist)

- [ ] **Step 3: Add temporal awareness to pipeline**

Add to `pipeline.py`:

```python
from datetime import datetime, timezone

# Add method to RetrievalPipeline class:
def _temporal_boost(self, date_str: str) -> float:
    """Calculate recency boost from a date string. Recent = higher boost."""
    if not date_str:
        return 0.0
    try:
        if isinstance(date_str, str):
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = date_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        days_ago = (datetime.now(timezone.utc) - dt).days
        # Exponential decay: 1.0 at 0 days, ~0.5 at 30 days, ~0.1 at 90 days
        return max(0.0, 2 ** (-days_ago / 30.0))
    except (ValueError, TypeError):
        return 0.0
```

In `_step6_rerank`, after graph_boost calculation, add temporal boost:

```python
# In _step6_rerank, after graph_boost loop:
date_str = payload.get("date", "")
temporal = self._temporal_boost(date_str)

# Update final_importance:
final_importance = base_importance + graph_boost + identity_boost + temporal
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_temporal_retrieval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/api/retrieval/pipeline.py tests/test_temporal_retrieval.py
git commit -m "feat(retrieval): add temporal awareness to boost recent memories"
```

---

## Task 10: Self-Editing Memory Endpoint

Allow agents to request memory edits or deletions. This is a key SOTA feature — agents should be able to correct their own memory.

**Files:**
- Create: `memory_watcher/api/routers/memory_edit.py`
- Modify: `memory_watcher/api/main.py`
- Create: `tests/test_memory_edit.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_memory_edit.py
import pytest
from fastapi.testclient import TestClient
from api.main import app


def test_edit_memory_endpoint():
    client = TestClient(app)
    response = client.post("/memory/edit", json={
        "path": "Daily/2026-06-01-Test.md",
        "old_text": "old content",
        "new_text": "new content",
    })
    # Should return 404 for non-existent file or success
    assert response.status_code in [200, 404]


def test_delete_memory_endpoint():
    client = TestClient(app)
    response = client.post("/memory/delete", json={
        "path": "Daily/nonexistent.md",
    })
    assert response.status_code in [200, 404]


def test_add_link_endpoint():
    client = TestClient(app)
    response = client.post("/memory/add-link", json={
        "path": "Daily/2026-06-01-Test.md",
        "entity": "NewEntity",
    })
    assert response.status_code in [200, 404]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd memory_watcher && python -m pytest tests/test_memory_edit.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement memory editing**

```python
# memory_watcher/api/routers/memory_edit.py
"""
Self-Editing Memory Endpoints.

Allows agents to correct, update, or delete their own memories.
Every edit is logged with an audit trail.
"""

import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/memory", tags=["Memory Edit"])


class EditRequest(BaseModel):
    path: str
    old_text: str
    new_text: str


class DeleteRequest(BaseModel):
    path: str
    reason: str = "agent_correction"


class AddLinkRequest(BaseModel):
    path: str
    entity: str
    context: Optional[str] = None


def _vault_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _audit_log_path() -> Path:
    root = _vault_root()
    log_dir = root / "Logs"
    log_dir.mkdir(exist_ok=True)
    return log_dir / "memory_edits.md"


def _log_edit(action: str, path: str, details: str = ""):
    log_path = _audit_log_path()
    timestamp = datetime.now().isoformat()
    entry = f"- [{timestamp}] **{action}** `{path}` {details}\n"
    with open(log_path, "a") as f:
        f.write(entry)


@router.post("/edit")
async def edit_memory(request: EditRequest):
    """Edit a specific section of a memory file."""
    file_path = _vault_root() / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    content = file_path.read_text(encoding="utf-8")
    if request.old_text not in content:
        raise HTTPException(status_code=400, detail="old_text not found in file")

    # Backup
    backup_path = file_path.with_suffix(f".backup-{datetime.now().strftime('%Y%m%d%H%M%S')}.md")
    shutil.copy2(file_path, backup_path)

    new_content = content.replace(request.old_text, request.new_text, 1)
    file_path.write_text(new_content, encoding="utf-8")

    _log_edit("EDIT", request.path, f"replaced `{request.old_text[:50]}...`")

    return {
        "status": "success",
        "path": request.path,
        "backup": str(backup_path.name),
        "message": "Memory edited successfully.",
    }


@router.post("/delete")
async def delete_memory(request: DeleteRequest):
    """Archive (soft-delete) a memory file."""
    file_path = _vault_root() / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    archive_dir = _vault_root() / "Archive"
    archive_dir.mkdir(exist_ok=True)

    archive_path = archive_dir / file_path.name
    shutil.move(str(file_path), str(archive_path))

    _log_edit("DELETE", request.path, f"reason: {request.reason}")

    return {
        "status": "success",
        "path": request.path,
        "archived_to": str(archive_path.relative_to(_vault_root())),
        "message": "Memory archived.",
    }


@router.post("/add-link")
async def add_link(request: AddLinkRequest):
    """Add a wikilink entity to a memory file."""
    file_path = _vault_root() / request.path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {request.path}")

    content = file_path.read_text(encoding="utf-8")
    link = f"[[{request.entity}]]"

    if link in content:
        return {"status": "noop", "message": f"Link {link} already exists."}

    # Add to frontmatter tags if tags section exists
    if "tags:" in content:
        # Insert entity as tag
        content = re.sub(
            r'(tags:\s*\[)',
            f'\\1"{link}", ',
            content,
            count=1,
        )

    # Also add to body as a reference
    context_line = f"\n\nReferenced: {link}" if request.context else f"\n\nSee also: {link}"
    content += context_line

    file_path.write_text(content, encoding="utf-8")

    _log_edit("ADD_LINK", request.path, f"added {link}")

    return {
        "status": "success",
        "path": request.path,
        "entity": request.entity,
        "message": f"Link {link} added.",
    }
```

- [ ] **Step 4: Wire into main.py**

Add to `api/main.py`:

```python
from api.routers.memory_edit import router as memory_edit_router
app.include_router(memory_edit_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd memory_watcher && python -m pytest tests/test_memory_edit.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add memory_watcher/api/routers/memory_edit.py memory_watcher/api/main.py tests/test_memory_edit.py
git commit -m "feat(memory): add self-editing memory endpoints with audit trail"
```

---

## Task 11: Run Full Test Suite + Type Check

Verify everything works together.

**Files:**
- None (verification only)

- [ ] **Step 1: Run all tests**

Run: `cd memory_watcher && python -m pytest tests/ -v --tb=short`
Expected: All tests PASS

- [ ] **Step 2: Check for import issues**

Run: `cd memory_watcher && python -c "from api.main import app; print('API imports OK')"`
Expected: No errors

- [ ] **Step 3: Check identity imports**

Run: `cd memory_watcher && python -c "from identity.store import IdentityStore; print('Identity store OK')"`
Expected: No errors

- [ ] **Step 4: Verify MCP server imports**

Run: `cd uams_sdk && python -c "from uams_sdk.mcp_server import mcp; print('MCP OK')"`
Expected: No errors

- [ ] **Step 5: Commit all remaining changes**

```bash
git add -A
git commit -m "chore: verify full test suite and imports"
```

---

## Task 12: Update Documentation

Update README with new SOTA features.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Add SOTA features section to README**

Add after the existing features section:

```markdown
## SOTA Intelligence Features

### LLM-Powered Distillation
Memory summarization and lesson extraction use real LLM calls (Ollama/OpenAI) instead of keyword heuristics. Configure via environment variables:
- `UAMS_LLM_PROVIDER` (ollama | openai | mock)
- `UAMS_LLM_MODEL` (default: llama3.2)
- `UAMS_LLM_BASE_URL` (default: http://localhost:11434)

### Cross-Encoder Neural Reranking
Retrieval results are reranked using `cross-encoder/ms-marco-MiniLM-L-6-v2` for more accurate relevance scoring. Falls back to heuristic if sentence-transformers is not installed.

### Identity Kernel
A 12-domain identity system that extracts traits from episodic memories, tracks stability, detects contradictions, and injects personalized context into agent reasoning.

### Memory Quality Scoring
Every memory note is scored on frontmatter completeness, link density, structural quality, and content length.

### Self-Editing Memory
Agents can correct, update, or delete their own memories with full audit trail.

### Temporal Awareness
Recent memories are boosted in retrieval to prevent stale context from dominating.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add SOTA features documentation"
```
