import re
from datetime import date, datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional
from uuid import UUID, uuid4

import yaml

from api.models import RememberRequest
from models.memory_record import atomic_write, get_vault_root, split_frontmatter


def _vault_root(root: Optional[Path] = None) -> Path:
    return get_vault_root(root)


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
    decision: str = "ADD"  # "ADD", "UPDATE", "NOOP"
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
        "entities": _as_list([*_as_list(existing.get("entities")), *request.entities]),
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
    base = get_vault_root(root)
    directory = CATEGORY_DIRS.get(category.lower(), "Daily")
    target = base / directory
    target.mkdir(parents=True, exist_ok=True)
    return target


def write_memory(request: RememberRequest, vault_root: Optional[Path] = None) -> MemoryWriteResult:
    base = get_vault_root(vault_root)
    directory = _target_directory(request.category, root=base)

    
    # Parse target incoming content
    incoming_raw_meta, incoming_body = split_frontmatter(request.text)
    incoming_title = _extract_title(incoming_body)
    incoming_slug = _slugify(incoming_title)

    # 1. Deduplication / Update Check for semantic, procedural, and distilled memories
    is_distilled_or_semantic = (
        request.category.lower() not in {"episodic", "daily"}
        or getattr(request, "distill", False)
        or getattr(request, "dedup", False)
    )

    if is_distilled_or_semantic:
        for existing_file in sorted(directory.glob("*.md")):
            if existing_file.name == "README.md":
                continue
            try:
                ex_content = existing_file.read_text(encoding="utf-8")
                ex_meta, ex_body = split_frontmatter(ex_content)
                ex_title = _extract_title(ex_body)
                ex_slug = _slugify(ex_title)

                # Check for title/slug identity match
                if ex_slug == incoming_slug or (incoming_title and ex_title and ex_title.strip().lower() == incoming_title.strip().lower()):
                    ex_raw_id = ex_meta.get("memory_id")
                    ex_id = UUID(str(ex_raw_id)) if ex_raw_id else uuid4()
                    ex_norm_body = " ".join(ex_body.split())
                    inc_norm_body = " ".join(incoming_body.split())

                    # A. Exact duplicate -> NOOP
                    if inc_norm_body in ex_norm_body or ex_norm_body == inc_norm_body:
                        return MemoryWriteResult(
                            memory_id=ex_id,
                            path=existing_file,
                            vault_path=existing_file.relative_to(base).as_posix(),
                            decision="NOOP",
                            index_status="unchanged",
                        )

                    # B. Novel update -> UPDATE existing file
                    now_str = datetime.now(timezone.utc).isoformat()
                    now_date = date.today().isoformat()
                    ex_meta.setdefault("timestamps", {})
                    if isinstance(ex_meta["timestamps"], dict):
                        ex_meta["timestamps"]["updated"] = now_str
                    ex_meta["tags"] = _normalize_tags([*_as_list(ex_meta.get("tags")), *request.tags])
                    ex_meta["entities"] = _as_list([*_as_list(ex_meta.get("entities")), *request.entities])

                    # Append update section
                    updated_body = ex_body.strip()
                    update_snippet = incoming_body.strip()
                    if update_snippet.startswith(f"# {incoming_title}"):
                        update_snippet = update_snippet[len(f"# {incoming_title}"):].strip()

                    updated_content = f"{updated_body}\n\n## Update ({now_date})\n{update_snippet}"
                    fm_str = yaml.safe_dump(ex_meta, sort_keys=False, allow_unicode=True).strip()
                    full_updated_text = f"---\n{fm_str}\n---\n{updated_content}\n"

                    atomic_write(existing_file, full_updated_text)
                    return MemoryWriteResult(
                        memory_id=ex_id,
                        path=existing_file,
                        vault_path=existing_file.relative_to(base).as_posix(),
                        decision="UPDATE",
                        index_status="pending",
                    )
            except Exception:
                pass


    # 2. No matching note -> ADD new note
    generated_id = uuid4()
    content, memory_id = _build_markdown(request, generated_id)
    _, body = split_frontmatter(content)
    title = _extract_title(body)
    prefix = date.today().isoformat() if directory.name == "Daily" else ""
    stem = "-".join(part for part in [prefix, _slugify(title), memory_id.hex[:12]] if part)
    path = directory / f"{stem}.md"

    atomic_write(path, content)
    return MemoryWriteResult(
        memory_id=memory_id,
        path=path,
        vault_path=path.relative_to(base).as_posix(),
        decision="ADD",
        index_status="pending",
    )


