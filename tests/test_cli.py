import fcntl
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from agent_memory.api.cli import main
from agent_memory.core.curation import approve_fact, create_candidate_fact, create_episode, supersede_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import RetrievalTraceEntry
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.integrations import hermes_hooks
from agent_memory.integrations.hermes_hooks import HermesPreLlmHookOptions, HermesShellHookPayload, scope_from_cwd
from agent_memory.storage.sqlite import (
    initialize_database,
    get_fact,
    insert_experience_trace,
    insert_relation,
    list_experience_traces,
    list_retrieval_observations,
    record_memory_retrieval,
    record_retrieval_observation,
    update_memory_status,
)


def _fact_trace(memory_id: int, *, label: str = "Agent Memory project fact") -> RetrievalTraceEntry:
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


def test_python_module_cli_backup_export_inspect_restore_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "cli-backup.db"
    bundle_path = tmp_path / "cli-backup.zip"
    restored_path = tmp_path / "cli-restored.db"
    initialize_database(db_path)
    source = ingest_source_text(db_path=db_path, source_type="note", content="CLI backup preserves memory state.")
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="CLI backup",
        predicate="preserves",
        object_ref_or_value="memory state",
        evidence_ids=[source.id],
        scope="project:backup-cli",
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    env = {**os.environ, "PYTHONPATH": "src"}

    export_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "backup", "export", str(db_path), str(bundle_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert export_result.returncode == 0, export_result.stderr
    assert json.loads(export_result.stdout)["kind"] == "agent_memory_backup_export"

    inspect_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "backup", "inspect", str(bundle_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert inspect_result.returncode == 0, inspect_result.stderr
    assert json.loads(inspect_result.stdout)["manifest"]["table_counts"]["facts"] == 1

    restore_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "backup", "restore", str(bundle_path), str(restored_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert restore_result.returncode == 0, restore_result.stderr
    packet = retrieve_memory_packet(restored_path, query="memory state", preferred_scope="project:backup-cli")
    assert [item.id for item in packet.semantic_facts] == [fact.id]


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


def test_python_module_cli_graph_export_html_writes_read_only_private_neural_view(tmp_path: Path) -> None:
    db_path = tmp_path / "graph-export-html.db"
    output_path = tmp_path / "memory-graph.html"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Graph visualization source contains token=SHOULD_NOT_LEAK.",
        metadata={"project": "graph-export"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Graph visualization",
        predicate="target_phrase",
        object_ref_or_value="GRAPH_EXPORT_OK",
        evidence_ids=[source.id],
        scope="project:graph-export",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{fact.id}",
        relation_type="supports",
        to_ref="procedure:7",
        evidence_ids=[source.id],
        confidence=0.8,
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="a" * 64,
        summary=None,
        scope="project:graph-export",
        related_memory_refs=[f"fact:{fact.id}"],
        related_observation_ids=[],
        retention_policy="ephemeral",
        metadata={"candidate_policy": "evidence_only", "auto_approved": False},
    )

    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("source_records", "facts", "relations", "experience_traces")
        }

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "graph",
            "export-html",
            str(db_path),
            "--output",
            str(output_path),
            "--limit",
            "100",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "memory_graph_html_export"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["output_path"] == str(output_path)
    assert payload["node_count"] >= 3
    assert payload["edge_count"] >= 2
    assert payload["privacy"] == {
        "raw_source_content_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "memory_labels_included": False,
    }
    html = output_path.read_text()
    assert "agent-memory neural graph" in html
    assert "application/json" in html
    assert f"fact:{fact.id}" in html
    assert "token=SHOULD_NOT_LEAK" not in result.stdout
    assert "token=SHOULD_NOT_LEAK" not in html
    assert "GRAPH_EXPORT_OK" not in html
    assert payload["performance"]["layout_mode"] == "interactive_brain_static"
    assert payload["performance"]["continuous_physics_enabled"] is False
    assert payload["performance"]["rendering"] == "dirty_rect_event_driven_canvas"
    assert payload["performance"]["device_pixel_ratio_cap"] == 1.5
    assert payload["performance"]["quality_modes"] == ["auto", "performance", "sharp"]
    assert "agent-memory 기억 그래프" in html
    assert "뇌형 기억 그래프" in html
    assert "주요 기억 허브" in html
    assert "Fact = 검토/승인된 사실형 장기 기억" in html
    assert "Procedure = 검토된 절차형 기억" in html
    assert "품질: 자동" in html
    assert "성능 우선" in html
    assert "선명도 우선" in html
    assert "setQualityMode" in html
    assert "effectiveDpr" in html
    assert "CSS_CLASS_LOW_POWER" in html
    assert "graph-data-summary" in html
    assert "requestDraw" in html
    assert "for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++)" not in html
    assert "continuous physics" not in html.lower()
    assert "requestAnimationFrame(draw)" not in html

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("source_records", "facts", "relations", "experience_traces")
        }
    assert after_counts == before_counts



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


def test_python_module_cli_activations_decay_risk_reports_ref_safe_resolution_hints(tmp_path: Path) -> None:
    db_path = tmp_path / "activation-decay-ref-safe.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Decay risk diagnostics should explain isolated approved refs without raw user prompts.",
        metadata={"project": "decay-ref-safe"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Decay diagnostics",
        predicate="posture",
        object_ref_or_value="ref-safe isolated approved memory explanation",
        evidence_ids=[source.id],
        scope="project:decay-ref-safe",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "Explain decay diagnostics token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:decay-ref-safe",
            "--observe",
            "hermes-pre-llm-hook",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr

    report_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "activations",
            "decay-risk-report",
            str(db_path),
            "--limit",
            "50",
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
    assert report_result.returncode == 0, report_result.stderr
    payload = json.loads(report_result.stdout)
    candidate = payload["decay_risk_candidates"][0]
    assert candidate["memory_ref"] == f"fact:{fact.id}"
    assert candidate["ref_safe_evidence"] == {
        "memory_ref": f"fact:{fact.id}",
        "memory_type": "fact",
        "memory_id": fact.id,
        "exists": True,
        "evidence_id_count": 1,
        "relation_count": 0,
        "scope_present": True,
        "content_included": False,
    }
    assert candidate["resolution_hint"] == "add_relation_or_confirm_isolated_approved_memory"
    assert candidate["review_support"] == {
        "review_required": True,
        "safe_to_auto_mutate": False,
        "raw_content_included": False,
        "recommended_actions": [
            "inspect_ref_safe_evidence",
            "add_relation_to_existing_memory_or_entity",
            "confirm_isolated_approved_memory",
        ],
        "operator_commands": [
            f"agent-memory review explain fact {str(db_path)} {fact.id}",
            f"agent-memory review history fact {str(db_path)} {fact.id}",
            f"agent-memory graph inspect {str(db_path)} fact:{fact.id} --depth 1",
        ],
    }
    assert payload["candidate_decomposition"]["resolution_hint_counts"] == {
        "add_relation_or_confirm_isolated_approved_memory": 1,
    }
    assert "SHOULD_NOT_LEAK" not in report_result.stdout
    assert "token=" not in report_result.stdout



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



def test_python_module_cli_dogfood_storage_health_reports_safe_read_only_invariants(tmp_path: Path) -> None:
    db_path = tmp_path / "dogfood-storage-health.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Storage health target phrase is STORAGE_HEALTH_OK.",
        metadata={"project": "dogfood-storage-health"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Storage health",
        predicate="target_phrase",
        object_ref_or_value="STORAGE_HEALTH_OK",
        evidence_ids=[source.id],
        scope="project:dogfood-storage-health",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the storage health phrase? token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:dogfood-storage-health",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr

    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="a" * 64,
        summary=None,
        scope="project:dogfood-storage-health",
        retention_policy="ephemeral",
        metadata={
            "trace_recording": "default_metadata_only",
            "candidate_policy": "evidence_only",
            "auto_approved": False,
            "raw_prompt": "token=SHOULD_NOT_LEAK",
        },
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="b" * 64,
        summary="User prefers storage-health reports before G4.",
        scope="project:dogfood-storage-health",
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
        content_sha256="c" * 64,
        summary=None,
        scope="project:dogfood-storage-health",
        retention_policy="ephemeral",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "rejected",
            "auto_approved": False,
            "secret_scan": "rejected",
            "rejected_reason": "secret_like_text",
            "raw_user_message": "api key SHOULD_NOT_LEAK",
        },
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE retrieval_observations SET query_preview = ? WHERE id = 1", ("token=SHOULD_NOT_LEAK",))
        connection.execute("UPDATE retrieval_observations SET metadata_json = ? WHERE id = 1", ("{not-json",))
        connection.execute(
            """
            INSERT INTO memory_activations (
                surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("cli-test", "retrieved", "fact:999", 999, 999, "project:dogfood-storage-health", 1.0, "{}"),
        )

    health_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "storage-health",
            str(db_path),
            "--hermes-config",
            str(tmp_path / "missing-config.yaml"),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert health_result.returncode == 0, health_result.stderr
    payload = json.loads(health_result.stdout)
    assert payload["kind"] == "dogfood_storage_health"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "warning"
    assert payload["agent_memory_version"]
    assert payload["table_counts"]["retrieval_observations"] == 1
    assert payload["table_counts"]["memory_activations"] == 2
    assert payload["table_counts"]["experience_traces"] == 3
    assert payload["memory_counts"]["facts"]["approved"] == 1
    assert payload["invariants"]["stored_query_excerpt_empty"]["violation_count"] == 1
    assert payload["invariants"]["query_hash_presence"]["violation_count"] == 0
    assert payload["invariants"]["metadata_json_valid"]["invalid_counts"]["retrieval_observations"] == 1
    assert payload["invariants"]["activation_links"]["orphan_observation_count"] == 1
    assert payload["invariants"]["activation_links"]["orphan_trace_count"] == 1
    ordinary = payload["invariants"]["ordinary_trace_metadata_only"]
    assert ordinary["checked_count"] == 1
    assert ordinary["violation_count"] == 0
    remember = payload["invariants"]["remember_intent_safety"]
    assert remember["checked_count"] == 2
    assert remember["review_ready_count"] == 1
    assert remember["rejected_secret_like_count"] == 1
    assert remember["violation_count"] == 0
    assert payload["hermes"]["config_exists"] is False
    assert "query_text" not in health_result.stdout
    assert "query_preview" not in health_result.stdout
    assert "SHOULD_NOT_LEAK" not in health_result.stdout
    assert "api key" not in health_result.stdout.lower()



def test_python_module_cli_dogfood_query_preview_cleanup_preview_reports_legacy_rows_without_mutation_or_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Query preview cleanup target phrase is CLEANUP_OK.",
        metadata={"project": "query-preview-cleanup"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Query preview cleanup",
        predicate="target_phrase",
        object_ref_or_value="CLEANUP_OK",
        evidence_ids=[source.id],
        scope="project:query-preview-cleanup",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for query in ("first token=SHOULD_NOT_LEAK", "second api key SHOULD_NOT_LEAK"):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                query,
                "--preferred-scope",
                "project:query-preview-cleanup",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE retrieval_observations SET query_preview = ? WHERE id = 1", ("token=SHOULD_NOT_LEAK",))
        connection.execute("UPDATE retrieval_observations SET query_preview = ? WHERE id = 2", ("api key SHOULD_NOT_LEAK",))
        before_rows = connection.execute(
            "SELECT COUNT(*) FROM retrieval_observations WHERE COALESCE(query_preview, '') <> ''"
        ).fetchone()[0]
    assert before_rows == 2

    preview_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2030-01-01T00:00:00",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert preview_result.returncode == 0, preview_result.stderr
    payload = json.loads(preview_result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "warning"
    assert payload["affected_count"] == 2
    assert payload["eligible_count"] == 2
    assert payload["latest_affected_at"]
    assert payload["cleanup_preview"]["mutation_required"] is True
    assert payload["cleanup_preview"]["recommended_operation"] == "clear_stored_query_excerpts"
    assert payload["cleanup_preview"]["parameters"] == {"older_than": "2030-01-01T00:00:00"}
    assert payload["cleanup_preview"]["apply_policy"] == "legacy-query-preview-cleanup-v1"
    assert payload["cleanup_preview"]["apply_guardrails"] == ["--apply", "--policy", "--actor", "--reason"]
    assert payload["privacy"]["raw_query_preview_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in preview_result.stdout
    assert "api key" not in preview_result.stdout.lower()
    assert "token=" not in preview_result.stdout

    with sqlite3.connect(db_path) as connection:
        after_rows = connection.execute(
            "SELECT COUNT(*) FROM retrieval_observations WHERE COALESCE(query_preview, '') <> ''"
        ).fetchone()[0]
    assert after_rows == 2



def test_python_module_cli_dogfood_query_preview_cleanup_apply_requires_actor_reason_and_clears_eligible_rows_without_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-apply.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Query preview cleanup apply target phrase is CLEANUP_APPLY_OK.",
        metadata={"project": "query-preview-cleanup-apply"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Query preview cleanup apply",
        predicate="target_phrase",
        object_ref_or_value="CLEANUP_APPLY_OK",
        evidence_ids=[source.id],
        scope="project:query-preview-cleanup-apply",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for query in ("first token=SHOULD_NOT_LEAK", "second api key SHOULD_NOT_LEAK"):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                query,
                "--preferred-scope",
                "project:query-preview-cleanup-apply",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 1", ("token=SHOULD_NOT_LEAK", "2026-01-01 00:00:00"))
        connection.execute("UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 2", ("api key SHOULD_NOT_LEAK", "2026-01-03 00:00:00"))

    missing_reason_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_reason_result.returncode != 0

    missing_policy_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--actor",
            "cli-test",
            "--reason",
            "remove legacy query preview values after read-only preview",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_policy_result.returncode != 0
    assert "--policy" in missing_policy_result.stderr

    invalid_policy_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "broad-g4-apply",
            "--actor",
            "cli-test",
            "--reason",
            "remove legacy query preview values after read-only preview",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert invalid_policy_result.returncode != 0
    assert "legacy-query-preview-cleanup-v1" in invalid_policy_result.stderr

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
            "--reason",
            "remove legacy query preview values after read-only preview",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert apply_result.returncode == 0, apply_result.stderr
    payload = json.loads(apply_result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_apply"
    assert payload["read_only"] is False
    assert payload["mutated"] is True
    assert payload["eligible_count"] == 1
    assert payload["cleared_count"] == 1
    assert payload["remaining_affected_count"] == 1
    assert payload["apply"]["actor"] == "cli-test"
    assert payload["apply"]["policy"] == "legacy-query-preview-cleanup-v1"
    assert payload["apply"]["reason_sha256"]
    assert payload["apply"]["audit_trace_id"]
    disposable = payload["apply"]["disposable_apply_check"]
    assert disposable["kind"] == "query_preview_cleanup_disposable_apply_check"
    assert disposable["status"] == "passed"
    assert disposable["live_database_mutated_before_check"] is False
    assert disposable["checked_database_path"].endswith(".db")
    assert disposable["checked_database_path"] != str(db_path)
    assert Path(disposable["checked_database_path"]).exists()
    assert disposable["eligible_count"] == 1
    assert disposable["cleared_count"] == 1
    assert disposable["remaining_affected_count"] == 1
    assert disposable["rollback_manifest"]["row_count"] == 1
    assert disposable["rollback_manifest"]["artifact_sha256"]
    assert disposable["privacy"]["raw_query_preview_included_in_output"] is False
    assert disposable["privacy"]["disposable_copy_contains_private_query_preview"] is True
    rollback = payload["apply"]["rollback_manifest"]
    assert rollback["kind"] == "query_preview_cleanup_rollback_manifest"
    assert rollback["policy"] == "legacy-query-preview-cleanup-v1"
    assert rollback["row_count"] == 1
    assert rollback["artifact_path"].endswith(".json")
    assert rollback["artifact_sha256"]
    assert rollback["privacy"]["raw_query_preview_included_in_output"] is False
    assert rollback["privacy"]["artifact_contains_private_query_preview"] is True
    rollback_path = Path(rollback["artifact_path"])
    assert rollback_path.exists()
    rollback_payload = json.loads(rollback_path.read_text())
    assert rollback_payload["kind"] == "query_preview_cleanup_rollback_artifact"
    assert rollback_payload["policy"] == "legacy-query-preview-cleanup-v1"
    assert rollback_payload["rows"] == [
        {"id": 1, "query_preview": "token=SHOULD_NOT_LEAK", "created_at": "2026-01-01 00:00:00"}
    ]
    assert payload["privacy"]["raw_query_preview_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in apply_result.stdout
    assert "api key" not in apply_result.stdout.lower()
    assert "token=" not in apply_result.stdout

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT id, query_preview FROM retrieval_observations ORDER BY id"
        ).fetchall()
        audit = connection.execute(
            "SELECT event_kind, summary, metadata_json FROM experience_traces ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert rows == [(1, None), (2, "api key SHOULD_NOT_LEAK")]
    assert audit[0] == "dogfood_query_preview_cleanup_apply"
    assert audit[1] is None
    audit_metadata = json.loads(audit[2])
    assert audit_metadata["cleared_count"] == 1
    assert audit_metadata["eligible_count"] == 1
    assert audit_metadata["policy"] == "legacy-query-preview-cleanup-v1"
    assert audit_metadata["rollback_manifest"]["artifact_sha256"] == rollback["artifact_sha256"]
    assert audit_metadata["rollback_manifest"]["row_count"] == 1
    assert audit_metadata["disposable_apply_check"]["status"] == "passed"
    assert audit_metadata["disposable_apply_check"]["rollback_manifest"]["artifact_sha256"] == disposable["rollback_manifest"]["artifact_sha256"]
    assert audit_metadata["reason_sha256"] == payload["apply"]["reason_sha256"]
    assert "SHOULD_NOT_LEAK" not in audit[2]
    assert "api key" not in audit[2].lower()
    assert "token=" not in audit[2]



def test_python_module_cli_dogfood_query_preview_cleanup_restore_dry_run_validates_artifact_without_mutation_or_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-restore.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Query preview cleanup restore target phrase is RESTORE_DRY_RUN_OK.",
        metadata={"project": "query-preview-cleanup-restore"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Query preview cleanup restore",
        predicate="target_phrase",
        object_ref_or_value="RESTORE_DRY_RUN_OK",
        evidence_ids=[source.id],
        scope="project:query-preview-cleanup-restore",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for query in ("first token=SHOULD_NOT_LEAK", "second api key SHOULD_NOT_LEAK"):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                query,
                "--preferred-scope",
                "project:query-preview-cleanup-restore",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 1",
            ("token=SHOULD_NOT_LEAK", "2026-01-01 00:00:00"),
        )
        connection.execute(
            "UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 2",
            ("api key SHOULD_NOT_LEAK", "2026-01-03 00:00:00"),
        )

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
            "--reason",
            "remove legacy query preview values before restore dry run test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    apply_payload = json.loads(apply_result.stdout)
    rollback_path = Path(apply_payload["apply"]["rollback_manifest"]["artifact_path"])
    assert rollback_path.exists()

    missing_dry_run_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(db_path),
            str(rollback_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_dry_run_result.returncode != 0
    assert "--dry-run" in missing_dry_run_result.stderr

    restore_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(db_path),
            str(rollback_path),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert restore_result.returncode == 0, restore_result.stderr
    payload = json.loads(restore_result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_restore_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "warning"
    assert payload["artifact"]["kind"] == "query_preview_cleanup_rollback_artifact"
    assert payload["artifact"]["policy"] == "legacy-query-preview-cleanup-v1"
    assert payload["artifact"]["row_count"] == 1
    assert payload["artifact"]["artifact_sha256"] == apply_payload["apply"]["rollback_manifest"]["artifact_sha256"]
    assert payload["artifact"]["eligible_ids_sha256"] == apply_payload["apply"]["rollback_manifest"]["eligible_ids_sha256"]
    assert payload["artifact"]["source_database"]["fingerprint_sha256"] == apply_payload["apply"]["rollback_manifest"]["source_database"]["fingerprint_sha256"]
    assert payload["source_database_match"]["matched"] is True
    assert payload["source_database_match"]["artifact_fingerprint_sha256"] == apply_payload["apply"]["rollback_manifest"]["source_database"]["fingerprint_sha256"]
    assert payload["source_database_match"]["target_fingerprint_sha256"] == apply_payload["apply"]["rollback_manifest"]["source_database"]["fingerprint_sha256"]
    assert payload["restore_preview"]["operation"] == "restore_stored_query_excerpts"
    assert payload["restore_preview"]["dry_run"] is True
    assert payload["restore_preview"]["restore_apply_available"] is False
    assert payload["restore_preview"]["candidate_restore_count"] == 1
    assert payload["restore_preview"]["target_rows_found_count"] == 1
    assert payload["restore_preview"]["restorable_count"] == 1
    assert payload["restore_preview"]["already_has_query_preview_count"] == 0
    assert payload["restore_preview"]["missing_row_count"] == 0
    assert payload["privacy"]["raw_query_preview_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert payload["privacy"]["artifact_contains_private_query_preview"] is True
    assert "live_restore_not_implemented" in payload["blocked_reasons"]
    assert "SHOULD_NOT_LEAK" not in restore_result.stdout
    assert "api key" not in restore_result.stdout.lower()
    assert "token=" not in restore_result.stdout

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT id, query_preview FROM retrieval_observations ORDER BY id"
        ).fetchall()
    assert rows == [(1, None), (2, "api key SHOULD_NOT_LEAK")]



def test_python_module_cli_dogfood_query_preview_cleanup_restore_apply_writes_single_audit_row_without_live_restore_or_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-restore-apply-contract.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Query preview cleanup restore apply contract target phrase is RESTORE_APPLY_CONTRACT_OK.",
        metadata={"project": "query-preview-cleanup-restore-apply-contract"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Query preview cleanup restore apply contract",
        predicate="target_phrase",
        object_ref_or_value="RESTORE_APPLY_CONTRACT_OK",
        evidence_ids=[source.id],
        scope="project:query-preview-cleanup-restore-apply-contract",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "restore apply token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:query-preview-cleanup-restore-apply-contract",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 1",
            ("token=SHOULD_NOT_LEAK", "2026-01-01 00:00:00"),
        )

    cleanup_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
            "--reason",
            "create rollback artifact before restore apply contract checkpoint",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert cleanup_result.returncode == 0, cleanup_result.stderr
    cleanup_payload = json.loads(cleanup_result.stdout)
    rollback_path = Path(cleanup_payload["apply"]["rollback_manifest"]["artifact_path"])

    approval_token_secret = "approval-token-secret-SHOULD_NOT_LEAK"
    approval_token_sha256 = hashlib.sha256(approval_token_secret.encode()).hexdigest()
    approval_token_expected_sha256 = approval_token_sha256.upper()
    restore_apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(db_path),
            str(rollback_path),
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-restore-v1",
            "--actor",
            "cli-test",
            "--reason",
            "restore apply contract reason token=SHOULD_NOT_LEAK",
            "--approval-token",
            approval_token_secret,
            "--approval-token-expected-sha256",
            approval_token_expected_sha256,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert restore_apply_result.returncode == 0, restore_apply_result.stderr
    payload = json.loads(restore_apply_result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_restore_apply_blocked"
    assert payload["read_only"] is False
    assert payload["mutated"] is True
    assert payload["status"] == "audit_written_restore_blocked"
    assert payload["audit_trace_mutated"] is True
    assert payload["live_restore_mutated"] is False
    assert payload["restore_preview"]["apply_requested"] is True
    assert payload["restore_preview"]["restore_apply_available"] is False
    assert payload["restore_preview"]["restorable_count"] == 1
    assert payload["restore_apply_contract"]["policy"] == "legacy-query-preview-cleanup-restore-v1"
    assert payload["restore_apply_contract"]["actor"] == "cli-test"
    assert payload["restore_apply_contract"]["reason_sha256"] == hashlib.sha256(
        b"restore apply contract reason token=SHOULD_NOT_LEAK"
    ).hexdigest()
    assert payload["restore_apply_contract"]["disposable_restore_check_required"] is True
    assert payload["restore_apply_contract"]["source_database_match_required"] is True
    assert payload["restore_apply_contract"]["artifact_integrity_required"] is True
    assert payload["restore_apply_contract"]["audit_raw_query_preview_allowed"] is False
    assert payload["restore_apply_contract"]["reason_raw_stored"] is False
    rehearsal = payload["restore_apply_contract"]["disposable_restore_rehearsal"]
    assert rehearsal["kind"] == "query_preview_cleanup_restore_disposable_rehearsal"
    assert rehearsal["status"] == "passed"
    assert rehearsal["live_database_mutated_before_check"] is False
    assert rehearsal["restored_count"] == 1
    assert rehearsal["expected"]["restored_count"] == 1
    assert rehearsal["post_restore_missing_count"] == 0
    assert rehearsal["post_restore_still_empty_count"] == 0
    assert rehearsal["privacy"]["raw_query_preview_included_in_output"] is False
    assert rehearsal["privacy"]["disposable_copy_contains_private_query_preview"] is True
    audit = payload["restore_apply_contract"]["audit_preview"]
    assert audit["kind"] == "query_preview_cleanup_restore_audit_preview"
    assert audit["audit_write_available"] is True
    assert audit["audit_row_would_be_written"] is True
    assert audit["audit_row_written"] is True
    assert audit["privacy"]["raw_query_preview_allowed"] is False
    assert audit["privacy"]["raw_reason_allowed"] is False
    assert audit["fields"]["policy"] == "legacy-query-preview-cleanup-restore-v1"
    assert audit["fields"]["actor"] == "cli-test"
    assert audit["fields"]["reason_sha256"] == payload["restore_apply_contract"]["reason_sha256"]
    assert audit["fields"]["artifact_sha256"] == payload["artifact"]["artifact_sha256"]
    assert audit["fields"]["source_database_fingerprint_sha256"] == payload["source_database_match"]["target_fingerprint_sha256"]
    assert audit["fields"]["rehearsal_status"] == "passed"
    assert audit["fields"]["restored_ids_sha256"] == payload["artifact"]["eligible_ids_sha256"]
    assert audit["fields"]["restored_count"] == 1
    assert set(audit["fields"]) == {
        "policy",
        "actor",
        "reason_sha256",
        "artifact_sha256",
        "source_database_fingerprint_sha256",
        "source_database_match",
        "artifact_integrity_passed",
        "rehearsal_status",
        "restored_ids_sha256",
        "restored_count",
    }
    dry_run = audit["write_dry_run"]
    assert dry_run["kind"] == "query_preview_cleanup_restore_audit_write_dry_run"
    assert dry_run["status"] == "inserted"
    assert dry_run["would_insert"] is True
    assert dry_run["inserted"] is True
    assert dry_run["inserted_trace_id"] >= 1
    assert dry_run["target_table"] == "experience_traces"
    assert dry_run["event_kind"] == "dogfood_query_preview_cleanup_restore_apply"
    assert dry_run["retention_policy"] == "review"
    assert dry_run["content_sha256"]
    assert dry_run["metadata_json_sha256"]
    assert dry_run["metadata_json_preview"] == audit["fields"]
    audit_write_apply = dry_run["apply_contract"]
    assert audit_write_apply["kind"] == "query_preview_cleanup_restore_audit_write_apply_contract"
    assert audit_write_apply["audit_write_apply_available"] is True
    assert audit_write_apply["would_insert"] is True
    assert audit_write_apply["inserted"] is True
    assert audit_write_apply["inserted_trace_id"] == dry_run["inserted_trace_id"]
    assert audit_write_apply["required_policy"] == "legacy-query-preview-cleanup-restore-audit-write-v1"
    assert audit_write_apply["required_actor"] == "cli-test"
    assert audit_write_apply["required_reason_sha256"] == payload["restore_apply_contract"]["reason_sha256"]
    assert audit_write_apply["target_table"] == "experience_traces"
    assert audit_write_apply["event_kind"] == "dogfood_query_preview_cleanup_restore_apply"
    assert audit_write_apply["retention_policy"] == "review"
    assert audit_write_apply["blocked_reasons"] == ["live_restore_not_implemented"]
    assert audit_write_apply["requirements"] == {
        "restore_apply_contract_required": True,
        "source_database_match_required": True,
        "artifact_integrity_required": True,
        "disposable_restore_rehearsal_required": True,
        "audit_metadata_json_sha256_required": True,
        "raw_query_preview_allowed": False,
        "raw_reason_allowed": False,
        "sample_values_allowed": False,
        "broad_g4_apply_allowed": False,
    }
    assert audit_write_apply["insert_preview"] == {
        "surface": "dogfood",
        "event_kind": "dogfood_query_preview_cleanup_restore_apply",
        "content_sha256": dry_run["content_sha256"],
        "summary": None,
        "salience": 0.0,
        "user_emphasis": 0.0,
        "related_memory_refs_json": [],
        "related_observation_ids_json": [],
        "retention_policy": "review",
        "metadata_json_sha256": dry_run["metadata_json_sha256"],
    }
    row_materialization = dry_run["row_materialization"]
    assert row_materialization["kind"] == "query_preview_cleanup_restore_audit_row_materialization"
    assert row_materialization["status"] == "inserted"
    assert row_materialization["inserted_trace_id"] == dry_run["inserted_trace_id"]
    assert row_materialization["target_table"] == "experience_traces"
    assert row_materialization["would_insert"] is True
    assert row_materialization["write_allowed"] is True
    assert row_materialization["schema_version"] == "query-preview-cleanup-restore-audit-row-v1"
    assert row_materialization["duplicate_key"] == {
        "surface": "dogfood",
        "event_kind": "dogfood_query_preview_cleanup_restore_apply",
        "content_sha256": dry_run["content_sha256"],
        "metadata_json_sha256": dry_run["metadata_json_sha256"],
    }
    assert row_materialization["columns"] == [
        "surface",
        "event_kind",
        "content_sha256",
        "summary",
        "salience",
        "user_emphasis",
        "related_memory_refs_json",
        "related_observation_ids_json",
        "retention_policy",
        "metadata_json",
    ]
    assert row_materialization["values"] == {
        "surface": "dogfood",
        "event_kind": "dogfood_query_preview_cleanup_restore_apply",
        "content_sha256": dry_run["content_sha256"],
        "summary": None,
        "salience": 0.0,
        "user_emphasis": 0.0,
        "related_memory_refs_json": "[]",
        "related_observation_ids_json": "[]",
        "retention_policy": "review",
        "metadata_json": row_materialization["metadata_json_canonical"],
    }
    assert json.loads(row_materialization["metadata_json_canonical"]) == dry_run["metadata_json_preview"]
    assert row_materialization["metadata_json_sha256"] == dry_run["metadata_json_sha256"]
    assert row_materialization["content_sha256"] == dry_run["content_sha256"]
    assert row_materialization["privacy"] == {
        "raw_query_preview_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
    }
    preflight = audit_write_apply["preflight"]
    assert preflight["kind"] == "query_preview_cleanup_restore_audit_write_preflight"
    assert preflight["status"] == "passed"
    assert preflight["passed"] is True
    assert preflight["write_allowed"] is True
    assert preflight["write_blocked_by_preflight"] is False
    assert preflight["duplicate_audit_event_count"] == 0
    assert preflight["checked_content_sha256"] == dry_run["content_sha256"]
    assert preflight["checked_metadata_json_sha256"] == dry_run["metadata_json_sha256"]
    assert preflight["checks"] == {
        "policy_matches_required": True,
        "actor_present": True,
        "reason_sha256_matches_restore_contract": True,
        "source_database_match_passed": True,
        "artifact_integrity_passed": True,
        "disposable_rehearsal_passed": True,
        "content_sha256_matches_insert_preview": True,
        "metadata_json_sha256_matches_insert_preview": True,
        "duplicate_audit_event_absent": True,
        "raw_query_preview_allowed": False,
        "raw_reason_allowed": False,
        "sample_values_allowed": False,
        "broad_g4_apply_allowed": False,
    }
    assert preflight["failed_checks"] == []
    assert preflight["conflict_policy"] == {
        "duplicate_audit_event": "fail_closed",
        "content_hash_mismatch": "fail_closed",
        "metadata_hash_mismatch": "fail_closed",
        "source_database_mismatch": "fail_closed",
        "artifact_integrity_failure": "fail_closed",
        "disposable_rehearsal_failure": "fail_closed",
        "privacy_leak_risk": "fail_closed",
    }
    assert preflight["blocked_reasons"] == audit_write_apply["blocked_reasons"]
    approval_packet = audit_write_apply["single_row_apply_policy_packet"]
    assert approval_packet["kind"] == "query_preview_cleanup_restore_audit_write_single_row_apply_policy_packet"
    assert approval_packet["status"] == "validated_write_allowed"
    assert approval_packet["requires_explicit_operator_approval"] is True
    assert approval_packet["approval_token_required"] is True
    assert approval_packet["approval_token_present"] is True
    assert approval_packet["approval_token_sha256"] == approval_token_sha256
    assert approval_packet["approval_token_validated"] is True
    assert approval_packet["approval_token_expected_sha256_required"] is True
    assert approval_packet["approval_token_expected_sha256_present"] is True
    assert approval_packet["approval_token_expected_sha256"] == approval_token_sha256
    assert approval_packet["approval_token_expected_sha256_fingerprint_sha256"] == hashlib.sha256(
        approval_token_sha256.encode()
    ).hexdigest()
    assert approval_packet["approval_token_hash_matches_expected"] is True
    assert approval_packet["approval_token_validation_status"] == "validated_by_expected_sha256"
    assert approval_packet["write_blocked_by_missing_approval"] is False
    assert approval_packet["write_blocked_by_unvalidated_approval"] is False
    assert approval_packet["write_blocked_by_invalid_approval"] is False
    assert approval_packet["write_blocked_by_missing_expected_approval_hash"] is False
    assert approval_packet["write_blocked_by_approval_hash_mismatch"] is False
    assert approval_packet["write_blocked_by_unimplemented_approval_validation"] is False
    assert approval_packet["would_insert"] is True
    assert approval_packet["write_allowed"] is True
    assert approval_packet["inserted_trace_id"] == dry_run["inserted_trace_id"]
    assert approval_packet["expected_insert_count"] == 1
    assert "restore_audit_write_approval_token_hash_match_validated_write_blocked" not in audit_write_apply["blocked_reasons"]
    assert approval_packet["blocked_reasons"] == audit_write_apply["blocked_reasons"]
    assert approval_packet["required_policy"] == "legacy-query-preview-cleanup-restore-audit-write-v1"
    assert approval_packet["actor"] == "cli-test"
    assert approval_packet["reason_sha256"] == payload["restore_apply_contract"]["reason_sha256"]
    assert approval_packet["source_database_fingerprint_sha256"] == payload["source_database_match"]["target_fingerprint_sha256"]
    assert approval_packet["artifact_sha256"] == payload["artifact"]["artifact_sha256"]
    assert approval_packet["rehearsal_status"] == "passed"
    assert approval_packet["preflight_passed"] is True
    assert approval_packet["duplicate_audit_event_count"] == 0
    assert approval_packet["row_materialization_sha256"] == row_materialization["metadata_json_sha256"]
    assert approval_packet["row_schema_version"] == row_materialization["schema_version"]
    assert approval_packet["rollback"] == {
        "undo_requires_manual_audit_trace_review": True,
        "live_restore_enabled": False,
        "audit_row_delete_enabled": False,
        "inserted_trace_id": dry_run["inserted_trace_id"],
    }
    assert approval_packet["privacy"] == {
        "raw_query_preview_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
    }
    assert audit_write_apply["privacy"] == {
        "raw_query_preview_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
    }
    assert dry_run["privacy"]["raw_query_preview_included"] is False
    assert dry_run["privacy"]["raw_reason_included"] is False
    assert dry_run["privacy"]["sample_values_included"] is False
    assert "restore_apply_contract_checkpoint_only" not in payload["blocked_reasons"]
    assert "restore_audit_write_not_implemented" not in payload["blocked_reasons"]
    assert payload["blocked_reasons"] == ["live_restore_not_implemented"]
    assert "SHOULD_NOT_LEAK" not in restore_apply_result.stdout
    assert "approval-token-secret" not in restore_apply_result.stdout
    assert "token=" not in restore_apply_result.stdout

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT id, query_preview FROM retrieval_observations ORDER BY id").fetchall()
        audit_rows = connection.execute(
            """
            SELECT id, surface, event_kind, content_sha256, summary, salience, user_emphasis,
                   related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            FROM experience_traces
            WHERE event_kind = 'dogfood_query_preview_cleanup_restore_apply'
            ORDER BY id
            """
        ).fetchall()
    assert rows == [(1, None)]
    assert len(audit_rows) == 1
    audit_row = audit_rows[0]
    assert audit_row[0] == dry_run["inserted_trace_id"]
    assert audit_row[1:10] == (
        "dogfood",
        "dogfood_query_preview_cleanup_restore_apply",
        dry_run["content_sha256"],
        None,
        0.0,
        0.0,
        "[]",
        "[]",
        "review",
    )
    assert json.loads(audit_row[10]) == dry_run["metadata_json_preview"]
    assert "SHOULD_NOT_LEAK" not in audit_row[10]
    assert "token=" not in audit_row[10]


def test_python_module_cli_dogfood_query_preview_cleanup_restore_audit_write_preflight_fails_closed_on_duplicate(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-restore-audit-duplicate.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Query preview cleanup duplicate audit contract target phrase is RESTORE_DUPLICATE_OK.",
        metadata={"project": "query-preview-cleanup-restore-audit-duplicate"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Query preview cleanup duplicate audit contract",
        predicate="target_phrase",
        object_ref_or_value="RESTORE_DUPLICATE_OK",
        evidence_ids=[source.id],
        scope="project:query-preview-cleanup-restore-audit-duplicate",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "restore duplicate token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:query-preview-cleanup-restore-audit-duplicate",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 1",
            ("token=SHOULD_NOT_LEAK", "2026-01-01 00:00:00"),
        )

    cleanup_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
            "--reason",
            "create rollback artifact before duplicate audit preflight test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert cleanup_result.returncode == 0, cleanup_result.stderr
    rollback_path = Path(json.loads(cleanup_result.stdout)["apply"]["rollback_manifest"]["artifact_path"])

    restore_command = [
        sys.executable,
        "-m",
        "agent_memory.api.cli",
        "dogfood",
        "query-preview-cleanup-restore",
        str(db_path),
        str(rollback_path),
        "--apply",
        "--policy",
        "legacy-query-preview-cleanup-restore-v1",
        "--actor",
        "cli-test",
        "--reason",
        "restore duplicate audit contract reason token=SHOULD_NOT_LEAK",
    ]
    first_restore_result = subprocess.run(
        restore_command,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert first_restore_result.returncode == 0, first_restore_result.stderr
    first_payload = json.loads(first_restore_result.stdout)
    first_dry_run = first_payload["restore_apply_contract"]["audit_preview"]["write_dry_run"]
    first_apply_contract = first_dry_run["apply_contract"]
    first_preflight = first_apply_contract["preflight"]
    assert first_preflight["passed"] is True
    assert first_preflight["write_allowed"] is False

    duplicate_metadata_json = json.dumps(first_dry_run["metadata_json_preview"], sort_keys=True)
    with sqlite3.connect(db_path) as connection:
        before_trace_count = connection.execute("SELECT COUNT(*) FROM experience_traces").fetchone()[0]
        connection.execute(
            """
            INSERT INTO experience_traces (
                surface,
                event_kind,
                content_sha256,
                summary,
                salience,
                user_emphasis,
                related_memory_refs_json,
                related_observation_ids_json,
                retention_policy,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                first_apply_contract["insert_preview"]["surface"],
                first_apply_contract["insert_preview"]["event_kind"],
                first_apply_contract["insert_preview"]["content_sha256"],
                None,
                0.0,
                0.0,
                json.dumps([]),
                json.dumps([]),
                "review",
                duplicate_metadata_json,
            ),
        )

    duplicate_restore_result = subprocess.run(
        restore_command,
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert duplicate_restore_result.returncode == 0, duplicate_restore_result.stderr
    duplicate_payload = json.loads(duplicate_restore_result.stdout)
    duplicate_dry_run = duplicate_payload["restore_apply_contract"]["audit_preview"]["write_dry_run"]
    duplicate_apply_contract = duplicate_dry_run["apply_contract"]
    duplicate_preflight = duplicate_apply_contract["preflight"]

    assert duplicate_payload["read_only"] is True
    assert duplicate_payload["mutated"] is False
    assert duplicate_dry_run["would_insert"] is False
    assert duplicate_apply_contract["would_insert"] is False
    assert duplicate_apply_contract["audit_write_apply_available"] is False
    assert duplicate_preflight["status"] == "failed_blocked"
    assert duplicate_preflight["passed"] is False
    assert duplicate_preflight["write_allowed"] is False
    assert duplicate_preflight["write_blocked_by_preflight"] is True
    assert duplicate_preflight["duplicate_audit_event_count"] == 1
    assert duplicate_preflight["checks"]["duplicate_audit_event_absent"] is False
    assert duplicate_preflight["failed_checks"] == ["duplicate_audit_event_absent"]
    assert duplicate_preflight["conflict_policy"] == {
        "duplicate_audit_event": "fail_closed",
        "content_hash_mismatch": "fail_closed",
        "metadata_hash_mismatch": "fail_closed",
        "source_database_mismatch": "fail_closed",
        "artifact_integrity_failure": "fail_closed",
        "disposable_rehearsal_failure": "fail_closed",
        "privacy_leak_risk": "fail_closed",
    }
    assert "restore_audit_write_preflight_failed" in duplicate_preflight["blocked_reasons"]
    assert "duplicate_restore_audit_event" in duplicate_preflight["blocked_reasons"]
    assert duplicate_apply_contract["blocked_reasons"] == duplicate_preflight["blocked_reasons"]
    assert "SHOULD_NOT_LEAK" not in duplicate_restore_result.stdout
    assert "token=" not in duplicate_restore_result.stdout

    with sqlite3.connect(db_path) as connection:
        after_trace_count = connection.execute("SELECT COUNT(*) FROM experience_traces").fetchone()[0]
        rows = connection.execute("SELECT id, query_preview FROM retrieval_observations ORDER BY id").fetchall()
    assert after_trace_count == before_trace_count + 1
    assert rows == [(1, None)]


def test_python_module_cli_dogfood_query_preview_cleanup_restore_dry_run_blocks_source_database_mismatch(
    tmp_path: Path,
) -> None:
    source_db_path = tmp_path / "query-preview-cleanup-source.db"
    other_db_path = tmp_path / "query-preview-cleanup-other.db"
    for db_path in (source_db_path, other_db_path):
        initialize_database(db_path)
        source = ingest_source_text(
            db_path=db_path,
            source_type="transcript",
            content="Query preview cleanup restore mismatch target phrase is RESTORE_MISMATCH_OK.",
            metadata={"project": "query-preview-cleanup-restore-mismatch"},
        )
        fact = create_candidate_fact(
            db_path=db_path,
            subject_ref="Query preview cleanup restore mismatch",
            predicate="target_phrase",
            object_ref_or_value="RESTORE_MISMATCH_OK",
            evidence_ids=[source.id],
            scope="project:query-preview-cleanup-restore-mismatch",
            confidence=0.95,
        )
        approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(source_db_path),
            "source token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:query-preview-cleanup-restore-mismatch",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr
    with sqlite3.connect(source_db_path) as connection:
        connection.execute(
            "UPDATE retrieval_observations SET query_preview = ?, created_at = ? WHERE id = 1",
            ("token=SHOULD_NOT_LEAK", "2026-01-01 00:00:00"),
        )

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup",
            str(source_db_path),
            "--older-than",
            "2026-01-02T00:00:00",
            "--apply",
            "--policy",
            "legacy-query-preview-cleanup-v1",
            "--actor",
            "cli-test",
            "--reason",
            "create source-bound rollback artifact for mismatch dry run test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    apply_payload = json.loads(apply_result.stdout)
    rollback = apply_payload["apply"]["rollback_manifest"]
    assert rollback["source_database"]["fingerprint_sha256"]
    rollback_path = Path(rollback["artifact_path"])

    restore_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(other_db_path),
            str(rollback_path),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert restore_result.returncode == 0, restore_result.stderr
    payload = json.loads(restore_result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_restore_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "error"
    assert payload["source_database_match"]["matched"] is False
    assert payload["source_database_match"]["artifact_fingerprint_sha256"] == rollback["source_database"]["fingerprint_sha256"]
    assert payload["source_database_match"]["target_fingerprint_sha256"] != rollback["source_database"]["fingerprint_sha256"]
    assert "source_database_mismatch" in payload["warnings"]
    assert "source_database_mismatch" in payload["blocked_reasons"]
    assert payload["restore_preview"]["restorable_count"] == 0
    assert payload["restore_preview"]["target_rows_found_count"] == 0
    assert payload["restore_preview"]["skipped_count"] == 1
    assert "SHOULD_NOT_LEAK" not in restore_result.stdout
    assert "token=" not in restore_result.stdout

    with sqlite3.connect(source_db_path) as connection:
        source_rows = connection.execute(
            "SELECT id, query_preview FROM retrieval_observations ORDER BY id"
        ).fetchall()
    with sqlite3.connect(other_db_path) as connection:
        other_rows = connection.execute(
            "SELECT id, query_preview FROM retrieval_observations ORDER BY id"
        ).fetchall()
    assert source_rows == [(1, None)]
    assert other_rows == []


def test_python_module_cli_dogfood_query_preview_cleanup_restore_dry_run_reports_wrong_policy_as_read_only_error(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-wrong-policy.db"
    initialize_database(db_path)
    artifact_path = tmp_path / "wrong-policy-rollback-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "kind": "query_preview_cleanup_rollback_artifact",
                "policy": "legacy-query-preview-cleanup-v0",
                "operation": "restore_stored_query_excerpts",
                "row_count": 0,
                "rows": [],
            }
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(db_path),
            str(artifact_path),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_restore_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "error"
    assert payload["artifact"]["exists"] is True
    assert payload["artifact"]["policy"] == "legacy-query-preview-cleanup-v0"
    assert "artifact_policy_invalid" in payload["blocked_reasons"]
    assert payload["restore_preview"]["restorable_count"] == 0
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "token=" not in result.stdout


def test_python_module_cli_dogfood_query_preview_cleanup_restore_dry_run_blocks_artifact_integrity_mismatch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "query-preview-cleanup-integrity.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations(surface, query_sha256, query_preview, preferred_scope, limit_value, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("cli-test", "c" * 64, None, "project:integrity", 5, "2026-01-01 00:00:00"),
        )

    resolved_path = db_path.expanduser().resolve(strict=False)
    source_database = {
        "fingerprint_sha256": hashlib.sha256(
            f"query-preview-cleanup-source-db-v1\0{resolved_path}".encode()
        ).hexdigest(),
        "fingerprint_version": "query-preview-cleanup-source-db-v1",
        "path_sha256": hashlib.sha256(str(resolved_path).encode()).hexdigest(),
        "path_basename": resolved_path.name,
    }
    artifact_path = tmp_path / "tampered-rollback-artifact.json"
    artifact_path.write_text(
        json.dumps(
            {
                "kind": "query_preview_cleanup_rollback_artifact",
                "policy": "legacy-query-preview-cleanup-v1",
                "operation": "restore_stored_query_excerpts",
                "parameters": {"older_than": "2026-01-02T00:00:00"},
                "source_database": source_database,
                "row_count": 3,
                "rows": [
                    {"id": 1, "query_preview": "token=SHOULD_NOT_LEAK", "created_at": "2026-01-01 00:00:00"},
                    {"id": 1, "query_preview": "token=SHOULD_NOT_LEAK", "created_at": "2026-01-01 00:00:00"},
                ],
                "privacy": {"artifact_contains_private_query_preview": True, "do_not_commit": True},
            }
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "query-preview-cleanup-restore",
            str(db_path),
            str(artifact_path),
            "--dry-run",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_query_preview_cleanup_restore_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["status"] == "error"
    assert payload["artifact"]["row_count"] == 2
    assert payload["artifact"]["declared_row_count"] == 3
    assert payload["artifact_integrity"]["passed"] is False
    assert payload["artifact_integrity"]["duplicate_id_count"] == 1
    assert payload["artifact_integrity"]["declared_row_count_matches"] is False
    assert "artifact_row_count_mismatch" in payload["blocked_reasons"]
    assert "duplicate_artifact_row_ids" in payload["blocked_reasons"]
    assert payload["restore_preview"]["restorable_count"] == 0
    assert payload["restore_preview"]["skipped_count"] == 2
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "token=" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        rows = connection.execute("SELECT id, query_preview FROM retrieval_observations ORDER BY id").fetchall()
    assert rows == [(1, None)]


def test_python_module_cli_dogfood_ordinary_trace_metadata_cleanup_apply_requires_actor_reason_and_fills_safe_defaults_without_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "ordinary-trace-metadata-cleanup.db"
    initialize_database(db_path)
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="d" * 64,
        summary=None,
        scope="project:ordinary-trace-metadata-cleanup",
        retention_policy="ephemeral",
        metadata={
            "trace_recording": "default_metadata_only",
            "hook_event_name": "PreToolUse",
            "raw_prompt": "token=SHOULD_NOT_LEAK",
        },
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    preview_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "ordinary-trace-metadata-cleanup",
            str(db_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert preview_result.returncode == 0, preview_result.stderr
    preview = json.loads(preview_result.stdout)
    assert preview["kind"] == "dogfood_ordinary_trace_metadata_cleanup_preview"
    assert preview["read_only"] is True
    assert preview["mutated"] is False
    assert preview["affected_count"] == 2
    assert preview["fixable_row_count"] == 1
    assert preview["violation_counts"] == {
        "auto_approved_not_false": 1,
        "candidate_policy_not_evidence_only": 1,
    }
    assert preview["privacy"]["raw_trace_content_included"] is False
    assert preview["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in preview_result.stdout
    assert "token=" not in preview_result.stdout

    missing_actor_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "ordinary-trace-metadata-cleanup",
            str(db_path),
            "--apply",
            "--reason",
            "normalize legacy ordinary turn trace metadata after read-only preview",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_actor_result.returncode != 0

    missing_reason_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "ordinary-trace-metadata-cleanup",
            str(db_path),
            "--apply",
            "--actor",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert missing_reason_result.returncode != 0

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "ordinary-trace-metadata-cleanup",
            str(db_path),
            "--apply",
            "--actor",
            "cli-test",
            "--reason",
            "normalize legacy ordinary turn trace metadata after read-only preview",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert apply_result.returncode == 0, apply_result.stderr
    payload = json.loads(apply_result.stdout)
    assert payload["kind"] == "dogfood_ordinary_trace_metadata_cleanup_apply"
    assert payload["read_only"] is False
    assert payload["mutated"] is True
    assert payload["affected_count"] == 2
    assert payload["fixable_row_count"] == 1
    assert payload["normalized_row_count"] == 1
    assert payload["remaining_violation_count"] == 0
    assert payload["apply"]["actor"] == "cli-test"
    assert payload["apply"]["reason_sha256"]
    assert payload["apply"]["audit_trace_id"]
    assert payload["privacy"]["raw_trace_content_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in apply_result.stdout
    assert "token=" not in apply_result.stdout

    with sqlite3.connect(db_path) as connection:
        trace = connection.execute(
            "SELECT metadata_json FROM experience_traces WHERE event_kind = 'turn'"
        ).fetchone()
        audit = connection.execute(
            "SELECT event_kind, summary, metadata_json FROM experience_traces ORDER BY id DESC LIMIT 1"
        ).fetchone()
    metadata = json.loads(trace[0])
    assert metadata["candidate_policy"] == "evidence_only"
    assert metadata["auto_approved"] is False
    assert "raw_prompt" not in metadata
    assert audit[0] == "dogfood_ordinary_trace_metadata_cleanup_apply"
    assert audit[1] is None
    audit_metadata = json.loads(audit[2])
    assert audit_metadata["normalized_row_count"] == 1
    assert audit_metadata["remaining_violation_count"] == 0
    assert "SHOULD_NOT_LEAK" not in audit[2]
    assert "token=" not in audit[2]



def test_python_module_cli_dogfood_trace_quality_reports_read_only_aggregate_signals_without_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "trace-quality.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Trace quality target phrase is TRACE_QUALITY_OK.",
        metadata={"project": "trace-quality"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Trace quality",
        predicate="target_phrase",
        object_ref_or_value="TRACE_QUALITY_OK",
        evidence_ids=[source.id],
        scope="project:trace-quality",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    for query in (
        "What is the trace quality phrase? token=SHOULD_NOT_LEAK",
        "Repeat the trace quality phrase.",
        "No matching trace quality api key SHOULD_NOT_LEAK",
    ):
        retrieve_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "agent_memory.api.cli",
                "retrieve",
                str(db_path),
                query,
                "--preferred-scope",
                "project:trace-quality",
                "--observe",
                "cli-test",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
        )
        assert retrieve_result.returncode == 0, retrieve_result.stderr

    with sqlite3.connect(db_path) as connection:
        observation_ids = [
            int(row[0])
            for row in connection.execute("SELECT id FROM retrieval_observations ORDER BY id ASC").fetchall()
        ]
    assert len(observation_ids) == 3
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE retrieval_observations SET retrieved_memory_refs_json = '[]', top_memory_ref = NULL WHERE id = ?",
            (observation_ids[2],),
        )
        connection.execute(
            "UPDATE memory_activations SET activation_kind = 'empty_retrieval', memory_ref = NULL, strength = 0.0 WHERE observation_id = ?",
            (observation_ids[2],),
        )

    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="d" * 64,
        summary=None,
        scope="project:trace-quality",
        related_memory_refs=[f"fact:{fact.id}"],
        related_observation_ids=[observation_ids[0]],
        retention_policy="ephemeral",
        metadata={
            "trace_recording": "default_metadata_only",
            "candidate_policy": "evidence_only",
            "auto_approved": False,
            "raw_user_message": "token=SHOULD_NOT_LEAK",
        },
    )
    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="remember_intent",
        content_sha256="e" * 64,
        summary="User explicitly asked to remember a trace-quality preference.",
        scope="project:trace-quality",
        retention_policy="review",
        metadata={
            "remember_intent": "explicit",
            "candidate_policy": "review_required",
            "auto_approved": False,
            "secret_scan": "passed",
        },
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-quality",
            str(db_path),
            "--since-hours",
            "24",
            "--min-trace-coverage",
            "0.25",
            "--min-evidence-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_trace_quality"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["time_window"]["since_hours"] == 24
    assert payload["coverage"]["observation_count"] == 3
    assert payload["coverage"]["trace_count"] == 2
    assert payload["coverage"]["observations_linked_from_traces"] == 1
    assert payload["coverage"]["observation_trace_coverage_ratio"] == 0.3333
    assert payload["coverage_diagnostics"] == {
        "unlinked_observation_count": 2,
        "trace_without_observation_link_count": 1,
        "activation_count": 3,
        "activations_linked_to_traces": 1,
        "activation_trace_link_coverage_ratio": 0.3333,
        "likely_gap": "traces_missing_observation_links",
        "next_action": "Verify the runtime links new metadata-only turn traces to retrieval observation ids before broad G4 planning.",
    }
    assert payload["retrieval_quality"]["empty_retrieval_count"] == 1
    assert payload["retrieval_quality"]["empty_retrieval_ratio"] == 0.3333
    assert payload["retrieval_quality"]["repeated_memory_ref_count"] == 1
    assert payload["trace_distribution"]["event_kind_counts"] == {"remember_intent": 1, "turn": 1}
    assert payload["trace_distribution"]["retention_policy_counts"] == {"ephemeral": 1, "review": 1}
    assert payload["invariants"]["ordinary_trace_metadata_only"]["violation_count"] == 0
    assert payload["candidate_signals"]["related_memory_ref_count"] == 1
    assert payload["recommendation"] in {"continue_dogfooding", "ready_for_more_dry_runs", "consider_g4_plan"}
    assert payload["privacy"]["raw_conversation_content_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "api key" not in result.stdout.lower()
    assert "token=" not in result.stdout
    assert "TRACE_QUALITY_OK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_trace_quality_epoch_start_filters_legacy_rows(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "trace-quality-epoch.db"
    initialize_database(db_path)
    old_time = "2026-05-09 00:00:00"
    epoch_start = "2026-05-10T00:00:00Z"
    fresh_time = "2026-05-10 00:05:00"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', ?, '', 'project:legacy', 1, '["approved"]', '[]', NULL, NULL, ?)
            """,
            (old_time, "a" * 64, json.dumps({"hook_event_name": "pre_llm_call"})),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', ?, '', 'project:fresh', 1, '["approved"]', '["fact:1"]', 'fact:1', 'direct', ?)
            """,
            (fresh_time, "b" * 64, json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "retrieved_memory"})),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, strength, scope, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 1, NULL, 0.0, 'project:legacy', '{}')
            """,
            (old_time,),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, strength, scope, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', 'retrieved', 'fact:1', 2, 1, 1.0, 'project:fresh', '{}')
            """,
            (fresh_time,),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, content_sha256, summary, scope,
                related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', 'turn', ?, NULL, 'project:fresh', '["fact:1"]', '[2]', 'ephemeral', ?)
            """,
            (fresh_time, "c" * 64, json.dumps({"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only", "auto_approved": False})),
        )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-quality",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--min-trace-coverage",
            "0.95",
            "--min-evidence-count",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_trace_quality"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["time_window"]["epoch_start"] == "2026-05-10 00:00:00"
    assert payload["time_window"]["historical_rows_excluded"] == {
        "experience_traces": 0,
        "memory_activations": 1,
        "retrieval_observations": 1,
    }
    assert payload["coverage"]["observation_count"] == 1
    assert payload["coverage"]["trace_count"] == 1
    assert payload["coverage"]["observation_trace_coverage_ratio"] == 1.0
    assert payload["retrieval_quality"]["empty_retrieval_count"] == 0
    assert payload["warnings"] == []
    assert payload["privacy"]["aggregate_only"] is True

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_fresh_epoch_filters_historical_telemetry_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh-epoch.db"
    initialize_database(db_path)
    old_time = "2026-05-09 00:00:00"
    epoch_start = "2026-05-10T00:00:00Z"
    new_time = "2026-05-10 00:05:00"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', ?, '', 'project:old', 1, '["approved"]', '[]', NULL, NULL, ?)
            """,
            (old_time, "a" * 64, json.dumps({"hook_event_name": "pre_llm_call"})),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', ?, '', 'project:fresh', 1, '["approved"]', '["fact:1"]', 'fact:1', 'direct', ?)
            """,
            (
                new_time,
                "b" * 64,
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "retrieved_memory"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (3, ?, 'hermes-pre-llm-hook', ?, '', 'project:fresh', 1, '["approved"]', '[]', NULL, 'verify_first', ?)
            """,
            (
                new_time,
                "c" * 64,
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "no_reliable_memory"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, summary,
                related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', 'turn', 'project:old', ?, NULL, '[]', '[]', 'ephemeral', '{}')
            """,
            (old_time, "d" * 64),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, summary,
                related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', 'turn', 'project:fresh', ?, NULL, '["fact:1"]', '[2]', 'ephemeral', ?)
            """,
            (
                new_time,
                "e" * 64,
                json.dumps({"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only", "auto_approved": False}),
            ),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, summary,
                related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (3, ?, 'hermes-pre-llm-hook', 'turn', 'project:fresh', ?, NULL, '[]', '[3]', 'ephemeral', ?)
            """,
            (
                new_time,
                "f" * 64,
                json.dumps({"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only", "auto_approved": False}),
            ),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 1, NULL, 'project:old', '{}')
            """,
            (old_time,),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', 'retrieved', 'fact:1', 2, NULL, 'project:fresh', '{}')
            """,
            (new_time,),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json
            ) VALUES (3, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 3, NULL, 'project:fresh', '{}')
            """,
            (new_time,),
        )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    output_path = tmp_path / "fresh-epoch.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "fresh-epoch",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--output",
            str(output_path),
            "--min-trace-coverage",
            "1.0",
            "--min-evidence-count",
            "1",
            "--high-empty-threshold",
            "0.75",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_fresh_epoch_readiness"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["epoch"]["started_at"] == "2026-05-10 00:00:00"
    assert payload["epoch"]["historical_rows_excluded"] == {
        "retrieval_observations": 1,
        "memory_activations": 1,
        "experience_traces": 1,
    }
    assert payload["coverage"] == {
        "observation_count": 2,
        "trace_count": 2,
        "activation_count": 2,
        "observations_linked_from_traces": 2,
        "observation_trace_coverage_ratio": 1.0,
    }
    assert payload["coverage_diagnostics"]["activation_trace_link_coverage_ratio"] == 1.0
    assert payload["coverage_diagnostics"]["likely_gap"] == "no_linkage_gap_detected"
    assert payload["empty_retrieval_diagnostics"]["count"] == 1
    assert payload["empty_retrieval_diagnostics"]["ratio"] == 0.5
    assert payload["empty_retrieval_diagnostics"]["by_response_mode"] == {"verify_first": 1}
    assert payload["empty_retrieval_diagnostics"]["by_retrieval_outcome"] == {"no_reliable_memory": 1}
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "fresh_epoch_ready_to_compare_against_historical",
        "blocked_reasons": [],
    }
    assert payload["automation_policy"]["apply_supported"] is False
    assert payload["automation_policy"]["telemetry_reset_apply_supported"] is False
    assert payload["privacy"]["aggregate_only"] is True
    assert "SHOULD_NOT_LEAK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_fresh_epoch_compare_gates_metadata_rich_reports_without_leaks(
    tmp_path: Path,
) -> None:
    first_report = tmp_path / "fresh-epoch-1.json"
    second_report = tmp_path / "fresh-epoch-2.json"
    first_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_fresh_epoch_readiness",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "epoch": {
                    "started_at": "2026-05-10 00:00:00",
                    "historical_rows_excluded": {"retrieval_observations": 10},
                    "latest_created_at": "2026-05-10 00:05:00",
                },
                "coverage": {
                    "observation_count": 2,
                    "trace_count": 2,
                    "observation_trace_coverage_ratio": 1.0,
                },
                "empty_retrieval_diagnostics": {
                    "count": 1,
                    "ratio": 0.5,
                    "unknown_outcome_drilldown": {"count": 0, "unresolved_count": 0},
                    "metadata_gap_diagnostic": {
                        "unknown_empty_outcome_count": 0,
                        "unresolved_adapter_payload_gap_count": 0,
                        "classified_missing_outcome_count": 0,
                        "dominant_blocker": "none",
                        "classification_confidence": "complete",
                    },
                },
                "quality_gate": {
                    "pass": True,
                    "decision": "fresh_epoch_ready_to_compare_against_historical",
                    "blocked_reasons": [],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    second_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_fresh_epoch_readiness",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "epoch": {
                    "started_at": "2026-05-10 00:00:00",
                    "historical_rows_excluded": {"retrieval_observations": 11},
                    "latest_created_at": "2026-05-10 00:10:00",
                },
                "coverage": {
                    "observation_count": 3,
                    "trace_count": 3,
                    "observation_trace_coverage_ratio": 1.0,
                },
                "empty_retrieval_diagnostics": {
                    "count": 1,
                    "ratio": 0.3333333333,
                    "unknown_outcome_drilldown": {"count": 0, "unresolved_count": 0},
                    "metadata_gap_diagnostic": {
                        "unknown_empty_outcome_count": 0,
                        "unresolved_adapter_payload_gap_count": 0,
                        "classified_missing_outcome_count": 0,
                        "dominant_blocker": "none",
                        "classification_confidence": "complete",
                    },
                },
                "quality_gate": {
                    "pass": True,
                    "decision": "fresh_epoch_ready_to_compare_against_historical",
                    "blocked_reasons": [],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "fresh-epoch-compare.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "fresh-epoch-compare",
            "--report",
            str(first_report),
            "--report",
            str(second_report),
            "--output",
            str(output_path),
            "--min-report-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_fresh_epoch_comparison"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["report_count"] == 2
    assert payload["aggregate"]["quality_gate_pass_count"] == 2
    assert payload["aggregate"]["observation_count_total"] == 5
    assert payload["aggregate"]["trace_coverage_ratio_min"] == 1.0
    assert payload["aggregate"]["empty_retrieval_ratio_max"] == 0.5
    assert payload["aggregate"]["unresolved_unknown_empty_outcome_count_total"] == 0
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "fresh_epoch_collection_stable_for_historical_comparison",
        "blocked_reasons": [],
    }
    assert payload["automation_policy"]["telemetry_reset_apply_supported"] is False
    assert payload["privacy"]["raw_conversation_content_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout


def test_python_module_cli_dogfood_fresh_epoch_compare_blocks_unresolved_metadata_gap(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "fresh-epoch-gap.json"
    report_path.write_text(
        json.dumps(
            {
                "kind": "dogfood_fresh_epoch_readiness",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "epoch": {"started_at": "2026-05-10 00:00:00", "latest_created_at": "2026-05-10 00:05:00"},
                "coverage": {"observation_count": 1, "trace_count": 1, "observation_trace_coverage_ratio": 1.0},
                "empty_retrieval_diagnostics": {
                    "count": 1,
                    "ratio": 1.0,
                    "unknown_outcome_drilldown": {"count": 1, "unresolved_count": 1},
                    "metadata_gap_diagnostic": {
                        "unknown_empty_outcome_count": 1,
                        "unresolved_adapter_payload_gap_count": 1,
                        "classified_missing_outcome_count": 0,
                        "dominant_blocker": "adapter_payload_gap",
                        "classification_confidence": "low",
                    },
                },
                "quality_gate": {
                    "pass": False,
                    "decision": "continue_fresh_epoch_dogfooding",
                    "blocked_reasons": ["epoch_empty_retrieval_outcome_unknown"],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "fresh-epoch-compare",
            "--report",
            str(report_path),
            "--min-report-count",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["aggregate"]["unresolved_unknown_empty_outcome_count_total"] == 1
    assert payload["aggregate"]["metadata_dominant_blocker_counts"] == {"adapter_payload_gap": 1}
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "continue_fresh_epoch_collection_before_historical_comparison"
    assert payload["quality_gate"]["blocked_reasons"] == [
        "fresh_epoch_quality_gate_not_stable",
        "unresolved_fresh_epoch_metadata_gap_present",
        "blocked_reasons_present",
    ]


def _seed_minimal_fresh_epoch_gate_pass(db_path: Path, *, epoch_start: str = "2026-05-10T00:00:00Z") -> None:
    del epoch_start
    new_time = "2026-05-10 00:05:00"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', ?, '', 'project:fresh', 1, '["approved"]', '["fact:1"]', 'fact:1', 'direct', ?)
            """,
            (
                new_time,
                "a" * 64,
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "retrieved_memory"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', ?, '', 'project:fresh', 1, '["approved"]', '[]', NULL, 'verify_first', ?)
            """,
            (
                new_time,
                "b" * 64,
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "no_reliable_memory"}),
            ),
        )
        for trace_id, observation_id, refs, sha in [
            (1, 1, '["fact:1"]', "c" * 64),
            (2, 2, '[]', "d" * 64),
        ]:
            connection.execute(
                """
                INSERT INTO experience_traces (
                    id, created_at, surface, event_kind, scope, content_sha256, summary,
                    related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', 'turn', 'project:fresh', ?, NULL, ?, ?, 'ephemeral', ?)
                """,
                (
                    trace_id,
                    new_time,
                    sha,
                    refs,
                    json.dumps([observation_id]),
                    json.dumps({"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only", "auto_approved": False}),
                ),
            )


def _write_fresh_epoch_comparison_report(path: Path, *, passed: bool) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "dogfood_fresh_epoch_comparison",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "report_count": 2,
                "aggregate": {
                    "quality_gate_pass_count": 2 if passed else 1,
                    "observation_count_total": 4,
                    "trace_count_total": 4,
                    "trace_coverage_ratio_min": 1.0,
                    "trace_coverage_ratio_max": 1.0,
                    "empty_retrieval_ratio_min": 0.0,
                    "empty_retrieval_ratio_max": 0.5,
                    "unknown_empty_outcome_count_total": 0 if passed else 1,
                    "unresolved_unknown_empty_outcome_count_total": 0 if passed else 1,
                    "classified_missing_outcome_count_total": 0,
                    "metadata_dominant_blocker_counts": {"none": 2} if passed else {"adapter_payload_gap": 1},
                    "metadata_classification_confidence_counts": {"complete": 2} if passed else {"low": 1},
                    "blocked_reasons": [] if passed else ["epoch_empty_retrieval_outcome_unknown"],
                },
                "quality_gate": {
                    "pass": passed,
                    "decision": "fresh_epoch_collection_stable_for_historical_comparison"
                    if passed
                    else "continue_fresh_epoch_collection_before_historical_comparison",
                    "blocked_reasons": []
                    if passed
                    else [
                        "fresh_epoch_quality_gate_not_stable",
                        "unresolved_fresh_epoch_metadata_gap_present",
                        "blocked_reasons_present",
                    ],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "raw_report_included": False,
                },
            }
        ),
        encoding="utf-8",
    )



def test_python_module_cli_dogfood_fresh_epoch_runway_writes_artifacts_and_reconciliation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh-epoch-runway.db"
    initialize_database(db_path)
    epoch_start = "2026-05-10T00:00:00Z"
    _seed_minimal_fresh_epoch_gate_pass(db_path, epoch_start=epoch_start)
    previous_report = tmp_path / "fresh-epoch-previous.json"
    previous_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_fresh_epoch_readiness",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "epoch": {
                    "started_at": "2026-05-10 00:00:00",
                    "latest_created_at": "2026-05-10 00:03:00",
                },
                "coverage": {
                    "observation_count": 2,
                    "trace_count": 2,
                    "observation_trace_coverage_ratio": 1.0,
                },
                "empty_retrieval_diagnostics": {
                    "count": 1,
                    "ratio": 0.5,
                    "unknown_outcome_drilldown": {"count": 0, "unresolved_count": 0},
                    "metadata_gap_diagnostic": {
                        "unknown_empty_outcome_count": 0,
                        "unresolved_adapter_payload_gap_count": 0,
                        "classified_missing_outcome_count": 0,
                        "dominant_blocker": "none",
                        "classification_confidence": "complete",
                    },
                },
                "quality_gate": {
                    "pass": True,
                    "decision": "fresh_epoch_ready_to_compare_against_historical",
                    "blocked_reasons": [],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    report_dir = tmp_path / "runway"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "fresh-epoch-runway",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--report-dir",
            str(report_dir),
            "--baseline-report",
            str(previous_report),
            "--artifact-prefix",
            "test-runway",
            "--high-empty-threshold",
            "1.0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_fresh_epoch_runway"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "fresh_epoch_runway_ready_for_manual_telemetry_reconciliation",
        "blocked_reasons": [],
    }
    artifacts = payload["artifacts"]
    for key in ["fresh_epoch_report", "fresh_epoch_comparison_report", "telemetry_reconciliation_report"]:
        assert Path(artifacts[key]).exists(), key
    assert json.loads(Path(artifacts["fresh_epoch_report"]).read_text())["kind"] == "dogfood_fresh_epoch_readiness"
    comparison = json.loads(Path(artifacts["fresh_epoch_comparison_report"]).read_text())
    assert comparison["report_count"] == 2
    assert comparison["quality_gate"]["pass"] is True
    reconciliation = json.loads(Path(artifacts["telemetry_reconciliation_report"]).read_text())
    assert reconciliation["fresh_epoch_comparison_evidence"]["usable_for_reset_avoidance"] is True
    assert reconciliation["quality_gate"]["pass"] is True
    assert payload["automation_policy"]["telemetry_reset_apply_supported"] is False
    assert payload["privacy"]["raw_report_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout


def test_python_module_cli_dogfood_telemetry_reconciliation_accepts_green_fresh_epoch_comparison_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "telemetry-reconciliation-green.db"
    initialize_database(db_path)
    epoch_start = "2026-05-10T00:00:00Z"
    _seed_minimal_fresh_epoch_gate_pass(db_path, epoch_start=epoch_start)
    comparison_path = tmp_path / "fresh-epoch-compare-green.json"
    _write_fresh_epoch_comparison_report(comparison_path, passed=True)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "telemetry-reconciliation",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--fresh-epoch-comparison-report",
            str(comparison_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_telemetry_reconciliation"
    evidence = payload["fresh_epoch_comparison_evidence"]
    assert evidence["provided"] is True
    assert evidence["usable_for_reset_avoidance"] is True
    assert evidence["quality_gate_pass"] is True
    assert evidence["unresolved_unknown_empty_outcome_count_total"] == 0
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "telemetry_only_reconciliation_ready_for_manual_apply",
        "blocked_reasons": [],
    }
    assert payload["apply_corridor"]["safety_gate"]["fresh_epoch_comparison_required_for_live_apply"] is True
    assert payload["apply_corridor"]["telemetry_reset_apply_supported"] is False
    assert payload["privacy"]["raw_report_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout


def test_python_module_cli_dogfood_telemetry_reconciliation_blocks_failed_fresh_epoch_comparison_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "telemetry-reconciliation-blocked.db"
    initialize_database(db_path)
    epoch_start = "2026-05-10T00:00:00Z"
    _seed_minimal_fresh_epoch_gate_pass(db_path, epoch_start=epoch_start)
    comparison_path = tmp_path / "fresh-epoch-compare-blocked.json"
    _write_fresh_epoch_comparison_report(comparison_path, passed=False)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "telemetry-reconciliation",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--fresh-epoch-comparison-report",
            str(comparison_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    evidence = payload["fresh_epoch_comparison_evidence"]
    assert evidence["provided"] is True
    assert evidence["usable_for_reset_avoidance"] is False
    assert evidence["quality_gate_pass"] is False
    assert evidence["unresolved_unknown_empty_outcome_count_total"] == 1
    assert payload["quality_gate"] == {
        "pass": False,
        "decision": "continue_fresh_epoch_collection_before_telemetry_reconciliation_apply",
        "blocked_reasons": ["fresh_epoch_comparison_not_green"],
    }
    assert payload["apply_corridor"]["telemetry_reset_apply_supported"] is False


def test_python_module_cli_dogfood_fresh_epoch_classifies_unknown_empty_retrieval_outcomes(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "fresh-epoch-unknown.db"
    initialize_database(db_path)
    epoch_start = "2026-05-10T00:00:00Z"
    created_at = "2026-05-10 00:05:00"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK', 'project:fresh', 1, '["approved"]', '[]', NULL, 'verify_first', ?)
            """,
            (created_at, "a" * 64, json.dumps({"hook_event_name": "pre_llm_call"})),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, ?, 'custom-adapter', ?, 'SHOULD_NOT_LEAK', 'project:fresh', 1, '["approved"]', '[]', NULL, NULL, '{}')
            """,
            (created_at, "b" * 64),
        )
        for trace_id, observation_id in [(1, 1), (2, 2)]:
            connection.execute(
                """
                INSERT INTO experience_traces (
                    id, created_at, surface, event_kind, scope, content_sha256, summary,
                    related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', 'turn', 'project:fresh', ?, NULL, '[]', ?, 'ephemeral', ?)
                """,
                (
                    trace_id,
                    created_at,
                    str(trace_id) * 64,
                    json.dumps([observation_id]),
                    json.dumps({"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only", "auto_approved": False}),
                ),
            )
        for activation_id, observation_id in [(1, 1), (2, 2)]:
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, ?, NULL, 'project:fresh', '{}')
                """,
                (activation_id, created_at, observation_id),
            )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "fresh-epoch",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--min-trace-coverage",
            "1.0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    diagnostics = payload["empty_retrieval_diagnostics"]
    assert diagnostics["by_retrieval_outcome"] == {"unknown": 2}
    assert diagnostics["by_likely_cause"] == {
        "adapter_payload_gap": 1,
        "legacy_missing_outcome_no_reliable_memory": 1,
    }
    assert diagnostics["unknown_outcome_drilldown"] == {
        "count": 2,
        "unresolved_count": 1,
        "by_likely_cause": {
            "adapter_payload_gap": 1,
            "legacy_missing_outcome_no_reliable_memory": 1,
        },
        "classification_rule": "metadata-only aggregate inference from hook_event_name and response_mode",
        "next_action": "Prefer more v0.1.129+ dogfood or a targeted metadata backfill preview before telemetry reset.",
    }
    assert diagnostics["metadata_gap_diagnostic"] == {
        "unknown_empty_outcome_count": 2,
        "unresolved_adapter_payload_gap_count": 1,
        "classified_missing_outcome_count": 1,
        "dominant_blocker": "adapter_payload_gap",
        "classification_confidence": "partial",
        "next_action": "Fix adapter payload metadata for unresolved empty observations before treating classified legacy gaps as reset-safe.",
    }
    assert payload["quality_gate"] == {
        "pass": False,
        "decision": "continue_fresh_epoch_dogfooding",
        "blocked_reasons": ["high_epoch_empty_retrieval_ratio", "epoch_empty_retrieval_outcome_unknown"],
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_telemetry_reset_preview_is_read_only_and_protects_memory_tables(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "telemetry-reset-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Telemetry reset preview protected memory SHOULD_NOT_LEAK.",
        metadata={"project": "telemetry-reset-preview"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Telemetry reset preview",
        predicate="protected",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:telemetry-reset-preview",
        confidence=0.9,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    old_time = "2026-05-09 00:00:00"
    new_time = "2026-05-10 00:05:00"
    epoch_start = "2026-05-10T00:00:00Z"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK', 'project:old', 1, '["approved"]', '[]', NULL, NULL, '{}')
            """,
            (old_time, "a" * 64),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, ?, 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK', 'project:new', 1, '["approved"]', '["fact:1"]', 'fact:1', 'direct', '{}')
            """,
            (new_time, "b" * 64),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json)
            VALUES (1, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 1, NULL, 'project:old', '{}'),
                   (2, ?, 'hermes-pre-llm-hook', 'retrieved', 'fact:1', 2, NULL, 'project:new', '{}')
            """,
            (old_time, new_time),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, summary,
                related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, ?, 'hermes-pre-llm-hook', 'turn', 'project:old', ?, 'SHOULD_NOT_LEAK', '[]', '[1]', 'ephemeral', '{}'),
                     (2, ?, 'hermes-pre-llm-hook', 'turn', 'project:new', ?, 'SHOULD_NOT_LEAK', '["fact:1"]', '[2]', 'ephemeral', '{}')
            """,
            (old_time, "c" * 64, new_time, "d" * 64),
        )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (
                "retrieval_observations",
                "memory_activations",
                "experience_traces",
                "facts",
                "source_records",
                "relations",
                "memory_status_transitions",
            )
        }

    output_path = tmp_path / "telemetry-reset-preview.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "telemetry-reset-preview",
            str(db_path),
            "--epoch-start",
            epoch_start,
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_telemetry_reset_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["reset_scope"] == "telemetry_only"
    assert payload["epoch_filter"] == {"enabled": True, "retain_rows_created_at_gte": "2026-05-10 00:00:00"}
    assert payload["candidate_delete_total"] == 3
    assert payload["telemetry_tables"]["retrieval_observations"]["candidate_rows"] == 1
    assert payload["telemetry_tables"]["memory_activations"]["candidate_rows"] == 1
    assert payload["telemetry_tables"]["experience_traces"]["candidate_rows"] == 1
    assert payload["guardrails"] == {
        "apply_supported": False,
        "requires_backup_before_future_apply": True,
        "default_retrieval_unchanged": True,
        "protected_memory_tables_mutated": False,
        "telemetry_tables_only": ["retrieval_observations", "memory_activations", "experience_traces"],
    }
    assert payload["protected_tables"]["facts"] == 1
    assert payload["protected_tables"]["source_records"] == 1
    assert payload["privacy"]["aggregate_only"] is True
    assert "SHOULD_NOT_LEAK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_g4_review_queue_preview_is_ref_safe_and_read_only(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 review queue sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-review-queue"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 review queue",
        predicate="sensitive",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-review-queue",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 5):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-review-queue', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (index, hashlib.sha256(f"query-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, NULL,
                          'project:g4-review-queue', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index),
            )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "memory_activations", "retrieval_observations", "experience_traces")
        }

    output_path = tmp_path / "g4-review-queue-preview.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-review-queue-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--queue-limit",
            "5",
            "--frequent-threshold",
            "3",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_review_queue_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "queue_persistence_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
    }
    reassessment = payload["broad_g4_apply_reassessment"]
    assert reassessment["broad_g4_apply_allowed"] is False
    assert reassessment["decision"] == "broad_g4_apply_still_blocked_until_all_live_safety_gates_pass"
    assert reassessment["required_green_gates"] == [
        "retrieval_ranking_gate_pass",
        "rollback_confidence_pass",
        "rollback_replay_validate_pass",
        "live_telemetry_reconciliation_pass",
        "human_review_queue_approval_pass",
    ]
    assert reassessment["current_report_green"] is payload["quality_gate"]["pass"]
    assert reassessment["default_retrieval_unchanged"] is True
    assert reassessment["ordinary_conversation_auto_approval"] is False
    assert payload["queue_count"] >= 1
    entry = payload["queue"][0]
    assert entry["proposal_type"] == "reinforcement_review"
    assert entry["target_ref"] == f"fact:{fact.id}"
    assert entry["policy"] == {
        "requires_human_review": True,
        "auto_apply_allowed": False,
        "approval_required": True,
        "approval_phrase": "approve-g4-review-queue-item",
    }
    assert entry["ref_safe_evidence"]["raw_content_included"] is False
    assert entry["ref_safe_evidence"]["sample_values_included"] is False
    assert entry["audit_contract"]["required_fields"] == [
        "actor",
        "reason",
        "policy",
        "evidence_refs",
        "source_queue_id",
    ]
    assert payload["privacy"]["aggregate_or_ref_only"] is True
    assert "SHOULD_NOT_LEAK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts




def test_python_module_cli_dogfood_g4_review_queue_preview_consumes_green_gate_artifacts_without_broad_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-artifacts.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 artifact sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-review-artifacts"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 artifact review",
        predicate="safe_gate",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-review-artifacts",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 4):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', ?, '',
                          'project:g4-review-artifacts', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (
                    index,
                    hashlib.sha256(f"artifact-query-{index}".encode()).hexdigest(),
                    json.dumps([f"fact:{fact.id}"]),
                    f"fact:{fact.id}",
                ),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, ?,
                          'project:g4-review-artifacts', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index, index),
            )
            connection.execute(
                """
                INSERT INTO experience_traces (
                    id, created_at, surface, event_kind, content_sha256, summary, scope,
                    related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', 'turn', ?, NULL,
                          'project:g4-review-artifacts', ?, ?, 'ephemeral', ?)
                """,
                (
                    index,
                    hashlib.sha256(f"artifact-trace-{index}".encode()).hexdigest(),
                    json.dumps([f"fact:{fact.id}"]),
                    json.dumps([index]),
                    json.dumps({"trace_recording": "default_metadata_only", "auto_approved": False}),
                ),
            )

    ranking_report = tmp_path / "ranking.json"
    ranking_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_retrieval_ranking_experiment",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "fixture_expansion": {"task_count": 50, "live_runtime_safe": True},
                "shadow_compare": {
                    "baseline_regression_count": 0,
                    "protected_default_order_returned": True,
                    "durable_memory_mutated": False,
                },
            }
        ),
        encoding="utf-8",
    )
    rollback_confidence_report = tmp_path / "rollback-confidence.json"
    rollback_confidence_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_confidence",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
            }
        ),
        encoding="utf-8",
    )
    rollback_replay_report = tmp_path / "rollback-replay.json"
    rollback_replay_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_replay_validate",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
            }
        ),
        encoding="utf-8",
    )
    telemetry_report = tmp_path / "telemetry.json"
    telemetry_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_telemetry_reconciliation",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    approval_report = tmp_path / "human-approval.json"
    approval_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_review_queue_approval_report",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "human_review_queue_approval_pass": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "privacy": {
                    "proposal_json_included": False,
                    "raw_content_included": False,
                    "raw_reason_included": False,
                    "sample_values_included": False,
                    "aggregate_or_ref_only": True,
                },
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-review-queue-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--queue-limit",
            "5",
            "--frequent-threshold",
            "3",
            "--retrieval-ranking-report",
            str(ranking_report),
            "--rollback-confidence-report",
            str(rollback_confidence_report),
            "--rollback-replay-report",
            str(rollback_replay_report),
            "--telemetry-reconciliation-report",
            str(telemetry_report),
            "--human-review-approval-report",
            str(approval_report),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    reassessment = payload["broad_g4_apply_reassessment"]
    assert reassessment["artifact_gate_evidence"] == {
        "retrieval_ranking_gate_pass": True,
        "rollback_confidence_pass": True,
        "rollback_replay_validate_pass": True,
        "live_telemetry_reconciliation_pass": True,
        "human_review_queue_approval_pass": True,
    }
    assert reassessment["provided_gate_artifacts_pass"] is True
    assert reassessment["missing_gate_artifacts"] == []
    assert reassessment["failed_gate_artifacts"] == []
    assert reassessment["broad_g4_apply_allowed"] is False
    assert reassessment["decision"] == "broad_g4_apply_still_blocked_pending_separate_apply_corridor"
    assert reassessment["human_review_queue_approval_source"] == "artifact"
    assert payload["automation_policy"]["apply_supported"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout


def _write_green_g4_gate_reports(tmp_path: Path) -> dict[str, Path]:
    ranking_report = tmp_path / "ranking.json"
    ranking_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_retrieval_ranking_experiment",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "fixture_expansion": {"task_count": 50, "live_runtime_safe": True},
                "shadow_compare": {
                    "baseline_regression_count": 0,
                    "protected_default_order_returned": True,
                    "durable_memory_mutated": False,
                },
            }
        ),
        encoding="utf-8",
    )
    rollback_confidence_report = tmp_path / "rollback-confidence.json"
    rollback_confidence_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_confidence",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
            }
        ),
        encoding="utf-8",
    )
    rollback_replay_report = tmp_path / "rollback-replay.json"
    rollback_replay_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_replay_validate",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
            }
        ),
        encoding="utf-8",
    )
    telemetry_report = tmp_path / "telemetry.json"
    telemetry_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_telemetry_reconciliation",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "privacy": {
                    "raw_conversation_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                },
            }
        ),
        encoding="utf-8",
    )
    return {
        "ranking": ranking_report,
        "rollback_confidence": rollback_confidence_report,
        "rollback_replay": rollback_replay_report,
        "telemetry": telemetry_report,
    }


def test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-operator-bundle.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 operator bundle sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-operator-bundle"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 operator bundle",
        predicate="safe_gate",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-operator-bundle",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    secret_reason = "operator bundle reason SHOULD_NOT_LEAK"
    reason_sha256 = hashlib.sha256(secret_reason.encode()).hexdigest()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE g4_review_queue_items (
                queue_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
                proposal_type TEXT NOT NULL,
                target_ref TEXT,
                proposal_json TEXT NOT NULL,
                source_preview_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actor TEXT NOT NULL,
                reason_sha256 TEXT NOT NULL,
                audit_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        connection.execute(
            """
            INSERT INTO g4_review_queue_items (
                queue_id, status, proposal_type, target_ref, proposal_json,
                source_preview_sha256, actor, reason_sha256, audit_json
            ) VALUES (?, 'approved', 'reinforcement_review', ?, ?, 'preview-green', 'human-reviewer', ?, ?)
            """,
            (
                "g4-review:reinforcement:operator-1",
                f"fact:{fact.id}",
                json.dumps({"secret": "SHOULD_NOT_LEAK", "reason_codes": ["frequent_activation"]}),
                reason_sha256,
                json.dumps([{"action": "approved", "reason_sha256": reason_sha256}]),
            ),
        )
        for index in range(1, 4):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', ?, '',
                          'project:g4-operator-bundle', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (
                    index,
                    hashlib.sha256(f"operator-query-{index}".encode()).hexdigest(),
                    json.dumps([f"fact:{fact.id}"]),
                    f"fact:{fact.id}",
                ),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, ?,
                          'project:g4-operator-bundle', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index, index),
            )
            connection.execute(
                """
                INSERT INTO experience_traces (
                    id, created_at, surface, event_kind, content_sha256, summary, scope,
                    related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
                ) VALUES (?, '2026-05-14 10:30:00', 'hermes-pre-llm-hook', 'turn', ?, NULL,
                          'project:g4-operator-bundle', ?, ?, 'ephemeral', ?)
                """,
                (
                    index,
                    hashlib.sha256(f"operator-trace-{index}".encode()).hexdigest(),
                    json.dumps([f"fact:{fact.id}"]),
                    json.dumps([index]),
                    json.dumps({"trace_recording": "default_metadata_only", "auto_approved": False}),
                ),
            )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("g4_review_queue_items", "facts", "procedures", "episodes")
        }
    reports = _write_green_g4_gate_reports(tmp_path)
    report_dir = tmp_path / "bundle"
    output_path = tmp_path / "bundle.json"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-operator-apply-bundle",
            str(db_path),
            "--report-dir",
            str(report_dir),
            "--retrieval-ranking-report",
            str(reports["ranking"]),
            "--rollback-confidence-report",
            str(reports["rollback_confidence"]),
            "--rollback-replay-report",
            str(reports["rollback_replay"]),
            "--telemetry-reconciliation-report",
            str(reports["telemetry"]),
            "--actor",
            "human-reviewer",
            "--reason",
            secret_reason,
            "--max-apply",
            "1",
            "--limit",
            "20",
            "--top",
            "5",
            "--queue-limit",
            "5",
            "--frequent-threshold",
            "3",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_operator_apply_bundle"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_executed"] is False
    assert payload["apply_supported"] is False
    assert payload["broad_g4_apply_allowed"] is False
    assert payload["bounded_partial_apply_ready"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "operator_apply_bundle_ready_for_exact_manual_apply",
        "blocked_reasons": [],
    }
    assert payload["artifact_paths"] == {
        "human_review_approval_report": str(report_dir / "g4-review-queue-approval-report.json"),
        "queue_preview_report": str(report_dir / "g4-review-queue-preview.json"),
        "apply_readiness_report": str(report_dir / "g4-apply-readiness.json"),
    }
    assert payload["exact_apply_command_preview"] == [
        "agent-memory",
        "dogfood",
        "g4-review-queue-apply",
        str(db_path.resolve(strict=False)),
        "--policy",
        "g4-review-queue-apply-v1",
        "--approval-phrase",
        "apply-approved-g4-review-queue-items-v1",
        "--actor",
        "human-reviewer",
        "--reason",
        "<operator-provided-reason>",
        "--backup-path",
        "<required-backup-path>",
        "--max-apply",
        "1",
        "--output",
        "<apply-audit-output.json>",
    ]
    assert payload["privacy"] == {
        "proposal_json_included": False,
        "raw_content_included": False,
        "raw_reason_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "sample_values_included": False,
        "aggregate_or_ref_only": True,
    }
    assert (report_dir / "g4-review-queue-approval-report.json").exists()
    assert (report_dir / "g4-review-queue-preview.json").exists()
    assert (report_dir / "g4-apply-readiness.json").exists()
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert secret_reason not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_readiness_gate_summary_mixes_retrieval_and_apply_artifacts_without_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-readiness-summary.db"
    initialize_database(db_path)
    reports = _write_green_g4_gate_reports(tmp_path)
    ranking_report = reports["ranking"]
    ranking_payload = json.loads(ranking_report.read_text(encoding="utf-8"))
    ranking_payload["fixture_gate_comparison"] = {
        "eval_gate_pass": True,
        "expanded_fixture_gate_met": True,
        "fixture_task_count": 50,
        "baseline_regression_count": 0,
        "rank_change_count": 120,
        "default_ranking_mutated": False,
        "ordinary_conversation_auto_enable": False,
    }
    ranking_payload["secret"] = "SHOULD_NOT_LEAK"
    ranking_report.write_text(json.dumps(ranking_payload), encoding="utf-8")
    bundle_report = tmp_path / "operator-bundle.json"
    bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": False,
                "apply_supported": False,
                "bounded_partial_apply_ready": True,
                "broad_g4_apply_allowed": False,
                "ordinary_conversation_auto_approval": False,
                "quality_gate": {
                    "pass": True,
                    "decision": "operator_apply_bundle_ready_for_exact_manual_apply",
                    "blocked_reasons": [],
                },
                "artifact_summaries": {
                    "apply_readiness": {
                        "bounded_partial_apply_ready": True,
                        "queue_count": 2,
                    }
                },
                "privacy": {
                    "proposal_json_included": False,
                    "raw_content_included": False,
                    "raw_reason_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "aggregate_or_ref_only": True,
                },
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "procedures", "episodes")
        }

    output_path = tmp_path / "g4-readiness-summary.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-readiness-gate-summary",
            str(db_path),
            "--retrieval-ranking-report",
            str(ranking_report),
            "--operator-apply-bundle-report",
            str(bundle_report),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_readiness_gate_summary"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "bounded_g4_preflight_summary_green_for_manual_operator_apply",
        "blocked_reasons": [],
    }
    assert payload["retrieval_ranking_gate"] == {
        "provided": True,
        "path": str(ranking_report.resolve(strict=False)),
        "report_sha256": hashlib.sha256(ranking_report.read_text(encoding="utf-8").encode()).hexdigest(),
        "kind": "dogfood_retrieval_ranking_experiment",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "pass": True,
        "blocked_reasons": [],
        "fixture_task_count": 50,
        "baseline_regression_count": 0,
        "rank_change_count": 120,
        "default_ranking_mutated": False,
        "ordinary_conversation_auto_enable": False,
    }
    assert payload["operator_apply_bundle_gate"] == {
        "provided": True,
        "path": str(bundle_report.resolve(strict=False)),
        "report_sha256": hashlib.sha256(bundle_report.read_text(encoding="utf-8").encode()).hexdigest(),
        "kind": "dogfood_g4_operator_apply_bundle",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "pass": True,
        "blocked_reasons": [],
        "bounded_partial_apply_ready": True,
        "broad_g4_apply_allowed": False,
        "apply_executed": False,
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
    }
    assert payload["next_step"] == "manual_operator_apply_requires_separate_explicit_approval"
    assert payload["privacy"] == {
        "raw_content_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
        "aggregate_or_ref_only": True,
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_readiness_gate_summary_blocks_mixed_artifact_regression(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-readiness-summary-blocked.db"
    initialize_database(db_path)
    reports = _write_green_g4_gate_reports(tmp_path)
    ranking_report = reports["ranking"]
    ranking_payload = json.loads(ranking_report.read_text(encoding="utf-8"))
    ranking_payload["fixture_gate_comparison"] = {
        "eval_gate_pass": True,
        "expanded_fixture_gate_met": True,
        "fixture_task_count": 50,
        "baseline_regression_count": 1,
        "rank_change_count": 120,
        "default_ranking_mutated": False,
        "ordinary_conversation_auto_enable": False,
    }
    ranking_report.write_text(json.dumps(ranking_payload), encoding="utf-8")
    bundle_report = tmp_path / "operator-bundle-blocked.json"
    bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": False,
                "apply_supported": False,
                "bounded_partial_apply_ready": False,
                "broad_g4_apply_allowed": False,
                "ordinary_conversation_auto_approval": False,
                "quality_gate": {"pass": False, "blocked_reasons": ["review_queue_empty"]},
                "privacy": {"sample_values_included": True},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-readiness-gate-summary",
            str(db_path),
            "--retrieval-ranking-report",
            str(ranking_report),
            "--operator-apply-bundle-report",
            str(bundle_report),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "bounded_g4_preflight_summary_blocked"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "retrieval_ranking_baseline_regressions_present",
        "operator_apply_bundle_not_green",
        "operator_apply_bundle_not_bounded_ready",
        "operator_apply_bundle_privacy_flags_not_ref_safe",
    }


def test_python_module_cli_dogfood_g4_operator_apply_packet_emits_machine_readable_checklist_without_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-operator-apply-packet.db"
    initialize_database(db_path)
    operator_bundle_report = tmp_path / "g4-operator-apply-bundle.json"
    operator_bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": False,
                "apply_supported": False,
                "bounded_partial_apply_ready": True,
                "broad_g4_apply_allowed": False,
                "ordinary_conversation_auto_approval": False,
                "quality_gate": {
                    "pass": True,
                    "decision": "operator_apply_bundle_ready_for_exact_manual_apply",
                    "blocked_reasons": [],
                },
                "artifact_summaries": {"queue_count": 8, "apply_readiness_pass": True},
                "privacy": {
                    "proposal_json_included": False,
                    "raw_content_included": False,
                    "raw_reason_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "aggregate_or_ref_only": True,
                },
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    readiness_summary_report = tmp_path / "g4-readiness-gate-summary.json"
    readiness_summary_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_readiness_gate_summary",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {
                    "pass": True,
                    "decision": "bounded_g4_preflight_summary_green_for_manual_operator_apply",
                    "blocked_reasons": [],
                },
                "operator_apply_bundle_gate": {"pass": True, "bounded_partial_apply_ready": True},
                "retrieval_ranking_gate": {"pass": True, "fixture_task_count": 50},
                "privacy": {
                    "raw_content_included": False,
                    "raw_reason_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "aggregate_or_ref_only": True,
                },
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "procedures", "episodes")
        }

    output_path = tmp_path / "operator-apply-packet.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-operator-apply-packet",
            str(db_path),
            "--operator-apply-bundle-report",
            str(operator_bundle_report),
            "--readiness-gate-summary-report",
            str(readiness_summary_report),
            "--actor",
            "operator@example.test",
            "--max-apply",
            "1",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_operator_apply_packet"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_executed"] is False
    assert payload["apply_supported"] is False
    assert payload["broad_g4_apply_allowed"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "operator_apply_packet_ready_for_manual_review_only",
        "blocked_reasons": [],
    }
    assert payload["operator_checklist"] == {
        "pre_authorization_required": True,
        "required_policy": "g4-review-queue-apply-v1",
        "required_approval_phrase": "apply-approved-g4-review-queue-items-v1",
        "actor_required": True,
        "private_reason_required": True,
        "backup_path_required": True,
        "audit_output_path_required": True,
        "max_apply": 1,
        "post_apply_verification_required": True,
        "repeated_apply_requires_new_packet": True,
    }
    assert payload["manual_apply_command_preview"] == [
        "agent-memory",
        "dogfood",
        "g4-review-queue-apply",
        str(db_path.resolve(strict=False)),
        "--policy",
        "g4-review-queue-apply-v1",
        "--approval-phrase",
        "apply-approved-g4-review-queue-items-v1",
        "--actor",
        "operator@example.test",
        "--reason",
        "<operator-private-reason>",
        "--backup-path",
        "<required-backup-path>",
        "--max-apply",
        "1",
        "--output",
        "<apply-audit-output.json>",
    ]
    assert payload["post_apply_verification_command_template"] == [
        "agent-memory",
        "dogfood",
        "g4-post-apply-verification",
        str(db_path.resolve(strict=False)),
        "--apply-report",
        "<apply-audit-output.json>",
        "--post-apply-bundle-report",
        "<post-apply-operator-bundle.json>",
        "--rollback-replay-report",
        "<post-apply-rollback-replay.json>",
        "--output",
        "<post-apply-verification.json>",
    ]
    assert payload["runbook_contract"] == {
        "matches_g4_bounded_operator_apply_runbook": True,
        "required_authorization_items": [
            "live_bounded_g4_review_queue_apply_intent",
            "approval_phrase",
            "policy",
            "actor",
            "private_reason",
            "backup_path",
            "audit_output_path",
            "bounded_max_apply",
        ],
        "pre_apply_evidence_items": [
            "g4_operator_apply_packet_green",
            "g4_operator_apply_bundle_green",
            "g4_readiness_gate_summary_green",
            "read_only_no_mutation_default_unchanged",
            "pre_apply_bundle_no_apply_support_or_execution",
            "privacy_ref_safe",
        ],
        "post_apply_stop_items": [
            "new_post_apply_operator_bundle_required",
            "g4_post_apply_verification_required",
            "stop_after_first_bounded_apply_without_fresh_approval",
        ],
        "manual_apply_command_contains_all_required_flags": True,
        "post_apply_verification_template_contains_all_required_flags": True,
        "readiness_is_not_authorization": True,
    }
    assert payload["artifact_gates"]["operator_apply_bundle"]["pass"] is True
    assert payload["artifact_gates"]["readiness_gate_summary"]["pass"] is True
    assert payload["privacy"] == {
        "raw_content_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
        "aggregate_or_ref_only": True,
    }
    assert payload["safety_exclusions"] == {
        "broad_g4_background_apply": False,
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_migration": False,
        "collapse_delete_apply": False,
        "live_telemetry_reset": False,
        "apply_without_exact_operator_approval": False,
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_operator_apply_packet_blocks_unsafe_or_stale_artifacts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-operator-apply-packet-blocked.db"
    initialize_database(db_path)
    operator_bundle_report = tmp_path / "g4-operator-apply-bundle-blocked.json"
    operator_bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": True,
                "apply_supported": True,
                "bounded_partial_apply_ready": False,
                "broad_g4_apply_allowed": True,
                "ordinary_conversation_auto_approval": True,
                "quality_gate": {"pass": False, "blocked_reasons": ["review_queue_not_green"]},
                "privacy": {"raw_reason_included": True},
            }
        ),
        encoding="utf-8",
    )
    readiness_summary_report = tmp_path / "g4-readiness-gate-summary-blocked.json"
    readiness_summary_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_readiness_gate_summary",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": False, "blocked_reasons": ["operator_apply_bundle_not_green"]},
                "privacy": {"sample_values_included": True},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-operator-apply-packet",
            str(db_path),
            "--operator-apply-bundle-report",
            str(operator_bundle_report),
            "--readiness-gate-summary-report",
            str(readiness_summary_report),
            "--actor",
            "operator@example.test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_executed"] is False
    assert payload["apply_supported"] is False
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "operator_apply_packet_blocked_before_manual_apply"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "operator_apply_bundle_not_green",
        "operator_apply_bundle_not_bounded_ready",
        "operator_apply_bundle_broad_apply_allowed",
        "operator_apply_bundle_apply_executed",
        "operator_apply_bundle_apply_supported",
        "operator_apply_bundle_ordinary_auto_approval_enabled",
        "operator_apply_bundle_privacy_flags_not_ref_safe",
        "readiness_gate_summary_not_green",
        "readiness_gate_summary_privacy_flags_not_ref_safe",
    }


def test_python_module_cli_dogfood_g4_post_apply_verification_validates_apply_bundle_and_replay_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-post-apply-verification.db"
    initialize_database(db_path)
    backup_path = tmp_path / "memory-before-apply.db"
    backup_path.write_bytes(b"safe backup bytes")
    backup_sha256 = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    apply_report = tmp_path / "g4-review-queue-apply.json"
    apply_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_review_queue_apply",
                "read_only": False,
                "mutated": True,
                "default_retrieval_unchanged": True,
                "policy": "g4-review-queue-apply-v1",
                "approval_phrase_matched": True,
                "backup": {"path": str(backup_path), "sha256": backup_sha256},
                "apply_mode": "bounded_partial_automation_reviewed_queue_items_only",
                "max_apply": 3,
                "applied_count": 2,
                "already_applied_count": 0,
                "skipped_count": 0,
                "memory_status_mutated": False,
                "memory_reinforcement_mutated": True,
                "ordinary_conversation_auto_approval": False,
                "privacy": {
                    "proposal_json_included": False,
                    "raw_content_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "raw_reason_included": False,
                    "reason_stored_as_sha256": True,
                },
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    post_bundle_report = tmp_path / "post-apply-bundle.json"
    post_bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": False,
                "apply_supported": False,
                "bounded_partial_apply_ready": True,
                "broad_g4_apply_allowed": False,
                "ordinary_conversation_auto_approval": False,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "privacy": {
                    "proposal_json_included": False,
                    "raw_content_included": False,
                    "raw_reason_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "sample_values_included": False,
                    "aggregate_or_ref_only": True,
                },
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    rollback_replay_report = tmp_path / "rollback-replay.json"
    rollback_replay_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_replay_validate",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "privacy": {"raw_content_included": False, "sample_values_included": False},
                "secret": "SHOULD_NOT_LEAK",
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "procedures", "episodes")
        }

    output_path = tmp_path / "post-apply-verification.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-post-apply-verification",
            str(db_path),
            "--apply-report",
            str(apply_report),
            "--post-apply-bundle-report",
            str(post_bundle_report),
            "--rollback-replay-report",
            str(rollback_replay_report),
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_post_apply_verification"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["verified_apply_mutated"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "g4_post_apply_verification_green_stop_before_next_mutation",
        "blocked_reasons": [],
    }
    assert payload["apply_artifact_gate"]["pass"] is True
    assert payload["apply_artifact_gate"]["applied_count"] == 2
    assert payload["apply_artifact_gate"]["max_apply"] == 3
    assert payload["backup_integrity_gate"] == {
        "pass": True,
        "blocked_reasons": [],
        "backup_path_provided": True,
        "backup_exists": True,
        "backup_sha256_matches": True,
        "backup_sha256": backup_sha256,
    }
    assert payload["post_apply_bundle_gate"]["pass"] is True
    assert payload["rollback_replay_gate"]["pass"] is True
    assert payload["next_step"] == "stop_or_collect_operator_review_before_any_further_mutation"
    assert payload["safety_exclusions"] == {
        "broad_g4_background_apply": False,
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_migration": False,
        "collapse_delete_apply": False,
        "live_telemetry_reset": False,
        "additional_apply_without_new_approval": False,
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_post_apply_verification_blocks_unsafe_artifacts(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-post-apply-verification-blocked.db"
    initialize_database(db_path)
    backup_path = tmp_path / "memory-before-apply.db"
    backup_path.write_bytes(b"changed backup bytes")
    apply_report = tmp_path / "g4-review-queue-apply-blocked.json"
    apply_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_review_queue_apply",
                "read_only": False,
                "mutated": True,
                "default_retrieval_unchanged": True,
                "policy": "g4-review-queue-apply-v1",
                "approval_phrase_matched": True,
                "backup": {"path": str(backup_path), "sha256": "0" * 64},
                "max_apply": 1,
                "applied_count": 2,
                "memory_status_mutated": True,
                "ordinary_conversation_auto_approval": True,
                "privacy": {"raw_reason_included": True},
            }
        ),
        encoding="utf-8",
    )
    post_bundle_report = tmp_path / "post-apply-bundle-blocked.json"
    post_bundle_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_operator_apply_bundle",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "apply_executed": False,
                "apply_supported": False,
                "bounded_partial_apply_ready": True,
                "broad_g4_apply_allowed": True,
                "ordinary_conversation_auto_approval": False,
                "quality_gate": {"pass": False, "blocked_reasons": ["review_queue_not_rechecked"]},
                "privacy": {"sample_values_included": True},
            }
        ),
        encoding="utf-8",
    )
    rollback_replay_report = tmp_path / "rollback-replay-blocked.json"
    rollback_replay_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_replay_validate",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": False, "blocked_reasons": ["backup_sha256_mismatch"]},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-post-apply-verification",
            str(db_path),
            "--apply-report",
            str(apply_report),
            "--post-apply-bundle-report",
            str(post_bundle_report),
            "--rollback-replay-report",
            str(rollback_replay_report),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "g4_post_apply_verification_blocked"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "apply_report_exceeds_max_apply",
        "apply_report_memory_status_mutated",
        "apply_report_ordinary_auto_approval_enabled",
        "apply_report_privacy_flags_not_ref_safe",
        "backup_sha256_mismatch",
        "post_apply_bundle_not_green",
        "post_apply_bundle_broad_apply_allowed",
        "post_apply_bundle_privacy_flags_not_ref_safe",
        "rollback_replay_not_green",
    }


def test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-operator-bundle-blocked.db"
    initialize_database(db_path)
    reports = _write_green_g4_gate_reports(tmp_path)
    reports["rollback_replay"].write_text(
        json.dumps(
            {
                "kind": "dogfood_rollback_replay_validate",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "quality_gate": {"pass": False, "blocked_reasons": ["restore_replay_missing"]},
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "procedures", "episodes")
        }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-operator-apply-bundle",
            str(db_path),
            "--report-dir",
            str(tmp_path / "blocked-bundle"),
            "--retrieval-ranking-report",
            str(reports["ranking"]),
            "--rollback-confidence-report",
            str(reports["rollback_confidence"]),
            "--rollback-replay-report",
            str(reports["rollback_replay"]),
            "--telemetry-reconciliation-report",
            str(reports["telemetry"]),
            "--actor",
            "human-reviewer",
            "--reason",
            "blocked reason SHOULD_NOT_LEAK",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_executed"] is False
    assert payload["apply_supported"] is False
    assert payload["bounded_partial_apply_ready"] is False
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "operator_apply_bundle_blocked_before_exact_manual_apply"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "review_queue_empty",
        "no_approved_queue_items",
        "rollback_replay_validate_pass",
        "rollback_replay_validate_pass_not_green",
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_review_queue_approval_report_is_ref_safe_read_only_gate(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-approval-report.db"
    initialize_database(db_path)
    reason_secret = "approval reason SHOULD_NOT_LEAK"
    reason_sha256 = hashlib.sha256(reason_secret.encode()).hexdigest()
    pending_reason_sha256 = hashlib.sha256(b"pending").hexdigest()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE g4_review_queue_items (
                queue_id TEXT PRIMARY KEY,
                status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected')),
                proposal_type TEXT NOT NULL,
                target_ref TEXT,
                proposal_json TEXT NOT NULL,
                source_preview_sha256 TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                actor TEXT NOT NULL,
                reason_sha256 TEXT NOT NULL,
                audit_json TEXT NOT NULL DEFAULT '[]'
            )
            """
        )
        rows = [
            ("g4-review:reinforcement:1", "approved", "reinforcement_review", "fact:1", "preview-a", "human-reviewer", reason_sha256),
            ("g4-review:decay-risk:1", "rejected", "decay_risk_review", "procedure:2", "preview-a", "human-reviewer", reason_sha256),
            ("g4-review:reinforcement:2", "pending", "reinforcement_review", "fact:3", "preview-b", "queue-bot", pending_reason_sha256),
        ]
        for queue_id, status, proposal_type, target_ref, preview_sha, actor, row_reason_sha in rows:
            connection.execute(
                """
                INSERT INTO g4_review_queue_items (
                    queue_id, status, proposal_type, target_ref, proposal_json,
                    source_preview_sha256, actor, reason_sha256, audit_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    status,
                    proposal_type,
                    target_ref,
                    json.dumps({"queue_id": queue_id, "secret": "SHOULD_NOT_LEAK"}),
                    preview_sha,
                    actor,
                    row_reason_sha,
                    json.dumps(
                        [
                            {"action": "persist", "actor": "queue-bot", "reason_sha256": pending_reason_sha256},
                            {"action": status, "actor": actor, "policy": "g4-review-queue-transition-v1", "reason_sha256": row_reason_sha},
                        ]
                    ),
                ),
            )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("g4_review_queue_items", "facts", "procedures", "episodes")
        }

    output_path = tmp_path / "approval-report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-review-queue-approval-report",
            str(db_path),
            "--actor",
            "human-reviewer",
            "--policy",
            "g4-review-queue-approval-artifact-v1",
            "--approval-phrase",
            "report-approved-g4-review-queue-v1",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_review_queue_approval_report"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["apply_supported"] is False
    assert payload["human_review_queue_approval_pass"] is False
    assert payload["approval_phrase_matched"] is True
    assert payload["queue_summary"] == {
        "total_count": 3,
        "approved_count": 1,
        "rejected_count": 1,
        "pending_count": 1,
        "reviewed_count": 2,
    }
    assert payload["quality_gate"] == {
        "pass": False,
        "decision": "human_review_queue_still_has_pending_items",
        "blocked_reasons": ["pending_review_queue_items_present"],
    }
    assert payload["source_preview_sha256s"] == ["preview-a", "preview-b"]
    assert payload["status_counts"] == {"approved": 1, "pending": 1, "rejected": 1}
    assert payload["review_actor_counts"] == {"human-reviewer": 2, "queue-bot": 1}
    assert payload["privacy"] == {
        "proposal_json_included": False,
        "raw_content_included": False,
        "raw_reason_included": False,
        "sample_values_included": False,
        "aggregate_or_ref_only": True,
    }
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert reason_secret not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_apply_readiness_consumes_green_preview_without_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-apply-readiness.db"
    initialize_database(db_path)
    preview_report = tmp_path / "g4-preview-green.json"
    preview_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_review_queue_preview",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "queue_count": 2,
                "quality_gate": {"pass": True, "blocked_reasons": []},
                "broad_g4_apply_reassessment": {
                    "broad_g4_apply_allowed": False,
                    "decision": "broad_g4_apply_still_blocked_pending_separate_apply_corridor",
                    "current_report_green": True,
                    "provided_gate_artifacts_pass": True,
                    "missing_gate_artifacts": [],
                    "failed_gate_artifacts": [],
                    "human_review_queue_approval_source": "artifact",
                    "artifact_gate_evidence": {
                        "retrieval_ranking_gate_pass": True,
                        "rollback_confidence_pass": True,
                        "rollback_replay_validate_pass": True,
                        "live_telemetry_reconciliation_pass": True,
                        "human_review_queue_approval_pass": True,
                    },
                    "required_green_gates": [
                        "retrieval_ranking_gate_pass",
                        "rollback_confidence_pass",
                        "rollback_replay_validate_pass",
                        "live_telemetry_reconciliation_pass",
                        "human_review_queue_approval_pass",
                    ],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "sample_values_included": False,
                    "raw_query_text_included": False,
                    "raw_trace_summary_included": False,
                    "aggregate_or_ref_only": True,
                },
            }
        ),
        encoding="utf-8",
    )
    with sqlite3.connect(db_path) as connection:
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("facts", "procedures", "episodes")
        }

    output_path = tmp_path / "readiness.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-apply-readiness",
            str(db_path),
            "--queue-preview-report",
            str(preview_report),
            "--max-apply",
            "1",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_g4_apply_readiness"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_supported"] is False
    assert payload["broad_g4_apply_allowed"] is False
    assert payload["bounded_partial_apply_ready"] is True
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "bounded_apply_ready_pending_exact_operator_approval",
        "blocked_reasons": [],
    }
    assert payload["required_operator_approval"] == {
        "command": "g4-review-queue-apply",
        "policy": "g4-review-queue-apply-v1",
        "approval_phrase": "apply-approved-g4-review-queue-items-v1",
        "backup_required": True,
        "max_apply": 1,
    }
    assert payload["preview_evidence"]["report_sha256"] == hashlib.sha256(preview_report.read_text(encoding="utf-8").encode()).hexdigest()
    assert payload["privacy"]["raw_content_included"] is False
    assert payload["privacy"]["sample_values_included"] is False

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in before_counts
        }
    assert after_counts == before_counts


def test_python_module_cli_dogfood_g4_apply_readiness_blocks_unsafe_preview_artifact(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-apply-readiness-blocked.db"
    initialize_database(db_path)
    preview_report = tmp_path / "g4-preview-unsafe.json"
    preview_report.write_text(
        json.dumps(
            {
                "kind": "dogfood_g4_review_queue_preview",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "queue_count": 0,
                "quality_gate": {"pass": False, "blocked_reasons": ["pending_review_queue_items_present"]},
                "broad_g4_apply_reassessment": {
                    "broad_g4_apply_allowed": False,
                    "current_report_green": False,
                    "provided_gate_artifacts_pass": False,
                    "missing_gate_artifacts": ["human_review_queue_approval_report"],
                    "failed_gate_artifacts": ["rollback_replay_validate_pass"],
                    "human_review_queue_approval_source": "absent",
                    "artifact_gate_evidence": {
                        "retrieval_ranking_gate_pass": True,
                        "rollback_confidence_pass": True,
                        "rollback_replay_validate_pass": False,
                        "live_telemetry_reconciliation_pass": True,
                        "human_review_queue_approval_pass": False,
                    },
                },
                "privacy": {"sample_values_included": True},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-apply-readiness",
            str(db_path),
            "--queue-preview-report",
            str(preview_report),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["apply_supported"] is False
    assert payload["broad_g4_apply_allowed"] is False
    assert payload["bounded_partial_apply_ready"] is False
    assert payload["quality_gate"]["pass"] is False
    assert payload["quality_gate"]["decision"] == "continue_read_only_gate_evidence_before_apply_readiness"
    assert set(payload["quality_gate"]["blocked_reasons"]) >= {
        "queue_preview_empty",
        "queue_preview_quality_gate_not_green",
        "pending_review_queue_items_present",
        "queue_preview_current_report_not_green",
        "queue_preview_artifact_gates_not_green",
        "queue_preview_missing_human_approval_artifact",
        "queue_preview_privacy_flag_claims_raw_content",
        "human_review_queue_approval_report",
        "rollback_replay_validate_pass",
        "rollback_replay_validate_pass_not_green",
        "human_review_queue_approval_pass_not_green",
    }


def test_python_module_cli_dogfood_g4_review_queue_preview_splits_historical_unknowns_with_fresh_epoch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-fresh-split.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 fresh split sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-fresh-split"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 fresh split",
        predicate="safe_ref",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-fresh-split",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 5):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-fresh-split', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (index, hashlib.sha256(f"historical-hit-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, NULL,
                          'project:g4-fresh-split', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index),
            )
        for index in range(5, 11):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-fresh-split', 1, '["approved"]', '[]', NULL, NULL, '{}')
                """,
                (index, hashlib.sha256(f"historical-empty-{index}".encode()).hexdigest()),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', 'empty_retrieval', NULL, ?, NULL,
                          'project:g4-fresh-split', 0.0, '{}')
                """,
                (index, index),
            )
        for index in range(11, 14):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 06:30:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-fresh-split', 1, '["approved"]', ?, ?, 'direct',
                          '{"retrieval_outcome":"retrieved_memory","hook_event_name":"pre_llm_call"}')
                """,
                (index, hashlib.sha256(f"fresh-hit-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO experience_traces (
                    id, created_at, surface, event_kind, content_sha256, summary, scope, session_ref,
                    salience, user_emphasis, related_memory_refs_json, related_observation_ids_json, retention_policy, metadata_json
                ) VALUES (?, '2026-05-10 06:30:00', 'hermes-pre-llm-hook', 'turn', ?, NULL,
                          'project:g4-fresh-split', 'session:test', 0.1, 0.0, ?, ?, 'ephemeral', '{}')
                """,
                (index, hashlib.sha256(f"fresh-trace-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), json.dumps([index])),
            )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-review-queue-preview",
            str(db_path),
            "--limit",
            "30",
            "--top",
            "5",
            "--queue-limit",
            "5",
            "--frequent-threshold",
            "3",
            "--epoch-start",
            "2026-05-10T06:00:00Z",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["fresh_epoch_comparison_enabled"] is True
    blockers = payload["quality_gate"]["blocked_reasons"]
    assert "background_empty_retrieval_outcome_unknown" not in blockers
    assert "background_empty_retrieval_outcome_classified_or_reset_previewable" not in blockers
    warning = payload["background_quality_warning_analysis"]["warnings"][0]
    assert warning["severity"] == "diagnostic"
    assert warning["gate_effect"] == "diagnostic_only_after_fresh_epoch_resolution"
    fresh = warning["ref_safe_metrics"]["fresh_epoch_comparison"]
    assert fresh["enabled"] is True
    assert fresh["fresh_unresolved_unknown_empty_outcome_count"] == 0
    assert fresh["reset_resolution_hint"] == "historical_telemetry_resolved_by_fresh_epoch_or_reset"
    assert "SHOULD_NOT_LEAK" not in result.stdout


def test_hermes_pre_llm_hook_resolves_trace_link_when_packet_observation_id_is_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-link-fallback.db"
    initialize_database(db_path)
    user_message = "Trace linkage fallback should use query sha only."
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, surface, query_sha256, query_preview, preferred_scope, limit_value, statuses_json,
                retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (42, 'hermes-pre-llm-hook', ?, NULL, 'project:trace-link', 5, '["approved"]',
                      '[]', NULL, 'verify_first', '{"retrieval_outcome":"no_reliable_memory"}')
            """,
            (hashlib.sha256(user_message.encode("utf-8")).hexdigest(),),
        )

    resolved = hermes_hooks._resolve_related_observation_ids(
        options=HermesPreLlmHookOptions(db_path=db_path, preferred_scope="project:trace-link", record_trace=True),
        packet=hermes_hooks.MemoryPacket(query=user_message),
        user_message=user_message,
    )

    assert resolved == [42]


