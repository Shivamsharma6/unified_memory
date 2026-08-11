from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _launcher_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    launcher = tmp_path / "uams"
    shutil.copy2(REPOSITORY_ROOT / "uams", launcher)
    capture = tmp_path / "capture"
    capture.mkdir()
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "UAMS_API_HOST=127.0.0.9",
                "UAMS_API_PORT=8123",
                "UAMS_API_URL=http://127.0.0.9:8123",
                "UAMS_POSTGRES_HOST=127.0.0.8",
                "UAMS_POSTGRES_PORT=5544",
                "UAMS_POSTGRES_DB=memory_test",
                "UAMS_POSTGRES_USER=memory_user",
                "UAMS_POSTGRES_PASSWORD=from-root-dotenv",
                "QDRANT_HOST=127.0.0.7",
                "QDRANT_HTTP_PORT=7444",
                "QDRANT_GRPC_PORT=7445",
                "UAMS_EMBED_PROVIDER=ollama",
                "UAMS_EMBED_MODEL=test-embedding-model",
                "UAMS_EMBED_DIMENSION=768",
                "UAMS_LLM_PROVIDER=ollama",
                "UAMS_LLM_BASE_URL=http://127.0.0.6:11434",
                "UAMS_LLM_MODEL=test-llm-model",
                "",
            ]
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment["UAMS_TEST_CAPTURE"] = str(capture)
    return launcher, capture, environment


def test_root_dotenv_is_loaded_before_child_commands(tmp_path):
    launcher, capture, environment = _launcher_fixture(tmp_path)
    _write_executable(
        tmp_path / "memory_watcher/.venv/bin/python",
        """#!/bin/sh
printf '%s' "$UAMS_POSTGRES_PASSWORD" > "$UAMS_TEST_CAPTURE/python-password"
""",
    )

    result = subprocess.run(
        ["bash", str(launcher), "doctor"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (capture / "python-password").read_text() == "from-root-dotenv"


def test_launchd_jobs_receive_resolved_root_environment(tmp_path):
    launcher, capture, environment = _launcher_fixture(tmp_path)
    bin_dir = tmp_path / "bin"
    environment["PATH"] = f"{bin_dir}:{environment['PATH']}"
    _write_executable(tmp_path / "memory_watcher/.venv/bin/python", "#!/bin/sh\nexit 0\n")
    _write_executable(
        bin_dir / "docker",
        """#!/bin/sh
if [ "$1" = "info" ]; then exit 0; fi
if [ "$1" = "compose" ] && [ "$2" = "version" ]; then exit 0; fi
if [ "$1" = "compose" ]; then exit 0; fi
exit 1
""",
    )
    _write_executable(bin_dir / "uname", "#!/bin/sh\nprintf 'Darwin\\n'\n")
    _write_executable(bin_dir / "curl", "#!/bin/sh\nprintf '{\"ready\":true}\\n'\n")
    _write_executable(
        bin_dir / "launchctl",
        """#!/bin/sh
capture="$UAMS_TEST_CAPTURE"
case "$1" in
  print)
    label="${2##*/}"
    test -f "$capture/$label"
    ;;
  submit)
    printf '%s\\n' "$@" >> "$capture/launchctl-arguments"
    while [ "$#" -gt 0 ]; do
      if [ "$1" = "-l" ]; then
        shift
        : > "$capture/$1"
        break
      fi
      shift
    done
    ;;
  *) exit 0 ;;
esac
""",
    )

    result = subprocess.run(
        ["bash", str(launcher), "start"],
        cwd=tmp_path,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    arguments = (capture / "launchctl-arguments").read_text(encoding="utf-8")
    for assignment in (
        f"UAMS_VAULT_PATH={tmp_path}",
        "UAMS_API_HOST=127.0.0.9",
        "UAMS_API_PORT=8123",
        "UAMS_API_URL=http://127.0.0.9:8123",
        "UAMS_POSTGRES_HOST=127.0.0.8",
        "UAMS_POSTGRES_PORT=5544",
        "UAMS_POSTGRES_DB=memory_test",
        "UAMS_POSTGRES_USER=memory_user",
        "UAMS_POSTGRES_PASSWORD=from-root-dotenv",
        "QDRANT_HOST=127.0.0.7",
        "QDRANT_HTTP_PORT=7444",
        "QDRANT_GRPC_PORT=7445",
        "UAMS_EMBED_PROVIDER=ollama",
        "UAMS_EMBED_MODEL=test-embedding-model",
        "UAMS_EMBED_DIMENSION=768",
        "UAMS_LLM_PROVIDER=ollama",
        "UAMS_LLM_BASE_URL=http://127.0.0.6:11434",
        "UAMS_LLM_MODEL=test-llm-model",
    ):
        assert assignment in arguments
