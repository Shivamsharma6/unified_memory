import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / "memory_watcher" / ".venv"


def check(name: str, ok: bool, detail: str = "") -> bool:
    status = "ok" if ok else "fail"
    suffix = f" - {detail}" if detail else ""
    print(f"[{status}] {name}{suffix}")
    return ok


def warn(name: str, detail: str = "") -> None:
    suffix = f" - {detail}" if detail else ""
    print(f"[warn] {name}{suffix}")


def main() -> int:
    failures = 0
    failures += not check("python >= 3.11", sys.version_info >= (3, 11), sys.version.split()[0])
    failures += not check("virtualenv", (VENV / "bin" / "python").exists(), str(VENV))
    failures += not check("docker cli", shutil.which("docker") is not None)
    failures += not check("uams command", (ROOT / "uams").exists(), str(ROOT / "uams"))
    failures += not check("mcp package", importlib.util.find_spec("mcp") is not None)
    failures += not check("uams_sdk package", importlib.util.find_spec("uams_sdk") is not None)

    try:
        response = httpx.get("http://localhost:8000/health", timeout=2.0)
        failures += not check("api health", response.status_code == 200, response.text[:120])
    except Exception as exc:
        warn("api health", f"not reachable yet: {exc}")

    try:
        result = subprocess.run(
            [str(ROOT / "uams"), "mcp-config", "codex"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=5,
        )
        failures += not check("mcp config generator", result.returncode == 0, result.stderr.strip())
    except Exception as exc:
        failures += not check("mcp config generator", False, str(exc))

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
