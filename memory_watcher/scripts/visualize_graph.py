import json
import networkx as nx
from collections import Counter

import os

# Load the graph
possible_paths = [
    "knowledge_graph.json",
    "memory_watcher/knowledge_graph.json",
    os.path.join(os.path.dirname(__file__), "..", "knowledge_graph.json"),
]
graph_path = next((p for p in possible_paths if os.path.exists(p)), None)

try:
    if not graph_path:
        raise FileNotFoundError("knowledge_graph.json not found in any expected location")
    with open(graph_path, "r") as f:
        data = json.load(f)
    
    G = nx.node_link_graph(data)
    
    print("=== KNOWLEDGE GRAPH SUMMARY ===")
    print(f"Total Nodes: {G.number_of_nodes()}")
    print(f"Total Edges: {G.number_of_edges()}")
    
    print("\n=== TOP ENTITIES (By Degree) ===")
    degrees = sorted(G.degree, key=lambda x: x[1], reverse=True)[:10]
    for node, deg in degrees:
        print(f"- {node} (Connections: {deg})")
        
    print("\n=== RECENT/KEY RELATIONSHIPS ===")
    # Print some interesting edges
    edges = list(G.edges(data=True))
    # Just show the last 15 edges to see the newly added stuff
    for u, v, d in edges[-15:]:
        rel = d.get("relation", d.get("relationship", "related_to"))
        print(f"[{u}] --({rel})--> [{v}]")

except Exception as e:
    print(f"Error analyzing graph: {e}")
