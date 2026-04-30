from __future__ import annotations

import json
from pathlib import Path

from agent_memory.core.models import (
    RetrievalEvalAdvisory,
    RetrievalEvalAdvisoryReport,
    RetrievalEvalBaselineSummary,
    RetrievalEvalDelta,
    RetrievalEvalDeltaSummary,
    RetrievalEvalExpected,
    RetrievalEvalFixture,
    RetrievalEvalMemoryDetail,
    RetrievalEvalMemorySelector,
    RetrievalEvalMemoryTypeDeltaSummary,
    RetrievalEvalMemoryTypeSummary,
    RetrievalEvalResultSet,
    RetrievalEvalRunMetrics,
    RetrievalEvalSummary,
    RetrievalEvalTask,
    RetrievalEvalTaskResult,
)
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import (
    get_source_records_by_ids,
    list_approved_episodes,
    list_approved_facts,
    list_approved_procedures,
)


_MEMORY_TYPES = ("facts", "procedures", "episodes")


class RetrievalEvalRegressionError(RuntimeError):
    def __init__(self, failed_task_ids: list[str], result_set: RetrievalEvalResultSet | None = None):
        self.failed_task_ids = failed_task_ids
        self.result_set = result_set
        joined_ids = ", ".join(failed_task_ids)
        super().__init__(f"regression detected for task(s): {joined_ids}")


def _normalize_path(path: Path | str) -> Path:
    return path if isinstance(path, Path) else Path(path)


def _resolve_fixture_paths(fixtures_path: Path | str) -> list[Path]:
    resolved = _normalize_path(fixtures_path)
    if resolved.is_dir():
        return sorted(path for path in resolved.rglob("*.json") if path.is_file())
    return [resolved]


def _load_fixture(path: Path) -> RetrievalEvalFixture:
    return RetrievalEvalFixture.model_validate(json.loads(path.read_text()))



def _contains_casefold(value: str, needle: str) -> bool:
    return needle.casefold() in value.casefold()



def _resolve_reference_id(db_path: Path, alias: str, selector: RetrievalEvalMemorySelector) -> int:
    if selector.memory_type == "fact":
        candidates = list_approved_facts(db_path, scope=selector.scope)
        matches = [
            fact
            for fact in candidates
            if (selector.subject_ref is None or fact.subject_ref == selector.subject_ref)
            and (selector.predicate is None or fact.predicate == selector.predicate)
            and (
                selector.object_ref_or_value is None
                or fact.object_ref_or_value == selector.object_ref_or_value
            )
            and (
                selector.searchable_text_contains is None
                or _contains_casefold(fact.searchable_text, selector.searchable_text_contains)
            )
        ]
    elif selector.memory_type == "procedure":
        candidates = list_approved_procedures(db_path, scope=selector.scope)
        matches = [
            procedure
            for procedure in candidates
            if (selector.name is None or procedure.name == selector.name)
            and (
                selector.trigger_context is None
                or procedure.trigger_context == selector.trigger_context
            )
            and (
                selector.searchable_text_contains is None
                or _contains_casefold(procedure.searchable_text, selector.searchable_text_contains)
            )
            and (
                selector.step_contains is None
                or any(_contains_casefold(step, selector.step_contains) for step in procedure.steps)
            )
        ]
    else:
        candidates = list_approved_episodes(db_path, scope=selector.scope)
        matches = [
            episode
            for episode in candidates
            if (selector.title is None or episode.title == selector.title)
            and (
                selector.searchable_text_contains is None
                or _contains_casefold(episode.searchable_text, selector.searchable_text_contains)
            )
            and all(tag in episode.tags for tag in selector.tags_include)
        ]

    if len(matches) != 1:
        raise ValueError(
            f"fixture reference '{alias}' resolved to {len(matches)} matches for selector {selector.model_dump()}"
        )
    return matches[0].id



def _resolve_expected_ids(
    values: list[int | str],
    *,
    memory_type: str,
    resolved_references: dict[str, int],
) -> list[int]:
    resolved_ids: list[int] = []
    for value in values:
        if isinstance(value, int):
            resolved_ids.append(value)
            continue
        if value not in resolved_references:
            raise ValueError(f"unknown fixture reference '{value}' in {memory_type}")
        resolved_ids.append(resolved_references[value])
    return resolved_ids



