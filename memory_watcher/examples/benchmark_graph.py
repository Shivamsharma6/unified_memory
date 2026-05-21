import sys
import asyncio
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from graph.extractor import GraphExtractor
from graph.store import KnowledgeGraphStore

async def run_benchmark():
    print("--- KNOWLEDGE GRAPH EXTRACTION BENCHMARK ---\n")
    
    extractor = GraphExtractor()
    store = KnowledgeGraphStore(use_neo4j=False) # Local JSON/NetworkX mode
    
    # Mock Markdown Documents
    doc1 = """---
related_to: ["[[Unified Memory]]"]
---
# Architecture
This project uses [[Qdrant]] for vector search. It depends on [[FastAPI]] for the API layer.
[[Shivam]] improves [[RetrievalPipeline]] heavily.
"""
    
    doc2 = """
# Issue Log
The latest commit fixes [[ConnectionError]] caused by [[DockerTimeout]].
[[OpenClaw]] uses [[Unified Memory]] to enhance conversational recall.
"""

    # Extract
    g1 = extractor.extract_from_markdown("architecture.md", doc1, {"related_to": ["[[Unified Memory]]"]})
    g2 = extractor.extract_from_markdown("issues.md", doc2, {})
    
    # Merge into global store
    store.merge_subgraph(g1)
    store.merge_subgraph(g2)
    
    print(f"Graph Nodes: {len(store.G.nodes)}")
    print(f"Graph Edges: {len(store.G.edges)}\n")
    
    print("--- Sample Nodes ---")
    for n, data in list(store.G.nodes(data=True))[:5]:
        print(f"Node: {n}, Type: {data.get('type')}")
        
    print("\n--- Sample Edges (Relationships) ---")
    for u, v, data in list(store.G.edges(data=True)):
        print(f"{u} -[{data.get('relation')}]-> {v}")
        
    print("\n--- Generating Semantic Neighborhood for 'Unified Memory' ---")
    neighborhood = store.get_semantic_neighborhood("Unified Memory", radius=1)
    if "error" not in neighborhood:
        print(f"Found {len(neighborhood['nodes'])} connected entities in 1-hop radius.")
    
    # Export Outputs
    print("\nExporting Graph JSON to 'knowledge_graph.json'...")
    store.export_json("knowledge_graph.json")
    
    print("Exporting Interactive Visualization to 'knowledge_graph.html'...")
    store.export_html_visualization("knowledge_graph.html")
    
    print("\nDone! Open memory_watcher/knowledge_graph.html in a browser to view the interactive graph.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
