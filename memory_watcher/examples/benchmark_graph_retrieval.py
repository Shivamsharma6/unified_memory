import sys
import asyncio
import networkx as nx
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from api.retrieval.pipeline import RetrievalPipeline
from api.models import SearchRequest

async def run_benchmark():
    print("=== GRAPH-AWARE RETRIEVAL BENCHMARK ===\n")
    
    pipeline = RetrievalPipeline()
    # Mock embedder initialization to avoid downloading models for this quick test
    pipeline.embedder.embed = lambda d: d 
    pipeline.vector_store.hybrid_search = lambda *args, **kwargs: [] # We will mock the results manually
    
    # 1. Manually build the Knowledge Graph scenario in memory
    G = nx.DiGraph()
    G.add_node("EditFailure", type="issue")
    G.add_node("FileLockError", type="issue")
    G.add_node("PatchScript", type="procedure")
    
    # Edit failures are caused by file locks
    G.add_edge("EditFailure", "FileLockError", relation="caused_by")
    # PatchScript fixes file locks
    G.add_edge("PatchScript", "FileLockError", relation="fixes")
    
    pipeline.kg_store.G = G
    
    # 2. Setup the User Query
    query = "Why are EditFailure happening and how do I fix them?"
    print(f"QUERY: '{query}'\n")
    
    extracted = await pipeline._step3_extract_entities(query)
    print(f"1. Extracted Entities: {extracted}")
    
    expanded = await pipeline._step4_graph_expansion(extracted)
    print(f"2. Graph Expansion: {expanded}\n")
    
    # 3. Mock Raw Semantic Vector Results (Vector search isn't perfect, it ranks purely by text overlap)
    mock_vector_results = [
        # High text overlap, but generic
        {"id": "1", "score": 0.88, "payload": {
            "text": "EditFailure are annoying. They happen when users try to edit files.", 
            "entities": ["EditFailure"], "source_file": "complaints.md"
        }},
        # Medium text overlap, contains the root cause
        {"id": "2", "score": 0.82, "payload": {
            "text": "Sometimes files get locked. This leads to a FileLockError during I/O.", 
            "entities": ["FileLockError"], "source_file": "logs.md"
        }},
        # Low text overlap to the query, but contains the actual FIX linked in the graph
        {"id": "3", "score": 0.75, "payload": {
            "text": "Run the PatchScript.sh utility to forcefully clear locked handles.", 
            "entities": ["PatchScript", "FileLockError"], "source_file": "procedures.md"
        }}
    ]
    
    print("3. Raw Semantic Vector Ranking (Pre-Graph):")
    for r in mock_vector_results:
        print(f"   [Score: {r['score']:.2f}] {r['payload']['text'][:40]}... (Entities: {r['payload']['entities']})")
    
    # 4. Execute Graph-Aware Reranking
    reranked = await pipeline._step6_rerank(mock_vector_results, extracted)
    
    # Sort for display since rerank just assigns importance
    reranked.sort(key=lambda x: x.importance, reverse=True)
    
    print("\n4. Relationship-Aware Graph Reranking (Post-Graph):")
    for r in reranked:
        print(f"   [Importance: {r.importance:.2f}] {r.text[:40]}... (Entities: {r.entities})")
        
    print("\nNotice how Chunk 3 (the fix) was boosted to the top because the Knowledge Graph knows `PatchScript` -> fixes -> `FileLockError` <- caused_by <- `EditFailure`.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
