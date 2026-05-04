import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

from agent_memory.api.cli import main
from agent_memory.core.curation import approve_fact, create_candidate_fact, supersede_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.integrations import hermes_hooks
from agent_memory.integrations.hermes_hooks import HermesPreLlmHookOptions, HermesShellHookPayload, scope_from_cwd
from agent_memory.storage.sqlite import initialize_database, insert_relation, list_experience_traces, update_memory_status


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



def test_python_module_cli_hermes_pre_llm_hook_does_not_record_trace_by_default(tmp_path: Path) -> None:
    db_path = tmp_path / "module-cli-hermes-default-no-trace.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Default Hermes trace recording should remain disabled while retrieval still works.",
        metadata={"project": "default-no-trace"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Default trace recording",
        predicate="posture",
        object_ref_or_value="disabled",
        evidence_ids=[source.id],
        scope="project:default-no-trace",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    hook_payload = {
        "hook_event_name": "pre_llm_call",
        "session_id": "real-session-default-no-trace",
        "cwd": str(tmp_path),
        "extra": {
            "user_message": "What is the default trace recording posture?",
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
            "project:default-no-trace",
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
        "trace_recording": "opt_in",
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
