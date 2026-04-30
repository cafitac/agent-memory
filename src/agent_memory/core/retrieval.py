from __future__ import annotations

from pathlib import Path

from agent_memory.core.models import (
    DecisionSummary,
    MemoryPacket,
    MemoryStatus,
    MemoryTrustSummary,
    PolicyHint,
    ProvenanceSummary,
    VerificationPlan,
    VerificationStep,
)
from agent_memory.storage.sqlite import (
    get_source_records_by_ids,
    record_memory_retrieval,
    record_retrieval_observation,
    search_ranked_approved_episodes,
    search_ranked_approved_facts,
    search_ranked_approved_procedures,
    search_ranked_episodes,
    search_ranked_facts,
    search_ranked_procedures,
    search_relations_for_refs,
    search_relations_matching_query,
)


def _clamp_unit(value: float) -> float:
    return max(0.0, min(1.0, value))


def _review_risk_score(*, conflict_count: int, hidden_alternative_count: int) -> float:
    return _clamp_unit((0.35 * conflict_count) + (0.15 * hidden_alternative_count))


def _uncertainty_score(
    *,
    rank_value: float,
    review_risk_score: float,
    text_match_count: int,
    relation_match_count: int,
    reinforcement_score: float,
) -> float:
    support_penalty = 0.2 if text_match_count == 0 and relation_match_count == 0 else 0.0
    confidence_risk = 1.0 - _clamp_unit(rank_value)
    reinforcement_credit = min(0.25, reinforcement_score * 0.1)
    return _clamp_unit((confidence_risk * 0.6) + (review_risk_score * 0.3) + support_penalty - reinforcement_credit)


def _trust_band(uncertainty_score: float) -> str:
    if uncertainty_score <= 0.25:
        return "high"
    if uncertainty_score <= 0.6:
        return "medium"
    return "low"


def _build_trust_summaries(packet_trace):
    trust_summaries: list[MemoryTrustSummary] = []
    for trace in packet_trace:
        review_risk_score = _review_risk_score(
            conflict_count=trace.conflict_count,
            hidden_alternative_count=trace.hidden_alternative_count,
        )
        uncertainty_score = _uncertainty_score(
            rank_value=trace.rank_value,
            review_risk_score=review_risk_score,
            text_match_count=trace.text_match_count,
            relation_match_count=trace.relation_match_count,
            reinforcement_score=trace.reinforcement_score,
        )
        trust_summaries.append(
            MemoryTrustSummary(
                memory_type=trace.memory_type,
                memory_id=trace.memory_id,
                label=trace.label,
                uncertainty_score=uncertainty_score,
                review_risk_score=review_risk_score,
                has_hidden_alternatives=trace.hidden_alternative_count > 0,
                trust_band=_trust_band(uncertainty_score),
            )
        )
    return trust_summaries


def _build_working_hints(packet_trace, trust_summaries):
    if not packet_trace or not trust_summaries:
        return []

    top_trace = packet_trace[0]
    top_trust = trust_summaries[0]
    hints = [
        f"Use {top_trace.memory_type} #{top_trace.memory_id} ({top_trace.label}) with {top_trust.trust_band} trust.",
    ]
    if top_trust.has_hidden_alternatives:
        count = top_trace.hidden_alternative_count
        noun = "alternative exists" if count == 1 else "alternatives exist"
        hints.append(f"Mention that {count} hidden {noun} behind the top memory.")
        hints.append("Cross-check this memory against hidden alternatives before asserting a final answer.")
    else:
        hints.append("No hidden alternatives detected for the top memory.")

    if top_trust.trust_band == "medium":
        hints.append("Mention uncertainty when presenting this memory.")
    elif top_trust.trust_band == "low":
        hints.append("Avoid definitive claims until corroborating evidence is found.")
    return hints


