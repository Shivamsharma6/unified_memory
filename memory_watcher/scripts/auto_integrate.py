import json
import os
import sys
from pathlib import Path

def get_uams_config(root_dir: Path) -> dict:
    return {
        "command": str(root_dir / "uams"),
        "args": ["mcp"],
        "env": {
            "UAMS_API_URL": "http://localhost:8000"
        }
    }

def integrate():
    root_dir = Path(__file__).resolve().parents[2]
    uams_config = get_uams_config(root_dir)
    
    print("=== UAMS Automatic MCP Installer ===")
    print(f"Detected UAMS Root: {root_dir}")
    print()

    updated_any = False

    # 1. Standard JSON targets
    json_targets = {
        "Claude Desktop": Path("~/Library/Application Support/Claude/claude_desktop_config.json").expanduser(),
        "Claude Code": Path("~/.claude.json").expanduser(),
        "Cursor": Path("~/Library/Application Support/Cursor/User/globalStorage/moose.copilot/mcp/settings.json").expanduser(),
        "Windsurf": Path("~/.codeium/windsurf/mcp_settings.json").expanduser(),
    }

    for name, path in json_targets.items():
        if not path.parent.exists():
            print(f"[-] {name}: App folder not found (Skipped)")
            continue
            
        print(f"[*] {name}: Found config folder. Integrating...")
        config_data = {}
        if path.exists():
            try:
                config_data = json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  [warn] Failed to parse existing {path.name}: {e}. Creating new.")
                config_data = {}
                
        if "mcpServers" not in config_data or not isinstance(config_data["mcpServers"], dict):
            config_data["mcpServers"] = {}
            
        config_data["mcpServers"]["uams"] = uams_config
        
        try:
            path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
            print(f"  [ok] Successfully updated {path}")
            updated_any = True
        except Exception as e:
            print(f"  [fail] Failed to write config to {path}: {e}")

    # 2. OpenClaw (uses nested mcp.servers JSON)
    openclaw_path = Path("~/.openclaw/openclaw.json").expanduser()
    if openclaw_path.parent.exists():
        print("[*] OpenClaw: Found config folder. Integrating...")
        config_data = {}
        if openclaw_path.exists():
            try:
                config_data = json.loads(openclaw_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"  [warn] Failed to parse existing openclaw.json: {e}. Creating new.")
                config_data = {}

        if "mcp" not in config_data or not isinstance(config_data["mcp"], dict):
            config_data["mcp"] = {}
        if "servers" not in config_data["mcp"] or not isinstance(config_data["mcp"]["servers"], dict):
            config_data["mcp"]["servers"] = {}

        config_data["mcp"]["servers"]["uams"] = uams_config

        try:
            openclaw_path.write_text(json.dumps(config_data, indent=2), encoding="utf-8")
            print(f"  [ok] Successfully updated {openclaw_path}")
            updated_any = True
        except Exception as e:
            print(f"  [fail] Failed to write config to {openclaw_path}: {e}")
    else:
        print("[-] OpenClaw: App folder not found (Skipped)")

    # 3. Hermes (uses YAML with mcp_servers)
    hermes_path = Path("~/.hermes/config.yaml").expanduser()
    if hermes_path.parent.exists():
        print("[*] Hermes: Found config folder. Integrating...")
        import yaml
        config_data = {}
        if hermes_path.exists():
            try:
                config_data = yaml.safe_load(hermes_path.read_text(encoding="utf-8")) or {}
            except Exception as e:
                print(f"  [warn] Failed to parse existing hermes config.yaml: {e}. Creating new.")
                config_data = {}

        if "mcp_servers" not in config_data or not isinstance(config_data["mcp_servers"], dict):
            config_data["mcp_servers"] = {}

        config_data["mcp_servers"]["uams"] = uams_config

        try:
            hermes_path.write_text(yaml.safe_dump(config_data, default_flow_style=False, sort_keys=False), encoding="utf-8")
            print(f"  [ok] Successfully updated {hermes_path}")
            updated_any = True
        except Exception as e:
            print(f"  [fail] Failed to write config to {hermes_path}: {e}")
    else:
        print("[-] Hermes: App folder not found (Skipped)")

    print()
    if updated_any:
        print("🎉 Integration complete! Please restart your agent client(s) to load UAMS.")
    else:
        print("⚠️ No compatible agent config directories were found on this machine.")
        print("To manually configure your client, register this MCP server configuration:")
        print(json.dumps({"uams": uams_config}, indent=2))

if __name__ == "__main__":
    integrate()
