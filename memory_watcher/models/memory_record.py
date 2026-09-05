"""Validated Markdown memory records and filesystem safety helpers."""

from __future__ import annotations

import os
import re
import unicodedata
import uuid
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

try:
    from memory_types.memory_types import normalize_memory_type
except ImportError:
    try:
        from memory_types import normalize_memory_type
    except ImportError:
        from memory_watcher.memory_types.memory_types import normalize_memory_type


MEMORY_ID_NAMESPACE = uuid.UUID("56b81673-c72e-4b52-8178-f78b1eb5107c")
_FRONTMATTER_RE = re.compile(
    r"\A---[ \t]*\r?\n(?P<yaml>.*?)\r?\n---[ \t]*(?:\r?\n|\Z)(?P<body>.*)\Z",
    re.DOTALL,
)
_KNOWN_VAULT_FOLDERS = {
    "Agents",
    "AI",
    "Archive",
    "Concepts",
    "Conversations",
    "Daily",
    "Logs",
    "People",
    "Procedures",
    "Projects",
    "Research",
    "Tasks",
}


class MemoryTimestamps(BaseModel):
    created: str | None = None
    updated: str | None = None
    occurred: str | None = None


class MemoryRelationship(BaseModel):
    predicate: str
    target: str
    status: Literal["explicit", "candidate", "verified", "retracted"] = "explicit"


class MemoryRecord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True, populate_by_name=True)

    memory_id: uuid.UUID
    path: Path
    vault_path: str
    title: str
    memory_type: str = Field(alias="type")
    status: str = "active"
    aliases: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    timestamps: MemoryTimestamps = Field(default_factory=MemoryTimestamps)
    source_agent: str | None = None
    project: str | None = None
    relationships: list[MemoryRelationship] = Field(default_factory=list)
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str
    chunks: list[Any] = Field(default_factory=list)

    @property
    def type(self) -> str:
        return self.memory_type



def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse a Markdown frontmatter block, returning an empty mapping if absent."""

    match = _FRONTMATTER_RE.match(text.lstrip("\ufeff"))
    if not match:
        return {}, text.strip()
    metadata = yaml.safe_load(match.group("yaml")) or {}
    if not isinstance(metadata, dict):
        raise ValueError("Markdown frontmatter must be a YAML mapping")
    return metadata, match.group("body").strip()


def get_vault_root(explicit_root: Path | str | None = None) -> Path:
    """Return the authoritative vault root path honoring UAMS_VAULT_PATH."""
    if explicit_root is not None:
        return Path(explicit_root).resolve()
    env_root = os.getenv("UAMS_VAULT_PATH")
    if env_root:
        return Path(env_root).resolve()
    return Path(__file__).resolve().parents[2]


def resolve_vault_path(vault_root: Path | None = None, requested_path: str | Path = "") -> Path:
    """Resolve a caller-controlled path and guarantee it stays inside the vault."""
    root = get_vault_root(vault_root)
    requested = Path(requested_path)
    candidate = requested if requested.is_absolute() else root / requested
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError as error:
        raise ValueError(f"Path is outside the memory vault: {requested_path}") from error
    if relative == Path("."):
        raise ValueError("A memory path must name a file inside the vault")
    return resolved



def normalized_vault_path(path: Path, vault_root: Path | None = None) -> str:
    candidate = Path(path)
    if vault_root is not None:
        relative = resolve_vault_path(vault_root, candidate).relative_to(Path(vault_root).resolve())
    elif not candidate.is_absolute():
        relative = candidate
    else:
        relative = candidate
        for index, part in enumerate(candidate.parts):
            if part in _KNOWN_VAULT_FOLDERS:
                relative = Path(*candidate.parts[index:])
                break
    normalized = unicodedata.normalize("NFKC", relative.as_posix()).strip("/")
    if not normalized:
        raise ValueError("Cannot derive a stable vault-relative memory path")
    return normalized


def deterministic_memory_id(path: Path, vault_root: Path | None = None) -> uuid.UUID:
    return uuid.uuid5(MEMORY_ID_NAMESPACE, normalized_vault_path(path, vault_root))


def _as_string_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = list(value) if isinstance(value, list) else [value]
    flattened = []
    while values:
        item = values.pop(0)
        if isinstance(item, (list, tuple)):
            values[:0] = list(item)
        else:
            flattened.append(item)
    return list(
        dict.fromkeys(
            str(item).strip()
            for item in flattened
            if item is not None and str(item).strip()
        )
    )


def _as_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _relationships(value: Any) -> list[MemoryRelationship]:
    if not value:
        return []
    items = value if isinstance(value, list) else [value]
    relationships: list[MemoryRelationship] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        predicate = item.get("predicate") or item.get("relation") or item.get("type")
        target = item.get("target") or item.get("object") or item.get("entity")
        if predicate and target:
            relationships.append(
                MemoryRelationship(
                    predicate=str(predicate).strip(),
                    target=str(target).strip(),
                    status=str(item.get("status", "explicit")),
                )
            )
    return relationships


def _title(body: str, fallback: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or fallback
    return fallback


def parse_memory(
    path: Path,
    text: str | None = None,
    *,
    vault_root: Path | None = None,
) -> MemoryRecord:
    """Parse a Markdown note into a stable, validated managed record."""

    if text is None:
        text = Path(path).read_text(encoding="utf-8")

    metadata, body = split_frontmatter(text)
    raw_memory_id = metadata.get("memory_id")
    memory_id = uuid.UUID(str(raw_memory_id)) if raw_memory_id else deterministic_memory_id(path, vault_root)
    timestamps = metadata.get("timestamps") if isinstance(metadata.get("timestamps"), dict) else {}
    created = timestamps.get("created") or metadata.get("created") or metadata.get("date")
    updated = timestamps.get("updated") or metadata.get("updated")
    occurred = timestamps.get("occurred") or metadata.get("occurred_at") or metadata.get("date")

    return MemoryRecord(
        memory_id=memory_id,
        path=Path(path),
        vault_path=normalized_vault_path(path, vault_root),
        title=_title(body, Path(path).stem),
        type=normalize_memory_type(metadata.get("type")),
        status=str(metadata.get("status") or "active"),
        aliases=_as_string_list(metadata.get("aliases")),
        tags=_as_string_list(metadata.get("tags")),
        entities=_as_string_list(metadata.get("entities")),
        timestamps=MemoryTimestamps(
            created=_as_timestamp(created),
            updated=_as_timestamp(updated),
            occurred=_as_timestamp(occurred),
        ),
        source_agent=metadata.get("source_agent"),
        project=metadata.get("project"),
        relationships=_relationships(metadata.get("relationships")),
        frontmatter=metadata,
        body=body,
    )


def atomic_write(path: Path, content: str) -> None:
    """Durably replace a Markdown file without exposing a partial write."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.tmp"
    try:
        with temporary.open("x", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
        directory_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)
