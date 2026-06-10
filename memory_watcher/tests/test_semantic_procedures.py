import pytest
from api.procedure_reader import get_relevant_procedures


def test_semantic_procedures_returns_list():
    result = get_relevant_procedures("How do I deploy to production?")
    assert isinstance(result, list)
    assert len(result) > 0


def test_semantic_procedures_includes_agents_md():
    result = get_relevant_procedures("How to commit code with git")
    assert isinstance(result, list)
    assert any("AGENTS.md" in r for r in result)
