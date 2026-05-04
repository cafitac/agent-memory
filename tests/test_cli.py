import fcntl
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from agent_memory.api.cli import main
from agent_memory.core.curation import approve_fact, create_candidate_fact, supersede_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.integrations import hermes_hooks
from agent_memory.integrations.hermes_hooks import HermesPreLlmHookOptions, HermesShellHookPayload, scope_from_cwd
from agent_memory.storage.sqlite import (
    initialize_database,
    insert_experience_trace,
    insert_relation,
    list_experience_traces,
    record_memory_retrieval,
    update_memory_status,
)


def test_python_module_cli_graph_inspect_returns_read_only_relation_neighborhood(tmp_path: Path) -> None:
    db_path = tmp_path / "graph-inspect.db"
    initialize_database(db_path)
    first = insert_relation(
        db_path,
        from_ref="fact:1",
        relation_type="superseded_by",
        to_ref="fact:2",
        evidence_ids=[11],
        confidence=0.9,
    )
    second = insert_relation(
        db_path,
        from_ref="fact:2",
        relation_type="supports",
        to_ref="procedure:7",
        evidence_ids=[12],
        confidence=0.8,
    )
    insert_relation(
        db_path,
        from_ref="episode:3",
        relation_type="mentions",
        to_ref="fact:99",
        evidence_ids=[],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "graph",
            "inspect",
            str(db_path),
            "fact:1",
            "--depth",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "relation_graph_inspection"
    assert payload["start_ref"] == "fact:1"
    assert payload["depth"] == 2
    assert payload["read_only"] is True
    assert payload["nodes"] == ["fact:1", "fact:2", "procedure:7"]
    assert [edge["id"] for edge in payload["edges"]] == [first.id, second.id]
    assert payload["edges"][0]["direction_from_start"] == "outbound"
    assert payload["edges"][1]["direction_from_start"] == "outbound"
    assert payload["truncated"] is False


def test_cli_init_creates_database(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "cli-memory.db"

    monkeypatch.setattr("sys.argv", ["agent-memory", "init", str(db_path)])
    main()

    assert db_path.exists()



def test_python_module_cli_init_creates_database(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-memory.db"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "init", str(db_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert db_path.exists()



def test_python_module_cli_traces_record_and_list_use_sanitized_payloads(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-cli.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    secret_summary = "User corrected scope naming without secret password=SUPERSECRET token=abc123"
    record_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "traces",
            "record",
            str(db_path),
            "--surface",
            "cli",
            "--event-kind",
            "user_correction",
            "--summary",
            "User corrected scope naming convention.",
            "--scope",
            "project:agent-memory",
            "--session-ref",
            "session:cli-test",
            "--salience",
            "0.75",
            "--user-emphasis",
            "0.5",
            "--related-memory-refs-json",
            '["fact:1"]',
            "--related-observation-ids-json",
            "[2, 3]",
            "--retention-policy",
            "short",
            "--metadata-json",
            json.dumps({"adapter": "manual", "raw_prompt": secret_summary}),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert record_result.returncode == 0, record_result.stderr
    record_payload = json.loads(record_result.stdout)
    assert record_payload["kind"] == "experience_trace"
    assert record_payload["trace"]["surface"] == "cli"
    assert record_payload["trace"]["event_kind"] == "user_correction"
    assert record_payload["trace"]["content_sha256"]
    assert record_payload["trace"]["metadata"] == {"adapter": "manual"}
    assert "SUPERSECRET" not in record_result.stdout
    assert "abc123" not in record_result.stdout
    assert "raw_prompt" not in record_result.stdout

    list_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "traces",
            "list",
            str(db_path),
            "--surface",
            "cli",
            "--event-kind",
            "user_correction",
            "--scope",
            "project:agent-memory",
            "--limit",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert list_result.returncode == 0, list_result.stderr
    list_payload = json.loads(list_result.stdout)
    assert list_payload["kind"] == "experience_traces"
    assert list_payload["read_only"] is True
    assert list_payload["filters"] == {
        "surface": "cli",
        "event_kind": "user_correction",
        "scope": "project:agent-memory",
    }
    assert len(list_payload["traces"]) == 1
    assert list_payload["traces"][0]["id"] == record_payload["trace"]["id"]
    assert "SUPERSECRET" not in list_result.stdout
    assert "abc123" not in list_result.stdout
    assert "raw_prompt" not in list_result.stdout



def test_python_module_cli_traces_list_handles_empty_database(tmp_path: Path) -> None:
    db_path = tmp_path / "empty-trace-cli.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "traces", "list", str(db_path), "--limit", "10"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "experience_traces"
    assert payload["read_only"] is True
    assert payload["trace_count"] == 0
    assert payload["traces"] == []


def test_python_module_cli_traces_retention_report_is_read_only_and_secret_safe(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-retention-cli.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "traces",
            "record",
            str(db_path),
            "--surface",
            "hermes-pre-llm-hook",
            "--event-kind",
            "turn",
            "--content-sha256",
            "1" * 64,
            "--retention-policy",
            "ephemeral",
            "--expires-at",
            "2026-01-01T00:00:00Z",
            "--metadata-json",
            json.dumps({"raw_prompt": "password=SUPERSECRET token=abc123"}),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "traces",
            "retention-report",
            str(db_path),
            "--now",
            "2026-06-01T00:00:00Z",
            "--max-trace-count",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "trace_retention_report"
    assert payload["read_only"] is True
    assert payload["trace_count"] == 1
    assert payload["expired"]["count"] == 1
    assert payload["warnings"] == ["trace_count_exceeds_budget"]
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout
    assert "raw_prompt" not in result.stdout

    list_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "traces", "list", str(db_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert json.loads(list_result.stdout)["trace_count"] == 1


def test_python_module_cli_retrieve_observe_records_secret_safe_local_observation(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieve-observation.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Observation smoke target phrase appears in curated memory records.",
        metadata={"project": "observation-smoke"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Observation smoke",
        predicate="target_phrase",
        object_ref_or_value="OBSERVATION_OK",
        evidence_ids=[source.id],
        scope="project:observation-smoke",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    secret_query = "What is the target phrase? password=SUPERSECRET token=abc123"
    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            secret_query,
            "--preferred-scope",
            "project:observation-smoke",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr

    list_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "list",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert list_result.returncode == 0, list_result.stderr
    payload = json.loads(list_result.stdout)
    assert payload["kind"] == "retrieval_observations"
    assert payload["observations"][0]["surface"] == "cli-test"
    assert payload["observations"][0]["query_sha256"]
    assert payload["observations"][0]["query_text"] is None
    assert payload["observations"][0]["query_preview"] is None
    assert payload["observations"][0]["retrieved_memory_refs"] == [f"fact:{fact.id}"]
    assert payload["observations"][0]["top_memory_ref"] == f"fact:{fact.id}"
    assert "SUPERSECRET" not in list_result.stdout
    assert "abc123" not in list_result.stdout


def test_python_module_cli_observations_audit_reports_frequent_and_stale_refs_without_raw_queries(tmp_path: Path) -> None:
    db_path = tmp_path / "observation-audit.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Noisy audit target phrase appears in curated memory records.",
        metadata={"project": "observation-audit"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Noisy audit",
        predicate="target_phrase",
        object_ref_or_value="AUDIT_OK",
        evidence_ids=[source.id],
        scope="project:observation-audit",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for secret_query in (
        "What is the noisy audit target phrase? password=SUPERSECRET",
        "Repeat the noisy audit target phrase token=abc123",
    ):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                secret_query,
                "--preferred-scope",
                "project:observation-audit",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    update_memory_status(
        db_path,
        memory_type="fact",
        memory_id=fact.id,
        status="deprecated",
        reason="audit regression smoke",
        actor="test",
    )

    audit_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "audit",
            str(db_path),
            "--limit",
            "50",
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

    assert audit_result.returncode == 0, audit_result.stderr
    payload = json.loads(audit_result.stdout)
    assert payload["kind"] == "retrieval_observation_audit"
    assert payload["read_only"] is True
    assert payload["observation_count"] == 2
    assert payload["surface_counts"] == {"cli-test": 2}
    assert payload["preferred_scope_counts"] == {"project:observation-audit": 2}
    assert payload["empty_retrieval_count"] == 0
    top_ref = payload["top_memory_refs"][0]
    assert top_ref["memory_ref"] == f"fact:{fact.id}"
    assert top_ref["injection_count"] == 2
    assert top_ref["current_status"] == "deprecated"
    assert top_ref["signals"] == ["frequently_injected", "current_status_not_approved"]
    assert top_ref["sample_observation_ids"]
    assert top_ref["observation_window"]["first_observation_id"] <= top_ref["observation_window"]["latest_observation_id"]
    assert top_ref["observation_window"]["first_observed_at"]
    assert top_ref["observation_window"]["latest_observed_at"]
    assert "SUPERSECRET" not in audit_result.stdout
    assert "abc123" not in audit_result.stdout


def test_python_module_cli_observations_review_candidates_explains_top_refs_without_mutation_or_raw_queries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "observation-review-candidates.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Review candidate target phrase moved from OLD_VALUE to NEW_VALUE.",
        metadata={"project": "observation-review"},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Review candidate",
        predicate="target_phrase",
        object_ref_or_value="OLD_VALUE",
        evidence_ids=[source.id],
        scope="project:observation-review",
        confidence=0.7,
    )
    replacement_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Review candidate",
        predicate="target_phrase",
        object_ref_or_value="NEW_VALUE",
        evidence_ids=[source.id],
        scope="project:observation-review",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for secret_query in (
        "What is the review candidate target phrase? password=SUPERSECRET",
        "Repeat the review candidate target phrase token=abc123",
    ):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                secret_query,
                "--preferred-scope",
                "project:observation-review",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    supersede_fact(
        db_path=db_path,
        superseded_fact_id=old_fact.id,
        replacement_fact_id=replacement_fact.id,
        reason="new target phrase replaced old one",
        actor="test",
        evidence_ids=[source.id],
    )

    review_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "review-candidates",
            str(db_path),
            "--limit",
            "50",
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

    assert review_result.returncode == 0, review_result.stderr
    payload = json.loads(review_result.stdout)
    assert payload["kind"] == "retrieval_observation_review_candidates"
    assert payload["read_only"] is True
    assert payload["observation_count"] == 2
    assert payload["candidate_count"] == 1
    assert payload["observation_audit"]["kind"] == "retrieval_observation_audit"
    assert payload["observation_audit"]["read_only"] is True
    candidate = payload["candidates"][0]
    assert candidate["memory_ref"] == f"fact:{old_fact.id}"
    assert candidate["injection_count"] == 2
    assert candidate["current_status"] == "deprecated"
    assert candidate["signals"] == [
        "frequently_injected",
        "current_status_not_approved",
        "has_replacement",
        "has_graph_relations",
    ]
    assert candidate["observation_window"]["first_observation_id"] <= candidate["observation_window"]["latest_observation_id"]
    assert candidate["observation_window"]["first_observed_at"]
    assert candidate["observation_window"]["latest_observed_at"]
    assert candidate["status_history_summary"]["transition_count"] == 2
    assert candidate["status_history_summary"]["latest_transition"]["to_status"] == "deprecated"
    assert candidate["review_explain"]["decision"]["visible_in_default_retrieval"] is False
    assert candidate["review_explain"]["replacement_chain"]["superseded_by"][0]["replacement_fact_id"] == replacement_fact.id
    assert candidate["graph_summary"]["edge_count"] == 1
    assert candidate["commands"] == {
        "review_explain": f"agent-memory review explain fact {db_path} {old_fact.id}",
        "review_replacements": f"agent-memory review replacements fact {db_path} {old_fact.id}",
        "graph_inspect": f"agent-memory graph inspect {db_path} fact:{old_fact.id} --depth 1",
    }
    assert "SUPERSECRET" not in review_result.stdout
    assert "abc123" not in review_result.stdout


def test_python_module_cli_observations_empty_diagnostics_groups_empty_segments_without_raw_queries(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "observation-empty-diagnostics.db"
    initialize_database(db_path)

    env = {**os.environ, "PYTHONPATH": "src"}
    for secret_query in (
        "no matching alpha sensitive marker SUPERSECRET",
        "no matching beta sensitive marker ABC123",
    ):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                secret_query,
                "--preferred-scope",
                "project:missing-scope",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Empty diagnostics hit target phrase is EMPTY_DIAG_OK.",
        metadata={"project": "empty-diagnostics"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Empty diagnostics",
        predicate="target_phrase",
        object_ref_or_value="EMPTY_DIAG_OK",
        evidence_ids=[source.id],
        scope="project:empty-diagnostics",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hit_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the empty diagnostics target phrase?",
            "--preferred-scope",
            "project:empty-diagnostics",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert hit_result.returncode == 0, hit_result.stderr

    diagnostics_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "empty-diagnostics",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--high-empty-threshold",
            "0.5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert diagnostics_result.returncode == 0, diagnostics_result.stderr
    payload = json.loads(diagnostics_result.stdout)
    assert payload["kind"] == "retrieval_empty_diagnostics"
    assert payload["read_only"] is True
    assert payload["observation_count"] == 3
    assert payload["empty_retrieval_count"] == 2
    assert payload["empty_retrieval_ratio"] == 0.6667
    assert payload["empty_by_surface"][0]["surface"] == "cli-test"
    assert payload["empty_by_surface"][0]["empty_count"] == 2
    scope_segment = payload["empty_by_preferred_scope"][0]
    assert scope_segment["preferred_scope"] == "project:missing-scope"
    assert scope_segment["empty_count"] == 2
    assert scope_segment["total_count"] == 2
    assert scope_segment["empty_ratio"] == 1.0
    assert scope_segment["signals"] == ["high_empty_segment"]
    assert scope_segment["sample_observation_ids"]
    assert scope_segment["observation_window"]["first_observation_id"] <= scope_segment["observation_window"]["latest_observation_id"]
    assert payload["suggested_next_steps"] == [
        "Run observations audit to compare empty vs non-empty retrieval surfaces.",
        "Check preferred scope values for scope mismatches before changing ranking.",
        "Add or approve memories only after confirming the missing queries represent durable user needs.",
    ]
    assert "SUPERSECRET" not in diagnostics_result.stdout
    assert "ABC123" not in diagnostics_result.stdout



def test_python_module_cli_dogfood_baseline_summarizes_observations_without_raw_queries(tmp_path: Path) -> None:
    db_path = tmp_path / "dogfood-baseline.db"
    config_path = tmp_path / "missing-hermes-config.yaml"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Dogfood baseline target phrase is BASELINE_OK.",
        metadata={"project": "dogfood-baseline"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Dogfood baseline",
        predicate="target_phrase",
        object_ref_or_value="BASELINE_OK",
        evidence_ids=[source.id],
        scope="project:dogfood-baseline",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for secret_query in (
        "What is the dogfood baseline target phrase? password=SUPERSECRET",
        "Unrelated durable missing token=abc123",
    ):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                secret_query,
                "--preferred-scope",
                "project:dogfood-baseline",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    baseline_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "baseline",
            str(db_path),
            "--output-json",
            "--limit",
            "20",
            "--top",
            "5",
            "--config-path",
            str(config_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert baseline_result.returncode == 0, baseline_result.stderr
    payload = json.loads(baseline_result.stdout)
    assert payload["kind"] == "dogfood_baseline"
    assert payload["read_only"] is True
    assert payload["agent_memory_version"]
    assert payload["database"]["path_exists"] is True
    assert payload["database"]["schema_user_version"] == 0
    assert payload["memory_counts"]["facts"]["approved"] == 1
    assert payload["observation_summary"]["observation_count"] == 2
    assert payload["observation_summary"]["empty_retrieval_count"] == 1
    assert payload["empty_diagnostics"]["kind"] == "retrieval_empty_diagnostics"
    assert payload["review_candidates"]["candidate_count"] == 0
    assert payload["hermes"]["status"] == "needs_setup"
    assert payload["hermes"]["config_exists"] is False
    assert "recommended_command" not in payload["hermes"]
    assert payload["local_e2e_marker"]["target_phrase"] == "not_executed"
    assert payload["suggested_next_steps"]
    assert "SUPERSECRET" not in baseline_result.stdout
    assert "abc123" not in baseline_result.stdout
    assert "query_text" not in baseline_result.stdout
    assert "query_preview" not in baseline_result.stdout



def test_python_module_cli_dogfood_baseline_handles_empty_database_without_observations(tmp_path: Path) -> None:
    db_path = tmp_path / "dogfood-empty-baseline.db"
    initialize_database(db_path)

    env = {**os.environ, "PYTHONPATH": "src"}
    baseline_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "baseline",
            str(db_path),
            "--output-json",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert baseline_result.returncode == 0, baseline_result.stderr
    payload = json.loads(baseline_result.stdout)
    assert payload["kind"] == "dogfood_baseline"
    assert payload["read_only"] is True
    assert payload["memory_counts"] == {
        "facts": {},
        "procedures": {},
        "episodes": {},
    }
    assert payload["observation_summary"]["observation_count"] == 0
    assert payload["observation_summary"]["quality_warnings"] == ["no_observations"]
    assert payload["empty_diagnostics"]["quality_warnings"] == ["no_observations"]
    assert payload["review_candidates"]["candidate_count"] == 0



def test_python_module_cli_observations_audit_reports_low_signal_empty_retrievals(tmp_path: Path) -> None:
    db_path = tmp_path / "observation-audit-empty.db"
    initialize_database(db_path)

    env = {**os.environ, "PYTHONPATH": "src"}
    for query in ("no matching alpha", "no matching beta"):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                query,
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    audit_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "audit",
            str(db_path),
            "--limit",
            "20",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert audit_result.returncode == 0, audit_result.stderr
    payload = json.loads(audit_result.stdout)
    assert payload["observation_count"] == 2
    assert payload["empty_retrieval_count"] == 2
    assert payload["empty_retrieval_ratio"] == 1.0
    assert "low_observation_count" in payload["quality_warnings"]
    assert "high_empty_retrieval_ratio" in payload["quality_warnings"]



def test_python_module_cli_approve_fact_migrates_existing_database_without_status_transition_table(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "legacy-status-transition.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Legacy status transition migration smoke.",
        metadata={"project": "legacy-status-transition"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Legacy transition",
        predicate="marker",
        object_ref_or_value="STATUS_TRANSITION_OK",
        evidence_ids=[source.id],
        scope="project:legacy-status-transition",
        confidence=0.95,
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE memory_status_transitions")

    env = {**os.environ, "PYTHONPATH": "src"}
    approve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "approve-fact",
            str(db_path),
            str(fact.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert approve_result.returncode == 0, approve_result.stderr
    approve_payload = json.loads(approve_result.stdout)
    assert approve_payload["status"] == "approved"

    history_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "history",
            "fact",
            str(db_path),
            str(fact.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert history_result.returncode == 0, history_result.stderr
    history_payload = json.loads(history_result.stdout)
    assert history_payload["history"][0]["from_status"] == "candidate"
    assert history_payload["history"][0]["to_status"] == "approved"



def test_python_module_cli_observations_list_migrates_existing_database_without_observation_table(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-observation.db"
    initialize_database(db_path)
    import sqlite3

    with sqlite3.connect(db_path) as connection:
        connection.execute("DROP TABLE retrieval_observations")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "list",
            str(db_path),
        ],
        text=True,
        capture_output=True,
        check=True,
    )

    payload = json.loads(result.stdout)
    assert payload["observations"] == []


def test_python_module_cli_retrieve_defaults_to_approved_and_hides_disputed_content(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieve-approved-only.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Status QA target phrase appears in curated memory records.",
        metadata={"project": "status-qa"},
    )
    approved = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    disputed = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="DISPUTED_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=approved.id)
    from agent_memory.core.curation import dispute_memory

    dispute_memory(db_path=db_path, memory_type="fact", memory_id=disputed.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the Status QA target phrase?",
            "--preferred-scope",
            "project:status-qa",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert [fact["object_ref_or_value"] for fact in payload["semantic_facts"]] == ["APPROVED_OK"]
    assert "DISPUTED_BAD" not in result.stdout
    assert payload["retrieval_trace"][0]["hidden_disputed_alternatives_count"] == 1
    assert payload["decision_summary"]["recommended_answer_mode"] == "verify_first"


def test_python_module_cli_retrieve_can_intentionally_include_disputed_for_forensic_review(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieve-forensic.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Status QA target phrase appears in curated memory records.",
        metadata={"project": "status-qa"},
    )
    approved = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    disputed = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="DISPUTED_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=approved.id)
    from agent_memory.core.curation import dispute_memory

    dispute_memory(db_path=db_path, memory_type="fact", memory_id=disputed.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the Status QA target phrase?",
            "--preferred-scope",
            "project:status-qa",
            "--status",
            "all",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    facts_by_value = {fact["object_ref_or_value"]: fact["status"] for fact in payload["semantic_facts"]}
    assert facts_by_value == {"APPROVED_OK": "approved", "DISPUTED_BAD": "disputed"}
    assert any("Forensic retrieval" in hint for hint in payload["working_hints"])
    assert payload["verification_plan"]["required"] is True


def test_python_module_cli_review_conflicts_shows_claim_lifecycle_across_statuses(tmp_path: Path) -> None:
    db_path = tmp_path / "review-conflicts.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Review conflicts source text.",
        metadata={"project": "status-qa"},
    )
    approved = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    disputed = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="DISPUTED_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    deprecated = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="OLD_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=approved.id)
    from agent_memory.core.curation import deprecate_memory, dispute_memory

    dispute_memory(db_path=db_path, memory_type="fact", memory_id=disputed.id)
    deprecate_memory(db_path=db_path, memory_type="fact", memory_id=deprecated.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "conflicts",
            "fact",
            str(db_path),
            "Status QA",
            "target_phrase",
            "--scope",
            "project:status-qa",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["claim_slot"] == {
        "subject_ref": "Status QA",
        "predicate": "target_phrase",
        "scope": "project:status-qa",
    }
    assert payload["counts"] == {"approved": 1, "candidate": 0, "disputed": 1, "deprecated": 1}
    assert [item["object_ref_or_value"] for item in payload["facts"]] == ["APPROVED_OK", "DISPUTED_BAD", "OLD_BAD"]
    assert payload["default_retrieval_policy"] == "approved_only"


def test_python_module_cli_review_explain_fact_shows_decision_context(tmp_path: Path) -> None:
    db_path = tmp_path / "review-explain-fact.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Review explain source text.",
        metadata={"project": "status-qa"},
    )
    approved = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    disputed = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="DISPUTED_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.91,
    )
    replacement = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="REPLACEMENT_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.99,
    )
    approve_fact(db_path=db_path, fact_id=approved.id)
    from agent_memory.core.curation import dispute_memory, supersede_fact

    dispute_memory(
        db_path=db_path,
        memory_type="fact",
        memory_id=disputed.id,
        reason="Contradicted by source #1",
        actor="reviewer:test",
        evidence_ids=[source.id],
    )
    supersede_fact(
        db_path=db_path,
        superseded_fact_id=disputed.id,
        replacement_fact_id=replacement.id,
        reason="Replacement has newer evidence",
        actor="reviewer:test",
        evidence_ids=[source.id],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "explain",
            "fact",
            str(db_path),
            str(disputed.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["memory_type"] == "fact"
    assert payload["fact"]["id"] == disputed.id
    assert payload["decision"]["current_status"] == "deprecated"
    assert payload["decision"]["visible_in_default_retrieval"] is False
    assert payload["decision"]["summary"] == "deprecated: hidden from default retrieval; superseded by fact #3"
    assert payload["claim_slot"]["counts"] == {"approved": 2, "candidate": 0, "disputed": 0, "deprecated": 1}
    assert [item["object_ref_or_value"] for item in payload["claim_slot"]["facts"]] == [
        "REPLACEMENT_OK",
        "APPROVED_OK",
        "DISPUTED_BAD",
    ]
    assert [entry["to_status"] for entry in payload["history"]] == ["disputed", "deprecated"]
    assert payload["history"][-1]["reason"] == "Replacement has newer evidence"
    assert payload["replacement_chain"]["superseded_by"][0]["replacement_fact_id"] == replacement.id
    assert payload["default_retrieval_policy"] == "approved_only"


def test_python_module_cli_review_history_shows_transition_reasons(tmp_path: Path) -> None:
    db_path = tmp_path / "review-history.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Review history source text.",
        metadata={"project": "status-qa"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    approve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "approve",
            "fact",
            str(db_path),
            str(fact.id),
            "--reason",
            "Verified during review.",
            "--actor",
            "maintainer",
            "--evidence-ids-json",
            json.dumps([source.id]),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert approve_result.returncode == 0, approve_result.stderr

    history_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "history",
            "fact",
            str(db_path),
            str(fact.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert history_result.returncode == 0, history_result.stderr
    payload = json.loads(history_result.stdout)
    assert payload["memory_type"] == "fact"
    assert payload["memory_id"] == fact.id
    assert payload["history"][0]["from_status"] == "candidate"
    assert payload["history"][0]["to_status"] == "approved"
    assert payload["history"][0]["reason"] == "Verified during review."
    assert payload["history"][0]["actor"] == "maintainer"
    assert payload["history"][0]["evidence_ids"] == [source.id]

def test_python_module_cli_review_supersede_fact_shows_replacement_chain(tmp_path: Path) -> None:
    db_path = tmp_path / "review-supersede.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Status QA target phrase changed from OLD_BAD to APPROVED_OK.",
        metadata={"project": "status-qa"},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="OLD_BAD",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    replacement_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Status QA",
        predicate="target_phrase",
        object_ref_or_value="APPROVED_OK",
        evidence_ids=[source.id],
        scope="project:status-qa",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    supersede_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "supersede",
            "fact",
            str(db_path),
            str(old_fact.id),
            str(replacement_fact.id),
            "--reason",
            "Current note replaces stale value.",
            "--actor",
            "maintainer",
            "--evidence-ids-json",
            json.dumps([source.id]),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert supersede_result.returncode == 0, supersede_result.stderr
    relation_payload = json.loads(supersede_result.stdout)
    assert relation_payload["relation_type"] == "superseded_by"
    assert relation_payload["from_ref"] == f"fact:{old_fact.id}"
    assert relation_payload["to_ref"] == f"fact:{replacement_fact.id}"

    replacements_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "replacements",
            "fact",
            str(db_path),
            str(old_fact.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert replacements_result.returncode == 0, replacements_result.stderr
    payload = json.loads(replacements_result.stdout)
    assert payload["memory_type"] == "fact"
    assert payload["memory_id"] == old_fact.id
    assert payload["replacements"] == [
        {
            "relation_id": relation_payload["id"],
            "superseded_fact_id": old_fact.id,
            "replacement_fact_id": replacement_fact.id,
            "relation_type": "superseded_by",
            "evidence_ids": [source.id],
        }
    ]

    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the Status QA target phrase?",
            "--preferred-scope",
            "project:status-qa",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr
    retrieve_payload = json.loads(retrieve_result.stdout)
    assert [fact["object_ref_or_value"] for fact in retrieve_payload["semantic_facts"]] == ["APPROVED_OK"]
    assert all(fact["status"] == "approved" for fact in retrieve_payload["semantic_facts"])


def test_python_module_cli_hermes_context_outputs_adapter_context(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-context.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Hermes Context uses branch pattern HC-###. "
            "Hermes Context owner is Team Context."
        ),
        metadata={"project": "hermes-context"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Context",
        predicate="branch_pattern",
        object_ref_or_value="HC-###",
        evidence_ids=[source.id],
        scope="project:hermes-context",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Context",
        predicate="owner",
        object_ref_or_value="Team Context",
        evidence_ids=[source.id],
        scope="project:hermes-context",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=branch_fact.id)
    approve_fact(db_path=db_path, fact_id=owner_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-context",
            str(db_path),
            "What branch pattern does Hermes Context use?",
            "--preferred-scope",
            "project:hermes-context",
            "--top-k",
            "2",
            "--max-prompt-lines",
            "8",
            "--max-alternatives",
            "1",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["context"]["should_answer_now"] is True
    assert payload["context"]["should_verify_first"] is False
    assert payload["context"]["payload"]["response_mode"] == "direct"
    assert len(payload["context"]["payload"]["alternative_memories"]) == 1
    prompt_lines = payload["context"]["prompt_text"].splitlines()
    assert len(prompt_lines) == 8
    assert "Reason codes:" not in payload["context"]["prompt_text"]
    assert "Retrieved fact #1: Hermes Context | branch_pattern | HC-###" in payload["context"]["prompt_text"]
    assert payload["outcome"] is None



def test_python_module_cli_codex_prompt_outputs_plain_prompt_text(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-codex-prompt.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Codex Prompt project uses branch pattern CP-###.",
        metadata={"project": "codex-prompt"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Codex Prompt",
        predicate="branch_pattern",
        object_ref_or_value="CP-###",
        evidence_ids=[source.id],
        scope="project:codex-prompt",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=branch_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "codex-prompt",
            str(db_path),
            "What branch pattern does Codex Prompt use?",
            "--preferred-scope",
            "project:codex-prompt",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Memory response mode:" in result.stdout
    assert "Top memory:" in result.stdout
    assert "Codex Prompt" in result.stdout
    assert "Retrieved fact #1: Codex Prompt | branch_pattern | CP-###" in result.stdout
    assert result.stdout.strip()



def test_python_module_cli_claude_prompt_outputs_plain_prompt_text(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-claude-prompt.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Claude Prompt project uses wrapper target CLAUDE_MEMORY_OK.",
        metadata={"project": "claude-prompt"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Claude Prompt",
        predicate="wrapper_target",
        object_ref_or_value="CLAUDE_MEMORY_OK",
        evidence_ids=[source.id],
        scope="project:claude-prompt",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "claude-prompt",
            str(db_path),
            "What wrapper target does Claude Prompt use?",
            "--preferred-scope",
            "project:claude-prompt",
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Memory response mode:" in result.stdout
    assert "Prompt prefix:" in result.stdout
    assert "CLAUDE_MEMORY_OK" in result.stdout
    assert result.stdout.strip()



def test_python_module_cli_hermes_context_applies_verification_results(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-outcome.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes Outcome policy says ALPHA. Hermes Outcome policy says ALPHA.",
        metadata={"project": "hermes-outcome"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Outcome",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:hermes-outcome",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Outcome",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:hermes-outcome",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=low_confidence_fact.id)
    # dispute via CLI command behavior is covered elsewhere; direct helper keeps this test focused on hermes-context output.
    from agent_memory.core.curation import dispute_memory

    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    verification_results = json.dumps(
        [
            {
                "step_action": "cross_check_hidden_alternatives",
                "status": "passed",
                "evidence_summary": "No approved alternative contradicted the primary memory.",
                "target_memory_type": "fact",
                "target_memory_id": low_confidence_fact.id,
            },
            {
                "step_action": "corroborate_before_answer",
                "status": "passed",
                "evidence_summary": "Source text repeated the ALPHA policy note.",
                "target_memory_type": "fact",
                "target_memory_id": low_confidence_fact.id,
            },
        ]
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-context",
            str(db_path),
            "Hermes Outcome policy ALPHA",
            "--preferred-scope",
            "project:hermes-outcome",
            "--verification-results-json",
            verification_results,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["context"]["should_verify_first"] is True
    assert payload["outcome"]["should_answer_now"] is True
    assert payload["outcome"]["should_verify_first"] is False
    assert payload["outcome"]["response_mode_after_verification"] == "cautious"
    assert payload["outcome"]["unresolved_blocking_steps"] == []
    assert payload["outcome"]["prompt_text"].count("Verification result:") == 2



def test_python_module_cli_hermes_context_respects_max_prompt_chars(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-char-budget.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Hermes Char Budget uses branch pattern HCB-###. "
            "Hermes Char Budget owner is Team Budget."
        ),
        metadata={"project": "hermes-char-budget"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Char Budget",
        predicate="branch_pattern",
        object_ref_or_value="HCB-###",
        evidence_ids=[source.id],
        scope="project:hermes-char-budget",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Char Budget",
        predicate="owner",
        object_ref_or_value="Team Budget",
        evidence_ids=[source.id],
        scope="project:hermes-char-budget",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=branch_fact.id)
    approve_fact(db_path=db_path, fact_id=owner_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-context",
            str(db_path),
            "What branch pattern does Hermes Char Budget use?",
            "--preferred-scope",
            "project:hermes-char-budget",
            "--top-k",
            "2",
            "--max-prompt-chars",
            "120",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    prompt_text = payload["context"]["prompt_text"]
    assert len(prompt_text) <= 120
    assert prompt_text.splitlines() == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
    ]
    assert len(payload["context"]["payload"]["alternative_memories"]) == 1



def test_python_module_cli_hermes_context_respects_max_prompt_tokens(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-token-budget.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Hermes Token Budget uses branch pattern HTB-###. "
            "Hermes Token Budget owner is Team Token."
        ),
        metadata={"project": "hermes-token-budget"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Token Budget",
        predicate="branch_pattern",
        object_ref_or_value="HTB-###",
        evidence_ids=[source.id],
        scope="project:hermes-token-budget",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Token Budget",
        predicate="owner",
        object_ref_or_value="Team Token",
        evidence_ids=[source.id],
        scope="project:hermes-token-budget",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=branch_fact.id)
    approve_fact(db_path=db_path, fact_id=owner_fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-context",
            str(db_path),
            "What branch pattern does Hermes Token Budget use?",
            "--preferred-scope",
            "project:hermes-token-budget",
            "--top-k",
            "2",
            "--max-prompt-tokens",
            "24",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    prompt_text = payload["context"]["prompt_text"]
    assert len(prompt_text) <= 96
    assert prompt_text.splitlines() == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
    ]
    assert len(payload["context"]["payload"]["alternative_memories"]) == 1



def test_python_module_cli_hermes_pre_llm_hook_outputs_context_for_hermes_shell_hook_payload(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "module-cli-hermes-pre-llm-hook.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes Hook project uses branch pattern HH-###.",
        metadata={"project": "hermes-hook"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes Hook",
        predicate="branch_pattern",
        object_ref_or_value="HH-###",
        evidence_ids=[source.id],
        scope="project:hermes-hook",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "tool_name": None,
        "tool_input": None,
        "session_id": "test-session",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "What branch pattern does Hermes Hook use?",
            "platform": "cli",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:hermes-hook",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "4",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    hook_response = json.loads(result.stdout)
    assert set(hook_response) == {"context"}
    assert "<agent_memory_context>" in hook_response["context"]
    assert "Memory response mode: direct" in hook_response["context"]
    assert "Top memory: fact" in hook_response["context"]
    assert "HH-###" not in hook_response["context"]  # compact target context, not raw fact dump
    assert "Reason codes:" not in hook_response["context"]

    observations_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "list",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert observations_result.returncode == 0, observations_result.stderr
    observations_payload = json.loads(observations_result.stdout)
    observation = observations_payload["observations"][0]
    assert observation["surface"] == "hermes-pre-llm-hook"
    assert observation["retrieved_memory_refs"] == [f"fact:{fact.id}"]
    assert observation["metadata"] == {"hook_event_name": "pre_llm_call"}



def test_python_module_cli_hermes_pre_llm_hook_records_metadata_only_turn_trace_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-default-turn-trace.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Default Hermes trace recording should store metadata-only ordinary turn traces.",
        metadata={"project": "default-turn-trace"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Default trace recording",
        predicate="posture",
        object_ref_or_value="metadata-only ordinary turn traces",
        evidence_ids=[source.id],
        scope="project:default-turn-trace",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    secret_prompt = "What is the default trace recording posture? token=SHOULD_NOT_APPEAR"
    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-default-turn-trace",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": secret_prompt,
            "platform": "cli",
            "model": "gpt-test",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:default-turn-trace",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Default trace recording" in json.loads(result.stdout)["context"]
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.surface == "hermes-pre-llm-hook"
    assert trace.event_kind == "turn"
    assert trace.scope == "project:default-turn-trace"
    assert trace.session_ref is not None
    assert "real-session-default-turn-trace" not in trace.session_ref
    assert trace.content_sha256 != secret_prompt
    assert trace.summary is None
    assert trace.salience == 0.1
    assert trace.user_emphasis == 0.0
    assert trace.retention_policy == "ephemeral"
    assert trace.related_memory_refs == [f"fact:{fact.id}"]
    trace_json = trace.model_dump_json()
    assert "SHOULD_NOT_APPEAR" not in trace_json
    assert "user_message" not in trace_json
    assert trace.metadata == {
        "hook_event_name": "pre_llm_call",
        "platform": "cli",
        "model": "gpt-test",
        "trace_recording": "default_metadata_only",
        "candidate_policy": "evidence_only",
        "auto_approved": False,
    }



def test_hermes_pre_llm_hook_records_metadata_only_trace_for_empty_retrieval_turn(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-empty-retrieval-turn-trace.db"
    initialize_database(db_path)

    secret_prompt = "Explain a new topic with no matching memory. password=SHOULD_NOT_APPEAR"
    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-empty-retrieval-turn-trace",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": secret_prompt,
            "platform": "cli",
            "model": "gpt-test",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:empty-retrieval-turn-trace",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Top memory: none" in json.loads(result.stdout)["context"]
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.event_kind == "turn"
    assert trace.summary is None
    assert trace.related_memory_refs == []
    trace_json = trace.model_dump_json()
    assert "SHOULD_NOT_APPEAR" not in trace_json
    assert "password" not in trace_json
    assert "user_message" not in trace_json
    assert trace.metadata == {
        "hook_event_name": "pre_llm_call",
        "platform": "cli",
        "model": "gpt-test",
        "trace_recording": "default_metadata_only",
        "candidate_policy": "evidence_only",
        "auto_approved": False,
    }



def test_hermes_pre_llm_hook_records_trace_even_when_no_context_is_injected(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "module-cli-hermes-no-context-turn-trace.db"
    initialize_database(db_path)

    class EmptyContext:
        prompt_text = ""

    monkeypatch.setattr(hermes_hooks, "prepare_hermes_memory_context", lambda *args, **kwargs: EmptyContext())

    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="real-session-no-context-turn-trace",
            cwd=str(tmp_path),
            extra={
                "user_message": "A live turn can be observed even when no memory context is injected.",
                "platform": "cli",
                "model": "gpt-test",
            },
        ),
        HermesPreLlmHookOptions(
            db_path=db_path,
            preferred_scope="project:no-context-turn-trace",
            top_k=1,
        ),
    )

    assert response == {}
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.event_kind == "turn"
    assert trace.scope == "project:no-context-turn-trace"
    assert trace.related_memory_refs == []
    assert trace.metadata == {
        "hook_event_name": "pre_llm_call",
        "platform": "cli",
        "model": "gpt-test",
        "trace_recording": "default_metadata_only",
        "candidate_policy": "evidence_only",
        "auto_approved": False,
    }


def test_python_module_cli_hermes_pre_llm_hook_can_disable_default_turn_trace(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-no-record-trace.db"
    initialize_database(db_path)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-no-record-trace",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "Explain a new topic without recording a trace.",
            "platform": "cli",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:no-record-trace",
            "--no-record-trace",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert list_experience_traces(db_path) == []



def test_python_module_cli_hermes_pre_llm_hook_records_trace_when_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-opt-in-trace.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Opt-in Hermes trace recording stores hash-only turn traces.",
        metadata={"project": "opt-in-trace"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Opt-in trace recording",
        predicate="stores",
        object_ref_or_value="hash-only turn traces",
        evidence_ids=[source.id],
        scope="project:opt-in-trace",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    secret_prompt = "What does opt-in trace recording store? token=SHOULD_NOT_APPEAR"
    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-opt-in-trace",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": secret_prompt,
            "platform": "cli",
            "model": "gpt-test",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:opt-in-trace",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
            "--record-trace",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Opt-in trace recording" in json.loads(result.stdout)["context"]
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.surface == "hermes-pre-llm-hook"
    assert trace.event_kind == "turn"
    assert trace.scope == "project:opt-in-trace"
    assert trace.session_ref is not None
    assert "real-session-opt-in-trace" not in trace.session_ref
    assert trace.content_sha256 != secret_prompt
    assert trace.summary is None
    assert trace.related_memory_refs == [f"fact:{fact.id}"]
    trace_json = trace.model_dump_json()
    assert "SHOULD_NOT_APPEAR" not in trace_json
    assert "user_message" not in trace_json
    assert trace.metadata == {
        "hook_event_name": "pre_llm_call",
        "platform": "cli",
        "model": "gpt-test",
        "trace_recording": "default_metadata_only",
        "candidate_policy": "evidence_only",
        "auto_approved": False,
    }



def test_python_module_cli_hermes_pre_llm_hook_skips_synthetic_doctor_trace_even_when_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-synthetic-trace.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Synthetic hook doctor trace rows should not be recorded.",
        metadata={"project": "synthetic-trace"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Weather",
        predicate="qa_marker",
        object_ref_or_value="SYNTHETIC_TRACE_SKIP",
        evidence_ids=[source.id],
        scope="project:synthetic-trace",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "test-session",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "What is the weather?",
            "conversation_history": [],
            "is_first_turn": True,
            "model": "gpt-4",
            "platform": "cli",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:synthetic-trace",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
            "--record-trace",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_TRACE_SKIP" in json.loads(result.stdout)["context"]
    assert list_experience_traces(db_path) == []



def test_hermes_pre_llm_hook_trace_write_failure_is_non_blocking(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "module-cli-hermes-trace-failure.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes trace write failures should not block memory context injection.",
        metadata={"project": "trace-failure"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Trace write failures",
        predicate="behavior",
        object_ref_or_value="non-blocking",
        evidence_ids=[source.id],
        scope="project:trace-failure",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    def fail_insert(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("trace write unavailable")

    monkeypatch.setattr(hermes_hooks, "insert_experience_trace", fail_insert)
    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="trace-failure-session",
            cwd=str(tmp_path),
            extra={"user_message": "What should trace write failures do?", "platform": "cli"},
        ),
        HermesPreLlmHookOptions(
            db_path=db_path,
            preferred_scope="project:trace-failure",
            top_k=1,
            max_prompt_lines=8,
            record_trace=True,
        ),
    )

    assert "context" in response
    assert "Trace write failures" in response["context"]
    assert list_experience_traces(db_path) == []



def test_python_module_cli_hermes_pre_llm_hook_skips_synthetic_doctor_observation(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-synthetic-observation.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Synthetic hook doctor weather memory should not become dogfood observation data.",
        metadata={"project": "synthetic-hook"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Weather",
        predicate="qa_marker",
        object_ref_or_value="SYNTHETIC_SKIP",
        evidence_ids=[source.id],
        scope="project:synthetic-hook",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "test-session",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "What is the weather?",
            "conversation_history": [],
            "is_first_turn": True,
            "model": "gpt-4",
            "platform": "cli",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:synthetic-hook",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SYNTHETIC_SKIP" in json.loads(result.stdout)["context"]

    observations_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "list",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert observations_result.returncode == 0, observations_result.stderr
    observations_payload = json.loads(observations_result.stdout)
    assert observations_payload["observations"] == []



def test_python_module_cli_hermes_pre_llm_hook_injects_retrieved_memory_context(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-injection-proof.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="The live Hermes QA marker is AM_LIVE_QA_137.",
        metadata={"project": "hermes-injection-proof"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes live QA",
        predicate="marker",
        object_ref_or_value="AM_LIVE_QA_137",
        evidence_ids=[source.id],
        scope="project:hermes-injection-proof",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-shape",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "What is the live Hermes QA marker?",
            "platform": "cli",
        },
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--preferred-scope",
            "project:hermes-injection-proof",
            "--top-k",
            "1",
            "--max-prompt-lines",
            "8",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    hook_response = json.loads(result.stdout)
    assert "<agent_memory_context>" in hook_response["context"]
    assert "Retrieved fact" in hook_response["context"]
    assert "AM_LIVE_QA_137" in hook_response["context"]

    observations_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "observations",
            "list",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert observations_result.returncode == 0, observations_result.stderr
    observations_payload = json.loads(observations_result.stdout)
    assert observations_payload["observations"][0]["retrieved_memory_refs"] == [f"fact:{fact.id}"]



def test_python_module_cli_hermes_pre_llm_hook_derives_path_scope_from_payload_cwd(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "module-cli-hermes-cwd-scope.db"
    project_alpha = tmp_path / "project-alpha"
    project_beta = tmp_path / "project-beta"
    project_alpha.mkdir()
    project_beta.mkdir()
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Alpha and Project Beta use different branch patterns.",
        metadata={"example": "cwd-scope"},
    )
    alpha_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Alpha",
        predicate="branch_pattern",
        object_ref_or_value="ALPHA-###",
        evidence_ids=[source.id],
        scope=scope_from_cwd(str(project_alpha)),
        confidence=0.95,
    )
    beta_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Beta",
        predicate="branch_pattern",
        object_ref_or_value="BETA-###",
        evidence_ids=[source.id],
        scope=scope_from_cwd(str(project_beta)),
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=alpha_fact.id)
    approve_fact(db_path=db_path, fact_id=beta_fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "test-session",
        "cwd": str(project_alpha),
        "extra": {"user_message": "What branch pattern should I use?"},
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
            "--top-k",
            "1",
            "--max-prompt-lines",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    hook_response = json.loads(result.stdout)
    assert "Project Alpha" in hook_response["context"]
    assert "Project Beta" not in hook_response["context"]


def test_python_module_cli_hermes_pre_llm_hook_fails_closed_when_db_is_unavailable(tmp_path: Path) -> None:
    missing_db_path = tmp_path / "missing" / "memory.db"
    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "test-session",
        "cwd": str(tmp_path),
        "extra": {"user_message": "What should I remember?"},
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(missing_db_path),
            "--max-prompt-lines",
            "8",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}


def test_python_module_cli_hermes_hook_config_snippet_outputs_mergeable_yaml_without_writing_config(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "snippet-memory.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text("model:\n  provider: openai-codex\n")
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-hook-config-snippet",
            str(db_path),
            "--preferred-scope",
            "project:snippet",
            "--top-k",
            "3",
            "--max-prompt-lines",
            "8",
            "--max-prompt-chars",
            "640",
            "--max-prompt-tokens",
            "160",
            "--max-alternatives",
            "2",
            "--timeout",
            "12",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    snippet = result.stdout
    assert snippet.startswith("hooks:\n")
    assert "pre_llm_call:" in snippet
    assert "command:" in snippet
    assert "agent-memory hermes-pre-llm-hook" in snippet
    assert "agent_memory.api.cli" not in snippet
    assert str(db_path) in snippet
    assert "--preferred-scope project:snippet" in snippet
    assert "--top-k 3" in snippet
    assert "--max-prompt-lines 8" in snippet
    assert "--max-prompt-chars 640" in snippet
    assert "--max-prompt-tokens 160" in snippet
    assert "--max-alternatives 2" in snippet
    assert "--no-reason-codes" in snippet
    assert "timeout: 12" in snippet
    assert "model:\n  provider: openai-codex\n" == config_path.read_text()



def test_python_module_cli_hermes_install_hook_writes_missing_config_with_snippet(tmp_path: Path) -> None:
    db_path = tmp_path / "install-memory.db"
    config_path = tmp_path / "hermes" / "config.yaml"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-install-hook",
            str(db_path),
            "--config-path",
            str(config_path),
            "--preferred-scope",
            "project:install",
            "--top-k",
            "2",
            "--max-prompt-tokens",
            "100",
            "--no-reason-codes",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["config_path"] == str(config_path)
    assert payload["backup_path"] is None
    assert payload["db_initialized"] is True
    assert db_path.exists()
    config_text = config_path.read_text()
    assert "hooks:" in config_text
    assert "hermes-pre-llm-hook" in config_text
    assert "--preferred-scope project:install" in config_text
    assert "--max-prompt-tokens 100" in config_text
    assert "--no-reason-codes" in config_text



def test_python_module_cli_hermes_install_hook_reports_when_database_already_exists(tmp_path: Path) -> None:
    db_path = tmp_path / "existing-install-memory.db"
    initialize_database(db_path)
    config_path = tmp_path / "config.yaml"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-install-hook",
            str(db_path),
            "--config-path",
            str(config_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["db_initialized"] is False
    assert config_path.exists()



def test_python_module_cli_hermes_bootstrap_defaults_to_user_paths_and_conservative_preset(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": "src", "HOME": str(tmp_path)}
    default_db_path = tmp_path / ".agent-memory" / "memory.db"
    default_config_path = tmp_path / ".hermes" / "config.yaml"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-bootstrap",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["config_path"] == str(default_config_path)
    assert payload["db_initialized"] is True
    assert default_db_path.exists()
    config_text = default_config_path.read_text()
    assert "hermes-pre-llm-hook" in config_text
    assert str(default_db_path) in config_text
    assert "--top-k 1" in config_text
    assert "--max-prompt-lines 6" in config_text
    assert "--max-prompt-chars 800" in config_text
    assert "--max-prompt-tokens 200" in config_text
    assert "--max-verification-steps 1" in config_text
    assert "--max-alternatives 0" in config_text
    assert "--max-guidelines 1" in config_text
    assert "--no-reason-codes" in config_text
    assert "timeout: 8" in config_text


def test_python_module_cli_hermes_hook_config_snippet_can_use_balanced_preset(tmp_path: Path) -> None:
    db_path = tmp_path / "balanced-snippet-memory.db"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-hook-config-snippet",
            str(db_path),
            "--preset",
            "balanced",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    snippet = result.stdout
    assert "--top-k 3" in snippet
    assert "--max-prompt-lines 8" in snippet
    assert "--max-prompt-chars 1200" in snippet
    assert "--max-prompt-tokens 300" in snippet
    assert "--max-alternatives 2" in snippet
    assert "--no-reason-codes" not in snippet
    assert "timeout: 12" in snippet



def test_python_module_cli_hermes_doctor_reports_missing_setup_and_fix_command(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": "src", "HOME": str(tmp_path)}

    result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "hermes-doctor"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "needs_setup"
    assert payload["db_exists"] is False
    assert payload["config_exists"] is False
    assert payload["hook_installed"] is False
    assert any(check["name"] == "database_exists" and check["ok"] is False for check in payload["checks"])
    assert "agent-memory bootstrap" in payload["recommended_command"]
    assert "uv run" not in payload["recommended_command"]



def test_python_module_cli_hermes_doctor_reports_ok_after_bootstrap(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": "src", "HOME": str(tmp_path)}
    cwd = Path(__file__).resolve().parents[1]

    bootstrap = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "hermes-bootstrap"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "hermes-doctor"],
        cwd=cwd,
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
    assert all(check["ok"] is True for check in payload["checks"])



def test_python_module_cli_bootstrap_and_doctor_aliases_match_hermes_commands(tmp_path: Path) -> None:
    env = {**os.environ, "PYTHONPATH": "src", "HOME": str(tmp_path)}
    cwd = Path(__file__).resolve().parents[1]

    bootstrap = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "bootstrap"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    assert bootstrap.returncode == 0, bootstrap.stderr

    doctor = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "doctor"],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )

    assert doctor.returncode == 0, doctor.stderr
    payload = json.loads(doctor.stdout)
    assert payload["status"] == "ok"
    assert payload["hook_installed"] is True
    assert payload["hook_occurrences"] == 1



def test_python_module_cli_hermes_install_hook_merges_existing_pre_llm_hooks(tmp_path: Path) -> None:
    db_path = tmp_path / "install-merge-memory.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "hooks:\n"
        "  pre_llm_call:\n"
        "    - command: \"/existing/context-hook.py\"\n"
        "      timeout: 15\n"
        "  on_session_end:\n"
        "    - command: \"/existing/session-hook.py\"\n"
        "      timeout: 15\n"
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-install-hook",
            str(db_path),
            "--config-path",
            str(config_path),
            "--preferred-scope",
            "project:merge",
            "--max-prompt-tokens",
            "120",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["reason"] == "merged_existing_hooks_block"
    assert payload["backup_path"] is not None
    config_text = config_path.read_text()
    assert config_text.count("pre_llm_call:") == 1
    assert "/existing/context-hook.py" in config_text
    assert "/existing/session-hook.py" in config_text
    assert "hermes-pre-llm-hook" in config_text
    assert "--preferred-scope project:merge" in config_text
    assert config_text.index("hermes-pre-llm-hook") < config_text.index("on_session_end:")


def test_python_module_cli_hermes_install_hook_preserves_two_space_hook_list_style(tmp_path: Path) -> None:
    db_path = tmp_path / "install-two-space-memory.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "hooks:\n"
        "  pre_llm_call:\n"
        "  - command: /existing/context-hook.py\n"
        "    timeout: 15\n"
        "  on_session_end:\n"
        "  - command: /existing/session-hook.py\n"
        "    timeout: 15\n"
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-install-hook",
            str(db_path),
            "--config-path",
            str(config_path),
            "--preferred-scope",
            "project:two-space",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["reason"] == "merged_existing_hooks_block"
    config_text = config_path.read_text()
    assert config_text.count("pre_llm_call:") == 1
    assert "/existing/context-hook.py" in config_text
    assert "/existing/session-hook.py" in config_text
    assert "hermes-pre-llm-hook" in config_text
    assert "--preferred-scope project:two-space" in config_text
    assert "timeout: 15\n  - command: \"agent-memory" in config_text
    assert "timeout: 15\n    - command:" not in config_text
    assert config_text.index("/existing/context-hook.py") < config_text.index("hermes-pre-llm-hook") < config_text.index("on_session_end:")


def test_python_module_cli_hermes_install_hook_upgrades_legacy_python_module_hook_command(tmp_path: Path) -> None:
    db_path = tmp_path / "install-upgrade-memory.db"
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        "model:\n"
        "  provider: openai-codex\n"
        "hooks:\n"
        "  pre_llm_call:\n"
        "    - command: \"/legacy/python -m agent_memory.api.cli hermes-pre-llm-hook "
        f"{db_path} --top-k 1\"\n"
        "      timeout: 10\n"
        "    - command: \"/existing/context-hook.py\"\n"
        "      timeout: 15\n"
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-install-hook",
            str(db_path),
            "--config-path",
            str(config_path),
            "--top-k",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["changed"] is True
    assert payload["reason"] == "updated_existing_hook"
    assert payload["backup_path"] is not None
    config_text = config_path.read_text()
    assert "/existing/context-hook.py" in config_text
    assert "/legacy/python" not in config_text
    assert "agent_memory.api.cli" not in config_text
    assert config_text.count("agent-memory hermes-pre-llm-hook") == 1
    assert "--top-k 3" in config_text



def test_python_module_cli_hermes_install_hook_is_idempotent_for_existing_command(tmp_path: Path) -> None:
    db_path = tmp_path / "install-idempotent-memory.db"
    config_path = tmp_path / "config.yaml"
    env = {**os.environ, "PYTHONPATH": "src"}
    base_args = [
        sys.executable,
        "-m",
        "agent_memory.api.cli",
        "hermes-install-hook",
        str(db_path),
        "--config-path",
        str(config_path),
        "--top-k",
        "2",
    ]

    first = subprocess.run(
        base_args,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    second = subprocess.run(
        base_args,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert json.loads(first.stdout)["changed"] is True
    second_payload = json.loads(second.stdout)
    assert second_payload["changed"] is False
    assert second_payload["reason"] == "already_installed"
    assert config_path.read_text().count("hermes-pre-llm-hook") == 1



def test_python_module_cli_hermes_hook_config_snippet_defaults_to_installed_agent_memory_command(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "snippet-default.db"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-hook-config-snippet",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    snippet = result.stdout
    assert "agent-memory hermes-pre-llm-hook" in snippet
    assert sys.executable not in snippet
    assert "agent_memory.api.cli" not in snippet
    assert "--top-k 1" in snippet
    assert "--max-prompt-lines 6" in snippet
    assert "--max-prompt-chars 800" in snippet
    assert "--max-prompt-tokens 200" in snippet
    assert "--max-alternatives 0" in snippet
    assert "--no-reason-codes" in snippet
    assert "timeout: 8" in snippet



def test_python_module_cli_hermes_pre_llm_hook_noops_for_non_pre_llm_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-pre-llm-hook-noop.db"
    initialize_database(db_path)
    hook_payload = {
        "hook_event_name": "post_tool_call",
        "tool_name": "terminal",
        "tool_input": {"command": "echo ok"},
        "session_id": "test-session",
        "cwd": str(tmp_path),
        "extra": {},
    }
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        input=json.dumps(hook_payload),
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {}



def test_python_module_cli_retrieve_outputs_json_packet(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-retrieve.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes stores sessions in SQLite with FTS5 search.",
        metadata={"project": "hermes"},
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

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "Where does Hermes store sessions?",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    packet = json.loads(result.stdout)
    assert packet["semantic_facts"][0]["subject_ref"] == "Hermes"
    assert packet["procedural_guidance"] == []


def _relation_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as connection:
        return connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]


def test_python_module_cli_review_relate_conflict_records_reviewed_relation_without_status_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "review-relate-conflict.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Human review accepted that Agent Memory E5 has two conflicting rollout modes during migration.",
        metadata={"project": "agent-memory-e5"},
    )
    first = create_candidate_fact(
        db_path=db_path,
        subject_ref="Agent Memory E5",
        predicate="rollout_mode",
        object_ref_or_value="strict supersession",
        evidence_ids=[source.id],
        scope="project:e5-reviewed-relations",
        confidence=0.91,
    )
    second = create_candidate_fact(
        db_path=db_path,
        subject_ref="Agent Memory E5",
        predicate="rollout_mode",
        object_ref_or_value="temporary coexistence",
        evidence_ids=[source.id],
        scope="project:e5-reviewed-relations",
        confidence=0.88,
    )
    approve_fact(db_path=db_path, fact_id=first.id)
    approve_fact(db_path=db_path, fact_id=second.id)
    before_relations = _relation_count(db_path)

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "relate-conflict",
            "fact",
            str(db_path),
            str(first.id),
            str(second.id),
            "--actor",
            "maintainer",
            "--reason",
            "Reviewed E4 conflict preflight and accepted temporary coexistence before a later supersession decision.",
            "--evidence-ids-json",
            json.dumps([source.id]),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_review_conflict_relation"
    assert payload["memory_type"] == "fact"
    assert payload["read_only"] is False
    assert payload["status_mutation"] is False
    assert payload["relation"]["relation_type"] == "conflicts_with"
    assert payload["relation"]["from_ref"] == f"fact:{first.id}"
    assert payload["relation"]["to_ref"] == f"fact:{second.id}"
    assert payload["relation"]["review_actor"] == "maintainer"
    assert "temporary coexistence" in payload["relation"]["review_reason"]
    assert payload["relation"]["evidence_ids"] == [source.id]
    assert payload["claim_slot"] == {
        "subject_ref": "Agent Memory E5",
        "predicate": "rollout_mode",
        "scope": "project:e5-reviewed-relations",
    }
    assert _relation_count(db_path) == before_relations + 1

    conflicts_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "conflicts",
            "fact",
            str(db_path),
            "Agent Memory E5",
            "rollout_mode",
            "--scope",
            "project:e5-reviewed-relations",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert conflicts_result.returncode == 0, conflicts_result.stderr
    conflicts_payload = json.loads(conflicts_result.stdout)
    assert conflicts_payload["conflict_relations"] == [
        {
            "relation_id": payload["relation"]["id"],
            "left_fact_id": first.id,
            "right_fact_id": second.id,
            "relation_type": "conflicts_with",
            "review_actor": "maintainer",
            "review_reason": "Reviewed E4 conflict preflight and accepted temporary coexistence before a later supersession decision.",
            "evidence_ids": [source.id],
        }
    ]
    statuses = {fact["id"]: fact["status"] for fact in conflicts_payload["facts"]}
    assert statuses[first.id] == "approved"
    assert statuses[second.id] == "approved"


def test_python_module_cli_review_relate_conflict_requires_same_claim_slot_and_review_metadata(tmp_path: Path) -> None:
    db_path = tmp_path / "review-relate-conflict-guard.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Human review must provide metadata and same-claim-slot facts before recording conflict relations.",
        metadata={"project": "agent-memory-e5"},
    )
    first = create_candidate_fact(
        db_path=db_path,
        subject_ref="Agent Memory E5",
        predicate="rollout_mode",
        object_ref_or_value="strict supersession",
        evidence_ids=[source.id],
        scope="project:e5-reviewed-relations",
        confidence=0.91,
    )
    different_slot = create_candidate_fact(
        db_path=db_path,
        subject_ref="Agent Memory E5",
        predicate="owner",
        object_ref_or_value="reviewer",
        evidence_ids=[source.id],
        scope="project:e5-reviewed-relations",
        confidence=0.88,
    )
    before_relations = _relation_count(db_path)

    env = {**os.environ, "PYTHONPATH": "src"}
    missing_metadata = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "relate-conflict",
            "fact",
            str(db_path),
            str(first.id),
            str(different_slot.id),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_metadata.returncode != 0
    assert _relation_count(db_path) == before_relations

    cross_slot = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "review",
            "relate-conflict",
            "fact",
            str(db_path),
            str(first.id),
            str(different_slot.id),
            "--actor",
            "maintainer",
            "--reason",
            "Tried to link different claim slots.",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert cross_slot.returncode != 0
    assert "same claim slot" in cross_slot.stderr
    assert _relation_count(db_path) == before_relations


def test_initialize_database_adds_review_columns_to_existing_relations_table(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy-relations.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_ref TEXT NOT NULL,
                relation_type TEXT NOT NULL,
                to_ref TEXT NOT NULL,
                weight REAL NOT NULL DEFAULT 1.0,
                evidence_ids_json TEXT NOT NULL,
                confidence REAL NOT NULL DEFAULT 0.5,
                valid_from TEXT,
                valid_to TEXT
            )
            """
        )
    initialize_database(db_path)

    relation = insert_relation(
        db_path,
        from_ref="fact:1",
        relation_type="conflicts_with",
        to_ref="fact:2",
        evidence_ids=[9],
        review_actor="maintainer",
        review_reason="legacy relation table gained review metadata columns",
    )

    assert relation.review_actor == "maintainer"
    assert relation.review_reason == "legacy relation table gained review metadata columns"
    assert relation.reviewed_at is not None


def test_python_module_retrieval_policy_preview_is_read_only_and_flags_reviewed_conflicts(tmp_path: Path) -> None:
    db_path = tmp_path / "policy-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X branch policy has conflicting reviewed evidence.",
        metadata={"project": "project-x", "raw_prompt": "password=SUPERSECRET token=abc123"},
    )
    older_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.91,
    )
    newer_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="PX-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.92,
    )
    approve_fact(db_path=db_path, fact_id=older_fact.id)
    approve_fact(db_path=db_path, fact_id=newer_fact.id)
    record_memory_retrieval(db_path, memory_type="fact", memory_id=newer_fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{older_fact.id}",
        relation_type="conflicts_with",
        to_ref=f"fact:{newer_fact.id}",
        evidence_ids=[source.id],
        review_actor="maintainer",
        review_reason="same claim slot has contradictory values",
    )

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_before = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        relation_count_before = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "policy-preview",
            str(db_path),
            "What branch pattern does Project X use? password=SUPERSECRET",
            "--preferred-scope",
            "project:project-x",
            "--limit",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout
    assert "raw_prompt" not in result.stdout
    assert "query_preview" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "retrieval_policy_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_policy"] == "approved_only"
    assert payload["default_retrieval_unchanged"] is True
    assert payload["query"] == {"stored": False, "sha256_present": True}
    assert payload["policy"] == "conservative_preview"
    assert payload["retrieved_counts"]["facts"] == 1

    fact_projection = payload["memory_projections"][0]
    assert fact_projection["memory_ref"] == f"fact:{newer_fact.id}"
    assert fact_projection["current_status"] == "approved"
    assert fact_projection["current_visibility"] == "visible_in_default_retrieval"
    assert fact_projection["preview_decision"]["action"] == "flag_for_review"
    assert "reviewed_conflict_relation" in fact_projection["signals"]
    assert fact_projection["relation_policy"]["reviewed_conflict_count"] == 1
    assert fact_projection["activation_policy"]["retrieval_count"] == 1
    assert fact_projection["score_components"]["reinforcement_score"] >= 0

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_after = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        relation_count_after = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert retrieval_counts_after == retrieval_counts_before
    assert relation_count_after == relation_count_before


def test_python_module_retrieval_policy_preview_excludes_superseded_default_fact_without_retrieval_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "policy-preview-superseded.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X moved from EP branches to PX branches.",
        metadata={"project": "project-x"},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    replacement_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="PX-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)
    supersede_fact(
        db_path=db_path,
        superseded_fact_id=old_fact.id,
        replacement_fact_id=replacement_fact.id,
        reason="new policy supersedes the old branch pattern",
        actor="maintainer",
        evidence_ids=[source.id],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "policy-preview",
            str(db_path),
            "What branch pattern does Project X use?",
            "--preferred-scope",
            "project:project-x",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["retrieved_counts"]["facts"] == 1
    projection = payload["memory_projections"][0]
    assert projection["memory_ref"] == f"fact:{replacement_fact.id}"
    assert projection["preview_decision"]["action"] == "include"
    assert projection["relation_policy"]["superseded_by_count"] == 0
    assert "superseded" not in projection["signals"]


def test_python_module_retrieval_ranker_preview_compares_reinforcement_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "ranker-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project Y uses the Nimbus deployment pattern. Project Y also references legacy Nimbus notes.",
        metadata={"raw_prompt": "password=SUPERSECRET token=abc123"},
    )
    first_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Y",
        predicate="deployment_pattern",
        object_ref_or_value="Nimbus primary",
        evidence_ids=[source.id],
        scope="project:project-y",
        confidence=0.95,
    )
    reinforced_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Y",
        predicate="deployment_note",
        object_ref_or_value="Nimbus reinforced",
        evidence_ids=[source.id],
        scope="project:project-y",
        confidence=0.5,
    )
    approve_fact(db_path=db_path, fact_id=first_fact.id)
    approve_fact(db_path=db_path, fact_id=reinforced_fact.id)
    for _ in range(4):
        record_memory_retrieval(db_path, memory_type="fact", memory_id=reinforced_fact.id)

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_before = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        relation_count_before = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "ranker-preview",
            str(db_path),
            "Project Y Nimbus deployment? password=SUPERSECRET",
            "--preferred-scope",
            "project:project-y",
            "--limit",
            "5",
            "--reinforcement-weight",
            "0.25",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout
    assert "raw_prompt" not in result.stdout
    assert "query_preview" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "retrieval_ranker_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["policy"] == "reinforcement_aware_preview"
    assert payload["query"] == {"stored": False, "sha256_present": True}
    assert payload["ranker_parameters"]["reinforcement_weight"] == 0.25

    candidates_by_ref = {candidate["memory_ref"]: candidate for candidate in payload["candidates"]}
    reinforced_projection = candidates_by_ref[f"fact:{reinforced_fact.id}"]
    assert reinforced_projection["activation_policy"]["retrieval_count"] == 4
    assert reinforced_projection["preview_score_components"]["reinforcement_delta"] > 0
    assert reinforced_projection["preview_score_components"]["preview_total_score"] > reinforced_projection["baseline_score_components"]["total_score"]
    assert any(change["memory_ref"] == f"fact:{reinforced_fact.id}" for change in payload["rank_changes"])

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_after = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        relation_count_after = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert retrieval_counts_after == retrieval_counts_before
    assert relation_count_after == relation_count_before


def test_python_module_retrieval_ranker_preview_requires_positive_reinforcement_weight(tmp_path: Path) -> None:
    db_path = tmp_path / "ranker-preview-validation.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "ranker-preview",
            str(db_path),
            "anything",
            "--reinforcement-weight",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "reinforcement weight must be > 0" in result.stderr



def test_python_module_retrieval_decay_preview_penalizes_stale_weak_memory_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "decay-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project Z uses Zephyr memory. Zephyr stable memory is connected. Zephyr stale memory is isolated.",
        metadata={"raw_prompt": "password=SUPERSECRET token=abc123"},
    )
    stale_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="stale_note",
        object_ref_or_value="Zephyr stale isolated memory",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.55,
    )
    protected_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="stable_note",
        object_ref_or_value="Zephyr stable connected memory",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.85,
    )
    approve_fact(db_path=db_path, fact_id=stale_fact.id)
    approve_fact(db_path=db_path, fact_id=protected_fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{protected_fact.id}",
        relation_type="supports",
        to_ref="concept:zephyr-memory",
        evidence_ids=[source.id],
        confidence=0.9,
    )

    retrieve_memory_packet(
        db_path,
        query="Zephyr stale memory",
        preferred_scope="project:project-z",
        limit=5,
        observation_surface="cli",
        observation_metadata={"query_preview": "SUPERSECRET should not leak"},
    )
    for _ in range(4):
        retrieve_memory_packet(
            db_path,
            query="Zephyr stable memory",
            preferred_scope="project:project-z",
            limit=5,
            observation_surface="hermes",
            observation_metadata={"raw_prompt": "SUPERSECRET should not leak"},
        )

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_before = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        observation_count_before = connection.execute("SELECT COUNT(*) FROM retrieval_observations").fetchone()[0]
        activation_count_before = connection.execute("SELECT COUNT(*) FROM memory_activations").fetchone()[0]
        relation_count_before = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "decay-preview",
            str(db_path),
            "Project Z Zephyr memory? password=SUPERSECRET",
            "--preferred-scope",
            "project:project-z",
            "--limit",
            "5",
            "--decay-weight",
            "0.5",
            "--frequent-threshold",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout
    assert "raw_prompt" not in result.stdout
    assert "query_preview" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "retrieval_decay_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["policy"] == "decay_risk_penalty_preview"
    assert payload["query"] == {"stored": False, "sha256_present": True}
    assert payload["ranker_parameters"]["decay_weight"] == 0.5
    assert payload["ranker_parameters"]["frequent_threshold"] == 3

    candidates_by_ref = {candidate["memory_ref"]: candidate for candidate in payload["candidates"]}
    stale_projection = candidates_by_ref[f"fact:{stale_fact.id}"]
    protected_projection = candidates_by_ref[f"fact:{protected_fact.id}"]
    assert stale_projection["decay_risk"]["score"] > protected_projection["decay_risk"]["score"]
    assert stale_projection["preview_score_components"]["decay_penalty"] > 0
    assert stale_projection["preview_score_components"]["preview_total_score"] < stale_projection["baseline_score_components"]["total_score"]
    assert "isolated_memory" in stale_projection["decay_risk"]["signals"]
    assert "protected_from_age_only_decay" in protected_projection["decay_risk"]["signals"]
    assert protected_projection["advisory"]["action"] == "compare_only"
    assert any(change["memory_ref"] == f"fact:{stale_fact.id}" for change in payload["rank_changes"])

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_after = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        observation_count_after = connection.execute("SELECT COUNT(*) FROM retrieval_observations").fetchone()[0]
        activation_count_after = connection.execute("SELECT COUNT(*) FROM memory_activations").fetchone()[0]
        relation_count_after = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert retrieval_counts_after == retrieval_counts_before
    assert observation_count_after == observation_count_before
    assert activation_count_after == activation_count_before
    assert relation_count_after == relation_count_before


def test_python_module_retrieval_decay_preview_marks_superseded_memory_excluded(tmp_path: Path) -> None:
    db_path = tmp_path / "decay-preview-superseded.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project Z Zephyr old path. Project Z Zephyr new path.",
        metadata={},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z old",
        predicate="memory_path",
        object_ref_or_value="Zephyr old path",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.9,
    )
    new_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z new",
        predicate="memory_path",
        object_ref_or_value="Zephyr new path",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.9,
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)
    approve_fact(db_path=db_path, fact_id=new_fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{old_fact.id}",
        relation_type="superseded_by",
        to_ref=f"fact:{new_fact.id}",
        evidence_ids=[source.id],
        confidence=0.95,
        review_actor="reviewer:alice",
        review_reason="new path replaces old path",
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "decay-preview",
            str(db_path),
            "Project Z Zephyr path",
            "--preferred-scope",
            "project:project-z",
            "--limit",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    candidates_by_ref = {candidate["memory_ref"]: candidate for candidate in payload["candidates"]}
    old_projection = candidates_by_ref[f"fact:{old_fact.id}"]
    assert old_projection["advisory"]["action"] == "exclude"
    assert old_projection["preview_rank"] is None
    assert "superseded_memory" in old_projection["advisory"]["reason_codes"]
    assert any(change["memory_ref"] == f"fact:{old_fact.id}" for change in payload["rank_changes"])


def test_python_module_retrieval_decay_preview_requires_positive_decay_weight(tmp_path: Path) -> None:
    db_path = tmp_path / "decay-preview-validation.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "decay-preview",
            str(db_path),
            "anything",
            "--decay-weight",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "decay weight must be > 0" in result.stderr


def test_python_module_retrieval_graph_neighborhood_preview_boosts_connected_reinforced_memory_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "graph-neighborhood-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content=(
            "Project N uses Nebula core memory. "
            "Project N uses Nebula connected memory. "
            "Project N uses Nebula isolated memory."
        ),
        metadata={"raw_prompt": "password=SUPERSECRET token=abc123"},
    )
    core_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project N",
        predicate="core_memory",
        object_ref_or_value="Nebula core memory",
        evidence_ids=[source.id],
        scope="project:project-n",
        confidence=0.9,
    )
    connected_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project N",
        predicate="connected_memory",
        object_ref_or_value="Nebula connected memory",
        evidence_ids=[source.id],
        scope="project:project-n",
        confidence=0.82,
    )
    isolated_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project N",
        predicate="isolated_memory",
        object_ref_or_value="Nebula isolated memory",
        evidence_ids=[source.id],
        scope="project:project-n",
        confidence=0.84,
    )
    approve_fact(db_path=db_path, fact_id=core_fact.id)
    approve_fact(db_path=db_path, fact_id=connected_fact.id)
    approve_fact(db_path=db_path, fact_id=isolated_fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{core_fact.id}",
        relation_type="supports",
        to_ref=f"fact:{connected_fact.id}",
        evidence_ids=[source.id],
        confidence=0.95,
    )
    insert_relation(
        db_path,
        from_ref=f"fact:{connected_fact.id}",
        relation_type="supports",
        to_ref="concept:nebula",
        evidence_ids=[source.id],
        confidence=0.8,
    )

    for _ in range(4):
        retrieve_memory_packet(
            db_path,
            query="Nebula core memory",
            preferred_scope="project:project-n",
            limit=5,
            observation_surface="hermes",
            observation_metadata={"query_preview": "SUPERSECRET should not leak"},
        )

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_before = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        observation_count_before = connection.execute("SELECT COUNT(*) FROM retrieval_observations").fetchone()[0]
        activation_count_before = connection.execute("SELECT COUNT(*) FROM memory_activations").fetchone()[0]
        relation_count_before = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "graph-neighborhood-preview",
            str(db_path),
            "Project N Nebula memory password=SUPERSECRET",
            "--preferred-scope",
            "project:project-n",
            "--limit",
            "5",
            "--depth",
            "1",
            "--graph-weight",
            "0.4",
            "--graph-cap",
            "0.6",
            "--neighbor-reinforcement-weight",
            "0.25",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "abc123" not in result.stdout
    assert "raw_prompt" not in result.stdout
    assert "query_preview" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "retrieval_graph_neighborhood_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["policy"] == "bounded_graph_neighborhood_reinforcement_preview"
    assert payload["query"] == {"stored": False, "sha256_present": True}
    assert payload["ranker_parameters"]["depth"] == 1
    assert payload["ranker_parameters"]["graph_weight"] == 0.4
    assert payload["ranker_parameters"]["graph_cap"] == 0.6
    assert payload["ranker_parameters"]["neighbor_reinforcement_weight"] == 0.25

    candidates_by_ref = {candidate["memory_ref"]: candidate for candidate in payload["candidates"]}
    connected_projection = candidates_by_ref[f"fact:{connected_fact.id}"]
    isolated_projection = candidates_by_ref[f"fact:{isolated_fact.id}"]
    assert connected_projection["graph_neighborhood"]["bounded"] is True
    assert connected_projection["graph_neighborhood"]["depth"] == 1
    assert f"fact:{core_fact.id}" in connected_projection["graph_neighborhood"]["neighbor_refs"]
    assert connected_projection["preview_score_components"]["graph_neighborhood_delta"] > 0
    assert connected_projection["preview_score_components"]["preview_total_score"] > connected_projection["baseline_score_components"]["total_score"]
    assert "bounded_graph_neighbor_support" in connected_projection["advisory"]["reason_codes"]
    assert isolated_projection["preview_score_components"]["graph_neighborhood_delta"] == 0
    assert any(change["memory_ref"] == f"fact:{connected_fact.id}" for change in payload["rank_changes"])

    with sqlite3.connect(db_path) as connection:
        retrieval_counts_after = {
            row[0]: row[1]
            for row in connection.execute("SELECT id, retrieval_count FROM facts").fetchall()
        }
        observation_count_after = connection.execute("SELECT COUNT(*) FROM retrieval_observations").fetchone()[0]
        activation_count_after = connection.execute("SELECT COUNT(*) FROM memory_activations").fetchone()[0]
        relation_count_after = connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0]
    assert retrieval_counts_after == retrieval_counts_before
    assert observation_count_after == observation_count_before
    assert activation_count_after == activation_count_before
    assert relation_count_after == relation_count_before


def test_python_module_retrieval_graph_neighborhood_preview_respects_depth_bound(tmp_path: Path) -> None:
    db_path = tmp_path / "graph-neighborhood-depth.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project N Nebula first hop memory. Project N Nebula second hop memory.",
        metadata={},
    )
    first = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project N",
        predicate="first_hop",
        object_ref_or_value="Nebula first hop memory",
        evidence_ids=[source.id],
        scope="project:project-n",
        confidence=0.8,
    )
    second = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project N",
        predicate="second_hop",
        object_ref_or_value="Nebula second hop memory",
        evidence_ids=[source.id],
        scope="project:project-n",
        confidence=0.8,
    )
    approve_fact(db_path=db_path, fact_id=first.id)
    approve_fact(db_path=db_path, fact_id=second.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{first.id}",
        relation_type="supports",
        to_ref="concept:nebula",
        evidence_ids=[source.id],
    )
    insert_relation(
        db_path,
        from_ref="concept:nebula",
        relation_type="supports",
        to_ref=f"fact:{second.id}",
        evidence_ids=[source.id],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "graph-neighborhood-preview",
            str(db_path),
            "Project N Nebula memory",
            "--preferred-scope",
            "project:project-n",
            "--limit",
            "5",
            "--depth",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    candidates_by_ref = {candidate["memory_ref"]: candidate for candidate in payload["candidates"]}
    first_neighbors = candidates_by_ref[f"fact:{first.id}"]["graph_neighborhood"]["neighbor_refs"]
    second_neighbors = candidates_by_ref[f"fact:{second.id}"]["graph_neighborhood"]["neighbor_refs"]
    assert "concept:nebula" in first_neighbors
    assert f"fact:{second.id}" not in first_neighbors
    assert "concept:nebula" in second_neighbors
    assert f"fact:{first.id}" not in second_neighbors


def test_python_module_retrieval_graph_neighborhood_preview_requires_positive_graph_weight(tmp_path: Path) -> None:
    db_path = tmp_path / "graph-neighborhood-validation.db"
    initialize_database(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieval",
            "graph-neighborhood-preview",
            str(db_path),
            "anything",
            "--graph-weight",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "graph weight must be > 0" in result.stderr



def test_hermes_pre_llm_hook_records_explicit_remember_intent_as_review_trace_without_approval(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-intent-trace.db"
    initialize_database(db_path)

    payload = HermesShellHookPayload(
        hook_event_name="pre_llm_call",
        session_id="real-remember-session",
        cwd=str(tmp_path),
        extra={
            "user_message": "Remember this: Project G1 prefers explicit review before long-term memory approval.",
            "platform": "cli",
            "model": "gpt-test",
        },
    )
    response = hermes_hooks.build_pre_llm_hook_context(
        payload,
        HermesPreLlmHookOptions(
            db_path=db_path,
            preferred_scope="project:g1",
            record_trace=True,
        ),
    )

    assert "context" in response
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.surface == "hermes-pre-llm-hook"
    assert trace.event_kind == "remember_intent"
    assert trace.scope == "project:g1"
    assert trace.retention_policy == "review"
    assert trace.salience == 1.0
    assert trace.user_emphasis == 1.0
    assert trace.summary == "Project G1 prefers explicit review before long-term memory approval."
    assert trace.related_memory_refs == []
    assert trace.metadata == {
        "hook_event_name": "pre_llm_call",
        "platform": "cli",
        "model": "gpt-test",
        "trace_recording": "opt_in",
        "remember_intent": "explicit",
        "candidate_policy": "review_required",
        "auto_approved": False,
        "secret_scan": "passed",
    }

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM procedures").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 0

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "candidates",
            str(db_path),
            "--min-evidence",
            "1",
            "--top",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Remember this:" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_consolidation_candidates"
    assert payload["read_only"] is True
    candidate = payload["candidates"][0]
    assert candidate["evidence_count"] == 1
    assert candidate["event_kind_counts"] == {"remember_intent": 1}
    assert candidate["retention_policy_counts"] == {"review": 1}
    assert candidate["user_emphasis_total"] == 1.0
    assert candidate["safe_summaries"] == ["Project G1 prefers explicit review before long-term memory approval."]


def test_hermes_pre_llm_hook_does_not_create_remember_candidate_for_ordinary_turn(tmp_path: Path) -> None:
    db_path = tmp_path / "ordinary-turn-no-remember-candidate.db"
    initialize_database(db_path)

    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="ordinary-session",
            cwd=str(tmp_path),
            extra={"user_message": "Please explain how review candidates work.", "platform": "cli"},
        ),
        HermesPreLlmHookOptions(db_path=db_path, preferred_scope="project:g1", record_trace=True),
    )

    assert "context" in response
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    assert traces[0].event_kind == "turn"
    assert traces[0].retention_policy == "ephemeral"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0


def test_hermes_pre_llm_hook_skips_secret_like_remember_intent_without_leaking_raw_text(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-secret-skip.db"
    initialize_database(db_path)
    secret_prompt = "remember this: api_key=SUPERSECRET should never be stored"

    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="secret-remember-session",
            cwd=str(tmp_path),
            extra={"user_message": secret_prompt, "platform": "cli"},
        ),
        HermesPreLlmHookOptions(db_path=db_path, preferred_scope="project:g1", record_trace=True),
    )

    assert "context" in response
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    assert traces[0].event_kind == "turn"
    assert traces[0].retention_policy == "ephemeral"
    trace_json = traces[0].model_dump_json()
    assert "SUPERSECRET" not in trace_json
    assert "api_key" not in trace_json
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "candidates",
            str(db_path),
            "--min-evidence",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "api_key" not in result.stdout
    candidates = json.loads(result.stdout)["candidates"]
    assert all(candidate["event_kind_counts"] != {"remember_intent": 1} for candidate in candidates)



def test_consolidation_auto_approve_remember_preferences_is_default_dry_run_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-auto-approve-dry-run.db"
    initialize_database(db_path)
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="e" * 64,
        summary="User prefers concise Korean handoffs.",
        scope="project:g2",
        session_ref="session:auto-dry-run",
        salience=1.0,
        user_emphasis=1.0,
        retention_policy="review",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        },
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "auto-approve",
            "remember-preferences",
            str(db_path),
            "--policy",
            "remember-preferences-v1",
            "--scope",
            "project:g2",
            "--actor",
            "agent-memory:g2-test",
            "--reason",
            "G2 dry-run policy test",
            "--limit",
            "50",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "remember_preference_auto_approval_report"
    assert payload["policy"] == "remember-preferences-v1"
    assert payload["apply"] is False
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["eligible_count"] == 1
    assert payload["approved_count"] == 0
    assert payload["blocked_count"] == 0
    assert payload["candidates"][0]["decision"] == "would_approve"
    assert payload["candidates"][0]["proposed_fact"] == {
        "subject_ref": "user",
        "predicate": "prefers",
        "object_ref_or_value": "concise Korean handoffs.",
        "scope": "project:g2",
    }

    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM memory_status_transitions").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0


def test_consolidation_auto_approve_remember_preferences_apply_is_guarded_and_audited(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-auto-approve-apply.db"
    initialize_database(db_path)
    safe_trace = insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="f" * 64,
        summary="User prefers concise Korean handoffs.",
        scope="project:g2",
        session_ref="session:auto-apply",
        salience=1.0,
        user_emphasis=1.0,
        retention_policy="review",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        },
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="0" * 64,
        summary="User prefers token=SUPERSECRET.",
        scope="project:g2",
        retention_policy="review",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        },
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="1" * 64,
        summary="User prefers this ordinary turn should not auto approve.",
        scope="project:g2",
        retention_policy="ephemeral",
        metadata={},
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "auto-approve",
            "remember-preferences",
            str(db_path),
            "--policy",
            "remember-preferences-v1",
            "--scope",
            "project:g2",
            "--apply",
            "--actor",
            "agent-memory:g2-test",
            "--reason",
            "G2 guarded auto-approval test",
            "--limit",
            "50",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "token=" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "remember_preference_auto_approval_report"
    assert payload["apply"] is True
    assert payload["read_only"] is False
    assert payload["mutated"] is True
    assert payload["eligible_count"] == 1
    assert payload["approved_count"] == 1
    assert payload["blocked_count"] == 1
    approved = payload["approved"][0]
    assert approved["trace_id"] == safe_trace.id
    assert approved["memory_ref"].startswith("fact:")
    assert approved["audit"]["actor"] == "agent-memory:g2-test"
    assert approved["audit"]["reason"] == "G2 guarded auto-approval test"
    assert payload["blocked"][0]["reason_codes"] == ["secret_like_summary"]
    assert "summary" not in payload["blocked"][0]

    with sqlite3.connect(db_path) as connection:
        fact_rows = connection.execute(
            "SELECT id, subject_ref, predicate, object_ref_or_value, scope, status, evidence_ids_json FROM facts"
        ).fetchall()
        assert len(fact_rows) == 1
        fact_row = fact_rows[0]
        assert fact_row[1:6] == ("user", "prefers", "concise Korean handoffs.", "project:g2", "approved")
        assert len(json.loads(fact_row[6])) == 1
        assert connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0] == 1
        transition = connection.execute(
            "SELECT memory_type, memory_id, from_status, to_status, actor, reason FROM memory_status_transitions"
        ).fetchone()
        assert transition == ("fact", fact_row[0], "candidate", "approved", "agent-memory:g2-test", "G2 guarded auto-approval test")
        relation = connection.execute(
            "SELECT from_ref, relation_type, to_ref FROM relations"
        ).fetchone()
        assert relation == (f"experience_trace:{safe_trace.id}", "auto_approved_as", f"fact:{fact_row[0]}")


def test_consolidation_auto_approve_remember_preferences_blocks_conflicts_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-auto-approve-conflict.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path,
        content="Existing reviewed preference says the user prefers verbose handoffs.",
        source_type="note",
        adapter="test",
    )
    create_candidate_fact(
        db_path,
        subject_ref="user",
        predicate="prefers",
        object_ref_or_value="verbose handoffs.",
        evidence_ids=[source.id],
        scope="project:g2",
        confidence=0.8,
    )
    approve_fact(db_path, fact_id=1)
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="2" * 64,
        summary="User prefers concise Korean handoffs.",
        scope="project:g2",
        retention_policy="review",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        },
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "auto-approve",
            "remember-preferences",
            str(db_path),
            "--policy",
            "remember-preferences-v1",
            "--scope",
            "project:g2",
            "--apply",
            "--actor",
            "agent-memory:g2-test",
            "--reason",
            "G2 guarded auto-approval test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["approved_count"] == 0
    assert payload["blocked_count"] == 1
    assert payload["blocked"][0]["reason_codes"] == ["claim_slot_conflict"]
    assert payload["blocked"][0]["conflict_preflight"]["result"] == "blocked"
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM source_records").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM relations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM memory_status_transitions").fetchone()[0] == 1


def test_dogfood_remember_intent_report_summarizes_review_ready_traces_without_mutation_or_secret_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "remember-intent-dogfood.db"
    initialize_database(db_path)
    safe_trace = insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="a" * 64,
        summary="Project prefers explicit review gates before long-term memory approval.",
        scope="project:g1",
        session_ref="session:safe",
        salience=1.0,
        user_emphasis=1.0,
        retention_policy="review",
        metadata={
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
            "api_key": "SHOULD_NOT_APPEAR",
        },
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="b" * 64,
        summary="Unsafe remember trace with token=SHOULD_NOT_APPEAR must stay out of samples.",
        scope="project:g1",
        session_ref="session:unsafe",
        salience=1.0,
        user_emphasis=1.0,
        retention_policy="review",
        metadata={"candidate_policy": "review_required", "auto_approved": False, "secret_scan": "passed"},
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="c" * 64,
        summary=None,
        scope="project:g1",
        session_ref="session:ordinary",
        retention_policy="ephemeral",
        metadata={"trace_recording": "opt_in"},
    )

    before_counts = _table_counts(db_path, ["experience_traces", "facts", "procedures", "episodes", "relations"])
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "remember-intent",
            str(db_path),
            "--limit",
            "20",
            "--sample-limit",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SHOULD_NOT_APPEAR" not in result.stdout
    assert "api_key" not in result.stdout
    assert "token=" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "remember_intent_dogfood_report"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["trace_counts"] == {
        "total": 3,
        "remember_intent": 2,
        "ordinary_turn": 1,
        "other": 0,
    }
    assert payload["review_ready_count"] == 1
    assert payload["unsafe_sample_count"] == 1
    assert payload["scopes"] == {"project:g1": 2}
    assert payload["samples"] == [
        {
            "trace_id": safe_trace.id,
            "scope": "project:g1",
            "summary": "Project prefers explicit review gates before long-term memory approval.",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        }
    ]
    assert payload["suggested_next_steps"][0].startswith("Review remember_intent")
    assert _table_counts(db_path, ["experience_traces", "facts", "procedures", "episodes", "relations"]) == before_counts


def test_consolidation_background_dry_run_writes_cron_friendly_read_only_report(tmp_path: Path) -> None:
    db_path = tmp_path / "background-dry-run.db"
    report_path = tmp_path / "reports" / "background-report.json"
    lock_path = tmp_path / "background.lock"
    initialize_database(db_path)
    for index in range(2):
        insert_experience_trace(
            db_path,
            surface="hermes-pre-llm-hook",
            event_kind="remember_intent",
            content_sha256=f"{index}" * 64,
            summary="User prefers concise Korean handoffs.",
            scope="project:g3",
            session_ref=f"session:g3:{index}",
            salience=1.0,
            user_emphasis=1.0,
            retention_policy="review",
            metadata={
                "remember_intent": "explicit",
                "candidate_policy": "review_required",
                "auto_approved": False,
                "secret_scan": "passed",
                "raw_prompt": "token=SHOULD_NOT_APPEAR",
            },
        )

    before_counts = _table_counts(db_path, ["experience_traces", "facts", "source_records", "relations", "memory_status_transitions"])
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "consolidation",
            "background",
            "dry-run",
            str(db_path),
            "--limit",
            "50",
            "--top",
            "10",
            "--min-evidence",
            "2",
            "--output",
            str(report_path),
            "--lock-path",
            str(lock_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SHOULD_NOT_APPEAR" not in result.stdout
    assert "raw_prompt" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_consolidation_background_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["status"] == "completed"
    assert payload["lock"]["acquired"] is True
    assert payload["output_path"] == str(report_path)
    assert payload["reports"]["candidates"]["kind"] == "memory_consolidation_candidates"
    assert payload["reports"]["candidates"]["candidate_count"] == 1
    assert payload["review_handoff"]["suitable_for_human_review"] is True
    assert payload["automation_policy"]["apply_supported"] is False
    assert report_path.exists()
    file_payload = json.loads(report_path.read_text())
    assert file_payload == payload
    assert _table_counts(db_path, ["experience_traces", "facts", "source_records", "relations", "memory_status_transitions"]) == before_counts


def test_consolidation_background_dry_run_skips_when_lock_is_busy_without_failing_cron(tmp_path: Path) -> None:
    db_path = tmp_path / "background-lock.db"
    report_path = tmp_path / "background-lock-report.json"
    lock_path = tmp_path / "background.lock"
    initialize_database(db_path)
    lock_path.touch()

    env = {**os.environ, "PYTHONPATH": "src"}
    with lock_path.open("r+") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "consolidation",
                "background",
                "dry-run",
                str(db_path),
                "--output",
                str(report_path),
                "--lock-path",
                str(lock_path),
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_consolidation_background_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "skipped_lock_busy"
    assert payload["lock"]["acquired"] is False
    assert payload["error"] is None
    assert report_path.exists()
    assert json.loads(report_path.read_text()) == payload
    assert _table_counts(db_path, ["facts", "source_records", "relations", "memory_status_transitions"]) == {
        "facts": 0,
        "source_records": 0,
        "relations": 0,
        "memory_status_transitions": 0,
    }


def test_dogfood_background_dry_run_quality_gates_summarize_reports_without_mutation_or_secret_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "background-dogfood.db"
    report_path = tmp_path / "background-report.json"
    output_path = tmp_path / "background-quality.json"
    initialize_database(db_path)
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="a" * 64,
        summary="User prefers read-only dogfood reports.",
        scope="project:g3",
        session_ref="session:g3:quality",
        salience=1.0,
        user_emphasis=1.0,
        retention_policy="review",
        metadata={"remember_intent": "explicit", "raw_prompt": "token=SHOULD_NOT_APPEAR"},
    )
    report_path.write_text(
        json.dumps(
            {
                "kind": "memory_consolidation_background_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "status": "completed",
                "scan": {"quality_warnings": []},
                "reports": {
                    "candidates": {"candidate_count": 1, "trace_count": 2, "quality_warnings": []},
                    "activation_summary": {"activation_count": 3, "quality_warnings": []},
                    "reinforcement": {"candidate_count": 1, "quality_warnings": []},
                    "decay_risk": {"decay_risk_candidates": [], "quality_warnings": []},
                },
                "review_handoff": {
                    "candidate_count": 1,
                    "reinforcement_candidate_count": 1,
                    "decay_risk_candidate_count": 0,
                },
                "debug": {"raw_prompt": "token=SHOULD_NOT_APPEAR"},
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )

    before_counts = _table_counts(db_path, ["experience_traces", "facts", "source_records", "relations", "memory_status_transitions"])
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "background-dry-run",
            str(db_path),
            "--report",
            str(report_path),
            "--candidate-min",
            "1",
            "--max-decay-risk",
            "0",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "SHOULD_NOT_APPEAR" not in result.stdout
    assert "raw_prompt" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["kind"] == "background_dry_run_dogfood_report"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["report_count"] == 1
    assert payload["status_counts"] == {"completed": 1}
    assert payload["aggregate"]["candidate_count_max"] == 1
    assert payload["aggregate"]["decay_risk_candidate_count_max"] == 0
    assert payload["quality_gate"]["pass"] is True
    assert payload["quality_gate"]["decision"] == "dry_run_quality_gate_passed_plan_g4_only"
    assert payload["automation_policy"]["apply_supported"] is False
    assert payload["automation_policy"]["ordinary_conversation_auto_approval"] is False
    assert payload["reports"][0]["path"] == str(report_path)
    assert "raw_report" not in payload["reports"][0]
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == payload
    assert _table_counts(db_path, ["experience_traces", "facts", "source_records", "relations", "memory_status_transitions"]) == before_counts


def test_dogfood_background_dry_run_quality_gates_block_g4_when_reports_are_noisy_or_incomplete(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "background-dogfood-blocked.db"
    completed_report = tmp_path / "completed-report.json"
    skipped_report = tmp_path / "skipped-report.json"
    failed_report = tmp_path / "failed-report.json"
    initialize_database(db_path)
    completed_report.write_text(
        json.dumps(
            {
                "kind": "memory_consolidation_background_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "status": "completed",
                "scan": {"quality_warnings": ["no_clusters_meet_min_evidence"]},
                "reports": {
                    "candidates": {"candidate_count": 0, "trace_count": 4, "quality_warnings": ["no_clusters_meet_min_evidence"]},
                    "activation_summary": {"activation_count": 1, "quality_warnings": []},
                    "reinforcement": {"candidate_count": 0, "quality_warnings": []},
                    "decay_risk": {"decay_risk_candidates": [{"memory_ref": "fact:1"}], "quality_warnings": []},
                },
                "review_handoff": {
                    "candidate_count": 0,
                    "reinforcement_candidate_count": 0,
                    "decay_risk_candidate_count": 1,
                },
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    skipped_report.write_text(
        json.dumps({"kind": "memory_consolidation_background_dry_run", "status": "skipped_lock_busy", "mutated": False}),
        encoding="utf-8",
    )
    failed_report.write_text(
        json.dumps({"kind": "memory_consolidation_background_dry_run", "status": "failed", "mutated": False}),
        encoding="utf-8",
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "background-dry-run",
            str(db_path),
            "--report",
            str(completed_report),
            "--report",
            str(skipped_report),
            "--report",
            str(failed_report),
            "--candidate-min",
            "1",
            "--max-decay-risk",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "background_dry_run_dogfood_report"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["report_count"] == 3
    assert payload["status_counts"] == {"completed": 1, "failed": 1, "skipped_lock_busy": 1}
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "continue_dry_run_dogfooding_before_g4"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "background_reports_have_failures_or_skips",
        "candidate_signal_below_threshold",
        "decay_risk_above_threshold",
        "quality_warnings_present",
    }
    assert payload["aggregate"]["candidate_count_max"] == 0
    assert payload["aggregate"]["decay_risk_candidate_count_max"] == 1
    assert "Do not enable background apply mode from this report." in payload["suggested_next_steps"]


def _table_counts(db_path: Path, tables: list[str]) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
