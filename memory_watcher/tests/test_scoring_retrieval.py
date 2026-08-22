import pytest
from pathlib import Path

try:
    from memory_types.scoring import ImportanceScorer
    from api.models import SearchResult
except ImportError:
    from memory_watcher.memory_types.scoring import ImportanceScorer
    from memory_watcher.api.models import SearchResult


def test_novelty_against_known_corpus():
    scorer = ImportanceScorer()
    known_corpus = {"qdrant", "database", "postgres", "vector", "embedding", "memory"}

    # Highly redundant content against known corpus
    redundant_content = "qdrant database postgres vector embedding memory"
    score_red = scorer.score(redundant_content, corpus_vocabulary=known_corpus)

    # Novel content
    novel_content = "quantum entanglement topological quantum computing qubits"
    score_nov = scorer.score(novel_content, corpus_vocabulary=known_corpus)

    assert score_nov.novelty > score_red.novelty
    assert score_red.novelty == 0.0
    assert score_nov.novelty > 0.8


def test_importance_score_affects_weighted_score():
    scorer = ImportanceScorer()
    score_high_imp = scorer.score(
        "Important architectural decision with critical bugs fixed",
        metadata={"mention_count": 5},
    )
    score_low_imp = scorer.score(
        "Casual random chat about nothing in particular",
        metadata={"mention_count": 0},
    )
    assert score_high_imp.weighted_score > score_low_imp.weighted_score
