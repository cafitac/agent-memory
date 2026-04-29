import json
import os
import subprocess
import sys
from pathlib import Path

from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.storage.sqlite import initialize_database


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _seed_prompt_db(db_path: Path) -> None:
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Project X uses SQLite-first agent memory and Hermes hook integration.",
        metadata={"title": "project-x-memory"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="memory_runtime",
        object_ref_or_value="SQLite-first agent memory with Hermes integration",
        evidence_ids=[source.id],
        scope="project:x",
    )
    approve_fact(db_path=db_path, fact_id=fact.id)


def _write_fake_binary(script_path: Path) -> None:
    script_path.write_text(
        "import json\n"
        "import os\n"
        "import pathlib\n"
        "import sys\n"
        "payload = {\"argv\": sys.argv[1:]}\n"
        "out = os.environ.get('FAKE_WRAPPER_CAPTURE_PATH')\n"
        "if out:\n"
        "    pathlib.Path(out).write_text(json.dumps(payload))\n"
        "print('OK')\n"
    )



def test_run_codex_with_memory_dry_run_outputs_command_and_prompt(tmp_path: Path) -> None:
    db_path = tmp_path / "codex-wrapper.db"
    _seed_prompt_db(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_codex_with_memory.py",
            str(db_path),
            "What does Project X use?",
            "--preferred-scope",
            "project:x",
            "--dry-run",
            "--codex-model",
            "gpt-5.4-mini",
            "--extra-codex-arg=--approval-mode=auto",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"][0] == "codex"
    assert payload["command"][1] == "exec"
    assert "--sandbox" in payload["command"]
    assert "--approval-mode=auto" in payload["command"]
    assert "Memory response mode:" in payload["prompt"]
    assert "Reason codes:" in payload["prompt"]
    assert "User request:" in payload["prompt"]
    assert "What does Project X use?" in payload["prompt"]



def test_run_claude_with_memory_dry_run_outputs_command_and_prompt(tmp_path: Path) -> None:
    db_path = tmp_path / "claude-wrapper.db"
    _seed_prompt_db(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_claude_with_memory.py",
            str(db_path),
            "What does Project X use?",
            "--preferred-scope",
            "project:x",
            "--dry-run",
            "--max-turns",
            "2",
            "--extra-claude-arg=--permission-mode=acceptEdits",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["command"][0] == "claude"
    assert payload["command"][1] == "-p"
    assert "--max-turns" in payload["command"]
    assert "--permission-mode=acceptEdits" in payload["command"]
    assert "Memory response mode:" in payload["prompt"]
    assert "Reason codes:" in payload["prompt"]
    assert "User request:" in payload["prompt"]
    assert "What does Project X use?" in payload["prompt"]



def test_run_codex_with_memory_can_invoke_overridden_binary(tmp_path: Path) -> None:
    db_path = tmp_path / "codex-wrapper-invoke.db"
    _seed_prompt_db(db_path)
    fake_binary = tmp_path / "fake_codex.py"
    capture_path = tmp_path / "capture.json"
    _write_fake_binary(fake_binary)
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "FAKE_WRAPPER_CAPTURE_PATH": str(capture_path),
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_codex_with_memory.py",
            str(db_path),
            "What does Project X use?",
            "--preferred-scope",
            "project:x",
            "--codex-bin",
            f"{sys.executable} {fake_binary}",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
    payload = json.loads(capture_path.read_text())
    assert payload["argv"][0] == "exec"
    assert any("What does Project X use?" in value for value in payload["argv"])



def test_run_claude_with_memory_can_invoke_overridden_binary(tmp_path: Path) -> None:
    db_path = tmp_path / "claude-wrapper-invoke.db"
    _seed_prompt_db(db_path)
    fake_binary = tmp_path / "fake_claude.py"
    capture_path = tmp_path / "capture.json"
    _write_fake_binary(fake_binary)
    env = {
        **os.environ,
        "PYTHONPATH": "src",
        "FAKE_WRAPPER_CAPTURE_PATH": str(capture_path),
    }

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_claude_with_memory.py",
            str(db_path),
            "What does Project X use?",
            "--preferred-scope",
            "project:x",
            "--claude-bin",
            f"{sys.executable} {fake_binary}",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "OK"
    payload = json.loads(capture_path.read_text())
    assert payload["argv"][0] == "-p"
    assert any("What does Project X use?" in value for value in payload["argv"])
