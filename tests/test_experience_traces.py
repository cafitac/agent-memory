from pathlib import Path

from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import (
    build_trace_retention_report,
    connect,
    initialize_database,
    insert_experience_trace,
    list_experience_traces,
)


def test_initialize_database_creates_experience_traces_table(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"

    initialize_database(db_path)

    with connect(db_path) as connection:
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(experience_traces)").fetchall()}
        indexes = {
            row["name"]
            for row in connection.execute("PRAGMA index_list(experience_traces)").fetchall()
        }

    assert {
        "id",
        "created_at",
        "surface",
        "event_kind",
        "scope",
        "session_ref",
        "content_sha256",
        "summary",
        "salience",
        "user_emphasis",
        "related_memory_refs_json",
        "related_observation_ids_json",
        "retention_policy",
        "expires_at",
        "metadata_json",
    }.issubset(columns)
    assert "raw_prompt" not in columns
    assert "raw_content" not in columns
    assert "idx_experience_traces_created_at" in indexes
    assert "idx_experience_traces_surface_kind" in indexes


def test_insert_and_list_experience_traces_store_only_sanitized_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    trace = insert_experience_trace(
        db_path,
        surface="cli",
        event_kind="user_correction",
        content_sha256="a" * 64,
        summary="User corrected the project scope naming convention.",
        scope="project:agent-memory",
        session_ref="session:test",
        salience=0.75,
        user_emphasis=0.5,
        related_memory_refs=["fact:1"],
        related_observation_ids=[3, 4],
        retention_policy="short",
        expires_at="2030-01-01T00:00:00Z",
        metadata={"adapter": "manual", "raw_prompt": "do not persist this"},
    )

    traces = list_experience_traces(db_path, limit=10)

    assert [item.id for item in traces] == [trace.id]
    assert traces[0].surface == "cli"
    assert traces[0].event_kind == "user_correction"
    assert traces[0].summary == "User corrected the project scope naming convention."
    assert traces[0].scope == "project:agent-memory"
    assert traces[0].content_sha256 == "a" * 64
    assert traces[0].related_memory_refs == ["fact:1"]
    assert traces[0].related_observation_ids == [3, 4]
    assert traces[0].retention_policy == "short"
    assert traces[0].metadata == {"adapter": "manual"}
    assert not hasattr(traces[0], "raw_prompt")
    assert "raw_prompt" not in traces[0].model_dump()


def test_existing_database_migrates_experience_traces_lazily(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"

    with connect(db_path) as connection:
        connection.execute("CREATE TABLE legacy_marker (id INTEGER PRIMARY KEY)")

    trace = insert_experience_trace(
        db_path,
        surface="cli",
        event_kind="turn",
        content_sha256="b" * 64,
        summary=None,
        metadata={},
    )

    with connect(db_path) as connection:
        legacy_exists = connection.execute("SELECT name FROM sqlite_master WHERE name = 'legacy_marker'").fetchone()
        trace_table_exists = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'experience_traces'"
        ).fetchone()

    assert legacy_exists is not None
    assert trace_table_exists is not None
    assert list_experience_traces(db_path, limit=1)[0].id == trace.id


def test_experience_trace_schema_does_not_change_retrieval_output(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Agent Memory B1 keeps trace storage separate from retrieval ranking.",
        metadata={"project": "agent-memory"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Agent Memory B1",
        predicate="keeps_separate",
        object_ref_or_value="trace storage and retrieval ranking",
        evidence_ids=[source.id],
        scope="project:agent-memory",
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    before = retrieve_memory_packet(
        db_path=db_path,
        query="What does Agent Memory B1 keep separate?",
        record_retrievals=False,
    )
    insert_experience_trace(
        db_path,
        surface="cli",
        event_kind="turn",
        content_sha256="c" * 64,
        summary="Synthetic trace unrelated to retrieval ranking.",
        metadata={},
    )
    after = retrieve_memory_packet(
        db_path=db_path,
        query="What does Agent Memory B1 keep separate?",
        record_retrievals=False,
    )

    assert [item.id for item in after.semantic_facts] == [item.id for item in before.semantic_facts]
    assert after.retrieval_trace == before.retrieval_trace


def test_trace_retention_report_identifies_expired_missing_expiry_and_volume(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)
    expired = insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="d" * 64,
        retention_policy="ephemeral",
        expires_at="2026-01-01T00:00:00Z",
        metadata={"raw_prompt": "do not emit this"},
    )
    active = insert_experience_trace(
        db_path,
        surface="cli",
        event_kind="user_correction",
        content_sha256="e" * 64,
        retention_policy="short",
        expires_at="2026-12-01T00:00:00Z",
        metadata={"adapter": "manual"},
    )
    missing_expiry = insert_experience_trace(
        db_path,
        surface="cli",
        event_kind="manual_note",
        content_sha256="f" * 64,
        retention_policy="ephemeral",
        metadata={"secret": "do not emit this"},
    )

    report = build_trace_retention_report(
        db_path,
        now="2026-06-01T00:00:00Z",
        max_trace_count=2,
        expired_limit=10,
        missing_expiry_limit=10,
    )

    assert report["kind"] == "trace_retention_report"
    assert report["read_only"] is True
    assert report["trace_count"] == 3
    assert report["max_trace_count"] == 2
    assert report["policy_counts"] == {"ephemeral": 2, "short": 1, "review": 0, "archive": 0}
    assert report["expired"]["count"] == 1
    assert report["expired"]["traces"][0]["id"] == expired.id
    assert report["missing_expiry"]["count"] == 1
    assert report["missing_expiry"]["traces"][0]["id"] == missing_expiry.id
    assert report["warnings"] == ["trace_count_exceeds_budget", "expirable_trace_without_expires_at"]
    assert active.id not in {item["id"] for item in report["expired"]["traces"]}
    report_text = str(report)
    assert "raw_prompt" not in report_text
    assert "secret" not in report_text
    assert len(list_experience_traces(db_path, limit=10)) == 3
