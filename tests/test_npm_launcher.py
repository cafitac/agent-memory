import json
import os
import stat
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


def test_npm_wrapper_pins_python_package_to_npm_version(tmp_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    recorded_args = tmp_path / "uvx-args.json"
    uvx_stub = bin_dir / "uvx"
    uvx_stub.write_text(
        "#!/usr/bin/env python3\n"
        "import json, pathlib, sys\n"
        f"pathlib.Path({str(recorded_args)!r}).write_text(json.dumps(sys.argv[1:]))\n",
    )
    uvx_stub.chmod(uvx_stub.stat().st_mode | stat.S_IXUSR)

    package_json = json.loads((REPO_ROOT / "package.json").read_text())
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
    }
    env.pop("AGENT_MEMORY_PYTHON_EXECUTABLE", None)

    result = subprocess.run(
        ["node", str(WRAPPER_PATH), "kb", "export", "--help"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    args = json.loads(recorded_args.read_text())
    assert args[:3] == ["--from", f"cafitac-agent-memory=={package_json['version']}", "agent-memory"]
    assert args[3:] == ["kb", "export", "--help"]


def test_user_docs_show_installed_agent_memory_command_after_npm_install() -> None:
    readme = (REPO_ROOT / "README.md").read_text()
    install_smoke = (REPO_ROOT / "docs" / "install-smoke.md").read_text()

    npm_section = readme.split("Alternative Python-first install paths:", maxsplit=1)[0]
    assert "npm install -g @cafitac/agent-memory" in npm_section
    assert "agent-memory bootstrap" in npm_section
    assert "agent-memory doctor" in npm_section
    assert "uv run agent-memory" not in readme
    assert "agent-memory [command]" in install_smoke


def test_install_smoke_docs_cover_external_user_trust_matrix() -> None:
    install_smoke = (REPO_ROOT / "docs" / "install-smoke.md").read_text()

    assert "Fresh-user trust matrix" in install_smoke
    for surface in ["npm", "npx", "uvx", "Hermes", "Codex/Claude prompts", "Forensic review"]:
        assert surface in install_smoke
    assert "external temp directory" in install_smoke
    assert "approved memory" in install_smoke
    assert "disputed/deprecated" in install_smoke
    assert "fails closed" in install_smoke