def _resolve_task_references(
    task: RetrievalEvalTask,
    *,
    resolved_references: dict[str, int],
) -> RetrievalEvalTask:
    return task.model_copy(
        update={
            "expected": RetrievalEvalExpected(
                facts=_resolve_expected_ids(task.expected.facts, memory_type="facts", resolved_references=resolved_references),
                procedures=_resolve_expected_ids(
                    task.expected.procedures,
                    memory_type="procedures",
                    resolved_references=resolved_references,
                ),
                episodes=_resolve_expected_ids(
                    task.expected.episodes,
                    memory_type="episodes",
                    resolved_references=resolved_references,
                ),
            ),
            "avoid": RetrievalEvalExpected(
                facts=_resolve_expected_ids(task.avoid.facts, memory_type="facts", resolved_references=resolved_references),
                procedures=_resolve_expected_ids(
                    task.avoid.procedures,
                    memory_type="procedures",
                    resolved_references=resolved_references,
                ),
                episodes=_resolve_expected_ids(
                    task.avoid.episodes,
                    memory_type="episodes",
                    resolved_references=resolved_references,
                ),
            ),
        }
    )



def _resolve_fixture_references(db_path: Path, fixture: RetrievalEvalFixture) -> RetrievalEvalFixture:
    resolved_references = {
        alias: _resolve_reference_id(db_path, alias, selector) for alias, selector in fixture.references.items()
    }
    return fixture.model_copy(
        update={
            "tasks": [
                _resolve_task_references(task, resolved_references=resolved_references) for task in fixture.tasks
            ]
        }
    )



def _expected_to_dict(expected: RetrievalEvalExpected) -> dict[str, list[int]]:
    return {
        "facts": list(expected.facts),
        "procedures": list(expected.procedures),
        "episodes": list(expected.episodes),
    }

def _retrieved_ids_for_task_result(packet) -> dict[str, list[int]]:
    return {
        "facts": [fact.id for fact in packet.semantic_facts],
        "procedures": [procedure.id for procedure in packet.procedural_guidance],
        "episodes": [episode.id for episode in packet.episodic_context],
    }


def _details_by_type(db_path: Path, ids_by_type: dict[str, list[int]]) -> dict[str, list[RetrievalEvalMemoryDetail]]:
    facts_by_id = {fact.id: fact for fact in list_approved_facts(db_path)}
    procedures_by_id = {procedure.id: procedure for procedure in list_approved_procedures(db_path)}
    episodes_by_id = {episode.id: episode for episode in list_approved_episodes(db_path)}
    return {
        "facts": [_detail_for_fact(facts_by_id[memory_id]) for memory_id in ids_by_type.get("facts", []) if memory_id in facts_by_id],
        "procedures": [
            _detail_for_procedure(procedures_by_id[memory_id])
            for memory_id in ids_by_type.get("procedures", [])
            if memory_id in procedures_by_id
        ],
        "episodes": [
            _detail_for_episode(episodes_by_id[memory_id])
            for memory_id in ids_by_type.get("episodes", [])
            if memory_id in episodes_by_id
        ],
    }


def _detail_for_fact(fact) -> RetrievalEvalMemoryDetail:
    return RetrievalEvalMemoryDetail(
        id=fact.id,
        label=fact.subject_ref,
        scope=fact.scope,
        status=fact.status,
        snippet=f"{fact.subject_ref} {fact.predicate} {fact.object_ref_or_value}",
    )


def _detail_for_procedure(procedure) -> RetrievalEvalMemoryDetail:
    return RetrievalEvalMemoryDetail(
        id=procedure.id,
        label=procedure.name,
        scope=procedure.scope,
        status=procedure.status,
        snippet=f"{procedure.name}: {procedure.trigger_context}; steps: {'; '.join(procedure.steps[:2])}",
    )


def _detail_for_episode(episode) -> RetrievalEvalMemoryDetail:
    return RetrievalEvalMemoryDetail(
        id=episode.id,
        label=episode.title,
        scope=episode.scope,
        status=episode.status,
        snippet=f"{episode.title}: {episode.summary}",
    )


def _policy_signals_by_retrieved_id(packet) -> dict[tuple[str, int], list[str]]:
    signals: dict[tuple[str, int], list[str]] = {}
    trust_by_key = {(trust.memory_type, trust.memory_id): trust for trust in packet.trust_summaries}
    decision = packet.decision_summary
    if decision is None:
        return signals
    key = (decision.target_memory_type, decision.target_memory_id)
    trust = trust_by_key.get(key)
    hidden = "yes" if decision.has_hidden_alternatives else "no"
    item_signals = [
        f"mode={decision.recommended_answer_mode}",
        f"trust={trust.trust_band if trust is not None else decision.trust_band}",
        f"hidden_alternatives={hidden}",
        f"reasons={','.join(decision.reason_codes)}",
    ]
    signals[key] = item_signals
    return signals


