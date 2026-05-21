import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from api.models import SearchResult
from api.retrieval.compressor import ContextCompressor

def run_benchmark():
    compressor = ContextCompressor(sim_threshold=0.8)
    
    # Mock some raw retrieved chunks (noisy, redundant, long)
    raw_chunks = [
        SearchResult(
            chunk_id="1",
            score=0.9,
            importance=1.0,
            source_file="architecture.md",
            entities=["Qdrant"],
            text="Qdrant is the chosen vector database. We use it for semantic search. It is highly optimized for local Apple Silicon deployment using Docker."
        ),
        SearchResult(
            chunk_id="2",
            score=0.88,
            importance=1.0,
            source_file="architecture_v2.md",
            entities=["Qdrant", "Docker"],
            # Almost identical to chunk 1 -> Should be deduplicated
            text="Qdrant is our vector database. We utilize it for semantic search. It's optimized for local Apple Silicon via Docker deployment."
        ),
        SearchResult(
            chunk_id="3",
            score=0.85,
            importance=1.0,
            source_file="implementation.md",
            entities=["Python"],
            text="```python\ndef setup_qdrant():\n    client = QdrantClient()\n    return client\n```"
        ),
        SearchResult(
            chunk_id="4",
            score=0.82,
            importance=1.0,
            source_file="daily_log.md",
            entities=[],
            # Extremely long conversational history -> Should be hierarchically summarized
            text="I started the day by looking at the Qdrant docs. It was very interesting. The weather is nice. I think we need to ensure the batching works asynchronously. Otherwise, it might block the main thread. I had lunch. Then I wrote the Qdrant wrapper class. It uses AsyncQdrantClient."
        )
    ]
    
    pre_tokens = sum(compressor._estimate_tokens(c.text) for c in raw_chunks)
    
    print("=== CONTEXT COMPRESSION BENCHMARK ===\n")
    print(f"RAW INPUT: {len(raw_chunks)} chunks, ~{pre_tokens} tokens")
    for i, c in enumerate(raw_chunks):
        print(f"  Chunk {i+1} [{c.source_file}]: {c.text[:50]}...")
    
    print("\n--- Profile: Coding Agent ---")
    # Will prioritize code blocks and compress fluff
    coding_res = compressor.compress(list(raw_chunks), max_tokens=100, profile="coding")
    post_tokens = sum(compressor._estimate_tokens(c.text) for c in coding_res)
    print(f"COMPRESSED: {len(coding_res)} chunks, ~{post_tokens} tokens (Reduced by {100 - (post_tokens/pre_tokens*100):.1f}%)")
    for r in coding_res:
        print(f"[Score: {r.importance:.2f}] {r.text}")

    print("\n--- Profile: Research Agent ---")
    # Will prioritize entity density
    research_res = compressor.compress(list(raw_chunks), max_tokens=100, profile="research")
    post_tokens_res = sum(compressor._estimate_tokens(c.text) for c in research_res)
    print(f"COMPRESSED: {len(research_res)} chunks, ~{post_tokens_res} tokens (Reduced by {100 - (post_tokens_res/pre_tokens*100):.1f}%)")
    for r in research_res:
         print(f"[Score: {r.importance:.2f}] {r.text}")

if __name__ == "__main__":
    run_benchmark()
