import pytest
from api.routers.quality import score_memory


def test_quality_with_good_content():
    content = """---
type: episodic
date: 2026-06-01
tags: ["#test"]
---
# Test Note

This is a [[test]] note with [[wikilinks]] that demonstrates how a well-structured memory should look in the unified agent memory system for multiple agents working together across different contexts and workflows.

## Section

- Point one
- Point two
- Point three with more detail about something important in the context of memory management
"""
    result = score_memory(content)
    assert result["checks"]["has_frontmatter"] is True
    assert result["checks"]["has_type"] is True
    assert result["checks"]["has_date"] is True
    assert result["checks"]["has_tags"] is True
    assert result["checks"]["wikilink_count"] >= 2
    assert result["score"] > 0.5


def test_quality_with_bare_note():
    content = "Just a plain note with no frontmatter or links."
    result = score_memory(content)
    assert result["checks"]["has_frontmatter"] is False
    assert result["score"] < 0.5


def test_quality_grade_mapping():
    content = """---
type: episodic
date: 2026-06-01
tags: ["#test"]
---
# Test

[[Entity1]] and [[Entity2]] and [[Entity3]].

## Details
- Item 1
- Item 2
- Item 3
"""
    result = score_memory(content)
    assert result["grade"] in ["A", "B", "C", "D", "F"]