def _with_policy_signals(
    details: dict[str, list[RetrievalEvalMemoryDetail]],
    policy_signals_by_id: dict[tuple[str, int], list[str]],
) -> dict[str, list[RetrievalEvalMemoryDetail]]:
    singular = {"facts": "fact", "procedures": "procedure", "episodes": "episode"}
    return {
        memory_type: [
            detail.model_copy(update={"policy_signals": policy_signals_by_id.get((singular[memory_type], detail.id), [])})
            for detail in details[memory_type]
        ]
        for memory_type in _MEMORY_TYPES
    }


def _tokenize_query(query: str) -> list[str]:
    return [token.lower() for token in query.replace("?", " ").replace(".", " ").split() if token.strip()]


def _text_match_count(searchable_text: str, tokens: list[str]) -> int:
    lowered = searchable_text.lower()
    return sum(1 for token in tokens if token in lowered)


def _lexical_retrieved_ids(db_path: Path, task: RetrievalEvalTask, *, scope: str | None) -> dict[str, list[int]]:
    tokens = _tokenize_query(task.query)
    if not tokens:
        return {memory_type: [] for memory_type in _MEMORY_TYPES}

    def _top_ids(models: list[object]) -> list[int]:
        scored = []
        for model in models:
            match_count = _text_match_count(model.searchable_text, tokens)
            if match_count <= 0:
                continue
            scored.append((-match_count, model.id, model.id))
        scored.sort()
        return [model_id for _neg_match_count, _sort_id, model_id in scored[: task.limit]]

    return {
        "facts": _top_ids(list_approved_facts(db_path, scope=scope)),
        "procedures": _top_ids(list_approved_procedures(db_path, scope=scope)),
        "episodes": _top_ids(list_approved_episodes(db_path, scope=scope)),
    }


def _source_lexical_retrieved_ids(db_path: Path, task: RetrievalEvalTask, *, scope: str | None) -> dict[str, list[int]]:
    tokens = _tokenize_query(task.query)
    if not tokens:
        return {memory_type: [] for memory_type in _MEMORY_TYPES}

    def _source_ids_for_model(model: object, memory_type: str) -> list[int]:
        if memory_type == "episodes":
            return list(model.source_ids)
        return list(model.evidence_ids)

    def _top_ids(models: list[object], memory_type: str) -> list[int]:
        source_ids = sorted({source_id for model in models for source_id in _source_ids_for_model(model, memory_type)})
        sources_by_id = {source.id: source for source in get_source_records_by_ids(db_path, source_ids)}
        scored = []
        for model in models:
            linked_sources = [sources_by_id[source_id] for source_id in _source_ids_for_model(model, memory_type) if source_id in sources_by_id]
            match_count = sum(_text_match_count(source.content, tokens) for source in linked_sources)
            if match_count <= 0:
                continue
            scored.append((-match_count, model.id, model.id))
        scored.sort()
        return [model_id for _neg_match_count, _sort_id, model_id in scored[: task.limit]]

    return {
        "facts": _top_ids(list_approved_facts(db_path, scope=scope), "facts"),
        "procedures": _top_ids(list_approved_procedures(db_path, scope=scope), "procedures"),
        "episodes": _top_ids(list_approved_episodes(db_path, scope=scope), "episodes"),
    }


def _evaluate_retrieved_ids(
    *,
    mode: str,
    task: RetrievalEvalTask,
    retrieved_ids: dict[str, list[int]],
) -> RetrievalEvalRunMetrics:
    expected = _expected_to_dict(task.expected)
    avoid = _expected_to_dict(task.avoid)

    expected_hits = {
        memory_type: [memory_id for memory_id in expected[memory_type] if memory_id in retrieved_ids[memory_type]]
        for memory_type in _MEMORY_TYPES
    }
    missing_expected = {
        memory_type: [memory_id for memory_id in expected[memory_type] if memory_id not in retrieved_ids[memory_type]]
        for memory_type in _MEMORY_TYPES
    }
    avoid_hits = {
        memory_type: [memory_id for memory_id in avoid[memory_type] if memory_id in retrieved_ids[memory_type]]
        for memory_type in _MEMORY_TYPES
    }

    pass_ = not any(missing_expected[memory_type] for memory_type in _MEMORY_TYPES) and not any(
        avoid_hits[memory_type] for memory_type in _MEMORY_TYPES
    )

    return RetrievalEvalRunMetrics(
        mode=mode,
        expected_hits=expected_hits,
        missing_expected=missing_expected,
        avoid_hits=avoid_hits,
        retrieved_ids=retrieved_ids,
        pass_=pass_,
    )



def _count_metric_ids(metric_ids: dict[str, list[int]]) -> int:
    return sum(len(metric_ids[memory_type]) for memory_type in _MEMORY_TYPES)



