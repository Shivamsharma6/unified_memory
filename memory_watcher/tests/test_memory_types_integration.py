import pytest
from pathlib import Path

try:
    from models.memory_record import parse_memory
    from memory_types.memory_types import MemoryCategory, normalize_memory_type, CANONICAL_TYPE_ALIASES
except ImportError:
    from memory_watcher.models.memory_record import parse_memory
    from memory_watcher.memory_types.memory_types import MemoryCategory, normalize_memory_type, CANONICAL_TYPE_ALIASES


def test_normalize_memory_type():
    assert normalize_memory_type("concept") == MemoryCategory.SEMANTIC.value
    assert normalize_memory_type("concepts") == MemoryCategory.SEMANTIC.value
    assert normalize_memory_type("daily") == MemoryCategory.EPISODIC.value
    assert normalize_memory_type("task") == MemoryCategory.PROCEDURAL.value
    assert normalize_memory_type("procedure") == MemoryCategory.PROCEDURAL.value
    assert normalize_memory_type("profile") == MemoryCategory.IDENTITY.value
    assert normalize_memory_type("goal") == MemoryCategory.GOAL.value
    assert normalize_memory_type("reflection") == MemoryCategory.REFLECTION.value
    assert normalize_memory_type("relationship") == MemoryCategory.RELATIONSHIP.value
    assert normalize_memory_type("unknown_type_xyz") == MemoryCategory.SEMANTIC.value


def test_parse_memory_canonicalizes_aliases():
    raw = """---
type: concept
tags: ["#test"]
---
# Concept Note
Content about something.
"""
    record = parse_memory(Path("Concepts/test.md"), raw)
    assert record.memory_type == MemoryCategory.SEMANTIC.value


def test_parse_memory_canonicalizes_daily_to_episodic():
    raw = """---
type: daily
date: 2026-08-22
---
# Daily Note
Today was productive.
"""
    record = parse_memory(Path("Daily/2026-08-22.md"), raw)
    assert record.memory_type == MemoryCategory.EPISODIC.value


def test_parse_memory_canonicalizes_task_to_procedural():
    raw = """---
type: task
---
# How to Deploy
1. Step one.
"""
    record = parse_memory(Path("Tasks/deploy.md"), raw)
    assert record.memory_type == MemoryCategory.PROCEDURAL.value


def test_parse_memory_handles_all_7_categories():
    for cat in MemoryCategory:
        raw = f"""---
type: {cat.value}
---
# Test {cat.value}
Body text.
"""
        record = parse_memory(Path(f"test_{cat.value}.md"), raw)
        assert record.memory_type == cat.value