def _build_policy_hints(packet_trace, trust_summaries):
    if not packet_trace or not trust_summaries:
        return []

    top_trace = packet_trace[0]
    top_trust = trust_summaries[0]
    policy_hints = [
        PolicyHint(
            action="prefer",
            target_memory_type=top_trace.memory_type,
            target_memory_id=top_trace.memory_id,
            target_label=top_trace.label,
            severity=top_trust.trust_band,
            reason_code="top_ranked_memory",
            message=f"Use {top_trace.memory_type} #{top_trace.memory_id} ({top_trace.label}) with {top_trust.trust_band} trust.",
        )
    ]
    if top_trust.has_hidden_alternatives:
        count = top_trace.hidden_alternative_count
        noun = "alternative exists" if count == 1 else "alternatives exist"
        policy_hints.append(
            PolicyHint(
                action="surface_hidden_alternatives",
                target_memory_type=top_trace.memory_type,
                target_memory_id=top_trace.memory_id,
                target_label=top_trace.label,
                severity="medium",
                reason_code="hidden_alternatives_present",
                message=f"Mention that {count} hidden {noun} behind the top memory.",
            )
        )
        policy_hints.append(
            PolicyHint(
                action="cross_check",
                target_memory_type=top_trace.memory_type,
                target_memory_id=top_trace.memory_id,
                target_label=top_trace.label,
                severity="high",
                reason_code="hidden_alternatives_present",
                message="Cross-check this memory against hidden alternatives before asserting a final answer.",
            )
        )
    else:
        policy_hints.append(
            PolicyHint(
                action="no_hidden_alternatives",
                target_memory_type=top_trace.memory_type,
                target_memory_id=top_trace.memory_id,
                target_label=top_trace.label,
                severity="low",
                reason_code="no_hidden_alternatives_detected",
                message="No hidden alternatives detected for the top memory.",
            )
        )

    if top_trust.trust_band == "medium":
        policy_hints.append(
            PolicyHint(
                action="mention_uncertainty",
                target_memory_type=top_trace.memory_type,
                target_memory_id=top_trace.memory_id,
                target_label=top_trace.label,
                severity="medium",
                reason_code="medium_uncertainty",
                message="Mention uncertainty when presenting this memory.",
            )
        )
    elif top_trust.trust_band == "low":
        policy_hints.append(
            PolicyHint(
                action="avoid_definitive",
                target_memory_type=top_trace.memory_type,
                target_memory_id=top_trace.memory_id,
                target_label=top_trace.label,
                severity="high",
                reason_code="low_trust_requires_corroboration",
                message="Avoid definitive claims until corroborating evidence is found.",
            )
        )
    return policy_hints


def _build_decision_summary(packet_trace, trust_summaries, policy_hints):
    if not packet_trace or not trust_summaries or not policy_hints:
        return None

    top_trace = packet_trace[0]
    top_trust = trust_summaries[0]
    reason_codes: list[str] = []
    for hint in policy_hints:
        if hint.reason_code not in reason_codes:
            reason_codes.append(hint.reason_code)

    requires_cross_check = any(hint.action == "cross_check" for hint in policy_hints)
    should_mention_uncertainty = any(hint.action == "mention_uncertainty" for hint in policy_hints)
    should_avoid_definitive = any(hint.action == "avoid_definitive" for hint in policy_hints)

    if requires_cross_check or should_avoid_definitive:
        recommended_answer_mode = "verify_first"
    elif should_mention_uncertainty or top_trust.trust_band == "medium":
        recommended_answer_mode = "cautious"
    else:
        recommended_answer_mode = "direct"

    return DecisionSummary(
        recommended_answer_mode=recommended_answer_mode,
        target_memory_type=top_trace.memory_type,
        target_memory_id=top_trace.memory_id,
        target_label=top_trace.label,
        trust_band=top_trust.trust_band,
        has_hidden_alternatives=top_trust.has_hidden_alternatives,
        should_mention_uncertainty=should_mention_uncertainty,
        requires_cross_check=requires_cross_check,
        should_avoid_definitive=should_avoid_definitive,
        reason_codes=reason_codes,
    )


def _build_verification_plan(packet_trace, decision_summary: DecisionSummary | None) -> VerificationPlan:
    if decision_summary is None:
        return VerificationPlan()

    steps: list[VerificationStep] = []
    alternative_memory_ids = [
        trace.memory_id
        for trace in packet_trace[1:]
        if trace.memory_type == decision_summary.target_memory_type
    ]

    if decision_summary.requires_cross_check:
        has_ranked_alternatives = len(alternative_memory_ids) > 0
        comparison_target = "ranked alternatives" if has_ranked_alternatives else "hidden alternatives"
        steps.append(
            VerificationStep(
                action="cross_check_hidden_alternatives",
                severity="high",
                target_memory_type=decision_summary.target_memory_type,
                target_memory_id=decision_summary.target_memory_id,
                target_label=decision_summary.target_label,
                reason_code="hidden_alternatives_present",
                blocking=True,
                compare_against_memory_ids=alternative_memory_ids,
                instruction=(
                    f"Cross-check {decision_summary.target_memory_type} #{decision_summary.target_memory_id} "
                    f"({decision_summary.target_label}) against {comparison_target} before asserting a final answer."
                ),
            )
        )

    if decision_summary.should_avoid_definitive:
        steps.append(
            VerificationStep(
                action="corroborate_before_answer",
                severity="high",
                target_memory_type=decision_summary.target_memory_type,
                target_memory_id=decision_summary.target_memory_id,
                target_label=decision_summary.target_label,
                reason_code="low_trust_requires_corroboration",
                blocking=True,
                instruction=(
                    f"Corroborate {decision_summary.target_memory_type} #{decision_summary.target_memory_id} "
                    f"({decision_summary.target_label}) before making a definitive claim."
                ),
            )
        )

    return VerificationPlan(
        required=any(step.blocking for step in steps),
        fallback_answer_mode="verify_first" if steps else decision_summary.recommended_answer_mode,
        steps=steps,
    )


