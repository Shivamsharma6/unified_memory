import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluate_retrieval import score_case_results


def test_golden_scoring_accepts_any_audited_source_and_flags_lifecycle_leaks():
    case = {
        "id": "control-plane",
        "expected_sources": ["design.md", "plan.md"],
    }
    results = [
        {
            "source_file": "plan.md",
            "memory_id": "memory-1",
            "revision_id": "revision-1",
        },
        {
            "source_file": "other.md",
            "memory_id": "memory-2",
            "revision_id": "revision-2",
        },
    ]

    scored = score_case_results(
        case,
        results,
        valid_pairs={("memory-1", "revision-1")},
    )

    assert scored["hit1"] is True
    assert scored["hit5"] is True
    assert scored["reciprocal_rank"] == 1.0
    assert scored["historical_leaks"] == ["memory-2:revision-2"]



def test_golden_scoring_treats_missing_revision_evidence_as_a_leak():
    case = {"id": "unsafe", "expected_sources": ["expected.md"]}

    scored = score_case_results(
        case,
        [{"source_file": "expected.md"}],
        valid_pairs=set(),
    )

    assert scored["hit1"] is True
    assert scored["historical_leaks"] == ["missing-evidence:expected.md"]