def test_python_module_cli_dogfood_g4_review_queue_persist_lists_and_updates_without_apply(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-persist.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 persist sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-persist"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 persist",
        predicate="safe_ref",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-persist",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 5):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-persist', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (index, hashlib.sha256(f"persist-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, NULL,
                          'project:g4-persist', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index),
            )
        before_facts = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    persist = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-persist", str(db_path),
            "--limit", "20", "--top", "5", "--queue-limit", "5", "--frequent-threshold", "3",
            "--actor", "pytest", "--reason", "persist queue for review without apply",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist.returncode == 0, persist.stderr
    persisted = json.loads(persist.stdout)
    assert persisted["queue_persistence_supported"] is True
    assert persisted["apply_supported"] is False
    assert persisted["inserted_count"] >= 1
    assert "SHOULD_NOT_LEAK" not in persist.stdout

    listed = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-list", str(db_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert listed.returncode == 0, listed.stderr
    list_payload = json.loads(listed.stdout)
    queue_id = list_payload["items"][0]["queue_id"]
    assert list_payload["items"][0]["status"] == "pending"
    assert "proposal_json" not in list_payload["items"][0]

    updated = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-update", str(db_path), queue_id,
            "--status", "approved", "--actor", "pytest", "--reason", "reviewed aggregate refs only",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert updated.returncode == 0, updated.stderr
    assert json.loads(updated.stdout)["apply_supported"] is False
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == before_facts
        assert connection.execute("SELECT status FROM g4_review_queue_items WHERE queue_id = ?", (queue_id,)).fetchone()[0] == "approved"