def _build_delta(current: RetrievalEvalRunMetrics, baseline: RetrievalEvalRunMetrics) -> RetrievalEvalDelta:
    return RetrievalEvalDelta(
        expected_hit_delta=_count_metric_ids(current.expected_hits) - _count_metric_ids(baseline.expected_hits),
        missing_expected_delta=_count_metric_ids(current.missing_expected) - _count_metric_ids(baseline.missing_expected),
        avoid_hit_delta=_count_metric_ids(current.avoid_hits) - _count_metric_ids(baseline.avoid_hits),
        pass_changed=current.pass_ != baseline.pass_,
    )



def _primary_task_memory_type(task: RetrievalEvalTask) -> str:
    expected = _expected_to_dict(task.expected)
    avoid = _expected_to_dict(task.avoid)

    expected_types = [memory_type for memory_type in _MEMORY_TYPES if expected[memory_type]]
    if len(expected_types) == 1:
        return expected_types[0]
    if len(expected_types) > 1:
        raise ValueError(f"task {task.id!r} must not expect multiple memory types for delta rollups")

    avoid_types = [memory_type for memory_type in _MEMORY_TYPES if avoid[memory_type]]
    if len(avoid_types) == 1:
        return avoid_types[0]
    if len(avoid_types) > 1:
        raise ValueError(f"task {task.id!r} must not avoid multiple memory types without an expected type")

    raise ValueError(f"task {task.id!r} must target at least one memory type for delta rollups")



def _build_delta_summary(task_results: list[tuple[str, RetrievalEvalTaskResult]]) -> RetrievalEvalDeltaSummary:
    summary = RetrievalEvalDeltaSummary(
        by_memory_type={memory_type: RetrievalEvalMemoryTypeDeltaSummary() for memory_type in _MEMORY_TYPES},
        by_primary_task_type={memory_type: RetrievalEvalMemoryTypeDeltaSummary() for memory_type in _MEMORY_TYPES},
    )
    for memory_type_key, result in task_results:
        if result.delta is None or result.baseline is None:
            continue
        pass_count_delta = int(result.pass_) - int(result.baseline.pass_)
        summary.total_expected_hit_delta += result.delta.expected_hit_delta
        summary.total_missing_expected_delta += result.delta.missing_expected_delta
        summary.total_avoid_hit_delta += result.delta.avoid_hit_delta
        summary.total_pass_count_delta += pass_count_delta

        type_summary = summary.by_memory_type[memory_type_key]
        type_summary.total_expected_hit_delta += result.delta.expected_hit_delta
        type_summary.total_missing_expected_delta += result.delta.missing_expected_delta
        type_summary.total_avoid_hit_delta += result.delta.avoid_hit_delta
        type_summary.total_pass_count_delta += pass_count_delta
        type_summary.tasks_with_pass_change += int(result.delta.pass_changed)

        primary_type_summary = summary.by_primary_task_type[memory_type_key]
        primary_type_summary.total_expected_hit_delta += result.delta.expected_hit_delta
        primary_type_summary.total_missing_expected_delta += result.delta.missing_expected_delta
        primary_type_summary.total_avoid_hit_delta += result.delta.avoid_hit_delta
        primary_type_summary.total_pass_count_delta += pass_count_delta
        primary_type_summary.tasks_with_pass_change += int(result.delta.pass_changed)
    return summary



def _evaluate_task(
    db_path: Path,
    task: RetrievalEvalTask,
    *,
    baseline_mode: str | None = None,
) -> RetrievalEvalTaskResult:
    packet = retrieve_memory_packet(
        db_path=db_path,
        query=task.query,
        limit=task.limit,
        preferred_scope=task.preferred_scope,
    )
    primary_metrics = _evaluate_retrieved_ids(
        mode="current",
        task=task,
        retrieved_ids=_retrieved_ids_for_task_result(packet),
    )
    retrieved_details = _with_policy_signals(
        _details_by_type(db_path, primary_metrics.retrieved_ids),
        _policy_signals_by_retrieved_id(packet),
    )
    expected_details = _details_by_type(db_path, _expected_to_dict(task.expected))
    avoid_hit_details = _details_by_type(db_path, primary_metrics.avoid_hits)

    baseline = None
    delta = None
    if baseline_mode in {"lexical", "lexical-global", "source-lexical", "source-global"}:
        if baseline_mode in {"source-lexical", "source-global"}:
            source_scope = task.preferred_scope if baseline_mode == "source-lexical" else None
            baseline_retrieved_ids = _source_lexical_retrieved_ids(
                db_path,
                task,
                scope=source_scope,
            )
        else:
            lexical_scope = task.preferred_scope if baseline_mode == "lexical" else None
            baseline_retrieved_ids = _lexical_retrieved_ids(db_path, task, scope=lexical_scope)

        baseline = _evaluate_retrieved_ids(
            mode=baseline_mode,
            task=task,
            retrieved_ids=baseline_retrieved_ids,
        )
        delta = _build_delta(primary_metrics, baseline)

    return RetrievalEvalTaskResult(
        task_id=task.id,
        query=task.query,
        preferred_scope=task.preferred_scope,
        limit=task.limit,
        rationale=task.rationale,
        notes=list(task.notes),
        expected_hits=primary_metrics.expected_hits,
        missing_expected=primary_metrics.missing_expected,
        avoid_hits=primary_metrics.avoid_hits,
        retrieved_ids=primary_metrics.retrieved_ids,
        retrieved_details=retrieved_details,
        expected_details=expected_details,
        avoid_hit_details=avoid_hit_details,
        pass_=primary_metrics.pass_,
        baseline=baseline,
        delta=delta,
    )


