import json
import networkx as nx
from pyvis.network import Network
import os

def generate_html():
    possible_paths = [
        "knowledge_graph.json",
        "memory_watcher/knowledge_graph.json",
        os.path.join(os.path.dirname(__file__), "..", "knowledge_graph.json"),
    ]
    graph_path = next((p for p in possible_paths if os.path.exists(p)), None)
    out_path = "knowledge_graph_interactive.html"
    
    if not graph_path:
        print(f"Error: knowledge_graph.json not found in any expected location.")
        return
        
    with open(graph_path, "r") as f:
        data = json.load(f)
    
    G = nx.node_link_graph(data)
    
    # Create PyVis network
    net = Network(height="800px", width="100%", bgcolor="#1e1e1e", font_color="white", directed=True)
    
    # Add nodes with custom styling based on degree
    for node, attributes in G.nodes(data=True):
        degree = G.degree(node)
        # Scale size based on connections
        size = 15 + (degree * 3)
        
        # Color based on type (heuristic)
        color = "#97c2fc" # Default blue
        if str(node).startswith("DOC:"):
            color = "#ff9999" # Red for documents
            node_label = str(node).split("/")[-1] # Simplify label
        else:
            node_label = str(node)
            
        if node in ["Unified Agent Memory", "Qdrant", "AGENTS.md", "Knowledge Graph"]:
            color = "#ffcc00" # Yellow for core concepts
            size += 10
            
        net.add_node(node, label=node_label, size=size, color=color, title=str(node))
        
    # Add edges with labels
    for u, v, attributes in G.edges(data=True):
        rel = attributes.get("relation", attributes.get("relationship", "related_to"))
        net.add_edge(u, v, title=rel, label=rel, color="#666666")
        
    # Set physics options for a nice organic layout
    net.set_options('''
    var options = {
      "physics": {
        "forceAtlas2Based": {
          "gravitationalConstant": -100,
          "centralGravity": 0.01,
          "springLength": 200,
          "springConstant": 0.05
        },
        "maxVelocity": 50,
        "solver": "forceAtlas2Based",
        "timestep": 0.35,
        "stabilization": {"iterations": 150}
      },
      "edges": {
        "smooth": {"type": "continuous"}
      }
    }
    ''')
    
    net.save_graph(out_path)
    print(f"Graph generated at {os.path.abspath(out_path)}")

generate_html()