def test_python_module_cli_dogfood_telemetry_reset_apply_is_guarded_and_telemetry_only(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "telemetry-reset-apply.db"
    backup_path = tmp_path / "telemetry-reset.backup.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Telemetry reset apply SHOULD_NOT_LEAK protected content.",
        metadata={"project": "telemetry-reset-apply"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Telemetry reset apply",
        predicate="protects",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:telemetry-reset-apply",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                      'project:telemetry-reset-apply', 1, '["approved"]', '[]', NULL, 'direct', '{}')
            """,
            (hashlib.sha256(b"old").hexdigest(),),
        )
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (2, '2026-05-11 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                      'project:telemetry-reset-apply', 1, '["approved"]', '[]', NULL, 'direct', '{}')
            """,
            (hashlib.sha256(b"fresh").hexdigest(),),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
            ) VALUES (1, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 1, NULL,
                      'project:telemetry-reset-apply', 0.0, '{}')
            """
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, summary, metadata_json
            ) VALUES (1, '2026-05-09 00:00:00', 'hermes-pre-llm-hook', 'turn',
                      'project:telemetry-reset-apply', ?, 'hash-only SHOULD_NOT_LEAK', '{}')
            """
        ,
            (hashlib.sha256(b"trace").hexdigest(),),
        )
        protected_before = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "telemetry-reset-apply", str(db_path),
            "--epoch-start", "2026-05-10T00:00:00Z",
            "--policy", "telemetry-reset-v1",
            "--approval-phrase", "apply-telemetry-reset-v1",
            "--actor", "pytest",
            "--reason", "retire historical telemetry only",
            "--backup-path", str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_telemetry_reset_apply"
    assert payload["deleted_total"] == 3
    assert payload["protected_memory_tables_mutated"] is False
    assert payload["post_apply_preview"]["candidate_delete_total"] == 0
    assert payload["backup"]["path"] == str(backup_path)
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == protected_before
        assert connection.execute("SELECT COUNT(*) FROM retrieval_observations").fetchone()[0] == 1
        assert connection.execute("SELECT COUNT(*) FROM memory_activations").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM experience_traces").fetchone()[0] == 0
    assert backup_path.exists()


