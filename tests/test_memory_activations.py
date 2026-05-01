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
    insert_relation,
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


def test_cli_activations_reinforcement_report_scores_refs_with_factor_breakdowns(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "reinforcement-report.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Reinforcement report target phrase is REINFORCEMENT_REPORT_OK.",
        metadata={"project": "reinforcement-report"},
    )
    approved_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Reinforcement report",
        predicate="target_phrase",
        object_ref_or_value="REINFORCEMENT_REPORT_OK",
        evidence_ids=[source.id],
        scope="project:reinforcement-report",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=approved_fact.id)
    deprecated_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Reinforcement report",
        predicate="old_phrase",
        object_ref_or_value="DEPRECATED_REINFORCEMENT_VALUE",
        evidence_ids=[source.id],
        scope="project:reinforcement-report",
        confidence=0.5,
    )
    deprecate_memory(
        db_path=db_path,
        memory_type="fact",
        memory_id=deprecated_fact.id,
        reason="old reinforcement value",
    )
    insert_relation(
        db_path,
        from_ref=f"fact:{approved_fact.id}",
        relation_type="mentions",
        to_ref="concept:reinforcement-report",
        evidence_ids=[source.id],
        weight=0.8,
        confidence=0.8,
    )

    for idx in range(3):
        record_retrieval_observation(
            db_path,
            surface="hermes" if idx < 2 else "cli",
            query="SUPERSECRET reinforcement query must not leak",
            preferred_scope="project:reinforcement-report",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_trace(approved_fact.id, label="approved reinforcement target")],
            response_mode="verify_first",
            metadata={"query_preview": "abc123", "session_id": f"session-reinforcement-{idx}"},
        )
    record_retrieval_observation(
        db_path,
        surface="cli",
        query="SUPERSECRET deprecated reinforcement query",
        preferred_scope="project:reinforcement-report",
        limit=5,
        statuses=("deprecated",),
        retrieval_trace=[_trace(deprecated_fact.id, label="deprecated reinforcement target")],
        response_mode="verify_first",
        metadata={"raw_prompt": "SUPERSECRET"},
    )
    record_retrieval_observation(
        db_path,
        surface="hermes",
        query="SUPERSECRET empty reinforcement query",
        preferred_scope="project:missing",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[],
        response_mode="verify_first",
        metadata={"api_key": "***"},
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "activations",
            "reinforcement-report",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_reinforcement_report"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 5
    assert payload["scoring"] == {
        "max_score": 1.0,
        "weights": {
            "connectivity": 0.15,
            "repetition": 0.35,
            "status_trust": 0.2,
            "strength": 0.2,
            "surface_scope_diversity": 0.1,
        },
        "penalties": {
            "deprecated": 0.4,
            "disputed": 0.3,
            "missing": 0.2,
            "supersession_or_replacement": 0.25,
        },
    }

    candidates = {item["memory_ref"]: item for item in payload["reinforcement_candidates"]}
    approved_payload = candidates[f"fact:{approved_fact.id}"]
    assert approved_payload["score"] == 1.0
    assert approved_payload["current_status"] == "approved"
    assert approved_payload["factor_breakdown"]["repetition"]["score"] == 0.35
    assert approved_payload["factor_breakdown"]["strength"]["score"] == 0.2
    assert approved_payload["factor_breakdown"]["status_trust"]["value"] == "approved"
    assert approved_payload["factor_breakdown"]["connectivity"]["relation_count"] == 1
    assert approved_payload["signals"] == ["strong_reinforcement_candidate", "frequently_activated", "connected_memory"]
    assert len(approved_payload["sample_activation_ids"]) == 3
    assert len(approved_payload["sample_observation_ids"]) == 3

    deprecated_payload = candidates[f"fact:{deprecated_fact.id}"]
    assert deprecated_payload["current_status"] == "deprecated"
    assert deprecated_payload["score"] < approved_payload["score"]
    assert "status_penalty" in deprecated_payload["penalties"]
    assert deprecated_payload["signals"] == ["not_reinforcement_ready", "deprecated_activation"]
    assert payload["negative_evidence"] == {"empty_retrieval_count": 1, "empty_retrieval_ratio": 0.2}
    assert payload["suggested_next_steps"] == [
        "Inspect strong candidates with activations summary before any promotion workflow.",
        "Use decay-risk reporting before mutating stale or weak memories.",
        "Keep retrieval ranking unchanged until opt-in eval and live Hermes E2E pass.",
    ]
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout


def test_cli_activations_reinforcement_report_lazily_migrates_legacy_database(tmp_path: Path) -> None:
    db_path = tmp_path / "reinforcement-report-legacy.db"
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
            "reinforcement-report",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_reinforcement_report"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 0
    assert payload["quality_warnings"] == ["no_activations"]


def test_cli_activations_decay_risk_report_flags_weak_refs_without_age_only_decay(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "decay-risk-report.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Decay risk target phrase is DECAY_RISK_REPORT_OK.",
        metadata={"project": "decay-risk-report"},
    )
    protected_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Decay risk",
        predicate="strong_phrase",
        object_ref_or_value="DECAY_RISK_REPORT_OK",
        evidence_ids=[source.id],
        scope="project:decay-risk-report",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=protected_fact.id)
    weak_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Decay risk",
        predicate="weak_phrase",
        object_ref_or_value="WEAK_DECAY_RISK_VALUE",
        evidence_ids=[source.id],
        scope="project:decay-risk-report",
        confidence=0.4,
    )
    insert_relation(
        db_path,
        from_ref=f"fact:{protected_fact.id}",
        relation_type="mentions",
        to_ref="concept:decay-risk-report",
        evidence_ids=[source.id],
        weight=0.8,
        confidence=0.8,
    )

    for idx in range(3):
        record_retrieval_observation(
            db_path,
            surface="hermes" if idx < 2 else "cli",
            query="SUPERSECRET protected decay query must not leak",
            preferred_scope="project:decay-risk-report",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_trace(protected_fact.id, label="protected decay target")],
            response_mode="verify_first",
            metadata={"query_preview": "abc123", "session_id": f"session-decay-{idx}"},
        )
    record_retrieval_observation(
        db_path,
        surface="cli",
        query="SUPERSECRET weak decay query",
        preferred_scope="project:decay-risk-report",
        limit=5,
        statuses=("candidate",),
        retrieval_trace=[_trace(weak_fact.id, label="weak decay target")],
        response_mode="verify_first",
        metadata={"raw_prompt": "SUPERSECRET"},
    )
    record_retrieval_observation(
        db_path,
        surface="hermes",
        query="SUPERSECRET empty decay query",
        preferred_scope="project:missing",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[],
        response_mode="verify_first",
        metadata={"api_key": "***"},
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "activations",
            "decay-risk-report",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_decay_risk_report"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 5
    assert payload["scoring"] == {
        "max_score": 1.0,
        "weights": {
            "low_connectivity": 0.15,
            "low_repetition": 0.3,
            "stale_activity": 0.2,
            "status_risk": 0.15,
            "weak_strength": 0.2,
        },
        "protections": {
            "approved_frequent_connected_max_score": 0.25,
            "approved_frequent_max_score": 0.4,
        },
    }

    candidates = {item["memory_ref"]: item for item in payload["decay_risk_candidates"]}
    weak_payload = candidates[f"fact:{weak_fact.id}"]
    protected_payload = candidates[f"fact:{protected_fact.id}"]
    assert weak_payload["score"] > protected_payload["score"]
    assert weak_payload["current_status"] == "candidate"
    assert weak_payload["factor_breakdown"]["low_repetition"]["activation_count"] == 1
    assert weak_payload["factor_breakdown"]["low_connectivity"]["relation_count"] == 0
    assert weak_payload["signals"] == ["decay_review_candidate", "low_activation_count", "isolated_memory"]
    assert protected_payload["current_status"] == "approved"
    assert protected_payload["score"] <= 0.25
    assert protected_payload["protections"] == ["approved_frequent_connected_max_score"]
    assert "protected_from_age_only_decay" in protected_payload["signals"]
    assert payload["negative_evidence"] == {"empty_retrieval_count": 1, "empty_retrieval_ratio": 0.2}
    assert payload["suggested_next_steps"] == [
        "Inspect high decay-risk refs with activations summary and review explain before any status change.",
        "Treat this report as advisory only; do not delete, deprecate, or mutate from decay score alone.",
        "Use future consolidation candidate reports to compare weak refs with trace clusters before cleanup.",
    ]
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout


def test_cli_activations_decay_risk_report_lazily_migrates_legacy_database(tmp_path: Path) -> None:
    db_path = tmp_path / "decay-risk-report-legacy.db"
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
            "decay-risk-report",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_decay_risk_report"
    assert payload["read_only"] is True
    assert payload["activation_count"] == 0
    assert payload["quality_warnings"] == ["no_activations"]
