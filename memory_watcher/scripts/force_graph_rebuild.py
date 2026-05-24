import asyncio
import glob
from pathlib import Path
import yaml
import networkx as nx
from graph.extractor import GraphExtractor
from graph.store import KnowledgeGraphStore

def extract_frontmatter(content: str):
    frontmatter = {}
    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            try:
                fm_text = parts[1]
                frontmatter = yaml.safe_load(fm_text) or {}
                content = parts[2]
            except Exception:
                pass
    return frontmatter, content

async def rebuild_graph():
    print("Rebuilding Knowledge Graph from entire vault...")
    extractor = GraphExtractor()
    store = KnowledgeGraphStore()
    
    vault_path = Path(__file__).resolve().parents[2]
    # Exclude venv files
    md_files = [
        f for f in glob.glob(f"{vault_path}/**/*.md", recursive=True)
        if ".venv" not in Path(f).parts and "venv" not in Path(f).parts
    ]
    
    for file_path in md_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                raw_content = f.read()
                
            fm, content = extract_frontmatter(raw_content)
            
            subgraph = extractor.extract_from_markdown(file_path, content, fm)
            store.merge_subgraph(subgraph)
        except Exception as e:
            print(f"Failed to process {file_path}: {e}")
            
    store.export_json(str(vault_path / "memory_watcher" / "knowledge_graph.json"))
    print("Graph rebuilt and saved.")
    
    G = store.graph
    
    print("\n=== UPDATED KNOWLEDGE GRAPH SUMMARY ===")
    print(f"Total Nodes: {G.number_of_nodes()}")
    print(f"Total Edges: {G.number_of_edges()}")
    
    print("\n=== TOP 15 ENTITIES (By Connections) ===")
    degrees = sorted(G.degree, key=lambda x: x[1], reverse=True)[:15]
    for node, deg in degrees:
        print(f"- {node} (Connections: {deg})")
        
    print("\n=== KEY CAUSAL RELATIONSHIPS ===")
    edges = list(G.edges(data=True))
    for u, v, d in edges:
        rel = d.get("relation", "")
        if rel in ["uses", "fixes", "depends_on", "caused_by"]:
            print(f"[{u}] --({rel})--> [{v}]")

asyncio.run(rebuild_graph())
