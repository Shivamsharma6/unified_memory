import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import yaml

from api.models import RememberRequest


VAULT_ROOT = Path(__file__).resolve().parents[2]

CATEGORY_DIRS = {
    "semantic": "Concepts",
    "concept": "Concepts",
    "episodic": "Daily",
    "daily": "Daily",
    "procedural": "Tasks",
    "procedure": "Tasks",
    "summary": "AI/Summaries",
}


def _slugify(text: str, fallback: str = "memory") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return slug[:72] or fallback


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("---"):
            return stripped[:80]
    return "Memory"


def _has_frontmatter(text: str) -> bool:
    return text.lstrip().startswith("---")


def _normalize_tags(tags: Iterable[str]) -> list[str]:
    normalized = []
    for tag in tags:
        clean = str(tag).strip()
        if not clean:
            continue
        normalized.append(clean if clean.startswith("#") else f"#{clean}")
    return list(dict.fromkeys(normalized))


def _build_markdown(request: RememberRequest) -> str:
    if _has_frontmatter(request.text):
        return request.text.strip() + "\n"

    today = date.today().isoformat()
    title = _extract_title(request.text)
    metadata = {
        "type": request.category,
        "date": today,
        "updated": datetime.now(timezone.utc).isoformat(),
        "tags": _normalize_tags(request.tags),
    }

    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=False).strip()
    return f"---\n{frontmatter}\n---\n# {title}\n\n## Summary\n{request.text.strip()}\n"


def _target_directory(category: str) -> Path:
    directory = CATEGORY_DIRS.get(category.lower(), "Daily")
    target = VAULT_ROOT / directory
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_memory(request: RememberRequest) -> Path:
    content = _build_markdown(request)
    title = _extract_title(content)
    directory = _target_directory(request.category)
    prefix = date.today().isoformat() if directory.name == "Daily" else ""
    stem = "-".join(part for part in [prefix, _slugify(title)] if part)
    path = directory / f"{stem}.md"

    counter = 2
    while path.exists():
        path = directory / f"{stem}-{counter}.md"
        counter += 1

    path.write_text(content, encoding="utf-8")
    return path