def _build_summary(task_metrics: list[tuple[str, RetrievalEvalRunMetrics]]) -> RetrievalEvalSummary:
    summary = RetrievalEvalSummary(
        total_tasks=len(task_metrics),
        by_memory_type={memory_type: RetrievalEvalMemoryTypeSummary() for memory_type in _MEMORY_TYPES},
        by_primary_task_type={memory_type: RetrievalEvalMemoryTypeSummary() for memory_type in _MEMORY_TYPES},
    )
    for primary_task_type, metrics in task_metrics:
        missing_count = sum(len(metrics.missing_expected[memory_type]) for memory_type in _MEMORY_TYPES)
        avoid_hit_count = sum(len(metrics.avoid_hits[memory_type]) for memory_type in _MEMORY_TYPES)
        expected_hit_count = sum(len(metrics.expected_hits[memory_type]) for memory_type in _MEMORY_TYPES)

        if metrics.pass_:
            summary.passed_tasks += 1
        else:
            summary.failed_tasks += 1

        if missing_count > 0:
            summary.tasks_with_missing_expected += 1
        if avoid_hit_count > 0:
            summary.tasks_with_avoid_hits += 1

        summary.total_expected_hits += expected_hit_count
        summary.total_missing_expected += missing_count
        summary.total_avoid_hits += avoid_hit_count

        primary_summary = summary.by_primary_task_type[primary_task_type]
        primary_summary.total_tasks += 1
        if metrics.pass_:
            primary_summary.passed_tasks += 1
        else:
            primary_summary.failed_tasks += 1
        if missing_count > 0:
            primary_summary.tasks_with_missing_expected += 1
        if avoid_hit_count > 0:
            primary_summary.tasks_with_avoid_hits += 1
        primary_summary.total_expected_hits += expected_hit_count
        primary_summary.total_missing_expected += missing_count
        primary_summary.total_avoid_hits += avoid_hit_count

        for memory_type in _MEMORY_TYPES:
            type_summary = summary.by_memory_type[memory_type]
            type_missing_count = len(metrics.missing_expected[memory_type])
            type_avoid_hit_count = len(metrics.avoid_hits[memory_type])
            type_expected_hit_count = len(metrics.expected_hits[memory_type])

            type_summary.total_tasks += 1 if (
                type_expected_hit_count > 0 or type_missing_count > 0 or type_avoid_hit_count > 0
            ) else 0
            if type_expected_hit_count > 0 or type_missing_count > 0 or type_avoid_hit_count > 0:
                if not metrics.missing_expected[memory_type] and not metrics.avoid_hits[memory_type]:
                    type_summary.passed_tasks += 1
                else:
                    type_summary.failed_tasks += 1

            if type_missing_count > 0:
                type_summary.tasks_with_missing_expected += 1
            if type_avoid_hit_count > 0:
                type_summary.tasks_with_avoid_hits += 1

            type_summary.total_expected_hits += type_expected_hit_count
            type_summary.total_missing_expected += type_missing_count
            type_summary.total_avoid_hits += type_avoid_hit_count
    return summary


def _signed_delta(value: int) -> str:
    return f"{value:+d}"


def _format_summary_line(prefix: str, summary: RetrievalEvalSummary) -> str:
    return (
        f"{prefix}: failures={summary.failed_tasks} "
        f"missing={summary.total_missing_expected} "
        f"avoid={summary.total_avoid_hits} "
        f"expected_hits={summary.total_expected_hits}"
    )


def _format_type_summary(memory_type: str, summary: RetrievalEvalMemoryTypeSummary) -> str:
    return (
        f"  {memory_type}: {summary.passed_tasks}/{summary.total_tasks} passed, "
        f"missing={summary.total_missing_expected}, avoid={summary.total_avoid_hits}"
    )


