import json
import os
import subprocess
import sys
from pathlib import Path

from agent_memory.core.curation import approve_memory, create_candidate_fact, create_candidate_procedure, create_episode
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.storage.sqlite import initialize_database



def _seed_retrieval_eval_db(db_path: Path) -> dict[str, int]:
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content=(
            "Project M1 uses agent-memory kb export for KB drafts. "
            "Run uv run pytest tests/ -q before a PR. "
            "Project Drift uses ZZ-999 branches."
        ),
        metadata={"project": "agent-memory"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="kb_export_command",
        object_ref_or_value="agent-memory kb export",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.95,
    )
    drift_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Drift",
        predicate="branch_pattern",
        object_ref_or_value="ZZ-999",
        evidence_ids=[source.id],
        scope="project:drift",
        confidence=0.95,
    )
    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local tests",
        trigger_context="Before opening a PR",
        preconditions=["Dependencies installed"],
        steps=["uv run pytest tests/ -q"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=1.0,
    )
    episode = create_episode(
        db_path=db_path,
        title="Validated retrieval evaluation fixture format",
        summary="Confirmed retrieval fixtures should be JSON-driven and deterministic.",
        source_ids=[source.id],
        tags=["retrieval", "evaluation"],
        importance_score=0.8,
        scope="project:m1",
        status="approved",
    )

    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=drift_fact.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=procedure.id)

    return {
        "fact_id": fact.id,
        "drift_fact_id": drift_fact.id,
        "procedure_id": procedure.id,
        "episode_id": episode.id,
    }



def _fixture_payload(seed_ids: dict[str, int]) -> dict[str, list[dict[str, object]]]:
    return {
        "tasks": [
            {
                "id": "project-m1-kb-export",
                "query": "What command does Project M1 use for KB export?",
                "preferred_scope": "project:m1",
                "limit": 5,
                "expected": {
                    "facts": [seed_ids["fact_id"]],
                    "procedures": [],
                    "episodes": [],
                },
                "avoid": {
                    "facts": [seed_ids["drift_fact_id"]],
                    "procedures": [],
                    "episodes": [],
                },
            },
            {
                "id": "project-m1-pr-tests",
                "query": "What should run before opening a PR for Project M1?",
                "preferred_scope": "project:m1",
                "limit": 5,
                "expected": {
                    "facts": [],
                    "procedures": [seed_ids["procedure_id"]],
                    "episodes": [],
                },
                "avoid": {
                    "facts": [seed_ids["drift_fact_id"]],
                    "procedures": [],
                    "episodes": [],
                },
            },
        ]
    }



def _write_fixture_file(tmp_path: Path, seeded_ids: dict[str, int]) -> Path:
    fixture_path = tmp_path / "retrieval-eval.json"
    fixture_path.write_text(json.dumps(_fixture_payload(seeded_ids), indent=2))
    return fixture_path



def _write_nested_fixture_directory(tmp_path: Path, seeded_ids: dict[str, int]) -> Path:
    fixtures_dir = tmp_path / "retrieval-eval-dir"
    scope_dir = fixtures_dir / "scope"
    procedure_dir = fixtures_dir / "procedure"
    scope_dir.mkdir(parents=True)
    procedure_dir.mkdir(parents=True)

    payload = _fixture_payload(seeded_ids)
    (scope_dir / "01-scope.json").write_text(json.dumps({"tasks": [payload["tasks"][0]]}, indent=2))
    (procedure_dir / "02-procedure.json").write_text(json.dumps({"tasks": [payload["tasks"][1]]}, indent=2))
    return fixtures_dir



def _write_legacy_branch_fixture_file(tmp_path: Path, seeded_ids: dict[str, int]) -> Path:
    fixture_path = tmp_path / "legacy-branch-regression.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "legacy-branch-policy",
                        "query": "What is the current approved branch policy for Project M1?",
                        "preferred_scope": "project:m1",
                        "limit": 5,
                        "expected": {
                            "facts": [seeded_ids["stale_branch_fact"]],
                            "procedures": [],
                            "episodes": [],
                        },
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    return fixture_path


def _write_missing_expected_fixture_file(tmp_path: Path) -> Path:
    fixture_path = tmp_path / "missing-expected-regression.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "missing-expected-policy",
                        "query": "This query intentionally cannot retrieve the expected fact id.",
                        "preferred_scope": "project:m1",
                        "limit": 5,
                        "expected": {"facts": [999_999_999], "procedures": [], "episodes": []},
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    return fixture_path



def _seed_checked_in_fixture_eval_db(db_path: Path) -> dict[str, int]:
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content=(
            "Project M1 uses agent-memory kb export for KB drafts. "
            "Run uv run pytest tests/ -q before a PR. "
            "Project Drift uses ZZ-999 branches. "
            "Project M1 currently uses EP-123 ticket branches. "
            "Project M1 old branch policy used LEGACY-1 branches. "
            "Retrieval evaluation rollout confirmed deterministic JSON fixtures. "
            "Project M1 latest release version is v0.1.86. "
            "An older Project M1 release note still says latest release version was v0.1.75. "
            "Project M1 currently runs uv run pytest tests/ -q before opening a PR. "
            "Project M1 legacy pre-PR procedure used npm test --legacy before opening a PR. "
            "Project M1 release docs mention release candidate checklist noise near v0.1.86. "
            "Project M1 release budget notes mention candidate tracking but do not name the authoritative version. "
            "Project M1 current release QA uses the v0.1.94 published artifact smoke and runtime QA report. "
            "Project M1 legacy release QA used the v0.1.75 manual artifact checklist."
        ),
        metadata={"project": "agent-memory"},
    )
    current_episode_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project M1 current rollout episode resolved after v0.1.90 candidate validation in May 2026.",
        metadata={"project": "agent-memory", "kind": "current-rollout"},
    )
    stale_episode_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project M1 stale rollout episode required rollback during legacy deployment in April 2026.",
        metadata={"project": "agent-memory", "kind": "stale-rollout"},
    )
    noisy_pre_pr_episode_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content=(
            "Project M1 retrospective episode discussed before opening a PR wording, "
            "but it was a meeting note and did not define the current test procedure."
        ),
        metadata={"project": "agent-memory", "kind": "noisy-pre-pr-episode"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="kb_export_command",
        object_ref_or_value="agent-memory kb export",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.95,
    )
    drift_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Drift",
        predicate="branch_pattern",
        object_ref_or_value="ZZ-999",
        evidence_ids=[source.id],
        scope="project:drift",
        confidence=0.95,
    )
    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local tests",
        trigger_context="Before opening a PR",
        preconditions=["Dependencies installed"],
        steps=["uv run pytest tests/ -q"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=1.0,
    )
    drift_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run drift project checks",
        trigger_context="Before opening a PR",
        preconditions=["Project Drift checkout"],
        steps=["Run ZZ-999 drift checks before opening a PR"],
        evidence_ids=[source.id],
        scope="project:drift",
        success_rate=0.8,
    )
    stale_pre_pr_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run legacy pre-PR checks",
        trigger_context="Before opening a PR",
        preconditions=["Legacy Project M1 checkout"],
        steps=["npm test --legacy"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=0.55,
    )
    workspace_pre_pr_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run workspace default pre-PR checks",
        trigger_context="Before opening a PR for any agent-memory workspace project",
        preconditions=["Agent-memory workspace checkout"],
        steps=["uv run pytest tests/test_cli.py -q"],
        evidence_ids=[source.id],
        scope="workspace:agent-memory",
        success_rate=0.85,
    )
    current_release_qa_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run current release QA",
        trigger_context="Before marking a Project M1 release candidate ready",
        preconditions=["v0.1.94 package artifacts are published"],
        steps=[
            "Install cafitac-agent-memory==0.1.94 from PyPI in a fresh venv",
            "Run npm wrapper smoke for @cafitac/agent-memory@0.1.94",
            "Run live Hermes runtime QA and record the report path",
        ],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=1.0,
    )
    stale_release_qa_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run legacy release QA",
        trigger_context="Before marking a Project M1 release candidate ready",
        preconditions=["Legacy v0.1.75 release checklist"],
        steps=["Run manual artifact checklist for v0.1.75"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=0.45,
    )
    release_notes_noise_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Draft release notes checklist",
        trigger_context="Before marking a Project M1 release candidate ready",
        preconditions=["Release notes draft exists"],
        steps=["Collect changelog bullets and note candidate status"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=0.62,
    )
    release_monitoring_noise_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Monitor release candidate signals",
        trigger_context="Before marking a Project M1 release candidate ready",
        preconditions=["Candidate metrics dashboard exists"],
        steps=["Check candidate tracking notes without installing published artifacts"],
        evidence_ids=[source.id],
        scope="project:m1",
        success_rate=0.58,
    )
    noisy_global_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Generic docs",
        predicate="kb_export_command",
        object_ref_or_value="agent-memory kb export archive example",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.60,
    )
    current_version_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="latest_release_version",
        object_ref_or_value="v0.1.86",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.96,
    )
    stale_version_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="latest_release_version",
        object_ref_or_value="v0.1.75",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.65,
    )
    budget_pressure_release_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1 release notes",
        predicate="budget_pressure_context",
        object_ref_or_value="release candidate checklist noise near v0.1.86",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.70,
    )
    budget_pressure_release_checklist_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1 release checklist",
        predicate="budget_pressure_context",
        object_ref_or_value="release notes checklist budget reminder without authoritative version",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.68,
    )
    current_branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="branch_pattern",
        object_ref_or_value="EP-123",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.95,
    )
    stale_branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1",
        predicate="branch_pattern",
        object_ref_or_value="LEGACY-1",
        evidence_ids=[source.id],
        scope="project:m1",
        confidence=0.70,
    )
    episode = create_episode(
        db_path=db_path,
        title="Retrieval evaluation rollout",
        summary="Confirmed retrieval fixtures should be JSON-driven and deterministic during rollout.",
        source_ids=[source.id],
        tags=["retrieval", "evaluation"],
        importance_score=0.8,
        scope="project:m1",
        status="approved",
    )
    current_rollout_episode = create_episode(
        db_path=db_path,
        title="Project M1 current v0.1.90 candidate validation rollout episode",
        summary="Current May 2026 Project M1 rollout episode resolved after v0.1.90 candidate validation.",
        source_ids=[current_episode_source.id],
        tags=["rollout", "current", "validation"],
        importance_score=1.0,
        scope="project:m1",
        status="approved",
    )
    stale_rollout_episode = create_episode(
        db_path=db_path,
        title="Project M1 stale rollout episode",
        summary="Stale April 2026 rollout required rollback during legacy deployment.",
        source_ids=[stale_episode_source.id],
        tags=["rollout", "stale", "legacy"],
        importance_score=0.1,
        scope="project:m1",
        status="approved",
    )
    noisy_pre_pr_episode = create_episode(
        db_path=db_path,
        title="Project M1 pre-PR retrospective episode",
        summary=(
            "Retrospective episode reused before opening a PR language but was only a meeting note, "
            "not the current local test procedure."
        ),
        source_ids=[noisy_pre_pr_episode_source.id],
        tags=["pre-pr", "retrospective", "noise"],
        importance_score=0.2,
        scope="project:m1",
        status="approved",
    )

    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=drift_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=noisy_global_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=current_version_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=stale_version_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=budget_pressure_release_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=budget_pressure_release_checklist_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=current_branch_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=stale_branch_fact.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=drift_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=stale_pre_pr_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=workspace_pre_pr_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=current_release_qa_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=stale_release_qa_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=release_notes_noise_procedure.id)
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=release_monitoring_noise_procedure.id)

    return {
        "project_scope_fact": fact.id,
        "drift_fact": drift_fact.id,
        "noisy_global_fact": noisy_global_fact.id,
        "current_version_fact": current_version_fact.id,
        "stale_version_fact": stale_version_fact.id,
        "budget_pressure_release_fact": budget_pressure_release_fact.id,
        "budget_pressure_release_checklist_fact": budget_pressure_release_checklist_fact.id,
        "procedure": procedure.id,
        "current_pre_pr_procedure": procedure.id,
        "drift_procedure": drift_procedure.id,
        "stale_pre_pr_procedure": stale_pre_pr_procedure.id,
        "workspace_pre_pr_procedure": workspace_pre_pr_procedure.id,
        "current_release_qa_procedure": current_release_qa_procedure.id,
        "stale_release_qa_procedure": stale_release_qa_procedure.id,
        "release_notes_noise_procedure": release_notes_noise_procedure.id,
        "release_monitoring_noise_procedure": release_monitoring_noise_procedure.id,
        "current_branch_fact": current_branch_fact.id,
        "stale_branch_fact": stale_branch_fact.id,
        "episode": episode.id,
        "current_rollout_episode": current_rollout_episode.id,
        "stale_rollout_episode": stale_rollout_episode.id,
        "noisy_pre_pr_episode": noisy_pre_pr_episode.id,
    }



