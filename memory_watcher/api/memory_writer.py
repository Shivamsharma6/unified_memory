import re
from datetime import date, datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID, uuid4

import yaml

from api.models import RememberRequest
from models.memory_record import atomic_write, split_frontmatter


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


@dataclass(frozen=True)
class MemoryWriteResult:
    memory_id: UUID
    path: Path
    vault_path: str
    index_status: str = "pending"


def _as_list(value) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return list(dict.fromkeys(str(item).strip() for item in values if str(item).strip()))


def _build_markdown(request: RememberRequest, memory_id: UUID) -> tuple[str, UUID]:
    existing, body = split_frontmatter(request.text)
    now = datetime.now(timezone.utc).isoformat()
    raw_memory_id = existing.get("memory_id")
    managed_id = UUID(str(raw_memory_id)) if raw_memory_id else memory_id
    timestamps = existing.get("timestamps") if isinstance(existing.get("timestamps"), dict) else {}
    tags = _normalize_tags([*_as_list(existing.get("tags")), *request.tags])

    metadata = {
        "memory_id": str(managed_id),
        "type": str(existing.get("type") or request.category),
        "status": str(existing.get("status") or "active"),
        "aliases": _as_list(existing.get("aliases")),
        "tags": tags,
        "entities": _as_list(existing.get("entities")),
        "timestamps": {
            "created": str(timestamps.get("created") or existing.get("created") or existing.get("date") or now),
            "updated": now,
        },
        "source_agent": existing.get("source_agent") or request.source_agent or "unknown",
        "project": existing.get("project") or request.project,
        "relationships": existing.get("relationships") or [],
    }
    if metadata["type"] in {"episodic", "daily"}:
        metadata["date"] = existing.get("date") or date.today().isoformat()
    for key, value in existing.items():
        if key not in metadata and key not in {"created", "updated"}:
            metadata[key] = value

    body = body.strip()
    if not body.startswith("# "):
        title = _extract_title(body)
        body = f"# {title}\n\n## Summary\n{body}"
    frontmatter = yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{frontmatter}\n---\n{body}\n", managed_id


def _target_directory(category: str, root: Optional[Path] = None) -> Path:
    base = root or VAULT_ROOT
    directory = CATEGORY_DIRS.get(category.lower(), "Daily")
    target = base / directory
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_memory(request: RememberRequest, vault_root: Optional[Path] = None) -> MemoryWriteResult:
    base = Path(vault_root) if vault_root else VAULT_ROOT
    generated_id = uuid4()
    content, memory_id = _build_markdown(request, generated_id)
    _, body = split_frontmatter(content)
    title = _extract_title(body)
    directory = _target_directory(request.category, root=base)
    prefix = date.today().isoformat() if directory.name == "Daily" else ""
    stem = "-".join(part for part in [prefix, _slugify(title), memory_id.hex[:12]] if part)
    path = directory / f"{stem}.md"

    atomic_write(path, content)
    return MemoryWriteResult(
        memory_id=memory_id,
        path=path,
        vault_path=path.relative_to(base).as_posix(),
    )