def test_python_module_cli_dogfood_g4_review_queue_apply_records_approved_items_without_memory_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-apply.db"
    backup_path = tmp_path / "g4-review-queue-apply.backup.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 apply sensitive SHOULD_NOT_LEAK content.",
        metadata={"project": "g4-apply"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 apply",
        predicate="safe_ref",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-apply",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 5):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-apply', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (index, hashlib.sha256(f"apply-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, NULL,
                          'project:g4-apply', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index),
            )
        before_facts = connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0]

    env = {**os.environ, "PYTHONPATH": "src"}
    persist = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-persist", str(db_path),
            "--limit", "20", "--top", "5", "--queue-limit", "5", "--frequent-threshold", "3",
            "--actor", "pytest", "--reason", "persist queue for guarded apply",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist.returncode == 0, persist.stderr
    listed = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-list", str(db_path)],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    listed_payload = json.loads(listed.stdout)
    queue_id = next(item["queue_id"] for item in listed_payload["items"] if item["proposal_type"] == "reinforcement_review")
    updated = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-update", str(db_path), queue_id,
            "--status", "approved", "--actor", "pytest", "--reason", "reviewed refs only",
            "--approval-phrase", "approved-g4-review-queue-item-v1",
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert updated.returncode == 0, updated.stderr
    applied = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-apply", str(db_path),
            "--queue-id", queue_id,
            "--policy", "g4-review-queue-apply-v1",
            "--approval-phrase", "apply-approved-g4-review-queue-items-v1",
            "--actor", "pytest", "--reason", "record approved g4 review outcome",
            "--backup-path", str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert applied.returncode == 0, applied.stderr
    payload = json.loads(applied.stdout)
    assert payload["kind"] == "dogfood_g4_review_queue_apply"
    assert payload["apply_mode"] == "bounded_partial_automation_reviewed_queue_items_only"
    assert payload["max_apply"] == 1
    assert payload["applied_count"] == 1
    assert payload["memory_status_mutated"] is False
    assert payload["memory_reinforcement_mutated"] is True
    assert payload["default_retrieval_unchanged"] is True
    assert payload["applied_items"][0]["action"] == "apply_reinforcement_marker"
    assert "proposal_json_included" in applied.stdout
    assert "SHOULD_NOT_LEAK" not in applied.stdout
    with sqlite3.connect(db_path) as connection:
        assert connection.execute("SELECT COUNT(*) FROM facts").fetchone()[0] == before_facts
        assert connection.execute("SELECT COUNT(*) FROM g4_review_queue_applications").fetchone()[0] == 1
        row = connection.execute("SELECT reinforcement_count, retrieval_count FROM facts WHERE id = ?", (fact.id,)).fetchone()
        assert row == (1.0, 0)
    assert backup_path.exists()


