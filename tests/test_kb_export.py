import json
import os
import subprocess
import sys
from pathlib import Path

from agent_memory.core.curation import (
    approve_fact,
    create_candidate_fact,
    create_candidate_procedure,
    create_episode,
    dispute_memory,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.kb_export import export_kb_markdown
from agent_memory.storage.sqlite import initialize_database


def test_export_kb_markdown_writes_only_approved_scoped_memories_with_provenance(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    output_dir = tmp_path / "kb"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project M1 uses KB export after approval. Run pytest before release.",
        metadata={"project": "m1"},
    )
    approved_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="uses",
        object_ref_or_value="KB export after approval",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.9,
    )
    approve_fact(db_path=db_path, fact_id=approved_fact.id)
    create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="leaks",
        object_ref_or_value="candidate memory",
        evidence_ids=[source.id],
        scope="project:m1",
    )
    disputed = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="leaks",
        object_ref_or_value="disputed memory",
        evidence_ids=[source.id],
        scope="project:m1",
    )
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=disputed.id)
    other_scope = create_candidate_fact(
        db_path=db_path,
        subject_ref="Other Project",
        predicate="uses",
        object_ref_or_value="different scope",
        evidence_ids=[source.id],
        scope="project:other",
    )
    approve_fact(db_path=db_path, fact_id=other_scope.id)

    result = export_kb_markdown(db_path=db_path, output_dir=output_dir, scope="project:m1")

    assert result.output_dir == str(output_dir)
    assert result.scope == "project:m1"
    assert {file.path for file in result.files} == {
        str(output_dir / "index.md"),
        str(output_dir / "facts.md"),
        str(output_dir / "procedures.md"),
        str(output_dir / "episodes.md"),
    }
    facts_md = (output_dir / "facts.md").read_text()
    assert "Project M1" in facts_md
    assert "KB export after approval" in facts_md
    assert f"Evidence source ids: {source.id}" in facts_md
    assert "candidate memory" not in facts_md
    assert "disputed memory" not in facts_md
    assert "Other Project" not in facts_md


def test_export_kb_markdown_writes_procedures_and_episodes(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    output_dir = tmp_path / "kb"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="runbook",
        content="Before release, run pytest and smoke tests.",
    )
    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Release verification",
        trigger_context="Before publishing a release",
        preconditions=["Dependencies installed"],
        steps=["Run uv run pytest -q", "Run install smoke"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=0.8,
    )
    from agent_memory.core.curation import approve_procedure

    approve_procedure(db_path=db_path, procedure_id=procedure.id)
    create_episode(
        db_path=db_path,
        title="Validated release workflow",
        summary="Confirmed tests and install smoke pass before release.",
        source_ids=[source.id],
        tags=["release", "smoke"],
        importance_score=0.7,
        scope="project:m1",
        status="approved",
    )

    export_kb_markdown(db_path=db_path, output_dir=output_dir, scope="project:m1")

    procedures_md = (output_dir / "procedures.md").read_text()
    episodes_md = (output_dir / "episodes.md").read_text()
    assert "Release verification" in procedures_md
    assert "Run uv run pytest -q" in procedures_md
    assert f"Evidence source ids: {source.id}" in procedures_md
    assert "Validated release workflow" in episodes_md
    assert "Tags: release, smoke" in episodes_md
    assert f"Source ids: {source.id}" in episodes_md


def test_cli_kb_export_runs_vertical_slice(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    output_dir = tmp_path / "kb"
    env = {**os.environ, "PYTHONPATH": "src"}
    cwd = Path(__file__).resolve().parents[1]

    init = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "init", str(db_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert init.returncode == 0, init.stderr

    source = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "ingest-source",
            str(db_path),
            "manual_note",
            "Project M1 exports approved memory to markdown.",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert source.returncode == 0, source.stderr
    source_id = json.loads(source.stdout)["id"]

    fact = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "create-fact",
            str(db_path),
            "Project M1",
            "exports",
            "approved memory to markdown",
            "project:m1",
            "--evidence-ids-json",
            f"[{source_id}]",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert fact.returncode == 0, fact.stderr
    fact_id = json.loads(fact.stdout)["id"]

    approve = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "approve-fact", str(db_path), str(fact_id)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert approve.returncode == 0, approve.stderr

    export = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "kb",
            "export",
            str(db_path),
            str(output_dir),
            "--scope",
            "project:m1",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )

    assert export.returncode == 0, export.stderr
    payload = json.loads(export.stdout)
    assert payload["scope"] == "project:m1"
    assert (output_dir / "facts.md").exists()
    assert "approved memory to markdown" in (output_dir / "facts.md").read_text()