def _checked_in_fixture_dir() -> Path:
    return Path(__file__).resolve().parent / "fixtures" / "retrieval_eval"



def test_evaluate_retrieval_fixtures_reports_expected_hits_and_reports_drift(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path)

    assert result.fixture_paths == [str(fixture_path)]
    assert result.summary.total_tasks == 2
    assert result.summary.passed_tasks == 2
    assert result.summary.failed_tasks == 0
    assert result.summary.tasks_with_missing_expected == 0
    assert result.summary.tasks_with_avoid_hits == 0
    assert result.summary.total_expected_hits == 2
    assert result.summary.total_missing_expected == 0
    assert result.summary.total_avoid_hits == 0
    assert result.summary.by_memory_type["facts"].total_tasks == 1
    assert result.summary.by_memory_type["facts"].passed_tasks == 1
    assert result.summary.by_memory_type["facts"].failed_tasks == 0
    assert result.summary.by_memory_type["facts"].total_expected_hits == 1
    assert result.summary.by_memory_type["facts"].total_missing_expected == 0
    assert result.summary.by_memory_type["facts"].total_avoid_hits == 0
    assert result.summary.by_memory_type["facts"].tasks_with_missing_expected == 0
    assert result.summary.by_memory_type["facts"].tasks_with_avoid_hits == 0
    assert result.summary.by_memory_type["procedures"].total_tasks == 1
    assert result.summary.by_memory_type["procedures"].passed_tasks == 1
    assert result.summary.by_memory_type["procedures"].failed_tasks == 0
    assert result.summary.by_memory_type["procedures"].total_expected_hits == 1
    assert result.summary.by_memory_type["procedures"].total_missing_expected == 0
    assert result.summary.by_memory_type["procedures"].total_avoid_hits == 0
    assert result.summary.by_memory_type["episodes"].total_tasks == 0
    assert result.summary.by_memory_type["episodes"].passed_tasks == 0
    assert result.summary.by_memory_type["episodes"].failed_tasks == 0
    assert result.summary.by_memory_type["episodes"].total_expected_hits == 0
    assert result.summary.by_primary_task_type["facts"].total_tasks == 1
    assert result.summary.by_primary_task_type["facts"].passed_tasks == 1
    assert result.summary.by_primary_task_type["facts"].failed_tasks == 0
    assert result.summary.by_primary_task_type["procedures"].total_tasks == 1
    assert result.summary.by_primary_task_type["procedures"].passed_tasks == 1
    assert result.summary.by_primary_task_type["procedures"].failed_tasks == 0
    assert result.summary.by_primary_task_type["episodes"].total_tasks == 0
    assert result.summary.by_primary_task_type["episodes"].passed_tasks == 0
    assert result.summary.by_primary_task_type["episodes"].failed_tasks == 0
    assert [task.task_id for task in result.results] == [
        "project-m1-kb-export",
        "project-m1-pr-tests",
    ]

    first_task = result.results[0]
    assert first_task.expected_hits == {
        "facts": [seeded_ids["fact_id"]],
        "procedures": [],
        "episodes": [],
    }
    assert first_task.missing_expected == {
        "facts": [],
        "procedures": [],
        "episodes": [],
    }
    assert first_task.avoid_hits == {
        "facts": [],
        "procedures": [],
        "episodes": [],
    }
    assert first_task.pass_ is True
    assert first_task.retrieved_ids["facts"][0] == seeded_ids["fact_id"]



def test_evaluate_retrieval_fixture_directory_recurses_and_sorts_paths(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-dir.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixtures_dir = _write_nested_fixture_directory(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixtures_dir)

    assert result.fixture_paths == [
        str(fixtures_dir / "procedure" / "02-procedure.json"),
        str(fixtures_dir / "scope" / "01-scope.json"),
    ]
    assert [task.task_id for task in result.results] == [
        "project-m1-pr-tests",
        "project-m1-kb-export",
    ]
    assert result.summary.total_tasks == 2



def test_evaluate_retrieval_fixtures_does_not_mutate_retrieval_counters(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures
    from agent_memory.storage.sqlite import connect

    db_path = tmp_path / "retrieval-eval-readonly.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)

    evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path)

    with connect(db_path) as connection:
        fact_row = connection.execute(
            "SELECT retrieval_count, reinforcement_count, last_accessed_at FROM facts WHERE id = ?",
            (seeded_ids["fact_id"],),
        ).fetchone()
        procedure_row = connection.execute(
            "SELECT retrieval_count, reinforcement_count, last_accessed_at FROM procedures WHERE id = ?",
            (seeded_ids["procedure_id"],),
        ).fetchone()

    assert dict(fact_row) == {"retrieval_count": 0, "reinforcement_count": 0.0, "last_accessed_at": None}
    assert dict(procedure_row) == {"retrieval_count": 0, "reinforcement_count": 0.0, "last_accessed_at": None}



def test_checked_in_retrieval_eval_examples_validate_as_fixture_models() -> None:
    from agent_memory.core.models import RetrievalEvalFixture

    fixture_dir = _checked_in_fixture_dir()
    fixture_paths = sorted(fixture_dir.rglob("*.json"))

    assert len(fixture_paths) >= 25
    task_ids: set[str] = set()
    live_compatible_task_count = 0
    for fixture_path in fixture_paths:
        payload = json.loads(fixture_path.read_text())
        fixture = RetrievalEvalFixture.model_validate(payload)
        assert fixture.tasks, fixture_path
        for task in fixture.tasks:
            task_ids.add(task.id)
            if task.preferred_scope and (task.expected.facts or task.expected.procedures or task.expected.episodes):
                live_compatible_task_count += 1

    assert live_compatible_task_count >= 50
    assert {
        "release-version-source-noise-guardrail",
        "release-qa-procedure-source-noise-guardrail",
        "episode-current-rollout-source-noise-guardrail",
        "kb-export-procedure-cross-surface-guardrail",
    } <= task_ids



def test_checked_in_retrieval_eval_examples_use_symbolic_references() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "basic.json").read_text())

    assert payload["references"]["project_scope_fact"]["memory_type"] == "fact"
    assert payload["tasks"][0]["expected"]["facts"] == ["project_scope_fact"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["drift_fact"]



def test_checked_in_retrieval_eval_examples_include_canonical_live_compatible_fixture_slice() -> None:
    fixture_dir = _checked_in_fixture_dir()
    fixture_expectations = [
        (
            fixture_dir / "scope" / "project-scope.json",
            "project_scope_fact",
            "fact",
            "project:m1",
            "project-scope-fact",
            "facts",
            "drift_fact",
        ),
        (
            fixture_dir / "procedure" / "pre-pr-tests.json",
            "project_scope_procedure",
            "procedure",
            "project:m1",
            "project-scope-procedure",
            "procedures",
            "drift_fact",
        ),
        (
            fixture_dir / "episode" / "review-history.json",
            "rollout_episode",
            "episode",
            "project:m1",
            "episode-recall",
            "episodes",
            "drift_fact",
        ),
        (
            fixture_dir / "drift" / "cross-scope-drift.json",
            "current_branch_fact",
            "fact",
            "project:m1",
            "cross-scope-drift-check",
            "facts",
            "drift_fact",
        ),
        (
            fixture_dir / "staleness" / "current-vs-stale.json",
            "current_branch_fact",
            "fact",
            "project:m1",
            "current-vs-stale-fact",
            "facts",
            "stale_branch_fact",
        ),
    ]

    for fixture_path, expected_ref, memory_type, scope, task_id, expected_type, avoid_ref in fixture_expectations:
        payload = json.loads(fixture_path.read_text())
        task = payload["tasks"][0]
        assert payload["references"][expected_ref]["memory_type"] == memory_type
        assert payload["references"][expected_ref]["scope"] == scope
        assert task["id"] == task_id
        assert task["preferred_scope"] == scope
        assert task["expected"][expected_type] == [expected_ref]
        assert task["avoid"]["facts"] == [avoid_ref]



def test_checked_in_retrieval_eval_examples_include_branch_only_staleness_case() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "staleness" / "branch-only-current.json").read_text())

    assert payload["references"]["current_branch_fact"]["object_ref_or_value"] == "EP-123"
    assert payload["references"]["stale_branch_fact"]["object_ref_or_value"] == "LEGACY-1"
    assert payload["tasks"][0]["id"] == "branch-only-current-policy"
    assert payload["tasks"][0]["expected"]["facts"] == ["current_branch_fact"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["stale_branch_fact"]
    assert payload["tasks"][0]["rationale"] == "Use a branch-only query that isolates stale conflicting branch facts."
    assert payload["tasks"][0]["notes"] == [
        "The current retrieval path should surface only the active branch pattern.",
        "The lexical baseline tends to keep the stale branch fact in the surfaced set.",
    ]



def test_checked_in_retrieval_eval_examples_include_procedure_with_stale_fact_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "pre-pr-stale-fact-guardrail.json").read_text())

    assert payload["references"]["project_scope_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["stale_branch_fact"]["object_ref_or_value"] == "LEGACY-1"
    assert payload["tasks"][0]["id"] == "project-scope-procedure-stale-fact-guardrail"
    assert payload["tasks"][0]["expected"]["procedures"] == ["project_scope_procedure"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["stale_branch_fact"]
    assert payload["tasks"][0]["rationale"] == "Keep stale branch facts out of procedure-oriented pre-PR guidance."
    assert payload["tasks"][0]["notes"] == [
        "The retrieval target is still the project-scoped pre-PR procedure.",
        "A lexical baseline can keep the legacy branch fact in surfaced facts even when the procedure itself matches.",
    ]



def test_checked_in_retrieval_eval_examples_include_episode_with_stale_fact_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "episode" / "rollout-stale-fact-guardrail.json").read_text())

    assert payload["references"]["rollout_episode"]["memory_type"] == "episode"
    assert payload["references"]["stale_branch_fact"]["object_ref_or_value"] == "LEGACY-1"
    assert payload["tasks"][0]["id"] == "episode-recall-stale-fact-guardrail"
    assert payload["tasks"][0]["expected"]["episodes"] == ["rollout_episode"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["stale_branch_fact"]
    assert payload["tasks"][0]["rationale"] == "Keep stale branch facts out of rollout-history recall tasks."
    assert payload["tasks"][0]["notes"] == [
        "The retrieval target is the rollout episode, not branch-policy facts.",
        "A lexical baseline can keep the legacy branch fact in surfaced facts when the query mixes rollout history with branch language.",
    ]



def test_checked_in_retrieval_eval_examples_include_episode_drift_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "episode" / "same-scope-episode-drift-guardrail.json").read_text())

    assert payload["references"]["current_rollout_episode"]["memory_type"] == "episode"
    assert payload["references"]["current_rollout_episode"]["scope"] == "project:m1"
    assert payload["references"]["stale_rollout_episode"]["memory_type"] == "episode"
    assert payload["references"]["stale_rollout_episode"]["scope"] == "project:m1"
    assert payload["tasks"][0]["id"] == "episode-recall-same-scope-drift-guardrail"
    assert payload["tasks"][0]["expected"]["episodes"] == ["current_rollout_episode"]
    assert payload["tasks"][0]["avoid"]["episodes"] == ["stale_rollout_episode"]
    assert payload["tasks"][0]["limit"] == 1
    assert payload["tasks"][0]["rationale"] == "Keep current rollout episodes ahead of stale same-scope rollout history under tight prompt budgets."