def test_python_module_cli_dogfood_g4_review_queue_preview_decomposes_background_quality_warnings(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-review-queue-warning-decomposition.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="G4 warning decomposition sensitive SHOULD_NOT_LEAK detail.",
        metadata={"project": "g4-warning-decomposition"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G4 warning decomposition",
        predicate="safe_ref",
        object_ref_or_value="SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g4-warning-decomposition",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    with sqlite3.connect(db_path) as connection:
        for index in range(1, 5):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-warning-decomposition', 1, '["approved"]', ?, ?, 'direct', '{}')
                """,
                (index, hashlib.sha256(f"retrieved-{index}".encode()).hexdigest(), json.dumps([f"fact:{fact.id}"]), f"fact:{fact.id}"),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', 'retrieved', ?, ?, NULL,
                          'project:g4-warning-decomposition', 1.0, '{}')
                """,
                (index, f"fact:{fact.id}", index),
            )
        for index in range(5, 11):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-warning-decomposition', 1, '["approved"]', '[]', NULL, 'verify_first', '{}')
                """,
                (index, hashlib.sha256(f"empty-{index}".encode()).hexdigest()),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, '2026-05-10 00:00:00', 'hermes-pre-llm-hook', 'empty_retrieval', NULL, ?, NULL,
                          'project:g4-warning-decomposition', 1.0, '{}')
                """,
                (index, index),
            )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-review-queue-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--queue-limit",
            "5",
            "--frequent-threshold",
            "3",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["queue_count"] >= 1
    assert "background_quality_warnings_present" not in payload["quality_gate"]["blocked_reasons"]
    assert "background_empty_retrieval_outcome_unknown" in payload["quality_gate"]["blocked_reasons"]
    assert "background_empty_retrieval_trace_linkage_gap" in payload["quality_gate"]["blocked_reasons"]
    analysis = payload["background_quality_warning_analysis"]
    assert analysis["kind"] == "g4_background_quality_warning_analysis"
    assert analysis["raw_content_included"] is False
    assert analysis["raw_query_text_included"] is False
    assert analysis["sample_values_included"] is False
    warning = analysis["warnings"][0]
    assert warning["warning"] == "high_empty_retrieval_activation_ratio"
    assert warning["severity"] == "blocking"
    assert warning["ref_safe_metrics"]["by_retrieval_outcome"] == {"unknown": 6}
    assert warning["ref_safe_metrics"]["trace_linkage"]["unlinked_to_trace_count"] == 6
    assert "SHOULD_NOT_LEAK" not in result.stdout



