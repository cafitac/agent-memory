import json
import subprocess
from pathlib import Path


def test_cli_review_commands_and_scope_aware_retrieval(tmp_path: Path) -> None:
    db_path = tmp_path / "cli-review-scope.db"
    cwd = Path(__file__).resolve().parents[1]

    subprocess.run(["uv", "run", "agent-memory", "init", str(db_path)], cwd=cwd, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "ingest-source",
            str(db_path),
            "manual_note",
            "Project X uses EP branches. Project Y uses YY branches.",
            "--metadata-json",
            '{"workspace":"agent-memory"}',
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "create-fact",
            str(db_path),
            "Project Y",
            "branch_pattern",
            "YY-###",
            "project:project-y",
            "--evidence-ids-json",
            "[1]",
            "--confidence",
            "0.95",
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "create-fact",
            str(db_path),
            "Project X",
            "branch_pattern",
            "EP-###",
            "project:project-x",
            "--evidence-ids-json",
            "[1]",
            "--confidence",
            "0.50",
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )

    candidate_output = subprocess.run(
        ["uv", "run", "agent-memory", "list-candidate-facts", str(db_path)],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    candidates = json.loads(candidate_output.stdout)
    assert len(candidates) == 2

    approved = subprocess.run(
        ["uv", "run", "agent-memory", "review", "approve", "fact", str(db_path), "1"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    approved_payload = json.loads(approved.stdout)
    assert approved_payload["status"] == "approved"

    subprocess.run(
        ["uv", "run", "agent-memory", "review", "approve", "fact", str(db_path), "2"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )

    retrieved = subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "retrieve",
            str(db_path),
            "What branch pattern does Project X use?",
            "--preferred-scope",
            "project:project-x",
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    packet = json.loads(retrieved.stdout)
    assert packet["semantic_facts"][0]["scope"] == "project:project-x"