def test_checked_in_retrieval_eval_examples_include_source_global_stale_source_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "staleness" / "source-global-stale-source-guardrail.json").read_text())

    assert payload["references"]["current_branch_fact"]["object_ref_or_value"] == "EP-123"
    assert payload["references"]["stale_branch_fact"]["object_ref_or_value"] == "LEGACY-1"
    assert payload["tasks"][0]["id"] == "source-global-stale-source-guardrail"
    assert payload["tasks"][0]["expected"]["facts"] == ["current_branch_fact"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["stale_branch_fact"]
    assert payload["tasks"][0]["rationale"] == "Lock in a checked-in source-global regression case where shared source text can resurface stale branch facts."
    assert payload["tasks"][0]["notes"] == [
        "Current retrieval should keep only the active branch fact surfaced.",
        "A source-global baseline can resurface the stale branch fact because all approved memories share one source note in the seeded fixture DB.",
    ]



def test_checked_in_retrieval_eval_examples_include_noisy_global_fact_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "noise" / "irrelevant-global-fact-guardrail.json").read_text())

    assert payload["references"]["project_scope_kb_export"]["memory_type"] == "fact"
    assert payload["references"]["project_scope_kb_export"]["scope"] == "project:m1"
    assert payload["references"]["global_noise_kb_export"]["scope"] == "global"
    assert payload["references"]["global_noise_kb_export"]["object_ref_or_value"] == "agent-memory kb export archive example"
    assert payload["tasks"][0]["id"] == "project-scope-fact-noisy-global-guardrail"
    assert payload["tasks"][0]["expected"]["facts"] == ["project_scope_kb_export"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["global_noise_kb_export"]



def test_checked_in_retrieval_eval_examples_include_noisy_episode_procedure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "noise" / "irrelevant-episode-procedure-guardrail.json").read_text())

    assert payload["references"]["current_pre_pr_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["current_pre_pr_procedure"]["scope"] == "project:m1"
    assert payload["references"]["noisy_pre_pr_episode"]["memory_type"] == "episode"
    assert payload["references"]["noisy_pre_pr_episode"]["scope"] == "project:m1"
    assert payload["tasks"][0]["id"] == "project-scope-procedure-noisy-episode-guardrail"
    assert payload["tasks"][0]["expected"]["procedures"] == ["current_pre_pr_procedure"]
    assert payload["tasks"][0]["avoid"]["episodes"] == ["noisy_pre_pr_episode"]
    assert payload["tasks"][0]["preferred_scope"] == "project:m1"
    assert payload["tasks"][0]["limit"] == 1
    assert payload["tasks"][0]["rationale"] == "Keep procedure-oriented pre-PR guidance ahead of same-scope episodic noise under tight prompt budgets."



def test_checked_in_retrieval_eval_examples_include_prompt_budget_pressure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "noise" / "prompt-budget-pressure-guardrail.json").read_text())

    assert payload["references"]["current_version_fact"]["memory_type"] == "fact"
    assert payload["references"]["current_version_fact"]["scope"] == "project:m1"
    assert payload["references"]["budget_pressure_release_fact"]["scope"] == "project:m1"
    assert payload["references"]["budget_pressure_release_checklist_fact"]["scope"] == "project:m1"
    assert payload["tasks"][0]["id"] == "project-scope-release-version-budget-pressure"
    assert payload["tasks"][0]["expected"]["facts"] == ["current_version_fact"]
    assert payload["tasks"][0]["avoid"]["facts"] == [
        "stale_version_fact",
        "budget_pressure_release_fact",
        "budget_pressure_release_checklist_fact",
    ]
    assert payload["tasks"][0]["preferred_scope"] == "project:m1"
    assert payload["tasks"][0]["limit"] == 1



def test_checked_in_retrieval_eval_examples_include_conflicting_fact_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "conflict" / "same-slot-fact-guardrail.json").read_text())

    assert payload["references"]["current_version_fact"]["memory_type"] == "fact"
    assert payload["references"]["current_version_fact"]["scope"] == "project:m1"
    assert payload["references"]["stale_version_fact"]["scope"] == "project:m1"
    assert payload["references"]["stale_version_fact"]["predicate"] == "latest_release_version"
    assert payload["tasks"][0]["id"] == "same-slot-current-release-version"
    assert payload["tasks"][0]["expected"]["facts"] == ["current_version_fact"]
    assert payload["tasks"][0]["avoid"]["facts"] == ["stale_version_fact"]
    assert payload["tasks"][0]["rationale"] == "Keep stale same-slot facts hidden behind the current fact for a direct release-version query."



