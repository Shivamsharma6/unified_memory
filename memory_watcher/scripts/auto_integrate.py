#!/usr/bin/env python3
"""Audit UAMS MCP integration without mutating external client configs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml


def get_uams_config(root_dir: Path) -> dict:
    return {
        "command": str(root_dir / "uams"),
        "args": ["mcp"],
        "env": {"UAMS_API_URL": "http://localhost:8000"},
    }


def _command_reachable(command: str) -> bool:
    path = Path(command).expanduser()
    return path.exists() if path.is_absolute() else shutil.which(command) is not None


def inspect_json_target(
    name: str,
    path: Path,
    expected: dict,
    *,
    nested: tuple[str, ...] = ("mcpServers", "uams"),
) -> dict:
    if not path.exists():
        return {"client": name, "status": "missing", "path": str(path)}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        for key in nested:
            value = value[key]
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {"client": name, "status": "invalid", "path": str(path), "detail": str(error)}
    if value == expected:
        return {"client": name, "status": "configured", "path": str(path)}
    command = value.get("command") if isinstance(value, dict) else None
    if command and not _command_reachable(command):
        return {
            "client": name,
            "status": "unreachable",
            "path": str(path),
            "detail": f"command not found: {command}",
        }
    return {
        "client": name,
        "status": "invalid",
        "path": str(path),
        "detail": "UAMS configuration differs from the expected command",
    }


def inspect_hermes(path: Path, expected: dict) -> dict:
    if not path.exists():
        return {"client": "Hermes", "status": "missing", "path": str(path)}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        value = data["mcp_servers"]["uams"]
    except (OSError, ValueError, TypeError, KeyError) as error:
        return {"client": "Hermes", "status": "invalid", "path": str(path), "detail": str(error)}
    if value == expected:
        return {"client": "Hermes", "status": "configured", "path": str(path)}
    command = value.get("command") if isinstance(value, dict) else None
    status = "unreachable" if command and not _command_reachable(command) else "invalid"
    return {"client": "Hermes", "status": status, "path": str(path)}


def integration_report(root_dir: Path | None = None) -> list[dict]:
    root = root_dir or Path(__file__).resolve().parents[2]
    expected = get_uams_config(root)
    home = Path.home()
    results = [
        inspect_json_target(
            "Claude Desktop",
            home / "Library/Application Support/Claude/claude_desktop_config.json",
            expected,
        ),
        inspect_json_target("Claude Code", home / ".claude.json", expected),
        inspect_json_target(
            "OpenClaw",
            home / ".openclaw/openclaw.json",
            expected,
            nested=("mcp", "servers", "uams"),
        ),
        inspect_hermes(home / ".hermes/config.yaml", expected),
    ]
    codex_path = home / ".codex/config.toml"
    if not codex_path.exists():
        results.append({"client": "Codex", "status": "missing", "path": str(codex_path)})
    else:
        text = codex_path.read_text(encoding="utf-8")
        status = "configured" if "mcp_servers.uams" in text else "missing"
        results.append({"client": "Codex", "status": status, "path": str(codex_path)})
    return results


def main() -> int:
    print("=== UAMS MCP Integration Audit ===")
    results = integration_report()
    for result in results:
        detail = f" - {result['detail']}" if result.get("detail") else ""
        print(f"[{result['status']}] {result['client']}: {result['path']}{detail}")
    return 1 if any(result["status"] in {"invalid", "unreachable"} for result in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
