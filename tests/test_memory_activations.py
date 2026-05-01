from pathlib import Path

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