def test_python_module_cli_dogfood_g4_linkage_gap_diagnose_is_read_only_ref_safe_and_classifies_latest_gap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-linkage-gap-diagnose.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        for observation_id, created_at, metadata_json in (
            (
                1,
                "2026-05-10T11:45:00Z",
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "no_reliable_memory"}),
            ),
            (
                2,
                "2026-05-10T11:50:00Z",
                json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "adapter_payload_gap", "secret": "SHOULD_NOT_LEAK"}),
            ),
        ):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-linkage-gap-diagnose', 1, '["approved"]', '[]', NULL, 'verify_first', ?)
                """,
                (observation_id, created_at, hashlib.sha256(f"empty-{observation_id}".encode()).hexdigest(), metadata_json),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', 'empty_retrieval', NULL, ?, NULL,
                          'project:g4-linkage-gap-diagnose', 1.0, '{}')
                """,
                (observation_id, created_at, observation_id),
            )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, related_memory_refs_json,
                related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, '2026-05-10T11:46:00Z', 'hermes-pre-llm-hook', 'turn',
                      'project:g4-linkage-gap-diagnose', ?, '[]', '[1]', 'ephemeral',
                      '{"trace_recording":"default_metadata_only","raw_prompt":"SHOULD_NOT_LEAK"}')
            """,
            ("a" * 64,),
        )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    output_path = tmp_path / "g4-linkage-gap-diagnose.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-linkage-gap-diagnose",
            str(db_path),
            "--epoch-start",
            "2026-05-10T11:40:00Z",
            "--surface",
            "hermes-pre-llm-hook",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "g4_linkage_gap_diagnosis"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["privacy"] == {
        "raw_conversation_content_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "sample_values_included": False,
        "aggregate_or_ref_only": True,
    }
    assert payload["filters"]["surface"] == "hermes-pre-llm-hook"
    assert payload["coverage"]["observation_count"] == 2
    assert payload["coverage"]["linked_observation_count"] == 1
    assert payload["coverage"]["unlinked_observation_count"] == 1
    assert payload["latest_unlinked_observation"] == {
        "observation_ref": "observation:2",
        "activation_refs": ["activation:2"],
        "created_at": "2026-05-10T11:50:00Z",
        "surface": "hermes-pre-llm-hook",
        "response_mode": "verify_first",
        "hook_event_name": "pre_llm_call",
        "retrieval_outcome": "adapter_payload_gap",
        "classification": "metadata_classification_gap",
        "classification_reason": "empty observation carries adapter/scope payload-gap outcome metadata",
        "raw_content_included": False,
        "sample_values_included": False,
    }
    assert payload["classification_counts"] == {"metadata_classification_gap": 1}
    assert payload["quality_gate"]["blocked_reasons"] == ["fresh_trace_linkage_gap_present"]
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "SHOULD_NOT_LEAK" not in output_path.read_text()
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_g4_linkage_gap_diagnose_treats_older_unlinked_rows_as_resolved_rollout_telemetry(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-linkage-gap-resolved-rollout.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        for observation_id, created_at in (
            (1, "2026-05-10T11:45:00Z"),
            (2, "2026-05-10T11:50:00Z"),
        ):
            connection.execute(
                """
                INSERT INTO retrieval_observations (
                    id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                    statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                          'project:g4-linkage-gap-diagnose', 1, '["approved"]', '["fact:1"]', 'fact:1', 'direct', ?)
                """,
                (
                    observation_id,
                    created_at,
                    hashlib.sha256(f"resolved-{observation_id}".encode()).hexdigest(),
                    json.dumps({"hook_event_name": "pre_llm_call", "retrieval_outcome": "retrieved_memory"}),
                ),
            )
            connection.execute(
                """
                INSERT INTO memory_activations (
                    id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
                ) VALUES (?, ?, 'hermes-pre-llm-hook', 'retrieved', 'fact:1', ?, NULL,
                          'project:g4-linkage-gap-diagnose', 1.0, '{}')
                """,
                (observation_id, created_at, observation_id),
            )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, related_memory_refs_json,
                related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, '2026-05-10T11:44:00Z', 'hermes-pre-llm-hook', 'turn',
                      'project:g4-linkage-gap-diagnose', ?, '["fact:1"]', '[]', 'ephemeral',
                      '{"trace_recording":"default_metadata_only"}')
            """,
            ("a" * 64,),
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, related_memory_refs_json,
                related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (2, '2026-05-10T11:50:01Z', 'hermes-pre-llm-hook', 'turn',
                      'project:g4-linkage-gap-diagnose', ?, '["fact:1"]', '[2]', 'ephemeral',
                      '{"trace_recording":"default_metadata_only"}')
            """,
            ("b" * 64,),
        )
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-linkage-gap-diagnose",
            str(db_path),
            "--epoch-start",
            "2026-05-10T11:40:00Z",
            "--surface",
            "hermes-pre-llm-hook",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["classification_counts"] == {"historical_or_rollout_telemetry": 1}
    assert payload["latest_unlinked_observation"]["classification"] == "historical_or_rollout_telemetry"
    assert payload["quality_gate"]["decision"] == "review_resolved_rollout_telemetry_before_g4_apply"
    assert payload["quality_gate"]["blocked_reasons"] == ["resolved_rollout_telemetry_requires_review"]
    assert "SHOULD_NOT_LEAK" not in result.stdout
    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_g4_linkage_gap_diagnose_classifies_stale_hook_metadata_gap(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "g4-linkage-gap-stale-hook.db"
    initialize_database(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO retrieval_observations (
                id, created_at, surface, query_sha256, query_preview, preferred_scope, limit_value,
                statuses_json, retrieved_memory_refs_json, top_memory_ref, response_mode, metadata_json
            ) VALUES (1, '2026-05-10T11:45:00Z', 'hermes-pre-llm-hook', ?, 'SHOULD_NOT_LEAK',
                      'project:g4-linkage-gap-diagnose', 1, '["approved"]', '[]', NULL, NULL, ?)
            """,
            (
                hashlib.sha256(b"stale-hook").hexdigest(),
                json.dumps({"hook_event_name": "pre_llm_call", "secret": "SHOULD_NOT_LEAK"}),
            ),
        )
        connection.execute(
            """
            INSERT INTO memory_activations (
                id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, strength, metadata_json
            ) VALUES (1, '2026-05-10T11:45:00Z', 'hermes-pre-llm-hook', 'empty_retrieval', NULL, 1, NULL,
                      'project:g4-linkage-gap-diagnose', 1.0, '{}')
            """
        )
        connection.execute(
            """
            INSERT INTO experience_traces (
                id, created_at, surface, event_kind, scope, content_sha256, related_memory_refs_json,
                related_observation_ids_json, retention_policy, metadata_json
            ) VALUES (1, '2026-05-10T11:45:01Z', 'hermes-pre-llm-hook', 'turn',
                      'project:g4-linkage-gap-diagnose', ?, '[]', '[]', 'ephemeral',
                      '{"trace_recording":"default_metadata_only"}')
            """,
            ("c" * 64,),
        )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "g4-linkage-gap-diagnose",
            str(db_path),
            "--epoch-start",
            "2026-05-10T11:40:00Z",
            "--surface",
            "hermes-pre-llm-hook",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["classification_counts"] == {"metadata_classification_gap": 1}
    assert payload["latest_unlinked_observation"]["classification_reason"] == (
        "hook observation is missing retrieval outcome/response mode metadata needed for ref-safe linkage diagnosis"
    )
    assert payload["quality_gate"]["decision"] == "classify_or_backfill_metadata_before_g4_apply"
    assert "SHOULD_NOT_LEAK" not in result.stdout



def test_python_module_cli_dogfood_scheduled_dry_run_bundles_read_only_reports_without_leaks(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "scheduled-dry-run.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Scheduled dry-run target phrase is SCHEDULED_DRY_RUN_OK.",
        metadata={"project": "scheduled-dry-run"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Scheduled dry-run",
        predicate="target_phrase",
        object_ref_or_value="SCHEDULED_DRY_RUN_OK",
        evidence_ids=[source.id],
        scope="project:scheduled-dry-run",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    env = {**os.environ, "PYTHONPATH": "src"}
    retrieve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "retrieve",
            str(db_path),
            "What is the scheduled dry-run phrase? token=SHOULD_NOT_LEAK",
            "--preferred-scope",
            "project:scheduled-dry-run",
            "--observe",
            "cli-test",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert retrieve_result.returncode == 0, retrieve_result.stderr

    with sqlite3.connect(db_path) as connection:
        observation_id = int(connection.execute("SELECT id FROM retrieval_observations").fetchone()[0])
        before_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    insert_experience_trace(
        db_path,
        surface="hermes-pre-llm-hook",
        event_kind="turn",
        content_sha256="f" * 64,
        summary=None,
        scope="project:scheduled-dry-run",
        related_memory_refs=[f"fact:{fact.id}"],
        related_observation_ids=[observation_id],
        retention_policy="ephemeral",
        metadata={
            "trace_recording": "default_metadata_only",
            "candidate_policy": "evidence_only",
            "auto_approved": False,
            "raw_prompt": "token=SHOULD_NOT_LEAK",
        },
    )
    before_counts["experience_traces"] += 1

    output_path = tmp_path / "scheduled-dry-run-report.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "scheduled-dry-run",
            str(db_path),
            "--output",
            str(output_path),
            "--since-hours",
            "24",
            "--epoch-start",
            "2000-01-01T00:00:00Z",
            "--min-trace-coverage",
            "0.25",
            "--min-evidence-count",
            "1",
            "--candidate-min",
            "0",
            "--max-decay-risk",
            "1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved_payload = json.loads(output_path.read_text())
    assert saved_payload == payload
    assert payload["kind"] == "dogfood_scheduled_dry_run"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["reports"]["storage_health"]["kind"] == "dogfood_storage_health"
    assert payload["reports"]["storage_health"]["status"] == "healthy"
    assert "storage_health_not_clean" not in payload["quality_gate"]["blocked_reasons"]
    assert payload["reports"]["trace_quality"]["kind"] == "dogfood_trace_quality"
    assert payload["reports"]["trace_quality"]["time_window"]["epoch_start"] == "2000-01-01 00:00:00"
    assert payload["thresholds"]["epoch_start"] == "2000-01-01T00:00:00Z"
    assert payload["reports"]["remember_intent"]["kind"] == "remember_intent_dogfood_report"
    assert payload["reports"]["background_dry_run"]["kind"] == "memory_consolidation_background_dry_run"
    assert payload["quality_gate"]["decision"] in {
        "continue_scheduled_dry_run_dogfooding_before_g4",
        "scheduled_dry_run_quality_gate_passed_plan_g4_only",
    }
    blocker_diagnostics = payload["quality_gate"]["blocker_diagnostics"]
    assert blocker_diagnostics["trace_quality_needs_more_dogfooding"]["source"] == "reports.trace_quality"
    assert blocker_diagnostics["trace_quality_needs_more_dogfooding"]["recommendation"] in {
        "continue_dogfooding",
        "ready_for_more_dry_runs",
        "consider_g4_plan",
    }
    assert blocker_diagnostics["trace_quality_needs_more_dogfooding"]["next_action"]
    assert "coverage_diagnostics" in blocker_diagnostics["trace_quality_needs_more_dogfooding"]
    assert blocker_diagnostics["trace_quality_needs_more_dogfooding"]["coverage_diagnostics"]["likely_gap"]
    assert blocker_diagnostics["decay_risk_above_threshold"]["source"] == (
        "reports.background_dry_run.review_handoff.decay_risk_candidate_count"
    )
    assert blocker_diagnostics["decay_risk_above_threshold"]["max_allowed"] == 1
    assert "candidate_decomposition" in blocker_diagnostics["decay_risk_above_threshold"]
    assert "top_factor_names" in blocker_diagnostics["decay_risk_above_threshold"]["candidate_decomposition"]
    assert blocker_diagnostics["background_quality_warnings_present"]["source"] == (
        "reports.background_dry_run.scan.quality_warnings"
    )
    assert isinstance(blocker_diagnostics["background_quality_warnings_present"]["warnings"], list)
    assert "empty_retrieval_activation_diagnostics" in blocker_diagnostics["background_quality_warnings_present"]
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
    }
    assert payload["privacy"]["raw_conversation_content_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "token=" not in result.stdout
    assert "SCHEDULED_DRY_RUN_OK" not in result.stdout

    with sqlite3.connect(db_path) as connection:
        after_counts = {
            table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
    assert after_counts == before_counts



def test_python_module_cli_dogfood_scheduled_blocker_resolution_classifies_fresh_aggregate_evidence(
    tmp_path: Path,
) -> None:
    report_path = tmp_path / "scheduled-report.json"
    output_path = tmp_path / "resolution.json"
    report_path.write_text(
        json.dumps(
            {
                "kind": "dogfood_scheduled_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "reports": {
                    "trace_quality": {
                        "recommendation": "ready_for_more_dry_runs",
                        "coverage": {"observation_trace_coverage_ratio": 0.34},
                        "retrieval_quality": {"empty_retrieval_ratio": 0.5061},
                        "warnings": [],
                    },
                    "background_dry_run": {
                        "review_handoff": {"decay_risk_candidate_count": 1},
                        "scan": {"quality_warnings": []},
                        "reports": {
                            "decay_risk": {
                                "candidate_decomposition": {
                                    "candidate_count": 1,
                                    "max_score": 0.2,
                                    "resolution_hint_counts": {"monitor_only_no_mutation": 1},
                                    "raw_content_included": False,
                                }
                            }
                        },
                    },
                },
                "quality_gate": {
                    "pass": False,
                    "blocked_reasons": [
                        "trace_quality_needs_more_dogfooding",
                        "decay_risk_above_threshold",
                    ],
                },
                "privacy": {
                    "raw_conversation_content_included": False,
                    "sample_values_included": False,
                    "raw_query_text_included": False,
                },
            }
        )
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "scheduled-blocker-resolution",
            "--report",
            str(report_path),
            "--output",
            str(output_path),
            "--accept-ready-trace-quality",
            "--allow-monitor-only-decay",
            "--max-empty-retrieval-ratio",
            "0.51",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "PYTHONPATH": "src"},
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert json.loads(output_path.read_text()) == payload
    assert payload["kind"] == "dogfood_scheduled_blocker_resolution"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["resolution_gate"] == {
        "pass": True,
        "decision": "scheduled_blockers_resolved_for_bounded_partial_automation_only",
        "unresolved_blockers": [],
    }
    assert payload["resolutions"]["trace_quality_needs_more_dogfooding"]["resolved"] is True
    assert payload["resolutions"]["decay_risk_above_threshold"]["resolution"] == "monitor_only_low_risk_decay_classified"
    assert payload["resolutions"]["background_quality_warnings_present"]["resolved"] is True
    assert payload["automation_policy"]["broad_g4_apply_allowed"] is False
    assert payload["automation_policy"]["bounded_partial_automation_allowed"] is True
    assert payload["privacy"]["raw_report_included"] is False


def test_python_module_cli_dogfood_scheduled_compare_summarizes_reports_without_raw_content(
    tmp_path: Path,
) -> None:
    report_a = tmp_path / "scheduled-a.json"
    report_b = tmp_path / "scheduled-b.json"
    output_path = tmp_path / "scheduled-compare.json"
    base_payload = {
        "kind": "dogfood_scheduled_dry_run",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": "/tmp/safe.db",
        "reports": {
            "storage_health": {"status": "warning", "mutated": False, "default_retrieval_unchanged": True},
            "trace_quality": {
                "recommendation": "continue_dogfooding",
                "coverage": {"observation_trace_coverage_ratio": 0.25},
                "retrieval_quality": {"empty_retrieval_ratio": 0.5},
                "mutated": False,
                "default_retrieval_unchanged": True,
            },
            "remember_intent": {
                "safe_remember_intent_count": 1,
                "rejected_remember_intent_count": 1,
                "raw_sample": "token=SHOULD_NOT_LEAK",
            },
            "background_dry_run": {
                "status": "completed",
                "mutated": False,
                "default_retrieval_unchanged": True,
                "review_handoff": {
                    "candidate_count": 1,
                    "reinforcement_candidate_count": 1,
                    "decay_risk_candidate_count": 0,
                },
                "scan": {"quality_warnings": ["low_activation_count", "no_clusters_meet_min_evidence"]},
            },
        },
        "quality_gate": {
            "pass": False,
            "decision": "continue_scheduled_dry_run_dogfooding_before_g4",
            "blocked_reasons": ["trace_quality_needs_more_dogfooding"],
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
        },
    }
    report_a.write_text(json.dumps(base_payload | {"generated_at": "2026-05-05T10:00:00Z"}))
    report_b.write_text(
        json.dumps(
            base_payload
            | {
                "generated_at": "2026-05-05T11:00:00Z",
                "reports": {
                    **base_payload["reports"],
                    "trace_quality": {
                        **base_payload["reports"]["trace_quality"],
                        "recommendation": "ready_for_more_dry_runs",
                        "coverage": {"observation_trace_coverage_ratio": 0.5},
                    },
                    "background_dry_run": {
                        **base_payload["reports"]["background_dry_run"],
                        "review_handoff": {
                            "candidate_count": 2,
                            "reinforcement_candidate_count": 2,
                            "decay_risk_candidate_count": 1,
                        },
                        "scan": {"quality_warnings": []},
                    },
                },
                "quality_gate": {
                    "pass": False,
                    "decision": "continue_scheduled_dry_run_dogfooding_before_g4",
                    "blocked_reasons": ["decay_risk_above_threshold"],
                },
            }
        )
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "scheduled-compare",
            "--report",
            str(report_a),
            "--report",
            str(report_b),
            "--output",
            str(output_path),
            "--min-report-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    saved_payload = json.loads(output_path.read_text())
    assert saved_payload == payload
    assert payload["kind"] == "dogfood_scheduled_dry_run_comparison"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["report_count"] == 2
    assert payload["aggregate"]["quality_gate_pass_count"] == 0
    assert payload["aggregate"]["candidate_count_max"] == 2
    assert payload["aggregate"]["decay_risk_candidate_count_max"] == 1
    assert payload["aggregate"]["trace_coverage_ratio_min"] == 0.25
    assert payload["aggregate"]["trace_coverage_ratio_max"] == 0.5
    assert payload["aggregate"]["blocked_reasons"] == [
        "decay_risk_above_threshold",
        "trace_quality_needs_more_dogfooding",
    ]
    assert payload["quality_gate"] == {
        "pass": False,
        "decision": "continue_scheduled_report_collection_before_g4",
        "blocked_reasons": [
            "scheduled_quality_gate_not_stable",
            "blocked_reasons_present",
            "decay_risk_above_threshold",
            "background_quality_warnings_present",
        ],
        "blocker_diagnostics": {
            "trace_quality_needs_more_dogfooding": {
                "blocked": True,
                "source": "aggregate.blocked_reasons",
                "report_count": 2,
                "affected_report_count": 1,
                "next_action": "Keep comparing scheduled reports until trace-quality blockers disappear consistently.",
            },
            "decay_risk_above_threshold": {
                "blocked": True,
                "source": "aggregate.decay_risk_candidate_count_max",
                "candidate_count_max": 1,
                "max_allowed": 0,
                "excess": 1,
                "next_action": "Inspect decay-risk candidates before broad G4 planning.",
            },
            "background_quality_warnings_present": {
                "blocked": True,
                "source": "aggregate.background_quality_warnings",
                "warning_count": 2,
                "warnings": ["low_activation_count", "no_clusters_meet_min_evidence"],
                "next_action": "Resolve or classify recurring background warnings before broad G4 planning.",
            },
        },
    }
    assert payload["privacy"]["raw_conversation_content_included"] is False
    assert payload["privacy"]["raw_query_text_included"] is False
    assert payload["privacy"]["sample_values_included"] is False
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "token=" not in result.stdout



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
    assert observation["metadata"] == {"hook_event_name": "pre_llm_call", "retrieval_outcome": "retrieved_memory"}



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
    observations = list_retrieval_observations(db_path)
    assert len(observations) == 1
    assert trace.related_observation_ids == [observations[0].id]
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
    observations = list_retrieval_observations(db_path)
    assert len(observations) == 1
    assert trace.related_observation_ids == [observations[0].id]
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

    dry_run_result = subprocess.run(
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
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert dry_run_result.returncode == 0, dry_run_result.stderr
    empty_diagnostics = json.loads(dry_run_result.stdout)["reports"]["activation_summary"]["empty_retrieval"]
    assert observations[0].response_mode == "verify_first"
    assert observations[0].metadata == {
        "hook_event_name": "pre_llm_call",
        "retrieval_outcome": "no_reliable_memory",
    }
    assert empty_diagnostics["by_surface"] == {"hermes-pre-llm-hook": 1}
    assert empty_diagnostics["by_hook_event_name"] == {"pre_llm_call": 1}
    assert empty_diagnostics["by_response_mode"] == {"verify_first": 1}
    assert empty_diagnostics["by_retrieval_outcome"] == {"no_reliable_memory": 1}
    assert empty_diagnostics["trace_linkage"] == {"linked_to_trace_count": 1, "unlinked_to_trace_count": 0}
    assert "SHOULD_NOT_APPEAR" not in dry_run_result.stdout
    assert "password" not in dry_run_result.stdout


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
    observations = list_retrieval_observations(db_path)
    assert len(observations) == 1
    assert trace.related_observation_ids == [observations[0].id]
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


def test_hermes_pre_llm_hook_records_korean_explicit_remember_intent_as_review_trace(tmp_path: Path) -> None:
    db_path = tmp_path / "remember-korean-intent-trace.db"
    initialize_database(db_path)

    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="korean-remember-session",
            cwd=str(tmp_path),
            extra={
                "user_message": "기억해둬: User prefers memory quality checks alongside consolidation.",
                "platform": "cli",
            },
        ),
        HermesPreLlmHookOptions(db_path=db_path, preferred_scope="project:g1", record_trace=True),
    )

    assert "context" in response
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.event_kind == "remember_intent"
    assert trace.retention_policy == "review"
    assert trace.summary == "User prefers memory quality checks alongside consolidation."
    assert trace.metadata["candidate_policy"] == "review_required"
    assert trace.metadata["secret_scan"] == "passed"


def test_hermes_pre_llm_hook_records_secret_like_remember_intent_as_rejected_diagnostic_without_raw_text(
    tmp_path: Path,
) -> None:
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
    trace = traces[0]
    assert trace.event_kind == "remember_intent"
    assert trace.retention_policy == "ephemeral"
    assert trace.summary is None
    assert trace.metadata["candidate_policy"] == "rejected"
    assert trace.metadata["secret_scan"] == "blocked"
    assert trace.metadata["rejected_reason"] == "secret_like_text"
    trace_json = trace.model_dump_json()
    assert "SUPERSECRET" not in trace_json
    assert "api_key" not in trace_json
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
            "10",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "SUPERSECRET" not in result.stdout
    assert "api_key" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["trace_counts"]["remember_intent"] == 1
    assert payload["review_ready_count"] == 0
    assert payload["unsafe_sample_count"] == 1
    assert payload["rejection_counts"] == {"secret_like_text": 1}



def test_hermes_pre_llm_hook_rejects_freeform_api_key_remember_intent_without_raw_text(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "remember-freeform-secret-skip.db"
    initialize_database(db_path)
    secret_prompt = "Remember this: api key sk-test-1234567890abcdef belongs to the smoke test"

    response = hermes_hooks.build_pre_llm_hook_context(
        HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id="freeform-secret-remember-session",
            cwd=str(tmp_path),
            extra={"user_message": secret_prompt, "platform": "cli"},
        ),
        HermesPreLlmHookOptions(db_path=db_path, preferred_scope="project:g1", record_trace=True),
    )

    assert "context" in response
    traces = list_experience_traces(db_path)
    assert len(traces) == 1
    trace = traces[0]
    assert trace.event_kind == "remember_intent"
    assert trace.retention_policy == "ephemeral"
    assert trace.summary is None
    assert trace.metadata["candidate_policy"] == "rejected"
    assert trace.metadata["secret_scan"] == "blocked"
    assert trace.metadata["rejected_reason"] == "secret_like_text"
    trace_json = trace.model_dump_json()
    assert "sk-test-1234567890abcdef" not in trace_json
    assert "api key" not in trace_json



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
    assert payload["rejection_counts"] == {}
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


@pytest.mark.xfail(strict=True, reason="Broad G4 apply contract is intentionally RED until apply mode is implemented.")
def test_dogfood_background_dry_run_broad_g4_apply_contract_red_until_supported(tmp_path: Path) -> None:
    db_path = tmp_path / "background-dogfood-future-apply.db"
    report_path = tmp_path / "background-report.json"
    initialize_database(db_path)
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
                    "candidates": {"candidate_count": 3, "trace_count": 8, "quality_warnings": []},
                    "activation_summary": {"activation_count": 25, "quality_warnings": []},
                    "reinforcement": {"candidate_count": 2, "quality_warnings": []},
                    "decay_risk": {"decay_risk_candidates": [], "quality_warnings": []},
                },
                "review_handoff": {
                    "candidate_count": 3,
                    "reinforcement_candidate_count": 2,
                    "decay_risk_candidate_count": 0,
                },
            },
            sort_keys=True,
        ),
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
            str(report_path),
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
    assert payload["quality_gate"]["pass"] is True
    assert payload["quality_gate"]["decision"] == "dry_run_quality_gate_passed_plan_g4_only"
    assert payload["automation_policy"] == {
        "apply_supported": True,
        "apply_mode": "broad_g4_review_queue",
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
        "mutation_contract": {
            "raw_content_allowed": False,
            "default_retrieval_policy_mutation_allowed": False,
            "memory_status_mutation_allowed": False,
            "writes_review_queue_only": True,
        },
    }



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
                    "activation_summary": {
                        "activation_count": 1,
                        "quality_warnings": [],
                        "empty_retrieval": {"count": 1, "ratio": 1.0, "by_surface": {"cli": 1}, "by_scope": {"global": 1}},
                    },
                    "reinforcement": {"candidate_count": 0, "quality_warnings": []},
                    "decay_risk": {
                        "candidate_decomposition": {
                            "candidate_count": 1,
                            "max_score": 0.85,
                            "top_factor_names": ["low_repetition", "weak_strength"],
                            "raw_content_included": False,
                        },
                        "decay_risk_candidates": [{"memory_ref": "fact:1"}],
                        "quality_warnings": [],
                    },
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
    blocker_diagnostics = payload["quality_gate"]["blocker_diagnostics"]
    assert blocker_diagnostics["decay_risk_above_threshold"] == {
        "blocked": True,
        "source": "aggregate.decay_risk_candidate_count_max",
        "candidate_count_max": 1,
        "max_allowed": 0,
        "excess": 1,
        "candidate_decomposition": {
            "report_count": 1,
            "top_factor_names": ["low_repetition", "weak_strength"],
            "max_score": 0.85,
            "raw_content_included": False,
        },
        "next_action": "Inspect aggregate decay-risk candidates before broad G4 planning.",
    }
    assert blocker_diagnostics["quality_warnings_present"]["blocked"] is True
    assert blocker_diagnostics["quality_warnings_present"]["source"] == "aggregate.quality_warnings"
    assert blocker_diagnostics["quality_warnings_present"]["warnings"] == ["no_clusters_meet_min_evidence"]
    assert blocker_diagnostics["quality_warnings_present"]["empty_retrieval_activation_diagnostics"] == [
        {"count": 1, "ratio": 1.0, "by_surface": {"cli": 1}, "by_scope": {"global": 1}}
    ]
    assert blocker_diagnostics["candidate_signal_below_threshold"]["candidate_count_max"] == 0
    assert payload["aggregate"]["candidate_count_max"] == 0
    assert payload["aggregate"]["decay_risk_candidate_count_max"] == 1
    assert "Do not enable background apply mode from this report." in payload["suggested_next_steps"]


