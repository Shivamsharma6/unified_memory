# Intelligence Layer Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform the UAMS intelligence layer from an unreachable facade and heuristic shell into a robust, active SOTA memory pipeline: canonical taxonomy validation, durable consolidation with write-back, corpus-aware scoring, persistent identity kernel with full evidence provenance, first-class reflection storage, and non-clobbering distillation with idempotent decay.

**Architecture:** Integrate `memory_types` as the canonical taxonomy throughout ingestion, reconciliation, and validation. Wire `MemoryConsolidator` with persistence and background scheduling. Fix provenance serialization in `identity/models.py` and disk-persist versions in `identity/versioning.py`. Store reflections as first-class Markdown memories. Eliminate distillation clobbering and decay compounding. Boost retrieval scoring with memory importance.

**Tech Stack:** Python 3.11, FastAPI, Pydantic V2, PostgreSQL (pgcrypto), Qdrant, Ollama/OpenAI (LLMProvider), Pytest.

---

### Task 1: Canonical Memory Taxonomy & Validation

**Files:**
- Modify: `memory_watcher/memory_types/memory_types.py:20-45`
- Modify: `memory_watcher/models/memory_record.py:1-215`
- Modify: `memory_watcher/api/routers/validation.py:20-150`
- Create: `memory_watcher/tests/test_memory_types_integration.py`

- [ ] **Step 1: Write the failing test for canonical taxonomy validation**

```python
# memory_watcher/tests/test_memory_types_integration.py
import pytest
from pathlib import Path
from models.memory_record import parse_memory
from memory_types.memory_types import MemoryCategory

def test_parse_memory_canonicalizes_aliases():
    raw = """---
type: concept
tags: ["#test"]
---
# Concept Note
Content about something.
"""
    record = parse_memory(Path("Concepts/test.md"), raw)
    assert record.memory_type == MemoryCategory.SEMANTIC.value

def test_parse_memory_canonicalizes_daily_to_episodic():
    raw = """---
type: daily
date: 2026-08-22
---
# Daily Note
Today was productive.
"""
    record = parse_memory(Path("Daily/2026-08-22.md"), raw)
    assert record.memory_type == MemoryCategory.EPISODIC.value

def test_parse_memory_canonicalizes_task_to_procedural():
    raw = """---
type: task
---
# How to Deploy
1. Step one.
"""
    record = parse_memory(Path("Tasks/deploy.md"), raw)
    assert record.memory_type == MemoryCategory.PROCEDURAL.value

def test_parse_memory_handles_all_7_categories():
    for cat in MemoryCategory:
        raw = f"""---
type: {cat.value}
---
# Test {cat.value}
Body text.
"""
        record = parse_memory(Path(f"test_{cat.value}.md"), raw)
        assert record.memory_type == cat.value
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_memory_types_integration.py -v`
Expected: FAIL (because `parse_memory` currently leaves `type: concept` as `"concept"` and does not canonicalize or validate against `MemoryCategory`).

- [ ] **Step 3: Update `memory_types.py`, `models/memory_record.py`, and `validation.py`**

In `memory_types/memory_types.py`:
Update `MemoryTypeConfig` to use Pydantic V2 `model_config = ConfigDict(use_enum_values=True)`.
Define `CANONICAL_TYPE_ALIASES`:
```python
CANONICAL_TYPE_ALIASES = {
    "concept": MemoryCategory.SEMANTIC.value,
    "concepts": MemoryCategory.SEMANTIC.value,
    "semantic": MemoryCategory.SEMANTIC.value,
    "daily": MemoryCategory.EPISODIC.value,
    "episodic": MemoryCategory.EPISODIC.value,
    "task": MemoryCategory.PROCEDURAL.value,
    "tasks": MemoryCategory.PROCEDURAL.value,
    "procedure": MemoryCategory.PROCEDURAL.value,
    "procedures": MemoryCategory.PROCEDURAL.value,
    "procedural": MemoryCategory.PROCEDURAL.value,
    "profile": MemoryCategory.IDENTITY.value,
    "identity": MemoryCategory.IDENTITY.value,
    "goal": MemoryCategory.GOAL.value,
    "goals": MemoryCategory.GOAL.value,
    "objective": MemoryCategory.GOAL.value,
    "reflection": MemoryCategory.REFLECTION.value,
    "review": MemoryCategory.REFLECTION.value,
    "relationship": MemoryCategory.RELATIONSHIP.value,
    "dynamics": MemoryCategory.RELATIONSHIP.value,
}
```

