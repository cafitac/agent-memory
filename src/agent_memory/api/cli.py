from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from agent_memory import __version__
from agent_memory.adapters import (
    HermesVerificationResult,
    apply_hermes_verification_results,
    prepare_hermes_memory_context,
)
from agent_memory.integrations.hermes_hooks import (
    HermesHookConfigSnippetOptions,
    HermesHookInstallOptions,
    HermesPreLlmHookOptions,
    build_hermes_hook_config_snippet,
    build_pre_llm_hook_context,
    diagnose_hermes_hook_setup,
    install_hermes_hook_config,
    load_hermes_shell_hook_payload,
)
from agent_memory.core.curation import (
    approve_fact,
    approve_memory,
    approve_procedure,
    create_candidate_fact,
    create_candidate_procedure,
    create_episode,
    create_fact_conflict_relation,
    deprecate_memory,
    dispute_memory,
    supersede_fact,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.kb_export import export_kb_markdown
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.core.retrieval_eval import (
    RetrievalEvalRegressionError,
    evaluate_retrieval_fixtures,
    render_retrieval_eval_text_report,
)
from agent_memory.storage.sqlite import (
    build_trace_retention_report,
    connect,
    get_fact,
    get_memory_status,
    initialize_database,
    insert_experience_trace,
    insert_relation,
    list_candidate_episodes,
    list_candidate_facts,
    list_candidate_procedures,
    list_experience_traces,
    list_fact_conflict_relations,
    list_fact_replacement_relations,
    list_memory_activations,
    list_facts_by_claim_slot,
    list_memory_status_history,
    list_relations_for_node,
    list_retrieval_observations,
)


def _dump_models(models: list[Any]) -> str:
    return json.dumps([model.model_dump(mode="json") for model in models], indent=2)


def _json_list(value: str, *, argument_name: str) -> list[Any]:
    parsed = json.loads(value)
    if not isinstance(parsed, list):
        raise ValueError(f"{argument_name} must be a JSON list")
    return parsed


def _trace_content_sha256(*, explicit_hash: str | None, summary: str | None) -> str:
    if explicit_hash:
        return explicit_hash
    if summary:
        return hashlib.sha256(summary.encode("utf-8")).hexdigest()
    raise ValueError("traces record requires --summary or --content-sha256")


def _trace_filters_payload(*, surface: str | None, event_kind: str | None, scope: str | None) -> dict[str, str]:
    return {
        key: value
        for key, value in {
            "surface": surface,
            "event_kind": event_kind,
            "scope": scope,
        }.items()
        if value is not None
    }


_SECRET_LIKE_REPORT_MARKERS: tuple[str, ...] = (
    "api_key",
    "api-key",
    "token=",
    "token:",
    "secret=",
    "secret:",
    "password=",
    "password:",
    "credential=",
    "credential:",
    "connection_string=",
    "connection-string=",
    "bearer ",
)


def _contains_secret_like_report_text(value: str | None) -> bool:
    if value is None:
        return False
    lowered = value.lower()
    return any(marker in lowered for marker in _SECRET_LIKE_REPORT_MARKERS)


def _remember_intent_trace_is_review_ready(trace: Any) -> bool:
    metadata = trace.metadata
    return (
        trace.event_kind == "remember_intent"
        and trace.retention_policy == "review"
        and metadata.get("candidate_policy") == "review_required"
        and metadata.get("auto_approved") is False
        and metadata.get("secret_scan") == "passed"
        and not _contains_secret_like_report_text(trace.summary)
    )


def _remember_intent_sample_payload(trace: Any) -> dict[str, Any]:
    metadata = trace.metadata
    return {
        "trace_id": trace.id,
        "scope": trace.scope,
        "summary": trace.summary,
        "candidate_policy": metadata.get("candidate_policy"),
        "auto_approved": metadata.get("auto_approved"),
        "secret_scan": metadata.get("secret_scan"),
    }


def _remember_intent_dogfood_report(db_path: Path, *, limit: int = 200, sample_limit: int = 10) -> dict[str, Any]:
    traces = list_experience_traces(db_path, limit=limit)
    remember_traces = [trace for trace in traces if trace.event_kind == "remember_intent"]
    ordinary_turns = [trace for trace in traces if trace.event_kind == "turn"]
    review_ready_traces = [trace for trace in remember_traces if _remember_intent_trace_is_review_ready(trace)]
    safe_samples = review_ready_traces[:sample_limit]
    scope_counts = Counter(trace.scope or "unspecified" for trace in remember_traces)
    unsafe_sample_count = len(remember_traces) - len(review_ready_traces)
    suggested_next_steps = [
        "Review remember_intent samples and their consolidation candidate explanations before enabling G2 auto-approval.",
        "Keep G2 default-off and require policy, conflict preflight, audit history, and rollback/review commands.",
    ]
    if unsafe_sample_count:
        suggested_next_steps.insert(1, "Inspect unsafe remember_intent counts before trusting any automation policy.")
    return {
        "kind": "remember_intent_dogfood_report",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "limit": limit,
        "sample_limit": sample_limit,
        "trace_counts": {
            "total": len(traces),
            "remember_intent": len(remember_traces),
            "ordinary_turn": len(ordinary_turns),
            "other": len(traces) - len(remember_traces) - len(ordinary_turns),
        },
        "review_ready_count": len(review_ready_traces),
        "unsafe_sample_count": unsafe_sample_count,
        "scopes": dict(sorted(scope_counts.items())),
        "samples": [_remember_intent_sample_payload(trace) for trace in safe_samples],
        "suggested_next_steps": suggested_next_steps,
    }


_REMEMBER_PREFERENCE_POLICIES = {"remember-preferences-v1"}


def _remember_preference_object_from_summary(summary: str | None) -> str | None:
    if not summary:
        return None
    stripped = summary.strip()
    for prefix in ("User prefers ", "I prefer "):
        if stripped.lower().startswith(prefix.lower()):
            value = stripped[len(prefix) :].strip()
            return value or None
    return None


def _remember_preference_auto_approval_candidate(db_path: Path, trace: Any, *, scope: str) -> dict[str, Any]:
    reason_codes: list[str] = []
    proposed_object = _remember_preference_object_from_summary(trace.summary)
    if trace.event_kind != "remember_intent":
        reason_codes.append("not_remember_intent")
    if trace.scope != scope:
        reason_codes.append("scope_not_allowed")
    if not _remember_intent_trace_is_review_ready(trace):
        reason_codes.append("not_review_ready")
    if _contains_secret_like_report_text(trace.summary):
        reason_codes = ["secret_like_summary"]
    if proposed_object is None and "secret_like_summary" not in reason_codes:
        reason_codes.append("unsupported_preference_shape")
    proposed_fact = None
    conflict_preflight = None
    if proposed_object is not None and not reason_codes:
        proposed_fact = {
            "subject_ref": "user",
            "predicate": "prefers",
            "object_ref_or_value": proposed_object,
            "scope": scope,
        }
        conflict_preflight = _promotion_conflict_preflight(
            db_path,
            subject_ref="user",
            predicate="prefers",
            object_ref_or_value=proposed_object,
            scope=scope,
            allow_conflict=False,
        )
        if conflict_preflight["result"] == "blocked":
            reason_codes = ["claim_slot_conflict"]
    if reason_codes:
        payload: dict[str, Any] = {
            "trace_id": trace.id,
            "scope": trace.scope,
            "decision": "blocked",
            "reason_codes": reason_codes,
        }
        if conflict_preflight is not None and reason_codes == ["claim_slot_conflict"]:
            payload["conflict_preflight"] = conflict_preflight
        return payload
    return {
        "trace_id": trace.id,
        "scope": trace.scope,
        "decision": "eligible",
        "reason_codes": ["explicit_review_ready_remember_preference"],
        "summary": trace.summary,
        "proposed_fact": proposed_fact,
        "conflict_preflight": conflict_preflight,
    }


def _remember_preference_auto_approval_report(
    db_path: Path,
    *,
    policy: str,
    scope: str,
    apply: bool,
    actor: str | None,
    reason: str | None,
    limit: int,
) -> dict[str, Any]:
    if policy not in _REMEMBER_PREFERENCE_POLICIES:
        raise ValueError("unsupported auto-approval policy")
    if not scope:
        raise ValueError("--scope is required for remember preference auto-approval")
    if apply and (not actor or not reason):
        raise ValueError("--apply requires --actor and --reason for audit history")
    traces = list_experience_traces(db_path, limit=limit, event_kind="remember_intent")
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    approved: list[dict[str, Any]] = []
    trace_by_id = {trace.id: trace for trace in traces}
    for trace in traces:
        candidate = _remember_preference_auto_approval_candidate(db_path, trace, scope=scope)
        if candidate["decision"] == "blocked":
            if "not_review_ready" in candidate["reason_codes"] and candidate["reason_codes"] != ["secret_like_summary"]:
                continue
            blocked.append(candidate)
            continue
        if not apply:
            preview = dict(candidate)
            preview["decision"] = "would_approve"
            candidates.append(preview)
            continue
        trace_for_apply = trace_by_id[candidate["trace_id"]]
        proposed_fact = candidate["proposed_fact"]
        source = ingest_source_text(
            db_path,
            source_type="remember_intent_trace",
            content=trace_for_apply.summary or "remember preference",
            adapter="agent-memory-g2-auto-approval",
            external_ref=f"experience_trace:{trace_for_apply.id}",
            metadata={
                "trace_id": trace_for_apply.id,
                "policy": policy,
                "sanitized": True,
            },
        )
        fact = create_candidate_fact(
            db_path,
            subject_ref=proposed_fact["subject_ref"],
            predicate=proposed_fact["predicate"],
            object_ref_or_value=proposed_fact["object_ref_or_value"],
            evidence_ids=[source.id],
            scope=proposed_fact["scope"],
            confidence=0.8,
        )
        approved_fact = approve_memory(
            db_path,
            memory_type="fact",
            memory_id=fact.id,
            reason=reason,
            actor=actor,
            evidence_ids=[source.id],
        )
        relation = insert_relation(
            db_path,
            from_ref=f"experience_trace:{trace_for_apply.id}",
            relation_type="auto_approved_as",
            to_ref=f"fact:{approved_fact.id}",
            evidence_ids=[source.id],
            confidence=0.8,
            review_actor=actor,
            review_reason=reason,
        )
        approved.append(
            {
                "trace_id": trace_for_apply.id,
                "memory_ref": f"fact:{approved_fact.id}",
                "source_id": source.id,
                "relation_id": relation.id,
                "proposed_fact": proposed_fact,
                "audit": {"actor": actor, "reason": reason, "policy": policy},
            }
        )
    mutated = bool(approved)
    return {
        "kind": "remember_preference_auto_approval_report",
        "policy": policy,
        "apply": apply,
        "read_only": not apply,
        "mutated": mutated,
        "default_retrieval_unchanged": not mutated,
        "scope": scope,
        "limit": limit,
        "eligible_count": len(candidates) if not apply else len(approved),
        "approved_count": len(approved),
        "blocked_count": len(blocked),
        "candidates": candidates,
        "approved": approved,
        "blocked": blocked,
        "guardrails": {
            "default_off": True,
            "requires_apply": True,
            "requires_actor_reason": True,
            "allowed_memory_type": "fact",
            "allowed_predicate": "prefers",
            "conflict_preflight": True,
            "secret_like_summaries_blocked": True,
        },
        "suggested_next_steps": [
            "Review approved auto-approval audit history with review explain before broadening policy.",
            "Keep this policy narrow and default-off until live dogfood evidence supports expansion.",
        ],
    }


def _fact_replacement_relation_payload(relation) -> dict[str, Any]:
    def parse_fact_ref(value: str) -> int | None:
        prefix = "fact:"
        if not value.startswith(prefix):
            return None
        return int(value[len(prefix) :])

    if relation.relation_type == "superseded_by":
        superseded_fact_id = parse_fact_ref(relation.from_ref)
        replacement_fact_id = parse_fact_ref(relation.to_ref)
    elif relation.relation_type == "replaces":
        superseded_fact_id = parse_fact_ref(relation.to_ref)
        replacement_fact_id = parse_fact_ref(relation.from_ref)
    else:
        superseded_fact_id = None
        replacement_fact_id = None

    return {
        "relation_id": relation.id,
        "superseded_fact_id": superseded_fact_id,
        "replacement_fact_id": replacement_fact_id,
        "relation_type": relation.relation_type,
        "evidence_ids": relation.evidence_ids,
    }


def _fact_replacement_chain_payload(relations, *, fact_id: int) -> dict[str, list[dict[str, Any]]]:
    chain = {"superseded_by": [], "replaces": []}
    for relation in relations:
        payload = _fact_replacement_relation_payload(relation)
        if payload["superseded_fact_id"] == fact_id:
            chain["superseded_by"].append(payload)
        elif payload["replacement_fact_id"] == fact_id:
            chain["replaces"].append(payload)
    return chain


def _fact_conflict_relation_payload(relation) -> dict[str, Any]:
    def parse_fact_ref(value: str) -> int | None:
        prefix = "fact:"
        if not value.startswith(prefix):
            return None
        return int(value[len(prefix) :])

    return {
        "relation_id": relation.id,
        "left_fact_id": parse_fact_ref(relation.from_ref),
        "right_fact_id": parse_fact_ref(relation.to_ref),
        "relation_type": relation.relation_type,
        "review_actor": relation.review_actor,
        "review_reason": relation.review_reason,
        "evidence_ids": relation.evidence_ids,
    }


def _fact_decision_summary(*, status: str, replacement_chain: dict[str, list[dict[str, Any]]]) -> str:
    superseded_by = replacement_chain["superseded_by"]
    if status == "approved":
        base = "approved: visible in default retrieval"
    elif status == "candidate":
        base = "candidate: hidden from default retrieval until approved"
    elif status == "disputed":
        base = "disputed: hidden from default retrieval pending review"
    elif status == "deprecated":
        base = "deprecated: hidden from default retrieval"
    else:
        base = f"{status}: hidden from default retrieval"
    if superseded_by:
        replacement_ids = ", ".join(
            f"fact #{item['replacement_fact_id']}" for item in superseded_by if item["replacement_fact_id"] is not None
        )
        if replacement_ids:
            base = f"{base}; superseded by {replacement_ids}"
    return base


def _status_counts_for_facts(facts) -> dict[str, int]:
    counts = {"approved": 0, "candidate": 0, "disputed": 0, "deprecated": 0}
    for fact in facts:
        counts[fact.status] += 1
    return counts


def _promotion_conflict_commands(db_path: Path, *, fact_id: int) -> dict[str, str]:
    fact_ref = f"fact:{fact_id}"
    return {
        "review_explain": f"agent-memory review explain fact {db_path} {fact_id}",
        "review_replacements": f"agent-memory review replacements fact {db_path} {fact_id}",
        "graph_inspect": f"agent-memory graph inspect {db_path} {fact_ref} --depth 1",
    }


def _promotion_conflict_fact_payload(db_path: Path, fact) -> dict[str, Any]:
    replacement_chain = _fact_replacement_chain_payload(
        list_fact_replacement_relations(db_path, fact_id=fact.id),
        fact_id=fact.id,
    )
    return {
        "fact_id": fact.id,
        "status": fact.status,
        "subject_ref": fact.subject_ref,
        "predicate": fact.predicate,
        "object_ref_or_value": fact.object_ref_or_value,
        "scope": fact.scope,
        "confidence": fact.confidence,
        "replacement_chain": replacement_chain,
        "commands": _promotion_conflict_commands(db_path, fact_id=fact.id),
    }


def _promotion_conflict_preflight(
    db_path: Path,
    *,
    subject_ref: str,
    predicate: str,
    object_ref_or_value: str,
    scope: str,
    allow_conflict: bool,
) -> dict[str, Any]:
    claim_facts = list_facts_by_claim_slot(
        db_path,
        subject_ref=subject_ref,
        predicate=predicate,
        scope=scope,
    )
    conflicts = [
        _promotion_conflict_fact_payload(db_path, fact)
        for fact in claim_facts
        if fact.object_ref_or_value != object_ref_or_value and fact.status in {"approved", "candidate", "disputed", "deprecated"}
    ]
    matching_facts = [
        _promotion_conflict_fact_payload(db_path, fact)
        for fact in claim_facts
        if fact.object_ref_or_value == object_ref_or_value
    ]
    if conflicts and allow_conflict:
        result = "allowed_by_explicit_action"
    elif conflicts:
        result = "blocked"
    else:
        result = "clear"
    suggested_next_steps = [
        "Run the suggested review and graph commands before changing lifecycle status.",
        "Use review supersede after promotion only if a human explicitly chooses a replacement chain.",
    ]
    if conflicts and not allow_conflict:
        suggested_next_steps.append(
            "Use --allow-conflict only after reviewing the conflicting claim slot and explicitly accepting coexisting claims."
        )
    return {
        "read_only": True,
        "result": result,
        "requires_explicit_action": bool(conflicts),
        "claim_slot": {
            "subject_ref": subject_ref,
            "predicate": predicate,
            "scope": scope,
        },
        "requested_fact": {
            "subject_ref": subject_ref,
            "predicate": predicate,
            "object_ref_or_value": object_ref_or_value,
            "scope": scope,
        },
        "status_counts": _status_counts_for_facts(claim_facts),
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
        "matching_facts": matching_facts,
        "suggested_next_steps": suggested_next_steps,
    }


def _memory_ref_parts(memory_ref: str) -> tuple[str, int] | None:
    memory_type, separator, raw_id = memory_ref.partition(":")
    if separator != ":" or not raw_id.isdigit() or memory_type not in {"fact", "procedure", "episode"}:
        return None
    return memory_type, int(raw_id)


def _current_status_for_memory_ref(db_path: Path, memory_ref: str) -> str | None:
    parts = _memory_ref_parts(memory_ref)
    if parts is None:
        return None
    memory_type, memory_id = parts
    try:
        return get_memory_status(db_path, memory_type=memory_type, memory_id=memory_id)
    except ValueError:
        return "missing"


def _fact_review_explanation_payload(db_path: Path, *, fact_id: int) -> dict[str, Any]:
    fact = get_fact(db_path, fact_id=fact_id)
    claim_facts = list_facts_by_claim_slot(
        db_path,
        subject_ref=fact.subject_ref,
        predicate=fact.predicate,
        scope=fact.scope,
    )
    history = list_memory_status_history(db_path, memory_type="fact", memory_id=fact.id)
    replacement_relations = list_fact_replacement_relations(db_path, fact_id=fact.id)
    replacement_chain = _fact_replacement_chain_payload(replacement_relations, fact_id=fact.id)
    return {
        "memory_type": "fact",
        "memory_id": fact.id,
        "fact": fact.model_dump(mode="json"),
        "decision": {
            "current_status": fact.status,
            "visible_in_default_retrieval": fact.status == "approved",
            "summary": _fact_decision_summary(status=fact.status, replacement_chain=replacement_chain),
        },
        "claim_slot": {
            "subject_ref": fact.subject_ref,
            "predicate": fact.predicate,
            "scope": fact.scope,
            "counts": _status_counts_for_facts(claim_facts),
            "facts": [item.model_dump(mode="json") for item in claim_facts],
        },
        "history": [entry.model_dump(mode="json") for entry in history],
        "replacement_chain": replacement_chain,
        "default_retrieval_policy": "approved_only",
    }


def _memory_activity_counts(db_path: Path, *, memory_type: str, memory_id: int) -> dict[str, int]:
    table_by_type = {
        "fact": "facts",
        "procedure": "procedures",
        "episode": "episodes",
    }
    table_name = table_by_type.get(memory_type)
    if table_name is None:
        return {"retrieval_count": 0, "reinforcement_count": 0}
    with connect(db_path) as connection:
        row = connection.execute(
            f"SELECT retrieval_count, reinforcement_count FROM {table_name} WHERE id = ?",
            (memory_id,),
        ).fetchone()
    if row is None:
        return {"retrieval_count": 0, "reinforcement_count": 0}
    return {
        "retrieval_count": int(row["retrieval_count"] or 0),
        "reinforcement_count": int(row["reinforcement_count"] or 0),
    }


def _relation_policy_for_memory(db_path: Path, *, memory_ref: str, memory_type: str, memory_id: int) -> dict[str, Any]:
    relations = list_relations_for_node(db_path, node_ref=memory_ref)
    conflict_relations = [relation for relation in relations if relation.relation_type == "conflicts_with"]
    superseded_by_relations = [
        relation for relation in relations if relation.relation_type == "superseded_by" and relation.from_ref == memory_ref
    ]
    replaces_relations = [
        relation
        for relation in relations
        if (relation.relation_type == "replaces" and relation.from_ref == memory_ref)
        or (relation.relation_type == "superseded_by" and relation.to_ref == memory_ref)
    ]
    reviewed_conflicts = [relation for relation in conflict_relations if relation.review_actor or relation.review_reason]
    payload: dict[str, Any] = {
        "relation_count": len(relations),
        "reviewed_conflict_count": len(reviewed_conflicts),
        "conflict_relation_ids": [relation.id for relation in conflict_relations],
        "superseded_by_count": len(superseded_by_relations),
        "superseded_by_relation_ids": [relation.id for relation in superseded_by_relations],
        "replaces_count": len(replaces_relations),
        "replacement_relation_ids": [relation.id for relation in replaces_relations],
    }
    if memory_type == "fact":
        replacement_chain = _fact_replacement_chain_payload(
            list_fact_replacement_relations(db_path, fact_id=memory_id),
            fact_id=memory_id,
        )
        payload["replacement_chain"] = replacement_chain
        payload["conflict_relations"] = [
            _fact_conflict_relation_payload(relation)
            for relation in list_fact_conflict_relations(db_path, fact_id=memory_id)
        ]
    return payload


def _preview_policy_decision(*, current_status: str | None, trace, relation_policy: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    if current_status != "approved":
        reasons.append("not_approved")
        return {
            "action": "exclude",
            "visibility": "hidden_from_default_retrieval",
            "reason_codes": reasons,
        }
    if relation_policy["superseded_by_count"] > 0:
        reasons.append("superseded_by_reviewed_relation")
        return {
            "action": "exclude",
            "visibility": "hidden_if_supersession_policy_enabled",
            "reason_codes": reasons,
        }
    if relation_policy["reviewed_conflict_count"] > 0:
        reasons.append("reviewed_conflict_relation")
    if trace.conflict_count > 0:
        reasons.append("same_claim_slot_conflict")
    hidden_alternatives_are_expected_replacements = (
        trace.hidden_alternative_count == trace.hidden_deprecated_alternatives_count
        and trace.hidden_deprecated_alternatives_count > 0
        and relation_policy["replaces_count"] > 0
    )
    if trace.hidden_alternative_count > 0 and not hidden_alternatives_are_expected_replacements:
        reasons.append("hidden_non_default_alternatives")
    if reasons:
        return {
            "action": "flag_for_review",
            "visibility": "visible_but_requires_review_if_conflict_policy_enabled",
            "reason_codes": reasons,
        }
    return {
        "action": "include",
        "visibility": "visible_in_default_retrieval",
        "reason_codes": ["approved_without_lifecycle_penalty"],
    }


def _retrieval_policy_preview(db_path: Path, *, query: str, limit: int, preferred_scope: str | None) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("retrieval policy-preview limit must be >= 1")
    packet = retrieve_memory_packet(
        db_path=db_path,
        query=query,
        limit=limit,
        preferred_scope=preferred_scope,
        record_retrievals=False,
    )
    trace_by_key = {(trace.memory_type, trace.memory_id): trace for trace in packet.retrieval_trace}
    memory_projections: list[dict[str, Any]] = []
    for memory_type, models in (
        ("fact", packet.semantic_facts),
        ("procedure", packet.procedural_guidance),
        ("episode", packet.episodic_context),
    ):
        for model in models:
            trace = trace_by_key.get((memory_type, model.id))
            if trace is None:
                continue
            memory_ref = f"{memory_type}:{model.id}"
            current_status = _current_status_for_memory_ref(db_path, memory_ref)
            relation_policy = _relation_policy_for_memory(
                db_path,
                memory_ref=memory_ref,
                memory_type=memory_type,
                memory_id=model.id,
            )
            preview_decision = _preview_policy_decision(
                current_status=current_status,
                trace=trace,
                relation_policy=relation_policy,
            )
            activity_counts = _memory_activity_counts(db_path, memory_type=memory_type, memory_id=model.id)
            signals = list(preview_decision["reason_codes"])
            if relation_policy["reviewed_conflict_count"] > 0 and "reviewed_conflict_relation" not in signals:
                signals.append("reviewed_conflict_relation")
            if relation_policy["superseded_by_count"] > 0 and "superseded_by_reviewed_relation" not in signals:
                signals.append("superseded_by_reviewed_relation")
            if activity_counts["retrieval_count"] > 0 or activity_counts["reinforcement_count"] > 0:
                signals.append("activation_or_retrieval_history")
            memory_projections.append(
                {
                    "memory_ref": memory_ref,
                    "memory_type": memory_type,
                    "memory_id": model.id,
                    "label": trace.label,
                    "scope": trace.scope,
                    "current_status": current_status,
                    "current_visibility": "visible_in_default_retrieval"
                    if current_status == "approved"
                    else "hidden_from_default_retrieval",
                    "preview_decision": preview_decision,
                    "signals": signals,
                    "score_components": {
                        "total_score": round(trace.total_score, 4),
                        "rank_value": round(trace.rank_value, 4),
                        "scope_score": round(trace.scope_score, 4),
                        "lexical_score": round(trace.lexical_score, 4),
                        "relation_score": round(trace.relation_score, 4),
                        "recency_score": round(trace.recency_score, 4),
                        "reinforcement_score": round(trace.reinforcement_score, 4),
                        "conflict_penalty": round(trace.conflict_penalty, 4),
                    },
                    "claim_slot_policy": {
                        "same_claim_slot_conflict_count": trace.conflict_count,
                        "hidden_disputed_alternatives_count": trace.hidden_disputed_alternatives_count,
                        "hidden_deprecated_alternatives_count": trace.hidden_deprecated_alternatives_count,
                        "hidden_alternative_count": trace.hidden_alternative_count,
                    },
                    "relation_policy": relation_policy,
                    "activation_policy": activity_counts,
                    "review_commands": {
                        "review_explain": f"agent-memory review explain {memory_type} {db_path} {model.id}"
                        if memory_type == "fact"
                        else None,
                        "graph_inspect": f"agent-memory graph inspect {db_path} {memory_ref} --depth 1",
                    },
                }
            )
    return {
        "kind": "retrieval_policy_preview",
        "read_only": True,
        "mutated": False,
        "policy": "conservative_preview",
        "default_retrieval_policy": "approved_only",
        "default_retrieval_unchanged": True,
        "query": {
            "stored": False,
            "sha256_present": bool(hashlib.sha256(query.encode("utf-8")).hexdigest()),
        },
        "preferred_scope": preferred_scope,
        "limit": limit,
        "retrieved_counts": {
            "facts": len(packet.semantic_facts),
            "procedures": len(packet.procedural_guidance),
            "episodes": len(packet.episodic_context),
        },
        "memory_projections": memory_projections,
        "suggested_next_steps": [
            "Use this report to inspect lifecycle effects before enabling opt-in retrieval ranking changes.",
            "Review conflict/supersession relations explicitly before hiding or downranking memories.",
            "Keep default retrieval unchanged until eval fixtures and live Hermes E2E pass.",
        ],
    }


def _retrieval_ranker_preview(
    db_path: Path,
    *,
    query: str,
    limit: int,
    preferred_scope: str | None,
    reinforcement_weight: float,
    reinforcement_cap: float,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("retrieval ranker-preview limit must be >= 1")
    if reinforcement_weight <= 0:
        raise ValueError("reinforcement weight must be > 0")
    if reinforcement_cap < 0:
        raise ValueError("reinforcement cap must be >= 0")

    packet = retrieve_memory_packet(
        db_path=db_path,
        query=query,
        limit=limit,
        preferred_scope=preferred_scope,
        record_retrievals=False,
    )
    baseline_traces = list(packet.retrieval_trace)
    baseline_rank_by_key = {
        (trace.memory_type, trace.memory_id): index + 1
        for index, trace in enumerate(baseline_traces)
    }

    preview_rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for trace in baseline_traces:
        memory_ref = f"{trace.memory_type}:{trace.memory_id}"
        activity_counts = _memory_activity_counts(db_path, memory_type=trace.memory_type, memory_id=trace.memory_id)
        reinforcement_delta = min(reinforcement_cap, trace.reinforcement_score * reinforcement_weight)
        preview_total_score = trace.total_score + reinforcement_delta
        baseline_rank = baseline_rank_by_key[(trace.memory_type, trace.memory_id)]
        candidate = {
            "memory_ref": memory_ref,
            "memory_type": trace.memory_type,
            "memory_id": trace.memory_id,
            "label": trace.label,
            "scope": trace.scope,
            "baseline_rank": baseline_rank,
            "preview_rank": None,
            "rank_delta": 0,
            "baseline_score_components": {
                "total_score": round(trace.total_score, 4),
                "rank_value": round(trace.rank_value, 4),
                "scope_score": round(trace.scope_score, 4),
                "lexical_score": round(trace.lexical_score, 4),
                "relation_score": round(trace.relation_score, 4),
                "recency_score": round(trace.recency_score, 4),
                "reinforcement_score": round(trace.reinforcement_score, 4),
                "conflict_penalty": round(trace.conflict_penalty, 4),
            },
            "preview_score_components": {
                "reinforcement_delta": round(reinforcement_delta, 4),
                "preview_total_score": round(preview_total_score, 4),
            },
            "activation_policy": activity_counts,
            "advisory": {
                "action": "compare_only",
                "reason_codes": ["opt_in_reinforcement_ranker_preview"],
            },
        }
        if reinforcement_delta > 0:
            candidate["advisory"]["reason_codes"].append("reinforcement_history_boost")
        preview_sort_key = (
            trace.scope_priority,
            -preview_total_score,
            -max(trace.text_match_count, trace.relation_match_count),
            -trace.relation_match_count,
            -trace.recency_score,
            -trace.reinforcement_score,
            -trace.rank_value,
            trace.memory_id,
        )
        preview_rows.append((preview_sort_key, candidate))

    preview_rows.sort(key=lambda item: item[0])
    candidates = [candidate for _sort_key, candidate in preview_rows]
    for index, candidate in enumerate(candidates):
        preview_rank = index + 1
        candidate["preview_rank"] = preview_rank
        candidate["rank_delta"] = candidate["baseline_rank"] - preview_rank

    rank_changes = [
        {
            "memory_ref": candidate["memory_ref"],
            "baseline_rank": candidate["baseline_rank"],
            "preview_rank": candidate["preview_rank"],
            "rank_delta": candidate["rank_delta"],
        }
        for candidate in candidates
        if candidate["rank_delta"] != 0 or candidate["preview_score_components"]["reinforcement_delta"] > 0
    ]

    return {
        "kind": "retrieval_ranker_preview",
        "read_only": True,
        "mutated": False,
        "policy": "reinforcement_aware_preview",
        "default_retrieval_policy": "approved_only",
        "default_retrieval_unchanged": True,
        "query": {
            "stored": False,
            "sha256_present": bool(hashlib.sha256(query.encode("utf-8")).hexdigest()),
        },
        "preferred_scope": preferred_scope,
        "limit": limit,
        "ranker_parameters": {
            "reinforcement_weight": reinforcement_weight,
            "reinforcement_cap": reinforcement_cap,
        },
        "baseline_source": "current_default_retrieval_trace",
        "candidates": candidates,
        "rank_changes": rank_changes,
        "suggested_next_steps": [
            "Treat this as an opt-in experiment only; do not change default retrieval without eval evidence.",
            "Compare rank_changes against fixture relevance before increasing reinforcement weight.",
            "Run live Hermes E2E before promoting any ranker policy beyond preview mode.",
        ],
    }


def _ref_activation_payload(db_path: Path, *, memory_ref: str, frequent_threshold: int) -> dict[str, Any]:
    activations = [
        activation
        for activation in list_memory_activations(db_path, limit=1000)
        if activation.memory_ref == memory_ref
    ]
    latest_global_activation_id = max((activation.id for activation in list_memory_activations(db_path, limit=1000)), default=0)
    if not activations:
        current_status = _current_status_for_memory_ref(db_path, memory_ref)
        relations = list_relations_for_node(db_path, node_ref=memory_ref)
        score = 0.65
        if current_status == "approved" and relations:
            score = 0.35
        signals = ["no_activation_history"]
        if relations:
            signals.append("connected_memory")
        else:
            signals.append("isolated_memory")
        return {
            "score": score,
            "current_status": current_status,
            "activation_count": 0,
            "total_strength": 0.0,
            "factor_breakdown": {
                "low_repetition": {"activation_count": 0, "threshold": frequent_threshold, "ratio": 1.0, "score": 0.3},
                "weak_strength": {"total_strength": 0.0, "threshold": frequent_threshold, "ratio": 1.0, "score": 0.2},
                "stale_activity": {
                    "latest_activation_id": None,
                    "global_latest_activation_id": latest_global_activation_id,
                    "activation_id_distance": None,
                    "ratio": 1.0,
                    "score": 0.2,
                },
                "low_connectivity": {
                    "relation_count": len(relations),
                    "ratio": 0.0 if relations else 1.0,
                    "score": 0.0 if relations else 0.15,
                },
                "status_risk": {"value": current_status, "risk_ratio": _decay_status_risk_value(current_status), "score": 0.0},
            },
            "protections": [],
            "signals": signals,
            "sample_activation_ids": [],
            "sample_observation_ids": [],
            "activation_window": None,
        }
    return _decay_risk_candidate_payload(
        db_path,
        memory_ref=memory_ref,
        ref_activations=activations,
        frequent_threshold=frequent_threshold,
        latest_activation_id=latest_global_activation_id,
    )


def _parse_memory_ref(value: str) -> tuple[str, int] | None:
    if ":" not in value:
        return None
    memory_type, raw_id = value.split(":", 1)
    if memory_type not in {"fact", "procedure", "episode"}:
        return None
    try:
        return memory_type, int(raw_id)
    except ValueError:
        return None


def _bounded_graph_neighborhood(db_path: Path, *, memory_ref: str, depth: int) -> dict[str, Any]:
    if depth < 1:
        raise ValueError("graph neighborhood depth must be >= 1")
    seen_nodes = {memory_ref}
    frontier = {memory_ref}
    edges_by_id: dict[int, Any] = {}
    neighbor_distances: dict[str, int] = {}
    truncated = False
    max_edges = 100

    for current_depth in range(1, depth + 1):
        next_frontier: set[str] = set()
        for node_ref in sorted(frontier):
            for relation in list_relations_for_node(db_path, node_ref=node_ref):
                if len(edges_by_id) >= max_edges and relation.id not in edges_by_id:
                    truncated = True
                    continue
                edges_by_id[relation.id] = relation
                other_ref = relation.to_ref if relation.from_ref == node_ref else relation.from_ref
                if other_ref not in neighbor_distances and other_ref != memory_ref:
                    neighbor_distances[other_ref] = current_depth
                if other_ref not in seen_nodes:
                    seen_nodes.add(other_ref)
                    next_frontier.add(other_ref)
        frontier = next_frontier
        if not frontier:
            break

    neighbor_refs = sorted(neighbor_distances, key=lambda ref: (neighbor_distances[ref], ref))
    relation_payloads = [
        {
            "relation_id": relation.id,
            "from_ref": relation.from_ref,
            "relation_type": relation.relation_type,
            "to_ref": relation.to_ref,
            "confidence": relation.confidence,
        }
        for relation in sorted(edges_by_id.values(), key=lambda relation: relation.id)
    ]
    return {
        "bounded": True,
        "depth": depth,
        "start_ref": memory_ref,
        "neighbor_refs": neighbor_refs,
        "neighbor_distances": {ref: neighbor_distances[ref] for ref in neighbor_refs},
        "relation_count": len(relation_payloads),
        "relation_ids": [relation["relation_id"] for relation in relation_payloads],
        "relations": relation_payloads,
        "truncated": truncated,
    }


def _neighbor_reinforcement_score(db_path: Path, *, neighbor_refs: list[str], neighbor_reinforcement_weight: float) -> tuple[float, list[str]]:
    activated_neighbor_refs: list[str] = []
    raw_score = 0.0
    for neighbor_ref in neighbor_refs:
        parsed = _parse_memory_ref(neighbor_ref)
        if parsed is None:
            continue
        memory_type, memory_id = parsed
        activity = _memory_activity_counts(db_path, memory_type=memory_type, memory_id=memory_id)
        activation_count = activity["retrieval_count"] + activity["reinforcement_count"]
        if activation_count <= 0:
            continue
        activated_neighbor_refs.append(neighbor_ref)
        raw_score += min(float(activation_count), 5.0) * neighbor_reinforcement_weight
    return raw_score, activated_neighbor_refs


def _retrieval_graph_neighborhood_preview(
    db_path: Path,
    *,
    query: str,
    limit: int,
    preferred_scope: str | None,
    depth: int,
    graph_weight: float,
    graph_cap: float,
    neighbor_reinforcement_weight: float,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("retrieval graph-neighborhood-preview limit must be >= 1")
    if depth < 1:
        raise ValueError("graph neighborhood depth must be >= 1")
    if graph_weight <= 0:
        raise ValueError("graph weight must be > 0")
    if graph_cap < 0:
        raise ValueError("graph cap must be >= 0")
    if neighbor_reinforcement_weight < 0:
        raise ValueError("neighbor reinforcement weight must be >= 0")

    packet = retrieve_memory_packet(
        db_path=db_path,
        query=query,
        limit=limit,
        preferred_scope=preferred_scope,
        record_retrievals=False,
    )
    baseline_traces = list(packet.retrieval_trace)
    baseline_rank_by_key = {
        (trace.memory_type, trace.memory_id): index + 1
        for index, trace in enumerate(baseline_traces)
    }

    preview_rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    for trace in baseline_traces:
        memory_ref = f"{trace.memory_type}:{trace.memory_id}"
        graph_neighborhood = _bounded_graph_neighborhood(db_path, memory_ref=memory_ref, depth=depth)
        neighbor_reinforcement_score, activated_neighbor_refs = _neighbor_reinforcement_score(
            db_path,
            neighbor_refs=graph_neighborhood["neighbor_refs"],
            neighbor_reinforcement_weight=neighbor_reinforcement_weight,
        )
        graph_signal = graph_neighborhood["relation_count"] * graph_weight
        graph_neighborhood_delta = min(graph_cap, graph_signal + neighbor_reinforcement_score)
        preview_total_score = trace.total_score + graph_neighborhood_delta
        baseline_rank = baseline_rank_by_key[(trace.memory_type, trace.memory_id)]
        reason_codes = ["opt_in_bounded_graph_neighborhood_preview"]
        if graph_neighborhood_delta > 0:
            reason_codes.append("bounded_graph_neighbor_support")
        if activated_neighbor_refs:
            reason_codes.append("activated_neighbor_support")
        if graph_neighborhood["truncated"]:
            reason_codes.append("graph_neighborhood_truncated")
        graph_neighborhood["activated_neighbor_refs"] = activated_neighbor_refs
        candidate = {
            "memory_ref": memory_ref,
            "memory_type": trace.memory_type,
            "memory_id": trace.memory_id,
            "label": trace.label,
            "scope": trace.scope,
            "baseline_rank": baseline_rank,
            "preview_rank": None,
            "rank_delta": 0,
            "baseline_score_components": {
                "total_score": round(trace.total_score, 4),
                "rank_value": round(trace.rank_value, 4),
                "scope_score": round(trace.scope_score, 4),
                "lexical_score": round(trace.lexical_score, 4),
                "relation_score": round(trace.relation_score, 4),
                "recency_score": round(trace.recency_score, 4),
                "reinforcement_score": round(trace.reinforcement_score, 4),
                "conflict_penalty": round(trace.conflict_penalty, 4),
            },
            "preview_score_components": {
                "graph_neighborhood_delta": round(graph_neighborhood_delta, 4),
                "graph_signal": round(graph_signal, 4),
                "neighbor_reinforcement_score": round(neighbor_reinforcement_score, 4),
                "preview_total_score": round(preview_total_score, 4),
            },
            "graph_neighborhood": graph_neighborhood,
            "activation_policy": _memory_activity_counts(
                db_path,
                memory_type=trace.memory_type,
                memory_id=trace.memory_id,
            ),
            "advisory": {
                "action": "compare_only",
                "reason_codes": reason_codes,
            },
        }
        preview_sort_key = (
            trace.scope_priority,
            -preview_total_score,
            -max(trace.text_match_count, trace.relation_match_count),
            -trace.relation_match_count,
            -trace.recency_score,
            -trace.reinforcement_score,
            -trace.rank_value,
            trace.memory_id,
        )
        preview_rows.append((preview_sort_key, candidate))

    preview_rows.sort(key=lambda item: item[0])
    candidates = [candidate for _sort_key, candidate in preview_rows]
    for index, candidate in enumerate(candidates):
        preview_rank = index + 1
        candidate["preview_rank"] = preview_rank
        candidate["rank_delta"] = candidate["baseline_rank"] - preview_rank

    rank_changes = [
        {
            "memory_ref": candidate["memory_ref"],
            "baseline_rank": candidate["baseline_rank"],
            "preview_rank": candidate["preview_rank"],
            "rank_delta": candidate["rank_delta"],
        }
        for candidate in candidates
        if candidate["rank_delta"] != 0 or candidate["preview_score_components"]["graph_neighborhood_delta"] > 0
    ]

    return {
        "kind": "retrieval_graph_neighborhood_preview",
        "read_only": True,
        "mutated": False,
        "policy": "bounded_graph_neighborhood_reinforcement_preview",
        "default_retrieval_policy": "approved_only",
        "default_retrieval_unchanged": True,
        "query": {
            "stored": False,
            "sha256_present": bool(hashlib.sha256(query.encode("utf-8")).hexdigest()),
        },
        "preferred_scope": preferred_scope,
        "limit": limit,
        "ranker_parameters": {
            "depth": depth,
            "graph_weight": graph_weight,
            "graph_cap": graph_cap,
            "neighbor_reinforcement_weight": neighbor_reinforcement_weight,
        },
        "baseline_source": "current_default_retrieval_trace",
        "candidates": candidates,
        "rank_changes": rank_changes,
        "suggested_next_steps": [
            "Treat this as an opt-in bounded graph preview only; do not change default retrieval without eval evidence.",
            "Inspect surprising graph boosts with graph inspect before promoting any ranker policy.",
            "Run live Hermes E2E before enabling graph-neighborhood reinforcement outside preview mode.",
        ],
    }


def _retrieval_decay_preview(
    db_path: Path,
    *,
    query: str,
    limit: int,
    preferred_scope: str | None,
    decay_weight: float,
    frequent_threshold: int,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("retrieval decay-preview limit must be >= 1")
    if decay_weight <= 0:
        raise ValueError("decay weight must be > 0")
    if frequent_threshold < 1:
        raise ValueError("frequent threshold must be >= 1")

    packet = retrieve_memory_packet(
        db_path=db_path,
        query=query,
        limit=limit,
        preferred_scope=preferred_scope,
        record_retrievals=False,
    )
    baseline_traces = list(packet.retrieval_trace)
    baseline_rank_by_key = {
        (trace.memory_type, trace.memory_id): index + 1
        for index, trace in enumerate(baseline_traces)
    }

    preview_rows: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    excluded_candidates: list[dict[str, Any]] = []
    for trace in baseline_traces:
        memory_ref = f"{trace.memory_type}:{trace.memory_id}"
        relation_policy = _relation_policy_for_memory(
            db_path,
            memory_ref=memory_ref,
            memory_type=trace.memory_type,
            memory_id=trace.memory_id,
        )
        decay_risk = _ref_activation_payload(db_path, memory_ref=memory_ref, frequent_threshold=frequent_threshold)
        decay_penalty = round(decay_risk["score"] * decay_weight, 4)
        preview_total_score = trace.total_score - decay_penalty
        baseline_rank = baseline_rank_by_key[(trace.memory_type, trace.memory_id)]
        reason_codes = ["opt_in_decay_risk_penalty_preview"]
        action = "compare_only"
        if relation_policy["superseded_by_count"] > 0:
            action = "exclude"
            reason_codes.append("superseded_memory")
        elif decay_risk["score"] >= 0.5:
            reason_codes.append("decay_review_candidate")
        if "protected_from_age_only_decay" in decay_risk["signals"]:
            reason_codes.append("protected_from_age_only_decay")
        candidate = {
            "memory_ref": memory_ref,
            "memory_type": trace.memory_type,
            "memory_id": trace.memory_id,
            "label": trace.label,
            "scope": trace.scope,
            "baseline_rank": baseline_rank,
            "preview_rank": None,
            "rank_delta": 0,
            "baseline_score_components": {
                "total_score": round(trace.total_score, 4),
                "rank_value": round(trace.rank_value, 4),
                "scope_score": round(trace.scope_score, 4),
                "lexical_score": round(trace.lexical_score, 4),
                "relation_score": round(trace.relation_score, 4),
                "recency_score": round(trace.recency_score, 4),
                "reinforcement_score": round(trace.reinforcement_score, 4),
                "conflict_penalty": round(trace.conflict_penalty, 4),
            },
            "preview_score_components": {
                "decay_penalty": decay_penalty,
                "preview_total_score": round(preview_total_score, 4),
            },
            "decay_risk": decay_risk,
            "relation_policy": relation_policy,
            "activation_policy": _memory_activity_counts(
                db_path,
                memory_type=trace.memory_type,
                memory_id=trace.memory_id,
            ),
            "advisory": {
                "action": action,
                "reason_codes": reason_codes,
            },
        }
        if action == "exclude":
            excluded_candidates.append(candidate)
            continue
        preview_sort_key = (
            trace.scope_priority,
            -preview_total_score,
            -max(trace.text_match_count, trace.relation_match_count),
            -trace.relation_match_count,
            -trace.recency_score,
            -trace.reinforcement_score,
            -trace.rank_value,
            trace.memory_id,
        )
        preview_rows.append((preview_sort_key, candidate))

    preview_rows.sort(key=lambda item: item[0])
    ranked_candidates = [candidate for _sort_key, candidate in preview_rows]
    for index, candidate in enumerate(ranked_candidates):
        preview_rank = index + 1
        candidate["preview_rank"] = preview_rank
        candidate["rank_delta"] = candidate["baseline_rank"] - preview_rank
    candidates = [*ranked_candidates, *excluded_candidates]

    rank_changes = [
        {
            "memory_ref": candidate["memory_ref"],
            "baseline_rank": candidate["baseline_rank"],
            "preview_rank": candidate["preview_rank"],
            "rank_delta": candidate["rank_delta"],
            "action": candidate["advisory"]["action"],
        }
        for candidate in candidates
        if candidate["rank_delta"] != 0
        or candidate["preview_score_components"]["decay_penalty"] > 0
        or candidate["advisory"]["action"] == "exclude"
    ]

    return {
        "kind": "retrieval_decay_preview",
        "read_only": True,
        "mutated": False,
        "policy": "decay_risk_penalty_preview",
        "default_retrieval_policy": "approved_only",
        "default_retrieval_unchanged": True,
        "query": {
            "stored": False,
            "sha256_present": bool(hashlib.sha256(query.encode("utf-8")).hexdigest()),
        },
        "preferred_scope": preferred_scope,
        "limit": limit,
        "ranker_parameters": {
            "decay_weight": decay_weight,
            "frequent_threshold": frequent_threshold,
        },
        "baseline_source": "current_default_retrieval_trace",
        "candidates": candidates,
        "rank_changes": rank_changes,
        "suggested_next_steps": [
            "Treat this as an opt-in noise-penalty preview only; do not change default retrieval without eval evidence.",
            "Inspect high decay-risk candidates with activations decay-risk-report before any lifecycle mutation.",
            "Run live Hermes E2E before promoting decay policy beyond preview mode.",
        ],
    }


def _audit_retrieval_observations(
    db_path: Path,
    *,
    limit: int,
    top: int,
    frequent_threshold: int,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("observations audit limit must be >= 1")
    if top < 1:
        raise ValueError("observations audit top must be >= 1")
    if frequent_threshold < 1:
        raise ValueError("observations audit frequent threshold must be >= 1")

    observations = list_retrieval_observations(db_path, limit=limit)
    surface_counts = Counter(observation.surface for observation in observations)
    preferred_scope_counts = Counter(
        observation.preferred_scope for observation in observations if observation.preferred_scope is not None
    )
    memory_ref_counts: Counter[str] = Counter()
    sample_observation_ids_by_ref: dict[str, list[int]] = defaultdict(list)
    observation_windows_by_ref: dict[str, dict[str, Any]] = {}
    empty_retrieval_count = 0
    for observation in observations:
        if not observation.retrieved_memory_refs:
            empty_retrieval_count += 1
        for memory_ref in observation.retrieved_memory_refs:
            memory_ref_counts[memory_ref] += 1
            sample_ids = sample_observation_ids_by_ref[memory_ref]
            if len(sample_ids) < 5:
                sample_ids.append(observation.id)
            window = observation_windows_by_ref.setdefault(
                memory_ref,
                {
                    "first_observation_id": observation.id,
                    "first_observed_at": observation.created_at,
                    "latest_observation_id": observation.id,
                    "latest_observed_at": observation.created_at,
                },
            )
            if observation.id < window["first_observation_id"]:
                window["first_observation_id"] = observation.id
                window["first_observed_at"] = observation.created_at
            if observation.id > window["latest_observation_id"]:
                window["latest_observation_id"] = observation.id
                window["latest_observed_at"] = observation.created_at

    top_memory_refs = []
    for memory_ref, injection_count in sorted(memory_ref_counts.items(), key=lambda item: (-item[1], item[0]))[:top]:
        current_status = _current_status_for_memory_ref(db_path, memory_ref)
        signals = []
        if injection_count >= frequent_threshold:
            signals.append("frequently_injected")
        if current_status is not None and current_status != "approved":
            signals.append("current_status_not_approved")
        top_memory_refs.append(
            {
                "memory_ref": memory_ref,
                "injection_count": injection_count,
                "current_status": current_status,
                "signals": signals,
                "sample_observation_ids": sample_observation_ids_by_ref[memory_ref],
                "observation_window": observation_windows_by_ref[memory_ref],
            }
        )

    empty_retrieval_ratio = empty_retrieval_count / len(observations) if observations else 0.0
    quality_warnings = []
    if not observations:
        quality_warnings.append("no_observations")
    if 0 < len(observations) < 10:
        quality_warnings.append("low_observation_count")
    if empty_retrieval_ratio >= 0.5 and observations:
        quality_warnings.append("high_empty_retrieval_ratio")

    return {
        "kind": "retrieval_observation_audit",
        "read_only": True,
        "observation_count": len(observations),
        "limit": limit,
        "top": top,
        "frequent_threshold": frequent_threshold,
        "surface_counts": dict(sorted(surface_counts.items())),
        "preferred_scope_counts": dict(sorted(preferred_scope_counts.items())),
        "empty_retrieval_count": empty_retrieval_count,
        "empty_retrieval_ratio": round(empty_retrieval_ratio, 4),
        "quality_warnings": quality_warnings,
        "top_memory_refs": top_memory_refs,
    }


def _observation_window(observations) -> dict[str, Any] | None:
    if not observations:
        return None
    first = min(observations, key=lambda observation: observation.id)
    latest = max(observations, key=lambda observation: observation.id)
    return {
        "first_observation_id": first.id,
        "first_observed_at": first.created_at,
        "latest_observation_id": latest.id,
        "latest_observed_at": latest.created_at,
    }


def _activation_window(activations) -> dict[str, Any] | None:
    if not activations:
        return None
    first = min(activations, key=lambda activation: activation.id)
    latest = max(activations, key=lambda activation: activation.id)
    return {
        "first_activation_id": first.id,
        "first_activated_at": first.created_at,
        "latest_activation_id": latest.id,
        "latest_activated_at": latest.created_at,
    }


def _unique_non_null(values: list[Any]) -> list[Any]:
    return sorted({value for value in values if value is not None})


def _sample_observation_ids(activations) -> list[int]:
    observation_ids = []
    for activation in activations:
        if activation.observation_id is not None and activation.observation_id not in observation_ids:
            observation_ids.append(activation.observation_id)
        if len(observation_ids) >= 5:
            break
    return observation_ids


def _reinforcement_scoring_contract() -> dict[str, Any]:
    return {
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


def _status_trust_value(current_status: str | None) -> float:
    if current_status == "approved":
        return 1.0
    if current_status == "candidate":
        return 0.5
    return 0.0


def _reinforcement_candidate_payload(
    db_path: Path,
    *,
    memory_ref: str,
    ref_activations,
    frequent_threshold: int,
) -> dict[str, Any]:
    scoring = _reinforcement_scoring_contract()
    weights = scoring["weights"]
    configured_penalties = scoring["penalties"]

    current_status = _current_status_for_memory_ref(db_path, memory_ref)
    activation_count = len(ref_activations)
    total_strength = sum(activation.strength for activation in ref_activations)
    unique_surfaces = _unique_non_null([activation.surface for activation in ref_activations])
    unique_scopes = _unique_non_null([activation.scope for activation in ref_activations])
    relations = list_relations_for_node(db_path, node_ref=memory_ref)
    replacement_relations = [relation for relation in relations if relation.relation_type in {"superseded_by", "replaces"}]

    repetition_ratio = min(activation_count / frequent_threshold, 1.0)
    strength_ratio = min(total_strength / frequent_threshold, 1.0)
    diversity_ratio = min((len(unique_surfaces) + len(unique_scopes)) / 3, 1.0)
    connectivity_ratio = min(len(relations), 1.0)
    status_trust = _status_trust_value(current_status)

    factor_breakdown = {
        "repetition": {
            "activation_count": activation_count,
            "threshold": frequent_threshold,
            "ratio": round(repetition_ratio, 4),
            "score": round(weights["repetition"] * repetition_ratio, 4),
        },
        "strength": {
            "total_strength": round(total_strength, 4),
            "threshold": frequent_threshold,
            "ratio": round(strength_ratio, 4),
            "score": round(weights["strength"] * strength_ratio, 4),
        },
        "status_trust": {
            "value": current_status,
            "trust_ratio": status_trust,
            "score": round(weights["status_trust"] * status_trust, 4),
        },
        "surface_scope_diversity": {
            "surface_count": len(unique_surfaces),
            "scope_count": len(unique_scopes),
            "surfaces": unique_surfaces,
            "scopes": unique_scopes,
            "ratio": round(diversity_ratio, 4),
            "score": round(weights["surface_scope_diversity"] * diversity_ratio, 4),
        },
        "connectivity": {
            "relation_count": len(relations),
            "ratio": round(connectivity_ratio, 4),
            "score": round(weights["connectivity"] * connectivity_ratio, 4),
        },
    }

    penalties = {}
    if current_status in {"deprecated", "disputed", "missing"}:
        penalties["status_penalty"] = configured_penalties[current_status]
    if replacement_relations:
        penalties["supersession_or_replacement"] = configured_penalties["supersession_or_replacement"]

    raw_score = sum(factor["score"] for factor in factor_breakdown.values()) - sum(penalties.values())
    score = round(max(0.0, min(scoring["max_score"], raw_score)), 4)

    signals = []
    if current_status == "approved" and score >= 0.75:
        signals.append("strong_reinforcement_candidate")
    elif current_status != "approved":
        signals.append("not_reinforcement_ready")
    if activation_count >= frequent_threshold:
        signals.append("frequently_activated")
    if relations:
        signals.append("connected_memory")
    if current_status == "deprecated":
        signals.append("deprecated_activation")
    elif current_status == "disputed":
        signals.append("disputed_activation")
    elif current_status == "missing":
        signals.append("missing_memory_ref")
    if replacement_relations:
        signals.append("supersession_or_replacement_relation")

    return {
        "memory_ref": memory_ref,
        "score": score,
        "current_status": current_status,
        "activation_count": activation_count,
        "total_strength": round(total_strength, 4),
        "factor_breakdown": factor_breakdown,
        "penalties": penalties,
        "signals": signals,
        "sample_activation_ids": [activation.id for activation in ref_activations[:5]],
        "sample_observation_ids": _sample_observation_ids(ref_activations),
        "activation_window": _activation_window(ref_activations),
    }


def _activation_reinforcement_report(db_path: Path, *, limit: int, top: int, frequent_threshold: int) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("activations reinforcement-report limit must be >= 1")
    if top < 1:
        raise ValueError("activations reinforcement-report top must be >= 1")
    if frequent_threshold < 1:
        raise ValueError("activations reinforcement-report frequent threshold must be >= 1")

    activations = list_memory_activations(db_path, limit=limit)
    activations_by_ref: dict[str, list[Any]] = defaultdict(list)
    empty_retrieval_count = 0
    for activation in activations:
        if activation.activation_kind == "empty_retrieval":
            empty_retrieval_count += 1
        if activation.memory_ref is not None:
            activations_by_ref[activation.memory_ref].append(activation)

    candidates = [
        _reinforcement_candidate_payload(
            db_path,
            memory_ref=memory_ref,
            ref_activations=ref_activations,
            frequent_threshold=frequent_threshold,
        )
        for memory_ref, ref_activations in activations_by_ref.items()
    ]
    candidates.sort(key=lambda candidate: (-candidate["score"], -candidate["activation_count"], candidate["memory_ref"]))

    quality_warnings = []
    if not activations:
        quality_warnings.append("no_activations")
    if 0 < len(activations) < 10:
        quality_warnings.append("low_activation_count")

    empty_ratio = empty_retrieval_count / len(activations) if activations else 0.0
    return {
        "kind": "memory_reinforcement_report",
        "read_only": True,
        "activation_count": len(activations),
        "limit": limit,
        "top": top,
        "frequent_threshold": frequent_threshold,
        "activation_window": _activation_window(activations),
        "scoring": _reinforcement_scoring_contract(),
        "quality_warnings": quality_warnings,
        "negative_evidence": {
            "empty_retrieval_count": empty_retrieval_count,
            "empty_retrieval_ratio": round(empty_ratio, 4),
        },
        "reinforcement_candidates": candidates[:top],
        "suggested_next_steps": [
            "Inspect strong candidates with activations summary before any promotion workflow.",
            "Use decay-risk reporting before mutating stale or weak memories.",
            "Keep retrieval ranking unchanged until opt-in eval and live Hermes E2E pass.",
        ],
    }


def _decay_risk_scoring_contract() -> dict[str, Any]:
    return {
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


def _decay_status_risk_value(current_status: str | None) -> float:
    if current_status == "approved":
        return 0.0
    if current_status == "candidate":
        return 0.5
    if current_status in {"deprecated", "disputed"}:
        return 0.8
    if current_status == "missing":
        return 0.7
    return 0.4


def _decay_risk_candidate_payload(
    db_path: Path,
    *,
    memory_ref: str,
    ref_activations,
    frequent_threshold: int,
    latest_activation_id: int,
) -> dict[str, Any]:
    scoring = _decay_risk_scoring_contract()
    weights = scoring["weights"]
    protections_config = scoring["protections"]

    current_status = _current_status_for_memory_ref(db_path, memory_ref)
    activation_count = len(ref_activations)
    total_strength = sum(activation.strength for activation in ref_activations)
    relations = list_relations_for_node(db_path, node_ref=memory_ref)
    latest_ref_activation_id = max(activation.id for activation in ref_activations)

    low_repetition_ratio = max(0.0, 1.0 - min(activation_count / frequent_threshold, 1.0))
    weak_strength_ratio = max(0.0, 1.0 - min(total_strength / frequent_threshold, 1.0))
    stale_distance = max(0, latest_activation_id - latest_ref_activation_id)
    stale_ratio = min(stale_distance / frequent_threshold, 1.0)
    low_connectivity_ratio = 0.0 if relations else 1.0
    status_risk = _decay_status_risk_value(current_status)

    factor_breakdown = {
        "low_repetition": {
            "activation_count": activation_count,
            "threshold": frequent_threshold,
            "ratio": round(low_repetition_ratio, 4),
            "score": round(weights["low_repetition"] * low_repetition_ratio, 4),
        },
        "weak_strength": {
            "total_strength": round(total_strength, 4),
            "threshold": frequent_threshold,
            "ratio": round(weak_strength_ratio, 4),
            "score": round(weights["weak_strength"] * weak_strength_ratio, 4),
        },
        "stale_activity": {
            "latest_activation_id": latest_ref_activation_id,
            "global_latest_activation_id": latest_activation_id,
            "activation_id_distance": stale_distance,
            "ratio": round(stale_ratio, 4),
            "score": round(weights["stale_activity"] * stale_ratio, 4),
        },
        "low_connectivity": {
            "relation_count": len(relations),
            "ratio": round(low_connectivity_ratio, 4),
            "score": round(weights["low_connectivity"] * low_connectivity_ratio, 4),
        },
        "status_risk": {
            "value": current_status,
            "risk_ratio": status_risk,
            "score": round(weights["status_risk"] * status_risk, 4),
        },
    }

    raw_score = sum(factor["score"] for factor in factor_breakdown.values())
    protections = []
    if current_status == "approved" and activation_count >= frequent_threshold and relations:
        protections.append("approved_frequent_connected_max_score")
        raw_score = min(raw_score, protections_config["approved_frequent_connected_max_score"])
    elif current_status == "approved" and activation_count >= frequent_threshold:
        protections.append("approved_frequent_max_score")
        raw_score = min(raw_score, protections_config["approved_frequent_max_score"])
    score = round(max(0.0, min(scoring["max_score"], raw_score)), 4)

    signals = []
    if score >= 0.5:
        signals.append("decay_review_candidate")
    if protections:
        signals.append("protected_from_age_only_decay")
    if activation_count < frequent_threshold:
        signals.append("low_activation_count")
    else:
        signals.append("frequently_activated")
    if not relations:
        signals.append("isolated_memory")
    else:
        signals.append("connected_memory")
    if current_status == "deprecated":
        signals.append("deprecated_memory")
    elif current_status == "disputed":
        signals.append("disputed_memory")
    elif current_status == "missing":
        signals.append("missing_memory_ref")

    return {
        "memory_ref": memory_ref,
        "score": score,
        "current_status": current_status,
        "activation_count": activation_count,
        "total_strength": round(total_strength, 4),
        "factor_breakdown": factor_breakdown,
        "protections": protections,
        "signals": signals,
        "sample_activation_ids": [activation.id for activation in ref_activations[:5]],
        "sample_observation_ids": _sample_observation_ids(ref_activations),
        "activation_window": _activation_window(ref_activations),
    }


def _activation_decay_risk_report(db_path: Path, *, limit: int, top: int, frequent_threshold: int) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("activations decay-risk-report limit must be >= 1")
    if top < 1:
        raise ValueError("activations decay-risk-report top must be >= 1")
    if frequent_threshold < 1:
        raise ValueError("activations decay-risk-report frequent threshold must be >= 1")

    activations = list_memory_activations(db_path, limit=limit)
    activations_by_ref: dict[str, list[Any]] = defaultdict(list)
    empty_retrieval_count = 0
    for activation in activations:
        if activation.activation_kind == "empty_retrieval":
            empty_retrieval_count += 1
        if activation.memory_ref is not None:
            activations_by_ref[activation.memory_ref].append(activation)

    latest_activation_id = max((activation.id for activation in activations), default=0)
    candidates = [
        _decay_risk_candidate_payload(
            db_path,
            memory_ref=memory_ref,
            ref_activations=ref_activations,
            frequent_threshold=frequent_threshold,
            latest_activation_id=latest_activation_id,
        )
        for memory_ref, ref_activations in activations_by_ref.items()
    ]
    candidates.sort(key=lambda candidate: (-candidate["score"], candidate["current_status"] or "", candidate["memory_ref"]))

    quality_warnings = []
    if not activations:
        quality_warnings.append("no_activations")
    if 0 < len(activations) < 10:
        quality_warnings.append("low_activation_count")

    empty_ratio = empty_retrieval_count / len(activations) if activations else 0.0
    return {
        "kind": "memory_decay_risk_report",
        "read_only": True,
        "activation_count": len(activations),
        "limit": limit,
        "top": top,
        "frequent_threshold": frequent_threshold,
        "activation_window": _activation_window(activations),
        "scoring": _decay_risk_scoring_contract(),
        "quality_warnings": quality_warnings,
        "negative_evidence": {
            "empty_retrieval_count": empty_retrieval_count,
            "empty_retrieval_ratio": round(empty_ratio, 4),
        },
        "decay_risk_candidates": candidates[:top],
        "suggested_next_steps": [
            "Inspect high decay-risk refs with activations summary and review explain before any status change.",
            "Treat this report as advisory only; do not delete, deprecate, or mutate from decay score alone.",
            "Use future consolidation candidate reports to compare weak refs with trace clusters before cleanup.",
        ],
    }


def _safe_summary_key(summary: str | None) -> str:
    if not summary:
        return "no-summary"
    tokens = [token.strip(".,:;!?()[]{}\"'").lower() for token in summary.split()]
    safe_tokens = [token for token in tokens if len(token) >= 4][:8]
    return "-".join(safe_tokens) or "summary"


def _consolidation_cluster_key(trace: Any) -> str:
    if trace.related_memory_refs:
        return f"scope:{trace.scope or 'global'}|memory:{sorted(trace.related_memory_refs)[0]}"
    return f"scope:{trace.scope or 'global'}|summary:{_safe_summary_key(trace.summary)}"


def _guess_consolidation_memory_type(traces: list[Any]) -> str:
    joined = " ".join(trace.summary or "" for trace in traces).lower()
    if any(token in joined for token in ["prefer", "prefers", "preference", "wants", "does not want"]):
        return "preference"
    if any(token in joined for token in ["step", "workflow", "procedure", "run ", "command"]):
        return "procedural"
    if any(token in joined for token in ["happened", "session", "meeting", "incident"]):
        return "episodic"
    if joined:
        return "semantic"
    return "unknown"


def _consolidation_candidate_payload(db_path: Path, *, cluster_key: str, traces: list[Any]) -> dict[str, Any]:
    trace_ids = sorted(trace.id for trace in traces)
    related_memory_refs = sorted({ref for trace in traces for ref in trace.related_memory_refs})
    related_observation_ids = sorted({oid for trace in traces for oid in trace.related_observation_ids})
    surfaces = sorted({trace.surface for trace in traces})
    scopes = sorted({trace.scope for trace in traces if trace.scope is not None})
    retention_policies = dict(sorted(Counter(trace.retention_policy for trace in traces).items()))
    event_kinds = dict(sorted(Counter(trace.event_kind for trace in traces).items()))
    safe_summaries = sorted({trace.summary for trace in traces if trace.summary})[:5]
    salience_total = round(sum(trace.salience for trace in traces), 4)
    user_emphasis_total = round(sum(trace.user_emphasis for trace in traces), 4)
    activations = list_memory_activations(db_path, limit=500)
    activations_by_ref = Counter(
        activation.memory_ref for activation in activations if activation.memory_ref in set(related_memory_refs)
    )
    current_statuses = {
        memory_ref: _current_status_for_memory_ref(db_path, memory_ref) for memory_ref in related_memory_refs
    }
    risk_flags = []
    if not related_memory_refs:
        risk_flags.append("no_related_memory_refs")
    if any(status not in {"approved", None} for status in current_statuses.values()):
        risk_flags.append("non_approved_related_memory")
    if len(traces) < 3:
        risk_flags.append("low_evidence_count")
    if not safe_summaries:
        risk_flags.append("missing_safe_summary")
    fingerprint_payload = {
        "cluster_key": cluster_key,
        "trace_ids": trace_ids,
        "related_memory_refs": related_memory_refs,
    }
    fingerprint = hashlib.sha256(json.dumps(fingerprint_payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    candidate_id = f"candidate:{fingerprint}"
    return {
        "candidate_id": candidate_id,
        "cluster_key": cluster_key,
        "fingerprint": fingerprint,
        "guessed_memory_type": _guess_consolidation_memory_type(traces),
        "evidence_count": len(traces),
        "evidence_trace_ids": trace_ids,
        "evidence_window": {
            "first_trace_id": min(trace_ids),
            "latest_trace_id": max(trace_ids),
        },
        "surfaces": surfaces,
        "scopes": scopes,
        "event_kind_counts": event_kinds,
        "retention_policy_counts": retention_policies,
        "safe_summaries": safe_summaries,
        "related_memory_refs": related_memory_refs,
        "related_observation_ids": related_observation_ids[:20],
        "salience_total": salience_total,
        "user_emphasis_total": user_emphasis_total,
        "reinforcement": {
            "activation_count": sum(activations_by_ref.values()),
            "activation_counts_by_ref": dict(sorted(activations_by_ref.items())),
            "current_statuses": current_statuses,
        },
        "risk_flags": risk_flags,
        "suggested_review_commands": [
            f"agent-memory consolidation explain {db_path} {candidate_id}",
        ],
    }


def _consolidation_group_reason(candidate: dict[str, Any]) -> dict[str, Any]:
    cluster_key = candidate["cluster_key"]
    reason: dict[str, Any] = {"cluster_key": cluster_key, "reason": "summary_similarity"}
    if cluster_key.startswith("scope:") and "|" in cluster_key:
        scope_part, key_part = cluster_key.split("|", 1)
        reason["shared_scope"] = scope_part.removeprefix("scope:")
        if key_part.startswith("memory:"):
            reason["reason"] = "shared_related_memory_ref"
            reason["shared_memory_ref"] = key_part.removeprefix("memory:")
        elif key_part.startswith("summary:"):
            reason["summary_key"] = key_part.removeprefix("summary:")
    return reason


def _consolidation_memory_type_reason(candidate: dict[str, Any]) -> dict[str, str]:
    guessed_type = candidate["guessed_memory_type"]
    reasons = {
        "preference": "safe summaries contain preference-like language",
        "procedural": "safe summaries contain workflow or command language",
        "episodic": "safe summaries contain session or incident language",
        "semantic": "safe summaries contain durable factual language",
        "unknown": "insufficient safe summary evidence",
    }
    return {"value": guessed_type, "reason": reasons.get(guessed_type, "heuristic classification")}


def _consolidation_candidate_explanation(
    db_path: Path,
    *,
    candidate_id: str,
    limit: int,
    min_evidence: int,
) -> dict[str, Any]:
    report = _consolidation_candidates_report(db_path, limit=limit, top=limit, min_evidence=min_evidence)
    for candidate in report["candidates"]:
        if candidate["candidate_id"] != candidate_id:
            continue
        return {
            "kind": "memory_consolidation_candidate_explanation",
            "read_only": True,
            "found": True,
            "candidate_id": candidate_id,
            "candidate": candidate,
            "why_grouped": _consolidation_group_reason(candidate),
            "evidence": {
                "trace_ids": candidate["evidence_trace_ids"],
                "evidence_window": candidate["evidence_window"],
                "safe_summaries": candidate["safe_summaries"],
                "surfaces": candidate["surfaces"],
                "scopes": candidate["scopes"],
                "event_kind_counts": candidate["event_kind_counts"],
                "retention_policy_counts": candidate["retention_policy_counts"],
                "related_observation_ids": candidate["related_observation_ids"],
            },
            "supporting_signals": {
                "salience_total": candidate["salience_total"],
                "user_emphasis_total": candidate["user_emphasis_total"],
                "activation_count": candidate["reinforcement"]["activation_count"],
                "activation_counts_by_ref": candidate["reinforcement"]["activation_counts_by_ref"],
                "current_statuses": candidate["reinforcement"]["current_statuses"],
            },
            "memory_type_guess": _consolidation_memory_type_reason(candidate),
            "risk_flags": candidate["risk_flags"],
            "review_state": {
                "promotion_allowed": False,
                "requires_human_approval": True,
                "mutation_commands_available": False,
            },
            "suggested_next_steps": [
                "Use this explanation for human review only; it does not create or approve memory.",
                "Compare related memory refs and risk flags before considering any future promotion command.",
                "Reject/snooze workflows are intentionally unavailable until candidate quality is trusted.",
            ],
        }
    return {
        "kind": "memory_consolidation_candidate_explanation",
        "read_only": True,
        "candidate_id": candidate_id,
        "found": False,
        "error": "candidate_not_found",
    }


def _promotion_history_payload(db_path: Path, *, memory_type: str, memory_id: int) -> list[dict[str, Any]]:
    return [
        {
            "from_status": transition.from_status,
            "to_status": transition.to_status,
            "actor": transition.actor,
            "reason": transition.reason,
            "evidence_ids": transition.evidence_ids,
        }
        for transition in list_memory_status_history(db_path, memory_type=memory_type, memory_id=memory_id)
    ]


def _consolidation_promotion_lineage_payload(
    *,
    candidate_id: str,
    fact_id: int,
    provenance_source_id: int,
) -> dict[str, Any]:
    fact_ref = f"fact:{fact_id}"
    source_ref = f"source_record:{provenance_source_id}"
    evidence_ids = [provenance_source_id]
    return {
        "candidate_ref": candidate_id,
        "promoted_memory_ref": fact_ref,
        "provenance_source_ref": source_ref,
        "relations": [
            {
                "from_ref": candidate_id,
                "relation_type": "promoted_to",
                "to_ref": fact_ref,
                "evidence_ids": evidence_ids,
            },
            {
                "from_ref": fact_ref,
                "relation_type": "has_promotion_provenance",
                "to_ref": source_ref,
                "evidence_ids": evidence_ids,
            },
        ],
    }


def _record_consolidation_promotion_lineage(
    db_path: Path,
    *,
    candidate_id: str,
    fact_id: int,
    provenance_source_id: int,
    confidence: float,
) -> dict[str, Any]:
    lineage = _consolidation_promotion_lineage_payload(
        candidate_id=candidate_id,
        fact_id=fact_id,
        provenance_source_id=provenance_source_id,
    )
    for relation in lineage["relations"]:
        insert_relation(
            db_path,
            from_ref=relation["from_ref"],
            relation_type=relation["relation_type"],
            to_ref=relation["to_ref"],
            evidence_ids=relation["evidence_ids"],
            weight=1.0,
            confidence=confidence,
        )
    return lineage


def _consolidation_promotions_report(db_path: Path, *, limit: int) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("consolidation promotions report limit must be >= 1")

    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT
                facts.id AS fact_id,
                facts.subject_ref AS subject_ref,
                facts.predicate AS predicate,
                facts.object_ref_or_value AS object_ref_or_value,
                facts.evidence_ids_json AS fact_evidence_ids_json,
                facts.confidence AS confidence,
                facts.valid_from AS valid_from,
                facts.valid_to AS valid_to,
                facts.scope AS scope,
                facts.status AS status,
                facts.searchable_text AS searchable_text,
                source_records.id AS source_id,
                source_records.source_type AS source_type,
                source_records.external_ref AS external_ref,
                source_records.created_at AS source_created_at,
                source_records.content AS source_content,
                source_records.metadata_json AS source_metadata_json
            FROM facts
            JOIN source_records ON facts.evidence_ids_json = '[' || source_records.id || ']'
            WHERE source_records.source_type = 'consolidation_candidate'
              AND source_records.metadata_json LIKE '%"promotion_kind": "manual_reviewed_fact"%'
            ORDER BY source_records.id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    promotions: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for row in rows:
        source_metadata = json.loads(row["source_metadata_json"])
        source_content = json.loads(row["source_content"])
        evidence_ids = json.loads(row["fact_evidence_ids_json"])
        status_counts[row["status"]] += 1
        promotions.append(
            {
                "memory_type": "fact",
                "candidate_id": row["external_ref"],
                "promotion_kind": "manual_reviewed_fact",
                "fact": {
                    "id": row["fact_id"],
                    "subject_ref": row["subject_ref"],
                    "predicate": row["predicate"],
                    "object_ref_or_value": row["object_ref_or_value"],
                    "evidence_ids": evidence_ids,
                    "confidence": row["confidence"],
                    "valid_from": row["valid_from"],
                    "valid_to": row["valid_to"],
                    "scope": row["scope"],
                    "status": row["status"],
                    "searchable_text": row["searchable_text"],
                },
                "provenance_source_id": row["source_id"],
                "provenance": {
                    "source_type": row["source_type"],
                    "candidate_fingerprint": row["external_ref"],
                    "trace_ids": source_metadata.get("trace_ids", []),
                    "related_observation_ids": source_metadata.get("related_observation_ids", []),
                    "safe_summaries": source_content.get("safe_summaries", []),
                    "created_at": row["source_created_at"],
                },
                "lineage": _consolidation_promotion_lineage_payload(
                    candidate_id=row["external_ref"],
                    fact_id=row["fact_id"],
                    provenance_source_id=row["source_id"],
                ),
                "approval_history": _promotion_history_payload(db_path, memory_type="fact", memory_id=row["fact_id"]),
            }
        )

    return {
        "kind": "memory_consolidation_promotions_report",
        "read_only": True,
        "total_promotions": len(promotions),
        "status_counts": dict(sorted(status_counts.items())),
        "promotions": promotions,
        "retrieval_policy": "default_retrieval_remains_approved_only",
    }


def _promote_consolidation_candidate_fact(
    db_path: Path,
    *,
    candidate_id: str,
    subject_ref: str,
    predicate: str,
    object_ref_or_value: str,
    scope: str,
    confidence: float,
    approve: bool,
    actor: str | None,
    reason: str | None,
    allow_conflict: bool,
    limit: int,
    min_evidence: int,
) -> dict[str, Any]:
    explanation = _consolidation_candidate_explanation(
        db_path,
        candidate_id=candidate_id,
        limit=limit,
        min_evidence=min_evidence,
    )
    if not explanation.get("found", False):
        return {
            "kind": "memory_consolidation_promotion",
            "candidate_id": candidate_id,
            "memory_type": "fact",
            "promoted": False,
            "error": "candidate_not_found",
        }

    conflict_preflight = _promotion_conflict_preflight(
        db_path,
        subject_ref=subject_ref,
        predicate=predicate,
        object_ref_or_value=object_ref_or_value,
        scope=scope,
        allow_conflict=allow_conflict,
    )
    if conflict_preflight["result"] == "blocked":
        return {
            "kind": "memory_consolidation_promotion",
            "candidate_id": candidate_id,
            "memory_type": "fact",
            "promoted": False,
            "read_only": True,
            "error": "conflict_preflight_required",
            "conflict_preflight": conflict_preflight,
            "retrieval_policy": "default_retrieval_remains_approved_only",
        }

    evidence = explanation["evidence"]
    provenance_source = ingest_source_text(
        db_path=db_path,
        source_type="consolidation_candidate",
        content=json.dumps(
            {
                "candidate_id": candidate_id,
                "safe_summaries": evidence["safe_summaries"],
                "scope": scope,
                "subject_ref": subject_ref,
                "predicate": predicate,
                "object_ref_or_value": object_ref_or_value,
            },
            sort_keys=True,
        ),
        metadata={
            "candidate_id": candidate_id,
            "trace_ids": evidence["trace_ids"],
            "related_observation_ids": evidence["related_observation_ids"],
            "promotion_kind": "manual_reviewed_fact",
        },
        adapter="agent-memory",
        external_ref=candidate_id,
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref=subject_ref,
        predicate=predicate,
        object_ref_or_value=object_ref_or_value,
        evidence_ids=[provenance_source.id],
        scope=scope,
        confidence=confidence,
    )
    if approve:
        fact = approve_memory(
            db_path=db_path,
            memory_type="fact",
            memory_id=fact.id,
            reason=reason,
            actor=actor,
            evidence_ids=[provenance_source.id],
        )

    lineage = _record_consolidation_promotion_lineage(
        db_path,
        candidate_id=candidate_id,
        fact_id=fact.id,
        provenance_source_id=provenance_source.id,
        confidence=confidence,
    )

    return {
        "kind": "memory_consolidation_promotion",
        "candidate_id": candidate_id,
        "memory_type": "fact",
        "promoted": True,
        "approved": approve,
        "status": fact.status,
        "fact": fact.model_dump(mode="json"),
        "provenance_source_id": provenance_source.id,
        "provenance": {
            "source_type": provenance_source.source_type,
            "trace_ids": evidence["trace_ids"],
            "related_observation_ids": evidence["related_observation_ids"],
            "safe_summaries": evidence["safe_summaries"],
            "candidate_fingerprint": explanation["candidate"]["fingerprint"],
        },
        "conflict_preflight": conflict_preflight,
        "lineage": lineage,
        "retrieval_policy": "default_retrieval_remains_approved_only",
    }


def _consolidation_candidates_report(db_path: Path, *, limit: int, top: int, min_evidence: int) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("consolidation candidates limit must be >= 1")
    if top < 1:
        raise ValueError("consolidation candidates top must be >= 1")
    if min_evidence < 1:
        raise ValueError("consolidation candidates min evidence must be >= 1")

    traces = list_experience_traces(db_path, limit=limit)
    clusters: dict[str, list[Any]] = defaultdict(list)
    for trace in traces:
        clusters[_consolidation_cluster_key(trace)].append(trace)

    candidates = [
        _consolidation_candidate_payload(db_path, cluster_key=cluster_key, traces=cluster_traces)
        for cluster_key, cluster_traces in clusters.items()
        if len(cluster_traces) >= min_evidence
    ]
    candidates.sort(
        key=lambda candidate: (
            -candidate["evidence_count"],
            -candidate["reinforcement"]["activation_count"],
            candidate["cluster_key"],
        )
    )

    quality_warnings = []
    if not traces:
        quality_warnings.append("no_traces")
    elif len(candidates) == 0:
        quality_warnings.append("no_clusters_meet_min_evidence")

    return {
        "kind": "memory_consolidation_candidates",
        "read_only": True,
        "trace_count": len(traces),
        "candidate_count": len(candidates[:top]),
        "limit": limit,
        "top": top,
        "min_evidence": min_evidence,
        "quality_warnings": quality_warnings,
        "candidates": candidates[:top],
        "suggested_next_steps": [
            "Inspect candidate explanations before any promotion workflow.",
            "Keep this report read-only; do not create or approve long-term memories automatically.",
            "Use candidate fingerprints for future reject/snooze workflows only after human review UX exists.",
        ],
    }


def _write_json_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _consolidation_background_dry_run_report(
    db_path: Path,
    *,
    limit: int,
    top: int,
    min_evidence: int,
    frequent_threshold: int,
    output_path: Path | None,
    lock_path: Path,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("consolidation background dry-run limit must be >= 1")
    if top < 1:
        raise ValueError("consolidation background dry-run top must be >= 1")
    if min_evidence < 1:
        raise ValueError("consolidation background dry-run min evidence must be >= 1")
    if frequent_threshold < 1:
        raise ValueError("consolidation background dry-run frequent threshold must be >= 1")

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            payload = {
                "kind": "memory_consolidation_background_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "status": "skipped_lock_busy",
                "error": None,
                "db_path": str(db_path),
                "output_path": str(output_path) if output_path is not None else None,
                "lock": {
                    "path": str(lock_path),
                    "acquired": False,
                    "mode": "non_blocking_exclusive",
                },
                "automation_policy": {
                    "apply_supported": False,
                    "ordinary_conversation_auto_approval": False,
                    "requires_human_review": True,
                },
                "reports": {},
                "review_handoff": {
                    "suitable_for_human_review": False,
                    "reason": "background_dry_run_already_running",
                    "next_steps": ["Keep the existing run; skipped runs are cron-safe and do not mutate memory."],
                },
            }
            _write_json_report(output_path, payload)
            return payload

        try:
            candidates = _consolidation_candidates_report(db_path, limit=limit, top=top, min_evidence=min_evidence)
            activation_summary = _activation_summary(
                db_path,
                limit=limit,
                top=top,
                frequent_threshold=frequent_threshold,
            )
            reinforcement = _activation_reinforcement_report(
                db_path,
                limit=limit,
                top=top,
                frequent_threshold=frequent_threshold,
            )
            decay_risk = _activation_decay_risk_report(
                db_path,
                limit=limit,
                top=top,
                frequent_threshold=frequent_threshold,
            )
            quality_warnings = sorted(
                set(
                    candidates.get("quality_warnings", [])
                    + activation_summary.get("quality_warnings", [])
                    + reinforcement.get("quality_warnings", [])
                    + decay_risk.get("quality_warnings", [])
                )
            )
            payload = {
                "kind": "memory_consolidation_background_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "status": "completed",
                "error": None,
                "db_path": str(db_path),
                "output_path": str(output_path) if output_path is not None else None,
                "lock": {
                    "path": str(lock_path),
                    "acquired": True,
                    "mode": "non_blocking_exclusive",
                },
                "scan": {
                    "limit": limit,
                    "top": top,
                    "min_evidence": min_evidence,
                    "frequent_threshold": frequent_threshold,
                    "quality_warnings": quality_warnings,
                },
                "automation_policy": {
                    "apply_supported": False,
                    "ordinary_conversation_auto_approval": False,
                    "requires_human_review": True,
                    "default_retrieval_policy": "approved_only_unchanged",
                },
                "reports": {
                    "candidates": candidates,
                    "activation_summary": activation_summary,
                    "reinforcement": reinforcement,
                    "decay_risk": decay_risk,
                },
                "review_handoff": {
                    "suitable_for_human_review": True,
                    "candidate_count": candidates.get("candidate_count", 0),
                    "reinforcement_candidate_count": reinforcement.get("candidate_count", 0),
                    "decay_risk_candidate_count": len(decay_risk.get("decay_risk_candidates", [])),
                    "next_steps": [
                        "Review this JSON report manually; it is intentionally read-only.",
                        "Use existing explain/promote/auto-approve commands only as explicit follow-up actions.",
                        "Do not infer or approve ordinary conversation memories from this background dry-run.",
                    ],
                },
            }
        except Exception as exc:
            payload = {
                "kind": "memory_consolidation_background_dry_run",
                "read_only": True,
                "mutated": False,
                "default_retrieval_unchanged": True,
                "status": "failed",
                "error": {
                    "type": exc.__class__.__name__,
                    "message": str(exc),
                },
                "db_path": str(db_path),
                "output_path": str(output_path) if output_path is not None else None,
                "lock": {
                    "path": str(lock_path),
                    "acquired": True,
                    "mode": "non_blocking_exclusive",
                },
                "automation_policy": {
                    "apply_supported": False,
                    "ordinary_conversation_auto_approval": False,
                    "requires_human_review": True,
                    "default_retrieval_policy": "approved_only_unchanged",
                },
                "reports": {},
                "review_handoff": {
                    "suitable_for_human_review": False,
                    "reason": "background_dry_run_failed_before_report_generation",
                    "next_steps": [
                        "Inspect the error object and rerun manually after fixing the local database or environment.",
                        "No memory mutations were attempted by this dry-run command.",
                    ],
                },
            }
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        _write_json_report(output_path, payload)
        return payload


def _activation_summary(db_path: Path, *, limit: int, top: int, frequent_threshold: int) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("activations summary limit must be >= 1")
    if top < 1:
        raise ValueError("activations summary top must be >= 1")
    if frequent_threshold < 1:
        raise ValueError("activations summary frequent threshold must be >= 1")

    activations = list_memory_activations(db_path, limit=limit)
    surface_counts = Counter(activation.surface for activation in activations)
    kind_counts = Counter(activation.activation_kind for activation in activations)
    scope_counts = Counter(activation.scope for activation in activations if activation.scope is not None)
    empty_retrieval_activations = [activation for activation in activations if activation.activation_kind == "empty_retrieval"]

    activations_by_ref: dict[str, list[Any]] = defaultdict(list)
    for activation in activations:
        if activation.memory_ref is not None:
            activations_by_ref[activation.memory_ref].append(activation)

    status_summary: Counter[str] = Counter()
    top_memory_refs = []
    for memory_ref, ref_activations in sorted(
        activations_by_ref.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )[:top]:
        current_status = _current_status_for_memory_ref(db_path, memory_ref)
        if current_status is not None:
            status_summary[current_status] += 1
        activation_count = len(ref_activations)
        signals = []
        if activation_count >= frequent_threshold:
            signals.append("frequently_activated")
        if current_status is not None and current_status != "approved":
            signals.append("current_status_not_approved")
        if current_status == "deprecated":
            signals.append("deprecated_activation")
        elif current_status == "disputed":
            signals.append("disputed_activation")
        elif current_status == "missing":
            signals.append("missing_memory_ref")
        elif current_status == "approved" and activation_count >= frequent_threshold:
            signals.append("likely_reinforcement_candidate")

        observation_ids = []
        for activation in ref_activations:
            if activation.observation_id is not None and activation.observation_id not in observation_ids:
                observation_ids.append(activation.observation_id)
            if len(observation_ids) >= 5:
                break

        top_memory_refs.append(
            {
                "memory_ref": memory_ref,
                "activation_count": activation_count,
                "total_strength": round(sum(activation.strength for activation in ref_activations), 4),
                "current_status": current_status,
                "signals": signals,
                "sample_activation_ids": [activation.id for activation in ref_activations[:5]],
                "sample_observation_ids": observation_ids,
                "activation_window": _activation_window(ref_activations),
            }
        )

    empty_ratio = len(empty_retrieval_activations) / len(activations) if activations else 0.0
    quality_warnings = []
    if not activations:
        quality_warnings.append("no_activations")
    if 0 < len(activations) < 10:
        quality_warnings.append("low_activation_count")
    if empty_ratio >= 0.5 and activations:
        quality_warnings.append("high_empty_retrieval_activation_ratio")

    return {
        "kind": "memory_activation_summary",
        "read_only": True,
        "activation_count": len(activations),
        "limit": limit,
        "top": top,
        "frequent_threshold": frequent_threshold,
        "activation_window": _activation_window(activations),
        "activation_kind_counts": dict(sorted(kind_counts.items())),
        "surface_counts": dict(sorted(surface_counts.items())),
        "scope_counts": dict(sorted(scope_counts.items())),
        "status_summary": dict(sorted(status_summary.items())),
        "empty_retrieval": {
            "count": len(empty_retrieval_activations),
            "ratio": round(empty_ratio, 4),
            "sample_activation_ids": [activation.id for activation in empty_retrieval_activations[:5]],
            "sample_observation_ids": [
                activation.observation_id
                for activation in empty_retrieval_activations[:5]
                if activation.observation_id is not None
            ],
        },
        "quality_warnings": quality_warnings,
        "top_memory_refs": top_memory_refs,
        "suggested_next_steps": [
            "Run observations audit to compare activation refs with retrieval observation behavior.",
            "Run observations empty-diagnostics if empty_retrieval is high for a surface or scope.",
            "Use future reinforcement/decay reports before changing retrieval ranking or memory status.",
        ],
    }


def _empty_diagnostic_segment_payload(
    *,
    segment_name: str,
    segment_value: Any,
    observations,
    high_empty_threshold: float,
) -> dict[str, Any]:
    empty_observations = [observation for observation in observations if not observation.retrieved_memory_refs]
    total_count = len(observations)
    empty_count = len(empty_observations)
    empty_ratio = empty_count / total_count if total_count else 0.0
    signals = []
    if empty_ratio >= high_empty_threshold and empty_count > 0:
        signals.append("high_empty_segment")
    return {
        segment_name: segment_value,
        "total_count": total_count,
        "empty_count": empty_count,
        "empty_ratio": round(empty_ratio, 4),
        "signals": signals,
        "sample_observation_ids": [observation.id for observation in empty_observations[:5]],
        "observation_window": _observation_window(observations),
    }


def _empty_retrieval_diagnostics(
    db_path: Path,
    *,
    limit: int,
    top: int,
    high_empty_threshold: float,
) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("observations empty-diagnostics limit must be >= 1")
    if top < 1:
        raise ValueError("observations empty-diagnostics top must be >= 1")
    if high_empty_threshold < 0 or high_empty_threshold > 1:
        raise ValueError("observations empty-diagnostics high empty threshold must be between 0 and 1")

    observations = list_retrieval_observations(db_path, limit=limit)
    empty_observations = [observation for observation in observations if not observation.retrieved_memory_refs]
    empty_retrieval_ratio = len(empty_observations) / len(observations) if observations else 0.0

    observations_by_surface: dict[str, list[Any]] = defaultdict(list)
    observations_by_scope: dict[str | None, list[Any]] = defaultdict(list)
    observations_by_statuses: dict[tuple[str, ...], list[Any]] = defaultdict(list)
    for observation in observations:
        observations_by_surface[observation.surface].append(observation)
        observations_by_scope[observation.preferred_scope].append(observation)
        observations_by_statuses[tuple(observation.statuses)].append(observation)

    def sort_segments(items):
        return sorted(
            items,
            key=lambda item: (-item["empty_count"], -item["empty_ratio"], str(next(iter(item.values())))),
        )[:top]

    empty_by_surface = sort_segments(
        [
            _empty_diagnostic_segment_payload(
                segment_name="surface",
                segment_value=surface,
                observations=segment_observations,
                high_empty_threshold=high_empty_threshold,
            )
            for surface, segment_observations in observations_by_surface.items()
        ]
    )
    empty_by_preferred_scope = sort_segments(
        [
            _empty_diagnostic_segment_payload(
                segment_name="preferred_scope",
                segment_value=preferred_scope,
                observations=segment_observations,
                high_empty_threshold=high_empty_threshold,
            )
            for preferred_scope, segment_observations in observations_by_scope.items()
        ]
    )
    empty_by_status_filter = sort_segments(
        [
            _empty_diagnostic_segment_payload(
                segment_name="statuses",
                segment_value=list(statuses),
                observations=segment_observations,
                high_empty_threshold=high_empty_threshold,
            )
            for statuses, segment_observations in observations_by_statuses.items()
        ]
    )

    quality_warnings = []
    if not observations:
        quality_warnings.append("no_observations")
    if 0 < len(observations) < 10:
        quality_warnings.append("low_observation_count")
    if empty_retrieval_ratio >= high_empty_threshold and observations:
        quality_warnings.append("high_empty_retrieval_ratio")

    return {
        "kind": "retrieval_empty_diagnostics",
        "read_only": True,
        "observation_count": len(observations),
        "limit": limit,
        "top": top,
        "high_empty_threshold": high_empty_threshold,
        "empty_retrieval_count": len(empty_observations),
        "empty_retrieval_ratio": round(empty_retrieval_ratio, 4),
        "quality_warnings": quality_warnings,
        "observation_window": _observation_window(observations),
        "empty_by_surface": empty_by_surface,
        "empty_by_preferred_scope": empty_by_preferred_scope,
        "empty_by_status_filter": empty_by_status_filter,
        "suggested_next_steps": [
            "Run observations audit to compare empty vs non-empty retrieval surfaces.",
            "Check preferred scope values for scope mismatches before changing ranking.",
            "Add or approve memories only after confirming the missing queries represent durable user needs.",
        ],
    }


def _review_candidates_from_observations(
    db_path: Path,
    *,
    limit: int,
    top: int,
    frequent_threshold: int,
) -> dict[str, Any]:
    audit = _audit_retrieval_observations(
        db_path,
        limit=limit,
        top=top,
        frequent_threshold=frequent_threshold,
    )
    candidates = []
    for top_ref in audit["top_memory_refs"]:
        memory_ref = top_ref["memory_ref"]
        parts = _memory_ref_parts(memory_ref)
        review_explain = None
        replacement_chain = None
        if parts is not None and parts[0] == "fact" and top_ref["current_status"] != "missing":
            review_explain = _fact_review_explanation_payload(db_path, fact_id=parts[1])
            replacement_chain = review_explain["replacement_chain"]

        graph = _inspect_relation_graph(db_path, start_ref=memory_ref, depth=1, limit=25)
        signals = list(top_ref["signals"])
        if replacement_chain is not None and (
            replacement_chain["superseded_by"] or replacement_chain["replaces"]
        ):
            signals.append("has_replacement")
        if graph["edges"]:
            signals.append("has_graph_relations")

        history = review_explain["history"] if review_explain is not None else []
        status_history_summary = {
            "transition_count": len(history),
            "latest_transition": history[-1] if history else None,
        }

        commands = {"graph_inspect": f"agent-memory graph inspect {db_path} {memory_ref} --depth 1"}
        if parts is not None:
            memory_type, memory_id = parts
            if memory_type == "fact":
                commands["review_explain"] = f"agent-memory review explain fact {db_path} {memory_id}"
                commands["review_replacements"] = f"agent-memory review replacements fact {db_path} {memory_id}"

        ordered_commands = {}
        for command_name in ("review_explain", "review_replacements", "graph_inspect"):
            if command_name in commands:
                ordered_commands[command_name] = commands[command_name]

        candidates.append(
            {
                **top_ref,
                "signals": signals,
                "review_explain": review_explain,
                "status_history_summary": status_history_summary,
                "graph_summary": {
                    "start_ref": graph["start_ref"],
                    "depth": graph["depth"],
                    "edge_count": len(graph["edges"]),
                    "neighbor_refs": [edge["neighbor_ref"] for edge in graph["edges"]],
                    "truncated": graph["truncated"],
                },
                "commands": ordered_commands,
            }
        )

    return {
        "kind": "retrieval_observation_review_candidates",
        "read_only": True,
        "observation_count": audit["observation_count"],
        "candidate_count": len(candidates),
        "observation_audit": audit,
        "candidates": candidates,
    }


def _memory_status_counts(db_path: Path) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    with connect(db_path) as connection:
        for payload_name, table_name in (
            ("facts", "facts"),
            ("procedures", "procedures"),
            ("episodes", "episodes"),
        ):
            rows = connection.execute(
                f"SELECT status, COUNT(*) AS count FROM {table_name} GROUP BY status ORDER BY status"
            ).fetchall()
            counts[payload_name] = {row["status"]: row["count"] for row in rows}
    return counts


def _database_baseline_payload(db_path: Path) -> dict[str, Any]:
    resolved_path = db_path.expanduser().resolve(strict=False)
    payload: dict[str, Any] = {
        "path": str(resolved_path),
        "path_exists": resolved_path.exists(),
        "schema_user_version": None,
    }
    if resolved_path.exists():
        with connect(resolved_path) as connection:
            payload["schema_user_version"] = connection.execute("PRAGMA user_version").fetchone()[0]
    return payload


def _hermes_baseline_payload(args: argparse.Namespace) -> dict[str, Any]:
    doctor = diagnose_hermes_hook_setup(
        HermesHookInstallOptions(
            config_path=args.config_path,
            snippet_options=HermesHookConfigSnippetOptions(
                db_path=args.db_path,
                python_executable=args.python_executable,
                limit=args.hook_limit,
                preferred_scope=args.preferred_scope,
                top_k=args.top_k or 1,
                max_prompt_lines=args.max_prompt_lines,
                max_prompt_chars=args.max_prompt_chars,
                max_prompt_tokens=args.max_prompt_tokens,
                max_verification_steps=args.max_verification_steps,
                max_alternatives=args.max_alternatives,
                max_guidelines=args.max_guidelines,
                include_reason_codes=not args.no_reason_codes,
                timeout=args.timeout or 10,
            ),
        )
    ).model_dump(mode="json")
    doctor.pop("recommended_command", None)
    return doctor


def _signal_review_candidates_for_baseline(review_candidates: dict[str, Any]) -> dict[str, Any]:
    signal_candidates = [candidate for candidate in review_candidates["candidates"] if candidate["signals"]]
    return {
        "kind": review_candidates["kind"],
        "read_only": review_candidates["read_only"],
        "observation_count": review_candidates["observation_count"],
        "candidate_count": len(signal_candidates),
        "candidates": signal_candidates,
    }


def _dogfood_baseline_payload(args: argparse.Namespace) -> dict[str, Any]:
    audit = _audit_retrieval_observations(
        args.db_path,
        limit=args.limit,
        top=args.top,
        frequent_threshold=args.frequent_threshold,
    )
    empty_diagnostics = _empty_retrieval_diagnostics(
        args.db_path,
        limit=args.limit,
        top=args.top,
        high_empty_threshold=args.high_empty_threshold,
    )
    review_candidates = _signal_review_candidates_for_baseline(
        _review_candidates_from_observations(
            args.db_path,
            limit=args.limit,
            top=args.top,
            frequent_threshold=args.frequent_threshold,
        )
    )
    suggested_next_steps = []
    if "no_observations" in audit["quality_warnings"]:
        suggested_next_steps.append("Run agent-memory retrieve with --observe from Hermes or CLI surfaces before judging retrieval quality.")
    if audit["empty_retrieval_count"]:
        suggested_next_steps.append("Inspect empty_diagnostics before adding memories or changing ranking.")
    if review_candidates["candidate_count"]:
        suggested_next_steps.append("Review signal-bearing injected memories for stale status, replacement chains, or graph context.")
    if not suggested_next_steps:
        suggested_next_steps.append("Keep collecting observations and compare this baseline after retrieval or hook changes.")

    return {
        "kind": "dogfood_baseline",
        "read_only": True,
        "agent_memory_version": __version__,
        "database": _database_baseline_payload(args.db_path),
        "memory_counts": _memory_status_counts(args.db_path),
        "observation_summary": audit,
        "empty_diagnostics": empty_diagnostics,
        "review_candidates": review_candidates,
        "hermes": _hermes_baseline_payload(args),
        "local_e2e_marker": {
            "target_phrase": "not_executed",
            "reason": "baseline is read-only; run a separate local E2E smoke for write-path validation",
        },
        "suggested_next_steps": suggested_next_steps,
    }


def _inspect_relation_graph(db_path: Path, *, start_ref: str, depth: int, limit: int) -> dict[str, Any]:
    if depth < 0:
        raise ValueError("graph inspect depth must be >= 0")
    if limit < 1:
        raise ValueError("graph inspect limit must be >= 1")
    nodes: list[str] = [start_ref]
    seen_nodes = {start_ref}
    seen_edge_ids: set[int] = set()
    edges: list[dict[str, Any]] = []
    frontier = [start_ref]
    truncated = False
    for current_depth in range(1, depth + 1):
        next_frontier: list[str] = []
        for node_ref in frontier:
            for relation in list_relations_for_node(db_path, node_ref=node_ref):
                if relation.id in seen_edge_ids:
                    continue
                if len(edges) >= limit:
                    truncated = True
                    break
                seen_edge_ids.add(relation.id)
                if relation.from_ref == node_ref:
                    neighbor_ref = relation.to_ref
                    direction = "outbound"
                else:
                    neighbor_ref = relation.from_ref
                    direction = "inbound"
                if neighbor_ref not in seen_nodes:
                    seen_nodes.add(neighbor_ref)
                    nodes.append(neighbor_ref)
                    next_frontier.append(neighbor_ref)
                edge_payload = relation.model_dump(mode="json")
                edge_payload["depth"] = current_depth
                edge_payload["via_ref"] = node_ref
                edge_payload["neighbor_ref"] = neighbor_ref
                edge_payload["direction_from_start"] = direction
                edges.append(edge_payload)
            if truncated:
                break
        if truncated or not next_frontier:
            break
        frontier = next_frontier
    return {
        "kind": "relation_graph_inspection",
        "start_ref": start_ref,
        "depth": depth,
        "limit": limit,
        "read_only": True,
        "nodes": nodes,
        "edges": edges,
        "truncated": truncated,
    }


def _retrieve_packet_for_prompt(args: argparse.Namespace):
    return retrieve_memory_packet(
        db_path=args.db_path,
        query=args.query,
        limit=args.limit,
        preferred_scope=args.preferred_scope,
    )


def _render_memory_context_for_prompt(args: argparse.Namespace):
    packet = _retrieve_packet_for_prompt(args)
    return prepare_hermes_memory_context(
        packet,
        top_k=args.top_k,
        max_prompt_lines=args.max_prompt_lines,
        max_prompt_chars=args.max_prompt_chars,
        max_prompt_tokens=args.max_prompt_tokens,
        max_verification_steps=args.max_verification_steps,
        max_alternatives=args.max_alternatives,
        max_guidelines=args.max_guidelines,
        include_reason_codes=not args.no_reason_codes,
    )


def _render_external_agent_prompt_text(args: argparse.Namespace) -> str:
    packet = _retrieve_packet_for_prompt(args)
    context = prepare_hermes_memory_context(
        packet,
        top_k=args.top_k,
        max_prompt_lines=None,
        max_prompt_chars=None,
        max_prompt_tokens=None,
        max_verification_steps=args.max_verification_steps,
        max_alternatives=args.max_alternatives,
        max_guidelines=args.max_guidelines,
        include_reason_codes=not args.no_reason_codes,
    )
    return context.prompt_text


def _normalize_command_aliases(argv: list[str]) -> list[str]:
    alias_map = {
        "bootstrap": "hermes-bootstrap",
        "doctor": "hermes-doctor",
    }
    if not argv:
        return argv
    return [alias_map.get(argv[0], argv[0]), *argv[1:]]


HERMES_HOOK_PRESETS = {
    "conservative": {
        "top_k": 1,
        "max_prompt_lines": 6,
        "max_prompt_chars": 800,
        "max_prompt_tokens": 200,
        "max_verification_steps": 1,
        "max_alternatives": 0,
        "max_guidelines": 1,
        "no_reason_codes": True,
        "timeout": 8,
    },
    "balanced": {
        "top_k": 3,
        "max_prompt_lines": 8,
        "max_prompt_chars": 1200,
        "max_prompt_tokens": 300,
        "max_verification_steps": None,
        "max_alternatives": 2,
        "max_guidelines": None,
        "no_reason_codes": False,
        "timeout": 12,
    },
}


def _add_hermes_hook_preset_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--preset",
        choices=sorted(HERMES_HOOK_PRESETS),
        default="conservative",
        help="Apply a Hermes hook budget preset before explicit flag overrides.",
    )


def _apply_hermes_hook_preset(args: argparse.Namespace) -> None:
    preset_name = getattr(args, "preset", None)
    if preset_name is None:
        return
    preset = HERMES_HOOK_PRESETS[preset_name]
    for field, value in preset.items():
        if field == "no_reason_codes":
            if value:
                args.no_reason_codes = True
            continue
        if hasattr(args, field) and getattr(args, field) is None:
            setattr(args, field, value)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agent-memory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("db_path", type=Path)

    ingest_parser = subparsers.add_parser("ingest-source")
    ingest_parser.add_argument("db_path", type=Path)
    ingest_parser.add_argument("source_type")
    ingest_parser.add_argument("content")
    ingest_parser.add_argument("--metadata-json", default="{}")
    ingest_parser.add_argument("--adapter")
    ingest_parser.add_argument("--external-ref")

    create_fact_parser = subparsers.add_parser("create-fact")
    create_fact_parser.add_argument("db_path", type=Path)
    create_fact_parser.add_argument("subject_ref")
    create_fact_parser.add_argument("predicate")
    create_fact_parser.add_argument("object_ref_or_value")
    create_fact_parser.add_argument("scope")
    create_fact_parser.add_argument("--evidence-ids-json", default="[]")
    create_fact_parser.add_argument("--confidence", type=float, default=0.5)

    approve_fact_parser = subparsers.add_parser("approve-fact")
    approve_fact_parser.add_argument("db_path", type=Path)
    approve_fact_parser.add_argument("fact_id", type=int)

    list_candidate_facts_parser = subparsers.add_parser("list-candidate-facts")
    list_candidate_facts_parser.add_argument("db_path", type=Path)
    list_candidate_facts_parser.add_argument("--limit", type=int, default=50)

    create_procedure_parser = subparsers.add_parser("create-procedure")
    create_procedure_parser.add_argument("db_path", type=Path)
    create_procedure_parser.add_argument("name")
    create_procedure_parser.add_argument("trigger_context")
    create_procedure_parser.add_argument("scope")
    create_procedure_parser.add_argument("--preconditions-json", default="[]")
    create_procedure_parser.add_argument("--steps-json", default="[]")
    create_procedure_parser.add_argument("--evidence-ids-json", default="[]")
    create_procedure_parser.add_argument("--success-rate", type=float, default=0.0)

    approve_procedure_parser = subparsers.add_parser("approve-procedure")
    approve_procedure_parser.add_argument("db_path", type=Path)
    approve_procedure_parser.add_argument("procedure_id", type=int)

    list_candidate_procedures_parser = subparsers.add_parser("list-candidate-procedures")
    list_candidate_procedures_parser.add_argument("db_path", type=Path)
    list_candidate_procedures_parser.add_argument("--limit", type=int, default=50)

    create_episode_parser = subparsers.add_parser("create-episode")
    create_episode_parser.add_argument("db_path", type=Path)
    create_episode_parser.add_argument("title")
    create_episode_parser.add_argument("summary")
    create_episode_parser.add_argument("--source-ids-json", default="[]")
    create_episode_parser.add_argument("--tags-json", default="[]")
    create_episode_parser.add_argument("--importance-score", type=float, default=0.0)
    create_episode_parser.add_argument("--scope", default="global")
    create_episode_parser.add_argument("--status", default="candidate")
    create_episode_parser.add_argument("--started-at")
    create_episode_parser.add_argument("--ended-at")

    list_candidate_episodes_parser = subparsers.add_parser("list-candidate-episodes")
    list_candidate_episodes_parser.add_argument("db_path", type=Path)
    list_candidate_episodes_parser.add_argument("--limit", type=int, default=50)

    kb_parser = subparsers.add_parser("kb")
    kb_subparsers = kb_parser.add_subparsers(dest="kb_action", required=True)
    kb_export_parser = kb_subparsers.add_parser("export")
    kb_export_parser.add_argument("db_path", type=Path)
    kb_export_parser.add_argument("output_dir", type=Path)
    kb_export_parser.add_argument("--scope")

    review_parser = subparsers.add_parser("review")
    review_subparsers = review_parser.add_subparsers(dest="review_action", required=True)
    for action_name in ["approve", "dispute", "deprecate"]:
        action_parser = review_subparsers.add_parser(action_name)
        action_parser.add_argument("memory_type", choices=["fact", "procedure", "episode"])
        action_parser.add_argument("db_path", type=Path)
        action_parser.add_argument("memory_id", type=int)
        action_parser.add_argument("--reason")
        action_parser.add_argument("--actor")
        action_parser.add_argument("--evidence-ids-json", default="[]")

    review_supersede_parser = review_subparsers.add_parser(
        "supersede",
        help="Mark one fact as superseded by another fact and record a replacement relation.",
    )
    review_supersede_parser.add_argument("memory_type", choices=["fact"])
    review_supersede_parser.add_argument("db_path", type=Path)
    review_supersede_parser.add_argument("superseded_memory_id", type=int)
    review_supersede_parser.add_argument("replacement_memory_id", type=int)
    review_supersede_parser.add_argument("--reason")
    review_supersede_parser.add_argument("--actor")
    review_supersede_parser.add_argument("--evidence-ids-json", default="[]")

    review_replacements_parser = review_subparsers.add_parser(
        "replacements",
        help="Show supersedes/replaces relations for one fact.",
    )
    review_replacements_parser.add_argument("memory_type", choices=["fact"])
    review_replacements_parser.add_argument("db_path", type=Path)
    review_replacements_parser.add_argument("memory_id", type=int)

    review_relate_conflict_parser = review_subparsers.add_parser(
        "relate-conflict",
        help="Record a human-reviewed conflict relation between two same-claim-slot facts without changing statuses.",
    )
    review_relate_conflict_parser.add_argument("memory_type", choices=["fact"])
    review_relate_conflict_parser.add_argument("db_path", type=Path)
    review_relate_conflict_parser.add_argument("left_memory_id", type=int)
    review_relate_conflict_parser.add_argument("right_memory_id", type=int)
    review_relate_conflict_parser.add_argument("--reason", required=True)
    review_relate_conflict_parser.add_argument("--actor", required=True)
    review_relate_conflict_parser.add_argument("--evidence-ids-json", default="[]")

    review_history_parser = review_subparsers.add_parser(
        "history",
        help="Show status transition history for one memory item.",
    )
    review_history_parser.add_argument("memory_type", choices=["fact", "procedure", "episode"])
    review_history_parser.add_argument("db_path", type=Path)
    review_history_parser.add_argument("memory_id", type=int)

    review_explain_parser = review_subparsers.add_parser(
        "explain",
        help="Explain why one memory is or is not visible in default retrieval.",
    )
    review_explain_parser.add_argument("memory_type", choices=["fact"])
    review_explain_parser.add_argument("db_path", type=Path)
    review_explain_parser.add_argument("memory_id", type=int)

    review_conflicts_parser = review_subparsers.add_parser(
        "conflicts",
        help="Inspect all fact statuses for one subject/predicate claim slot without changing default retrieval policy.",
    )
    review_conflicts_parser.add_argument("memory_type", choices=["fact"])
    review_conflicts_parser.add_argument("db_path", type=Path)
    review_conflicts_parser.add_argument("subject_ref")
    review_conflicts_parser.add_argument("predicate")
    review_conflicts_parser.add_argument("--scope")

    retrieve_parser = subparsers.add_parser("retrieve")
    retrieve_parser.add_argument("db_path", type=Path)
    retrieve_parser.add_argument("query")
    retrieve_parser.add_argument("--limit", type=int, default=5)
    retrieve_parser.add_argument("--preferred-scope")
    retrieve_parser.add_argument(
        "--status",
        choices=["approved", "candidate", "disputed", "deprecated", "all"],
        default="approved",
        help="Memory status to retrieve. Defaults to approved; use all for forensic/debug review.",
    )
    retrieve_parser.add_argument(
        "--observe",
        metavar="SURFACE",
        help="Record a secret-safe local retrieval observation for this query.",
    )

    retrieval_parser = subparsers.add_parser(
        "retrieval",
        help="Read-only retrieval policy previews and diagnostics.",
    )
    retrieval_subparsers = retrieval_parser.add_subparsers(dest="retrieval_action", required=True)
    retrieval_policy_preview_parser = retrieval_subparsers.add_parser(
        "policy-preview",
        help="Preview conservative lifecycle-aware retrieval policy effects without mutating ranking or memory state.",
    )
    retrieval_policy_preview_parser.add_argument("db_path", type=Path)
    retrieval_policy_preview_parser.add_argument("query")
    retrieval_policy_preview_parser.add_argument("--limit", type=int, default=5)
    retrieval_policy_preview_parser.add_argument("--preferred-scope")

    retrieval_ranker_preview_parser = retrieval_subparsers.add_parser(
        "ranker-preview",
        help="Preview opt-in reinforcement-aware ranking without mutating default retrieval or memory state.",
    )
    retrieval_ranker_preview_parser.add_argument("db_path", type=Path)
    retrieval_ranker_preview_parser.add_argument("query")
    retrieval_ranker_preview_parser.add_argument("--limit", type=int, default=5)
    retrieval_ranker_preview_parser.add_argument("--preferred-scope")
    retrieval_ranker_preview_parser.add_argument("--reinforcement-weight", type=float, default=0.15)
    retrieval_ranker_preview_parser.add_argument("--reinforcement-cap", type=float, default=0.5)

    retrieval_decay_preview_parser = retrieval_subparsers.add_parser(
        "decay-preview",
        help="Preview opt-in decay-risk prompt-time noise penalties without mutating default retrieval or memory state.",
    )
    retrieval_decay_preview_parser.add_argument("db_path", type=Path)
    retrieval_decay_preview_parser.add_argument("query")
    retrieval_decay_preview_parser.add_argument("--limit", type=int, default=5)
    retrieval_decay_preview_parser.add_argument("--preferred-scope")
    retrieval_decay_preview_parser.add_argument("--decay-weight", type=float, default=0.2)
    retrieval_decay_preview_parser.add_argument("--frequent-threshold", type=int, default=3)

    retrieval_graph_neighborhood_preview_parser = retrieval_subparsers.add_parser(
        "graph-neighborhood-preview",
        help="Preview opt-in bounded graph-neighborhood reinforcement without mutating default retrieval or memory state.",
    )
    retrieval_graph_neighborhood_preview_parser.add_argument("db_path", type=Path)
    retrieval_graph_neighborhood_preview_parser.add_argument("query")
    retrieval_graph_neighborhood_preview_parser.add_argument("--limit", type=int, default=5)
    retrieval_graph_neighborhood_preview_parser.add_argument("--preferred-scope")
    retrieval_graph_neighborhood_preview_parser.add_argument("--depth", type=int, default=1)
    retrieval_graph_neighborhood_preview_parser.add_argument("--graph-weight", type=float, default=0.15)
    retrieval_graph_neighborhood_preview_parser.add_argument("--graph-cap", type=float, default=0.5)
    retrieval_graph_neighborhood_preview_parser.add_argument("--neighbor-reinforcement-weight", type=float, default=0.1)

    observations_parser = subparsers.add_parser("observations")
    observations_subparsers = observations_parser.add_subparsers(dest="observations_action", required=True)
    observations_list_parser = observations_subparsers.add_parser("list")
    observations_list_parser.add_argument("db_path", type=Path)
    observations_list_parser.add_argument("--limit", type=int, default=50)
    observations_audit_parser = observations_subparsers.add_parser("audit")
    observations_audit_parser.add_argument("db_path", type=Path)
    observations_audit_parser.add_argument("--limit", type=int, default=200)
    observations_audit_parser.add_argument("--top", type=int, default=10)
    observations_audit_parser.add_argument("--frequent-threshold", type=int, default=3)
    observations_empty_diagnostics_parser = observations_subparsers.add_parser(
        "empty-diagnostics",
        help="Build a read-only diagnostic report for empty retrieval observations.",
    )
    observations_empty_diagnostics_parser.add_argument("db_path", type=Path)
    observations_empty_diagnostics_parser.add_argument("--limit", type=int, default=200)
    observations_empty_diagnostics_parser.add_argument("--top", type=int, default=10)
    observations_empty_diagnostics_parser.add_argument("--high-empty-threshold", type=float, default=0.5)
    observations_review_candidates_parser = observations_subparsers.add_parser(
        "review-candidates",
        help="Build a read-only forensic review report from top retrieval observation refs.",
    )
    observations_review_candidates_parser.add_argument("db_path", type=Path)
    observations_review_candidates_parser.add_argument("--limit", type=int, default=200)
    observations_review_candidates_parser.add_argument("--top", type=int, default=10)
    observations_review_candidates_parser.add_argument("--frequent-threshold", type=int, default=3)

    activations_parser = subparsers.add_parser(
        "activations",
        help="Read-only activation reports over retrieval-use evidence.",
    )
    activations_subparsers = activations_parser.add_subparsers(dest="activations_action", required=True)
    activations_summary_parser = activations_subparsers.add_parser(
        "summary",
        help="Summarize memory activation evidence without changing retrieval ranking or memory state.",
    )
    activations_summary_parser.add_argument("db_path", type=Path)
    activations_summary_parser.add_argument("--limit", type=int, default=200)
    activations_summary_parser.add_argument("--top", type=int, default=20)
    activations_summary_parser.add_argument("--frequent-threshold", type=int, default=3)
    activations_reinforcement_parser = activations_subparsers.add_parser(
        "reinforcement-report",
        help="Score activation refs as read-only reinforcement candidates without mutating ranking or memory state.",
    )
    activations_reinforcement_parser.add_argument("db_path", type=Path)
    activations_reinforcement_parser.add_argument("--limit", type=int, default=200)
    activations_reinforcement_parser.add_argument("--top", type=int, default=20)
    activations_reinforcement_parser.add_argument("--frequent-threshold", type=int, default=3)
    activations_decay_parser = activations_subparsers.add_parser(
        "decay-risk-report",
        help="Score activation refs as read-only decay-risk review candidates without mutating memory state.",
    )
    activations_decay_parser.add_argument("db_path", type=Path)
    activations_decay_parser.add_argument("--limit", type=int, default=200)
    activations_decay_parser.add_argument("--top", type=int, default=20)
    activations_decay_parser.add_argument("--frequent-threshold", type=int, default=3)

    consolidation_parser = subparsers.add_parser(
        "consolidation",
        help="Read-only consolidation candidate diagnostics over traces and activation evidence.",
    )
    consolidation_subparsers = consolidation_parser.add_subparsers(dest="consolidation_action", required=True)
    consolidation_candidates_parser = consolidation_subparsers.add_parser(
        "candidates",
        help="Group sanitized traces into read-only consolidation candidates without promoting memories.",
    )
    consolidation_candidates_parser.add_argument("db_path", type=Path)
    consolidation_candidates_parser.add_argument("--limit", type=int, default=200)
    consolidation_candidates_parser.add_argument("--top", type=int, default=20)
    consolidation_candidates_parser.add_argument("--min-evidence", type=int, default=2)
    consolidation_background_parser = consolidation_subparsers.add_parser(
        "background",
        help="Cron-friendly background consolidation diagnostics; dry-run only and never mutates memory.",
    )
    consolidation_background_subparsers = consolidation_background_parser.add_subparsers(
        dest="background_action",
        required=True,
    )
    consolidation_background_dry_run_parser = consolidation_background_subparsers.add_parser(
        "dry-run",
        help="Write a read-only background consolidation report for human review.",
    )
    consolidation_background_dry_run_parser.add_argument("db_path", type=Path)
    consolidation_background_dry_run_parser.add_argument("--limit", type=int, default=200)
    consolidation_background_dry_run_parser.add_argument("--top", type=int, default=20)
    consolidation_background_dry_run_parser.add_argument("--min-evidence", type=int, default=2)
    consolidation_background_dry_run_parser.add_argument("--frequent-threshold", type=int, default=3)
    consolidation_background_dry_run_parser.add_argument("--output", type=Path)
    consolidation_background_dry_run_parser.add_argument(
        "--lock-path",
        type=Path,
        default=Path.home() / ".agent-memory" / "background-consolidation.lock",
    )
    consolidation_explain_parser = consolidation_subparsers.add_parser(
        "explain",
        help="Explain one read-only consolidation candidate without promoting or mutating memory.",
    )
    consolidation_explain_parser.add_argument("db_path", type=Path)
    consolidation_explain_parser.add_argument("candidate_id")
    consolidation_explain_parser.add_argument("--limit", type=int, default=200)
    consolidation_explain_parser.add_argument("--min-evidence", type=int, default=2)
    consolidation_promotions_parser = consolidation_subparsers.add_parser(
        "promotions",
        help="Inspect manual consolidation promotions as a read-only audit report.",
    )
    consolidation_promotions_subparsers = consolidation_promotions_parser.add_subparsers(
        dest="promotions_action",
        required=True,
    )
    consolidation_promotions_report_parser = consolidation_promotions_subparsers.add_parser(
        "report",
        help="List manual reviewed consolidation promotions without changing memory state.",
    )
    consolidation_promotions_report_parser.add_argument("db_path", type=Path)
    consolidation_promotions_report_parser.add_argument("--limit", type=int, default=50)
    consolidation_promote_parser = consolidation_subparsers.add_parser(
        "promote",
        help="Promote a reviewed consolidation candidate into candidate or approved memory.",
    )
    consolidation_promote_subparsers = consolidation_promote_parser.add_subparsers(
        dest="promotion_memory_type",
        required=True,
    )
    consolidation_promote_fact_parser = consolidation_promote_subparsers.add_parser(
        "fact",
        help="Promote a reviewed consolidation candidate into a semantic fact.",
    )
    consolidation_promote_fact_parser.add_argument("db_path", type=Path)
    consolidation_promote_fact_parser.add_argument("candidate_id")
    consolidation_promote_fact_parser.add_argument("--subject-ref", required=True)
    consolidation_promote_fact_parser.add_argument("--predicate", required=True)
    consolidation_promote_fact_parser.add_argument("--object-ref-or-value", required=True)
    consolidation_promote_fact_parser.add_argument("--scope", required=True)
    consolidation_promote_fact_parser.add_argument("--confidence", type=float, default=0.75)
    consolidation_promote_fact_parser.add_argument("--approve", action="store_true")
    consolidation_promote_fact_parser.add_argument(
        "--allow-conflict",
        action="store_true",
        help="Explicitly allow promotion when same subject/predicate/scope facts conflict.",
    )
    consolidation_promote_fact_parser.add_argument("--actor")
    consolidation_promote_fact_parser.add_argument("--reason")
    consolidation_promote_fact_parser.add_argument("--limit", type=int, default=200)
    consolidation_promote_fact_parser.add_argument("--min-evidence", type=int, default=2)
    consolidation_auto_parser = consolidation_subparsers.add_parser(
        "auto-approve",
        help="Default-off guarded auto-approval policies for narrow remember-intent memories.",
    )
    consolidation_auto_subparsers = consolidation_auto_parser.add_subparsers(
        dest="auto_approval_policy_kind",
        required=True,
    )
    consolidation_auto_remember_parser = consolidation_auto_subparsers.add_parser(
        "remember-preferences",
        help="Dry-run or apply the G2 remember-preferences-v1 policy for explicit remember_intent traces.",
    )
    consolidation_auto_remember_parser.add_argument("db_path", type=Path)
    consolidation_auto_remember_parser.add_argument("--policy", required=True, choices=sorted(_REMEMBER_PREFERENCE_POLICIES))
    consolidation_auto_remember_parser.add_argument("--scope", required=True)
    consolidation_auto_remember_parser.add_argument("--apply", action="store_true")
    consolidation_auto_remember_parser.add_argument("--actor")
    consolidation_auto_remember_parser.add_argument("--reason")
    consolidation_auto_remember_parser.add_argument("--limit", type=int, default=200)

    traces_parser = subparsers.add_parser(
        "traces",
        help="Record and list sanitized local experience traces. Experimental; does not create long-term memories.",
    )
    traces_subparsers = traces_parser.add_subparsers(dest="traces_action", required=True)
    traces_record_parser = traces_subparsers.add_parser(
        "record",
        help="Record one explicitly sanitized experience trace.",
    )
    traces_record_parser.add_argument("db_path", type=Path)
    traces_record_parser.add_argument("--surface", required=True)
    traces_record_parser.add_argument("--event-kind", required=True)
    traces_record_parser.add_argument("--summary")
    traces_record_parser.add_argument("--content-sha256")
    traces_record_parser.add_argument("--scope")
    traces_record_parser.add_argument("--session-ref")
    traces_record_parser.add_argument("--salience", type=float, default=0.0)
    traces_record_parser.add_argument("--user-emphasis", type=float, default=0.0)
    traces_record_parser.add_argument("--related-memory-refs-json", default="[]")
    traces_record_parser.add_argument("--related-observation-ids-json", default="[]")
    traces_record_parser.add_argument(
        "--retention-policy",
        choices=["ephemeral", "short", "review", "archive"],
        default="ephemeral",
    )
    traces_record_parser.add_argument("--expires-at")
    traces_record_parser.add_argument("--metadata-json", default="{}")
    traces_list_parser = traces_subparsers.add_parser(
        "list",
        help="List sanitized experience traces without changing memory state.",
    )
    traces_list_parser.add_argument("db_path", type=Path)
    traces_list_parser.add_argument("--limit", type=int, default=50)
    traces_list_parser.add_argument("--surface")
    traces_list_parser.add_argument("--event-kind")
    traces_list_parser.add_argument("--scope")
    traces_retention_parser = traces_subparsers.add_parser(
        "retention-report",
        help="Build a read-only trace retention guardrail report without deleting or promoting traces.",
    )
    traces_retention_parser.add_argument("db_path", type=Path)
    traces_retention_parser.add_argument("--now")
    traces_retention_parser.add_argument("--max-trace-count", type=int, default=10000)
    traces_retention_parser.add_argument("--expired-limit", type=int, default=50)
    traces_retention_parser.add_argument("--missing-expiry-limit", type=int, default=50)

    dogfood_parser = subparsers.add_parser("dogfood")
    dogfood_subparsers = dogfood_parser.add_subparsers(dest="dogfood_action", required=True)
    dogfood_baseline_parser = dogfood_subparsers.add_parser(
        "baseline",
        help="Build a read-only local dogfood baseline report for observations, memory counts, and Hermes hook setup.",
    )
    dogfood_baseline_parser.add_argument("db_path", type=Path)
    dogfood_baseline_parser.add_argument("--output-json", action="store_true", help="Emit machine-readable JSON.")
    dogfood_baseline_parser.add_argument("--limit", type=int, default=200)
    dogfood_baseline_parser.add_argument("--top", type=int, default=10)
    dogfood_baseline_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_baseline_parser.add_argument("--high-empty-threshold", type=float, default=0.5)
    dogfood_baseline_parser.add_argument("--config-path", type=Path, default=Path.home() / ".hermes" / "config.yaml")
    dogfood_baseline_parser.add_argument("--python-executable")
    dogfood_baseline_parser.add_argument("--hook-limit", type=int, default=5)
    dogfood_baseline_parser.add_argument("--preferred-scope")
    dogfood_baseline_parser.add_argument("--top-k", type=int)
    dogfood_baseline_parser.add_argument("--max-prompt-lines", type=int)
    dogfood_baseline_parser.add_argument("--max-prompt-chars", type=int)
    dogfood_baseline_parser.add_argument("--max-prompt-tokens", type=int)
    dogfood_baseline_parser.add_argument("--max-verification-steps", type=int)
    dogfood_baseline_parser.add_argument("--max-alternatives", type=int)
    dogfood_baseline_parser.add_argument("--max-guidelines", type=int)
    dogfood_baseline_parser.add_argument("--no-reason-codes", action="store_true")
    dogfood_baseline_parser.add_argument("--timeout", type=int)
    dogfood_remember_parser = dogfood_subparsers.add_parser(
        "remember-intent",
        help="Build a read-only dogfood report for explicit remember-intent traces before G2 automation.",
    )
    dogfood_remember_parser.add_argument("db_path", type=Path)
    dogfood_remember_parser.add_argument("--limit", type=int, default=200)
    dogfood_remember_parser.add_argument("--sample-limit", type=int, default=10)

    graph_parser = subparsers.add_parser("graph")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_action", required=True)
    graph_inspect_parser = graph_subparsers.add_parser("inspect")
    graph_inspect_parser.add_argument("db_path", type=Path)
    graph_inspect_parser.add_argument("start_ref")
    graph_inspect_parser.add_argument("--depth", type=int, default=1)
    graph_inspect_parser.add_argument("--limit", type=int, default=100)

    eval_parser = subparsers.add_parser("eval")
    eval_subparsers = eval_parser.add_subparsers(dest="eval_action", required=True)
    eval_retrieval_parser = eval_subparsers.add_parser("retrieval")
    eval_retrieval_parser.add_argument("db_path", type=Path)
    eval_retrieval_parser.add_argument("fixtures_path", type=Path)
    eval_retrieval_parser.add_argument("--baseline-mode", choices=["lexical", "lexical-global", "source-lexical", "source-global"])
    eval_retrieval_parser.add_argument("--format", choices=["json", "text"], default="json")
    eval_retrieval_parser.add_argument("--fail-on-regression", action="store_true")
    eval_retrieval_parser.add_argument("--warn-on-regression-threshold", type=int)
    eval_retrieval_parser.add_argument("--fail-on-baseline-regression", action="store_true")
    eval_retrieval_parser.add_argument("--warn-on-baseline-regression-threshold", type=int)
    eval_retrieval_parser.add_argument(
        "--fail-on-baseline-regression-memory-type",
        action="append",
        choices=["facts", "procedures", "episodes"],
        dest="fail_on_baseline_regression_memory_types",
    )

    hermes_context_parser = subparsers.add_parser("hermes-context")
    hermes_context_parser.add_argument("db_path", type=Path)
    hermes_context_parser.add_argument("query")
    hermes_context_parser.add_argument("--limit", type=int, default=5)
    hermes_context_parser.add_argument("--preferred-scope")
    hermes_context_parser.add_argument("--top-k", type=int, default=1)
    hermes_context_parser.add_argument("--max-prompt-lines", type=int)
    hermes_context_parser.add_argument("--max-prompt-chars", type=int)
    hermes_context_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_context_parser.add_argument("--max-verification-steps", type=int)
    hermes_context_parser.add_argument("--max-alternatives", type=int)
    hermes_context_parser.add_argument("--max-guidelines", type=int)
    hermes_context_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_context_parser.add_argument("--verification-results-json")

    codex_prompt_parser = subparsers.add_parser("codex-prompt")
    codex_prompt_parser.add_argument("db_path", type=Path)
    codex_prompt_parser.add_argument("query")
    codex_prompt_parser.add_argument("--limit", type=int, default=5)
    codex_prompt_parser.add_argument("--preferred-scope")
    codex_prompt_parser.add_argument("--top-k", type=int, default=1)
    codex_prompt_parser.add_argument("--max-prompt-lines", type=int)
    codex_prompt_parser.add_argument("--max-prompt-chars", type=int)
    codex_prompt_parser.add_argument("--max-prompt-tokens", type=int)
    codex_prompt_parser.add_argument("--max-verification-steps", type=int)
    codex_prompt_parser.add_argument("--max-alternatives", type=int)
    codex_prompt_parser.add_argument("--max-guidelines", type=int)
    codex_prompt_parser.add_argument("--no-reason-codes", action="store_true")

    claude_prompt_parser = subparsers.add_parser("claude-prompt")
    claude_prompt_parser.add_argument("db_path", type=Path)
    claude_prompt_parser.add_argument("query")
    claude_prompt_parser.add_argument("--limit", type=int, default=5)
    claude_prompt_parser.add_argument("--preferred-scope")
    claude_prompt_parser.add_argument("--top-k", type=int, default=1)
    claude_prompt_parser.add_argument("--max-prompt-lines", type=int)
    claude_prompt_parser.add_argument("--max-prompt-chars", type=int)
    claude_prompt_parser.add_argument("--max-prompt-tokens", type=int)
    claude_prompt_parser.add_argument("--max-verification-steps", type=int)
    claude_prompt_parser.add_argument("--max-alternatives", type=int)
    claude_prompt_parser.add_argument("--max-guidelines", type=int)
    claude_prompt_parser.add_argument("--no-reason-codes", action="store_true")

    hermes_pre_llm_hook_parser = subparsers.add_parser("hermes-pre-llm-hook")
    hermes_pre_llm_hook_parser.add_argument("db_path", type=Path)
    _add_hermes_hook_preset_argument(hermes_pre_llm_hook_parser)
    hermes_pre_llm_hook_parser.add_argument("--limit", type=int, default=5)
    hermes_pre_llm_hook_parser.add_argument("--preferred-scope")
    hermes_pre_llm_hook_parser.add_argument("--top-k", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-prompt-lines", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-prompt-chars", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-verification-steps", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-alternatives", type=int)
    hermes_pre_llm_hook_parser.add_argument("--max-guidelines", type=int)
    hermes_pre_llm_hook_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_pre_llm_hook_parser.add_argument(
        "--record-trace",
        action="store_true",
        help="Opt in to sanitized experience trace recording for real Hermes turns. Raw prompts are never stored.",
    )

    hermes_hook_config_snippet_parser = subparsers.add_parser("hermes-hook-config-snippet")
    hermes_hook_config_snippet_parser.add_argument("db_path", type=Path)
    _add_hermes_hook_preset_argument(hermes_hook_config_snippet_parser)
    hermes_hook_config_snippet_parser.add_argument("--python-executable")
    hermes_hook_config_snippet_parser.add_argument("--limit", type=int, default=5)
    hermes_hook_config_snippet_parser.add_argument("--preferred-scope")
    hermes_hook_config_snippet_parser.add_argument("--top-k", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-prompt-lines", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-prompt-chars", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-verification-steps", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-alternatives", type=int)
    hermes_hook_config_snippet_parser.add_argument("--max-guidelines", type=int)
    hermes_hook_config_snippet_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_hook_config_snippet_parser.add_argument(
        "--record-trace",
        action="store_true",
        help="Include --record-trace in the rendered hook command for opt-in sanitized trace recording.",
    )
    hermes_hook_config_snippet_parser.add_argument("--timeout", type=int)

    hermes_install_hook_parser = subparsers.add_parser("hermes-install-hook")
    hermes_install_hook_parser.add_argument("db_path", type=Path)
    _add_hermes_hook_preset_argument(hermes_install_hook_parser)
    hermes_install_hook_parser.add_argument("--config-path", type=Path, default=Path.home() / ".hermes" / "config.yaml")
    hermes_install_hook_parser.add_argument("--python-executable")
    hermes_install_hook_parser.add_argument("--limit", type=int, default=5)
    hermes_install_hook_parser.add_argument("--preferred-scope")
    hermes_install_hook_parser.add_argument("--top-k", type=int)
    hermes_install_hook_parser.add_argument("--max-prompt-lines", type=int)
    hermes_install_hook_parser.add_argument("--max-prompt-chars", type=int)
    hermes_install_hook_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_install_hook_parser.add_argument("--max-verification-steps", type=int)
    hermes_install_hook_parser.add_argument("--max-alternatives", type=int)
    hermes_install_hook_parser.add_argument("--max-guidelines", type=int)
    hermes_install_hook_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_install_hook_parser.add_argument(
        "--record-trace",
        action="store_true",
        help="Install the hook with opt-in sanitized experience trace recording enabled.",
    )
    hermes_install_hook_parser.add_argument("--timeout", type=int)

    hermes_bootstrap_parser = subparsers.add_parser(
        "hermes-bootstrap",
        help="One-line Hermes bootstrap: initialize DB if needed and install the pre_llm_call hook.",
    )
    hermes_bootstrap_parser.add_argument(
        "db_path",
        type=Path,
        nargs="?",
        default=Path.home() / ".agent-memory" / "memory.db",
    )
    _add_hermes_hook_preset_argument(hermes_bootstrap_parser)
    hermes_bootstrap_parser.add_argument("--config-path", type=Path, default=Path.home() / ".hermes" / "config.yaml")
    hermes_bootstrap_parser.add_argument("--python-executable")
    hermes_bootstrap_parser.add_argument("--limit", type=int, default=5)
    hermes_bootstrap_parser.add_argument("--preferred-scope")
    hermes_bootstrap_parser.add_argument("--top-k", type=int)
    hermes_bootstrap_parser.add_argument("--max-prompt-lines", type=int)
    hermes_bootstrap_parser.add_argument("--max-prompt-chars", type=int)
    hermes_bootstrap_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_bootstrap_parser.add_argument("--max-verification-steps", type=int)
    hermes_bootstrap_parser.add_argument("--max-alternatives", type=int)
    hermes_bootstrap_parser.add_argument("--max-guidelines", type=int)
    hermes_bootstrap_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_bootstrap_parser.add_argument(
        "--record-trace",
        action="store_true",
        help="Install the hook with opt-in sanitized experience trace recording enabled.",
    )
    hermes_bootstrap_parser.add_argument("--timeout", type=int)

    hermes_doctor_parser = subparsers.add_parser(
        "hermes-doctor",
        help="Check whether the recommended Hermes hook setup is present and print the one-line fix.",
    )
    hermes_doctor_parser.add_argument(
        "db_path",
        type=Path,
        nargs="?",
        default=Path.home() / ".agent-memory" / "memory.db",
    )
    _add_hermes_hook_preset_argument(hermes_doctor_parser)
    hermes_doctor_parser.add_argument("--config-path", type=Path, default=Path.home() / ".hermes" / "config.yaml")
    hermes_doctor_parser.add_argument("--python-executable")
    hermes_doctor_parser.add_argument("--limit", type=int, default=5)
    hermes_doctor_parser.add_argument("--preferred-scope")
    hermes_doctor_parser.add_argument("--top-k", type=int)
    hermes_doctor_parser.add_argument("--max-prompt-lines", type=int)
    hermes_doctor_parser.add_argument("--max-prompt-chars", type=int)
    hermes_doctor_parser.add_argument("--max-prompt-tokens", type=int)
    hermes_doctor_parser.add_argument("--max-verification-steps", type=int)
    hermes_doctor_parser.add_argument("--max-alternatives", type=int)
    hermes_doctor_parser.add_argument("--max-guidelines", type=int)
    hermes_doctor_parser.add_argument("--no-reason-codes", action="store_true")
    hermes_doctor_parser.add_argument("--timeout", type=int)

    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args(_normalize_command_aliases(sys.argv[1:]))
    _apply_hermes_hook_preset(args)

    if args.command == "init":
        initialize_database(args.db_path)
        print(f"initialized {args.db_path}")
        return

    if args.command == "ingest-source":
        source = ingest_source_text(
            db_path=args.db_path,
            source_type=args.source_type,
            content=args.content,
            metadata=json.loads(args.metadata_json),
            adapter=args.adapter,
            external_ref=args.external_ref,
        )
        print(source.model_dump_json(indent=2))
        return

    if args.command == "create-fact":
        fact = create_candidate_fact(
            db_path=args.db_path,
            subject_ref=args.subject_ref,
            predicate=args.predicate,
            object_ref_or_value=args.object_ref_or_value,
            evidence_ids=json.loads(args.evidence_ids_json),
            scope=args.scope,
            confidence=args.confidence,
        )
        print(fact.model_dump_json(indent=2))
        return

    if args.command == "approve-fact":
        fact = approve_fact(db_path=args.db_path, fact_id=args.fact_id)
        print(fact.model_dump_json(indent=2))
        return

    if args.command == "list-candidate-facts":
        print(_dump_models(list_candidate_facts(args.db_path, limit=args.limit)))
        return

    if args.command == "create-procedure":
        procedure = create_candidate_procedure(
            db_path=args.db_path,
            name=args.name,
            trigger_context=args.trigger_context,
            scope=args.scope,
            preconditions=json.loads(args.preconditions_json),
            steps=json.loads(args.steps_json),
            evidence_ids=json.loads(args.evidence_ids_json),
            success_rate=args.success_rate,
        )
        print(procedure.model_dump_json(indent=2))
        return

    if args.command == "approve-procedure":
        procedure = approve_procedure(db_path=args.db_path, procedure_id=args.procedure_id)
        print(procedure.model_dump_json(indent=2))
        return

    if args.command == "list-candidate-procedures":
        print(_dump_models(list_candidate_procedures(args.db_path, limit=args.limit)))
        return

    if args.command == "create-episode":
        episode = create_episode(
            db_path=args.db_path,
            title=args.title,
            summary=args.summary,
            source_ids=json.loads(args.source_ids_json),
            tags=json.loads(args.tags_json),
            importance_score=args.importance_score,
            scope=args.scope,
            status=args.status,
            started_at=args.started_at,
            ended_at=args.ended_at,
        )
        print(episode.model_dump_json(indent=2))
        return

    if args.command == "list-candidate-episodes":
        print(_dump_models(list_candidate_episodes(args.db_path, limit=args.limit)))
        return

    if args.command == "kb":
        if args.kb_action == "export":
            result = export_kb_markdown(db_path=args.db_path, output_dir=args.output_dir, scope=args.scope)
            print(result.model_dump_json(indent=2))
            return
        raise ValueError(f"Unsupported kb action: {args.kb_action}")

    if args.command == "review":
        if args.review_action in {"approve", "dispute", "deprecate"}:
            review_kwargs = {
                "db_path": args.db_path,
                "memory_type": args.memory_type,
                "memory_id": args.memory_id,
                "reason": args.reason,
                "actor": args.actor,
                "evidence_ids": json.loads(args.evidence_ids_json),
            }
            if args.review_action == "approve":
                memory = approve_memory(**review_kwargs)
            elif args.review_action == "dispute":
                memory = dispute_memory(**review_kwargs)
            else:
                memory = deprecate_memory(**review_kwargs)
        elif args.review_action == "supersede":
            relation = supersede_fact(
                db_path=args.db_path,
                superseded_fact_id=args.superseded_memory_id,
                replacement_fact_id=args.replacement_memory_id,
                reason=args.reason,
                actor=args.actor,
                evidence_ids=json.loads(args.evidence_ids_json),
            )
            print(relation.model_dump_json(indent=2))
            return
        elif args.review_action == "replacements":
            relations = list_fact_replacement_relations(args.db_path, fact_id=args.memory_id)
            print(
                json.dumps(
                    {
                        "memory_type": args.memory_type,
                        "memory_id": args.memory_id,
                        "replacements": [_fact_replacement_relation_payload(relation) for relation in relations],
                    },
                    indent=2,
                )
            )
            return
        elif args.review_action == "relate-conflict":
            relation = create_fact_conflict_relation(
                db_path=args.db_path,
                left_fact_id=args.left_memory_id,
                right_fact_id=args.right_memory_id,
                reason=args.reason,
                actor=args.actor,
                evidence_ids=json.loads(args.evidence_ids_json),
            )
            left_fact = get_fact(args.db_path, fact_id=args.left_memory_id)
            print(
                json.dumps(
                    {
                        "kind": "memory_review_conflict_relation",
                        "memory_type": args.memory_type,
                        "read_only": False,
                        "status_mutation": False,
                        "claim_slot": {
                            "subject_ref": left_fact.subject_ref,
                            "predicate": left_fact.predicate,
                            "scope": left_fact.scope,
                        },
                        "relation": relation.model_dump(mode="json"),
                    },
                    indent=2,
                )
            )
            return
        elif args.review_action == "history":
            history = list_memory_status_history(
                args.db_path,
                memory_type=args.memory_type,
                memory_id=args.memory_id,
            )
            print(
                json.dumps(
                    {
                        "memory_type": args.memory_type,
                        "memory_id": args.memory_id,
                        "history": [entry.model_dump(mode="json") for entry in history],
                    },
                    indent=2,
                )
            )
            return
        elif args.review_action == "explain":
            print(json.dumps(_fact_review_explanation_payload(args.db_path, fact_id=args.memory_id), indent=2))
            return
        elif args.review_action == "conflicts":
            facts = list_facts_by_claim_slot(
                args.db_path,
                subject_ref=args.subject_ref,
                predicate=args.predicate,
                scope=args.scope,
            )
            counts = _status_counts_for_facts(facts)
            conflict_relation_payloads = []
            seen_relation_ids = set()
            for fact in facts:
                for relation in list_fact_conflict_relations(args.db_path, fact_id=fact.id):
                    if relation.id in seen_relation_ids:
                        continue
                    seen_relation_ids.add(relation.id)
                    conflict_relation_payloads.append(_fact_conflict_relation_payload(relation))
            print(
                json.dumps(
                    {
                        "claim_slot": {
                            "subject_ref": args.subject_ref,
                            "predicate": args.predicate,
                            "scope": args.scope,
                        },
                        "counts": counts,
                        "default_retrieval_policy": "approved_only",
                        "conflict_relations": conflict_relation_payloads,
                        "facts": [fact.model_dump(mode="json") for fact in facts],
                    },
                    indent=2,
                )
            )
            return
        else:
            raise ValueError(f"Unsupported review action: {args.review_action}")
        print(memory.model_dump_json(indent=2))
        return

    if args.command == "retrieve":
        statuses = (
            ("candidate", "approved", "disputed", "deprecated")
            if args.status == "all"
            else (args.status,)
        )
        packet = retrieve_memory_packet(
            db_path=args.db_path,
            query=args.query,
            limit=args.limit,
            preferred_scope=args.preferred_scope,
            statuses=statuses,
            observation_surface=args.observe,
        )
        print(packet.model_dump_json(indent=2))
        return

    if args.command == "retrieval":
        if args.retrieval_action == "policy-preview":
            print(
                json.dumps(
                    _retrieval_policy_preview(
                        args.db_path,
                        query=args.query,
                        limit=args.limit,
                        preferred_scope=args.preferred_scope,
                    ),
                    indent=2,
                )
            )
            return
        if args.retrieval_action == "ranker-preview":
            print(
                json.dumps(
                    _retrieval_ranker_preview(
                        args.db_path,
                        query=args.query,
                        limit=args.limit,
                        preferred_scope=args.preferred_scope,
                        reinforcement_weight=args.reinforcement_weight,
                        reinforcement_cap=args.reinforcement_cap,
                    ),
                    indent=2,
                )
            )
            return
        if args.retrieval_action == "decay-preview":
            print(
                json.dumps(
                    _retrieval_decay_preview(
                        args.db_path,
                        query=args.query,
                        limit=args.limit,
                        preferred_scope=args.preferred_scope,
                        decay_weight=args.decay_weight,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        if args.retrieval_action == "graph-neighborhood-preview":
            print(
                json.dumps(
                    _retrieval_graph_neighborhood_preview(
                        args.db_path,
                        query=args.query,
                        limit=args.limit,
                        preferred_scope=args.preferred_scope,
                        depth=args.depth,
                        graph_weight=args.graph_weight,
                        graph_cap=args.graph_cap,
                        neighbor_reinforcement_weight=args.neighbor_reinforcement_weight,
                    ),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported retrieval action: {args.retrieval_action}")

    if args.command == "observations":
        if args.observations_action == "list":
            observations = list_retrieval_observations(args.db_path, limit=args.limit)
            print(
                json.dumps(
                    {
                        "kind": "retrieval_observations",
                        "read_only": True,
                        "observations": [observation.model_dump(mode="json") for observation in observations],
                    },
                    indent=2,
                )
            )
            return
        if args.observations_action == "audit":
            print(
                json.dumps(
                    _audit_retrieval_observations(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        if args.observations_action == "empty-diagnostics":
            print(
                json.dumps(
                    _empty_retrieval_diagnostics(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        high_empty_threshold=args.high_empty_threshold,
                    ),
                    indent=2,
                )
            )
            return
        if args.observations_action == "review-candidates":
            print(
                json.dumps(
                    _review_candidates_from_observations(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported observations action: {args.observations_action}")

    if args.command == "activations":
        if args.activations_action == "summary":
            print(
                json.dumps(
                    _activation_summary(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        if args.activations_action == "reinforcement-report":
            print(
                json.dumps(
                    _activation_reinforcement_report(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        if args.activations_action == "decay-risk-report":
            print(
                json.dumps(
                    _activation_decay_risk_report(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        frequent_threshold=args.frequent_threshold,
                    ),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported activations action: {args.activations_action}")

    if args.command == "consolidation":
        if args.consolidation_action == "candidates":
            print(
                json.dumps(
                    _consolidation_candidates_report(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        min_evidence=args.min_evidence,
                    ),
                    indent=2,
                )
            )
            return
        if args.consolidation_action == "background":
            if args.background_action != "dry-run":
                raise ValueError(f"Unsupported consolidation background action: {args.background_action}")
            print(
                json.dumps(
                    _consolidation_background_dry_run_report(
                        args.db_path,
                        limit=args.limit,
                        top=args.top,
                        min_evidence=args.min_evidence,
                        frequent_threshold=args.frequent_threshold,
                        output_path=args.output,
                        lock_path=args.lock_path,
                    ),
                    indent=2,
                )
            )
            return
        if args.consolidation_action == "explain":
            payload = _consolidation_candidate_explanation(
                args.db_path,
                candidate_id=args.candidate_id,
                limit=args.limit,
                min_evidence=args.min_evidence,
            )
            print(json.dumps(payload, indent=2))
            if not payload.get("found", False):
                sys.exit(1)
            return
        if args.consolidation_action == "promotions":
            if args.promotions_action != "report":
                raise ValueError(f"Unsupported consolidation promotions action: {args.promotions_action}")
            print(json.dumps(_consolidation_promotions_report(args.db_path, limit=args.limit), indent=2))
            return
        if args.consolidation_action == "promote":
            if args.promotion_memory_type != "fact":
                raise ValueError(f"Unsupported consolidation promotion type: {args.promotion_memory_type}")
            payload = _promote_consolidation_candidate_fact(
                args.db_path,
                candidate_id=args.candidate_id,
                subject_ref=args.subject_ref,
                predicate=args.predicate,
                object_ref_or_value=args.object_ref_or_value,
                scope=args.scope,
                confidence=args.confidence,
                approve=args.approve,
                actor=args.actor,
                reason=args.reason,
                allow_conflict=args.allow_conflict,
                limit=args.limit,
                min_evidence=args.min_evidence,
            )
            print(json.dumps(payload, indent=2))
            if not payload.get("promoted", False):
                sys.exit(1)
            return
        if args.consolidation_action == "auto-approve":
            if args.auto_approval_policy_kind != "remember-preferences":
                raise ValueError(f"Unsupported consolidation auto-approval policy kind: {args.auto_approval_policy_kind}")
            payload = _remember_preference_auto_approval_report(
                args.db_path,
                policy=args.policy,
                scope=args.scope,
                apply=args.apply,
                actor=args.actor,
                reason=args.reason,
                limit=args.limit,
            )
            print(json.dumps(payload, indent=2))
            if args.apply and payload["blocked_count"] > 0 and payload["approved_count"] == 0:
                sys.exit(1)
            return
        raise ValueError(f"Unsupported consolidation action: {args.consolidation_action}")

    if args.command == "traces":
        if args.traces_action == "record":
            related_memory_refs = _json_list(args.related_memory_refs_json, argument_name="--related-memory-refs-json")
            related_observation_ids = _json_list(
                args.related_observation_ids_json,
                argument_name="--related-observation-ids-json",
            )
            metadata = json.loads(args.metadata_json)
            if not isinstance(metadata, dict):
                raise ValueError("--metadata-json must be a JSON object")
            trace = insert_experience_trace(
                args.db_path,
                surface=args.surface,
                event_kind=args.event_kind,
                content_sha256=_trace_content_sha256(explicit_hash=args.content_sha256, summary=args.summary),
                summary=args.summary,
                scope=args.scope,
                session_ref=args.session_ref,
                salience=args.salience,
                user_emphasis=args.user_emphasis,
                related_memory_refs=[str(item) for item in related_memory_refs],
                related_observation_ids=[int(item) for item in related_observation_ids],
                retention_policy=args.retention_policy,
                expires_at=args.expires_at,
                metadata=metadata,
            )
            print(
                json.dumps(
                    {
                        "kind": "experience_trace",
                        "trace": trace.model_dump(mode="json"),
                    },
                    indent=2,
                )
            )
            return
        if args.traces_action == "list":
            if args.limit < 1:
                raise ValueError("traces list limit must be >= 1")
            traces = list_experience_traces(
                args.db_path,
                limit=args.limit,
                surface=args.surface,
                event_kind=args.event_kind,
                scope=args.scope,
            )
            print(
                json.dumps(
                    {
                        "kind": "experience_traces",
                        "read_only": True,
                        "trace_count": len(traces),
                        "limit": args.limit,
                        "filters": _trace_filters_payload(
                            surface=args.surface,
                            event_kind=args.event_kind,
                            scope=args.scope,
                        ),
                        "traces": [trace.model_dump(mode="json") for trace in traces],
                    },
                    indent=2,
                )
            )
            return
        if args.traces_action == "retention-report":
            if args.max_trace_count < 0:
                raise ValueError("traces retention-report max trace count must be >= 0")
            if args.expired_limit < 1:
                raise ValueError("traces retention-report expired limit must be >= 1")
            if args.missing_expiry_limit < 1:
                raise ValueError("traces retention-report missing expiry limit must be >= 1")
            print(
                json.dumps(
                    build_trace_retention_report(
                        args.db_path,
                        now=args.now,
                        max_trace_count=args.max_trace_count,
                        expired_limit=args.expired_limit,
                        missing_expiry_limit=args.missing_expiry_limit,
                    ),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported traces action: {args.traces_action}")

    if args.command == "dogfood":
        if args.dogfood_action == "baseline":
            print(json.dumps(_dogfood_baseline_payload(args), indent=2))
            return
        if args.dogfood_action == "remember-intent":
            if args.limit < 1:
                raise ValueError("dogfood remember-intent limit must be >= 1")
            if args.sample_limit < 0:
                raise ValueError("dogfood remember-intent sample limit must be >= 0")
            print(
                json.dumps(
                    _remember_intent_dogfood_report(
                        args.db_path,
                        limit=args.limit,
                        sample_limit=args.sample_limit,
                    ),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported dogfood action: {args.dogfood_action}")

    if args.command == "graph":
        if args.graph_action == "inspect":
            print(
                json.dumps(
                    _inspect_relation_graph(args.db_path, start_ref=args.start_ref, depth=args.depth, limit=args.limit),
                    indent=2,
                )
            )
            return
        raise ValueError(f"Unsupported graph action: {args.graph_action}")

    if args.command == "eval":
        if args.eval_action == "retrieval":
            try:
                result = evaluate_retrieval_fixtures(
                    db_path=args.db_path,
                    fixtures_path=args.fixtures_path,
                    baseline_mode=args.baseline_mode,
                    fail_on_regression=args.fail_on_regression,
                    warn_on_regression_threshold=args.warn_on_regression_threshold,
                    fail_on_baseline_regression=args.fail_on_baseline_regression,
                    warn_on_baseline_regression_threshold=args.warn_on_baseline_regression_threshold,
                    fail_on_baseline_regression_memory_types=args.fail_on_baseline_regression_memory_types,
                )
            except RetrievalEvalRegressionError as exc:
                print(f"retrieval eval failed: {exc}", file=sys.stderr)
                if exc.result_set is not None:
                    print(render_retrieval_eval_text_report(exc.result_set), file=sys.stderr)
                raise SystemExit(1) from exc
            if args.format == "text":
                print(render_retrieval_eval_text_report(result))
            else:
                print(result.model_dump_json(indent=2, by_alias=True))
            return
        raise ValueError(f"Unsupported eval action: {args.eval_action}")

    if args.command == "hermes-context":
        context = _render_memory_context_for_prompt(args)
        outcome = None
        if args.verification_results_json is not None:
            verification_results = [
                HermesVerificationResult.model_validate(result)
                for result in json.loads(args.verification_results_json)
            ]
            outcome = apply_hermes_verification_results(context, verification_results)
        print(
            json.dumps(
                {
                    "context": context.model_dump(mode="json"),
                    "outcome": outcome.model_dump(mode="json") if outcome is not None else None,
                },
                indent=2,
            )
        )
        return

    if args.command in {"codex-prompt", "claude-prompt"}:
        print(_render_external_agent_prompt_text(args))
        return

    if args.command == "hermes-pre-llm-hook":
        payload = load_hermes_shell_hook_payload()
        hook_response = build_pre_llm_hook_context(
            payload,
            HermesPreLlmHookOptions(
                db_path=args.db_path,
                limit=args.limit,
                preferred_scope=args.preferred_scope,
                top_k=args.top_k,
                max_prompt_lines=args.max_prompt_lines,
                max_prompt_chars=args.max_prompt_chars,
                max_prompt_tokens=args.max_prompt_tokens,
                max_verification_steps=args.max_verification_steps,
                max_alternatives=args.max_alternatives,
                max_guidelines=args.max_guidelines,
                include_reason_codes=not args.no_reason_codes,
                record_trace=args.record_trace,
            ),
        )
        print(json.dumps(hook_response, indent=2))
        return

    if args.command == "hermes-hook-config-snippet":
        snippet = build_hermes_hook_config_snippet(
            HermesHookConfigSnippetOptions(
                db_path=args.db_path,
                python_executable=args.python_executable,
                render_default_arguments=True,
                limit=args.limit,
                preferred_scope=args.preferred_scope,
                top_k=args.top_k,
                max_prompt_lines=args.max_prompt_lines,
                max_prompt_chars=args.max_prompt_chars,
                max_prompt_tokens=args.max_prompt_tokens,
                max_verification_steps=args.max_verification_steps,
                max_alternatives=args.max_alternatives,
                max_guidelines=args.max_guidelines,
                include_reason_codes=not args.no_reason_codes,
                record_trace=args.record_trace,
                timeout=args.timeout,
            )
        )
        print(snippet, end="")
        return

    if args.command in {"hermes-install-hook", "hermes-bootstrap"}:
        result = install_hermes_hook_config(
            HermesHookInstallOptions(
                config_path=args.config_path,
                snippet_options=HermesHookConfigSnippetOptions(
                    db_path=args.db_path,
                    python_executable=args.python_executable,
                    render_default_arguments=True,
                    limit=args.limit,
                    preferred_scope=args.preferred_scope,
                    top_k=args.top_k,
                    max_prompt_lines=args.max_prompt_lines,
                    max_prompt_chars=args.max_prompt_chars,
                    max_prompt_tokens=args.max_prompt_tokens,
                    max_verification_steps=args.max_verification_steps,
                    max_alternatives=args.max_alternatives,
                    max_guidelines=args.max_guidelines,
                    include_reason_codes=not args.no_reason_codes,
                    record_trace=args.record_trace,
                    timeout=args.timeout,
                ),
            )
        )
        print(result.model_dump_json(indent=2))
        return

    if args.command == "hermes-doctor":
        result = diagnose_hermes_hook_setup(
            HermesHookInstallOptions(
                config_path=args.config_path,
                snippet_options=HermesHookConfigSnippetOptions(
                    db_path=args.db_path,
                    python_executable=args.python_executable,
                    render_default_arguments=True,
                    limit=args.limit,
                    preferred_scope=args.preferred_scope,
                    top_k=args.top_k,
                    max_prompt_lines=args.max_prompt_lines,
                    max_prompt_chars=args.max_prompt_chars,
                    max_prompt_tokens=args.max_prompt_tokens,
                    max_verification_steps=args.max_verification_steps,
                    max_alternatives=args.max_alternatives,
                    max_guidelines=args.max_guidelines,
                    include_reason_codes=not args.no_reason_codes,
                    timeout=args.timeout,
                ),
            )
        )
        print(result.model_dump_json(indent=2))
        return

    raise ValueError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    main()
