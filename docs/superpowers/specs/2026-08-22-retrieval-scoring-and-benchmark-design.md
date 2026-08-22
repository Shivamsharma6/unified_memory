# Architecture Design: Retrieval Scoring Calibration, Async Cross-Encoder, Provenance-Safe Compression, and Realistic Evaluation Benchmark

**Date**: 2026-08-22
**Author**: Antigravity (Pair Programming with Shivam Sharma)
**Status**: Approved

---

## 1. Problem Statement
The UAMS retrieval pipeline has correct high-level stages, but numerical flaws defeat it in production:
1. **Broken Default Thresholding**: `min_score=0.7` combined with artificial `1/rank` dominance drops rank-2+ items (~0.62), limiting results to 1–2 hits regardless of `limit`.
2. **Uncalibrated Blocking Cross-Encoder**: ms-marco cross-encoder logits ($-11 \dots +11$) are clipped to $[0, 1]$ without sigmoid, collapsing all scores to 1.0 or 0.0. Inference runs synchronously on the main `asyncio` event loop.
3. **Double-Counted Rank Signal**: 55% weight on raw `1/rank` creates an artificial 2x cliff between rank 1 and rank 2.
4. **Destructive Compressor**: `ContextCompressor` overrides reranker scores with arbitrary heuristics, drops `evidence_ids` during deduplication, and aborts greedy token packing on the first oversized chunk.
5. **Missing Signals & Query Asymmetry**: Missing asymmetric embedding query prefix for `mxbai-embed-large`, graph expansion only boosts already-retrieved chunks without pulling graph-connected candidate documents, and tags are unfilterable.
6. **Illusionary Evaluation Gate**: 11 of 16 queries target the same file with binary hit@1/hit@5 and `min_score=0.0`, masking production defects.

---

## 2. Technical Architecture & Solutions

```
                                  ┌───────────────────────────┐
                                  │      Search Request       │
                                  │ (query, tags, min_score)  │
                                  └─────────────┬─────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │               Query Prefix & Expansion                  │
                   │  - Asymmetric Prefix: "Represent this sentence..."      │
                   │  - Graph-connected candidate entity/document injection  │
                   └────────────────────────────┬────────────────────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     ▼                                                     ▼
       ┌───────────────────────────┐                         ┌───────────────────────────┐
       │   Lexical FTS (Postgres)  │                         │    Dense Vector (Qdrant)  │
       │   - Tags filter           │                         │    - Tags & status filter │
       │   - Normalized BM25 rank  │                         │    - Cosine similarity    │
       └─────────────┬─────────────┘                         └─────────────┬─────────────┘
                     │                                                     │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │             Calibrated Reciprocal Rank Fusion           │
                   │  - Balanced RRF: 1 / (60 + rank)                        │
                   │  - Combined with true semantic similarity               │
                   │  - No artificial 1/rank cliff                           │
                   └────────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │           Non-Blocking Sigmoid Cross-Encoder            │
                   │  - asyncio.to_thread worker                             │
                   │  - Sigmoid calibration: 1 / (1 + exp(-logit))           │
                   │  - Linear interpolation with hybrid fusion score        │
                   └────────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │           Provenance-Safe Context Compressor            │
                   │  - Preserves cross-encoder ranking order                │
                   │  - Aggregates evidence_ids across deduped chunks        │
                   │  - Greedy knapsack token packing                        │
                   └────────────────────────────┬────────────────────────────┘
                                                │
                                                ▼
                   ┌─────────────────────────────────────────────────────────┐
                   │         Realistic Graded Multi-Domain Benchmark         │
                   │  - Multi-topic queries across specs, AGENTS.md, daily   │
                   │  - Measures MRR, Precision@k, Recall@k, NDCG@k         │
                   └─────────────────────────────────────────────────────────┘
```

---

## 3. Subsystem Detailed Changes

### Component 1: Calibrated Hybrid Fusion Scoring & `min_score`
- In `api/models.py`: Set `min_score: float = 0.0` as default (or allow caller-controlled filtering without forced drop of relevant rank 2-5 items).
- In `api/retrieval/hybrid.py`:
  - Calculate `base_score = 0.40 * rrf_normalized + 0.35 * semantic_score + 0.25 * lexical_score`.
  - Eliminate the standalone `1/rank` term which double-counted RRF.

### Component 2: Async Non-Blocking Sigmoid Cross-Encoder
- In `api/retrieval/reranker.py`:
  - Wrap model inference in `await asyncio.to_thread(self._model.predict, pairs)`.
  - Apply logistic sigmoid `1.0 / (1.0 + math.exp(-float(raw_logit)))` to convert ms-marco logits into calibrated $(0, 1)$ probabilities.
  - Blend with hybrid score: `result.score = min(1.0, 0.60 * sigmoid_ce + 0.40 * hybrid_score)`.

### Component 3: Provenance-Preserving Context Compressor
- In `api/retrieval/compressor.py`:
  - Preserve the reranker's sort order; do not override `importance` with heuristic scores.
  - In `_semantic_deduplication`: merge `evidence_ids = list(dict.fromkeys(existing.evidence_ids + res.evidence_ids))` and append compression notes.
  - In token packing: continue evaluating remaining items in greedy knapsack fashion instead of hard-breaking on the first oversized chunk.

### Component 4: Asymmetric Embedding Query Prefix & Graph Candidate Injection
- In `models/embeddings.py` / `api/retrieval/hybrid.py`:
  - Prepend `"Represent this sentence for searching relevant passages: "` to queries when using `mxbai-embed-large`.
  - Inject graph-expanded document revisions into the candidate pool so graph-only reachable knowledge can be retrieved.
  - Add `tags: List[str]` to `SearchRequest` and pass down to FTS and vector filter payloads.

### Component 5: Realistic Graded Multi-Domain Benchmark
- In `tests/fixtures/retrieval_golden.json`:
  - Include 25+ diverse queries spanning architecture specs, AGENTS.md rules, procedures, concepts, identities, and daily logs.
  - Test retrieval with `compress=True` and `compress=False`.
  - Compute MRR, Hit@1, Hit@5, and NDCG.