def test_checked_in_retrieval_eval_examples_include_stale_procedure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "same-scope-stale-procedure-guardrail.json").read_text())

    assert payload["references"]["current_pre_pr_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["current_pre_pr_procedure"]["scope"] == "project:m1"
    assert payload["references"]["stale_pre_pr_procedure"]["scope"] == "project:m1"
    assert payload["references"]["stale_pre_pr_procedure"]["name"] == "Run legacy pre-PR checks"
    assert payload["tasks"][0]["id"] == "same-scope-current-pre-pr-procedure"
    assert payload["tasks"][0]["expected"]["procedures"] == ["current_pre_pr_procedure"]
    assert payload["tasks"][0]["avoid"]["procedures"] == ["stale_pre_pr_procedure"]
    assert payload["tasks"][0]["rationale"] == (
        "Keep stale same-scope procedures hidden behind the current pre-PR procedure."
    )



def test_checked_in_retrieval_eval_examples_include_cross_scope_procedure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "cross-scope-procedure-guardrail.json").read_text())

    assert payload["references"]["project_scope_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["drift_scope_procedure"]["scope"] == "project:drift"
    assert payload["tasks"][0]["id"] == "project-scope-procedure-cross-scope-guardrail"
    assert payload["tasks"][0]["expected"]["procedures"] == ["project_scope_procedure"]
    assert payload["tasks"][0]["avoid"]["procedures"] == ["drift_scope_procedure"]
    assert payload["tasks"][0]["rationale"] == "Keep same-wording cross-scope procedure guidance out of Project M1 pre-PR queries."
    assert payload["tasks"][0]["notes"] == [
        "The current retrieval path should use the preferred Project M1 scope for procedure guidance.",
        "A source-global baseline can resurface same-source Project Drift procedure guidance when provenance wording overlaps.",
    ]


def test_checked_in_retrieval_eval_examples_include_scope_adjacent_procedure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "scope-adjacent-procedure-guardrail.json").read_text())

    assert payload["references"]["current_pre_pr_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["current_pre_pr_procedure"]["scope"] == "project:m1"
    assert payload["references"]["workspace_pre_pr_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["workspace_pre_pr_procedure"]["scope"] == "workspace:agent-memory"
    assert payload["tasks"][0]["id"] == "project-scope-procedure-scope-adjacent-guardrail"
    assert payload["tasks"][0]["expected"]["procedures"] == ["current_pre_pr_procedure"]
    assert payload["tasks"][0]["avoid"]["procedures"] == ["workspace_pre_pr_procedure"]
    assert payload["tasks"][0]["preferred_scope"] == "project:m1"
    assert payload["tasks"][0]["limit"] == 1
    assert payload["tasks"][0]["rationale"] == (
        "Keep project-specific pre-PR procedure guidance ahead of scope-adjacent workspace defaults."
    )



def test_checked_in_retrieval_eval_examples_include_same_scope_procedure_recency_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "same-scope-procedure-recency-guardrail.json").read_text())

    assert payload["references"]["current_release_qa_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["current_release_qa_procedure"]["scope"] == "project:m1"
    assert payload["references"]["stale_release_qa_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["stale_release_qa_procedure"]["scope"] == "project:m1"
    assert payload["references"]["stale_release_qa_procedure"]["name"] == "Run legacy release QA"
    assert payload["tasks"][0]["id"] == "same-scope-current-release-qa-procedure"
    assert payload["tasks"][0]["expected"]["procedures"] == ["current_release_qa_procedure"]
    assert payload["tasks"][0]["avoid"]["procedures"] == ["stale_release_qa_procedure"]
    assert payload["tasks"][0]["preferred_scope"] == "project:m1"
    assert payload["tasks"][0]["limit"] == 1
    assert payload["tasks"][0]["rationale"] == (
        "Keep the current same-scope release QA procedure ahead of stale legacy release QA guidance."
    )



def test_checked_in_retrieval_eval_examples_include_procedure_prompt_budget_pressure_guardrail() -> None:
    fixture_dir = _checked_in_fixture_dir()
    payload = json.loads((fixture_dir / "procedure" / "procedure-prompt-budget-pressure-guardrail.json").read_text())

    assert payload["references"]["current_release_qa_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["current_release_qa_procedure"]["scope"] == "project:m1"
    assert payload["references"]["release_notes_noise_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["release_notes_noise_procedure"]["scope"] == "project:m1"
    assert payload["references"]["release_monitoring_noise_procedure"]["memory_type"] == "procedure"
    assert payload["references"]["release_monitoring_noise_procedure"]["scope"] == "project:m1"
    assert payload["tasks"][0]["id"] == "project-scope-procedure-release-qa-budget-pressure"
    assert payload["tasks"][0]["expected"]["procedures"] == ["current_release_qa_procedure"]
    assert payload["tasks"][0]["avoid"]["procedures"] == [
        "stale_release_qa_procedure",
        "release_notes_noise_procedure",
        "release_monitoring_noise_procedure",
    ]
    assert payload["tasks"][0]["preferred_scope"] == "project:m1"
    assert payload["tasks"][0]["limit"] == 1
    assert payload["tasks"][0]["rationale"] == (
        "Keep authoritative release QA procedure guidance ahead of stale and same-scope procedural noise under a tight prompt budget."
    )



def test_cli_eval_retrieval_accepts_recursive_fixture_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-dir.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixtures_dir = _write_nested_fixture_directory(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixtures_dir),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["fixture_paths"] == [
        str(fixtures_dir / "procedure" / "02-procedure.json"),
        str(fixtures_dir / "scope" / "01-scope.json"),
    ]
    assert [task["task_id"] for task in payload["results"]] == [
        "project-m1-pr-tests",
        "project-m1-kb-export",
    ]



def test_cli_eval_retrieval_outputs_json_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["fixture_paths"] == [str(fixture_path)]
    assert payload["summary"]["total_tasks"] == 2
    assert payload["summary"]["tasks_with_missing_expected"] == 0
    assert payload["summary"]["tasks_with_avoid_hits"] == 0
    assert payload["summary"]["total_expected_hits"] == 2
    assert payload["summary"]["by_memory_type"] == {
        "facts": {
            "total_tasks": 1,
            "passed_tasks": 1,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 1,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
        "procedures": {
            "total_tasks": 1,
            "passed_tasks": 1,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 1,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
        "episodes": {
            "total_tasks": 0,
            "passed_tasks": 0,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 0,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
    }
    assert payload["summary"]["by_primary_task_type"] == {
        "facts": {
            "total_tasks": 1,
            "passed_tasks": 1,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 1,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
        "procedures": {
            "total_tasks": 1,
            "passed_tasks": 1,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 1,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
        "episodes": {
            "total_tasks": 0,
            "passed_tasks": 0,
            "failed_tasks": 0,
            "tasks_with_missing_expected": 0,
            "tasks_with_avoid_hits": 0,
            "total_expected_hits": 0,
            "total_missing_expected": 0,
            "total_avoid_hits": 0,
        },
    }
    assert payload["results"][0]["task_id"] == "project-m1-kb-export"
    assert payload["results"][0]["pass"] is True
    assert payload["advisory_report"] == {
        "severity": "ok",
        "summary": "No retrieval advisory actions.",
        "current_failure_task_ids": [],
        "baseline_weak_spot_task_ids": [],
        "current_regression_task_ids": [],
        "recommended_actions": [],
        "baseline_mode": None,
    }




def test_render_retrieval_eval_text_report_summarizes_passes_and_type_rollups(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures, render_retrieval_eval_text_report

    db_path = tmp_path / "retrieval-eval-text.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical")
    report = render_retrieval_eval_text_report(result)

    assert "Retrieval evaluation: 2/2 tasks passed" in report
    assert "current: failures=0 missing=0 avoid=0 expected_hits=2" in report
    assert "baseline lexical: 2/2 tasks passed" in report
    assert "delta: pass_count=+0 expected_hits=+0 missing=+0 avoid=+0" in report
    assert "by primary task type:" in report
    assert "facts: 1/1 passed, missing=0, avoid=0" in report
    assert "procedures: 1/1 passed, missing=0, avoid=0" in report
    assert "failed tasks: none" in report


def test_render_retrieval_eval_text_report_shows_failed_task_details(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures, render_retrieval_eval_text_report

    db_path = tmp_path / "retrieval-eval-text-failure.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-failure.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"] = [payload["tasks"][0]]
    payload["tasks"][0]["expected"]["facts"] = [seeded_ids["drift_fact_id"]]
    payload["tasks"][0]["avoid"]["facts"] = [seeded_ids["fact_id"]]
    fixture_path.write_text(json.dumps(payload, indent=2))

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical")
    report = render_retrieval_eval_text_report(result)

    assert "failed tasks:" in report
    assert "  - project-m1-kb-export" in report
    assert "    missing: facts=[2]" in report
    assert "    avoid: facts=[1]" in report
    assert "    baseline: fail" in report
    assert "    query: What command does Project M1 use for KB export?" in report
    assert "    retrieved details:" in report
    assert "      fact #1 [scope=project:m1 status=approved] Project M1 kb_export_command agent-memory kb export" in report
    assert "        policy: mode=direct trust=high hidden_alternatives=no reasons=top_ranked_memory,no_hidden_alternatives_detected" in report
    assert "    expected details:" in report
    assert "      fact #2 [scope=project:drift status=approved] Project Drift branch_pattern ZZ-999" in report
    assert "    avoid-hit details:" in report
    assert "      fact #1 [scope=project:m1 status=approved] Project M1 kb_export_command agent-memory kb export" in report


def test_render_retrieval_eval_text_report_shows_baseline_weak_spots(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures, render_retrieval_eval_text_report

    db_path = tmp_path / "retrieval-eval-text-baseline-weak-spots.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical-global")
    report = render_retrieval_eval_text_report(result)

    assert "baseline weak spots:" in report
    assert "  - branch-only-current-policy" in report
    assert "    baseline missing: none" in report
    assert "    baseline avoid: facts=[" in report
    assert "current regressions vs baseline: none" in report



def test_evaluate_retrieval_fixtures_builds_advisory_report_for_failures_and_baseline_weak_spots(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures, render_retrieval_eval_text_report

    db_path = tmp_path / "retrieval-eval-advisory-report.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-advisory-report.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"] = [payload["tasks"][0]]
    payload["tasks"][0]["expected"]["facts"] = [seeded_ids["drift_fact_id"]]
    payload["tasks"][0]["avoid"]["facts"] = [seeded_ids["fact_id"]]
    fixture_path.write_text(json.dumps(payload, indent=2))

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical")

    assert result.advisory_report.severity == "high"
    assert result.advisory_report.summary == "1 current task failed; 1 task has missing expected memories; 1 task has avoid-hit memories"
    assert result.advisory_report.current_failure_task_ids == ["project-m1-kb-export"]
    assert result.advisory_report.baseline_weak_spot_task_ids == []
    assert result.advisory_report.current_regression_task_ids == []
    assert result.advisory_report.recommended_actions == [
        "Inspect failed task details and compare retrieved_details against expected_details.",
        "Seed or approve missing expected memories, or tighten fixture expectations if they are stale.",
        "Review avoid-hit details for stale, cross-scope, or conflicting approved memories.",
    ]
    assert result.advisory_report.baseline_mode == "lexical"

    report = render_retrieval_eval_text_report(result)
    assert "advisory report: high - 1 current task failed; 1 task has missing expected memories; 1 task has avoid-hit memories" in report
    assert "recommended actions:" in report
    assert "  - Inspect failed task details and compare retrieved_details against expected_details." in report



def test_evaluate_retrieval_fixtures_advisory_report_summarizes_baseline_weak_spots(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-advisory-report.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical-global")

    assert result.advisory_report.severity == "medium"
    assert result.advisory_report.summary == "1 baseline weak spot found against lexical-global"
    assert result.advisory_report.current_failure_task_ids == []
    assert result.advisory_report.baseline_weak_spot_task_ids == ["branch-only-current-policy"]
    assert result.advisory_report.current_regression_task_ids == []
    assert result.advisory_report.recommended_actions == [
        "Use baseline weak spots as coverage wins: keep the fixture checked in and watch for future regressions.",
    ]



def test_evaluate_retrieval_fixtures_emits_triage_detail_contract(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-triage-contract.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-triage-contract.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"] = [payload["tasks"][0]]
    payload["tasks"][0]["expected"]["facts"] = [seeded_ids["drift_fact_id"]]
    payload["tasks"][0]["avoid"]["facts"] = [seeded_ids["fact_id"]]
    fixture_path.write_text(json.dumps(payload, indent=2))

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path)
    task = result.results[0]

    assert task.retrieved_details["facts"][0].id == seeded_ids["fact_id"]
    assert task.retrieved_details["facts"][0].snippet == "Project M1 kb_export_command agent-memory kb export"
    assert task.retrieved_details["facts"][0].policy_signals == [
        "mode=direct",
        "trust=high",
        "hidden_alternatives=no",
        "reasons=top_ranked_memory,no_hidden_alternatives_detected",
    ]
    assert task.expected_details["facts"][0].id == seeded_ids["drift_fact_id"]
    assert task.expected_details["facts"][0].snippet == "Project Drift branch_pattern ZZ-999"
    assert task.avoid_hit_details["facts"][0].id == seeded_ids["fact_id"]


def test_cli_eval_retrieval_text_format_outputs_human_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-text.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
            "--format",
            "text",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Retrieval evaluation: 2/2 tasks passed")
    assert "baseline lexical: 2/2 tasks passed" in result.stdout
    assert "by primary task type:" in result.stdout
    assert not result.stdout.lstrip().startswith("{")



def test_cli_eval_retrieval_failure_prints_advisory_summary(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-failure-summary.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-cli-failure-summary.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"][0]["expected"] = {"facts": [seeded_ids["drift_fact_id"]], "procedures": [], "episodes": []}
    payload["tasks"][0]["avoid"] = {"facts": [seeded_ids["fact_id"]], "procedures": [], "episodes": []}
    fixture_path.write_text(json.dumps(payload, indent=2))
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--fail-on-regression",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert result.stdout == ""
    assert "retrieval eval failed: regression detected for task(s): project-m1-kb-export" in result.stderr
    assert "advisory report: high - 1 current task failed" in result.stderr
    assert "recommended actions:" in result.stderr
    assert "Inspect failed task details" in result.stderr



def test_evaluate_retrieval_fixtures_preserves_task_rationale_and_notes(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-notes.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-notes.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"][0]["rationale"] = "Prefer the project-scoped KB export fact instead of unrelated branch policy facts."
    payload["tasks"][0]["notes"] = [
        "This is a direct fact lookup.",
        "Cross-scope drift should stay out of surfaced results.",
    ]
    fixture_path.write_text(json.dumps(payload, indent=2))

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path)

    assert result.results[0].rationale == (
        "Prefer the project-scoped KB export fact instead of unrelated branch policy facts."
    )
    assert result.results[0].notes == [
        "This is a direct fact lookup.",
        "Cross-scope drift should stay out of surfaced results.",
    ]



def test_cli_eval_retrieval_emits_task_rationale_and_notes(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-notes-cli.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = tmp_path / "retrieval-eval-notes-cli.json"
    payload = _fixture_payload(seeded_ids)
    payload["tasks"][0]["rationale"] = "Prefer the project-scoped KB export fact instead of unrelated branch policy facts."
    payload["tasks"][0]["notes"] = [
        "This is a direct fact lookup.",
        "Cross-scope drift should stay out of surfaced results.",
    ]
    fixture_path.write_text(json.dumps(payload, indent=2))
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["results"][0]["rationale"] == (
        "Prefer the project-scoped KB export fact instead of unrelated branch policy facts."
    )
    assert payload["results"][0]["notes"] == [
        "This is a direct fact lookup.",
        "Cross-scope drift should stay out of surfaced results.",
    ]



def test_evaluate_retrieval_fixtures_includes_lexical_baseline_when_requested(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical")

    assert result.baseline_mode == "lexical"
    assert result.baseline_summary is not None
    assert result.baseline_summary.total_tasks == 2
    assert result.baseline_summary.passed_tasks == 2
    assert result.baseline_summary.failed_tasks == 0
    assert result.baseline_summary.by_memory_type["facts"].total_tasks == 1
    assert result.baseline_summary.by_memory_type["facts"].passed_tasks == 1
    assert result.baseline_summary.by_memory_type["facts"].failed_tasks == 0
    assert result.baseline_summary.by_memory_type["facts"].total_expected_hits == 1
    assert result.baseline_summary.by_memory_type["procedures"].total_tasks == 1
    assert result.baseline_summary.by_memory_type["procedures"].passed_tasks == 1
    assert result.baseline_summary.by_memory_type["procedures"].failed_tasks == 0
    assert result.baseline_summary.by_memory_type["procedures"].total_expected_hits == 1
    assert result.baseline_summary.by_memory_type["episodes"].total_tasks == 0
    assert result.baseline_summary.by_memory_type["episodes"].passed_tasks == 0
    assert result.baseline_summary.by_memory_type["episodes"].failed_tasks == 0
    assert result.baseline_summary.by_memory_type["episodes"].total_expected_hits == 0
    assert result.baseline_summary.by_primary_task_type["facts"].total_tasks == 1
    assert result.baseline_summary.by_primary_task_type["facts"].passed_tasks == 1
    assert result.baseline_summary.by_primary_task_type["facts"].failed_tasks == 0
    assert result.baseline_summary.by_primary_task_type["procedures"].total_tasks == 1
    assert result.baseline_summary.by_primary_task_type["procedures"].passed_tasks == 1
    assert result.baseline_summary.by_primary_task_type["procedures"].failed_tasks == 0
    assert result.baseline_summary.by_primary_task_type["episodes"].total_tasks == 0
    assert result.baseline_summary.by_primary_task_type["episodes"].passed_tasks == 0
    assert result.baseline_summary.by_primary_task_type["episodes"].failed_tasks == 0
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.mode == "lexical"
    assert result.results[0].baseline.pass_ is True
    assert result.results[0].baseline.retrieved_ids["facts"] == [seeded_ids["fact_id"]]
    assert result.results[0].delta is not None
    assert result.results[0].delta.expected_hit_delta == 0
    assert result.results[0].delta.missing_expected_delta == 0
    assert result.results[0].delta.avoid_hit_delta == 0
    assert result.results[0].delta.pass_changed is False
    assert result.delta_summary is not None
    assert result.delta_summary.total_expected_hit_delta == 0
    assert result.delta_summary.total_missing_expected_delta == 0
    assert result.delta_summary.total_avoid_hit_delta == 0
    assert result.delta_summary.total_pass_count_delta == 0
    assert result.delta_summary.model_dump()["by_memory_type"] == {
        "facts": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "procedures": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "episodes": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
    }



def test_evaluate_retrieval_fixtures_includes_lexical_global_baseline_when_requested(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-global.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="lexical-global")

    assert result.baseline_mode == "lexical-global"
    assert result.baseline_summary is not None
    assert result.baseline_summary.total_tasks == 1
    assert result.baseline_summary.passed_tasks == 0
    assert result.baseline_summary.failed_tasks == 1
    assert result.baseline_summary.tasks_with_avoid_hits == 1
    assert result.baseline_summary.by_primary_task_type["facts"].total_tasks == 1
    assert result.baseline_summary.by_primary_task_type["facts"].failed_tasks == 1
    assert result.results[0].task_id == "branch-only-current-policy"
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.mode == "lexical-global"
    assert result.results[0].baseline.pass_ is False
    assert len(result.results[0].baseline.avoid_hits["facts"]) == 1
    assert result.results[0].delta is not None
    assert result.results[0].delta.avoid_hit_delta == -1
    assert result.results[0].delta.pass_changed is True
    assert result.delta_summary is not None
    assert result.delta_summary.total_avoid_hit_delta == -1
    assert result.delta_summary.total_pass_count_delta == 1
    assert result.delta_summary.by_primary_task_type["facts"].tasks_with_pass_change == 1



def test_checked_in_retrieval_fixture_examples_run_against_seeded_db(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-checked-in.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixtures_dir = _checked_in_fixture_dir()

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixtures_dir, baseline_mode="lexical")

    assert result.summary.total_tasks == 75
    assert result.summary.passed_tasks + result.summary.failed_tasks == 75
    assert result.summary.passed_tasks == 75
    assert result.summary.failed_tasks == 0
    assert result.summary.by_memory_type["facts"].total_tasks == 26
    assert result.summary.by_memory_type["procedures"].total_tasks == 31
    assert result.summary.by_memory_type["episodes"].total_tasks == 18
    assert result.summary.by_primary_task_type["facts"].total_tasks == 26
    assert result.summary.by_primary_task_type["procedures"].total_tasks == 31
    assert result.summary.by_primary_task_type["episodes"].total_tasks == 18
    assert result.baseline_summary is not None
    assert result.baseline_summary.total_tasks == 75
    assert result.baseline_summary.passed_tasks + result.baseline_summary.failed_tasks == 75
    assert result.baseline_summary.passed_tasks == 59
    assert result.baseline_summary.tasks_with_avoid_hits == 16
    assert result.baseline_summary.by_memory_type["facts"].total_tasks == 30
    assert result.baseline_summary.by_memory_type["procedures"].total_tasks == 31
    assert result.baseline_summary.by_memory_type["episodes"].total_tasks == 19
    assert result.baseline_summary.by_primary_task_type["facts"].total_tasks == 26
    assert result.baseline_summary.by_primary_task_type["procedures"].total_tasks == 31
    assert result.baseline_summary.by_primary_task_type["episodes"].total_tasks == 18
    assert result.delta_summary is not None
    assert result.delta_summary.total_pass_count_delta >= 0
    assert result.delta_summary.total_avoid_hit_delta <= 0
    task_ids = {task.task_id for task in result.results}
    assert {
        "project-scope-fact",
        "project-scope-procedure",
        "project-scope-procedure-stale-fact-guardrail",
        "project-scope-procedure-cross-scope-guardrail",
        "same-scope-current-pre-pr-procedure",
        "cross-scope-drift-check",
        "current-vs-stale-fact",
        "branch-only-current-policy",
        "source-global-stale-source-guardrail",
        "project-scope-fact-noisy-global-guardrail",
        "project-scope-release-version-budget-pressure",
        "same-slot-current-release-version",
        "episode-recall",
        "episode-recall-stale-fact-guardrail",
        "episode-recall-same-scope-drift-guardrail",
        "project-scope-procedure-noisy-episode-guardrail",
        "project-scope-procedure-scope-adjacent-guardrail",
        "same-scope-current-release-qa-procedure",
        "project-scope-procedure-release-qa-budget-pressure",
        "release-version-source-noise-guardrail",
        "release-qa-procedure-source-noise-guardrail",
        "episode-current-rollout-source-noise-guardrail",
        "kb-export-procedure-cross-surface-guardrail",
    } <= task_ids
    assert len({task_id for task_id in task_ids if task_id.startswith("expanded-")}) == 50
    current_by_task = {task.task_id: task.pass_ for task in result.results}
    baseline_by_task = {task.task_id: task.baseline.pass_ for task in result.results if task.baseline is not None}
    assert current_by_task["episode-recall"] is True
    assert current_by_task["episode-recall-stale-fact-guardrail"] is True
    assert current_by_task["episode-recall-same-scope-drift-guardrail"] is True
    assert current_by_task["current-vs-stale-fact"] is True
    assert current_by_task["branch-only-current-policy"] is True
    assert current_by_task["source-global-stale-source-guardrail"] is True
    assert current_by_task["project-scope-fact-noisy-global-guardrail"] is True
    assert current_by_task["project-scope-release-version-budget-pressure"] is True
    assert current_by_task["same-slot-current-release-version"] is True
    assert current_by_task["project-scope-procedure-stale-fact-guardrail"] is True
    assert current_by_task["project-scope-procedure-cross-scope-guardrail"] is True
    assert current_by_task["same-scope-current-pre-pr-procedure"] is True
    assert current_by_task["project-scope-procedure-noisy-episode-guardrail"] is True
    assert current_by_task["project-scope-procedure-scope-adjacent-guardrail"] is True
    assert current_by_task["same-scope-current-release-qa-procedure"] is True
    assert current_by_task["project-scope-procedure-release-qa-budget-pressure"] is True
    assert current_by_task["cross-scope-drift-check"] is True
    assert baseline_by_task["episode-recall"] is True
    assert baseline_by_task["cross-scope-drift-check"] is True
    assert baseline_by_task["episode-recall-stale-fact-guardrail"] is True
    assert baseline_by_task["episode-recall-same-scope-drift-guardrail"] is True
    assert baseline_by_task["current-vs-stale-fact"] is False
    assert baseline_by_task["branch-only-current-policy"] is False
    assert baseline_by_task["source-global-stale-source-guardrail"] is False
    assert baseline_by_task["project-scope-procedure-stale-fact-guardrail"] is True
    assert baseline_by_task["project-scope-procedure-cross-scope-guardrail"] is True
    assert baseline_by_task["same-scope-current-pre-pr-procedure"] is True
    assert baseline_by_task["project-scope-procedure-noisy-episode-guardrail"] is False
    assert baseline_by_task["project-scope-procedure-scope-adjacent-guardrail"] is True
    assert baseline_by_task["same-scope-current-release-qa-procedure"] is True
    assert baseline_by_task["project-scope-procedure-release-qa-budget-pressure"] is True
    assert baseline_by_task["project-scope-fact-noisy-global-guardrail"] is True
    assert baseline_by_task["project-scope-release-version-budget-pressure"] is True
    assert baseline_by_task["same-slot-current-release-version"] is False



def test_cli_eval_retrieval_runs_checked_in_symbolic_fixture_directory(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-checked-in.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixtures_dir = _checked_in_fixture_dir()
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixtures_dir),
            "--baseline-mode",
            "lexical",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["summary"]["total_tasks"] == 75
    assert payload["summary"]["passed_tasks"] == 75
    assert payload["summary"]["failed_tasks"] == 0
    assert payload["summary"]["by_primary_task_type"]["facts"]["total_tasks"] == 26
    assert payload["summary"]["by_primary_task_type"]["facts"]["passed_tasks"] == 26
    assert payload["summary"]["by_primary_task_type"]["procedures"]["total_tasks"] == 31
    assert payload["summary"]["by_primary_task_type"]["procedures"]["passed_tasks"] == 31
    assert payload["summary"]["by_primary_task_type"]["episodes"]["total_tasks"] == 18
    assert payload["summary"]["by_primary_task_type"]["episodes"]["passed_tasks"] == 18
    assert payload["baseline_summary"]["total_tasks"] == 75
    assert payload["baseline_summary"]["passed_tasks"] == 59
    assert payload["baseline_summary"]["failed_tasks"] == 16
    assert payload["baseline_summary"]["by_primary_task_type"]["facts"]["total_tasks"] == 26
    assert payload["baseline_summary"]["by_primary_task_type"]["facts"]["passed_tasks"] == 15
    assert payload["baseline_summary"]["by_primary_task_type"]["facts"]["failed_tasks"] == 11
    assert payload["baseline_summary"]["by_primary_task_type"]["procedures"]["total_tasks"] == 31
    assert payload["baseline_summary"]["by_primary_task_type"]["procedures"]["passed_tasks"] == 27
    assert payload["baseline_summary"]["by_primary_task_type"]["procedures"]["failed_tasks"] == 4
    assert payload["baseline_summary"]["by_primary_task_type"]["episodes"]["total_tasks"] == 18
    assert payload["baseline_summary"]["by_primary_task_type"]["episodes"]["passed_tasks"] == 17
    assert payload["baseline_summary"]["by_primary_task_type"]["episodes"]["failed_tasks"] == 1
    assert payload["baseline_summary"]["tasks_with_avoid_hits"] == 16
    assert payload["baseline_summary"]["by_memory_type"]["facts"]["total_tasks"] == 30
    assert payload["baseline_summary"]["by_memory_type"]["facts"]["passed_tasks"] == 15
    assert payload["baseline_summary"]["by_memory_type"]["facts"]["failed_tasks"] == 15
    assert payload["baseline_summary"]["by_memory_type"]["procedures"]["total_tasks"] == 31
    assert payload["baseline_summary"]["by_memory_type"]["procedures"]["passed_tasks"] == 31
    assert payload["baseline_summary"]["by_memory_type"]["procedures"]["failed_tasks"] == 0
    assert payload["baseline_summary"]["by_memory_type"]["episodes"]["total_tasks"] == 19
    assert payload["baseline_summary"]["by_memory_type"]["episodes"]["passed_tasks"] == 18
    assert payload["baseline_summary"]["by_memory_type"]["episodes"]["failed_tasks"] == 1
    assert payload["delta_summary"]["total_avoid_hit_delta"] <= 0
    assert payload["delta_summary"]["by_memory_type"]["facts"]["total_avoid_hit_delta"] <= 0
    assert payload["delta_summary"]["by_memory_type"]["facts"]["total_pass_count_delta"] >= 0
    assert payload["delta_summary"]["by_memory_type"]["procedures"]["total_avoid_hit_delta"] <= 0
    assert isinstance(payload["delta_summary"]["by_memory_type"]["procedures"]["total_pass_count_delta"], int)
    assert isinstance(payload["delta_summary"]["by_memory_type"]["episodes"]["total_avoid_hit_delta"], int)
    assert isinstance(payload["delta_summary"]["by_memory_type"]["episodes"]["total_pass_count_delta"], int)
    assert isinstance(payload["delta_summary"]["by_memory_type"]["episodes"]["tasks_with_pass_change"], int)



def test_evaluate_retrieval_fixtures_includes_source_lexical_baseline_when_requested(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-source-lexical.db"
    initialize_database(db_path)

    expected_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="The handbook says to run uv run agent-memory kb export before publishing the KB draft.",
        metadata={"doc": "handbook"},
    )
    avoid_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="The archived note only mentions a legacy shell alias for an older workflow.",
        metadata={"doc": "archive"},
    )

    expected_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-alpha",
        evidence_ids=[expected_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    avoid_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-beta",
        evidence_ids=[avoid_source.id],
        scope="project:m1",
        confidence=0.60,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=expected_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=avoid_fact.id)

    fixture_path = tmp_path / "source-lexical.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-lexical-fact",
                        "query": "What does the handbook say to run before publishing?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [expected_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [avoid_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="source-lexical")

    assert result.baseline_mode == "source-lexical"
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.mode == "source-lexical"
    assert result.results[0].baseline.pass_ is True
    assert result.results[0].baseline.expected_hits["facts"] == [expected_fact.id]
    assert result.results[0].baseline.avoid_hits["facts"] == []
    assert result.baseline_summary is not None
    assert result.baseline_summary.total_tasks == 1
    assert result.baseline_summary.passed_tasks == 1
    assert result.baseline_summary.failed_tasks == 0
    assert result.delta_summary is not None
    assert result.delta_summary.total_pass_count_delta == -1
    assert result.delta_summary.by_primary_task_type["facts"].tasks_with_pass_change == 1


def test_cli_eval_retrieval_outputs_source_lexical_baseline_when_requested(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-source-lexical.db"
    initialize_database(db_path)

    expected_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="The handbook says to run uv run agent-memory kb export before publishing the KB draft.",
        metadata={"doc": "handbook"},
    )
    avoid_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="The archived note only mentions a legacy shell alias for an older workflow.",
        metadata={"doc": "archive"},
    )

    expected_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-alpha",
        evidence_ids=[expected_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    avoid_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-beta",
        evidence_ids=[avoid_source.id],
        scope="project:m1",
        confidence=0.60,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=expected_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=avoid_fact.id)

    fixture_path = tmp_path / "source-lexical.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-lexical-fact",
                        "query": "What does the handbook say to run before publishing?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [expected_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [avoid_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-lexical",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline_mode"] == "source-lexical"
    assert payload["results"][0]["baseline"]["mode"] == "source-lexical"
    assert payload["results"][0]["baseline"]["pass"] is True
    assert payload["results"][0]["baseline"]["expected_hits"]["facts"] == [expected_fact.id]
    assert payload["baseline_summary"]["passed_tasks"] == 1
    assert payload["baseline_summary"]["failed_tasks"] == 0
    assert payload["delta_summary"]["total_pass_count_delta"] == -1



def test_checked_in_retrieval_fixture_examples_have_stable_comparator_matrix(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-comparator-matrix.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixtures_dir = _checked_in_fixture_dir()

    expected = {
        "lexical": {
            "baseline_passed": 59,
            "baseline_failed": 16,
            "baseline_avoid": 16,
            "delta_avoid": -16,
            "delta_pass": 16,
            "facts_primary": (26, 15, 11),
        },
        "source-lexical": {
            "baseline_passed": 54,
            "baseline_failed": 21,
            "baseline_avoid": 8,
            "delta_avoid": -8,
            "delta_pass": 21,
            "facts_primary": (26, 11, 15),
        },
        "lexical-global": {
            "baseline_passed": 50,
            "baseline_failed": 25,
            "baseline_avoid": 22,
            "delta_avoid": -23,
            "delta_pass": 25,
            "facts_primary": (26, 10, 16),
        },
        "source-global": {
            "baseline_passed": 38,
            "baseline_failed": 37,
            "baseline_avoid": 26,
            "delta_avoid": -26,
            "delta_pass": 37,
            "facts_primary": (26, 1, 25),
        },
     }

    for mode, expectation in expected.items():
        result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixtures_dir, baseline_mode=mode)

        assert result.summary.total_tasks == 75
        assert result.summary.passed_tasks + result.summary.failed_tasks == 75
        assert result.summary.by_primary_task_type["facts"].total_tasks == 26
        assert result.summary.by_primary_task_type["procedures"].total_tasks == 31
        assert result.summary.by_primary_task_type["episodes"].total_tasks == 18
        assert result.baseline_summary is not None
        assert result.baseline_summary.mode == mode
        assert result.baseline_summary.total_tasks == 75
        assert result.baseline_summary.passed_tasks + result.baseline_summary.failed_tasks == 75
        assert result.baseline_summary.passed_tasks == expectation["baseline_passed"]
        assert result.baseline_summary.failed_tasks == expectation["baseline_failed"]
        assert result.baseline_summary.tasks_with_avoid_hits == expectation["baseline_avoid"]
        facts_total, facts_passed, facts_failed = expectation["facts_primary"]
        assert result.baseline_summary.by_primary_task_type["facts"].total_tasks == facts_total
        assert result.baseline_summary.by_primary_task_type["facts"].passed_tasks == facts_passed
        assert result.baseline_summary.by_primary_task_type["facts"].failed_tasks == facts_failed
        assert result.baseline_summary.by_primary_task_type["procedures"].total_tasks == 31
        assert result.baseline_summary.by_primary_task_type["episodes"].total_tasks == 18
        assert result.delta_summary is not None
        assert result.delta_summary.total_avoid_hit_delta == expectation["delta_avoid"]
        assert result.delta_summary.total_pass_count_delta == expectation["delta_pass"]


def test_evaluate_retrieval_fixtures_includes_source_global_baseline_when_requested(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-source-global.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project m1 shorthand note mentions only the export command.",
        metadata={"doc": "m1-short-note"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Handbook checklist says before publishing run uv run agent-memory kb export and verify the KB draft.",
        metadata={"doc": "global-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-local",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-global",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-fact",
                        "query": "What does the handbook checklist say to run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, baseline_mode="source-global")

    assert result.baseline_mode == "source-global"
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.mode == "source-global"
    assert result.results[0].baseline.pass_ is True
    assert result.results[0].baseline.expected_hits["facts"] == [cross_scope_fact.id]
    assert result.results[0].baseline.avoid_hits["facts"] == []
    assert result.baseline_summary is not None
    assert result.baseline_summary.passed_tasks == 1
    assert result.baseline_summary.failed_tasks == 0
    assert result.delta_summary is not None
    assert result.delta_summary.total_pass_count_delta == -1


def test_cli_eval_retrieval_outputs_source_global_baseline_when_requested(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-source-global.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project m1 shorthand note mentions only the export command.",
        metadata={"doc": "m1-short-note"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Handbook checklist says before publishing run uv run agent-memory kb export and verify the KB draft.",
        metadata={"doc": "global-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-local",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-global",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-fact",
                        "query": "What does the handbook checklist say to run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-global",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline_mode"] == "source-global"
    assert payload["results"][0]["baseline"]["mode"] == "source-global"
    assert payload["results"][0]["baseline"]["pass"] is True
    assert payload["results"][0]["baseline"]["expected_hits"]["facts"] == [cross_scope_fact.id]
    assert payload["baseline_summary"]["passed_tasks"] == 1
    assert payload["baseline_summary"]["failed_tasks"] == 0
    assert payload["delta_summary"]["total_pass_count_delta"] == -1


def test_cli_eval_retrieval_outputs_lexical_global_baseline_when_requested(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-global.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical-global",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline_mode"] == "lexical-global"
    assert payload["baseline_summary"]["total_tasks"] == 1
    assert payload["baseline_summary"]["passed_tasks"] == 0
    assert payload["baseline_summary"]["failed_tasks"] == 1
    assert payload["baseline_summary"]["tasks_with_avoid_hits"] == 1
    assert payload["results"][0]["task_id"] == "branch-only-current-policy"
    assert payload["results"][0]["baseline"]["mode"] == "lexical-global"
    assert payload["results"][0]["baseline"]["pass"] is False
    assert len(payload["results"][0]["baseline"]["avoid_hits"]["facts"]) == 1
    assert payload["results"][0]["delta"] is not None
    assert payload["results"][0]["delta"]["avoid_hit_delta"] in {-1, 0}
    assert payload["delta_summary"]["total_avoid_hit_delta"] in {-1, 0}
    assert payload["delta_summary"]["total_pass_count_delta"] in {0, 1}
    assert payload["delta_summary"]["by_primary_task_type"]["facts"]["tasks_with_pass_change"] in {0, 1}



def test_cli_eval_retrieval_outputs_lexical_baseline_when_requested(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline.db"
    seeded_ids = _seed_retrieval_eval_db(db_path)
    fixture_path = _write_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["baseline_mode"] == "lexical"
    assert payload["summary"]["passed_tasks"] == 2
    assert payload["summary"]["failed_tasks"] == 0
    assert payload["baseline_summary"]["total_tasks"] == 2
    assert payload["baseline_summary"]["passed_tasks"] == 2
    assert payload["baseline_summary"]["failed_tasks"] == 0
    assert payload["summary"]["by_primary_task_type"]["facts"]["total_tasks"] == 1
    assert payload["summary"]["by_primary_task_type"]["procedures"]["total_tasks"] == 1
    assert payload["baseline_summary"]["by_primary_task_type"]["facts"]["total_tasks"] == 1
    assert payload["baseline_summary"]["by_primary_task_type"]["procedures"]["total_tasks"] == 1
    assert payload["results"][0]["baseline"]["mode"] == "lexical"
    assert payload["results"][0]["baseline"]["pass"] is True
    assert payload["results"][0]["delta"] == {
        "expected_hit_delta": 0,
        "missing_expected_delta": 0,
        "avoid_hit_delta": 0,
        "pass_changed": False,
    }
    assert payload["delta_summary"] == {
        "total_expected_hit_delta": 0,
        "total_missing_expected_delta": 0,
        "total_avoid_hit_delta": 0,
        "total_pass_count_delta": 0,
        "by_memory_type": {
        "facts": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "procedures": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "episodes": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
},
        "by_primary_task_type": {
        "facts": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "procedures": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
        "episodes": {
            "total_expected_hit_delta": 0,
            "total_missing_expected_delta": 0,
            "total_avoid_hit_delta": 0,
            "total_pass_count_delta": 0,
            "tasks_with_pass_change": 0,
        },
},
    }



def test_evaluate_retrieval_fixtures_raises_when_fail_on_regression_enabled(tmp_path: Path) -> None:
    import pytest
    from agent_memory.core.retrieval_eval import RetrievalEvalRegressionError, evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-fail.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_missing_expected_fixture_file(tmp_path)

    with pytest.raises(RetrievalEvalRegressionError) as exc_info:
        evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path, fail_on_regression=True)

    assert exc_info.value.failed_task_ids == ["missing-expected-policy"]



def test_cli_eval_retrieval_exits_nonzero_when_fail_on_regression_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-fail.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_missing_expected_fixture_file(tmp_path)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--fail-on-regression",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "missing-expected-policy" in result.stderr
    assert result.stdout == ""



def test_evaluate_retrieval_fixtures_raises_when_current_is_worse_than_baseline(tmp_path: Path) -> None:
    import pytest
    from agent_memory.core.retrieval_eval import RetrievalEvalRegressionError, evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-fail.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)

    with pytest.raises(RetrievalEvalRegressionError) as exc_info:
        evaluate_retrieval_fixtures(
            db_path=db_path,
            fixtures_path=fixture_path,
            baseline_mode="lexical",
            fail_on_baseline_regression=True,
        )

    assert exc_info.value.failed_task_ids == ["legacy-branch-policy"]



def test_evaluate_retrieval_fixtures_can_gate_baseline_regressions_by_primary_task_type(tmp_path: Path) -> None:
    import pytest
    from agent_memory.core.retrieval_eval import RetrievalEvalRegressionError, evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-facts-filter.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="lexical",
        fail_on_baseline_regression_memory_types=["procedures"],
    )

    assert result.results[0].task_id == "legacy-branch-policy"
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.pass_ is True

    if result.results[0].pass_ is False:
        with pytest.raises(RetrievalEvalRegressionError) as exc_info:
            evaluate_retrieval_fixtures(
                db_path=db_path,
                fixtures_path=fixture_path,
                baseline_mode="lexical",
                fail_on_baseline_regression_memory_types=["facts"],
            )

        assert exc_info.value.failed_task_ids == ["legacy-branch-policy"]
    else:
        stable_result = evaluate_retrieval_fixtures(
            db_path=db_path,
            fixtures_path=fixture_path,
            baseline_mode="lexical",
            fail_on_baseline_regression_memory_types=["facts"],
        )
        assert stable_result.results[0].pass_ is True
        assert stable_result.results[0].delta is not None
        assert stable_result.results[0].delta.pass_changed is False



def test_cli_eval_retrieval_exits_nonzero_when_current_is_worse_than_baseline(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-fail.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
            "--fail-on-baseline-regression",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "legacy-branch-policy" in result.stderr
    assert result.stdout == ""



def test_cli_eval_retrieval_can_gate_baseline_regressions_by_primary_task_type(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-facts-filter.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    allowed = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
            "--fail-on-baseline-regression-memory-type",
            "procedures",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert allowed.returncode == 0
    assert allowed.stderr == ""

    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
            "--fail-on-baseline-regression-memory-type",
            "facts",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert blocked.returncode in {0, 1}
    if blocked.returncode == 1:
        assert "legacy-branch-policy" in blocked.stderr
        assert blocked.stdout == ""
    else:
        assert blocked.stderr == ""
        blocked_payload = json.loads(blocked.stdout)
        assert blocked_payload["summary"]["total_tasks"] == 1
        assert blocked_payload["baseline_summary"]["mode"] == "lexical"
        assert blocked_payload["delta_summary"]["by_primary_task_type"]["procedures"]["tasks_with_pass_change"] == 0


def test_evaluate_retrieval_fixtures_emits_soft_regression_gate_advisories(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-soft-current.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)

    result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        warn_on_regression_threshold=0,
    )

    assert result.results[0].task_id == "legacy-branch-policy"
    advisory_payloads = [advisory.model_dump() for advisory in result.advisories]
    if result.results[0].pass_ is False:
        assert advisory_payloads == [
            {
                "code": "regression-threshold-exceeded",
                "message": "Current retrieval has 1 failing tasks, which exceeds the soft threshold of 0.",
                "observed": 1,
                "threshold": 0,
                "task_ids": ["legacy-branch-policy"],
                "baseline_mode": None,
            }
        ]
    else:
        assert result.results[0].pass_ is True
        assert advisory_payloads == []

    baseline_filtered = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="lexical",
        warn_on_baseline_regression_threshold=1,
    )
    baseline_triggered = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="lexical",
        warn_on_baseline_regression_threshold=0,
    )

    assert baseline_filtered.advisories == []
    baseline_advisories = [advisory.model_dump() for advisory in baseline_triggered.advisories]
    delta = baseline_triggered.results[0].delta
    if delta and delta.pass_changed and baseline_triggered.results[0].pass_ is False:
        assert baseline_advisories == [
            {
                "code": "baseline-regression-threshold-exceeded",
                "message": "Current retrieval is worse than the lexical baseline on 1 tasks, which exceeds the soft threshold of 0.",
                "observed": 1,
                "threshold": 0,
                "task_ids": ["legacy-branch-policy"],
                "baseline_mode": "lexical",
            }
        ]
    else:
        assert baseline_advisories == []



def test_cli_eval_retrieval_emits_soft_regression_gate_advisories(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-soft-current.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _write_legacy_branch_fixture_file(tmp_path, seeded_ids)
    env = {**os.environ, "PYTHONPATH": "src"}

    current_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--warn-on-regression-threshold",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )
    baseline_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical",
            "--warn-on-baseline-regression-threshold",
            "0",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert current_result.returncode == 0, current_result.stderr
    assert baseline_result.returncode == 0, baseline_result.stderr
    assert json.loads(current_result.stdout)["advisories"] == [
        {
            "code": "regression-threshold-exceeded",
            "message": "Current retrieval has 1 failing tasks, which exceeds the soft threshold of 0.",
            "observed": 1,
            "threshold": 0,
            "task_ids": ["legacy-branch-policy"],
            "baseline_mode": None,
        }
    ]
    assert json.loads(baseline_result.stdout)["advisories"] == [
        {
            "code": "baseline-regression-threshold-exceeded",
            "message": "Current retrieval is worse than the lexical baseline on 1 tasks, which exceeds the soft threshold of 0.",
            "observed": 1,
            "threshold": 0,
            "task_ids": ["legacy-branch-policy"],
            "baseline_mode": "lexical",
        }
    ]



def test_evaluate_retrieval_fixtures_can_gate_source_global_baseline_regressions_by_primary_task_type(tmp_path: Path) -> None:
    import pytest
    from agent_memory.core.retrieval_eval import RetrievalEvalRegressionError, evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-source-global-facts-filter.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project m1 shorthand note mentions only the export command.",
        metadata={"doc": "m1-short-note"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Handbook checklist says before publishing run uv run agent-memory kb export and verify the KB draft.",
        metadata={"doc": "global-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-local",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-global",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global-selective.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-fact",
                        "query": "What does the handbook checklist say to run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )

    result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="source-global",
        fail_on_baseline_regression_memory_types=["procedures"],
    )

    assert result.results[0].task_id == "source-global-fact"
    assert result.results[0].pass_ is False
    assert result.results[0].baseline is not None
    assert result.results[0].baseline.pass_ is True

    with pytest.raises(RetrievalEvalRegressionError) as exc_info:
        evaluate_retrieval_fixtures(
            db_path=db_path,
            fixtures_path=fixture_path,
            baseline_mode="source-global",
            fail_on_baseline_regression_memory_types=["facts"],
        )

    assert exc_info.value.failed_task_ids == ["source-global-fact"]


def test_cli_eval_retrieval_can_gate_source_global_baseline_regressions_by_primary_task_type(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-source-global-facts-filter.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project m1 shorthand note mentions only the export command.",
        metadata={"doc": "m1-short-note"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Handbook checklist says before publishing run uv run agent-memory kb export and verify the KB draft.",
        metadata={"doc": "global-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-local",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="KB draft workflow",
        predicate="command_code",
        object_ref_or_value="cmd-global",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global-selective.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-fact",
                        "query": "What does the handbook checklist say to run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    allowed = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-global",
            "--fail-on-baseline-regression-memory-type",
            "procedures",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert allowed.returncode == 0
    assert allowed.stderr == ""

    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-global",
            "--fail-on-baseline-regression-memory-type",
            "facts",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert blocked.returncode == 1
    assert "source-global-fact" in blocked.stderr
    assert blocked.stdout == ""


def test_evaluate_retrieval_fixtures_can_filter_lexical_global_baseline_gating_without_false_failures(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-baseline-global-filter.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"

    procedures_result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="lexical-global",
        fail_on_baseline_regression_memory_types=["procedures"],
    )
    facts_result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="lexical-global",
        fail_on_baseline_regression_memory_types=["facts"],
    )

    for result_set in (procedures_result, facts_result):
        assert result_set.results[0].task_id == "branch-only-current-policy"
        assert result_set.results[0].pass_ is True
        assert result_set.results[0].baseline is not None
        assert result_set.results[0].baseline.mode == "lexical-global"
        assert result_set.results[0].baseline.pass_ is False


def test_cli_eval_retrieval_does_not_false_fail_lexical_global_baseline_gating(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-baseline-global-filter.db"
    _seed_checked_in_fixture_eval_db(db_path)
    fixture_path = _checked_in_fixture_dir() / "staleness" / "branch-only-current.json"
    env = {**os.environ, "PYTHONPATH": "src"}

    procedures_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical-global",
            "--fail-on-baseline-regression-memory-type",
            "procedures",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert procedures_result.returncode == 0
    assert procedures_result.stderr == ""

    facts_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "lexical-global",
            "--fail-on-baseline-regression-memory-type",
            "facts",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert facts_result.returncode == 0
    assert facts_result.stderr == ""


def test_evaluate_retrieval_fixtures_does_not_false_fail_source_global_baseline_gating(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-source-global-no-false-fail.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Short local note for Project M1.",
        metadata={"doc": "m1-guide"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Archived handbook checklist says before publishing the KB draft you should run uv run agent-memory kb export, verify the KB draft, notify reviewers, and follow the legacy archive workflow.",
        metadata={"doc": "archive-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1 publishing guide",
        predicate="recommended_command",
        object_ref_or_value="run uv run agent-memory kb export before publishing the KB draft",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Archived publishing guide",
        predicate="recommended_command",
        object_ref_or_value="legacy archive workflow",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global-no-false-fail.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-current-better",
                        "query": "What should Project M1 run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )

    procedures_result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="source-global",
        fail_on_baseline_regression_memory_types=["procedures"],
    )
    facts_result = evaluate_retrieval_fixtures(
        db_path=db_path,
        fixtures_path=fixture_path,
        baseline_mode="source-global",
        fail_on_baseline_regression_memory_types=["facts"],
    )

    for result_set in (procedures_result, facts_result):
        assert result_set.results[0].task_id == "source-global-current-better"
        assert result_set.results[0].pass_ is True
        assert result_set.results[0].baseline is not None
        assert result_set.results[0].baseline.mode == "source-global"
        assert result_set.results[0].baseline.pass_ is False


def test_cli_eval_retrieval_does_not_false_fail_source_global_baseline_gating(tmp_path: Path) -> None:
    db_path = tmp_path / "retrieval-eval-cli-source-global-no-false-fail.db"
    initialize_database(db_path)

    preferred_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Short local note for Project M1.",
        metadata={"doc": "m1-guide"},
    )
    cross_scope_source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Archived handbook checklist says before publishing the KB draft you should run uv run agent-memory kb export, verify the KB draft, notify reviewers, and follow the legacy archive workflow.",
        metadata={"doc": "archive-handbook"},
    )

    preferred_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project M1 publishing guide",
        predicate="recommended_command",
        object_ref_or_value="run uv run agent-memory kb export before publishing the KB draft",
        evidence_ids=[preferred_source.id],
        scope="project:m1",
        confidence=0.95,
    )
    cross_scope_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Archived publishing guide",
        predicate="recommended_command",
        object_ref_or_value="legacy archive workflow",
        evidence_ids=[cross_scope_source.id],
        scope="project:archive",
        confidence=0.55,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=preferred_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=cross_scope_fact.id)

    fixture_path = tmp_path / "source-global-no-false-fail.json"
    fixture_path.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "id": "source-global-current-better",
                        "query": "What should Project M1 run before publishing the KB draft?",
                        "preferred_scope": "project:m1",
                        "limit": 1,
                        "expected": {"facts": [preferred_fact.id], "procedures": [], "episodes": []},
                        "avoid": {"facts": [cross_scope_fact.id], "procedures": [], "episodes": []},
                    }
                ]
            },
            indent=2,
        )
    )
    env = {**os.environ, "PYTHONPATH": "src"}

    procedures_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-global",
            "--fail-on-baseline-regression-memory-type",
            "procedures",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert procedures_result.returncode == 0
    assert procedures_result.stderr == ""

    facts_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agent_memory.api.cli",
            "eval",
            "retrieval",
            str(db_path),
            str(fixture_path),
            "--baseline-mode",
            "source-global",
            "--fail-on-baseline-regression-memory-type",
            "facts",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
    )

    assert facts_result.returncode == 0
    assert facts_result.stderr == ""


def test_symbolic_references_support_step_and_tag_based_selectors(tmp_path: Path) -> None:
    from agent_memory.core.retrieval_eval import evaluate_retrieval_fixtures

    db_path = tmp_path / "retrieval-eval-symbolic-expanded.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)
    source_id = seeded_ids["project_scope_fact"]
    extra_procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local tests",
        trigger_context="Before opening a PR",
        preconditions=["Dependencies installed"],
        steps=["npm test"],
        evidence_ids=[source_id],
        scope="project:m1",
        success_rate=1.0,
    )
    approve_memory(db_path=db_path, memory_type="procedure", memory_id=extra_procedure.id)
    create_episode(
        db_path=db_path,
        title="Retrieval evaluation rollout follow-up",
        summary="A follow-up note that should not match the exact tag-based selector.",
        source_ids=[source_id],
        tags=["retrieval", "follow-up"],
        importance_score=0.4,
        scope="project:m1",
        status="approved",
    )
    fixture_path = tmp_path / "expanded-symbolic.json"
    fixture_path.write_text(
        json.dumps(
            {
                "references": {
                    "procedure_by_step": {
                        "memory_type": "procedure",
                        "scope": "project:m1",
                        "step_contains": "pytest tests/",
                    },
                    "episode_by_tags": {
                        "memory_type": "episode",
                        "scope": "project:m1",
                        "tags_include": ["retrieval", "evaluation"],
                    },
                },
                "tasks": [
                    {
                        "id": "step-selector-procedure",
                        "query": "What should run before opening a PR for Project M1?",
                        "preferred_scope": "project:m1",
                        "limit": 5,
                        "expected": {"facts": [], "procedures": ["procedure_by_step"], "episodes": []},
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                    },
                    {
                        "id": "tag-selector-episode",
                        "query": "What happened during the retrieval evaluation rollout?",
                        "preferred_scope": "project:m1",
                        "limit": 5,
                        "expected": {"facts": [], "procedures": [], "episodes": ["episode_by_tags"]},
                        "avoid": {"facts": [], "procedures": [], "episodes": []},
                    },
                ],
            },
            indent=2,
        )
    )

    result = evaluate_retrieval_fixtures(db_path=db_path, fixtures_path=fixture_path)

    assert [task.task_id for task in result.results] == ["step-selector-procedure", "tag-selector-episode"]
    assert result.results[0].expected_hits["procedures"] or result.results[0].missing_expected["procedures"]
    assert result.results[1].expected_hits["episodes"]



def test_retrieve_memory_packet_filters_cross_scope_fact_drift_when_exact_scope_match_exists(tmp_path: Path) -> None:
    from agent_memory.core.retrieval import retrieve_memory_packet

    db_path = tmp_path / "retrieval-cross-scope-improvement.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What EP-123 branch pattern does Project M1 use?",
        preferred_scope="project:m1",
    )

    fact_ids = [fact.id for fact in packet.semantic_facts]
    assert packet.semantic_facts[0].id == seeded_ids["current_branch_fact"]
    assert seeded_ids["drift_fact"] not in fact_ids



def test_retrieve_memory_packet_hides_stale_conflicting_fact_when_newer_fact_matches_same_claim_slot(tmp_path: Path) -> None:
    from agent_memory.core.retrieval import retrieve_memory_packet

    db_path = tmp_path / "retrieval-stale-improvement.db"
    seeded_ids = _seed_checked_in_fixture_eval_db(db_path)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What is the current approved branch policy for Project M1?",
        preferred_scope="project:m1",
    )

    fact_ids = [fact.id for fact in packet.semantic_facts]
    assert packet.semantic_facts[0].id == seeded_ids["current_branch_fact"]
    assert seeded_ids["stale_branch_fact"] not in fact_ids
