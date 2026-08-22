# UAMS Intelligence Layer Architecture & Pipeline Design

**Date:** 2026-08-22  
**Status:** Approved  
**Author:** Antigravity Team  

---

## 1. Overview & Problem Statement

Unified Agent Memory System (UAMS) currently suffers from an intelligence layer that is partially a facade:
1. The 7-category `memory_types/` taxonomy, `MemoryConsolidator`, and `ImportanceScorer` are unreferenced in production code; memory records pass unvalidated type strings defaulting to `semantic`.
2. Memory consolidation never runs (no scheduler, no endpoint), its `memories_pruned` counter is provably always 0, clustering uses naive exact string keys, and results are never written back or embedded.
3. Importance scores are never used in retrieval or ranking, and novelty calculation is a static stopword ratio without awareness of vault contents.
4. Identity kernel loses all evidence and evolution history upon disk reload due to incomplete `to_payload()` serialization; versioning lives in an in-memory dictionary; and extraction/contradiction rely purely on hardcoded keywords/regexes.
5. Reflection outputs from `POST /reflect` are returned to HTTP clients and immediately discarded.
6. The `MemoryDistiller` contains a clobbering bug where summarize and promote in the same cycle wipes out the LLM summary, and importance decay compounds exponentially on itself.

This design transforms UAMS into a state-of-the-art intelligent memory system (matching Mem0, Zep/Graphiti, Letta) where memory distillation, consolidation, identity evolution, and reflection are fully wired, durable, and active in the write and retrieval paths.

---

## 2. Core Architectural Components