def _format_id_map(ids_by_type: dict[str, list[int]]) -> str:
    parts = [f"{memory_type}={ids_by_type[memory_type]}" for memory_type in _MEMORY_TYPES if ids_by_type.get(memory_type)]
    return ", ".join(parts) if parts else "none"


def _format_pass_label(passed: bool) -> str:
    return "pass" if passed else "fail"


def _append_detail_section(
    lines: list[str],
    title: str,
    details_by_type: dict[str, list[RetrievalEvalMemoryDetail]],
) -> None:
    details = [detail for memory_type in _MEMORY_TYPES for detail in details_by_type.get(memory_type, [])]
    if not details:
        return
    singular = {"facts": "fact", "procedures": "procedure", "episodes": "episode"}
    lines.append(f"    {title}:")
    for memory_type in _MEMORY_TYPES:
        for detail in details_by_type.get(memory_type, []):
            lines.append(
                f"      {singular[memory_type]} #{detail.id} [scope={detail.scope} status={detail.status}] {detail.snippet}"
            )
            if detail.policy_signals:
                lines.append(f"        policy: {' '.join(detail.policy_signals)}")


def _append_task_detail(lines: list[str], task: RetrievalEvalTaskResult, *, include_current: bool) -> None:
    lines.append(f"  - {task.task_id}")
    lines.append(f"    query: {task.query}")
    if include_current:
        lines.append(f"    missing: {_format_id_map(task.missing_expected)}")
        lines.append(f"    avoid: {_format_id_map(task.avoid_hits)}")
        _append_detail_section(lines, "retrieved details", task.retrieved_details)
        _append_detail_section(lines, "expected details", task.expected_details)
        _append_detail_section(lines, "avoid-hit details", task.avoid_hit_details)
    if task.baseline is not None:
        lines.append(f"    baseline: {_format_pass_label(task.baseline.pass_)}")
        lines.append(f"    baseline missing: {_format_id_map(task.baseline.missing_expected)}")
        lines.append(f"    baseline avoid: {_format_id_map(task.baseline.avoid_hits)}")
    if task.delta is not None:
        lines.append(
            "    delta: "
            f"expected_hits={_signed_delta(task.delta.expected_hit_delta)} "
            f"missing={_signed_delta(task.delta.missing_expected_delta)} "
            f"avoid={_signed_delta(task.delta.avoid_hit_delta)} "
            f"pass_changed={task.delta.pass_changed}"
        )


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    label = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {label}"


def _build_advisory_report(
    *,
    results: list[RetrievalEvalTaskResult],
    baseline_mode: str | None,
) -> RetrievalEvalAdvisoryReport:
    current_failure_task_ids = [task.task_id for task in results if not task.pass_]
    missing_task_ids = [task.task_id for task in results if any(task.missing_expected[memory_type] for memory_type in _MEMORY_TYPES)]
    avoid_hit_task_ids = [task.task_id for task in results if any(task.avoid_hits[memory_type] for memory_type in _MEMORY_TYPES)]
    baseline_weak_spot_task_ids = [
        task.task_id
        for task in results
        if task.pass_ and task.baseline is not None and not task.baseline.pass_
    ]
    current_regression_task_ids = [
        task.task_id
        for task in results
        if not task.pass_ and task.baseline is not None and task.baseline.pass_
    ]

    summary_parts: list[str] = []
    if current_failure_task_ids:
        summary_parts.append(f"{_plural(len(current_failure_task_ids), 'current task')} failed")
    if missing_task_ids:
        summary_parts.append(f"{_plural(len(missing_task_ids), 'task')} has missing expected memories")
    if avoid_hit_task_ids:
        summary_parts.append(f"{_plural(len(avoid_hit_task_ids), 'task')} has avoid-hit memories")
    if current_regression_task_ids and baseline_mode is not None:
        summary_parts.append(f"{_plural(len(current_regression_task_ids), 'current regression')} against {baseline_mode}")
    if baseline_weak_spot_task_ids and not current_failure_task_ids and baseline_mode is not None:
        summary_parts.append(f"{_plural(len(baseline_weak_spot_task_ids), 'baseline weak spot')} found against {baseline_mode}")

    recommended_actions: list[str] = []
    if current_failure_task_ids:
        recommended_actions.append("Inspect failed task details and compare retrieved_details against expected_details.")
    if missing_task_ids:
        recommended_actions.append("Seed or approve missing expected memories, or tighten fixture expectations if they are stale.")
    if avoid_hit_task_ids:
        recommended_actions.append("Review avoid-hit details for stale, cross-scope, or conflicting approved memories.")
    if current_regression_task_ids:
        recommended_actions.append("Compare current regressions against the selected baseline before merging retrieval changes.")
    if baseline_weak_spot_task_ids and not current_failure_task_ids:
        recommended_actions.append("Use baseline weak spots as coverage wins: keep the fixture checked in and watch for future regressions.")

    severity = "ok"
    if current_failure_task_ids or current_regression_task_ids:
        severity = "high"
    elif baseline_weak_spot_task_ids:
        severity = "medium"

    return RetrievalEvalAdvisoryReport(
        severity=severity,
        summary="; ".join(summary_parts) if summary_parts else "No retrieval advisory actions.",
        current_failure_task_ids=current_failure_task_ids,
        baseline_weak_spot_task_ids=baseline_weak_spot_task_ids,
        current_regression_task_ids=current_regression_task_ids,
        recommended_actions=recommended_actions,
        baseline_mode=baseline_mode,
    )


