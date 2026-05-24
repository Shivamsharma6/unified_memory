import re
from pathlib import Path


VAULT_ROOT = Path(__file__).resolve().parents[2]


def _terms(task: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-zA-Z0-9_]{3,}", task.lower())
        if term not in {"the", "and", "for", "with", "that", "this", "from"}
    }


def _score(text: str, terms: set[str]) -> int:
    lower = text.lower()
    return sum(lower.count(term) for term in terms)


def _excerpt(path: Path, max_chars: int = 2400) -> str:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "\n\n..."


def get_relevant_procedures(task: str, limit: int = 4) -> list[str]:
    procedures = []

    agents_file = VAULT_ROOT / "AGENTS.md"
    if agents_file.exists():
        procedures.append(f"Source: AGENTS.md\n{_excerpt(agents_file, max_chars=3600)}")

    task_terms = _terms(task)
    candidates = []
    tasks_dir = VAULT_ROOT / "Tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("*.md"):
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            candidates.append((_score(content + " " + path.stem, task_terms), path))

    for score, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        if score <= 0 or len(procedures) >= limit:
            break
        procedures.append(f"Source: {path.relative_to(VAULT_ROOT)}\n{_excerpt(path)}")

    return procedures
