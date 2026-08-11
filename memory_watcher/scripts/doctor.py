import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
VENV = ROOT / "memory_watcher" / ".venv"
COMPOSE_FILE = ROOT / "memory_watcher" / "docker-compose.yml"


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

    if shutil.which("docker"):
        try:
            result = subprocess.run(
                [
                    "docker",
                    "compose",
                    "-f",
                    str(COMPOSE_FILE),
                    "ps",
                    "--status",
                    "running",
                    "--services",
                ],
                text=True,
                capture_output=True,
                timeout=10,
            )
            services = set(result.stdout.split())
            failures += not check("postgres container", "postgres" in services)
            failures += not check("qdrant container", "qdrant" in services)
        except Exception as exc:
            failures += not check("database containers", False, str(exc))

    try:
        response = httpx.get("http://localhost:8000/ready", timeout=10.0)
        failures += not check("api readiness", response.status_code == 200, response.text[:240])
    except Exception as exc:
        failures += not check("api readiness", False, str(exc))

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
