import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def stdio_config() -> dict:
    root = repo_root()
    return {
        "command": str(root / "uams"),
        "args": ["mcp"],
        "env": {"UAMS_API_URL": "http://localhost:8000"},
    }


def mcp_json() -> str:
    return json.dumps({"mcpServers": {"uams": stdio_config()}}, indent=2)


def codex_toml() -> str:
    config = stdio_config()
    args = ", ".join(json.dumps(arg) for arg in config["args"])
    env = ", ".join(f"{key} = {json.dumps(value)}" for key, value in config["env"].items())
    return "\n".join(
        [
            "[mcp_servers.uams]",
            f"command = {json.dumps(config['command'])}",
            f"args = [{args}]",
            f"env = {{{env}}}",
        ]
    )


def main() -> None:
    target = sys.argv[1] if len(sys.argv) > 1 else "json"
    if target in {"json", "claude", "cursor", "windsurf"}:
        print(mcp_json())
    elif target == "codex":
        print(codex_toml())
    elif target == "all":
        print("# Claude Code / Claude Desktop / Cursor / Windsurf")
        print(mcp_json())
        print("\n# Codex ~/.codex/config.toml")
        print(codex_toml())
    else:
        raise SystemExit("Usage: mcp_config.py [json|claude|cursor|windsurf|codex|all]")


if __name__ == "__main__":
    main()
