import json
import networkx as nx
from collections import Counter

# Load the graph
graph_path = "knowledge_graph.json"
try:
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
        rel = d.get("relationship", "related_to")
        print(f"[{u}] --({rel})--> [{v}]")

except Exception as e:
    print(f"Error analyzing graph: {e}")
