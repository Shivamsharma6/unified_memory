import sys
import json
from pathlib import Path

# Add parent dir to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from models.document import Document
from chunkers.semantic import SemanticChunker

def run_benchmark():
    sample_markdown = """---
type: episodic
tags: ["#architecture", "#planning"]
date: 2026-05-21
---
# Unified Agent Memory System

The UAMS is designed to give [[OpenClaw]] and [[VoiceAI]] a shared brain.

## Core Concepts

### Vector Storage
We use [[Qdrant]] for embeddings. This allows us to perform rapid semantic search over thousands of memory fragments without hitting latency limits. 

```python
# Pseudo connection
client = QdrantClient("localhost", port=6333)
client.search(collection_name="memories", query_vector=[0.1, 0.2])
```

### Knowledge Graph
To supplement vector search, a knowledge graph extracts relationships between entities. 

## Next Steps
- Implement semantic chunker.
- Tie it to watchdog.
"""

    doc = Document(path="architecture/uams_planning.md", raw_content=sample_markdown)
    chunker = SemanticChunker(max_chunk_size=300) # Small chunk size to force overlap logic
    
    print("--- RUNNING CHUNKER BENCHMARK ---")
    processed_doc = chunker.chunk(doc)
    
    print(f"\nDocument parsed. Found {len(processed_doc.chunks)} chunks.\n")
    
    for i, chunk in enumerate(processed_doc.chunks):
        print(f"=== Chunk {i} | ID: {chunk.metadata.chunk_id} ===")
        print(f"Hierarchy: {' > '.join(chunk.metadata.heading_hierarchy)}")
        print(f"Entities: {chunk.metadata.entities}")
        print(f"Tags: {chunk.metadata.tags}")
        print(f"Category: {chunk.metadata.semantic_category}")
        print("-" * 30)
        print(f"{chunk.content}")
        print("=" * 50 + "\n")

if __name__ == "__main__":
    run_benchmark()
