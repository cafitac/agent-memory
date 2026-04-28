import json
import os
import subprocess
import sys
from pathlib import Path

from agent_memory.core.curation import (
    approve_fact,
    approve_procedure,
    create_candidate_fact,
    create_candidate_procedure,
    create_episode,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import Episode, ProvenanceSummary
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import (
    initialize_database,
    list_candidate_facts,
    list_candidate_procedures,
)


def test_retrieve_packet_includes_approved_episode_and_provenance(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes stores sessions in SQLite with FTS5 search.",
        metadata={"project": "hermes", "workspace": "agent-memory"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes",
        predicate="stores_sessions_in",
        object_ref_or_value="SQLite with FTS5 search",
        evidence_ids=[source.id],
        scope="project:hermes",
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    episode = create_episode(
        db_path=db_path,
        title="Investigated Hermes session storage",
        summary="Confirmed Hermes stores sessions in SQLite with FTS5 search.",
        source_ids=[source.id],
        tags=["hermes", "storage"],
        importance_score=0.8,
        status="approved",
    )

    packet = retrieve_memory_packet(db_path=db_path, query="Where does Hermes store sessions?")

    assert packet.episodic_context[0].id == episode.id
    assert isinstance(packet.episodic_context[0], Episode)
    assert packet.episodic_context[0].tags == ["hermes", "storage"]
    assert isinstance(packet.provenance[0], ProvenanceSummary)
    assert packet.provenance[0].source_id == source.id
    assert packet.provenance[0].source_type == "transcript"
    assert packet.provenance[0].metadata["project"] == "hermes"



def test_candidate_review_lists_pending_facts_and_procedures(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Run pytest before opening a PR. Project X uses EP branches.",
        metadata={"project": "project-x"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local tests",
        trigger_context="Before opening a PR",
        preconditions=["Dependencies installed"],
        steps=["Run PYTHONPATH=src pytest tests/ -q"],
        evidence_ids=[source.id],
        scope="project:project-x",
    )

    candidate_facts = list_candidate_facts(db_path)
    candidate_procedures = list_candidate_procedures(db_path)

    assert [item.id for item in candidate_facts] == [fact.id]
    assert [item.id for item in candidate_procedures] == [procedure.id]



def test_cli_list_candidates_and_retrieve_include_new_fields(tmp_path: Path) -> None:
    db_path = tmp_path / "cli-episode-review.db"
    env = {**os.environ, "PYTHONPATH": "src"}
    cwd = Path(__file__).resolve().parents[1]

    init = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "init", str(db_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert init.returncode == 0

    source = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "ingest-source",
            str(db_path),
            "transcript",
            "Hermes stores sessions in SQLite with FTS5 search.",
            "--metadata-json",
            '{"project":"hermes"}',
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert source.returncode == 0

    fact = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "create-fact",
            str(db_path),
            "Hermes",
            "stores_sessions_in",
            "SQLite with FTS5 search",
            "project:hermes",
            "--evidence-ids-json",
            "[1]",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert fact.returncode == 0

    list_candidates = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "list-candidate-facts", str(db_path)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert list_candidates.returncode == 0
    list_payload = json.loads(list_candidates.stdout)
    assert list_payload[0]["subject_ref"] == "Hermes"

    approve = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "approve-fact", str(db_path), "1"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert approve.returncode == 0

    create_episode_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "create-episode",
            str(db_path),
            "Investigated Hermes session storage",
            "Confirmed Hermes stores sessions in SQLite with FTS5 search.",
            "--source-ids-json",
            "[1]",
            "--tags-json",
            '["hermes","storage"]',
            "--importance-score",
            "0.8",
            "--status",
            "approved",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert create_episode_result.returncode == 0

    retrieve = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "Where does Hermes store sessions?",
        ],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve.returncode == 0
    packet = json.loads(retrieve.stdout)
    assert packet["episodic_context"][0]["title"] == "Investigated Hermes session storage"
    assert packet["provenance"][0]["source_id"] == 1
