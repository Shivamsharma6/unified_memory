import json
import networkx as nx
from pyvis.network import Network
import logging
from typing import List, Dict, Any
from neo4j import AsyncGraphDatabase

logger = logging.getLogger(__name__)

class KnowledgeGraphStore:
    """Manages the global knowledge graph (Local NetworkX JSON + Neo4j Support)."""
    
    def __init__(self, use_neo4j: bool = False, neo4j_uri: str = "neo4j://localhost:7687", neo4j_auth=("neo4j", "password")):
        self.G = nx.DiGraph()
        self.use_neo4j = use_neo4j
        self.neo4j_driver = None
        
        if self.use_neo4j:
            self.neo4j_driver = AsyncGraphDatabase.driver(neo4j_uri, auth=neo4j_auth)

    async def close(self):
        if self.neo4j_driver:
            await self.neo4j_driver.close()

    def merge_subgraph(self, sub_g: nx.DiGraph):
        """Merge a document's extracted subgraph into the global NetworkX graph."""
        self.G = nx.compose(self.G, sub_g)

    def export_json(self, filepath: str = "knowledge_graph.json"):
        """Export global graph to JSON."""
        data = nx.node_link_data(self.G)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
    def export_html_visualization(self, filepath: str = "knowledge_graph.html"):
        """Generate interactive HTML visualization using PyVis."""
        net = Network(height="750px", width="100%", directed=True, bgcolor="#222222", font_color="white")
        net.from_nx(self.G)
        net.write_html(filepath)
        
    def get_semantic_neighborhood(self, entity: str, radius: int = 2) -> Dict[str, Any]:
        """Graph Traversal: Fetch n-hop neighborhood for an entity."""
        if entity not in self.G:
            return {"error": "Entity not found"}
            
        subgraph = nx.ego_graph(self.G, entity, radius=radius)
        return nx.node_link_data(subgraph)
        
    async def push_to_neo4j(self, sub_g: nx.DiGraph):
        """Sync a subgraph to Neo4j database."""
        if not self.use_neo4j: return
        
        async def _create_nodes_and_edges(tx):
            # Create Nodes
            for node, data in sub_g.nodes(data=True):
                node_type = data.get("type", "Concept").capitalize()
                label = data.get("label", node)
                # Sanitize labels for cypher injection (basic)
                node_type = "".join(c for c in node_type if c.isalnum())
                query = f"MERGE (n:{node_type} {{id: $id}}) SET n.name = $name"
                await tx.run(query, id=node, name=label)
                
            # Create Edges
            for u, v, data in sub_g.edges(data=True):
                rel = data.get("relation", "RELATED_TO").upper()
                rel = "".join(c for c in rel if c.isalnum() or c == "_")
                query = (
                    f"MATCH (a {{id: $u}}), (b {{id: $v}}) "
                    f"MERGE (a)-[r:{rel}]->(b)"
                )
                await tx.run(query, u=u, v=v)
                
        async with self.neo4j_driver.session() as session:
            await session.execute_write(_create_nodes_and_edges)
            logger.info("Subgraph synced to Neo4j.")