def test_dogfood_trace_cluster_preview_reports_ref_safe_clusters_without_mutation(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-cluster-preview.db"
    output_path = tmp_path / "trace-cluster-preview.json"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Trace cluster preview source text should never appear in preview output.",
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Trace cluster preview",
        predicate="prefers",
        object_ref_or_value="ref safe reports",
        evidence_ids=[source.id],
        scope="project:trace-cluster-preview",
        confidence=0.91,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    for index in range(2):
        insert_experience_trace(
            db_path,
            surface="hermes-pre-llm-hook",
            event_kind="turn",
            content_sha256=f"{index + 1}" * 64,
            summary=f"token=SHOULD_NOT_LEAK cluster preview secret {index}",
            scope="project:trace-cluster-preview",
            related_memory_refs=[f"fact:{fact.id}"],
            related_observation_ids=[index + 10],
            retention_policy="ephemeral",
            metadata={
                "trace_recording": "default_metadata_only",
                "candidate_policy": "evidence_only",
                "auto_approved": False,
            },
        )
    before_counts = _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "source_records", "relations"],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-cluster-preview",
            str(db_path),
            "--min-evidence-count",
            "2",
            "--top",
            "5",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_trace_cluster_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["cluster_count"] == 1
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "trace_cluster_preview_ready_for_reviewed_candidate_flow",
        "blocked_reasons": [],
    }
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
        "mutation_contract": {
            "writes_review_queue": False,
            "promotes_long_term_memory": False,
            "raw_content_allowed": False,
        },
    }
    cluster = payload["clusters"][0]
    assert cluster["candidate_id"].startswith("candidate:")
    assert cluster["group_reason"] == {
        "reason": "shared_related_memory_ref",
        "shared_memory_ref": f"fact:{fact.id}",
        "shared_scope": "project:trace-cluster-preview",
    }
    assert cluster["evidence_count"] == 2
    assert cluster["related_memory_refs"] == [f"fact:{fact.id}"]
    assert cluster["related_observation_ids"] == [10, 11]
    assert cluster["review_score"] == {
        "score": 7,
        "tier": "high",
        "components": {
            "evidence_count": 2,
            "related_observation_count": 2,
            "related_memory_ref_count": 1,
            "salience_total": 0.0,
            "user_emphasis_total": 0.0,
            "reinforcement_count": 0,
            "risk_penalty": 0,
        },
    }
    assert cluster["review_recommendation"] == {
        "decision": "ready_for_human_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }
    assert "safe_summaries" not in cluster
    assert "cluster_key" not in cluster
    assert "cluster_key_sha256" in cluster
    assert payload["privacy"] == {
        "raw_conversation_content_included": False,
        "sample_values_included": False,
        "safe_summaries_included": False,
    }
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == payload
    assert _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "source_records", "relations"],
    ) == before_counts
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "token=" not in result.stdout
    assert "source text" not in result.stdout


def test_dogfood_reinforcement_refinement_preview_scores_repeated_activation_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "reinforcement-refinement-preview.db"
    output_path = tmp_path / "reinforcement-refinement-preview.json"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5d reinforcement refinement source text must not leak.",
        metadata={"project": "g5d-reinforcement"},
    )
    repeated_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5d reinforcement",
        predicate="needs",
        object_ref_or_value="preview-first refinement",
        evidence_ids=[source.id],
        scope="project:g5d-reinforcement",
        confidence=0.93,
    )
    approve_fact(db_path=db_path, fact_id=repeated_fact.id)
    weak_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5d weak candidate",
        predicate="has",
        object_ref_or_value="single activation",
        evidence_ids=[source.id],
        scope="project:g5d-reinforcement",
        confidence=0.7,
    )
    approve_fact(db_path=db_path, fact_id=weak_fact.id)
    insert_relation(
        db_path,
        from_ref=f"fact:{repeated_fact.id}",
        relation_type="supports",
        to_ref="concept:g5d-reinforcement",
        evidence_ids=[source.id],
        weight=0.8,
        confidence=0.8,
    )
    for index in range(3):
        record_retrieval_observation(
            db_path,
            surface="hermes-pre-llm-hook" if index < 2 else "cli",
            query="SHOULD_NOT_LEAK repeated reinforcement query",
            preferred_scope="project:g5d-reinforcement",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_fact_trace(repeated_fact.id, label="repeated reinforcement target")],
            response_mode="verify_first",
            metadata={"query_preview": "token=SHOULD_NOT_LEAK", "session_id": f"g5d-{index}"},
        )
    record_retrieval_observation(
        db_path,
        surface="cli",
        query="SHOULD_NOT_LEAK single reinforcement query",
        preferred_scope="project:g5d-reinforcement",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[_fact_trace(weak_fact.id, label="weak reinforcement target")],
        response_mode="verify_first",
        metadata={"raw_prompt": "SHOULD_NOT_LEAK"},
    )
    before_counts = _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "reinforcement-refinement-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_reinforcement_refinement_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
        "g5c_review_score_is_apply_approval": False,
        "mutation_contract": {
            "writes_review_queue": False,
            "increments_reinforcement_count": False,
            "promotes_long_term_memory": False,
            "raw_content_allowed": False,
        },
    }
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "reinforcement_refinement_preview_ready_for_human_review",
        "blocked_reasons": [],
    }
    candidates = {candidate["memory_ref"]: candidate for candidate in payload["reinforcement_candidates"]}
    repeated = candidates[f"fact:{repeated_fact.id}"]
    assert repeated["activation_count"] == 3
    assert repeated["current_status"] == "approved"
    assert repeated["review_score"]["tier"] == "high"
    assert repeated["review_recommendation"] == {
        "decision": "ready_for_reinforcement_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }
    assert repeated["refinement"] == {
        "candidate_action": "consider_reinforcement_marker_after_review",
        "apply_path": "not_supported_by_preview",
        "requires_separate_guarded_policy": True,
    }
    assert candidates[f"fact:{weak_fact.id}"]["review_recommendation"]["decision"] == "continue_dogfooding_before_review"
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == payload
    assert _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    ) == before_counts
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "source text" not in result.stdout
    assert "query_preview" not in result.stdout


def test_dogfood_decay_collapse_preview_reports_stale_weak_evidence_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "decay-collapse-preview.db"
    output_path = tmp_path / "decay-collapse-preview.json"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5e decay collapse source text and token=SHOULD_NOT_LEAK must not leak.",
        metadata={"project": "g5e-decay"},
    )
    stale_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5e stale weak evidence",
        predicate="needs",
        object_ref_or_value="collapse review preview",
        evidence_ids=[source.id],
        scope="project:g5e-decay",
        confidence=0.41,
    )
    fresh_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5e fresh evidence",
        predicate="needs",
        object_ref_or_value="protection from stale-only cleanup",
        evidence_ids=[source.id],
        scope="project:g5e-decay",
        confidence=0.94,
    )
    approve_fact(db_path=db_path, fact_id=fresh_fact.id)
    record_retrieval_observation(
        db_path,
        surface="hermes-pre-llm-hook",
        query="SHOULD_NOT_LEAK stale weak collapse query",
        preferred_scope="project:g5e-decay",
        limit=5,
        statuses=("approved", "candidate"),
        retrieval_trace=[_fact_trace(stale_fact.id, label="stale weak candidate")],
        response_mode="verify_first",
        metadata={"query_preview": "token=SHOULD_NOT_LEAK", "session_id": "g5e-stale"},
    )
    for index in range(4):
        record_retrieval_observation(
            db_path,
            surface="cli",
            query="SHOULD_NOT_LEAK fresh decay spacing query",
            preferred_scope="project:g5e-decay",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_fact_trace(fresh_fact.id, label="fresh protected target")],
            response_mode="verify_first",
            metadata={"raw_prompt": "SHOULD_NOT_LEAK", "session_id": f"g5e-fresh-{index}"},
        )
    before_counts = _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "decay-collapse-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
            "--min-decay-score",
            "0.5",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_decay_collapse_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
        "mutation_contract": {
            "writes_review_queue": False,
            "deprecates_or_deletes_memory": False,
            "collapses_memory": False,
            "raw_content_allowed": False,
        },
    }
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "decay_collapse_preview_ready_for_human_review",
        "blocked_reasons": [],
    }
    assert payload["candidate_count"] == 1
    candidate = payload["decay_collapse_candidates"][0]
    assert candidate["memory_ref"] == f"fact:{stale_fact.id}"
    assert candidate["current_status"] == "candidate"
    assert candidate["decay_score"] >= 0.5
    assert candidate["collapse_review"]["candidate_action"] == "consider_decay_or_collapse_after_review"
    assert candidate["collapse_review"]["apply_path"] == "not_supported_by_preview"
    assert candidate["collapse_review"]["requires_separate_guarded_policy"] is True
    assert candidate["review_recommendation"] == {
        "decision": "ready_for_decay_collapse_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }
    assert candidate["ref_safe_evidence"]["content_included"] is False
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == payload
    assert _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    ) == before_counts
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "source text" not in result.stdout
    assert "query_preview" not in result.stdout



def test_dogfood_decay_collapse_preview_handles_episode_source_ids_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "decay-collapse-episode-preview.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5e episode source text and token=SHOULD_NOT_LEAK must not leak.",
        metadata={"project": "g5e-decay-episode"},
    )
    episode = create_episode(
        db_path=db_path,
        title="G5e stale episode",
        summary="Episode evidence should be counted from source ids without reading raw content.",
        source_ids=[source.id],
        tags=["g5e", "episode"],
        importance_score=0.25,
        scope="project:g5e-decay",
        status="approved",
    )
    record_retrieval_observation(
        db_path,
        surface="hermes-pre-llm-hook",
        query="SHOULD_NOT_LEAK stale episode collapse query",
        preferred_scope="project:g5e-decay",
        limit=5,
        statuses=("approved",),
        retrieval_trace=[
            RetrievalTraceEntry(
                memory_type="episode",
                memory_id=episode.id,
                label="stale episode candidate",
                scope="project:g5e-decay",
                scope_priority=0,
                text_match_count=1,
                rank_value=0.7,
                total_score=0.7,
            )
        ],
        response_mode="verify_first",
        metadata={"query_preview": "token=SHOULD_NOT_LEAK", "session_id": "g5e-episode"},
    )

    before_counts = _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "procedures", "episodes"],
    )
    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "decay-collapse-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
            "--min-decay-score",
            "0.1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    candidates = {candidate["memory_ref"]: candidate for candidate in payload["decay_collapse_candidates"]}
    candidate = candidates[f"episode:{episode.id}"]
    assert candidate["ref_safe_evidence"]["evidence_id_count"] == 1
    assert candidate["ref_safe_evidence"]["content_included"] is False
    assert _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "procedures", "episodes"],
    ) == before_counts
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "source text" not in result.stdout