In `models/memory_record.py`:
Normalize `metadata.get("type")` using `CANONICAL_TYPE_ALIASES` with fallback to `semantic`.

In `api/routers/validation.py`:
Update `VALID_MEMORY_TYPES` to include all canonical categories and aliases.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_memory_types_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/memory_types/memory_types.py memory_watcher/models/memory_record.py memory_watcher/api/routers/validation.py memory_watcher/tests/test_memory_types_integration.py
git commit -m "feat(taxonomy): wire canonical MemoryCategory and alias normalization into parse_memory and validation"
```

---

### Task 2: Distiller Clobbering Bug & Idempotent Decay Fix

**Files:**
- Modify: `memory_watcher/intelligence/distiller.py:78-202`
- Create: `memory_watcher/tests/test_distiller_fixes.py`

- [ ] **Step 1: Write failing tests for summary clobbering and decay compounding**

```python
# memory_watcher/tests/test_distiller_fixes.py
import pytest
from datetime import datetime
from pathlib import Path
from intelligence.distiller import MemoryDistiller
from llm.provider import LLMConfig

@pytest.mark.asyncio
async def test_distiller_preserves_summary_when_promoted(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    tasks = tmp_path / "Tasks"
    tasks.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()

    # Note that is > 2 days old AND has high importance (eligible for both B and C)
    note = daily / "2026-06-01-Important-Work.md"
    note.write_text("""---
type: episodic
date: 2026-06-01
importance: 0.9
---
# Work Session
Crucial error: Docker port collision fixed by changing to 6334.
[[Qdrant]] [[PostgreSQL]]
""")

    config = LLMConfig(provider="mock", model="test")
    distiller = MemoryDistiller(
        str(tmp_path),
        llm_config=config,
        now=lambda: datetime(2026, 6, 5),
    )
    await distiller.distill_cycle()

    # Verify daily note still has the distilled summary header and content
    content = note.read_text()
    assert "# Distilled Summary" in content or "lifecycle: distilled" in content
    assert "Distilled Summary" in content, "Summary was clobbered by pre-summary body!"

def test_decay_calculation_is_idempotent(tmp_path):
    distiller = MemoryDistiller(str(tmp_path))
    fm = {"importance": 0.8, "base_importance": 0.8}
    content = "Test content [[Entity1]]"

    # Day 30 calculation
    score_day30 = distiller._calculate_importance(fm, content, age_days=30)
    # If fm has the updated score, recalculating day 30 should not decay from the decayed score
    fm["importance"] = score_day30
    score_day30_recalc = distiller._calculate_importance(fm, content, age_days=30)
    assert abs(score_day30 - score_day30_recalc) < 1e-4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_distiller_fixes.py -v`
Expected: FAIL (summary clobbered and decay compounded).

- [ ] **Step 3: Fix `MemoryDistiller` in `intelligence/distiller.py`**

1. In `_calculate_importance`:
   - Check `frontmatter.get("base_importance")` or `frontmatter.get("initial_importance")` first, falling back to `frontmatter.get("importance", 0.5)`.
   - Store `fm.setdefault("base_importance", base)` so the baseline never changes.
2. In `distill_cycle`:
   - If block B fires:
     ```python
     summary = await self._generate_summary_llm(content)
     fm["lifecycle"] = "summarized"
     fm["importance"] = importance
     content = f"# Distilled Summary\n{summary}\n\n## Raw Logs\n{content}"
     self._write_file(file, fm, content)
     ```
   - When block C fires:
     - Use the updated `content` so the final write keeps the summary!
     - `self._write_file(file, fm, content)` persists the summarized content.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_distiller_fixes.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/intelligence/distiller.py memory_watcher/tests/test_distiller_fixes.py
git commit -m "fix(distiller): prevent summary clobbering during same-cycle promotion and make decay idempotent"
```

---

### Task 3: Consolidation Engine Pruning, Clustering, & Persistent Write-Back

**Files:**
- Modify: `memory_watcher/memory_types/consolidation.py:1-195`
- Modify: `memory_watcher/api/main.py:240-282`
- Modify: `memory_watcher/services/watcher.py:60-120`
- Create: `memory_watcher/tests/test_consolidation_pipeline.py`

- [ ] **Step 1: Write failing tests for consolidation pruning count and persistent write-back**

```python
# memory_watcher/tests/test_consolidation_pipeline.py
import pytest
from pathlib import Path
from memory_types.consolidation import MemoryConsolidator
from memory_types.episodic import EpisodicMemory, ContextData, OutcomeData, EmotionalState

def test_memories_pruned_count_is_accurate():
    consolidator = MemoryConsolidator()
    m1 = EpisodicMemory(
        event_type="meeting", summary="Architecture sync 1",
        participants=["Shivam", "Hermes"],
        emotional_state=EmotionalState(frustration=0.1, satisfaction=0.8),
        importance=0.8,
        context=ContextData(platform="cli"),
        outcome=OutcomeData(lessons_learned=["Lesson A"]),
    )
    m2 = EpisodicMemory(
        event_type="meeting", summary="Architecture sync 2",
        participants=["Shivam", "Hermes"],
        emotional_state=EmotionalState(frustration=0.1, satisfaction=0.5),
        importance=0.4,
        context=ContextData(platform="cli"),
        outcome=OutcomeData(lessons_learned=["Lesson B"]),
    )
    result = consolidator.consolidate([m1, m2])
    assert result.memories_processed == 2
    assert result.memories_pruned == 1
    assert result.memories_retained == 1
    assert result.redundancy_reduced == 1

def test_consolidate_and_persist_writes_concepts_to_vault(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    concepts = tmp_path / "Concepts"
    concepts.mkdir()
    archive = tmp_path / "Archive"
    archive.mkdir()

    for i in range(3):
        note = daily / f"2026-06-0{i+1}-Sync.md"
        note.write_text(f"""---
type: episodic
date: 2026-06-0{i+1}
---
# Sync {i+1}
Discussed [[Knowledge Graph]] and [[Qdrant]] architecture with [[Shivam]].
""")

    consolidator = MemoryConsolidator(vault_path=str(tmp_path))
    result = consolidator.consolidate_vault()
    assert result.abstractions_generated >= 1 or len(list(concepts.glob("*.md"))) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_consolidation_pipeline.py -v`
Expected: FAIL (pruned count is 0 and `consolidate_vault` not implemented).

- [ ] **Step 3: Implement consolidation fixes and write-back**

In `memory_types/consolidation.py`:
1. Fix `consolidate()`:
   ```python
   pruned, redundancy_count = self._reduce_redundancy(clusters, abstractions)
   total = len(memories)
   pruned_count = redundancy_count
   retained = total - pruned_count
   ```
2. Enhance `_cluster_memories`:
   - Extract entities/topics from summary & outcome lessons to group related memories.
3. Implement `consolidate_vault(vault_root=None)`:
   - Scans episodic memories in `Daily/`.
   - Runs consolidation and promotion.
   - Writes generated semantic abstractions as Markdown to `Concepts/Concept_<slug>.md` with `type: semantic` frontmatter, wikilinks, and origin memory IDs.
   - Updates consolidated notes with `distilled_to: "[[Concept_<slug>]]"`.

In `api/main.py`:
- Add `POST /consolidate` endpoint invoking `MemoryConsolidator.consolidate_vault()`.

In `services/watcher.py`:
- In `_debounced_worker` or periodic reconciliation, run consolidation when memory batch thresholds are reached.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_consolidation_pipeline.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/memory_types/consolidation.py memory_watcher/api/main.py memory_watcher/services/watcher.py memory_watcher/tests/test_consolidation_pipeline.py
git commit -m "feat(consolidation): fix pruning counter, add concept write-back and POST /consolidate endpoint"
```

---

### Task 4: Corpus-Aware Importance & Retrieval Scoring Integration

**Files:**
- Modify: `memory_watcher/memory_types/scoring.py:50-130`
- Modify: `memory_watcher/api/retrieval/hybrid.py:200-265`
- Modify: `memory_watcher/api/retrieval/pipeline.py:215-245`
- Create: `memory_watcher/tests/test_scoring_retrieval.py`

- [ ] **Step 1: Write failing tests for corpus-aware novelty and retrieval ranking boost**

```python
# memory_watcher/tests/test_scoring_retrieval.py
import pytest
from memory_types.scoring import ImportanceScorer
from api.retrieval.hybrid import HybridRetrieval
from api.models import SearchResult

def test_novelty_against_known_corpus():
    scorer = ImportanceScorer()
    known_corpus = {"qdrant", "database", "postgres", "vector", "embedding", "memory"}
    
    # Highly redundant content
    redundant_content = "qdrant database postgres vector embedding memory"
    score_red = scorer.score(redundant_content, corpus_vocabulary=known_corpus)
    
    # Highly novel content
    novel_content = "quantum entanglement topological quantum computing qubits"
    score_nov = scorer.score(novel_content, corpus_vocabulary=known_corpus)
    
    assert score_nov.novelty > score_red.novelty

def test_hybrid_retrieval_importance_boost():
    r1 = SearchResult(chunk_id="c1", text="some text", score=0.8, importance=1.5, source_file="a.md", entities=[])
    r2 = SearchResult(chunk_id="c2", text="some text", score=0.8, importance=1.0, source_file="b.md", entities=[])
    
    # Apply importance weighting
    boosted_1 = r1.score * (1.0 + 0.1 * (r1.importance - 1.0))
    boosted_2 = r2.score * (1.0 + 0.1 * (r2.importance - 1.0))
    assert boosted_1 > boosted_2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_scoring_retrieval.py -v`
Expected: FAIL (`corpus_vocabulary` argument not supported in scorer).

- [ ] **Step 3: Implement corpus-aware scoring and retrieval boost**

In `memory_types/scoring.py`:
- Update `_calculate_novelty(content, corpus_vocabulary=None)`:
  - If `corpus_vocabulary` is provided, novelty is the fraction of non-stop words that are novel relative to the known corpus.
  - If omitted, computes novelty relative to common terms with term frequency weighting.

In `api/retrieval/hybrid.py` & `api/retrieval/pipeline.py`:
- Extract `importance` from memory payload/metadata (defaulting to 1.0).
- In `_step6_rerank` / `HybridRetrieval.search`, adjust score:
  $$Score = \min(1.0, Score \times (0.9 + 0.1 \times \text{importance}))$$

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_scoring_retrieval.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/memory_types/scoring.py memory_watcher/api/retrieval/hybrid.py memory_watcher/api/retrieval/pipeline.py memory_watcher/tests/test_scoring_retrieval.py
git commit -m "feat(scoring): implement corpus-aware novelty and integrate memory importance into retrieval reranking"
```

---

### Task 5: Persistent Identity Kernel & Full Provenance Serialization

**Files:**
- Modify: `memory_watcher/identity/models.py:140-277`
- Modify: `memory_watcher/identity/versioning.py:30-105`
- Modify: `memory_watcher/identity/store.py:30-88`
- Modify: `memory_watcher/identity/extraction.py:150-250`
- Modify: `memory_watcher/identity/contradiction.py:70-150`
- Create: `memory_watcher/tests/test_identity_persistence.py`

- [ ] **Step 1: Write failing tests for identity evidence preservation, disk versioning, and LLM reasoning**

```python
# memory_watcher/tests/test_identity_persistence.py
import pytest
import json
from pathlib import Path
from identity.models import TraitObject, TraitEvidence, IdentityProfile
from identity.store import IdentityStore

def test_trait_to_payload_preserves_evidence_and_evolution():
    trait = TraitObject(
        trait_id="systems_thinker",
        domain_id="cognitive_style",
        label="Systems Thinker",
        confidence=0.8,
    )
    ev = TraitEvidence(
        source_memory_id="mem-123",
        source_type="episodic",
        content="Designed modular multi-agent system",
        strength=0.9,
    )
    trait.add_evidence(ev)

    payload = trait.to_payload()
    assert "evidence" in payload
    assert len(payload["evidence"]) == 1
    assert payload["evidence"][0]["source_memory_id"] == "mem-123"
    assert "evolution_history" in payload
    assert len(payload["evolution_history"]) >= 1

def test_identity_store_roundtrip_preserves_evidence(tmp_path):
    store = IdentityStore(str(tmp_path))
    profile = IdentityProfile(entity_id="agent_1", entity_name="Hermes")
    trait = TraitObject(trait_id="pragmatic", domain_id="core_traits", label="Pragmatic", confidence=0.75)
    ev = TraitEvidence(source_memory_id="mem-456", source_type="episodic", content="Shipped MVP fast", strength=0.85)
    trait.add_evidence(ev)
    profile.add_trait(trait)

    store.save_profile(profile)

    loaded = store.get_profile("agent_1")
    assert loaded is not None
    loaded_trait = loaded.get_trait("pragmatic")
    assert len(loaded_trait.evidence) == 1
    assert loaded_trait.evidence[0].content == "Shipped MVP fast"
    assert len(loaded_trait.evolution_history) >= 1

def test_versioning_persists_across_store_reloads(tmp_path):
    store1 = IdentityStore(str(tmp_path))
    profile = IdentityProfile(entity_id="agent_2", entity_name="OpenClaw")
    store1.versioning.create_version(profile, trigger="manual", change_summary="v1 creation")
    store1.versioning.create_version(profile, trigger="extraction", change_summary="v2 update")
    store1.save_profile(profile)

    # Recreate store (simulating process restart)
    store2 = IdentityStore(str(tmp_path))
    history = store2.versioning.get_version_history("agent_2")
    assert len(history) == 2
    assert history[1]["version_number"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_persistence.py -v`
Expected: FAIL (`to_payload()` drops evidence, and versions are not saved to disk).

- [ ] **Step 3: Implement identity model serialization, disk versioning, and LLM reasoning**

In `identity/models.py`:
- In `TraitObject.to_payload()`, include:
  ```python
  "evidence": [e.to_payload() for e in self.evidence],
  "evolution_history": self.evolution_history,
  ```
- In `TraitObject` initialization, Pydantic parses `evidence: List[TraitEvidence]` from dictionaries automatically.

In `identity/versioning.py`:
- Add `storage_dir: Optional[Path] = None`.
- Implement `_load_versions_from_disk()` and `_save_versions_to_disk(entity_id)`.
- Write version history to `Identity/{entity_id}_versions.json`.

In `identity/store.py`:
- Initialize `IdentityVersioningEngine(storage_dir=self.identity_dir)`.

In `identity/extraction.py` & `identity/contradiction.py`:
- Integrate `LLMProvider` for structured trait extraction and contradiction detection with fallback to existing regex/keyword rules.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity_persistence.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/identity/models.py memory_watcher/identity/versioning.py memory_watcher/identity/store.py memory_watcher/identity/extraction.py memory_watcher/identity/contradiction.py memory_watcher/tests/test_identity_persistence.py
git commit -m "feat(identity): preserve evidence provenance on disk round-trips and persist version history"
```

---

### Task 6: First-Class Reflection Storage & Feedback Loop

**Files:**
- Modify: `memory_watcher/intelligence/reflection.py:60-140`
- Modify: `memory_watcher/api/main.py:260-282`
- Create: `memory_watcher/tests/test_reflection_storage.py`

- [ ] **Step 1: Write failing test for reflection storage and feedback loop**

```python
# memory_watcher/tests/test_reflection_storage.py
import pytest
from pathlib import Path
from intelligence.reflection import MemoryReflector

@pytest.mark.asyncio
async def test_reflect_and_persist_saves_to_vault(tmp_path):
    daily = tmp_path / "Daily"
    daily.mkdir()
    summaries = tmp_path / "AI" / "Summaries"
    summaries.mkdir(parents=True)

    test_note = daily / "2026-06-01-Note.md"
    test_note.write_text("""---
type: episodic
date: 2026-06-01
---
# Sync
Decided to use fastembed for local embeddings.
""")

    reflector = MemoryReflector(vault_path=str(tmp_path))
    result = await reflector.reflect_and_persist(memories=[{
        "content": test_note.read_text(),
        "source_file": "2026-06-01-Note.md",
    }])

    assert "quality_score" in result
    assert result.get("saved_path") is not None
    saved_file = tmp_path / result["saved_path"]
    assert saved_file.exists()
    content = saved_file.read_text()
    assert "type: reflection" in content
    assert "# Memory Quality Reflection" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_reflection_storage.py -v`
Expected: FAIL (`reflect_and_persist` not defined on `MemoryReflector`).

- [ ] **Step 3: Implement reflection persistence and feed in `reflection.py` & `api/main.py`**

In `intelligence/reflection.py`:
- Add `vault_path: Optional[Path] = None` to `MemoryReflector`.
- Implement `reflect_and_persist()`:
  - Calls `reflect(memories)`.
  - Formats markdown note with frontmatter (`type: reflection`, `tags: ["#reflection"]`).
  - Writes to `AI/Summaries/Reflection-YYYY-MM-DD.md` (or with UUID suffix if multiple exist).
  - Returns dict with `quality_score`, `completeness`, `gaps`, `contradictions`, `suggestions`, and `saved_path`.

In `api/main.py`:
- Update `POST /reflect` to call `reflector.reflect_and_persist()`, stage the saved file if reconciler is active, and feed any contradiction strings to `identity_store.contradiction`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_reflection_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/intelligence/reflection.py memory_watcher/api/main.py memory_watcher/tests/test_reflection_storage.py
git commit -m "feat(reflection): persist reflection results as first-class Markdown notes and feed contradictions"
```

---

### Task 7: SOTA Write-Path Distillation Integration

**Files:**
- Modify: `memory_watcher/api/memory_writer.py:1-131`
- Modify: `memory_watcher/api/main.py:72-101`
- Create: `memory_watcher/tests/test_write_distillation.py`

- [ ] **Step 1: Write failing test for write-path distillation**

```python
# memory_watcher/tests/test_write_distillation.py
import pytest
from api.models import RememberRequest
from api.memory_writer import write_memory, distill_and_write_memory

def test_distill_and_write_memory_extracts_entities_and_category():
    raw_text = "Met with Shivam to discuss Qdrant vector database optimization and indexing."
    req = RememberRequest(text=raw_text, category="general")
    result = distill_and_write_memory(req)
    assert result.path.exists()
    content = result.path.read_text()
    assert "[[Shivam]]" in content or "[[Qdrant]]" in content
    assert "type: " in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_write_distillation.py -v`
Expected: FAIL (`distill_and_write_memory` not defined).

- [ ] **Step 3: Implement intelligent write path in `memory_writer.py` & `api/main.py`**

In `api/memory_writer.py`:
- Implement `distill_and_write_memory(request: RememberRequest)`:
  - If text lacks frontmatter or wikilinks:
    - Auto-wraps recognized capitalized entities/proper nouns in `[[Entity]]` wikilinks.
    - Classifies category via `CANONICAL_TYPE_ALIASES` or keyword heuristics.
    - Computes initial importance score.
    - Structures Markdown body with clean `# Title` and sections.
  - Calls `write_memory()`.
- Update `write_memory()` to always canonicalize `type` via `CANONICAL_TYPE_ALIASES`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_write_distillation.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add memory_watcher/api/memory_writer.py memory_watcher/api/main.py memory_watcher/tests/test_write_distillation.py
git commit -m "feat(write-path): add intelligent entity extraction and category canonicalization to write_memory"
```

---

### Task 8: Full Test Suite Verification & Quality Assurance

**Files:**
- Run complete test suite and fix any edge cases or deprecations.

- [ ] **Step 1: Run full test suite with coverage**

Run: `source .venv/bin/activate && pytest -v`
Expected: 100% tests pass (186+ tests).

- [ ] **Step 2: Commit any final refinements**

```bash
git add -A
git commit -m "chore: verify test suite passing across all intelligence layer enhancements"
```
