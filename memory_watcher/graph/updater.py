from models.document import Document
from graph.extractor import GraphExtractor
from graph.store import KnowledgeGraphStore
from pathlib import Path
import json
import networkx as nx

class GraphUpdater:
    def __init__(self, graph_path: str = "knowledge_graph.json"):
        self.graph_path = Path(graph_path)
        self.extractor = GraphExtractor()

    async def update_relations(self, doc: Document) -> None:
        """
        Extract wikilinks and update the Knowledge Graph triples.
        """
        store = KnowledgeGraphStore()
        if self.graph_path.exists():
            try:
                store.G = nx.node_link_graph(json.loads(self.graph_path.read_text(encoding="utf-8")))
            except Exception:
                store.G = nx.DiGraph()

        subgraph = self.extractor.extract_from_markdown(doc.path, doc.raw_content, doc.frontmatter)
        store.merge_subgraph(subgraph)
        store.export_json(str(self.graph_path))
