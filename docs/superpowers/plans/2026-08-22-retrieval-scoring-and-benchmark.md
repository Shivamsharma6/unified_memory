# Implementation Plan: Retrieval Scoring Calibration, Async Cross-Encoder, Compressor, and Benchmark

**Goal**: Fix the numerical, latency, compression, and evaluation defects in the UAMS retrieval pipeline.

---

## Tasks

### Task 1: Calibrated Hybrid Fusion Scoring & `min_score` Default
- **Files**:
  - `memory_watcher/api/models.py`
  - `memory_watcher/api/retrieval/hybrid.py`
  - `memory_watcher/tests/test_hybrid_scoring_calibration.py`
- **Changes**:
  - Set default `min_score: float = 0.0` in `SearchRequest`.
  - In `HybridRetrieval.search()`, remove double-counted `1/rank` term and balance RRF + raw semantic cosine + lexical scores.

### Task 2: Async Non-Blocking Sigmoid Cross-Encoder Reranker
- **Files**:
  - `memory_watcher/api/retrieval/reranker.py`
  - `memory_watcher/api/retrieval/hybrid.py`
  - `memory_watcher/tests/test_cross_encoder_calibration.py`
- **Changes**:
  - Run model inference with `await asyncio.to_thread(self._model.predict, pairs)`.
  - Apply logistic sigmoid `1.0 / (1.0 + math.exp(-logit))` on ms-marco logits.
  - Linearly interpolate sigmoid score with fusion score.

### Task 3: Provenance-Safe, Rank-Preserving Context Compressor
- **Files**:
  - `memory_watcher/api/retrieval/compressor.py`
  - `memory_watcher/tests/test_compressor_provenance.py`
- **Changes**:
  - Preserve the reranked ordering; remove importance re-sorting.
  - Merge `evidence_ids` in `_semantic_deduplication`.
  - Greedy knapsack token packing that continues inspecting subsequent chunks.

### Task 4: Asymmetric Query Prefix, Tag Filtering & Graph Candidate Injection
- **Files**:
  - `memory_watcher/api/models.py`
  - `memory_watcher/api/retrieval/hybrid.py`
  - `memory_watcher/tests/test_query_prefix_and_tags.py`
- **Changes**:
  - Prepend `Represent this sentence for searching relevant passages: ` to query embedding for asymmetric models (`mxbai-embed-large`).
  - Add `tags: List[str]` to `SearchRequest` and pass into Qdrant payload filters and Postgres FTS.
  - Incorporate graph-expanded entities into candidate search.

### Task 5: Multi-Domain Graded Retrieval Benchmark Suite
- **Files**:
  - `memory_watcher/tests/fixtures/retrieval_golden.json`
  - `memory_watcher/tests/test_retrieval_evaluation.py`
- **Changes**:
  - Expand `retrieval_golden.json` with 25+ diverse multi-domain queries across specs, AGENTS.md, daily logs, and tasks.
  - Measure Hit@1, Hit@5, MRR, and NDCG with compression active and inactive.

### Task 6: Full Test Suite Verification & Quality Assurance
- Run `pytest memory_watcher/tests/ -v`.
- Ensure 0 failures and 0 regressions.
