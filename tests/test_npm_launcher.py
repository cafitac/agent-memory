import json
import os
import stat
import subprocess
import sys
from pathlib import Path

from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.storage.sqlite import initialize_database


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


def test_npm_wrapper_forwards_stdin_to_hermes_hook(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    db_path = tmp_path / "wrapper-hermes-hook.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="NPM launcher stdin forwarding uses target NPM_STDIN_OK.",
        metadata={"project": "npm-wrapper"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="NPM launcher stdin forwarding",
        predicate="target",
        object_ref_or_value="NPM_STDIN_OK",
        evidence_ids=[source.id],
        scope="project:npm-wrapper",
        confidence=0.96,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    env = _wrapper_env(home)
    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "tool_name": None,
        "tool_input": None,
        "session_id": "npm-wrapper-stdin-test",
        "cwd": str(tmp_path),
        "extra": {"user_message": "What target does NPM launcher stdin forwarding use?"},
    }

    result = subprocess.run(
        [
            "node",
            str(WRAPPER_PATH),
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:npm-wrapper",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
        ],
        cwd=REPO_ROOT,
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "NPM_STDIN_OK" in payload["context"]


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

    assert "npm install -g @cafitac/agent-memory" in readme
    assert "agent-memory bootstrap" in readme
    assert "agent-memory doctor" in readme
    assert "uv run agent-memory" not in readme
    assert "Alternative Python-first install paths" not in readme
    assert "Basic example" not in readme
    assert "Hermes dogfood" not in readme
    assert "npm exec --yes --package @cafitac/agent-memory" in readme
    assert "agent-memory [command]" not in install_smoke


def test_install_smoke_docs_cover_npm_first_external_smoke() -> None:
    install_smoke = (REPO_ROOT / "docs" / "install-smoke.md").read_text()

    assert "npm global install" in install_smoke
    assert "npm one-shot install" in install_smoke
    assert "npm exec --yes --package @cafitac/agent-memory@<version> -- agent-memory doctor" in install_smoke
    assert "UV_NO_CACHE=1" in install_smoke
    assert "temporary directory" in install_smoke
    assert "published-install-smoke.yml" in install_smoke
    assert "Keep private data private" in install_smoke


def test_npm_package_metadata_is_oss_facing() -> None:
    package_json = json.loads((REPO_ROOT / "package.json").read_text())

    assert package_json["name"] == "@cafitac/agent-memory"
    assert package_json["description"] == "Local-first graph memory CLI for AI agents"
    assert package_json["license"] == "MIT"
    assert package_json["homepage"] == "https://github.com/cafitac/agent-memory#readme"
    assert package_json["repository"] == {
        "type": "git",
        "url": "https://github.com/cafitac/agent-memory",
    }
    assert package_json["bugs"] == {"url": "https://github.com/cafitac/agent-memory/issues"}
    assert package_json["bin"] == {"agent-memory": "bin/agent-memory.js"}
    assert package_json["files"] == ["bin/agent-memory.js", "README.md"]
    assert package_json["publishConfig"] == {"access": "public"}
    assert set(package_json["keywords"]) == {
        "ai",
        "agent-memory",
        "cli",
        "graph-memory",
        "hermes",
        "local-first",
    }


def test_npm_pack_dry_run_contains_only_public_launcher_files() -> None:
    result = subprocess.run(
        ["npm", "pack", "--dry-run", "--json"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr

    payload = json.loads(result.stdout)[0]
    paths = {entry["path"] for entry in payload["files"]}
    assert paths == {
        "LICENSE",
        "README.md",
        "bin/agent-memory.js",
        "package.json",
    }
    assert not any(path.startswith(".dev/") for path in paths)
    assert not any(path.startswith(".agent-learner/") for path in paths)
    assert not any(path.startswith(".claude/") for path in paths)
    assert not any(path.startswith(".worktrees/") for path in paths)
    assert not any("report" in path.lower() or "dogfood" in path.lower() for path in paths)