```
                ┌────────────────────────────────────────────────────────┐
                │                   Raw Experience Input                 │
                │        (POST /remember, Filesystem Watcher, API)        │
                └──────────────────────────┬─────────────────────────────┘
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             Write-Path Intelligence Pipeline                             │
│                                                                                          │
│  1. Taxonomy Normalizer & Validator (Canonical 7 categories + aliases)                  │
│  2. Entity & Wikilink Extractor (LLM + Regex Fallback)                                   │
│  3. Initial Importance & Novelty Scoring (Corpus-Aware vs. Active Vault)                 │
│  4. Structured Relationship Inferrer                                                    │
└──────────────────────────────────────────┬───────────────────────────────────────────────┘
                                           │
                   ┌───────────────────────┴───────────────────────┐
                   ▼                                               ▼
     ┌───────────────────────────┐                   ┌───────────────────────────┐
     │    Authoritative Vault    │                   │   Control Plane & Graph   │
     │  (Atomic Markdown Files)  │                   │ (Postgres + Qdrant Embed) │
     └─────────────┬─────────────┘                   └─────────────┬─────────────┘
                   │                                               │
                   ├───────────────────────┐                       │
                   ▼                       ▼                       ▼
     ┌───────────────────────────┐   ┌───────────────────────────┐ │
     │ Memory Consolidation      │   │ Persistent Identity       │ │
     │ (Clustering, Abstraction, │   │ Kernel                    │ │
     │ Write-Back, Prune/Archive)│   │ (Evidence, Versions, LLM) │ │
     └─────────────┬─────────────┘   └─────────────┬─────────────┘ │
                   │                               │               │
                   └───────────────────────┬───────┴───────────────┘
                                           │
                                           ▼
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                            Feedback Loops & Retrieval Layer                              │
│                                                                                          │
│  - Reflection Engine: Persists insights to vault + feeds contradiction detector         │
│  - Distiller Engine: Idempotent decay + non-clobbering summarization/promotion          │
│  - Hybrid Retrieval: Importance-weighted RRF + graph-aware + cross-encoder reranking    │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Detailed Specifications

### 3.1. Canonical Taxonomy & Validation
- **Single Source of Truth:** `MemoryCategory` in `memory_types/memory_types.py` defines canonical types: `semantic`, `episodic`, `procedural`, `identity`, `goal`, `reflection`, `relationship`.
- **Normalization Mapping:**
  - `concept` -> `semantic`
  - `daily` -> `episodic`
  - `task` / `procedure` -> `procedural`
  - `profile` -> `identity`
  - `objective` -> `goal`
  - `review` -> `reflection`
  - `dynamics` -> `relationship`
- **Validation:**
  - `models/memory_record.py` (`parse_memory`): validates and normalizes frontmatter type against `MemoryCategory` and aliases; unknown types default to `semantic` with diagnostic logging.
  - `api/routers/validation.py`: checks note types against canonical categories.

### 3.2. SOTA Write-Path Distillation
- **Direct & Watcher Ingestion:** When memories are posted to `POST /remember` or written by agents:
  - If unstructured prose is submitted, `MemoryWriter` / `LLMProvider` optionally extracts:
    - Title and summary
    - Wikilinks `[[Entity]]`
    - Inferred memory category
    - Inferred relationships (`predicate`, `target`)
    - Initial importance score
  - If LLM is offline, deterministic regex heuristics extract wikilinks and classify category.

### 3.3. Memory Consolidation & Write-Back
- **Bug Fix in Pruning Counter:** Use actual `total_pruned` count from `_reduce_redundancy` instead of evaluating `sum(len(cluster) - 1)` over 1-item clusters.
- **Clustering:** Cluster episodic memories by topic and entity overlap.
- **Persistent Write-Back:**
  - Write synthesized semantic concepts to `Concepts/Concept_<name>.md` with frontmatter `type: semantic`, `origin_memories: [...]`, and distilled lessons.
  - Mark source memories as `distilled` or move low-value memories to `Archive/` per retention policy.
  - Trigger PostgreSQL staging and Qdrant vector embedding for new/modified files.
- **Triggers:**
  - API endpoint: `POST /consolidate`.
  - Periodic & file-threshold invocation in `MemoryWatcher`.

### 3.4. Corpus-Aware Importance & Retrieval Ranking
- **Novelty Calculation:** Evaluate novelty by comparing term distributions against recent memory history or embedding distance against existing memories rather than a static 35-word stopword list.
- **Hybrid Retrieval Ranking:**
  - Pass memory importance into search results.
  - In `HybridRetrieval.search()` and `RetrievalPipeline._step6_rerank()`, modulate the final score using memory importance:
    $$Score_{final} = Score_{base} \times (1.0 + 0.2 \times Importance)$$

### 3.5. Persistent Identity Kernel & Reasoning
- **Serialization Provenance:** Update `TraitObject.to_payload()` and `IdentityProfile.to_payload()` to serialize all `evidence` items and complete `evolution_history`.
- **Durable Versioning:** Store version history in `Identity/<entity_id>_versions.json` so version counts, drift detection, and rollback survive process restarts.
- **LLM-Assisted Trait Extraction & Contradiction Resolution:**
  - Use `LLMProvider` to extract nuanced traits and evaluate contradictions between active traits.
  - Fall back cleanly to regex/keyword rules if LLM is unavailable.

### 3.6. First-Class Reflection Storage
- **Vault Persistence:** `POST /reflect` writes its structured findings to `AI/Summaries/Reflection-YYYY-MM-DD.md` with `type: reflection`.
- **Indexing:** Reflection notes are staged to Postgres and embedded in Qdrant.
- **Contradiction Feed:** Identified contradictions are routed to `ContradictionEngine` to adjust confidence and flag inconsistencies.

### 3.7. Distiller Bug Fixes
- **Non-Clobbering Execution:** When both summarize (age > 2) and promote (score >= 0.75) execute in the same cycle, ensure the updated summarized body is retained when writing the file.
- **Idempotent Decay:** Compute decay strictly as $Importance = (BaseImportance + EntityBoost) \times 0.5^{(\text{age\_days} / 30.0)}$ without re-assigning decayed score as `base_importance` in frontmatter.

---

## 4. Verification Plan

1. **Unit & Regression Tests:**
   - Run existing 186 pytest cases to ensure zero regressions.
   - Add unit tests for `to_payload()` round-trip preserving evidence and evolution history.
   - Add unit tests for persistent `IdentityVersioningEngine` across restarts.
   - Add unit tests for `MemoryConsolidator` pruning calculation and concept write-back.
   - Add unit tests for `MemoryDistiller` summary preservation during same-cycle promotion and idempotent decay.
   - Add unit tests for canonical taxonomy validation and alias normalization in `parse_memory`.
   - Add unit tests for `POST /consolidate` and `POST /reflect` vault persistence.
2. **Integration Verification:**
   - Verify full end-to-end memory lifecycle: Write raw episodic memory -> Reconcile -> Distill/Consolidate -> Query via Hybrid Retrieval -> Reflect -> Check Knowledge Graph & Identity update.
