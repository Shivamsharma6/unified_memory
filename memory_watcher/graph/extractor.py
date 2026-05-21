import re
import logging
from typing import List, Dict, Any, Tuple
import networkx as nx

logger = logging.getLogger(__name__)

class GraphExtractor:
    """
    Extracts entities and relationships from markdown memories to build a Knowledge Graph.
    """
    def __init__(self):
        self.wikilink_pattern = re.compile(r'\[\[(.*?)\]\]')
        
        # Heuristic relationship detection based on sentence structure around wikilinks
        self.rel_patterns = {
            "uses": re.compile(r'(?:uses|utilizes|leverages)\s+\[\[(.*?)\]\]', re.I),
            "depends_on": re.compile(r'(?:depends on|requires|needs)\s+\[\[(.*?)\]\]', re.I),
            "fixes": re.compile(r'(?:fixes|resolves|patches)\s+\[\[(.*?)\]\]', re.I),
            "caused_by": re.compile(r'(?:caused by|due to)\s+\[\[(.*?)\]\]', re.I),
            "improves": re.compile(r'(?:improves|enhances|optimizes)\s+\[\[(.*?)\]\]', re.I),
            "references": re.compile(r'(?:see also|references?|mentioned)\s+\[\[(.*?)\]\]', re.I),
        }
        
        self.entity_types = ["project", "person", "technology", "procedure", "issue", "fix", "architecture", "concept"]

    def _infer_entity_type(self, entity: str, context: str) -> str:
        """Simple heuristic to infer entity type from its name or surrounding context."""
        ent_lower = entity.lower()
        if "bug" in ent_lower or "error" in ent_lower or "issue" in ent_lower: return "issue"
        if "fix" in ent_lower or "patch" in ent_lower: return "fix"
        if "architecture" in ent_lower or "system" in ent_lower: return "architecture"
        if "how to" in ent_lower or "step" in ent_lower: return "procedure"
        if entity.istitle() and " " in entity: return "person" # Extremely naive heuristic
        return "concept"

    def extract_from_markdown(self, source_file: str, content: str, frontmatter: dict) -> nx.DiGraph:
        """Build a directed graph of entities and relationships from a single document."""
        G = nx.DiGraph()
        
        # Add the document itself as a node
        doc_node = f"DOC:{source_file}"
        G.add_node(doc_node, type="document", label=source_file)
        
        # Extract explicit frontmatter relations
        if "related_to" in frontmatter:
            for rel in frontmatter["related_to"]:
                rel_clean = rel.replace("[[", "").replace("]]", "")
                G.add_node(rel_clean, type="concept")
                G.add_edge(doc_node, rel_clean, relation="related_to")

        # Parse sentences for contextual relationships
        sentences = [s.strip() for s in re.split(r'(?<=[.!?\n])\s+', content) if s.strip()]
        
        for sentence in sentences:
            entities_in_sentence = self.wikilink_pattern.findall(sentence)
            if not entities_in_sentence:
                continue
                
            # Add all entities and link to document
            for ent in entities_in_sentence:
                ent_type = self._infer_entity_type(ent, sentence)
                if not G.has_node(ent):
                    G.add_node(ent, type=ent_type, label=ent)
                G.add_edge(doc_node, ent, relation="references")
                
            # Detect directed relationships between the document (or primary entity) and extracted entities
            for rel_name, pattern in self.rel_patterns.items():
                matches = pattern.findall(sentence)
                for target_ent in matches:
                    # If multiple entities in sentence, assume the first one acts on the target
                    # Else the document acts on the target
                    source_ent = entities_in_sentence[0] if len(entities_in_sentence) > 1 and entities_in_sentence[0] != target_ent else doc_node
                    
                    if not G.has_node(target_ent):
                        G.add_node(target_ent, type=self._infer_entity_type(target_ent, sentence), label=target_ent)
                    
                    G.add_edge(source_ent, target_ent, relation=rel_name)
                    
        return G