def retrieve_memory_packet(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
    statuses: tuple[MemoryStatus, ...] = ("approved",),
    record_retrievals: bool = True,
    observation_surface: str | None = None,
    observation_metadata: dict[str, object] | None = None,
) -> MemoryPacket:
    if statuses == ("approved",):
        ranked_facts = search_ranked_approved_facts(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
        ranked_procedures = search_ranked_approved_procedures(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
        ranked_episodes = search_ranked_approved_episodes(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
    else:
        ranked_facts = search_ranked_facts(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
            statuses=statuses,
        )
        ranked_procedures = search_ranked_procedures(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
            statuses=statuses,
        )
        ranked_episodes = search_ranked_episodes(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
            statuses=statuses,
        )

    semantic_facts = [fact for fact, _trace in ranked_facts]
    procedural_guidance = [procedure for procedure, _trace in ranked_procedures]
    episodic_context = [episode for episode, _trace in ranked_episodes]
    retrieval_trace = [
        *[trace for _fact, trace in ranked_facts],
        *[trace for _procedure, trace in ranked_procedures],
        *[trace for _episode, trace in ranked_episodes],
    ]

    related_refs = [fact.subject_ref for fact in semantic_facts]
    for fact in semantic_facts:
        related_refs.append(fact.object_ref_or_value)
    for procedure in procedural_guidance:
        related_refs.append(procedure.name)
    for episode in episodic_context:
        related_refs.extend(episode.tags)
        related_refs.append(episode.title)

    related_relation_pool = search_relations_for_refs(db_path, refs=related_refs, limit=limit * 2)
    query_relations = search_relations_matching_query(db_path, query=query, limit=limit * 2)

    seen_relation_ids: set[int] = set()
    related_relations = []
    for relation in [*query_relations, *related_relation_pool]:
        if relation.id in seen_relation_ids:
            continue
        seen_relation_ids.add(relation.id)
        related_relations.append(relation)
        if len(related_relations) >= limit:
            break

    source_ids: set[int] = set()
    for fact in semantic_facts:
        source_ids.update(fact.evidence_ids)
    for procedure in procedural_guidance:
        source_ids.update(procedure.evidence_ids)
    for episode in episodic_context:
        source_ids.update(episode.source_ids)
    for relation in related_relations:
        source_ids.update(relation.evidence_ids)

    provenance = [
        ProvenanceSummary(
            source_id=source.id,
            source_type=source.source_type,
            created_at=source.created_at,
            excerpt=source.content[:200],
            metadata=source.metadata,
        )
        for source in get_source_records_by_ids(db_path, sorted(source_ids))
    ]

    retrieval_trace.sort(
        key=lambda trace: (
            -trace.total_score,
            trace.scope_priority,
            -max(trace.text_match_count, trace.relation_match_count),
            -trace.relation_match_count,
            -trace.recency_score,
            -trace.reinforcement_score,
            -trace.rank_value,
            trace.memory_id,
        )
    )
    trust_summaries = _build_trust_summaries(retrieval_trace)
    working_hints = _build_working_hints(retrieval_trace, trust_summaries)
    policy_hints = _build_policy_hints(retrieval_trace, trust_summaries)
    decision_summary = _build_decision_summary(retrieval_trace, trust_summaries, policy_hints)
    verification_plan = _build_verification_plan(retrieval_trace, decision_summary)

    if statuses != ("approved",):
        statuses_label = ", ".join(statuses)
        working_hints.insert(
            0,
            f"Forensic retrieval includes non-default statuses ({statuses_label}); do not use it as normal answer memory without review.",
        )
        verification_plan = VerificationPlan(
            required=True,
            fallback_answer_mode="verify_first",
            steps=[
                VerificationStep(
                    action="corroborate_before_answer",
                    severity="high",
                    blocking=True,
                    instruction="Forensic retrieval may include candidate, disputed, or deprecated memories; corroborate before making definitive claims.",
                )
            ],
        )

    if record_retrievals:
        for fact in semantic_facts:
            if fact.status == "approved":
                record_memory_retrieval(db_path, memory_type="fact", memory_id=fact.id)
        for procedure in procedural_guidance:
            if procedure.status == "approved":
                record_memory_retrieval(db_path, memory_type="procedure", memory_id=procedure.id)
        for episode in episodic_context:
            if episode.status == "approved":
                record_memory_retrieval(db_path, memory_type="episode", memory_id=episode.id)

    if observation_surface:
        try:
            record_retrieval_observation(
                db_path,
                surface=observation_surface,
                query=query,
                preferred_scope=preferred_scope,
                limit=limit,
                statuses=statuses,
                retrieval_trace=retrieval_trace,
                response_mode=decision_summary.recommended_answer_mode if decision_summary is not None else None,
                metadata=observation_metadata,
            )
        except Exception:
            pass

    return MemoryPacket(
        query=query,
        working_hints=working_hints,
        policy_hints=policy_hints,
        decision_summary=decision_summary,
        verification_plan=verification_plan,
        episodic_context=episodic_context,
        semantic_facts=semantic_facts,
        procedural_guidance=procedural_guidance,
        related_relations=related_relations,
        provenance=provenance,
        retrieval_trace=retrieval_trace,
        trust_summaries=trust_summaries,
    )
