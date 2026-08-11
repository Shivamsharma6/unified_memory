import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chunkers.semantic import SemanticChunker
from graph.extractor import extract_projection, normalize_entity_key
from models.document import Document
from models.memory_record import parse_memory


def record(body: str, extra_frontmatter: str = ""):
    markdown = f"""---
type: semantic
status: active
aliases: []
tags: ["#test"]
entities: []
timestamps:
  created: 2026-08-11T00:00:00Z
  updated: 2026-08-11T00:00:00Z
{extra_frontmatter}---
# Unified Memory

{body}
"""
    return parse_memory(Path("Concepts/Unified Memory.md"), markdown)


def test_heading_only_blocks_are_not_vector_chunks():
    document = Document(
        path="Concepts/Test.md",
        raw_content="# Test Memory\n## Empty Section\n## Fix\nRestarted [[Qdrant]] and verified cleanup.",
    )

    chunked = SemanticChunker().chunk(document)

    assert len(chunked.chunks) == 1
    assert "Empty Section" not in chunked.chunks[0].content
    assert "Test Memory" in chunked.chunks[0].content
    assert "Fix" in chunked.chunks[0].content
    assert "Restarted" in chunked.chunks[0].content


def test_body_chunks_include_title_and_heading_hierarchy():
    document = Document(
        path="Concepts/Test.md",
        raw_content="# Unified Memory\n## Retrieval\n### Exact Match\nPostgreSQL stores durable profiles.",
    )

    chunk = SemanticChunker().chunk(document).chunks[0]

    assert chunk.metadata.heading_hierarchy == ["Unified Memory", "Retrieval", "Exact Match"]
    assert chunk.content.startswith("# Unified Memory\n## Retrieval\n### Exact Match")


def test_alias_keys_are_unicode_and_case_normalized():
    assert normalize_entity_key("  ＱＤＲＡＮＴ   Store ") == "qdrant store"


def test_wikilink_is_a_mention_not_a_factual_claim():
    projection = extract_projection(record("This note references [[Qdrant]]."))

    assert [mention.entity_name for mention in projection.mentions] == ["Qdrant"]
    assert projection.claims == []


def test_related_to_is_an_explicit_evidenced_claim():
    projection = extract_projection(
        record("Uses semantic retrieval.", 'related_to: ["[[Qdrant]]"]\n')
    )

    assert len(projection.claims) == 1
    claim = projection.claims[0]
    assert claim.subject == "Unified Memory"
    assert claim.predicate == "related_to"
    assert claim.object == "Qdrant"
    assert claim.status == "explicit"
    assert claim.evidence_memory_id == projection.memory_id


def test_candidate_relationships_are_excluded_from_retrieval_claims():
    projection = extract_projection(
        record(
            "[[PostgreSQL]] and [[Qdrant]] are mentioned.",
            """relationships:
  - predicate: uses
    target: "[[PostgreSQL]]"
    status: explicit
  - predicate: fixes
    target: "[[Qdrant]]"
    status: candidate
""",
        )
    )

    assert [claim.predicate for claim in projection.claims] == ["uses", "fixes"]
    assert [claim.predicate for claim in projection.retrieval_claims()] == ["uses"]