def test_dogfood_supersession_preview_reports_claim_conflicts_without_mutation(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "supersession-preview.db"
    output_path = tmp_path / "supersession-preview.json"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5f supersession source text token=SHOULD_NOT_LEAK must not leak.",
        metadata={"project": "g5f-supersession"},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="agent-memory runtime",
        predicate="uses_version",
        object_ref_or_value="v0.1.142 SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g5f",
        confidence=0.62,
    )
    new_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="agent-memory runtime",
        predicate="uses_version",
        object_ref_or_value="v0.1.143 SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g5f",
        confidence=0.93,
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)
    approve_fact(db_path=db_path, fact_id=new_fact.id)
    before_counts = _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    )

    env = {**os.environ, "PYTHONPATH": "src"}
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "supersession-preview",
            str(db_path),
            "--limit",
            "20",
            "--top",
            "5",
            "--output",
            str(output_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["kind"] == "dogfood_supersession_preview"
    assert payload["read_only"] is True
    assert payload["mutated"] is False
    assert payload["default_retrieval_unchanged"] is True
    assert payload["automation_policy"] == {
        "apply_supported": False,
        "ordinary_conversation_auto_approval": False,
        "requires_human_review": True,
        "default_retrieval_policy": "approved_only_unchanged",
        "mutation_contract": {
            "writes_review_queue": False,
            "creates_replacement_relation": False,
            "deprecates_or_deletes_memory": False,
            "raw_content_allowed": False,
        },
    }
    assert payload["quality_gate"] == {
        "pass": True,
        "decision": "supersession_preview_ready_for_human_review",
        "blocked_reasons": [],
    }
    assert payload["candidate_count"] == 1
    candidate = payload["supersession_candidates"][0]
    assert candidate["candidate_kind"] == "same_claim_slot_conflict"
    assert candidate["claim_slot"] == {
        "subject_ref_sha256": hashlib.sha256("agent-memory runtime".encode()).hexdigest(),
        "predicate": "uses_version",
        "scope": "project:g5f",
        "fact_count": 2,
    }
    assert candidate["older_fact_ref"] == f"fact:{old_fact.id}"
    assert candidate["newer_fact_ref"] == f"fact:{new_fact.id}"
    assert candidate["enriched_evidence"]["raw_content_included"] is False
    assert candidate["enriched_evidence"]["relation_signals"]["older_relation_count"] >= 0
    assert candidate["enriched_evidence"]["temporal_signals"]["order"] == "newer_fact_id_after_older"
    assert candidate["enriched_evidence"]["activation_signals"]["older_activation_count"] == 0
    assert candidate["review_score"]["tier"] == "high"
    assert candidate["review_recommendation"] == {
        "decision": "ready_for_supersession_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }
    assert candidate["review_commands"] == {
        "review_older": f"agent-memory review fact {db_path} {old_fact.id}",
        "review_newer": f"agent-memory review fact {db_path} {new_fact.id}",
        "review_replacements_older": f"agent-memory review replacements fact {db_path} {old_fact.id}",
        "future_guarded_apply": "not_supported_by_preview",
    }
    assert payload["privacy"] == {
        "raw_conversation_content_included": False,
        "sample_values_included": False,
        "safe_summaries_included": False,
        "subject_values_hashed": True,
        "object_values_included": False,
    }
    assert output_path.exists()
    assert json.loads(output_path.read_text()) == payload
    assert _table_counts(
        db_path,
        ["experience_traces", "retrieval_observations", "memory_activations", "facts", "relations"],
    ) == before_counts
    assert "SHOULD_NOT_LEAK" not in result.stdout
    assert "source text" not in result.stdout
    assert "v0.1.142" not in result.stdout
    assert "v0.1.143" not in result.stdout


def test_dogfood_lifecycle_candidate_registry_persists_lists_and_updates_supersession(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lifecycle-candidate-registry.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5f lifecycle registry source text token=SHOULD_NOT_LEAK must not leak.",
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="registry runtime",
        predicate="uses_version",
        object_ref_or_value="old SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g5f-registry",
        confidence=0.52,
    )
    new_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="registry runtime",
        predicate="uses_version",
        object_ref_or_value="new SHOULD_NOT_LEAK",
        evidence_ids=[source.id],
        scope="project:g5f-registry",
        confidence=0.91,
    )
    approve_fact(db_path=db_path, fact_id=old_fact.id)
    approve_fact(db_path=db_path, fact_id=new_fact.id)
    before_counts = _table_counts(db_path, ["facts", "relations", "memory_status_transitions"])
    env = {**os.environ, "PYTHONPATH": "src"}

    persist_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-persist",
            str(db_path),
            "--candidate-kind",
            "supersession",
            "--actor",
            "tester",
            "--reason",
            "registry runway",
            "--limit",
            "20",
            "--top",
            "5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    persist_payload = json.loads(persist_result.stdout)
    assert persist_payload["kind"] == "dogfood_lifecycle_candidate_persist"
    assert persist_payload["candidate_kind"] == "supersession"
    assert persist_payload["candidate_persistence_supported"] is True
    assert persist_payload["apply_supported"] is False
    assert persist_payload["inserted_count"] == 1
    assert persist_payload["privacy"] == {
        "candidate_json_included": False,
        "raw_content_included": False,
        "sample_values_included": False,
        "reason_stored_as_sha256": True,
    }
    candidate_id = persist_payload["candidate_ids"][0]

    list_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-list",
            str(db_path),
            "--candidate-kind",
            "supersession",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert list_result.returncode == 0, list_result.stderr
    list_payload = json.loads(list_result.stdout)
    assert list_payload["kind"] == "dogfood_lifecycle_candidate_list"
    assert list_payload["count"] == 1
    assert list_payload["items"] == [
        {
            "candidate_id": candidate_id,
            "status": "pending",
            "candidate_kind": "supersession",
            "proposal_type": "supersession_review",
            "target_ref": f"fact:{old_fact.id}",
            "candidate_sha256": persist_payload["source_preview_sha256"],
        }
    ]

    update_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-update",
            str(db_path),
            candidate_id,
            "--status",
            "approved",
            "--actor",
            "tester",
            "--reason",
            "approved for later guarded corridor",
            "--approval-phrase",
            "approve-g5-lifecycle-candidate-v1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert update_result.returncode == 0, update_result.stderr
    update_payload = json.loads(update_result.stdout)
    assert update_payload["kind"] == "dogfood_lifecycle_candidate_update"
    assert update_payload["status_before"] == "pending"
    assert update_payload["status_after"] == "approved"
    assert update_payload["apply_supported"] is False
    assert _table_counts(db_path, ["facts", "relations", "memory_status_transitions"]) == before_counts

    backup_path = tmp_path / "lifecycle-apply-backup.db"
    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-apply",
            str(db_path),
            "--candidate-id",
            candidate_id,
            "--policy",
            "g5-lifecycle-supersession-apply-v1",
            "--approval-phrase",
            "apply-approved-g5-lifecycle-supersession-v1",
            "--actor",
            "tester",
            "--reason",
            "guarded supersession relation",
            "--backup-path",
            str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["kind"] == "dogfood_lifecycle_candidate_apply"
    assert apply_payload["apply_mode"] == "approved_supersession_lifecycle_candidates_only"
    assert apply_payload["mutated"] is True
    assert apply_payload["default_retrieval_unchanged"] is True
    assert apply_payload["applied"] == [
        {
            "candidate_id": candidate_id,
            "action": "apply_reviewed_supersession_relation",
            "inserted": True,
            "superseded_ref": f"fact:{old_fact.id}",
            "replacement_ref": f"fact:{new_fact.id}",
        }
    ]
    assert apply_payload["backup"]["path"] == str(backup_path.resolve(strict=False))
    assert backup_path.exists()
    assert get_fact(db_path, fact_id=old_fact.id).status == "deprecated"
    assert get_fact(db_path, fact_id=new_fact.id).status == "approved"
    assert _table_counts(db_path, ["facts"])["facts"] == before_counts["facts"]
    assert _table_counts(db_path, ["relations"])["relations"] == before_counts["relations"] + 1
    assert "SHOULD_NOT_LEAK" not in apply_result.stdout
    assert "old " not in apply_result.stdout
    assert "new " not in apply_result.stdout
    assert "SHOULD_NOT_LEAK" not in persist_result.stdout
    assert "SHOULD_NOT_LEAK" not in list_result.stdout
    assert "SHOULD_NOT_LEAK" not in update_result.stdout


def test_dogfood_lifecycle_candidate_apply_deprecates_approved_decay_candidate_with_backup(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "lifecycle-decay-apply.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5g decay apply source text token=SHOULD_NOT_LEAK must not leak.",
        metadata={"project": "g5g-decay"},
    )
    stale_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5g stale weak evidence",
        predicate="needs",
        object_ref_or_value="guarded decay apply",
        evidence_ids=[source.id],
        scope="project:g5g-decay",
        confidence=0.41,
    )
    fresh_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5g fresh evidence",
        predicate="protects",
        object_ref_or_value="decay gate",
        evidence_ids=[source.id],
        scope="project:g5g-decay",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fresh_fact.id)
    record_retrieval_observation(
        db_path,
        surface="hermes-pre-llm-hook",
        query="SHOULD_NOT_LEAK stale weak collapse query",
        preferred_scope="project:g5g-decay",
        limit=5,
        statuses=("approved", "candidate"),
        retrieval_trace=[_fact_trace(stale_fact.id, label="stale weak candidate")],
        response_mode="verify_first",
        metadata={"query_preview": "token=SHOULD_NOT_LEAK", "session_id": "g5g-stale"},
    )
    for index in range(4):
        record_retrieval_observation(
            db_path,
            surface="cli",
            query="SHOULD_NOT_LEAK fresh decay spacing query",
            preferred_scope="project:g5g-decay",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_fact_trace(fresh_fact.id, label="fresh protected target")],
            response_mode="verify_first",
            metadata={"raw_prompt": "SHOULD_NOT_LEAK", "session_id": f"g5g-fresh-{index}"},
        )
    env = {**os.environ, "PYTHONPATH": "src"}
    persist_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-persist",
            str(db_path),
            "--candidate-kind",
            "decay",
            "--actor",
            "tester",
            "--reason",
            "decay apply runway",
            "--limit",
            "20",
            "--top",
            "5",
            "--frequent-threshold",
            "3",
            "--min-decay-score",
            "0.5",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    candidate_id = json.loads(persist_result.stdout)["candidate_ids"][0]
    proof_artifact_path = tmp_path / "decay-collapse-proof.json"
    proof_artifact_path.write_text(
        json.dumps(
            {
                "current_status": "partially_satisfied",
                "missing_evidence": ["relation_equivalence_or_supersession_chain", "retrieval_eval_gate_pass"],
                "proof_inputs": {"human_reviewed_candidate_payload": True},
            }
        )
    )
    update_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-update",
            str(db_path),
            candidate_id,
            "--status",
            "approved",
            "--actor",
            "tester",
            "--reason",
            "approved guarded decay deprecate",
            "--approval-phrase",
            "approve-g5-lifecycle-candidate-v1",
            "--collapse-proof-artifact-json",
            str(proof_artifact_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert update_result.returncode == 0, update_result.stderr
    update_payload = json.loads(update_result.stdout)
    assert update_payload["proof_artifact_stored"] is True
    assert update_payload["proof_artifact_status"] == "partially_satisfied"
    assert update_payload["proof_artifact_sha256"]
    backup_path = tmp_path / "decay-apply-backup.db"
    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "lifecycle-candidate-apply",
            str(db_path),
            "--candidate-id",
            candidate_id,
            "--policy",
            "g5-lifecycle-decay-deprecate-apply-v1",
            "--approval-phrase",
            "apply-approved-g5-lifecycle-decay-deprecate-v1",
            "--actor",
            "tester",
            "--reason",
            "guarded decay deprecate",
            "--backup-path",
            str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    payload = json.loads(apply_result.stdout)
    assert payload["apply_mode"] == "approved_decay_lifecycle_candidates_deprecate_only"
    assert payload["applied"] == [
        {
            "candidate_id": candidate_id,
            "action": "apply_reviewed_decay_deprecation",
            "memory_ref": f"fact:{stale_fact.id}",
            "inserted": True,
        }
    ]
    assert payload["rollback_hint"]["restore_backup_to_revert"] is True
    assert backup_path.exists()
    assert get_fact(db_path, fact_id=stale_fact.id).status == "deprecated"
    assert "SHOULD_NOT_LEAK" not in persist_result.stdout
    assert "SHOULD_NOT_LEAK" not in apply_result.stdout


def test_dogfood_new_brainlike_readiness_commands_are_safe_and_helpful(tmp_path: Path) -> None:
    db_path = tmp_path / "brainlike-readiness.db"
    initialize_database(db_path)
    _seed_trace_cluster_for_candidate_flow(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    generate_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "trace-candidate-generate", str(db_path), "--limit", "20", "--top", "5"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert generate_result.returncode == 0, generate_result.stderr
    generate_payload = json.loads(generate_result.stdout)
    assert generate_payload["kind"] == "dogfood_trace_candidate_generate"
    assert generate_payload["mutated"] is False
    assert generate_payload["automation_policy"]["ordinary_conversation_auto_approval"] is False

    rollback_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "rollback-confidence", str(db_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert rollback_result.returncode == 0, rollback_result.stderr
    rollback_payload = json.loads(rollback_result.stdout)
    assert rollback_payload["kind"] == "dogfood_rollback_confidence"
    assert rollback_payload["read_only"] is True
    assert rollback_payload["quality_gate"]["pass"] is True

    eval_source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Ranking gate fact says Project Gate uses retrieval eval before ranking changes.",
    )
    gate_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Gate",
        predicate="ranking_policy",
        object_ref_or_value="run retrieval eval before ranking changes",
        evidence_ids=[eval_source.id],
        scope="project:gate",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=gate_fact.id)
    fixture_path = tmp_path / "ranking-gate-fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "ranking-gate",
                        "query": "What must Project Gate run before ranking changes?",
                        "preferred_scope": "project:gate",
                        "limit": 5,
                        "expected": {"facts": [gate_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    ranking_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "retrieval-ranking-gate",
            str(db_path),
            "--fixtures",
            str(fixture_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert ranking_result.returncode == 0, ranking_result.stderr
    ranking_payload = json.loads(ranking_result.stdout)
    assert ranking_payload["kind"] == "dogfood_retrieval_ranking_gate"
    assert ranking_payload["read_only"] is True
    assert "ranking_change_allowed" in ranking_payload
    assert ranking_payload["policy"] == "ranking changes require passing retrieval eval gate before implementation"



def test_retrieval_ranking_opt_in_default_migration_is_shadow_gated_and_rollbackable(tmp_path: Path) -> None:
    db_path = tmp_path / "ranking-migration.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Ranking migration keeps conservative legacy as default until explicit approval.",
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Ranking migration",
        predicate="default_policy",
        object_ref_or_value="conservative legacy until explicit approval",
        evidence_ids=[source.id],
        scope="project:ranking-migration",
        confidence=0.95,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    fixture_path = tmp_path / "ranking-migration-fixture.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "ranking-migration-default-freeze",
                        "query": "What default policy does ranking migration keep?",
                        "preferred_scope": "project:ranking-migration",
                        "limit": 5,
                        "expected": {"facts": [fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                        "source": "ranking-migration-test",
                        "rationale": "covers explicit opt-in-to-default migration gate",
                    }
                ]
            },
            indent=2,
        )
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    experiment_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "retrieval-ranking-experiment",
            str(db_path),
            "--fixtures",
            str(fixture_path),
            "--ranking-policy",
            "graph_reinforced_v1",
            "--shadow-compare",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert experiment_result.returncode == 0, experiment_result.stderr
    experiment_payload = json.loads(experiment_result.stdout)
    assert experiment_payload["active_ranking_policy"] == "conservative_legacy"
    assert experiment_payload["candidate_ranking_policy"] == "graph_reinforced_v1"
    assert experiment_payload["shadow_compare"]["mode"] == "legacy_returned_candidate_compared"
    assert experiment_payload["shadow_compare"]["protected_default_order_returned"] is True
    assert experiment_payload["promotion_policy"]["migration_command_required"] is True
    assert experiment_payload["default_retrieval_unchanged"] is True

    config_path = tmp_path / "agent-memory-ranking-config.yaml"
    config_path.write_text("agent_memory:\n  retrieval_ranking_policy: conservative_legacy\n")
    audit_path = tmp_path / "ranking-migration-audit.json"
    migrate_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "retrieval-ranking-migrate-default",
            str(db_path),
            "--fixtures",
            str(fixture_path),
            "--policy",
            "graph_reinforced_v1",
            "--config-path",
            str(config_path),
            "--actor",
            "tester",
            "--reason",
            "promote candidate ranking after fixture gate",
            "--approval-phrase",
            "migrate-retrieval-ranking-default-v1",
            "--audit-output",
            str(audit_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert migrate_result.returncode == 0, migrate_result.stderr
    migrate_payload = json.loads(migrate_result.stdout)
    assert migrate_payload["kind"] == "dogfood_retrieval_ranking_migrate_default"
    assert migrate_payload["mutated"] is True
    assert migrate_payload["mutation_scope"] == "config_only"
    assert migrate_payload["policy_before"] == "conservative_legacy"
    assert migrate_payload["policy_after"] == "graph_reinforced_v1"
    assert migrate_payload["rollback_command"]["policy"] == "conservative_legacy"
    assert migrate_payload["rollback_replay_gate"]["protected_durable_tables_unchanged"] is True
    assert "retrieval_ranking_policy: graph_reinforced_v1" in config_path.read_text()
    assert json.loads(audit_path.read_text())["policy_after"] == "graph_reinforced_v1"

    rollback_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "retrieval-ranking-migrate-default",
            str(db_path),
            "--fixtures",
            str(fixture_path),
            "--policy",
            "conservative_legacy",
            "--config-path",
            str(config_path),
            "--actor",
            "tester",
            "--reason",
            "rollback ranking default",
            "--approval-phrase",
            "migrate-retrieval-ranking-default-v1",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert rollback_result.returncode == 0, rollback_result.stderr
    rollback_payload = json.loads(rollback_result.stdout)
    assert rollback_payload["policy_before"] == "graph_reinforced_v1"
    assert rollback_payload["policy_after"] == "conservative_legacy"
    assert "retrieval_ranking_policy: conservative_legacy" in config_path.read_text()



def test_dogfood_g5h_next_brainlike_steps_are_read_only_or_guarded(tmp_path: Path) -> None:
    db_path = tmp_path / "g5h-next-steps.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5h next-step source token=SHOULD_NOT_LEAK must stay private. Project G5h uses rollback replay before automation.",
        metadata={"project": "g5h"},
    )
    stale_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project G5h stale memory",
        predicate="needs",
        object_ref_or_value="reviewed deprecation",
        evidence_ids=[source.id],
        scope="project:g5h",
        confidence=0.42,
    )
    ranked_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project G5h ranking",
        predicate="requires",
        object_ref_or_value="eval backed experiment",
        evidence_ids=[source.id],
        scope="project:g5h",
        confidence=0.96,
    )
    approve_fact(db_path=db_path, fact_id=ranked_fact.id)
    record_retrieval_observation(
        db_path,
        surface="cli",
        query="SHOULD_NOT_LEAK stale g5h decay query",
        preferred_scope="project:g5h",
        limit=5,
        statuses=("approved", "candidate"),
        retrieval_trace=[_fact_trace(stale_fact.id, label="g5h stale candidate")],
        response_mode="verify_first",
        metadata={"session_id": "g5h-stale", "raw_prompt": "SHOULD_NOT_LEAK"},
    )
    for index in range(4):
        record_retrieval_observation(
            db_path,
            surface="cli",
            query="SHOULD_NOT_LEAK g5h decay query",
            preferred_scope="project:g5h",
            limit=5,
            statuses=("approved",),
            retrieval_trace=[_fact_trace(ranked_fact.id, label="g5h ranked fact")],
            response_mode="verify_first",
            metadata={"session_id": f"g5h-{index}", "raw_prompt": "SHOULD_NOT_LEAK"},
        )
    before_counts = _table_counts(db_path, ["facts", "relations", "memory_status_transitions", "retrieval_observations", "experience_traces"])
    env = {**os.environ, "PYTHONPATH": "src"}

    persist_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "lifecycle-candidate-persist", str(db_path),
            "--candidate-kind", "decay", "--actor", "tester", "--reason", "g5h decay candidate", "--limit", "20", "--top", "5",
            "--frequent-threshold", "3", "--min-decay-score", "0.5",
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    candidate_id = json.loads(persist_result.stdout)["candidate_ids"][0]
    g5h_proof_artifact_path = tmp_path / "g5h-collapse-proof.json"
    g5h_proof_artifact_path.write_text(
        json.dumps(
            {
                "current_status": "satisfied",
                "missing_evidence": [],
                "proof_inputs": {
                    "rollback_replay_validate_pass": True,
                    "relation_equivalence_or_supersession_chain": True,
                    "retrieval_eval_gate_pass": True,
                    "human_reviewed_candidate_payload": True,
                },
                "relation_equivalence_evidence": {
                    "type": "reviewed_supersession_chain",
                    "superseded_ref": f"fact:{stale_fact.id}",
                    "replacement_ref": f"fact:{ranked_fact.id}",
                    "reviewed": True,
                },
            }
        )
    )
    update_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "lifecycle-candidate-update", str(db_path), candidate_id,
            "--status", "approved", "--actor", "tester", "--reason", "approve g5h", "--approval-phrase", "approve-g5-lifecycle-candidate-v1",
            "--collapse-proof-artifact-json", str(g5h_proof_artifact_path),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert update_result.returncode == 0, update_result.stderr
    update_payload = json.loads(update_result.stdout)
    assert update_payload["proof_artifact_stored"] is True
    assert update_payload["proof_artifact_status"] == "satisfied"
    backup_path = tmp_path / "g5h-apply-backup.db"
    apply_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "lifecycle-candidate-apply", str(db_path),
            "--candidate-id", candidate_id, "--policy", "g5-lifecycle-decay-deprecate-apply-v1",
            "--approval-phrase", "apply-approved-g5-lifecycle-decay-deprecate-v1", "--actor", "tester", "--reason", "guarded g5h apply",
            "--backup-path", str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    supersession_relation = supersede_fact(
        db_path=db_path,
        superseded_fact_id=stale_fact.id,
        replacement_fact_id=ranked_fact.id,
        actor="tester",
        reason="reviewed supersession-chain evidence for collapse proof",
        evidence_ids=[source.id],
    )
    assert supersession_relation.relation_type == "superseded_by"

    replay_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "rollback-replay-validate", str(db_path)],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert replay_result.returncode == 0, replay_result.stderr
    replay_payload = json.loads(replay_result.stdout)
    assert replay_payload["kind"] == "dogfood_rollback_replay_validate"
    assert replay_payload["read_only"] is True
    assert replay_payload["quality_gate"]["pass"] is True
    assert replay_payload["applications"][0]["rollback_replay_validation"]["restored_db_opened"] is True
    assert replay_payload["applications"][0]["rollback_replay_validation"]["table_counts_match_backup"] is True
    assert replay_payload["rollup"] == {
        "checked_application_count": 1,
        "passed_replay_count": 1,
        "failed_replay_count": 0,
        "policy_counts": {"g5-lifecycle-decay-deprecate-apply-v1": 1},
        "latest_application_created_at": replay_payload["applications"][0]["created_at"],
        "live_report_accumulation_safe": True,
    }

    fixture_path = tmp_path / "g5h-ranking-fixture.json"
    fixture_path.write_text(json.dumps({"tasks": [{"id": "g5h-ranking", "query": "What does Project G5h ranking require?", "preferred_scope": "project:g5h", "limit": 5, "expected": {"facts": [ranked_fact.id], "procedures": [], "episodes": []}, "avoid": {"facts": [], "procedures": [], "episodes": []}, "source": "live-compatible-g5i", "rationale": "covers eval-gated opt-in ranking on live-shaped scopes"}]}))
    experiment_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "retrieval-ranking-experiment", str(db_path),
            "--fixtures", str(fixture_path), "--reinforcement-weight", "1.5", "--reinforcement-cap", "1.0",
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert experiment_result.returncode == 0, experiment_result.stderr
    experiment_payload = json.loads(experiment_result.stdout)
    assert experiment_payload["kind"] == "dogfood_retrieval_ranking_experiment"
    assert experiment_payload["read_only"] is True
    assert experiment_payload["default_retrieval_unchanged"] is True
    assert experiment_payload["promotion_policy"]["ordinary_conversation_auto_enable"] is False
    assert experiment_payload["fixture_expansion"] == {
        "task_count": 1,
        "live_compatible_task_count": 1,
        "scoped_task_count": 1,
        "has_rationale_count": 1,
        "fixture_source_counts": {"live-compatible-g5i": 1},
        "live_runtime_safe": True,
    }
    assert experiment_payload["fixture_gate_comparison"] == {
        "comparison_mode": "expanded_fixtures_vs_current_default_read_only",
        "baseline_mode": "current_default",
        "active_ranking_policy": "conservative_legacy",
        "candidate_ranking_policy": "conservative_legacy",
        "fixture_task_count": 1,
        "expanded_fixture_gate_met": False,
        "eval_gate_pass": True,
        "baseline_regression_count": 0,
        "max_baseline_regressions": 0,
        "previewed_task_count": 1,
        "rank_change_count": experiment_payload["rank_change_count"],
        "default_ranking_mutated": False,
        "ordinary_conversation_auto_enable": False,
    }

    decision_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "decay-collapse-decision", str(db_path),
            "--limit", "20", "--top", "5", "--fixtures", str(fixture_path),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert decision_result.returncode == 0, decision_result.stderr
    decision_payload = json.loads(decision_result.stdout)
    assert decision_payload["decision"]["deprecate_corridor"] == "supported_for_reviewed_approved_decay_candidates"
    assert decision_payload["decision"]["collapse_corridor"].startswith("blocked")
    assert "g5-lifecycle-delete-apply-v1" in decision_payload["blocked_policies"]
    proof = decision_payload["collapse_equivalence_proof"]
    assert proof["proof_required"] is True
    assert proof["accepted_evidence"] == [
        "rollback_replay_validate_pass",
        "relation_equivalence_or_supersession_chain",
        "retrieval_eval_gate_pass",
        "human_reviewed_candidate_payload",
    ]
    assert proof["evidence_status"]["rollback_replay_validate_pass"]["passed"] is True
    assert proof["evidence_status"]["human_reviewed_candidate_payload"]["passed"] is True
    assert proof["evidence_status"]["retrieval_eval_gate_pass"]["passed"] is True
    assert proof["evidence_status"]["relation_equivalence_or_supersession_chain"]["passed"] is True
    assert proof["evidence_status"]["relation_equivalence_or_supersession_chain"]["replacement_relation_evidence_count"] == 1
    assert proof["green_evidence_count"] == 4
    assert proof["required_evidence_count"] == 4
    assert proof["missing_evidence"] == []
    assert proof["current_status"] == "satisfied"
    replay = proof["candidate_proof_replay"]
    assert replay["reviewed_decay_candidate_count"] == 1
    assert replay["artifact_count"] == 1
    assert replay["green_artifact_count"] == 1
    assert replay["all_candidate_artifacts_green"] is True
    assert replay["missing_artifact_candidate_ids"] == []
    assert replay["items"] == [
        {
            "candidate_id": candidate_id,
            "target_ref": f"fact:{stale_fact.id}",
            "artifact_present": True,
            "current_status": "satisfied",
            "missing_evidence": [],
            "replacement_relation_evidence_count": 1,
            "collapse_apply_allowed": False,
            "delete_apply_allowed": False,
        }
    ]
    assert proof["collapse_apply_allowed"] is False
    assert proof["delete_apply_allowed"] is False

    _seed_trace_cluster_for_candidate_flow(db_path)
    generate_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "trace-candidate-generate", str(db_path), "--limit", "20", "--top", "5"],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert generate_result.returncode == 0, generate_result.stderr
    generate_payload = json.loads(generate_result.stdout)
    assert generate_payload["generated_candidates"]
    generated = generate_payload["generated_candidates"][0]
    assert "classification_signals" in generated
    assert "quality_annotations" in generated
    assert "promotion_template" in generated
    assert generated["quality_annotations"]["auto_promotion_allowed"] is False

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE retrieval_observations SET created_at = '2020-01-01T00:00:00+00:00'")
        connection.execute("UPDATE experience_traces SET created_at = '2026-01-01T00:00:00+00:00'")
    reconciliation_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "telemetry-reconciliation", str(db_path),
            "--epoch-start", "2025-01-01T00:00:00+00:00",
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert reconciliation_result.returncode == 0, reconciliation_result.stderr
    reconciliation_payload = json.loads(reconciliation_result.stdout)
    assert reconciliation_payload["kind"] == "dogfood_telemetry_reconciliation"
    assert reconciliation_payload["read_only"] is True
    assert reconciliation_payload["apply_corridor"]["protected_memory_tables_mutated"] is False
    assert reconciliation_payload["apply_corridor"]["ordinary_conversation_auto_apply"] is False
    assert reconciliation_payload["apply_corridor"]["safety_gate"] == {
        "fresh_epoch_gate_required": True,
        "fresh_epoch_comparison_required_for_live_apply": True,
        "backup_required": True,
        "post_apply_preview_required": True,
        "rollback_restore_replay_required_before_broad_g4": True,
        "protected_table_count_verification_required": True,
    }
    apply_reset_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "telemetry-reset-apply", str(db_path),
            "--epoch-start", "2025-01-01T00:00:00+00:00",
            "--policy", "telemetry-reset-v1",
            "--approval-phrase", "apply-telemetry-reset-v1",
            "--actor", "tester",
            "--reason", "g5i telemetry only corridor",
            "--backup-path", str(tmp_path / "g5i-telemetry-reset.backup.db"),
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert apply_reset_result.returncode == 0, apply_reset_result.stderr
    apply_reset_payload = json.loads(apply_reset_result.stdout)
    assert apply_reset_payload["quality_gate"] == {
        "pass": True,
        "decision": "telemetry_only_reset_applied_with_protected_tables_verified",
        "blocked_reasons": [],
    }

    g4_result = subprocess.run(
        [
            sys.executable, "-m", "agent_memory.api.cli", "dogfood", "g4-review-queue-preview", str(db_path),
            "--limit", "20", "--top", "5", "--queue-limit", "5", "--epoch-start", "2025-01-01T00:00:00+00:00",
        ],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert g4_result.returncode == 0, g4_result.stderr
    g4_payload = json.loads(g4_result.stdout)
    assert g4_payload["broad_g4_apply_reassessment"]["broad_g4_apply_allowed"] is False
    assert g4_payload["broad_g4_apply_reassessment"]["required_green_gates"] == [
        "retrieval_ranking_gate_pass",
        "rollback_confidence_pass",
        "rollback_replay_validate_pass",
        "live_telemetry_reconciliation_pass",
        "human_review_queue_approval_pass",
    ]
    assert _table_counts(db_path, ["facts", "relations"])["facts"] == before_counts["facts"] + 1
    assert "SHOULD_NOT_LEAK" not in replay_result.stdout
    assert "SHOULD_NOT_LEAK" not in experiment_result.stdout
    assert "SHOULD_NOT_LEAK" not in decision_result.stdout
    assert "SHOULD_NOT_LEAK" not in generate_result.stdout
    assert "SHOULD_NOT_LEAK" not in reconciliation_result.stdout


def _seed_trace_cluster_for_candidate_flow(db_path: Path) -> int:
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="G5 reviewed candidate seed source text must not leak.",
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="G5 candidate flow",
        predicate="needs",
        object_ref_or_value="reviewed promotion",
        evidence_ids=[source.id],
        scope="project:g5-candidates",
        confidence=0.92,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    for index in range(2):
        insert_experience_trace(
            db_path,
            surface="hermes-pre-llm-hook",
            event_kind="turn",
            content_sha256=f"g5{index}".encode().hex().ljust(64, "0")[:64],
            summary=f"raw-secret-token g5 candidate summary {index}",
            scope="project:g5-candidates",
            related_memory_refs=[f"fact:{fact.id}"],
            related_observation_ids=[index + 21],
            retention_policy="ephemeral",
            metadata={"trace_recording": "default_metadata_only", "candidate_policy": "evidence_only"},
        )
    return fact.id


def test_dogfood_trace_candidate_review_flow_persists_lists_and_updates_without_promotion(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-candidate-flow.db"
    initialize_database(db_path)
    existing_fact_id = _seed_trace_cluster_for_candidate_flow(db_path)
    before_counts = _table_counts(db_path, ["facts", "memory_status_transitions", "experience_traces"])
    env = {**os.environ, "PYTHONPATH": "src"}

    persist_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-persist",
            str(db_path),
            "--actor",
            "tester",
            "--reason",
            "review candidate runway",
            "--min-evidence-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    persist_payload = json.loads(persist_result.stdout)
    assert persist_payload["kind"] == "dogfood_trace_candidate_persist"
    assert persist_payload["candidate_persistence_supported"] is True
    assert persist_payload["promotion_supported"] is False
    assert persist_payload["inserted_count"] == 1
    assert persist_payload["privacy"] == {
        "cluster_json_included": False,
        "raw_content_included": False,
        "safe_summaries_included": False,
        "reason_stored_as_sha256": True,
    }
    candidate_id = persist_payload["candidate_ids"][0]

    list_result = subprocess.run(
        [sys.executable, "-m", "agent_memory.api.cli", "dogfood", "trace-candidate-list", str(db_path)],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert list_result.returncode == 0, list_result.stderr
    list_payload = json.loads(list_result.stdout)
    assert list_payload["kind"] == "dogfood_trace_candidate_list"
    assert list_payload["items"] == [
        {
            "candidate_id": candidate_id,
            "status": "pending",
            "proposal_type": "trace_cluster_review",
            "target_ref": f"fact:{existing_fact_id}",
            "cluster_sha256": persist_payload["source_preview_sha256"],
        }
    ]
    assert list_payload["privacy"]["cluster_json_included"] is False

    update_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-update",
            str(db_path),
            candidate_id,
            "--status",
            "approved",
            "--actor",
            "tester",
            "--reason",
            "human reviewed promotion fields",
            "--approval-phrase",
            "approve-g5-trace-candidate-v1",
            "--promotion-type",
            "fact",
            "--subject",
            "G5 reviewed candidates",
            "--predicate",
            "require",
            "--object",
            "human-approved promotion fields",
            "--scope",
            "project:g5-candidates",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert update_result.returncode == 0, update_result.stderr
    update_payload = json.loads(update_result.stdout)
    assert update_payload["kind"] == "dogfood_trace_candidate_update"
    assert update_payload["status_before"] == "pending"
    assert update_payload["status_after"] == "approved"
    assert update_payload["proposal_type"] == "fact_promotion"
    assert update_payload["promotion_ready"] is True
    assert update_payload["apply_supported"] is False
    assert update_payload["privacy"] == {"reviewed_payload_included": False, "raw_reason_included": False, "raw_content_included": False}
    assert "raw-secret-token" not in persist_result.stdout + list_result.stdout + update_result.stdout
    assert _table_counts(db_path, ["facts", "memory_status_transitions", "experience_traces"]) == before_counts


def test_dogfood_trace_candidate_apply_promotes_only_approved_reviewed_fact_candidates(tmp_path: Path) -> None:
    db_path = tmp_path / "trace-candidate-apply.db"
    backup_path = tmp_path / "trace-candidate-apply.bak"
    initialize_database(db_path)
    _seed_trace_cluster_for_candidate_flow(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    persist_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-persist",
            str(db_path),
            "--actor",
            "tester",
            "--reason",
            "persist before approval",
            "--min-evidence-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    candidate_id = json.loads(persist_result.stdout)["candidate_ids"][0]
    before_pending_counts = _table_counts(db_path, ["facts", "memory_status_transitions"])

    pending_apply = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-apply",
            str(db_path),
            "--candidate-id",
            candidate_id,
            "--policy",
            "g5-reviewed-candidate-promotion-v1",
            "--approval-phrase",
            "apply-approved-g5-reviewed-candidates-v1",
            "--actor",
            "tester",
            "--reason",
            "should skip pending",
            "--backup-path",
            str(backup_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert pending_apply.returncode == 0, pending_apply.stderr
    pending_payload = json.loads(pending_apply.stdout)
    assert pending_payload["applied_count"] == 0
    assert pending_payload["skipped_items"] == [{"candidate_id": candidate_id, "reason": "status_pending"}]
    assert _table_counts(db_path, ["facts", "memory_status_transitions"]) == before_pending_counts

    approve_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-update",
            str(db_path),
            candidate_id,
            "--status",
            "approved",
            "--actor",
            "tester",
            "--reason",
            "approve explicit reviewed fact",
            "--approval-phrase",
            "approve-g5-trace-candidate-v1",
            "--promotion-type",
            "fact",
            "--subject",
            "Reviewed G5 candidate",
            "--predicate",
            "promotes_to",
            "--object",
            "approved fact memory",
            "--scope",
            "project:g5-candidates",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert approve_result.returncode == 0, approve_result.stderr

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-apply",
            str(db_path),
            "--candidate-id",
            candidate_id,
            "--policy",
            "g5-reviewed-candidate-promotion-v1",
            "--approval-phrase",
            "apply-approved-g5-reviewed-candidates-v1",
            "--actor",
            "tester",
            "--reason",
            "apply explicit reviewed fact",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    payload = json.loads(apply_result.stdout)
    assert payload["kind"] == "dogfood_trace_candidate_apply"
    assert payload["policy"] == "g5-reviewed-candidate-promotion-v1"
    assert payload["applied_count"] == 1
    assert payload["skipped_count"] == 0
    assert payload["applied_items"][0]["action"] == "promote_reviewed_fact"
    promoted_ref = payload["applied_items"][0]["promoted_ref"]
    assert promoted_ref.startswith("fact:")
    with sqlite3.connect(db_path) as connection:
        row = connection.execute("SELECT subject_ref, predicate, object_ref_or_value, status FROM facts WHERE id = ?", (int(promoted_ref.split(":")[1]),)).fetchone()
    assert row == ("Reviewed G5 candidate", "promotes_to", "approved fact memory", "approved")
    assert payload["memory_status_mutated"] is True
    assert payload["default_retrieval_unchanged"] is True
    assert payload["ordinary_conversation_auto_approval"] is False
    assert payload["privacy"]["reviewed_payload_included"] is False
    assert "raw-secret-token" not in apply_result.stdout


@pytest.mark.parametrize(
    ("promotion_type", "update_args", "expected_action", "expected_ref_prefix", "table", "columns", "expected_row"),
    [
        (
            "preference",
            [
                "--promotion-type",
                "preference",
                "--subject",
                "user",
                "--predicate",
                "prefers",
                "--object",
                "explicit reviewed memory promotion",
                "--scope",
                "global",
            ],
            "promote_reviewed_preference",
            "fact:",
            "facts",
            "subject_ref, predicate, object_ref_or_value, status",
            ("user", "prefers", "explicit reviewed memory promotion", "approved"),
        ),
        (
            "procedure",
            [
                "--promotion-type",
                "procedure",
                "--name",
                "Run reviewed candidate promotion",
                "--trigger-context",
                "when a trace candidate is explicitly approved",
                "--precondition",
                "candidate status is approved",
                "--step",
                "create the reviewed durable memory",
                "--step",
                "record audit and rollback hints",
                "--scope",
                "project:g5-candidates",
                "--success-rate",
                "0.8",
            ],
            "promote_reviewed_procedure",
            "procedure:",
            "procedures",
            "name, trigger_context, status",
            ("Run reviewed candidate promotion", "when a trace candidate is explicitly approved", "approved"),
        ),
        (
            "episode",
            [
                "--promotion-type",
                "episode",
                "--title",
                "Reviewed live mixed corpus checkpoint",
                "--summary",
                "A reviewed episode records the live mixed retrieval shadow corpus checkpoint without raw transcript storage.",
                "--tag",
                "retrieval-eval",
                "--tag",
                "shadow-corpus",
                "--scope",
                "project:g5-candidates",
                "--importance-score",
                "0.7",
            ],
            "promote_reviewed_episode",
            "episode:",
            "episodes",
            "title, summary, status",
            (
                "Reviewed live mixed corpus checkpoint",
                "A reviewed episode records the live mixed retrieval shadow corpus checkpoint without raw transcript storage.",
                "approved",
            ),
        ),
    ],
)
def test_dogfood_trace_candidate_apply_supports_reviewed_preference_procedure_and_episode_promotions(
    tmp_path: Path,
    promotion_type: str,
    update_args: list[str],
    expected_action: str,
    expected_ref_prefix: str,
    table: str,
    columns: str,
    expected_row: tuple[str, ...],
) -> None:
    db_path = tmp_path / f"trace-candidate-{promotion_type}.db"
    initialize_database(db_path)
    _seed_trace_cluster_for_candidate_flow(db_path)
    env = {**os.environ, "PYTHONPATH": "src"}
    persist_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-persist",
            str(db_path),
            "--actor",
            "tester",
            "--reason",
            f"persist {promotion_type}",
            "--min-evidence-count",
            "2",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert persist_result.returncode == 0, persist_result.stderr
    candidate_id = json.loads(persist_result.stdout)["candidate_ids"][0]

    update_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-update",
            str(db_path),
            candidate_id,
            "--status",
            "approved",
            "--actor",
            "tester",
            "--reason",
            f"approve reviewed {promotion_type}",
            "--approval-phrase",
            "approve-g5-trace-candidate-v1",
            *update_args,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert update_result.returncode == 0, update_result.stderr
    update_payload = json.loads(update_result.stdout)
    assert update_payload["proposal_type"] == f"{promotion_type}_promotion"
    assert update_payload["promotion_ready"] is True

    apply_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "dogfood",
            "trace-candidate-apply",
            str(db_path),
            "--candidate-id",
            candidate_id,
            "--policy",
            "g5-reviewed-candidate-promotion-v1",
            "--approval-phrase",
            "apply-approved-g5-reviewed-candidates-v1",
            "--actor",
            "tester",
            "--reason",
            f"apply reviewed {promotion_type}",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    assert apply_result.returncode == 0, apply_result.stderr
    apply_payload = json.loads(apply_result.stdout)
    assert apply_payload["applied_items"][0]["action"] == expected_action
    promoted_ref = apply_payload["applied_items"][0]["promoted_ref"]
    assert promoted_ref.startswith(expected_ref_prefix)
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(f"SELECT {columns} FROM {table} WHERE id = ?", (int(promoted_ref.split(":")[1]),)).fetchone()
    assert row == expected_row
    assert "raw-secret-token" not in update_result.stdout + apply_result.stdout


def _table_counts(db_path: Path, tables: list[str]) -> dict[str, int]:
    with sqlite3.connect(db_path) as connection:
        return {table: connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in tables}
