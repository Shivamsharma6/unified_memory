import pytest
import uuid
from pathlib import Path

try:
    from graph.extractor import ProjectedClaim, extract_projection, GraphExtractor
    from models.memory_record import parse_memory
except ImportError:
    from memory_watcher.graph.extractor import ProjectedClaim, extract_projection, GraphExtractor
    from memory_watcher.models.memory_record import parse_memory


def test_graph_extractor_identifies_opposing_relations():
    extractor = GraphExtractor()
    text_v1 = "The auth system uses [[JWT tokens]]."
    fm_v1 = {"type": "semantic"}
    G1 = extractor.extract_from_markdown("Auth.md", text_v1, fm_v1)
    assert G1.has_edge("Auth.md", "JWT tokens") or G1.has_edge("DOC:Auth.md", "JWT tokens")

    # Contradicting or updated decision
    text_v2 = "The auth system replaces [[JWT tokens]] with [[Paseto]]."
    fm_v2 = {"type": "semantic"}
    G2 = extractor.extract_from_markdown("Auth.md", text_v2, fm_v2)
    assert "Paseto" in G2.nodes()
