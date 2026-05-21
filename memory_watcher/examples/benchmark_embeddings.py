import asyncio
import sys
import time
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from embeddings.generator import EmbeddingGenerator
from embeddings.utils import cosine_similarity
from models.document import Document, Chunk, ChunkMetadata

async def run_benchmark():
    print("--- Embedding Engine Benchmark & Comparison ---")
    
    sentences = [
        "The unified memory system uses Obsidian for markdown storage.",
        "Qdrant is utilized as the primary vector database for semantic search.",
        "Apple Silicon provides excellent hardware acceleration for machine learning models.",
        "The weather in San Francisco is quite foggy today." # Unrelated sentence for cosine similarity comparison
    ]
    
    # Create a mock document
    doc = Document(path="test.md", raw_content="mock")
    for i, s in enumerate(sentences):
        meta = ChunkMetadata(chunk_id=str(i), source_file="test.md")
        doc.chunks.append(Chunk(content=s, metadata=meta))

    # Test fastembed with nomic
    print("\n[1] Testing fastembed (nomic-ai/nomic-embed-text-v1.5) natively...")
    gen_fastembed = EmbeddingGenerator(provider="fastembed", model_name="nomic-ai/nomic-embed-text-v1.5")
    
    start_time = time.time()
    doc_fastembed = await gen_fastembed.embed(doc)
    duration = time.time() - start_time
    
    print(f"Time taken (uncached): {duration:.4f}s")
    
    # Check cache hit speed
    start_time_cached = time.time()
    # Reset embeddings to force cache read
    for c in doc.chunks: c.embedding = None 
    await gen_fastembed.embed(doc)
    duration_cached = time.time() - start_time_cached
    print(f"Time taken (cached): {duration_cached:.4f}s")

    # Cosine Similarity Test
    print("\n[2] Cosine Similarity Utilities Test")
    e1 = doc.chunks[0].embedding # Unified memory
    e2 = doc.chunks[1].embedding # Qdrant vector database
    e3 = doc.chunks[3].embedding # Weather
    
    sim_1_2 = cosine_similarity(e1, e2)
    sim_1_3 = cosine_similarity(e1, e3)
    
    print(f"Similarity (Memory System vs Vector DB): {sim_1_2:.4f} (Expect high)")
    print(f"Similarity (Memory System vs Weather): {sim_1_3:.4f} (Expect low)")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
