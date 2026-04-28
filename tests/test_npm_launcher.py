import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
WRAPPER_PATH = REPO_ROOT / "bin" / "agent-memory.js"


def _wrapper_env(home: Path) -> dict[str, str]:
    return {
        **os.environ,
        "HOME": str(home),
        "PYTHONPATH": "src",
        "AGENT_MEMORY_PYTHON_EXECUTABLE": sys.executable,
    }


def test_npm_wrapper_bootstrap_alias_invokes_python_cli(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _wrapper_env(home)

    result = subprocess.run(
        ["node", str(WRAPPER_PATH), "bootstrap"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["config_path"] == str(home / ".hermes" / "config.yaml")
    assert payload["db_initialized"] is True
    assert (home / ".agent-memory" / "memory.db").exists()
    assert (home / ".hermes" / "config.yaml").exists()


def test_npm_wrapper_doctor_alias_invokes_python_cli(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _wrapper_env(home)

    bootstrap = subprocess.run(
        ["node", str(WRAPPER_PATH), "bootstrap"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    result = subprocess.run(
        ["node", str(WRAPPER_PATH), "doctor"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["db_exists"] is True
    assert payload["config_exists"] is True
    assert payload["hook_installed"] is True
    assert payload["hook_occurrences"] == 1


def test_npm_wrapper_help_passthrough(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    env = _wrapper_env(home)

    result = subprocess.run(
        ["node", str(WRAPPER_PATH), "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usage: agent-memory" in result.stdout
    assert "hermes-bootstrap" in result.stdout
    assert "hermes-doctor" in result.stdout
