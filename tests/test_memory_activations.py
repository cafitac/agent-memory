from pathlib import Path

import json
import os
import subprocess
import sys

from agent_memory.core.curation import approve_fact, create_candidate_fact, deprecate_memory
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import RetrievalTraceEntry
from agent_memory.storage.sqlite import (
    connect,
    initialize_database,
    list_memory_activations,
    record_retrieval_observation,
)


def _trace(memory_id: int, *, label: str = "Agent Memory project fact") -> RetrievalTraceEntry:
    return RetrievalTraceEntry(
        memory_type="fact",
        memory_id=memory_id,
        label=label,
        scope="project:agent-memory",
        scope_priority=0,
        text_match_count=1,
        rank_value=1.0,
        total_score=1.0,
    )


def test_initialize_database_creates_memory_activations_table(tmp_path: Path) -> None:
    db_path = tmp_path / "activations.db"

    initialize_database(db_path)

    with connect(db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(memory_activations)").fetchall()}
        indexes = {row["name"] for row in connection.execute("PRAGMA index_list(memory_activations)").fetchall()}

    assert {
        "id",
        "created_at",
        "surface",
        "activation_kind",
        "memory_ref",
        "observation_id",
        "trace_id",
        "scope",
        "strength",
        "metadata_json",
    }.issubset(columns)
    assert "query_text" not in columns
    assert "query_preview" not in columns
    assert "raw_prompt" not in columns
    assert "idx_memory_activations_memory" in indexes
    assert "idx_memory_activations_observation" in indexes


def test_retrieval_observation_records_secret_safe_activation_events(tmp_path: Path) -> None:
    db_path = tmp_path / "activations.db"
    initialize_database(db_path)

    observation = record_retrieval_observation(
        db_path,
        surface="hermes",
        query="SUPERSECRET user query must never be stored as activation text",
        preferred_scope="project:agent-memory",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[_trace(1), _trace(2, label="Second fact")],
        response_mode="verify_first",
        metadata={"session_id": "session-1", "raw_prompt": "SUPERSECRET", "query_preview": "abc123"},
    )

    activations = list_memory_activations(db_path, limit=10)

    assert [activation.memory_ref for activation in activations] == ["fact:2", "fact:1"]
    assert {activation.activation_kind for activation in activations} == {"retrieved"}
    assert {activation.observation_id for activation in activations} == {observation.id}
    assert {activation.surface for activation in activations} == {"hermes"}
    assert {activation.scope for activation in activations} == {"project:agent-memory"}
    assert all(activation.strength == 1.0 for activation in activations)
    assert all(activation.metadata == {"response_mode": "verify_first", "session_id": "session-1"} for activation in activations)

    with connect(db_path) as connection:
        stored_payload = "\n".join(
            row["metadata_json"]
            for row in connection.execute("SELECT metadata_json FROM memory_activations ORDER BY id").fetchall()
        )
    assert "SUPERSECRET" not in stored_payload
    assert "abc123" not in stored_payload


def test_empty_retrieval_observation_records_negative_activation_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-activations.db"
    initialize_database(db_path)

    observation = record_retrieval_observation(
        db_path,
        surface="cli",
        query="query with no durable memory match",
        preferred_scope="project:agent-memory",
        limit=3,
        statuses=("approved",),
        retrieval_trace=[],
        response_mode="verify_first",
        metadata={"reason": "empty-smoke"},
    )

    activations = list_memory_activations(db_path, limit=10)

    assert len(activations) == 1
    activation = activations[0]
    assert activation.activation_kind == "empty_retrieval"
    assert activation.memory_ref is None
    assert activation.observation_id == observation.id
    assert activation.surface == "cli"
    assert activation.scope == "project:agent-memory"
    assert activation.strength == 0.0
    assert activation.metadata == {"reason": "empty-smoke", "response_mode": "verify_first"}


def test_activation_listing_lazily_migrates_legacy_database_without_table(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-activations.db"
    initialize_database(db_path)
    with connect(db_path) as connection:
        connection.execute("DROP TABLE memory_activations")

    activations = list_memory_activations(db_path, limit=10)

    assert activations == []
    with connect(db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(memory_activations)").fetchall()}
    assert "activation_kind" in columns


def test_cli_activations_summary_reports_read_only_reinforcement_and_negative_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "activation-summary.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Activation summary target phrase is ACTIVATION_SUMMARY_OK.",
        metadata={"project": "activation-summary"},
    )
    approved_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Activation summary",
        predicate="target_phrase",
        object_ref_or_value="ACTIVATION_SUMMARY_OK",
        evidence_ids=[source.id],
        scope="project:activation-summary",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=approved_fact.id)
    deprecated_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Activation summary",
        predicate="old_phrase",
        object_ref_or_value="DEPRECATED_ACTIVATION_VALUE",
        evidence_ids=[source.id],
        scope="project:activation-summary",
        confidence=0.5,
    )
    deprecate_memory(
        db_path=db_path,
        memory_type="fact",
        memory_id=deprecated_fact.id,
        reason="old activation summary value",
    )

    for _ in range(2):
        record_retrieval_observation(
            db_path,
            surface="hermes",
            query="SUPERSECRET should be hashed only",
            preferred_scope="project:activation-summary",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_trace(approved_fact.id, label="approved target")],
            response_mode="verify_first",
            metadata={"query_preview": "abc123", "session_id": "session-activation-summary"},
        )
    record_retrieval_observation(
        db_path,
        surface="cli",
        query="SUPERSECRET deprecated forensic query",
        preferred_scope="project:activation-summary",
        limit=5,
        statuses=("deprecated",),
        retrieval_trace=[_trace(deprecated_fact.id, label="deprecated target")],
        response_mode="verify_first",
        metadata={"raw_prompt": "SUPERSECRET"},
    )
    record_retrieval_observation(
        db_path,
        surface="hermes",
        query="SUPERSECRET empty query",
        preferred_scope="project:missing",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[],
        response_mode="verify_first",
        metadata={"token": "abc123"},
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "activations",
            "summary",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_activation_summary"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 4
    assert payload["activation_kind_counts"] == {"empty_retrieval": 1, "retrieved": 3}
    assert payload["surface_counts"] == {"cli": 1, "hermes": 3}
    assert payload["scope_counts"] == {"project:activation-summary": 3, "project:missing": 1}
    assert payload["empty_retrieval"]["count"] == 1
    assert payload["empty_retrieval"]["ratio"] == 0.25
    assert payload["status_summary"] == {"approved": 1, "deprecated": 1}
    assert payload["activation_window"]["first_activation_id"] <= payload["activation_window"]["latest_activation_id"]

    top_refs = {item["memory_ref"]: item for item in payload["top_memory_refs"]}
    approved_payload = top_refs[f"fact:{approved_fact.id}"]
    assert approved_payload["activation_count"] == 2
    assert approved_payload["total_strength"] == 2.0
    assert approved_payload["current_status"] == "approved"
    assert approved_payload["signals"] == ["frequently_activated", "likely_reinforcement_candidate"]
    assert len(approved_payload["sample_activation_ids"]) == 2
    assert len(approved_payload["sample_observation_ids"]) == 2

    deprecated_payload = top_refs[f"fact:{deprecated_fact.id}"]
    assert deprecated_payload["current_status"] == "deprecated"
    assert deprecated_payload["signals"] == ["current_status_not_approved", "deprecated_activation"]
    assert payload["suggested_next_steps"] == [
        "Run observations audit to compare activation refs with retrieval observation behavior.",
        "Run observations empty-diagnostics if empty_retrieval is high for a surface or scope.",
        "Use future reinforcement/decay reports before changing retrieval ranking or memory status.",
    ]
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout


def test_cli_activations_summary_lazily_migrates_legacy_database(tmp_path: Path) -> None:
    db_path = tmp_path / "activation-summary-legacy.db"
    initialize_database(db_path)
    with connect(db_path) as connection:
        connection.execute("DROP TABLE memory_activations")

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "activations",
            "summary",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_activation_summary"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 0
    assert payload["quality_warnings"] == ["no_activations"]