def render_retrieval_eval_text_report(result_set: RetrievalEvalResultSet) -> str:
    summary = result_set.summary
    lines = [
        f"Retrieval evaluation: {summary.passed_tasks}/{summary.total_tasks} tasks passed",
        _format_summary_line("current", summary),
    ]

    if result_set.baseline_summary is not None:
        baseline = result_set.baseline_summary
        lines.append(f"baseline {baseline.mode}: {baseline.passed_tasks}/{baseline.total_tasks} tasks passed")
    if result_set.delta_summary is not None:
        delta = result_set.delta_summary
        lines.append(
            "delta: "
            f"pass_count={_signed_delta(delta.total_pass_count_delta)} "
            f"expected_hits={_signed_delta(delta.total_expected_hit_delta)} "
            f"missing={_signed_delta(delta.total_missing_expected_delta)} "
            f"avoid={_signed_delta(delta.total_avoid_hit_delta)}"
        )

    lines.append("by primary task type:")
    for memory_type in _MEMORY_TYPES:
        type_summary = summary.by_primary_task_type.get(memory_type, RetrievalEvalMemoryTypeSummary())
        lines.append(_format_type_summary(memory_type, type_summary))

    failed_tasks = [task for task in result_set.results if not task.pass_]
    if failed_tasks:
        lines.append("failed tasks:")
        for task in failed_tasks:
            _append_task_detail(lines, task, include_current=True)
    else:
        lines.append("failed tasks: none")

    if result_set.baseline_summary is not None:
        baseline_weak_spots = [task for task in result_set.results if task.pass_ and task.baseline is not None and not task.baseline.pass_]
        current_regressions = [task for task in result_set.results if not task.pass_ and task.baseline is not None and task.baseline.pass_]
        if baseline_weak_spots:
            lines.append("baseline weak spots:")
            for task in baseline_weak_spots:
                _append_task_detail(lines, task, include_current=False)
        else:
            lines.append("baseline weak spots: none")
        if current_regressions:
            lines.append("current regressions vs baseline:")
            for task in current_regressions:
                _append_task_detail(lines, task, include_current=True)
        else:
            lines.append("current regressions vs baseline: none")

    if result_set.advisories:
        lines.append("advisories:")
        lines.extend(f"  - {advisory.code}: {advisory.message}" for advisory in result_set.advisories)

    advisory_report = result_set.advisory_report
    lines.append(f"advisory report: {advisory_report.severity} - {advisory_report.summary}")
    if advisory_report.recommended_actions:
        lines.append("recommended actions:")
        lines.extend(f"  - {action}" for action in advisory_report.recommended_actions)

    return "\n".join(lines)


def evaluate_retrieval_fixtures(
    db_path: Path | str,
    fixtures_path: Path | str,
    *,
    baseline_mode: str | None = None,
    fail_on_regression: bool = False,
    warn_on_regression_threshold: int | None = None,
    fail_on_baseline_regression: bool = False,
    warn_on_baseline_regression_threshold: int | None = None,
    fail_on_baseline_regression_memory_types: list[str] | None = None,
) -> RetrievalEvalResultSet:
    resolved_db_path = _normalize_path(db_path)
    fixture_paths = _resolve_fixture_paths(fixtures_path)
    results: list[RetrievalEvalTaskResult] = []
    delta_rollup_inputs: list[tuple[str, RetrievalEvalTaskResult]] = []
    task_result_inputs: list[tuple[str, RetrievalEvalTaskResult]] = []

    if warn_on_regression_threshold is not None and warn_on_regression_threshold < 0:
        raise ValueError("warn_on_regression_threshold must be non-negative")
    if warn_on_baseline_regression_threshold is not None and warn_on_baseline_regression_threshold < 0:
        raise ValueError("warn_on_baseline_regression_threshold must be non-negative")

    selected_baseline_regression_memory_types = (
        set(fail_on_baseline_regression_memory_types) if fail_on_baseline_regression_memory_types is not None else None
    )
    if selected_baseline_regression_memory_types is not None:
        unknown_memory_types = selected_baseline_regression_memory_types.difference(_MEMORY_TYPES)
        if unknown_memory_types:
            joined_unknown = ", ".join(sorted(unknown_memory_types))
            raise ValueError(f"unknown baseline regression memory types: {joined_unknown}")

    for fixture_path in fixture_paths:
        fixture = _resolve_fixture_references(resolved_db_path, _load_fixture(fixture_path))
        for task in fixture.tasks:
            task_result = _evaluate_task(resolved_db_path, task, baseline_mode=baseline_mode)
            primary_task_type = _primary_task_memory_type(task)
            results.append(task_result)
            delta_rollup_inputs.append((primary_task_type, task_result))
            task_result_inputs.append((primary_task_type, task_result))

    summary = _build_summary(
        [
            (
                primary_task_type,
                RetrievalEvalRunMetrics(
                    mode="current",
                    expected_hits=result.expected_hits,
                    missing_expected=result.missing_expected,
                    avoid_hits=result.avoid_hits,
                    retrieved_ids=result.retrieved_ids,
                    pass_=result.pass_,
                ),
            )
            for primary_task_type, result in task_result_inputs
        ]
    )

    baseline_summary = None
    if baseline_mode is not None:
        baseline_metrics = [
            (primary_task_type, result.baseline)
            for primary_task_type, result in task_result_inputs
            if result.baseline is not None
        ]
        baseline_rollup = _build_summary(baseline_metrics)
        baseline_summary = RetrievalEvalBaselineSummary(mode=baseline_mode, **baseline_rollup.model_dump())

    delta_summary = _build_delta_summary(delta_rollup_inputs) if baseline_mode is not None else None

    baseline_regression_task_ids = [
        result.task_id
        for primary_task_type, result in task_result_inputs
        if result.baseline is not None
        and result.baseline.pass_
        and not result.pass_
        and (
            selected_baseline_regression_memory_types is None
            or primary_task_type in selected_baseline_regression_memory_types
        )
    ]
    current_regression_task_ids = [result.task_id for result in results if not result.pass_]

    advisories: list[RetrievalEvalAdvisory] = []
    if warn_on_regression_threshold is not None and len(current_regression_task_ids) > warn_on_regression_threshold:
        advisories.append(
            RetrievalEvalAdvisory(
                code="regression-threshold-exceeded",
                message=(
                    f"Current retrieval has {len(current_regression_task_ids)} failing tasks, "
                    f"which exceeds the soft threshold of {warn_on_regression_threshold}."
                ),
                observed=len(current_regression_task_ids),
                threshold=warn_on_regression_threshold,
                task_ids=current_regression_task_ids,
                baseline_mode=None,
            )
        )
    if warn_on_baseline_regression_threshold is not None:
        if baseline_mode is None:
            raise ValueError("warn_on_baseline_regression_threshold requires baseline_mode")
        if len(baseline_regression_task_ids) > warn_on_baseline_regression_threshold:
            advisories.append(
                RetrievalEvalAdvisory(
                    code="baseline-regression-threshold-exceeded",
                    message=(
                        f"Current retrieval is worse than the {baseline_mode} baseline on "
                        f"{len(baseline_regression_task_ids)} tasks, which exceeds the soft threshold of "
                        f"{warn_on_baseline_regression_threshold}."
                    ),
                    observed=len(baseline_regression_task_ids),
                    threshold=warn_on_baseline_regression_threshold,
                    task_ids=baseline_regression_task_ids,
                    baseline_mode=baseline_mode,
                )
            )

    result_set = RetrievalEvalResultSet(
        fixture_paths=[str(path) for path in fixture_paths],
        summary=summary,
        results=results,
        baseline_mode=baseline_mode,
        baseline_summary=baseline_summary,
        delta_summary=delta_summary,
        advisories=advisories,
        advisory_report=_build_advisory_report(results=results, baseline_mode=baseline_mode),
    )
    if fail_on_baseline_regression or selected_baseline_regression_memory_types is not None:
        if baseline_mode is None:
            raise ValueError("fail_on_baseline_regression requires baseline_mode")
        if baseline_regression_task_ids:
            raise RetrievalEvalRegressionError(baseline_regression_task_ids, result_set=result_set)
    if fail_on_regression:
        if current_regression_task_ids:
            raise RetrievalEvalRegressionError(current_regression_task_ids, result_set=result_set)
    return result_set
