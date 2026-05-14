from __future__ import annotations

import argparse
import fcntl
import hashlib
import html
import json
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
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
from agent_memory.core.backup import export_backup, inspect_backup, restore_backup
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
    fact_from_row,
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
    rejection_counts = Counter(
        str(trace.metadata.get("rejected_reason"))
        for trace in remember_traces
        if trace.metadata.get("rejected_reason")
    )
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
        "rejection_counts": dict(sorted(rejection_counts.items())),
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


def _ref_safe_evidence_snapshot(db_path: Path, memory_ref: str) -> dict[str, Any]:
    parts = _memory_ref_parts(memory_ref)
    if parts is None:
        return {
            "memory_ref": memory_ref,
            "memory_type": None,
            "memory_id": None,
            "exists": False,
            "evidence_id_count": 0,
            "relation_count": 0,
            "scope_present": False,
            "content_included": False,
        }
    memory_type, memory_id = parts
    table_by_type = {"fact": "facts", "procedure": "procedures", "episode": "episodes"}
    evidence_column_by_type = {"fact": "evidence_ids_json", "procedure": "evidence_ids_json", "episode": "source_ids_json"}
    table_name = table_by_type[memory_type]
    evidence_column = evidence_column_by_type[memory_type]
    with _open_readonly_sqlite(db_path) as connection:
        row = connection.execute(
            f"SELECT {evidence_column} AS evidence_refs_json, scope FROM {table_name} WHERE id = ?",
            (memory_id,),
        ).fetchone()
    relations = list_relations_for_node(db_path, node_ref=memory_ref)
    if row is None:
        return {
            "memory_ref": memory_ref,
            "memory_type": memory_type,
            "memory_id": memory_id,
            "exists": False,
            "evidence_id_count": 0,
            "relation_count": len(relations),
            "scope_present": False,
            "content_included": False,
        }
    return {
        "memory_ref": memory_ref,
        "memory_type": memory_type,
        "memory_id": memory_id,
        "exists": True,
        "evidence_id_count": len(_safe_json_list_from_db(row["evidence_refs_json"])),
        "relation_count": len(relations),
        "scope_present": row["scope"] is not None,
        "content_included": False,
    }


def _decay_resolution_hint(*, current_status: str | None, activation_count: int, frequent_threshold: int, evidence_snapshot: dict[str, Any]) -> str:
    if current_status == "missing" or not evidence_snapshot.get("exists"):
        return "verify_missing_ref_before_any_cleanup"
    if current_status == "approved" and evidence_snapshot.get("relation_count", 0) == 0:
        return "add_relation_or_confirm_isolated_approved_memory"
    if current_status == "approved" and activation_count < frequent_threshold:
        return "collect_more_activation_evidence_before_decay_action"
    if current_status in {"deprecated", "disputed"}:
        return "review_status_history_before_visibility_change"
    return "monitor_only_no_mutation"


def _decay_review_support(db_path: Path, memory_ref: str, resolution_hint: str) -> dict[str, Any]:
    parts = _memory_ref_parts(memory_ref)
    recommended_actions_by_hint = {
        "add_relation_or_confirm_isolated_approved_memory": [
            "inspect_ref_safe_evidence",
            "add_relation_to_existing_memory_or_entity",
            "confirm_isolated_approved_memory",
        ],
        "verify_missing_ref_before_any_cleanup": [
            "inspect_ref_safe_evidence",
            "verify_missing_memory_ref",
        ],
        "collect_more_activation_evidence_before_decay_action": [
            "inspect_ref_safe_evidence",
            "collect_more_activation_evidence",
        ],
        "review_status_history_before_visibility_change": [
            "inspect_ref_safe_evidence",
            "review_status_history",
        ],
    }
    operator_commands = [f"agent-memory graph inspect {db_path} {memory_ref} --depth 1"]
    if parts is not None:
        memory_type, memory_id = parts
        operator_commands.insert(0, f"agent-memory review history {memory_type} {db_path} {memory_id}")
        if memory_type == "fact":
            operator_commands.insert(0, f"agent-memory review explain fact {db_path} {memory_id}")
    return {
        "review_required": True,
        "safe_to_auto_mutate": False,
        "raw_content_included": False,
        "recommended_actions": recommended_actions_by_hint.get(
            resolution_hint,
            ["inspect_ref_safe_evidence", "monitor_without_mutation"],
        ),
        "operator_commands": operator_commands,
    }


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


def _reinforcement_refinement_review_score(
    candidate: dict[str, Any], *, frequent_threshold: int
) -> dict[str, Any]:
    activation_count = _safe_int(candidate.get("activation_count"))
    base_score = round(_safe_float(candidate.get("score")), 4)
    current_status = str(candidate.get("current_status") or "missing")
    signals = candidate.get("signals") if isinstance(candidate.get("signals"), list) else []
    penalties = candidate.get("penalties") if isinstance(candidate.get("penalties"), dict) else {}
    repeated_activation = activation_count >= frequent_threshold
    approved = current_status == "approved"
    connected = "connected_memory" in signals
    penalty_count = len(penalties)
    score = max(
        0,
        int(
            round(base_score * 10)
            + (2 if repeated_activation else 0)
            + (1 if approved else 0)
            + (1 if connected else 0)
            - penalty_count
        ),
    )
    if approved and repeated_activation and score >= 10:
        tier = "high"
    elif approved and repeated_activation and score >= 7:
        tier = "medium"
    else:
        tier = "low"
    return {
        "score": score,
        "tier": tier,
        "components": {
            "base_reinforcement_score": base_score,
            "activation_count": activation_count,
            "frequent_threshold": frequent_threshold,
            "repeated_activation": repeated_activation,
            "current_status": current_status,
            "connected_memory": connected,
            "penalty_count": penalty_count,
        },
    }


def _reinforcement_refinement_recommendation(review_score: dict[str, Any]) -> dict[str, Any]:
    tier = str(review_score.get("tier") or "low")
    return {
        "decision": "ready_for_reinforcement_review" if tier in {"high", "medium"} else "continue_dogfooding_before_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }


def _ref_safe_reinforcement_refinement_candidate(
    candidate: dict[str, Any], *, frequent_threshold: int
) -> dict[str, Any]:
    review_score = _reinforcement_refinement_review_score(candidate, frequent_threshold=frequent_threshold)
    return {
        "memory_ref": candidate["memory_ref"],
        "current_status": candidate["current_status"],
        "activation_count": candidate["activation_count"],
        "total_strength": candidate["total_strength"],
        "signals": candidate["signals"],
        "penalties": sorted(candidate.get("penalties", {}).keys()),
        "sample_activation_ids": candidate["sample_activation_ids"],
        "sample_observation_ids": candidate["sample_observation_ids"],
        "activation_window": candidate["activation_window"],
        "review_score": review_score,
        "review_recommendation": _reinforcement_refinement_recommendation(review_score),
        "refinement": {
            "candidate_action": "consider_reinforcement_marker_after_review",
            "apply_path": "not_supported_by_preview",
            "requires_separate_guarded_policy": True,
        },
    }


def _dogfood_reinforcement_refinement_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    report = _activation_reinforcement_report(
        args.db_path,
        limit=args.limit,
        top=args.top,
        frequent_threshold=args.frequent_threshold,
    )
    candidates = [
        _ref_safe_reinforcement_refinement_candidate(candidate, frequent_threshold=args.frequent_threshold)
        for candidate in report["reinforcement_candidates"]
    ]
    blocked_reasons: list[str] = []
    if not candidates:
        blocked_reasons.append("no_reinforcement_candidates_ready")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_reinforcement_refinement_preview",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "activation_count": report["activation_count"],
        "negative_evidence": report["negative_evidence"],
        "scan": {
            "limit": args.limit,
            "top": args.top,
            "frequent_threshold": args.frequent_threshold,
            "quality_warnings": report["quality_warnings"],
        },
        "candidate_count": len(candidates),
        "reinforcement_candidates": candidates,
        "quality_gate": {
            "pass": passed,
            "decision": (
                "reinforcement_refinement_preview_ready_for_human_review"
                if passed
                else "continue_reinforcement_dogfooding_before_refinement_review"
            ),
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
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
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "safe_summaries_included": False,
        },
        "suggested_next_steps": [
            "Review repeated activation candidates before any reinforcement marker apply corridor.",
            "Keep this preview read-only; do not treat G5c/G5d scores as approval.",
            "Use a separate guarded policy with backup/audit/rollback for any future mutation slice.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _fact_review_ref(fact_id: int) -> str:
    return f"fact:{fact_id}"


def _list_supersession_preview_facts(db_path: Path, *, limit: int):
    with connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT *
            FROM facts
            WHERE status IN ('approved', 'candidate', 'disputed', 'deprecated')
            ORDER BY id ASC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [fact_from_row(row) for row in rows]


def _supersession_review_score(*, older_fact, newer_fact, fact_count: int) -> dict[str, Any]:
    confidence_delta = round(float(newer_fact.confidence) - float(older_fact.confidence), 4)
    both_approved = older_fact.status == "approved" and newer_fact.status == "approved"
    newer_higher_confidence = confidence_delta > 0
    different_objects = older_fact.object_ref_or_value != newer_fact.object_ref_or_value
    score = 0
    score += 4 if different_objects else 0
    score += 3 if both_approved else 1
    score += 2 if newer_higher_confidence else 0
    score += 1 if fact_count > 1 else 0
    if score >= 8:
        tier = "high"
    elif score >= 5:
        tier = "medium"
    else:
        tier = "low"
    return {
        "score": score,
        "tier": tier,
        "components": {
            "different_objects": different_objects,
            "both_approved": both_approved,
            "newer_higher_confidence": newer_higher_confidence,
            "confidence_delta": confidence_delta,
            "same_claim_slot_fact_count": fact_count,
        },
    }


def _supersession_review_recommendation(review_score: dict[str, Any]) -> dict[str, Any]:
    tier = str(review_score.get("tier") or "low")
    return {
        "decision": "ready_for_supersession_review" if tier in {"high", "medium"} else "continue_dogfooding_before_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }


def _same_claim_slot_supersession_candidates(db_path: Path, *, limit: int, top: int) -> list[dict[str, Any]]:
    facts = _list_supersession_preview_facts(db_path, limit=limit)
    grouped: dict[tuple[str, str, str], list[Any]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.subject_ref, fact.predicate, fact.scope)].append(fact)

    candidates: list[dict[str, Any]] = []
    for (subject_ref, predicate, scope), slot_facts in grouped.items():
        object_values = {fact.object_ref_or_value for fact in slot_facts}
        if len(slot_facts) < 2 or len(object_values) < 2:
            continue
        sorted_facts = sorted(slot_facts, key=lambda fact: (fact.id, fact.confidence))
        older_fact = sorted_facts[0]
        newer_fact = max(sorted_facts[1:], key=lambda fact: (fact.id, fact.confidence))
        review_score = _supersession_review_score(
            older_fact=older_fact,
            newer_fact=newer_fact,
            fact_count=len(slot_facts),
        )
        candidates.append(
            {
                "candidate_kind": "same_claim_slot_conflict",
                "claim_slot": {
                    "subject_ref_sha256": hashlib.sha256(subject_ref.encode("utf-8")).hexdigest(),
                    "predicate": predicate,
                    "scope": scope,
                    "fact_count": len(slot_facts),
                },
                "older_fact_ref": _fact_review_ref(older_fact.id),
                "newer_fact_ref": _fact_review_ref(newer_fact.id),
                "status_context": {
                    "older_status": older_fact.status,
                    "newer_status": newer_fact.status,
                    "older_confidence": round(float(older_fact.confidence), 4),
                    "newer_confidence": round(float(newer_fact.confidence), 4),
                },
                "replacement_chain": {
                    "existing_relation_count": len(
                        list_fact_replacement_relations(db_path, fact_id=older_fact.id)
                    ),
                    "relation_mutation_supported_by_preview": False,
                },
                "enriched_evidence": _supersession_enriched_evidence(
                    db_path,
                    older_fact=older_fact,
                    newer_fact=newer_fact,
                ),
                "review_score": review_score,
                "review_recommendation": _supersession_review_recommendation(review_score),
                "review_commands": {
                    "review_older": f"agent-memory review fact {db_path} {older_fact.id}",
                    "review_newer": f"agent-memory review fact {db_path} {newer_fact.id}",
                    "review_replacements_older": f"agent-memory review replacements fact {db_path} {older_fact.id}",
                    "future_guarded_apply": "not_supported_by_preview",
                },
            }
        )
    candidates.sort(
        key=lambda candidate: (
            -_safe_int(candidate["review_score"]["score"]),
            candidate["older_fact_ref"],
            candidate["newer_fact_ref"],
        )
    )
    return candidates[:top]


def _dogfood_supersession_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.limit < 1:
        raise ValueError("dogfood supersession-preview limit must be >= 1")
    if args.top < 1:
        raise ValueError("dogfood supersession-preview top must be >= 1")
    candidates = _same_claim_slot_supersession_candidates(args.db_path, limit=args.limit, top=args.top)
    blocked_reasons: list[str] = []
    if not candidates:
        blocked_reasons.append("no_supersession_candidates_ready")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_supersession_preview",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "scan": {
            "limit": args.limit,
            "top": args.top,
            "candidate_sources": ["same_claim_slot_conflict"],
        },
        "candidate_count": len(candidates),
        "supersession_candidates": candidates,
        "quality_gate": {
            "pass": passed,
            "decision": (
                "supersession_preview_ready_for_human_review"
                if passed
                else "continue_supersession_dogfooding_before_review"
            ),
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
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
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "safe_summaries_included": False,
            "subject_values_hashed": True,
            "object_values_included": False,
        },
        "suggested_next_steps": [
            "Review same-claim-slot conflicts before any replacement/supersession relation apply corridor.",
            "Keep this preview read-only; do not deprecate or supersede memories from score alone.",
            "Use a separate guarded policy with backup/audit/rollback for any future mutation slice.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _ref_safe_decay_collapse_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "memory_ref": candidate["memory_ref"],
        "current_status": candidate["current_status"],
        "decay_score": candidate["score"],
        "activation_count": candidate["activation_count"],
        "total_strength": candidate["total_strength"],
        "signals": candidate["signals"],
        "factor_breakdown": candidate["factor_breakdown"],
        "ref_safe_evidence": candidate["ref_safe_evidence"],
        "resolution_hint": candidate["resolution_hint"],
        "review_support": candidate["review_support"],
        "sample_activation_ids": candidate["sample_activation_ids"],
        "sample_observation_ids": candidate["sample_observation_ids"],
        "activation_window": candidate["activation_window"],
        "review_recommendation": {
            "decision": "ready_for_decay_collapse_review",
            "automation": "human_review_only",
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_unchanged": True,
            "mutation_supported": False,
        },
        "collapse_review": {
            "candidate_action": "consider_decay_or_collapse_after_review",
            "apply_path": "not_supported_by_preview",
            "requires_separate_guarded_policy": True,
        },
    }


def _dogfood_decay_collapse_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.min_decay_score < 0:
        raise ValueError("dogfood decay-collapse-preview min-decay-score must be >= 0")
    report = _activation_decay_risk_report(
        args.db_path,
        limit=args.limit,
        top=args.top,
        frequent_threshold=args.frequent_threshold,
    )
    candidates = [
        _ref_safe_decay_collapse_candidate(candidate)
        for candidate in report["decay_risk_candidates"]
        if candidate["score"] >= args.min_decay_score
    ]
    blocked_reasons: list[str] = []
    if not candidates:
        blocked_reasons.append("no_decay_collapse_candidates_ready")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_decay_collapse_preview",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "activation_count": report["activation_count"],
        "negative_evidence": report["negative_evidence"],
        "scan": {
            "limit": args.limit,
            "top": args.top,
            "frequent_threshold": args.frequent_threshold,
            "min_decay_score": args.min_decay_score,
            "quality_warnings": report["quality_warnings"],
        },
        "candidate_decomposition": report["candidate_decomposition"],
        "candidate_count": len(candidates),
        "decay_collapse_candidates": candidates,
        "quality_gate": {
            "pass": passed,
            "decision": (
                "decay_collapse_preview_ready_for_human_review"
                if passed
                else "continue_decay_collapse_dogfooding_before_review"
            ),
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
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
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "safe_summaries_included": False,
        },
        "suggested_next_steps": [
            "Review stale weak-evidence candidates before any decay/collapse apply corridor.",
            "Keep this preview read-only; do not delete, deprecate, or collapse memories from score alone.",
            "Use a separate guarded policy with backup/audit/rollback for any future mutation slice.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


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
    evidence_snapshot = _ref_safe_evidence_snapshot(db_path, memory_ref)
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

    resolution_hint = _decay_resolution_hint(
        current_status=current_status,
        activation_count=activation_count,
        frequent_threshold=frequent_threshold,
        evidence_snapshot=evidence_snapshot,
    )

    return {
        "memory_ref": memory_ref,
        "score": score,
        "current_status": current_status,
        "activation_count": activation_count,
        "total_strength": round(total_strength, 4),
        "factor_breakdown": factor_breakdown,
        "protections": protections,
        "ref_safe_evidence": evidence_snapshot,
        "resolution_hint": resolution_hint,
        "review_support": _decay_review_support(db_path, memory_ref, resolution_hint),
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
    top_candidates = candidates[:top]
    factor_score_max: dict[str, float] = {}
    signal_counts: Counter[str] = Counter()
    resolution_hint_counts: Counter[str] = Counter()
    for candidate in top_candidates:
        signal_counts.update(str(signal) for signal in candidate.get("signals", []) if signal)
        if candidate.get("resolution_hint"):
            resolution_hint_counts[str(candidate["resolution_hint"])] += 1
        for factor_name, factor in candidate.get("factor_breakdown", {}).items():
            factor_score_max[factor_name] = max(factor_score_max.get(factor_name, 0.0), _safe_float(factor.get("score")))
    top_factor_names = [
        factor_name
        for factor_name, _score in sorted(factor_score_max.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]

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
        "candidate_decomposition": {
            "candidate_count": len(top_candidates),
            "max_score": max((candidate["score"] for candidate in top_candidates), default=0.0),
            "top_factor_names": top_factor_names,
            "factor_score_max": dict(sorted(factor_score_max.items())),
            "signal_counts": {key: signal_counts[key] for key in sorted(signal_counts)},
            "resolution_hint_counts": {key: resolution_hint_counts[key] for key in sorted(resolution_hint_counts)},
            "sample_memory_refs": [candidate["memory_ref"] for candidate in top_candidates[:5]],
            "raw_content_included": False,
        },
        "decay_risk_candidates": top_candidates,
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


def _trace_cluster_review_score(candidate: dict[str, Any]) -> dict[str, Any]:
    evidence_count = _safe_int(candidate.get("evidence_count"))
    related_observation_count = len(candidate.get("related_observation_ids", []) or [])
    related_memory_ref_count = len(candidate.get("related_memory_refs", []) or [])
    salience_total = round(_safe_float(candidate.get("salience_total")), 4)
    user_emphasis_total = round(_safe_float(candidate.get("user_emphasis_total")), 4)
    reinforcement = candidate.get("reinforcement") if isinstance(candidate.get("reinforcement"), dict) else {}
    reinforcement_count = _safe_int(reinforcement.get("activation_count", 0))
    risk_flags = candidate.get("risk_flags", []) if isinstance(candidate.get("risk_flags"), list) else []
    risk_penalty = len(risk_flags) if any(flag != "low_evidence_count" for flag in risk_flags) else 0
    score = max(
        0,
        int(
            (evidence_count * 2)
            + related_observation_count
            + related_memory_ref_count
            + min(salience_total, 5.0)
            + min(user_emphasis_total, 5.0)
            + min(reinforcement_count, 5)
            - risk_penalty
        ),
    )
    if score >= 7:
        tier = "high"
    elif score >= 4:
        tier = "medium"
    else:
        tier = "low"
    return {
        "score": score,
        "tier": tier,
        "components": {
            "evidence_count": evidence_count,
            "related_observation_count": related_observation_count,
            "related_memory_ref_count": related_memory_ref_count,
            "salience_total": salience_total,
            "user_emphasis_total": user_emphasis_total,
            "reinforcement_count": reinforcement_count,
            "risk_penalty": risk_penalty,
        },
    }


def _trace_cluster_review_recommendation(review_score: dict[str, Any]) -> dict[str, Any]:
    tier = str(review_score.get("tier") or "low")
    return {
        "decision": "ready_for_human_review" if tier in {"high", "medium"} else "continue_dogfooding_before_review",
        "automation": "human_review_only",
        "ordinary_conversation_auto_approval": False,
        "default_retrieval_unchanged": True,
        "mutation_supported": False,
    }


def _ref_safe_trace_cluster(candidate: dict[str, Any]) -> dict[str, Any]:
    group_reason = _consolidation_group_reason(candidate)
    review_score = _trace_cluster_review_score(candidate)
    group_reason.pop("cluster_key", None)
    group_reason.pop("summary_key", None)
    cluster_key = str(candidate["cluster_key"])
    return {
        "candidate_id": candidate["candidate_id"],
        "fingerprint": candidate["fingerprint"],
        "cluster_key_sha256": hashlib.sha256(cluster_key.encode("utf-8")).hexdigest(),
        "group_reason": group_reason,
        "guessed_memory_type": candidate["guessed_memory_type"],
        "evidence_count": candidate["evidence_count"],
        "evidence_trace_ids": candidate["evidence_trace_ids"],
        "evidence_window": candidate["evidence_window"],
        "surfaces": candidate["surfaces"],
        "scopes": candidate["scopes"],
        "event_kind_counts": candidate["event_kind_counts"],
        "retention_policy_counts": candidate["retention_policy_counts"],
        "related_memory_refs": candidate["related_memory_refs"],
        "related_observation_ids": candidate["related_observation_ids"],
        "salience_total": candidate["salience_total"],
        "user_emphasis_total": candidate["user_emphasis_total"],
        "reinforcement": candidate["reinforcement"],
        "review_score": review_score,
        "review_recommendation": _trace_cluster_review_recommendation(review_score),
        "risk_flags": candidate["risk_flags"],
    }


def _dogfood_trace_cluster_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.limit < 1:
        raise ValueError("dogfood trace-cluster-preview limit must be >= 1")
    if args.top < 1:
        raise ValueError("dogfood trace-cluster-preview top must be >= 1")
    if args.min_evidence_count < 1:
        raise ValueError("dogfood trace-cluster-preview min-evidence-count must be >= 1")

    report = _consolidation_candidates_report(
        args.db_path,
        limit=args.limit,
        top=args.top,
        min_evidence=args.min_evidence_count,
    )
    clusters = [_ref_safe_trace_cluster(candidate) for candidate in report["candidates"]]
    blocked_reasons: list[str] = []
    if not clusters:
        blocked_reasons.append("no_trace_clusters_ready")
    if report.get("quality_warnings"):
        blocked_reasons.append("trace_cluster_quality_warnings_present")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_trace_cluster_preview",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "scan": {
            "limit": args.limit,
            "top": args.top,
            "min_evidence_count": args.min_evidence_count,
            "source_trace_count": report["trace_count"],
            "quality_warnings": report["quality_warnings"],
        },
        "cluster_count": len(clusters),
        "clusters": clusters,
        "quality_gate": {
            "pass": passed,
            "decision": (
                "trace_cluster_preview_ready_for_reviewed_candidate_flow"
                if passed
                else "continue_trace_cluster_dogfooding_before_reviewed_candidate_flow"
            ),
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
            "apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
            "mutation_contract": {
                "writes_review_queue": False,
                "promotes_long_term_memory": False,
                "raw_content_allowed": False,
            },
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "safe_summaries_included": False,
        },
        "suggested_next_steps": [
            "Use these ref-safe clusters as the first G5 reviewed-candidate runway signal only.",
            "Do not persist review queue items or promote long-term memories from this preview command.",
            "Next slice should add explicit reviewed candidate flow with RED-tested audit and rollback contracts.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _ensure_trace_candidate_review_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS g5_trace_candidate_reviews (
            candidate_id TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'promoted')),
            proposal_type TEXT NOT NULL,
            target_ref TEXT,
            cluster_json TEXT NOT NULL,
            cluster_sha256 TEXT NOT NULL,
            reviewed_json TEXT NOT NULL DEFAULT '{}',
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
        CREATE TABLE IF NOT EXISTS g5_trace_candidate_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            candidate_id TEXT NOT NULL,
            proposal_type TEXT NOT NULL,
            promoted_ref TEXT,
            policy TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason_sha256 TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            backup_sha256 TEXT NOT NULL,
            rollback_hint_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(candidate_id, policy)
        )
        """
    )


def _ensure_lifecycle_candidate_review_tables(connection: sqlite3.Connection) -> None:
    _ensure_trace_candidate_review_tables(connection)
    columns = {row[1] for row in connection.execute("PRAGMA table_info(g5_trace_candidate_reviews)").fetchall()}
    if "candidate_kind" not in columns:
        connection.execute("ALTER TABLE g5_trace_candidate_reviews ADD COLUMN candidate_kind TEXT NOT NULL DEFAULT 'trace'")


def _lifecycle_preview_for_kind(
    db_path: Path,
    *,
    candidate_kind: str,
    limit: int,
    top: int,
    frequent_threshold: int,
    min_decay_score: float,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    if candidate_kind == "reinforcement":
        preview = _dogfood_reinforcement_refinement_preview_payload(
            argparse.Namespace(db_path=db_path, output=None, limit=limit, top=top, frequent_threshold=frequent_threshold)
        )
        candidates = preview.get("reinforcement_candidates", [])
    elif candidate_kind == "decay":
        preview = _dogfood_decay_collapse_preview_payload(
            argparse.Namespace(
                db_path=db_path,
                output=None,
                limit=limit,
                top=top,
                frequent_threshold=frequent_threshold,
                min_decay_score=min_decay_score,
            )
        )
        candidates = preview.get("decay_collapse_candidates", [])
    elif candidate_kind == "supersession":
        preview = _dogfood_supersession_preview_payload(argparse.Namespace(db_path=db_path, output=None, limit=limit, top=top))
        candidates = preview.get("supersession_candidates", [])
    else:
        raise ValueError("candidate-kind must be reinforcement, decay, or supersession")
    return preview, [candidate for candidate in candidates if isinstance(candidate, dict)]


def _lifecycle_candidate_id(candidate_kind: str, candidate: dict[str, Any]) -> str:
    digest = hashlib.sha256(json.dumps(candidate, sort_keys=True).encode("utf-8")).hexdigest()
    return f"g5-{candidate_kind}-{digest[:24]}"


def _lifecycle_candidate_target_ref(candidate_kind: str, candidate: dict[str, Any]) -> str | None:
    if candidate_kind in {"reinforcement", "decay"}:
        value = candidate.get("memory_ref")
        return str(value) if value else None
    if candidate_kind == "supersession":
        value = candidate.get("older_fact_ref")
        return str(value) if value else None
    return None


def _dogfood_lifecycle_candidate_persist_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood lifecycle-candidate-persist requires non-empty --actor and --reason")
    preview, candidates = _lifecycle_preview_for_kind(
        args.db_path,
        candidate_kind=args.candidate_kind,
        limit=args.limit,
        top=args.top,
        frequent_threshold=args.frequent_threshold,
        min_decay_score=args.min_decay_score,
    )
    source_preview_sha256 = hashlib.sha256(json.dumps(preview, sort_keys=True).encode("utf-8")).hexdigest()
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    proposal_type = f"{args.candidate_kind}_review"
    inserted = 0
    existing = 0
    candidate_ids: list[str] = []
    with sqlite3.connect(args.db_path) as connection:
        _ensure_lifecycle_candidate_review_tables(connection)
        for candidate in candidates:
            candidate_id = _lifecycle_candidate_id(args.candidate_kind, candidate)
            candidate_ids.append(candidate_id)
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO g5_trace_candidate_reviews (
                    candidate_id, status, proposal_type, target_ref, cluster_json, cluster_sha256,
                    reviewed_json, actor, reason_sha256, audit_json, candidate_kind
                ) VALUES (?, 'pending', ?, ?, ?, ?, '{}', ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    proposal_type,
                    _lifecycle_candidate_target_ref(args.candidate_kind, candidate),
                    json.dumps(candidate, sort_keys=True),
                    source_preview_sha256,
                    args.actor.strip(),
                    reason_sha256,
                    json.dumps([
                        {
                            "action": "persist",
                            "actor": args.actor.strip(),
                            "reason_sha256": reason_sha256,
                            "candidate_kind": args.candidate_kind,
                        }
                    ], sort_keys=True),
                    args.candidate_kind,
                ),
            )
            if connection.total_changes > before:
                inserted += 1
            else:
                existing += 1
    payload = {
        "kind": "dogfood_lifecycle_candidate_persist",
        "read_only": False,
        "mutated": inserted > 0,
        "default_retrieval_unchanged": True,
        "candidate_kind": args.candidate_kind,
        "candidate_persistence_supported": True,
        "apply_supported": False,
        "db_path": str(args.db_path),
        "source_preview_sha256": source_preview_sha256,
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "inserted_count": inserted,
        "existing_count": existing,
        "quality_gate": preview.get("quality_gate", {}),
        "privacy": {
            "candidate_json_included": False,
            "raw_content_included": False,
            "sample_values_included": False,
            "reason_stored_as_sha256": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_lifecycle_candidate_list_payload(args: argparse.Namespace) -> dict[str, Any]:
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        rows = connection.execute(
            """
            SELECT candidate_id, status, candidate_kind, proposal_type, target_ref, cluster_sha256 AS candidate_sha256
            FROM g5_trace_candidate_reviews
            WHERE (? IS NULL OR status = ?) AND (? IS NULL OR candidate_kind = ?)
            ORDER BY created_at DESC, candidate_id
            LIMIT ?
            """,
            (args.status, args.status, args.candidate_kind, args.candidate_kind, args.limit),
        ).fetchall()
    return {
        "kind": "dogfood_lifecycle_candidate_list",
        "read_only": True,
        "mutated": False,
        "db_path": str(args.db_path),
        "count": len(rows),
        "items": [dict(row) for row in rows],
        "privacy": {
            "candidate_json_included": False,
            "reviewed_payload_included": False,
            "raw_content_included": False,
            "sample_values_included": False,
        },
    }


def _dogfood_lifecycle_candidate_update_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.status not in {"approved", "rejected"}:
        raise ValueError("dogfood lifecycle-candidate-update status must be approved or rejected")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood lifecycle-candidate-update requires non-empty --actor and --reason")
    expected_phrase = f"{args.status[:-1] if args.status.endswith('d') else args.status}-g5-lifecycle-candidate-v1"
    if args.approval_phrase != expected_phrase:
        raise ValueError(f"dogfood lifecycle-candidate-update requires --approval-phrase {expected_phrase}")
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        row = connection.execute(
            "SELECT status, proposal_type, candidate_kind, target_ref, cluster_sha256, reviewed_json, audit_json FROM g5_trace_candidate_reviews WHERE candidate_id = ?",
            (args.candidate_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"lifecycle candidate not found: {args.candidate_id}")
        status_before = row["status"]
        audit = _safe_json_list_from_db(row["audit_json"])
        reviewed = _safe_json_dict_from_db(row["reviewed_json"])
        artifact_stored = False
        artifact_sha256 = None
        artifact_status = None
        artifact_input = _load_json_argument(
            getattr(args, "collapse_proof_artifact_json", None),
            label="--collapse-proof-artifact-json",
        )
        if artifact_input:
            if row["candidate_kind"] != "decay":
                raise ValueError("--collapse-proof-artifact-json is only supported for decay lifecycle candidates")
            artifact = artifact_input.get("collapse_proof_artifact", artifact_input)
            if not isinstance(artifact, dict):
                raise ValueError("--collapse-proof-artifact-json must contain an object artifact")
            artifact = dict(artifact)
            artifact.setdefault("candidate_id", args.candidate_id)
            artifact.setdefault("target_ref", row["target_ref"])
            artifact.setdefault("candidate_sha256", row["cluster_sha256"])
            artifact.setdefault("collapse_apply_allowed", False)
            artifact.setdefault("delete_apply_allowed", False)
            reviewed["collapse_proof_artifact"] = artifact
            artifact_sha256 = hashlib.sha256(json.dumps(artifact, sort_keys=True).encode("utf-8")).hexdigest()
            artifact_status = _collapse_proof_status_from_artifact(artifact)
            artifact_stored = True
        audit.append(
            {
                "action": args.status,
                "actor": args.actor.strip(),
                "reason_sha256": reason_sha256,
                "candidate_id": args.candidate_id,
                "status_before": status_before,
                "status_after": args.status,
                "proposal_type": row["proposal_type"],
                "candidate_kind": row["candidate_kind"],
            }
        )
        connection.execute(
            """
            UPDATE g5_trace_candidate_reviews
            SET status = ?, updated_at = CURRENT_TIMESTAMP, actor = ?, reason_sha256 = ?, reviewed_json = ?, audit_json = ?
            WHERE candidate_id = ?
            """,
            (
                args.status,
                args.actor.strip(),
                reason_sha256,
                json.dumps(reviewed, sort_keys=True),
                json.dumps(audit, sort_keys=True),
                args.candidate_id,
            ),
        )
    return {
        "kind": "dogfood_lifecycle_candidate_update",
        "read_only": False,
        "mutated": status_before != args.status,
        "default_retrieval_unchanged": True,
        "apply_supported": False,
        "candidate_id": args.candidate_id,
        "candidate_kind": row["candidate_kind"],
        "proposal_type": row["proposal_type"],
        "status_before": status_before,
        "status_after": args.status,
        "reason_sha256": reason_sha256,
        "proof_artifact_stored": artifact_stored,
        "proof_artifact_sha256": artifact_sha256,
        "proof_artifact_status": artifact_status,
        "privacy": {"candidate_json_included": False, "raw_reason_included": False, "raw_content_included": False},
    }


def _fact_id_from_ref(ref: str) -> int:
    if not ref.startswith("fact:"):
        raise ValueError(f"expected fact ref, got: {ref}")
    return int(ref.split(":", 1)[1])


def _load_json_argument(value: str | None, *, label: str) -> dict[str, Any]:
    if not value:
        return {}
    raw = value.strip()
    path = Path(raw).expanduser()
    if path.exists():
        raw = path.read_text()
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError(f"{label} must be a JSON object or a path to a JSON object")
    return parsed


def _collapse_proof_artifact_from_reviewed(reviewed: dict[str, Any]) -> dict[str, Any]:
    artifact = reviewed.get("collapse_proof_artifact", {})
    return artifact if isinstance(artifact, dict) else {}


def _collapse_proof_status_from_artifact(artifact: dict[str, Any]) -> str:
    status = artifact.get("current_status")
    return status if status in {"satisfied", "partially_satisfied", "not_satisfied"} else "not_satisfied"


def _memory_ref_parts(ref: str) -> tuple[str, int]:
    if ":" not in ref:
        raise ValueError(f"expected memory ref, got: {ref}")
    memory_type, raw_id = ref.split(":", 1)
    if memory_type not in {"fact", "procedure", "episode"}:
        raise ValueError(f"unsupported memory ref type for lifecycle apply: {memory_type}")
    return memory_type, int(raw_id)


def _supersession_enriched_evidence(db_path: Path, *, older_fact, newer_fact) -> dict[str, Any]:
    older_ref = _fact_review_ref(older_fact.id)
    newer_ref = _fact_review_ref(newer_fact.id)
    older_relations = list_relations_for_node(db_path, node_ref=older_ref)
    newer_relations = list_relations_for_node(db_path, node_ref=newer_ref)
    older_activations = [a for a in list_memory_activations(db_path, limit=500) if a.memory_type == "fact" and a.memory_id == older_fact.id]
    newer_activations = [a for a in list_memory_activations(db_path, limit=500) if a.memory_type == "fact" and a.memory_id == newer_fact.id]
    older_history = list_memory_status_history(db_path, memory_type="fact", memory_id=older_fact.id)
    newer_history = list_memory_status_history(db_path, memory_type="fact", memory_id=newer_fact.id)
    temporal_order = "newer_fact_id_after_older" if newer_fact.id > older_fact.id else "ambiguous"
    return {
        "relation_signals": {
            "older_relation_count": len(older_relations),
            "newer_relation_count": len(newer_relations),
            "older_conflict_relation_count": len(list_fact_conflict_relations(db_path, fact_id=older_fact.id)),
            "newer_conflict_relation_count": len(list_fact_conflict_relations(db_path, fact_id=newer_fact.id)),
            "older_replacement_relation_count": len(list_fact_replacement_relations(db_path, fact_id=older_fact.id)),
            "newer_replacement_relation_count": len(list_fact_replacement_relations(db_path, fact_id=newer_fact.id)),
        },
        "temporal_signals": {
            "order": temporal_order,
            "older_fact_id": older_fact.id,
            "newer_fact_id": newer_fact.id,
            "older_status_transition_count": len(older_history),
            "newer_status_transition_count": len(newer_history),
        },
        "activation_signals": {
            "older_activation_count": len(older_activations),
            "newer_activation_count": len(newer_activations),
            "older_activation_ids": [a.id for a in older_activations[:5]],
            "newer_activation_ids": [a.id for a in newer_activations[:5]],
        },
        "raw_content_included": False,
    }


def _rollback_confidence_for_backup(backup_path: str, expected_sha256: str | None) -> dict[str, Any]:
    path = Path(backup_path).expanduser().resolve(strict=False)
    exists = path.exists()
    actual_sha256 = None
    if exists:
        actual_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "backup_path": str(path),
        "backup_exists": exists,
        "backup_sha256_matches": bool(expected_sha256 and actual_sha256 == expected_sha256),
        "restore_command": f"cp {path} <target-db>" if exists else None,
    }


def _sqlite_table_counts_for_tables(db_path: Path, tables: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    with sqlite3.connect(db_path) as connection:
        for table in tables:
            counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if _table_exists(connection, table) else 0
    return counts


def _validate_sqlite_backup_restore(backup_path: str, expected_sha256: str | None, *, temp_dir: Path) -> dict[str, Any]:
    path = Path(backup_path).expanduser().resolve(strict=False)
    confidence = _rollback_confidence_for_backup(str(path), expected_sha256)
    validation: dict[str, Any] = {
        **confidence,
        "restore_replay_checked": False,
        "restored_db_opened": False,
        "schema_initialized": False,
        "table_counts_match_backup": False,
        "raw_content_included": False,
    }
    if not path.exists() or not confidence["backup_sha256_matches"]:
        return validation
    restore_path = temp_dir / f"restore-{hashlib.sha256(str(path).encode('utf-8')).hexdigest()[:12]}.db"
    shutil.copy2(path, restore_path)
    try:
        initialize_database(restore_path)
        tables = (
            "source_records",
            "facts",
            "procedures",
            "episodes",
            "relations",
            "memory_status_transitions",
            "retrieval_observations",
            "experience_traces",
            "memory_activations",
        )
        original_counts = _sqlite_table_counts_for_tables(path, tables)
        restored_counts = _sqlite_table_counts_for_tables(restore_path, tables)
        validation.update(
            {
                "restore_replay_checked": True,
                "restored_db_opened": True,
                "schema_initialized": True,
                "table_counts_match_backup": original_counts == restored_counts,
                "restored_table_counts": restored_counts,
            }
        )
    except sqlite3.DatabaseError as exc:
        validation["restore_error"] = type(exc).__name__
    finally:
        if restore_path.exists():
            restore_path.unlink()
    return validation


def _dogfood_rollback_replay_validate_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        rows = connection.execute(
            """
            SELECT candidate_id, proposal_type, promoted_ref, policy, action, backup_path, backup_sha256, rollback_hint_json, created_at
            FROM g5_trace_candidate_applications
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    applications: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        for row in rows:
            replay = _validate_sqlite_backup_restore(row["backup_path"], row["backup_sha256"], temp_dir=temp_dir)
            applications.append(
                {
                    "candidate_id": row["candidate_id"],
                    "proposal_type": row["proposal_type"],
                    "policy": row["policy"],
                    "action": row["action"],
                    "promoted_ref": row["promoted_ref"],
                    "created_at": row["created_at"],
                    "rollback_hint": _safe_json_dict_from_db(row["rollback_hint_json"]),
                    "rollback_replay_validation": replay,
                }
            )
    blocked_reasons: list[str] = []
    if any(not app["rollback_replay_validation"]["backup_exists"] for app in applications):
        blocked_reasons.append("missing_backup")
    if any(not app["rollback_replay_validation"]["backup_sha256_matches"] for app in applications):
        blocked_reasons.append("backup_checksum_mismatch")
    if any(not app["rollback_replay_validation"]["restored_db_opened"] for app in applications):
        blocked_reasons.append("restore_open_failed")
    if any(not app["rollback_replay_validation"]["table_counts_match_backup"] for app in applications):
        blocked_reasons.append("restore_table_count_mismatch")
    passed_replay_count = sum(
        1
        for app in applications
        if app["rollback_replay_validation"].get("backup_exists")
        and app["rollback_replay_validation"].get("backup_sha256_matches")
        and app["rollback_replay_validation"].get("restored_db_opened")
        and app["rollback_replay_validation"].get("table_counts_match_backup")
    )
    policy_counts = Counter(str(app.get("policy") or "unknown") for app in applications)
    latest_application_created_at = max((str(app.get("created_at") or "") for app in applications), default=None)
    payload = {
        "kind": "dogfood_rollback_replay_validate",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "application_count": len(applications),
        "applications": applications,
        "rollup": {
            "checked_application_count": len(applications),
            "passed_replay_count": passed_replay_count,
            "failed_replay_count": len(applications) - passed_replay_count,
            "policy_counts": {key: policy_counts[key] for key in sorted(policy_counts)},
            "latest_application_created_at": latest_application_created_at,
            "live_report_accumulation_safe": True,
        },
        "quality_gate": {
            "pass": not blocked_reasons,
            "blocked_reasons": blocked_reasons,
            "decision": "rollback_restore_replay_sufficient_for_bounded_partial_automation" if not blocked_reasons else "fix_restore_replay_before_broader_automation",
        },
        "privacy": {"raw_content_included": False, "backup_content_included": False},
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_lifecycle_candidate_apply_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy_contracts = {
        "g5-lifecycle-supersession-apply-v1": {
            "candidate_kind": "supersession",
            "proposal_type": "supersession_review",
            "approval_phrase": "apply-approved-g5-lifecycle-supersession-v1",
            "apply_mode": "approved_supersession_lifecycle_candidates_only",
        },
        "g5-lifecycle-decay-deprecate-apply-v1": {
            "candidate_kind": "decay",
            "proposal_type": "decay_review",
            "approval_phrase": "apply-approved-g5-lifecycle-decay-deprecate-v1",
            "apply_mode": "approved_decay_lifecycle_candidates_deprecate_only",
        },
    }
    contract = policy_contracts.get(args.policy)
    if contract is None:
        expected = ", ".join(sorted(policy_contracts))
        raise ValueError(f"dogfood lifecycle-candidate-apply requires --policy one of: {expected}")
    policy = args.policy
    if args.approval_phrase != contract["approval_phrase"]:
        raise ValueError(f"dogfood lifecycle-candidate-apply requires --approval-phrase {contract['approval_phrase']}")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood lifecycle-candidate-apply requires non-empty --actor and --reason")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")
    backup_path = args.backup_path.expanduser().resolve(strict=False) if args.backup_path else _default_backup_path(db_path, label="g5-lifecycle-candidate-apply")
    backup = _create_sqlite_backup(db_path, backup_path)
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    candidate_filter = list(args.candidate_id or [])
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        if candidate_filter:
            placeholders = ", ".join("?" for _ in candidate_filter)
            rows = connection.execute(
                f"SELECT * FROM g5_trace_candidate_reviews WHERE candidate_id IN ({placeholders}) ORDER BY candidate_id",
                tuple(candidate_filter),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM g5_trace_candidate_reviews WHERE status = 'approved' AND candidate_kind = ? ORDER BY candidate_id",
                (contract["candidate_kind"],),
            ).fetchall()
        found_ids = {row["candidate_id"] for row in rows}
        for missing in sorted(set(candidate_filter) - found_ids):
            skipped.append({"candidate_id": missing, "reason": "not_found"})

    for row in rows:
        candidate_id = row["candidate_id"]
        if row["status"] != "approved":
            skipped.append({"candidate_id": candidate_id, "reason": f"status_{row['status']}"})
            continue
        if row["candidate_kind"] != contract["candidate_kind"] or row["proposal_type"] != contract["proposal_type"]:
            skipped.append({"candidate_id": candidate_id, "reason": f"unsupported_{row['candidate_kind']}_{row['proposal_type']}"})
            continue
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                "SELECT promoted_ref FROM g5_trace_candidate_applications WHERE candidate_id = ? AND policy = ?",
                (candidate_id, policy),
            ).fetchone()
        candidate = _safe_json_dict_from_db(row["cluster_json"])
        applied_entry: dict[str, Any]
        rollback_hint: dict[str, Any]
        promoted_ref: str
        if contract["candidate_kind"] == "supersession":
            superseded_ref = str(candidate.get("older_fact_ref") or "")
            replacement_ref = str(candidate.get("newer_fact_ref") or "")
            action = "apply_reviewed_supersession_relation"
            applied_entry = {
                "candidate_id": candidate_id,
                "action": action,
                "superseded_ref": superseded_ref,
                "replacement_ref": replacement_ref,
            }
            promoted_ref = replacement_ref
        else:
            memory_ref = str(candidate.get("memory_ref") or row["target_ref"] or "")
            action = "apply_reviewed_decay_deprecation"
            applied_entry = {"candidate_id": candidate_id, "action": action, "memory_ref": memory_ref}
            promoted_ref = memory_ref
        if existing is not None:
            applied.append({**applied_entry, "inserted": False})
            continue
        if contract["candidate_kind"] == "supersession":
            relation = supersede_fact(
                db_path=db_path,
                superseded_fact_id=_fact_id_from_ref(applied_entry["superseded_ref"]),
                replacement_fact_id=_fact_id_from_ref(applied_entry["replacement_ref"]),
                actor=args.actor.strip(),
                reason=args.reason.strip(),
            )
            rollback_hint = {
                "restore_backup_path": str(backup_path),
                "candidate_id": candidate_id,
                "policy": policy,
                "relation_id": relation.id,
                "superseded_ref": applied_entry["superseded_ref"],
                "replacement_ref": applied_entry["replacement_ref"],
                "default_retrieval_mutated": False,
            }
        else:
            memory_type, memory_id = _memory_ref_parts(applied_entry["memory_ref"])
            before_status = get_memory_status(db_path, memory_type=memory_type, memory_id=memory_id)
            deprecate_memory(
                db_path=db_path,
                memory_type=memory_type,
                memory_id=memory_id,
                actor=args.actor.strip(),
                reason=args.reason.strip(),
            )
            rollback_hint = {
                "restore_backup_path": str(backup_path),
                "candidate_id": candidate_id,
                "policy": policy,
                "memory_ref": applied_entry["memory_ref"],
                "status_before": before_status,
                "status_after": "deprecated",
                "default_retrieval_mutated": False,
            }
        with sqlite3.connect(db_path) as connection:
            _ensure_lifecycle_candidate_review_tables(connection)
            connection.execute(
                """
                INSERT INTO g5_trace_candidate_applications (
                    candidate_id, proposal_type, promoted_ref, policy, action, actor, reason_sha256,
                    backup_path, backup_sha256, rollback_hint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row["proposal_type"],
                    promoted_ref,
                    policy,
                    action,
                    args.actor.strip(),
                    reason_sha256,
                    str(backup_path),
                    backup["sha256"],
                    json.dumps(rollback_hint, sort_keys=True),
                ),
            )
            audit = _safe_json_list_from_db(row["audit_json"])
            audit_event = {
                "action": "apply",
                "actor": args.actor.strip(),
                "policy": policy,
                "reason_sha256": reason_sha256,
                "candidate_kind": contract["candidate_kind"],
            }
            audit_event.update({key: value for key, value in applied_entry.items() if key != "candidate_id"})
            audit.append(audit_event)
            connection.execute(
                "UPDATE g5_trace_candidate_reviews SET status = 'promoted', updated_at = CURRENT_TIMESTAMP, actor = ?, reason_sha256 = ?, audit_json = ? WHERE candidate_id = ?",
                (args.actor.strip(), reason_sha256, json.dumps(audit, sort_keys=True), candidate_id),
            )
        applied.append({**applied_entry, "inserted": True})

    payload = {
        "kind": "dogfood_lifecycle_candidate_apply",
        "read_only": False,
        "mutated": any(item.get("inserted") for item in applied),
        "default_retrieval_unchanged": True,
        "db_path": str(db_path),
        "policy": policy,
        "approval_phrase_matched": True,
        "actor": args.actor.strip(),
        "reason_sha256": reason_sha256,
        "backup": backup,
        "apply_mode": contract["apply_mode"],
        "applied": applied,
        "skipped": skipped,
        "rollback_hint": {
            "restore_backup_to_revert": True,
            "backup_path": str(backup_path),
            "default_retrieval_mutated": False,
        },
        "privacy": {"candidate_json_included": False, "raw_reason_included": False, "raw_content_included": False},
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_trace_candidate_generate_payload(args: argparse.Namespace) -> dict[str, Any]:
    preview = _dogfood_trace_cluster_preview_payload(
        argparse.Namespace(
            db_path=args.db_path,
            output=None,
            limit=args.limit,
            top=args.top,
            min_evidence_count=args.min_evidence_count,
        )
    )
    generated: list[dict[str, Any]] = []
    for cluster in preview.get("clusters", []):
        if not isinstance(cluster, dict):
            continue
        guessed_type = str(cluster.get("guessed_memory_type") or "fact")
        proposal_type = "preference" if guessed_type == "preference" else guessed_type
        if proposal_type not in {"fact", "procedure", "preference"}:
            proposal_type = "fact"
        generated.append(
            {
                "candidate_id": cluster.get("candidate_id"),
                "proposal_type": proposal_type,
                "review_score": cluster.get("review_score", {}),
                "review_recommendation": cluster.get("review_recommendation", {}),
                "required_human_fields": (
                    ["subject", "predicate", "object", "scope", "confidence"]
                    if proposal_type in {"fact", "preference"}
                    else ["name", "trigger_context", "step", "scope", "confidence"]
                ),
                "safe_evidence": {
                    "evidence_trace_ids": cluster.get("evidence_trace_ids", []),
                    "evidence_trace_count": len(cluster.get("evidence_trace_ids", []) if isinstance(cluster.get("evidence_trace_ids"), list) else []),
                    "related_memory_refs": cluster.get("related_memory_refs", []),
                    "related_memory_count": len(cluster.get("related_memory_refs", []) if isinstance(cluster.get("related_memory_refs"), list) else []),
                    "related_observation_ids": cluster.get("related_observation_ids", []),
                    "related_observation_count": len(cluster.get("related_observation_ids", []) if isinstance(cluster.get("related_observation_ids"), list) else []),
                    "raw_content_included": False,
                },
                "classification_signals": {
                    "guessed_memory_type": guessed_type,
                    "proposal_type": proposal_type,
                    "has_related_memory": bool(cluster.get("related_memory_refs")),
                    "has_observations": bool(cluster.get("related_observation_ids")),
                },
                "quality_annotations": {
                    "confidence_band": "reviewable" if cluster.get("review_score") else "needs_more_evidence",
                    "missing_human_fields": (
                        ["subject", "predicate", "object", "scope", "confidence"]
                        if proposal_type in {"fact", "preference"}
                        else ["name", "trigger_context", "step", "scope", "confidence"]
                    ),
                    "auto_promotion_allowed": False,
                },
                "promotion_template": (
                    {"promotion_type": proposal_type, "subject": None, "predicate": None, "object": None, "scope": "global", "confidence": 0.7}
                    if proposal_type in {"fact", "preference"}
                    else {"promotion_type": proposal_type, "name": None, "trigger_context": None, "precondition": [], "step": [], "scope": "global", "confidence": 0.7}
                ),
                "next_review_command": "agent-memory dogfood trace-candidate-update ... --promotion-type " + proposal_type,
            }
        )
    payload = {
        "kind": "dogfood_trace_candidate_generate",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "generation_mode": "automatic_graph_cluster_to_reviewed_candidate_skeletons",
        "candidate_count": len(generated),
        "generated_candidates": generated,
        "automation_policy": {
            "ordinary_conversation_auto_approval": False,
            "promotion_supported_without_human_fields": False,
            "raw_content_allowed": False,
        },
        "quality_gate": preview.get("quality_gate", {}),
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_retrieval_ranking_gate_payload(args: argparse.Namespace) -> dict[str, Any]:
    result = evaluate_retrieval_fixtures(
        args.db_path,
        args.fixtures,
        baseline_mode=args.baseline_mode,
        fail_on_regression=False,
        fail_on_baseline_regression=False,
    )
    data = result.model_dump(mode="json")
    summary = data.get("summary", {}) if isinstance(data, dict) else {}
    failed_count = _safe_int(summary.get("failed_count", 0))
    pass_marker = summary.get("pass", summary.get("pass_"))
    pass_value = failed_count == 0 if pass_marker is None else bool(pass_marker)
    if not summary and isinstance(data, dict):
        results = data.get("results", []) or []
        failed_count = sum(1 for item in results if isinstance(item, dict) and not bool(item.get("pass", item.get("pass_", False))))
        pass_value = failed_count == 0
    baseline_regression_count = _safe_int((data.get("baseline_summary", {}) or {}).get("regression_count", 0)) if isinstance(data, dict) else 0
    blocked_reasons: list[str] = []
    if not pass_value or failed_count > 0:
        blocked_reasons.append("retrieval_eval_failures_present")
    if baseline_regression_count > args.max_baseline_regressions:
        blocked_reasons.append("baseline_regression_threshold_exceeded")
    payload = {
        "kind": "dogfood_retrieval_ranking_gate",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "ranking_change_allowed": not blocked_reasons,
        "blocked_reasons": blocked_reasons,
        "eval_summary": summary,
        "baseline_regression_count": baseline_regression_count,
        "max_baseline_regressions": args.max_baseline_regressions,
        "policy": "ranking changes require passing retrieval eval gate before implementation",
    }
    _write_json_report(args.output, payload)
    return payload


def _fixture_tasks_for_preview(fixtures_path: Path) -> list[dict[str, Any]]:
    data = json.loads(fixtures_path.read_text())
    tasks = data.get("tasks", []) if isinstance(data, dict) else []
    return [task for task in tasks if isinstance(task, dict)]


def _retrieval_fixture_expansion_summary(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    source_counts = Counter(str(task.get("source") or "unspecified") for task in tasks)
    live_compatible_count = sum(
        1
        for task in tasks
        if bool(task.get("preferred_scope"))
        and isinstance(task.get("expected"), dict)
        and any(task["expected"].get(key) for key in ("facts", "procedures", "episodes"))
    )
    return {
        "task_count": len(tasks),
        "live_compatible_task_count": live_compatible_count,
        "scoped_task_count": sum(1 for task in tasks if bool(task.get("preferred_scope"))),
        "has_rationale_count": sum(1 for task in tasks if bool(task.get("rationale") or task.get("notes"))),
        "fixture_source_counts": {key: source_counts[key] for key in sorted(source_counts)},
        "live_runtime_safe": True,
    }


RANKING_POLICIES = ("conservative_legacy", "graph_reinforced_v1", "shadow_compare")
RANKING_DEFAULT_POLICY = "conservative_legacy"
RANKING_MIGRATION_APPROVAL_PHRASE = "migrate-retrieval-ranking-default-v1"
PROTECTED_RANKING_MIGRATION_TABLES = (
    "facts",
    "procedures",
    "episodes",
    "relations",
    "memory_status_transitions",
    "g5_trace_candidate_reviews",
    "g4_review_queue_items",
    "g4_review_queue_applications",
)


def _ranking_policy_or_default(args: argparse.Namespace) -> str:
    policy = str(getattr(args, "ranking_policy", None) or RANKING_DEFAULT_POLICY)
    if policy not in RANKING_POLICIES:
        raise ValueError(f"unsupported ranking policy: {policy}")
    return policy


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return bool(
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    )


def _protected_table_hashes(db_path: Path) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        for table in PROTECTED_RANKING_MIGRATION_TABLES:
            if not _table_exists(connection, table):
                hashes[table] = {"exists": False, "row_count": 0, "sha256": None}
                continue
            rows = [dict(row) for row in connection.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
            encoded = json.dumps(rows, sort_keys=True, default=str).encode("utf-8")
            hashes[table] = {
                "exists": True,
                "row_count": len(rows),
                "sha256": hashlib.sha256(encoded).hexdigest(),
            }
    return hashes


def _read_ranking_policy_from_config(config_path: Path) -> str:
    if not config_path.exists():
        return RANKING_DEFAULT_POLICY
    for line in config_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("retrieval_ranking_policy:"):
            value = stripped.split(":", 1)[1].strip().strip('"\'')
            if value in RANKING_POLICIES:
                return value
    return RANKING_DEFAULT_POLICY


def _write_ranking_policy_to_config(config_path: Path, policy: str) -> None:
    original = config_path.read_text(encoding="utf-8") if config_path.exists() else "agent_memory:\n"
    lines = original.splitlines()
    replaced = False
    new_lines: list[str] = []
    for line in lines:
        if line.strip().startswith("retrieval_ranking_policy:"):
            indent = line[: len(line) - len(line.lstrip())]
            new_lines.append(f"{indent}retrieval_ranking_policy: {policy}")
            replaced = True
        else:
            new_lines.append(line)
    if not replaced:
        if not new_lines:
            new_lines.append("agent_memory:")
        if not any(line.strip() == "agent_memory:" for line in new_lines):
            new_lines.extend(["", "agent_memory:"])
        new_lines.append(f"  retrieval_ranking_policy: {policy}")
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")


def _dogfood_retrieval_ranking_experiment_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_policy = _ranking_policy_or_default(args)
    shadow_compare_requested = bool(getattr(args, "shadow_compare", False)) or candidate_policy == "shadow_compare"
    gate = _dogfood_retrieval_ranking_gate_payload(
        argparse.Namespace(
            db_path=args.db_path,
            fixtures=args.fixtures,
            baseline_mode=args.baseline_mode,
            max_baseline_regressions=args.max_baseline_regressions,
            output=None,
        )
    )
    previews: list[dict[str, Any]] = []
    fixture_tasks = _fixture_tasks_for_preview(args.fixtures)
    if gate["ranking_change_allowed"]:
        for task in fixture_tasks[: args.max_tasks]:
            query = str(task.get("query") or "")
            if not query:
                continue
            previews.append(
                _retrieval_ranker_preview(
                    args.db_path,
                    query=query,
                    limit=_safe_int(task.get("limit", args.limit)) or args.limit,
                    preferred_scope=task.get("preferred_scope"),
                    reinforcement_weight=args.reinforcement_weight,
                    reinforcement_cap=args.reinforcement_cap,
                )
            )
    rank_change_count = sum(len(preview.get("rank_changes", [])) for preview in previews)
    fixture_expansion = _retrieval_fixture_expansion_summary(fixture_tasks)
    fixture_gate_comparison = {
        "comparison_mode": "expanded_fixtures_vs_current_default_read_only",
        "baseline_mode": args.baseline_mode or "current_default",
        "active_ranking_policy": RANKING_DEFAULT_POLICY,
        "candidate_ranking_policy": candidate_policy,
        "fixture_task_count": fixture_expansion["task_count"],
        "expanded_fixture_gate_met": fixture_expansion["task_count"] >= 50,
        "eval_gate_pass": bool(gate.get("ranking_change_allowed")),
        "baseline_regression_count": gate.get("baseline_regression_count", 0),
        "max_baseline_regressions": gate.get("max_baseline_regressions", 0),
        "previewed_task_count": len(previews),
        "rank_change_count": rank_change_count,
        "default_ranking_mutated": False,
        "ordinary_conversation_auto_enable": False,
    }
    shadow_compare = {
        "mode": "legacy_returned_candidate_compared" if shadow_compare_requested else "not_requested",
        "active_ranking_policy": RANKING_DEFAULT_POLICY,
        "candidate_ranking_policy": candidate_policy,
        "protected_default_order_returned": True,
        "candidate_preview_count": len(previews),
        "candidate_rank_change_count": rank_change_count,
        "baseline_regression_count": gate.get("baseline_regression_count", 0),
        "requires_zero_baseline_regressions": True,
        "durable_memory_mutated": False,
    }
    payload = {
        "kind": "dogfood_retrieval_ranking_experiment",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "active_ranking_policy": RANKING_DEFAULT_POLICY,
        "candidate_ranking_policy": candidate_policy,
        "experiment_mode": "eval_gated_opt_in_ranker_preview_only",
        "gate": gate,
        "preview_count": len(previews),
        "rank_change_count": rank_change_count,
        "previews": previews,
        "fixture_expansion": fixture_expansion,
        "fixture_gate_comparison": fixture_gate_comparison,
        "shadow_compare": shadow_compare,
        "promotion_policy": {
            "default_ranking_mutated": False,
            "requires_gate_pass": True,
            "requires_live_e2e_before_default": True,
            "requires_shadow_compare": True,
            "migration_command_required": True,
            "ordinary_conversation_auto_enable": False,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_retrieval_ranking_migrate_default_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy = str(args.policy)
    if policy not in ("conservative_legacy", "graph_reinforced_v1"):
        raise ValueError("retrieval-ranking-migrate-default policy must be conservative_legacy or graph_reinforced_v1")
    if args.approval_phrase != RANKING_MIGRATION_APPROVAL_PHRASE:
        raise ValueError(f"approval phrase must be {RANKING_MIGRATION_APPROVAL_PHRASE}")
    if not args.actor.strip():
        raise ValueError("actor is required")
    if not args.reason.strip():
        raise ValueError("reason is required")

    before_hashes = _protected_table_hashes(args.db_path)
    gate = _dogfood_retrieval_ranking_gate_payload(
        argparse.Namespace(
            db_path=args.db_path,
            fixtures=args.fixtures,
            baseline_mode=getattr(args, "baseline_mode", None),
            max_baseline_regressions=getattr(args, "max_baseline_regressions", 0),
            output=None,
        )
    )
    if not gate.get("ranking_change_allowed"):
        raise ValueError("retrieval ranking migration blocked by retrieval-ranking-gate")

    shadow = _dogfood_retrieval_ranking_experiment_payload(
        argparse.Namespace(
            db_path=args.db_path,
            fixtures=args.fixtures,
            baseline_mode=getattr(args, "baseline_mode", None),
            max_baseline_regressions=getattr(args, "max_baseline_regressions", 0),
            max_tasks=getattr(args, "max_tasks", 5),
            limit=getattr(args, "limit", 5),
            reinforcement_weight=getattr(args, "reinforcement_weight", 1.5),
            reinforcement_cap=getattr(args, "reinforcement_cap", 1.0),
            ranking_policy=policy,
            shadow_compare=True,
            output=None,
        )
    )
    policy_before = _read_ranking_policy_from_config(args.config_path)
    _write_ranking_policy_to_config(args.config_path, policy)
    after_hashes = _protected_table_hashes(args.db_path)
    protected_unchanged = before_hashes == after_hashes
    payload = {
        "kind": "dogfood_retrieval_ranking_migrate_default",
        "read_only": False,
        "mutated": policy_before != policy,
        "mutation_scope": "config_only",
        "db_mutated": False,
        "default_retrieval_unchanged": policy == RANKING_DEFAULT_POLICY,
        "policy_before": policy_before,
        "policy_after": policy,
        "config_path": str(args.config_path),
        "actor": args.actor,
        "reason_sha256": hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest(),
        "retrieval_gate": gate,
        "shadow_compare": shadow.get("shadow_compare", {}),
        "rollback_replay_gate": {
            "protected_durable_tables_unchanged": protected_unchanged,
            "protected_tables": sorted(before_hashes),
            "before_hashes": before_hashes,
            "after_hashes": after_hashes,
            "rollback_policy": RANKING_DEFAULT_POLICY,
        },
        "rollback_command": {
            "dogfood_action": "retrieval-ranking-migrate-default",
            "db_path": str(args.db_path),
            "fixtures": str(args.fixtures),
            "config_path": str(args.config_path),
            "policy": RANKING_DEFAULT_POLICY,
            "approval_phrase": RANKING_MIGRATION_APPROVAL_PHRASE,
        },
        "safety_exclusions": {
            "broad_g4_apply_enabled": False,
            "ordinary_conversation_auto_approval": False,
            "collapse_delete_apply_enabled": False,
            "raw_prompt_or_query_storage_enabled": False,
        },
    }
    if not protected_unchanged:
        raise ValueError("protected durable memory tables changed during config-only ranking migration")
    _write_json_report(getattr(args, "audit_output", None), payload)
    _write_json_report(getattr(args, "output", None), payload)
    return payload


def _dogfood_decay_collapse_decision_payload(args: argparse.Namespace) -> dict[str, Any]:
    preview = _dogfood_decay_collapse_preview_payload(args)
    candidate_count = _safe_int(preview.get("candidate_count", 0))
    accepted_evidence = [
        "rollback_replay_validate_pass",
        "relation_equivalence_or_supersession_chain",
        "retrieval_eval_gate_pass",
        "human_reviewed_candidate_payload",
    ]
    replay_payload = _dogfood_rollback_replay_validate_payload(
        argparse.Namespace(db_path=args.db_path, limit=50, output=None)
    )
    fixtures = getattr(args, "fixtures", None)
    if fixtures:
        ranking_gate = _dogfood_retrieval_ranking_gate_payload(
            argparse.Namespace(
                db_path=args.db_path,
                fixtures=fixtures,
                baseline_mode=getattr(args, "baseline_mode", None),
                max_baseline_regressions=getattr(args, "max_baseline_regressions", 0),
                output=None,
            )
        )
        retrieval_eval_status = {
            "passed": bool(ranking_gate.get("ranking_change_allowed")),
            "source": "dogfood_retrieval_ranking_gate.ranking_change_allowed",
            "blocked_reasons": ranking_gate.get("blocked_reasons", []),
        }
    else:
        retrieval_eval_status = {
            "passed": None,
            "source": "dogfood_retrieval_ranking_gate.ranking_change_allowed",
            "skipped_reason": "fixtures_not_provided",
        }

    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        decay_review_rows = connection.execute(
            """
            SELECT candidate_id, target_ref, reviewed_json
            FROM g5_trace_candidate_reviews
            WHERE candidate_kind = 'decay'
              AND proposal_type = 'decay_review'
              AND status IN ('approved', 'promoted')
            ORDER BY updated_at DESC, candidate_id
            """
        ).fetchall()
        decay_review_count = len(decay_review_rows)
        supersession_review_count = _safe_int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM g5_trace_candidate_reviews
                WHERE candidate_kind = 'supersession'
                  AND proposal_type = 'supersession_review'
                  AND status IN ('approved', 'promoted')
                """
            ).fetchone()[0]
        )

    candidate_proof_items: list[dict[str, Any]] = []
    missing_artifact_candidate_ids: list[str] = []
    green_artifact_count = 0
    replacement_relation_evidence_count = 0
    for row in decay_review_rows:
        reviewed = _safe_json_dict_from_db(row["reviewed_json"])
        artifact = _collapse_proof_artifact_from_reviewed(reviewed)
        artifact_status = _collapse_proof_status_from_artifact(artifact) if artifact else "missing"
        replacement_relation_count = 0
        target_ref = str(row["target_ref"] or "")
        if target_ref.startswith("fact:"):
            replacement_relation_count = len(
                list_fact_replacement_relations(args.db_path, fact_id=_fact_id_from_ref(target_ref))
            )
            replacement_relation_evidence_count += replacement_relation_count
        if not artifact:
            missing_artifact_candidate_ids.append(row["candidate_id"])
        elif artifact_status == "satisfied":
            green_artifact_count += 1
        candidate_proof_items.append(
            {
                "candidate_id": row["candidate_id"],
                "target_ref": row["target_ref"],
                "artifact_present": bool(artifact),
                "current_status": artifact_status,
                "missing_evidence": artifact.get("missing_evidence", []) if artifact else ["collapse_proof_artifact"],
                "replacement_relation_evidence_count": replacement_relation_count,
                "collapse_apply_allowed": bool(artifact.get("collapse_apply_allowed", False)) if artifact else False,
                "delete_apply_allowed": bool(artifact.get("delete_apply_allowed", False)) if artifact else False,
            }
        )
    artifact_count = decay_review_count - len(missing_artifact_candidate_ids)
    all_candidate_artifacts_green = decay_review_count > 0 and artifact_count == decay_review_count and green_artifact_count == decay_review_count
    candidate_proof_replay = {
        "reviewed_decay_candidate_count": decay_review_count,
        "artifact_count": artifact_count,
        "green_artifact_count": green_artifact_count,
        "all_candidate_artifacts_green": all_candidate_artifacts_green,
        "missing_artifact_candidate_ids": missing_artifact_candidate_ids,
        "items": candidate_proof_items,
    }

    evidence_status: dict[str, dict[str, Any]] = {
        "rollback_replay_validate_pass": {
            "passed": bool((replay_payload.get("quality_gate") or {}).get("pass")),
            "source": "dogfood_rollback_replay_validate.quality_gate.pass",
            "checked_application_count": (replay_payload.get("rollup") or {}).get("checked_application_count", 0),
        },
        "relation_equivalence_or_supersession_chain": {
            "passed": supersession_review_count > 0 or replacement_relation_evidence_count > 0,
            "source": "approved_supersession_candidate_or_existing_supersession_relation",
            "approved_supersession_candidate_count": supersession_review_count,
            "replacement_relation_evidence_count": replacement_relation_evidence_count,
            "green_collapse_proof_artifact_count": green_artifact_count,
        },
        "retrieval_eval_gate_pass": retrieval_eval_status,
        "human_reviewed_candidate_payload": {
            "passed": decay_review_count > 0,
            "source": "g5_trace_candidate_reviews approved decay candidate proof replay",
            "approved_decay_candidate_count": decay_review_count,
            "candidate_proof_artifact_count": artifact_count,
        },
    }
    missing_evidence = [
        key
        for key in accepted_evidence
        if evidence_status.get(key, {}).get("passed") is not True
    ]
    green_evidence_count = len(accepted_evidence) - len(missing_evidence)
    current_status = (
        "satisfied"
        if not missing_evidence
        else "partially_satisfied"
        if green_evidence_count > 0
        else "not_satisfied"
    )
    payload = {
        "kind": "dogfood_decay_collapse_decision",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "candidate_count": candidate_count,
        "preview_quality_gate": preview.get("quality_gate", {}),
        "decision": {
            "deprecate_corridor": "supported_for_reviewed_approved_decay_candidates",
            "collapse_corridor": "blocked_until_restore_replay_and_relation_equivalence_are_green",
            "delete_corridor": "blocked_no_delete_apply_path",
            "broader_background_apply": "blocked",
        },
        "allowed_next_policy": "g5-lifecycle-decay-deprecate-apply-v1",
        "blocked_policies": ["g5-lifecycle-collapse-apply-v1", "g5-lifecycle-delete-apply-v1"],
        "required_evidence_before_collapse": accepted_evidence,
        "collapse_equivalence_proof": {
            "proof_required": True,
            "accepted_evidence": accepted_evidence,
            "evidence_status": evidence_status,
            "green_evidence_count": green_evidence_count,
            "required_evidence_count": len(accepted_evidence),
            "missing_evidence": missing_evidence,
            "current_status": current_status,
            "candidate_proof_replay": candidate_proof_replay,
            "collapse_apply_allowed": False,
            "delete_apply_allowed": False,
        },
        "privacy": {"raw_content_included": False, "sample_values_included": False},
    }
    _write_json_report(args.output, payload)
    return payload


def _fresh_epoch_comparison_evidence_from_report(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {
            "provided": False,
            "path": None,
            "report_sha256": None,
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "not_provided",
            "quality_gate_blocked_reasons": [],
            "report_count": 0,
            "quality_gate_pass_count": 0,
            "trace_coverage_ratio_min": 0.0,
            "empty_retrieval_ratio_max": 0.0,
            "unknown_empty_outcome_count_total": 0,
            "unresolved_unknown_empty_outcome_count_total": 0,
            "classified_missing_outcome_count_total": 0,
            "metadata_dominant_blocker_counts": {},
            "privacy_flags": {},
            "usable_for_reset_avoidance": False,
            "error": None,
        }
    report_path = path.expanduser().resolve(strict=False)
    try:
        raw_text = report_path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except Exception as exc:
        return {
            "provided": True,
            "path": str(report_path),
            "report_sha256": None,
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "unreadable",
            "quality_gate_blocked_reasons": ["report_unreadable"],
            "report_count": 0,
            "quality_gate_pass_count": 0,
            "trace_coverage_ratio_min": 0.0,
            "empty_retrieval_ratio_max": 0.0,
            "unknown_empty_outcome_count_total": 0,
            "unresolved_unknown_empty_outcome_count_total": 0,
            "classified_missing_outcome_count_total": 0,
            "metadata_dominant_blocker_counts": {},
            "privacy_flags": {},
            "usable_for_reset_avoidance": False,
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(raw, dict):
        return {
            "provided": True,
            "path": str(report_path),
            "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "invalid",
            "quality_gate_blocked_reasons": ["report_not_json_object"],
            "report_count": 0,
            "quality_gate_pass_count": 0,
            "trace_coverage_ratio_min": 0.0,
            "empty_retrieval_ratio_max": 0.0,
            "unknown_empty_outcome_count_total": 0,
            "unresolved_unknown_empty_outcome_count_total": 0,
            "classified_missing_outcome_count_total": 0,
            "metadata_dominant_blocker_counts": {},
            "privacy_flags": {},
            "usable_for_reset_avoidance": False,
            "error": None,
        }

    quality_gate = raw.get("quality_gate", {}) if isinstance(raw.get("quality_gate"), dict) else {}
    aggregate = raw.get("aggregate", {}) if isinstance(raw.get("aggregate"), dict) else {}
    privacy = raw.get("privacy", {}) if isinstance(raw.get("privacy"), dict) else {}
    privacy_flags = {
        "raw_conversation_content_included": privacy.get("raw_conversation_content_included") is True,
        "sample_values_included": privacy.get("sample_values_included") is True,
        "raw_query_text_included": privacy.get("raw_query_text_included") is True,
        "raw_trace_summary_included": privacy.get("raw_trace_summary_included") is True,
        "raw_report_included": privacy.get("raw_report_included") is True,
    }
    blocked_reasons = (
        quality_gate.get("blocked_reasons", []) if isinstance(quality_gate.get("blocked_reasons"), list) else []
    )
    kind = raw.get("kind")
    read_only = raw.get("read_only")
    mutated = raw.get("mutated")
    default_unchanged = raw.get("default_retrieval_unchanged")
    quality_pass = quality_gate.get("pass") is True
    unresolved = _safe_int(aggregate.get("unresolved_unknown_empty_outcome_count_total"))
    usable = bool(
        kind == "dogfood_fresh_epoch_comparison"
        and read_only is True
        and mutated is False
        and default_unchanged is True
        and quality_pass
        and unresolved == 0
        and not any(privacy_flags.values())
    )
    metadata_blockers = aggregate.get("metadata_dominant_blocker_counts", {})
    if not isinstance(metadata_blockers, dict):
        metadata_blockers = {}
    return {
        "provided": True,
        "path": str(report_path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "kind": kind,
        "read_only": read_only,
        "mutated": mutated,
        "default_retrieval_unchanged": default_unchanged,
        "quality_gate_pass": quality_pass,
        "quality_gate_decision": str(quality_gate.get("decision", "unknown")),
        "quality_gate_blocked_reasons": sorted(str(reason) for reason in blocked_reasons if reason),
        "report_count": _safe_int(raw.get("report_count")),
        "quality_gate_pass_count": _safe_int(aggregate.get("quality_gate_pass_count")),
        "trace_coverage_ratio_min": round(_safe_float(aggregate.get("trace_coverage_ratio_min")), 4),
        "empty_retrieval_ratio_max": round(_safe_float(aggregate.get("empty_retrieval_ratio_max")), 4),
        "unknown_empty_outcome_count_total": _safe_int(aggregate.get("unknown_empty_outcome_count_total")),
        "unresolved_unknown_empty_outcome_count_total": unresolved,
        "classified_missing_outcome_count_total": _safe_int(aggregate.get("classified_missing_outcome_count_total")),
        "metadata_dominant_blocker_counts": {str(key): _safe_int(value) for key, value in metadata_blockers.items()},
        "privacy_flags": privacy_flags,
        "usable_for_reset_avoidance": usable,
        "error": None,
    }


def _dogfood_telemetry_reconciliation_payload(args: argparse.Namespace) -> dict[str, Any]:
    fresh = _dogfood_fresh_epoch_payload(
        argparse.Namespace(
            db_path=args.db_path,
            epoch_start=args.epoch_start,
            output=None,
            min_trace_coverage=args.min_trace_coverage,
            min_evidence_count=args.min_evidence_count,
            high_empty_threshold=args.high_empty_threshold,
        )
    )
    reset_preview = _dogfood_telemetry_reset_preview_payload(
        argparse.Namespace(db_path=args.db_path, epoch_start=args.epoch_start, output=None)
    )
    fresh_quality_gate = fresh.get("quality_gate", {}) if isinstance(fresh.get("quality_gate"), dict) else {}
    fresh_comparison_evidence = _fresh_epoch_comparison_evidence_from_report(
        getattr(args, "fresh_epoch_comparison_report", None)
    )
    blocked_reasons: list[str] = []
    if reset_preview.get("candidate_delete_total") is None:
        blocked_reasons.append("telemetry_reset_preview_unavailable")
    if fresh_quality_gate.get("pass") is not True:
        blocked_reasons.append("fresh_epoch_quality_gate_not_green")
    if not fresh_comparison_evidence["provided"]:
        blocked_reasons.append("fresh_epoch_comparison_not_provided")
    elif not fresh_comparison_evidence["usable_for_reset_avoidance"]:
        blocked_reasons.append("fresh_epoch_comparison_not_green")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_telemetry_reconciliation",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "reconciliation_mode": "historical_telemetry_only_corridor",
        "fresh_epoch_quality_gate": fresh_quality_gate,
        "fresh_epoch_comparison_evidence": fresh_comparison_evidence,
        "telemetry_reset_preview": {
            "candidate_delete_total": reset_preview.get("candidate_delete_total"),
            "candidate_delete_by_table": reset_preview.get("candidate_delete_by_table"),
            "protected_memory_tables_mutated": False,
            "warnings": reset_preview.get("warnings", []),
        },
        "apply_corridor": {
            "supported_command": "dogfood telemetry-reset-apply",
            "policy": "telemetry-reset-v1",
            "approval_phrase": "apply-telemetry-reset-v1",
            "protected_memory_tables_mutated": False,
            "ordinary_conversation_auto_apply": False,
            "telemetry_reset_apply_supported": False,
            "safety_gate": {
                "fresh_epoch_gate_required": True,
                "fresh_epoch_comparison_required_for_live_apply": True,
                "backup_required": True,
                "post_apply_preview_required": True,
                "rollback_restore_replay_required_before_broad_g4": True,
                "protected_table_count_verification_required": True,
            },
        },
        "quality_gate": {
            "pass": passed,
            "decision": "telemetry_only_reconciliation_ready_for_manual_apply"
            if passed
            else "continue_fresh_epoch_collection_before_telemetry_reconciliation_apply",
            "blocked_reasons": blocked_reasons,
        },
        "privacy": {
            "raw_content_included": False,
            "raw_query_text_included": False,
            "sample_values_included": False,
            "raw_report_included": False,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_rollback_confidence_payload(args: argparse.Namespace) -> dict[str, Any]:
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_lifecycle_candidate_review_tables(connection)
        rows = connection.execute(
            """
            SELECT candidate_id, proposal_type, promoted_ref, policy, action, backup_path, backup_sha256, rollback_hint_json, created_at
            FROM g5_trace_candidate_applications
            ORDER BY id DESC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()
    applications = []
    for row in rows:
        confidence = _rollback_confidence_for_backup(row["backup_path"], row["backup_sha256"])
        applications.append(
            {
                "candidate_id": row["candidate_id"],
                "proposal_type": row["proposal_type"],
                "policy": row["policy"],
                "action": row["action"],
                "promoted_ref": row["promoted_ref"],
                "created_at": row["created_at"],
                "rollback_hint": _safe_json_dict_from_db(row["rollback_hint_json"]),
                "rollback_confidence": confidence,
            }
        )
    blocked_reasons = []
    if any(not app["rollback_confidence"]["backup_exists"] for app in applications):
        blocked_reasons.append("missing_backup")
    if any(not app["rollback_confidence"]["backup_sha256_matches"] for app in applications):
        blocked_reasons.append("backup_checksum_mismatch")
    payload = {
        "kind": "dogfood_rollback_confidence",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "application_count": len(applications),
        "applications": applications,
        "quality_gate": {
            "pass": not blocked_reasons,
            "blocked_reasons": blocked_reasons,
            "decision": "rollback_confidence_sufficient_for_bounded_partial_automation" if not blocked_reasons else "fix_rollback_evidence_before_broader_automation",
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_trace_candidate_persist_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood trace-candidate-persist requires non-empty --actor and --reason")
    preview = _dogfood_trace_cluster_preview_payload(
        argparse.Namespace(
            db_path=args.db_path,
            output=None,
            limit=args.limit,
            top=args.top,
            min_evidence_count=args.min_evidence_count,
        )
    )
    source_preview_sha256 = hashlib.sha256(json.dumps(preview, sort_keys=True).encode("utf-8")).hexdigest()
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    inserted = 0
    existing = 0
    candidate_ids: list[str] = []
    clusters = preview.get("clusters", []) if isinstance(preview.get("clusters"), list) else []
    with sqlite3.connect(args.db_path) as connection:
        _ensure_trace_candidate_review_tables(connection)
        for cluster in clusters:
            if not isinstance(cluster, dict):
                continue
            candidate_id = str(cluster.get("candidate_id") or "")
            if not candidate_id:
                continue
            candidate_ids.append(candidate_id)
            target_refs = cluster.get("related_memory_refs") if isinstance(cluster.get("related_memory_refs"), list) else []
            target_ref = str(target_refs[0]) if target_refs else None
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO g5_trace_candidate_reviews (
                    candidate_id, status, proposal_type, target_ref, cluster_json, cluster_sha256,
                    actor, reason_sha256, audit_json
                ) VALUES (?, 'pending', 'trace_cluster_review', ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    target_ref,
                    json.dumps(cluster, sort_keys=True),
                    source_preview_sha256,
                    args.actor.strip(),
                    reason_sha256,
                    json.dumps([{"action": "persist", "actor": args.actor.strip(), "reason_sha256": reason_sha256}]),
                ),
            )
            if connection.total_changes > before:
                inserted += 1
            else:
                existing += 1
    payload = {
        "kind": "dogfood_trace_candidate_persist",
        "read_only": False,
        "mutated": inserted > 0,
        "default_retrieval_unchanged": True,
        "candidate_persistence_supported": True,
        "promotion_supported": False,
        "db_path": str(args.db_path),
        "source_preview_sha256": source_preview_sha256,
        "candidate_count": len(candidate_ids),
        "candidate_ids": candidate_ids,
        "inserted_count": inserted,
        "existing_count": existing,
        "quality_gate": preview.get("quality_gate", {}),
        "privacy": {
            "cluster_json_included": False,
            "raw_content_included": False,
            "safe_summaries_included": False,
            "reason_stored_as_sha256": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_trace_candidate_list_payload(args: argparse.Namespace) -> dict[str, Any]:
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_trace_candidate_review_tables(connection)
        rows = connection.execute(
            """
            SELECT candidate_id, status, proposal_type, target_ref, cluster_sha256
            FROM g5_trace_candidate_reviews
            WHERE (? IS NULL OR status = ?)
            ORDER BY created_at DESC, candidate_id
            LIMIT ?
            """,
            (args.status, args.status, args.limit),
        ).fetchall()
    return {
        "kind": "dogfood_trace_candidate_list",
        "read_only": True,
        "mutated": False,
        "db_path": str(args.db_path),
        "count": len(rows),
        "items": [dict(row) for row in rows],
        "privacy": {
            "cluster_json_included": False,
            "reviewed_payload_included": False,
            "raw_content_included": False,
            "sample_values_included": False,
        },
    }


def _reviewed_promotion_payload_from_args(args: argparse.Namespace) -> dict[str, Any] | None:
    if args.promotion_type is None:
        return None
    if args.promotion_type in {"fact", "preference"}:
        if not args.subject or not args.predicate or not args.object:
            raise ValueError(
                "dogfood trace-candidate-update fact/preference promotion requires --subject, --predicate, and --object"
            )
        return {
            "promotion_type": args.promotion_type,
            "subject_ref": args.subject,
            "predicate": args.predicate,
            "object_ref_or_value": args.object,
            "scope": args.scope,
            "confidence": args.confidence,
            "evidence_ids": [],
        }
    if args.promotion_type == "procedure":
        if not args.name or not args.trigger_context or not args.step:
            raise ValueError(
                "dogfood trace-candidate-update procedure promotion requires --name, --trigger-context, and at least one --step"
            )
        return {
            "promotion_type": "procedure",
            "name": args.name,
            "trigger_context": args.trigger_context,
            "preconditions": list(args.precondition or []),
            "steps": list(args.step or []),
            "scope": args.scope,
            "success_rate": args.success_rate,
            "evidence_ids": [],
        }
    if args.promotion_type == "episode":
        if not args.title or not args.summary:
            raise ValueError("dogfood trace-candidate-update episode promotion requires --title and --summary")
        return {
            "promotion_type": "episode",
            "title": args.title,
            "summary": args.summary,
            "source_ids": [],
            "tags": list(args.tag or []),
            "scope": args.scope,
            "importance_score": args.importance_score,
        }
    raise ValueError("unsupported trace candidate promotion type")


def _dogfood_trace_candidate_update_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.status not in {"approved", "rejected"}:
        raise ValueError("dogfood trace-candidate-update status must be approved or rejected")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood trace-candidate-update requires non-empty --actor and --reason")
    expected_phrase = f"{args.status[:-1] if args.status.endswith('d') else args.status}-g5-trace-candidate-v1"
    if args.approval_phrase != expected_phrase:
        raise ValueError(f"dogfood trace-candidate-update requires --approval-phrase {expected_phrase}")
    reviewed_payload = _reviewed_promotion_payload_from_args(args)
    proposal_type = f"{reviewed_payload['promotion_type']}_promotion" if reviewed_payload is not None else "trace_cluster_review"
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_trace_candidate_review_tables(connection)
        row = connection.execute(
            "SELECT status, proposal_type, target_ref, audit_json FROM g5_trace_candidate_reviews WHERE candidate_id = ?",
            (args.candidate_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"trace candidate not found: {args.candidate_id}")
        status_before = row["status"]
        audit = _safe_json_list_from_db(row["audit_json"])
        audit.append({
            "action": args.status,
            "actor": args.actor.strip(),
            "reason_sha256": reason_sha256,
            "candidate_id": args.candidate_id,
            "status_before": status_before,
            "status_after": args.status,
            "proposal_type": proposal_type,
            "reviewed_payload_stored": reviewed_payload is not None,
        })
        connection.execute(
            """
            UPDATE g5_trace_candidate_reviews
            SET status = ?, proposal_type = ?, reviewed_json = ?, updated_at = CURRENT_TIMESTAMP,
                actor = ?, reason_sha256 = ?, audit_json = ?
            WHERE candidate_id = ?
            """,
            (
                args.status,
                proposal_type,
                json.dumps(reviewed_payload or {}, sort_keys=True),
                args.actor.strip(),
                reason_sha256,
                json.dumps(audit, sort_keys=True),
                args.candidate_id,
            ),
        )
    return {
        "kind": "dogfood_trace_candidate_update",
        "read_only": False,
        "mutated": status_before != args.status or proposal_type != row["proposal_type"],
        "default_retrieval_unchanged": True,
        "apply_supported": False,
        "candidate_id": args.candidate_id,
        "status_before": status_before,
        "status_after": args.status,
        "status": args.status,
        "proposal_type": proposal_type,
        "promotion_ready": args.status == "approved" and proposal_type in {"fact_promotion", "preference_promotion", "procedure_promotion", "episode_promotion"},
        "reason_sha256": reason_sha256,
        "privacy": {"reviewed_payload_included": False, "raw_reason_included": False, "raw_content_included": False},
    }


def _dogfood_trace_candidate_apply_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy = "g5-reviewed-candidate-promotion-v1"
    approval_phrase = "apply-approved-g5-reviewed-candidates-v1"
    if args.policy != policy:
        raise ValueError(f"dogfood trace-candidate-apply requires --policy {policy}")
    if args.approval_phrase != approval_phrase:
        raise ValueError(f"dogfood trace-candidate-apply requires --approval-phrase {approval_phrase}")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood trace-candidate-apply requires non-empty --actor and --reason")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")
    backup_path = args.backup_path.expanduser().resolve(strict=False) if args.backup_path else _default_backup_path(db_path, label="g5-trace-candidate-apply")
    backup = _create_sqlite_backup(db_path, backup_path)
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    candidate_filter = list(args.candidate_id or [])
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_trace_candidate_review_tables(connection)
        if candidate_filter:
            placeholders = ", ".join("?" for _ in candidate_filter)
            rows = connection.execute(
                f"SELECT * FROM g5_trace_candidate_reviews WHERE candidate_id IN ({placeholders}) ORDER BY candidate_id",
                tuple(candidate_filter),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM g5_trace_candidate_reviews WHERE status = 'approved' ORDER BY candidate_id"
            ).fetchall()
        found_ids = {row["candidate_id"] for row in rows}
        for missing in sorted(set(candidate_filter) - found_ids):
            skipped.append({"candidate_id": missing, "reason": "not_found"})

    for row in rows:
        candidate_id = row["candidate_id"]
        if row["status"] != "approved":
            skipped.append({"candidate_id": candidate_id, "reason": f"status_{row['status']}"})
            continue
        if row["proposal_type"] not in {"fact_promotion", "preference_promotion", "procedure_promotion", "episode_promotion"}:
            skipped.append({"candidate_id": candidate_id, "reason": f"proposal_type_{row['proposal_type']}"})
            continue
        with sqlite3.connect(db_path) as connection:
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                "SELECT promoted_ref FROM g5_trace_candidate_applications WHERE candidate_id = ? AND policy = ?",
                (candidate_id, policy),
            ).fetchone()
        reviewed = _safe_json_dict_from_db(row["reviewed_json"])
        promotion_type = str(reviewed.get("promotion_type") or "")
        action = f"promote_reviewed_{promotion_type}"
        if existing is not None:
            applied.append({"candidate_id": candidate_id, "action": action, "inserted": False, "promoted_ref": existing["promoted_ref"]})
            continue
        if promotion_type in {"fact", "preference"}:
            fact = create_candidate_fact(
                db_path=db_path,
                subject_ref=str(reviewed["subject_ref"]),
                predicate=str(reviewed["predicate"]),
                object_ref_or_value=str(reviewed["object_ref_or_value"]),
                evidence_ids=[int(value) for value in reviewed.get("evidence_ids", [])],
                scope=str(reviewed.get("scope") or "global"),
                confidence=float(reviewed.get("confidence") or 0.5),
            )
            approve_fact(db_path=db_path, fact_id=fact.id)
            promoted_ref = f"fact:{fact.id}"
        elif promotion_type == "procedure":
            procedure = create_candidate_procedure(
                db_path=db_path,
                name=str(reviewed["name"]),
                trigger_context=str(reviewed["trigger_context"]),
                preconditions=[str(value) for value in reviewed.get("preconditions", [])],
                steps=[str(value) for value in reviewed.get("steps", [])],
                evidence_ids=[int(value) for value in reviewed.get("evidence_ids", [])],
                scope=str(reviewed.get("scope") or "global"),
                success_rate=float(reviewed.get("success_rate") or 0.0),
            )
            approve_procedure(db_path=db_path, procedure_id=procedure.id)
            promoted_ref = f"procedure:{procedure.id}"
        elif promotion_type == "episode":
            episode = create_episode(
                db_path=db_path,
                title=str(reviewed["title"]),
                summary=str(reviewed["summary"]),
                source_ids=[int(value) for value in reviewed.get("source_ids", [])],
                tags=[str(value) for value in reviewed.get("tags", [])],
                importance_score=float(reviewed.get("importance_score") or 0.0),
                scope=str(reviewed.get("scope") or "global"),
                status="approved",
            )
            promoted_ref = f"episode:{episode.id}"
        else:
            skipped.append({"candidate_id": candidate_id, "reason": f"reviewed_payload_not_promotable_{promotion_type or 'missing'}"})
            continue
        rollback_hint = {
            "restore_backup_path": str(backup_path),
            "candidate_id": candidate_id,
            "policy": policy,
            "promoted_ref": promoted_ref,
            "default_retrieval_mutated": False,
        }
        with sqlite3.connect(db_path) as connection:
            _ensure_trace_candidate_review_tables(connection)
            connection.execute(
                """
                INSERT INTO g5_trace_candidate_applications (
                    candidate_id, proposal_type, promoted_ref, policy, action, actor, reason_sha256,
                    backup_path, backup_sha256, rollback_hint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate_id,
                    row["proposal_type"],
                    promoted_ref,
                    policy,
                    action,
                    args.actor.strip(),
                    reason_sha256,
                    str(backup_path),
                    backup["sha256"],
                    json.dumps(rollback_hint, sort_keys=True),
                ),
            )
            audit = _safe_json_list_from_db(row["audit_json"])
            audit.append({"action": "apply", "actor": args.actor.strip(), "policy": policy, "reason_sha256": reason_sha256, "promoted_ref": promoted_ref})
            connection.execute(
                "UPDATE g5_trace_candidate_reviews SET status = 'promoted', updated_at = CURRENT_TIMESTAMP, actor = ?, reason_sha256 = ?, audit_json = ? WHERE candidate_id = ?",
                (args.actor.strip(), reason_sha256, json.dumps(audit, sort_keys=True), candidate_id),
            )
        applied.append({"candidate_id": candidate_id, "action": action, "inserted": True, "promoted_ref": promoted_ref})

    payload = {
        "kind": "dogfood_trace_candidate_apply",
        "read_only": False,
        "mutated": any(item.get("inserted") for item in applied),
        "db_path": str(db_path),
        "policy": policy,
        "approval_phrase_matched": True,
        "actor": args.actor.strip(),
        "reason_sha256": reason_sha256,
        "backup": backup,
        "apply_mode": "approved_reviewed_trace_candidates_only",
        "applied_count": len([item for item in applied if item.get("inserted")]),
        "already_applied_count": len([item for item in applied if not item.get("inserted")]),
        "skipped_count": len(skipped),
        "applied_items": applied,
        "skipped_items": skipped,
        "memory_status_mutated": any(item.get("inserted") for item in applied),
        "default_retrieval_unchanged": True,
        "ordinary_conversation_auto_approval": False,
        "privacy": {
            "cluster_json_included": False,
            "reviewed_payload_included": False,
            "raw_content_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "raw_reason_included": False,
            "reason_stored_as_sha256": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _write_json_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _collect_background_quality_warnings(report: dict[str, Any]) -> list[str]:
    warnings: set[str] = set()
    scan = report.get("scan")
    if isinstance(scan, dict):
        warnings.update(str(warning) for warning in scan.get("quality_warnings", []) if warning)
    nested_reports = report.get("reports")
    if isinstance(nested_reports, dict):
        for nested in nested_reports.values():
            if isinstance(nested, dict):
                warnings.update(str(warning) for warning in nested.get("quality_warnings", []) if warning)
    return sorted(warnings)


def _background_dry_run_report_summary(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "path": str(path),
            "kind": None,
            "status": "unreadable",
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "candidate_count": 0,
            "reinforcement_candidate_count": 0,
            "decay_risk_candidate_count": 0,
            "activation_count": 0,
            "quality_warnings": ["report_unreadable"],
            "empty_retrieval_activation_diagnostics": {},
            "decay_risk_candidate_decomposition": {},
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(raw, dict):
        return {
            "path": str(path),
            "kind": None,
            "status": "invalid",
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "candidate_count": 0,
            "reinforcement_candidate_count": 0,
            "decay_risk_candidate_count": 0,
            "activation_count": 0,
            "quality_warnings": ["report_not_json_object"],
            "empty_retrieval_activation_diagnostics": {},
            "decay_risk_candidate_decomposition": {},
            "error": None,
        }

    reports = raw.get("reports") if isinstance(raw.get("reports"), dict) else {}
    handoff = raw.get("review_handoff") if isinstance(raw.get("review_handoff"), dict) else {}
    candidates = reports.get("candidates") if isinstance(reports.get("candidates"), dict) else {}
    activation_summary = reports.get("activation_summary") if isinstance(reports.get("activation_summary"), dict) else {}
    reinforcement = reports.get("reinforcement") if isinstance(reports.get("reinforcement"), dict) else {}
    decay_risk = reports.get("decay_risk") if isinstance(reports.get("decay_risk"), dict) else {}
    decay_candidates = decay_risk.get("decay_risk_candidates", []) if isinstance(decay_risk, dict) else []
    decay_count = len(decay_candidates) if isinstance(decay_candidates, list) else _safe_int(decay_candidates)

    return {
        "path": str(path),
        "kind": raw.get("kind"),
        "status": raw.get("status", "unknown"),
        "read_only": raw.get("read_only"),
        "mutated": raw.get("mutated"),
        "default_retrieval_unchanged": raw.get("default_retrieval_unchanged"),
        "candidate_count": _safe_int(handoff.get("candidate_count", candidates.get("candidate_count"))),
        "reinforcement_candidate_count": _safe_int(
            handoff.get("reinforcement_candidate_count", reinforcement.get("candidate_count"))
        ),
        "decay_risk_candidate_count": _safe_int(handoff.get("decay_risk_candidate_count", decay_count)),
        "activation_count": _safe_int(activation_summary.get("activation_count")),
        "quality_warnings": _collect_background_quality_warnings(raw),
        "empty_retrieval_activation_diagnostics": (
            activation_summary.get("empty_retrieval", {}) if isinstance(activation_summary.get("empty_retrieval"), dict) else {}
        ),
        "decay_risk_candidate_decomposition": (
            decay_risk.get("candidate_decomposition", {}) if isinstance(decay_risk.get("candidate_decomposition"), dict) else {}
        ),
        "error": None,
    }


def _scheduled_dry_run_quality_decision(
    *,
    storage_health: dict[str, Any],
    trace_quality: dict[str, Any],
    background_dry_run: dict[str, Any],
    candidate_min: int,
    max_decay_risk: int,
) -> dict[str, Any]:
    blocked_reasons: list[str] = []
    trace_recommendation = str(trace_quality.get("recommendation", "unknown"))
    trace_coverage = trace_quality.get("coverage", {}) if isinstance(trace_quality.get("coverage"), dict) else {}
    retrieval_quality = (
        trace_quality.get("retrieval_quality", {}) if isinstance(trace_quality.get("retrieval_quality"), dict) else {}
    )
    trace_warnings = trace_quality.get("warnings", []) if isinstance(trace_quality.get("warnings"), list) else []
    review_handoff = background_dry_run.get("review_handoff", {}) if isinstance(background_dry_run.get("review_handoff"), dict) else {}
    candidate_count = _safe_int(review_handoff.get("candidate_count"))
    decay_risk_candidate_count = _safe_int(review_handoff.get("decay_risk_candidate_count"))
    scan = background_dry_run.get("scan", {}) if isinstance(background_dry_run.get("scan"), dict) else {}
    quality_warnings = scan.get("quality_warnings", []) if isinstance(scan.get("quality_warnings"), list) else []

    if storage_health.get("status") not in {"ok", "pass", "healthy"}:
        blocked_reasons.append("storage_health_not_clean")
    if trace_recommendation != "consider_g4_plan":
        blocked_reasons.append("trace_quality_needs_more_dogfooding")
    if background_dry_run.get("status") != "completed":
        blocked_reasons.append("background_dry_run_not_completed")
    if candidate_count < candidate_min:
        blocked_reasons.append("candidate_signal_below_threshold")
    if decay_risk_candidate_count > max_decay_risk:
        blocked_reasons.append("decay_risk_above_threshold")
    if quality_warnings:
        blocked_reasons.append("background_quality_warnings_present")
    if background_dry_run.get("mutated") is True or storage_health.get("mutated") is True or trace_quality.get("mutated") is True:
        blocked_reasons.append("report_claims_mutation")
    if (
        background_dry_run.get("default_retrieval_unchanged") is False
        or storage_health.get("default_retrieval_unchanged") is False
        or trace_quality.get("default_retrieval_unchanged") is False
    ):
        blocked_reasons.append("default_retrieval_changed")

    blocker_diagnostics = {
        "trace_quality_needs_more_dogfooding": {
            "blocked": "trace_quality_needs_more_dogfooding" in blocked_reasons,
            "source": "reports.trace_quality",
            "recommendation": trace_recommendation,
            "coverage_ratio": round(_safe_float(trace_coverage.get("observation_trace_coverage_ratio")), 4),
            "empty_retrieval_ratio": round(_safe_float(retrieval_quality.get("empty_retrieval_ratio")), 4),
            "warnings": sorted(str(warning) for warning in trace_warnings if warning),
            "coverage_diagnostics": trace_quality.get("coverage_diagnostics", {}),
            "next_action": "Collect more metadata-only trace/activation evidence or lower only after a RED-tested plan.",
        },
        "decay_risk_above_threshold": {
            "blocked": "decay_risk_above_threshold" in blocked_reasons,
            "source": "reports.background_dry_run.review_handoff.decay_risk_candidate_count",
            "candidate_count": decay_risk_candidate_count,
            "max_allowed": max_decay_risk,
            "excess": max(0, decay_risk_candidate_count - max_decay_risk),
            "candidate_decomposition": (
                background_dry_run.get("reports", {}).get("decay_risk", {}).get("candidate_decomposition", {})
                if isinstance(background_dry_run.get("reports"), dict)
                and isinstance(background_dry_run.get("reports", {}).get("decay_risk"), dict)
                else {}
            ),
            "next_action": "Inspect aggregate decay-risk candidates and decide whether they are stale evidence or expected weak traces.",
        },
        "background_quality_warnings_present": {
            "blocked": "background_quality_warnings_present" in blocked_reasons,
            "source": "reports.background_dry_run.scan.quality_warnings",
            "warning_count": len(quality_warnings),
            "warnings": sorted(str(warning) for warning in quality_warnings if warning),
            "empty_retrieval_activation_diagnostics": (
                background_dry_run.get("reports", {}).get("activation_summary", {}).get("empty_retrieval", {})
                if isinstance(background_dry_run.get("reports"), dict)
                and isinstance(background_dry_run.get("reports", {}).get("activation_summary"), dict)
                else {}
            ),
            "next_action": "Resolve or classify each background warning before drafting any broad G4 apply contract.",
        },
    }

    passed = not blocked_reasons
    return {
        "pass": passed,
        "decision": (
            "scheduled_dry_run_quality_gate_passed_plan_g4_only"
            if passed
            else "continue_scheduled_dry_run_dogfooding_before_g4"
        ),
        "blocked_reasons": blocked_reasons,
        "blocker_diagnostics": blocker_diagnostics,
    }


def _scheduled_dry_run_report_summary(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except Exception as exc:
        return {
            "path": str(path),
            "report_sha256": None,
            "kind": None,
            "generated_at": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "unreadable",
            "blocked_reasons": ["report_unreadable"],
            "storage_health_status": "unknown",
            "trace_quality_recommendation": "unknown",
            "trace_coverage_ratio": 0.0,
            "empty_retrieval_ratio": 0.0,
            "background_status": "unknown",
            "candidate_count": 0,
            "reinforcement_candidate_count": 0,
            "decay_risk_candidate_count": 0,
            "background_quality_warnings": ["report_unreadable"],
            "safe_remember_intent_count": 0,
            "rejected_remember_intent_count": 0,
            "privacy_flags": {},
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(raw, dict):
        return {
            "path": str(path),
            "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "kind": None,
            "generated_at": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "invalid",
            "blocked_reasons": ["report_not_json_object"],
            "storage_health_status": "unknown",
            "trace_quality_recommendation": "unknown",
            "trace_coverage_ratio": 0.0,
            "empty_retrieval_ratio": 0.0,
            "background_status": "unknown",
            "candidate_count": 0,
            "reinforcement_candidate_count": 0,
            "decay_risk_candidate_count": 0,
            "background_quality_warnings": ["report_not_json_object"],
            "safe_remember_intent_count": 0,
            "rejected_remember_intent_count": 0,
            "privacy_flags": {},
            "error": None,
        }

    reports = raw.get("reports", {}) if isinstance(raw.get("reports"), dict) else {}
    storage_health = reports.get("storage_health", {}) if isinstance(reports.get("storage_health"), dict) else {}
    trace_quality = reports.get("trace_quality", {}) if isinstance(reports.get("trace_quality"), dict) else {}
    remember_intent = reports.get("remember_intent", {}) if isinstance(reports.get("remember_intent"), dict) else {}
    background = reports.get("background_dry_run", {}) if isinstance(reports.get("background_dry_run"), dict) else {}
    handoff = background.get("review_handoff", {}) if isinstance(background.get("review_handoff"), dict) else {}
    scan = background.get("scan", {}) if isinstance(background.get("scan"), dict) else {}
    quality_gate = raw.get("quality_gate", {}) if isinstance(raw.get("quality_gate"), dict) else {}
    trace_coverage = trace_quality.get("coverage", {}) if isinstance(trace_quality.get("coverage"), dict) else {}
    retrieval_quality = (
        trace_quality.get("retrieval_quality", {}) if isinstance(trace_quality.get("retrieval_quality"), dict) else {}
    )
    privacy = raw.get("privacy", {}) if isinstance(raw.get("privacy"), dict) else {}
    blocked_reasons = quality_gate.get("blocked_reasons", []) if isinstance(quality_gate.get("blocked_reasons"), list) else []
    background_quality_warnings = scan.get("quality_warnings", []) if isinstance(scan.get("quality_warnings"), list) else []

    return {
        "path": str(path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "kind": raw.get("kind"),
        "generated_at": raw.get("generated_at"),
        "read_only": raw.get("read_only"),
        "mutated": raw.get("mutated"),
        "default_retrieval_unchanged": raw.get("default_retrieval_unchanged"),
        "quality_gate_pass": quality_gate.get("pass") is True,
        "quality_gate_decision": str(quality_gate.get("decision", "unknown")),
        "blocked_reasons": sorted(str(reason) for reason in blocked_reasons if reason),
        "storage_health_status": str(storage_health.get("status", "unknown")),
        "trace_quality_recommendation": str(trace_quality.get("recommendation", "unknown")),
        "trace_coverage_ratio": round(_safe_float(trace_coverage.get("observation_trace_coverage_ratio")), 4),
        "empty_retrieval_ratio": round(_safe_float(retrieval_quality.get("empty_retrieval_ratio")), 4),
        "background_status": str(background.get("status", "unknown")),
        "candidate_count": _safe_int(handoff.get("candidate_count")),
        "reinforcement_candidate_count": _safe_int(handoff.get("reinforcement_candidate_count")),
        "decay_risk_candidate_count": _safe_int(handoff.get("decay_risk_candidate_count")),
        "background_quality_warnings": sorted(str(warning) for warning in background_quality_warnings if warning),
        "safe_remember_intent_count": _safe_int(remember_intent.get("safe_remember_intent_count")),
        "rejected_remember_intent_count": _safe_int(remember_intent.get("rejected_remember_intent_count")),
        "privacy_flags": {
            "raw_conversation_content_included": privacy.get("raw_conversation_content_included") is True,
            "sample_values_included": privacy.get("sample_values_included") is True,
            "raw_query_text_included": privacy.get("raw_query_text_included") is True,
        },
        "error": None,
    }


def _fresh_epoch_report_summary(path: Path) -> dict[str, Any]:
    try:
        raw_text = path.read_text(encoding="utf-8")
        raw = json.loads(raw_text)
    except Exception as exc:
        return {
            "path": str(path),
            "report_sha256": None,
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "epoch_started_at": None,
            "latest_created_at": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "unreadable",
            "blocked_reasons": ["report_unreadable"],
            "observation_count": 0,
            "trace_count": 0,
            "trace_coverage_ratio": 0.0,
            "empty_retrieval_ratio": 0.0,
            "unknown_empty_outcome_count": 0,
            "unresolved_unknown_empty_outcome_count": 0,
            "classified_missing_outcome_count": 0,
            "metadata_dominant_blocker": "unknown",
            "metadata_classification_confidence": "unknown",
            "privacy_flags": {},
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(raw, dict):
        return {
            "path": str(path),
            "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "epoch_started_at": None,
            "latest_created_at": None,
            "quality_gate_pass": False,
            "quality_gate_decision": "invalid",
            "blocked_reasons": ["report_not_json_object"],
            "observation_count": 0,
            "trace_count": 0,
            "trace_coverage_ratio": 0.0,
            "empty_retrieval_ratio": 0.0,
            "unknown_empty_outcome_count": 0,
            "unresolved_unknown_empty_outcome_count": 0,
            "classified_missing_outcome_count": 0,
            "metadata_dominant_blocker": "unknown",
            "metadata_classification_confidence": "unknown",
            "privacy_flags": {},
            "error": None,
        }

    epoch = raw.get("epoch", {}) if isinstance(raw.get("epoch"), dict) else {}
    coverage = raw.get("coverage", {}) if isinstance(raw.get("coverage"), dict) else {}
    empty = raw.get("empty_retrieval_diagnostics", {}) if isinstance(raw.get("empty_retrieval_diagnostics"), dict) else {}
    metadata_gap = empty.get("metadata_gap_diagnostic", {}) if isinstance(empty.get("metadata_gap_diagnostic"), dict) else {}
    unknown_drilldown = empty.get("unknown_outcome_drilldown", {}) if isinstance(empty.get("unknown_outcome_drilldown"), dict) else {}
    quality_gate = raw.get("quality_gate", {}) if isinstance(raw.get("quality_gate"), dict) else {}
    blocked_reasons = quality_gate.get("blocked_reasons", []) if isinstance(quality_gate.get("blocked_reasons"), list) else []
    privacy = raw.get("privacy", {}) if isinstance(raw.get("privacy"), dict) else {}
    return {
        "path": str(path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "kind": raw.get("kind"),
        "read_only": raw.get("read_only"),
        "mutated": raw.get("mutated"),
        "default_retrieval_unchanged": raw.get("default_retrieval_unchanged"),
        "epoch_started_at": epoch.get("started_at"),
        "latest_created_at": epoch.get("latest_created_at"),
        "quality_gate_pass": quality_gate.get("pass") is True,
        "quality_gate_decision": str(quality_gate.get("decision", "unknown")),
        "blocked_reasons": sorted(str(reason) for reason in blocked_reasons if reason),
        "observation_count": _safe_int(coverage.get("observation_count")),
        "trace_count": _safe_int(coverage.get("trace_count")),
        "trace_coverage_ratio": round(_safe_float(coverage.get("observation_trace_coverage_ratio")), 4),
        "empty_retrieval_ratio": round(_safe_float(empty.get("ratio")), 4),
        "unknown_empty_outcome_count": _safe_int(metadata_gap.get("unknown_empty_outcome_count", unknown_drilldown.get("count"))),
        "unresolved_unknown_empty_outcome_count": _safe_int(
            metadata_gap.get("unresolved_adapter_payload_gap_count", unknown_drilldown.get("unresolved_count"))
        ),
        "classified_missing_outcome_count": _safe_int(metadata_gap.get("classified_missing_outcome_count")),
        "metadata_dominant_blocker": str(metadata_gap.get("dominant_blocker", "unknown")),
        "metadata_classification_confidence": str(metadata_gap.get("classification_confidence", "unknown")),
        "privacy_flags": {
            "raw_conversation_content_included": privacy.get("raw_conversation_content_included") is True,
            "sample_values_included": privacy.get("sample_values_included") is True,
            "raw_query_text_included": privacy.get("raw_query_text_included") is True,
            "raw_trace_summary_included": privacy.get("raw_trace_summary_included") is True,
        },
        "error": None,
    }


def _fresh_epoch_comparison_report(
    *,
    report_paths: list[Path],
    output_path: Path | None,
    min_report_count: int,
) -> dict[str, Any]:
    if not report_paths:
        raise ValueError("dogfood fresh-epoch-compare requires at least one --report path")
    if min_report_count < 1:
        raise ValueError("dogfood fresh-epoch-compare min-report-count must be >= 1")

    summaries = [_fresh_epoch_report_summary(path) for path in report_paths]
    blocked_reasons = sorted({reason for summary in summaries for reason in summary.get("blocked_reasons", [])})
    pass_count = sum(1 for summary in summaries if summary.get("quality_gate_pass") is True)
    unresolved_total = sum(summary["unresolved_unknown_empty_outcome_count"] for summary in summaries)
    unknown_total = sum(summary["unknown_empty_outcome_count"] for summary in summaries)
    classified_total = sum(summary["classified_missing_outcome_count"] for summary in summaries)
    coverage_ratios = [summary["trace_coverage_ratio"] for summary in summaries]
    empty_ratios = [summary["empty_retrieval_ratio"] for summary in summaries]
    quality_gate_counter = Counter(str(summary.get("quality_gate_decision", "unknown")) for summary in summaries)
    metadata_blocker_counter = Counter(str(summary.get("metadata_dominant_blocker", "unknown")) for summary in summaries)
    confidence_counter = Counter(str(summary.get("metadata_classification_confidence", "unknown")) for summary in summaries)

    comparison_blocked_reasons: list[str] = []
    if len(summaries) < min_report_count:
        comparison_blocked_reasons.append("not_enough_fresh_epoch_reports")
    if pass_count < len(summaries):
        comparison_blocked_reasons.append("fresh_epoch_quality_gate_not_stable")
    if unresolved_total:
        comparison_blocked_reasons.append("unresolved_fresh_epoch_metadata_gap_present")
    if blocked_reasons:
        comparison_blocked_reasons.append("blocked_reasons_present")
    if any(summary.get("kind") != "dogfood_fresh_epoch_readiness" for summary in summaries):
        comparison_blocked_reasons.append("non_fresh_epoch_report_present")
    if any(summary.get("read_only") is not True for summary in summaries):
        comparison_blocked_reasons.append("report_not_read_only")
    if any(summary.get("mutated") is True for summary in summaries):
        comparison_blocked_reasons.append("report_claims_mutation")
    if any(summary.get("default_retrieval_unchanged") is False for summary in summaries):
        comparison_blocked_reasons.append("default_retrieval_changed")
    if any(any(summary.get("privacy_flags", {}).values()) for summary in summaries):
        comparison_blocked_reasons.append("privacy_flag_claims_raw_content")

    passed = not comparison_blocked_reasons
    payload = {
        "kind": "dogfood_fresh_epoch_comparison",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "report_count": len(summaries),
        "reports": summaries,
        "aggregate": {
            "quality_gate_pass_count": pass_count,
            "quality_gate_decision_counts": {key: quality_gate_counter[key] for key in sorted(quality_gate_counter)},
            "observation_count_total": sum(summary["observation_count"] for summary in summaries),
            "trace_count_total": sum(summary["trace_count"] for summary in summaries),
            "trace_coverage_ratio_min": min(coverage_ratios, default=0.0),
            "trace_coverage_ratio_max": max(coverage_ratios, default=0.0),
            "empty_retrieval_ratio_min": min(empty_ratios, default=0.0),
            "empty_retrieval_ratio_max": max(empty_ratios, default=0.0),
            "unknown_empty_outcome_count_total": unknown_total,
            "unresolved_unknown_empty_outcome_count_total": unresolved_total,
            "classified_missing_outcome_count_total": classified_total,
            "metadata_dominant_blocker_counts": {key: metadata_blocker_counter[key] for key in sorted(metadata_blocker_counter)},
            "metadata_classification_confidence_counts": {key: confidence_counter[key] for key in sorted(confidence_counter)},
            "blocked_reasons": blocked_reasons,
        },
        "thresholds": {"min_report_count": min_report_count},
        "quality_gate": {
            "pass": passed,
            "decision": (
                "fresh_epoch_collection_stable_for_historical_comparison"
                if passed
                else "continue_fresh_epoch_collection_before_historical_comparison"
            ),
            "blocked_reasons": comparison_blocked_reasons,
        },
        "automation_policy": {
            "apply_supported": False,
            "telemetry_reset_apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "raw_report_included": False,
        },
        "suggested_next_steps": [
            "Use a passing comparison only as reset-avoidance evidence for historical telemetry analysis.",
            "Keep telemetry reset/apply in a separate reviewed corridor with explicit backup and approval phrase.",
            "Keep broad G4 apply blocked until reviewed candidates have their own persist/apply gate evidence.",
        ],
    }
    _write_json_report(output_path, payload)
    return payload



def _dogfood_fresh_epoch_runway_payload(args: argparse.Namespace) -> dict[str, Any]:
    report_dir = args.report_dir.expanduser().resolve(strict=False)
    report_dir.mkdir(parents=True, exist_ok=True)
    artifact_prefix = (args.artifact_prefix or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")).strip()
    if not artifact_prefix:
        raise ValueError("dogfood fresh-epoch-runway artifact-prefix must be non-empty")
    fresh_report_path = report_dir / f"{artifact_prefix}-fresh-epoch.json"
    comparison_report_path = report_dir / f"{artifact_prefix}-fresh-epoch-compare.json"
    reconciliation_report_path = report_dir / f"{artifact_prefix}-telemetry-reconciliation.json"

    fresh_payload = _dogfood_fresh_epoch_payload(
        argparse.Namespace(
            db_path=args.db_path,
            epoch_start=args.epoch_start,
            output=fresh_report_path,
            min_trace_coverage=args.min_trace_coverage,
            min_evidence_count=args.min_evidence_count,
            high_empty_threshold=args.high_empty_threshold,
        )
    )
    baseline_reports = [path.expanduser().resolve(strict=False) for path in (args.baseline_reports or [])]
    comparison_reports = [*baseline_reports, fresh_report_path]
    comparison_payload = _fresh_epoch_comparison_report(
        report_paths=comparison_reports,
        output_path=comparison_report_path,
        min_report_count=args.min_report_count,
    )
    reconciliation_payload = _dogfood_telemetry_reconciliation_payload(
        argparse.Namespace(
            db_path=args.db_path,
            epoch_start=args.epoch_start,
            output=reconciliation_report_path,
            min_trace_coverage=args.min_trace_coverage,
            min_evidence_count=args.min_evidence_count,
            high_empty_threshold=args.high_empty_threshold,
            fresh_epoch_comparison_report=comparison_report_path,
        )
    )
    blocked_reasons: list[str] = []
    fresh_gate = fresh_payload.get("quality_gate", {}) if isinstance(fresh_payload.get("quality_gate"), dict) else {}
    comparison_gate = comparison_payload.get("quality_gate", {}) if isinstance(comparison_payload.get("quality_gate"), dict) else {}
    reconciliation_gate = reconciliation_payload.get("quality_gate", {}) if isinstance(reconciliation_payload.get("quality_gate"), dict) else {}
    if fresh_gate.get("pass") is not True:
        blocked_reasons.append("fresh_epoch_quality_gate_not_green")
    if comparison_gate.get("pass") is not True:
        blocked_reasons.append("fresh_epoch_comparison_not_green")
    if reconciliation_gate.get("pass") is not True:
        blocked_reasons.append("telemetry_reconciliation_not_green")
    passed = not blocked_reasons
    payload = {
        "kind": "dogfood_fresh_epoch_runway",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path.expanduser().resolve(strict=False)),
        "epoch_start": args.epoch_start,
        "report_dir": str(report_dir),
        "artifacts": {
            "fresh_epoch_report": str(fresh_report_path),
            "fresh_epoch_comparison_report": str(comparison_report_path),
            "telemetry_reconciliation_report": str(reconciliation_report_path),
        },
        "input_reports": {
            "baseline_report_count": len(baseline_reports),
            "baseline_reports": [str(path) for path in baseline_reports],
            "comparison_report_count": len(comparison_reports),
        },
        "fresh_epoch_quality_gate": fresh_gate,
        "fresh_epoch_comparison_quality_gate": comparison_gate,
        "telemetry_reconciliation_quality_gate": reconciliation_gate,
        "quality_gate": {
            "pass": passed,
            "decision": "fresh_epoch_runway_ready_for_manual_telemetry_reconciliation"
            if passed
            else "continue_fresh_epoch_collection_before_manual_telemetry_reconciliation",
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
            "apply_supported": False,
            "telemetry_reset_apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_policy": "approved_only_unchanged",
            "requires_human_review": True,
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "raw_report_included": False,
            "aggregate_only": True,
        },
        "suggested_next_steps": [
            "Inspect the saved aggregate reports before any manual telemetry-only reset decision.",
            "Treat a green runway as reset-avoidance evidence only; it does not authorize live reset/apply.",
            "Keep broad G4 apply, default ranking migration, collapse/delete, and ordinary auto-approval blocked.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload

def _dogfood_scheduled_blocker_resolution_payload(args: argparse.Namespace) -> dict[str, Any]:
    report_path = args.report.expanduser().resolve(strict=False)
    raw_text = report_path.read_text(encoding="utf-8")
    raw = json.loads(raw_text)
    if not isinstance(raw, dict) or raw.get("kind") != "dogfood_scheduled_dry_run":
        raise ValueError("dogfood scheduled-blocker-resolution requires a dogfood_scheduled_dry_run report")
    if raw.get("mutated") is True or raw.get("default_retrieval_unchanged") is False:
        raise ValueError("dogfood scheduled-blocker-resolution requires a read-only unchanged scheduled report")
    privacy = raw.get("privacy", {}) if isinstance(raw.get("privacy"), dict) else {}
    if any(privacy.get(key) is True for key in ("raw_conversation_content_included", "sample_values_included", "raw_query_text_included")):
        raise ValueError("dogfood scheduled-blocker-resolution refuses reports that claim raw/sample content exposure")

    reports = raw.get("reports", {}) if isinstance(raw.get("reports"), dict) else {}
    trace_quality = reports.get("trace_quality", {}) if isinstance(reports.get("trace_quality"), dict) else {}
    background = reports.get("background_dry_run", {}) if isinstance(reports.get("background_dry_run"), dict) else {}
    background_reports = background.get("reports", {}) if isinstance(background.get("reports"), dict) else {}
    decay_risk = background_reports.get("decay_risk", {}) if isinstance(background_reports.get("decay_risk"), dict) else {}
    candidate_decomposition = decay_risk.get("candidate_decomposition", {}) if isinstance(decay_risk.get("candidate_decomposition"), dict) else {}
    scan = background.get("scan", {}) if isinstance(background.get("scan"), dict) else {}
    quality_warnings = scan.get("quality_warnings", []) if isinstance(scan.get("quality_warnings"), list) else []
    quality_gate = raw.get("quality_gate", {}) if isinstance(raw.get("quality_gate"), dict) else {}
    blocked_reasons = sorted(str(reason) for reason in quality_gate.get("blocked_reasons", []) if reason)
    trace_coverage = trace_quality.get("coverage", {}) if isinstance(trace_quality.get("coverage"), dict) else {}
    retrieval_quality = trace_quality.get("retrieval_quality", {}) if isinstance(trace_quality.get("retrieval_quality"), dict) else {}
    trace_recommendation = str(trace_quality.get("recommendation", "unknown"))
    trace_warnings = trace_quality.get("warnings", []) if isinstance(trace_quality.get("warnings"), list) else []
    coverage_ratio = _safe_float(trace_coverage.get("observation_trace_coverage_ratio"))
    empty_ratio = _safe_float(retrieval_quality.get("empty_retrieval_ratio"))
    hint_counts = candidate_decomposition.get("resolution_hint_counts", {}) if isinstance(candidate_decomposition.get("resolution_hint_counts"), dict) else {}
    monitor_only_count = _safe_int(hint_counts.get("monitor_only_no_mutation"))
    decay_candidate_count = _safe_int(candidate_decomposition.get("candidate_count"))
    decay_max_score = _safe_float(candidate_decomposition.get("max_score"))

    trace_resolved = trace_recommendation == "consider_g4_plan" or (
        args.accept_ready_trace_quality
        and trace_recommendation == "ready_for_more_dry_runs"
        and coverage_ratio >= args.min_trace_coverage
        and empty_ratio <= args.max_empty_retrieval_ratio
        and not trace_warnings
    )
    decay_resolved = (
        "decay_risk_above_threshold" not in blocked_reasons
        or (
            args.allow_monitor_only_decay
            and decay_candidate_count > 0
            and monitor_only_count == decay_candidate_count
            and decay_max_score <= args.max_monitor_decay_score
            and candidate_decomposition.get("raw_content_included") is False
        )
    )
    background_resolved = len(quality_warnings) == 0
    resolutions = {
        "trace_quality_needs_more_dogfooding": {
            "resolved": trace_resolved,
            "resolution": "accepted_ready_trace_quality" if trace_resolved and trace_recommendation != "consider_g4_plan" else ("native_g4_trace_quality" if trace_resolved else "unresolved"),
            "recommendation": trace_recommendation,
            "coverage_ratio": round(coverage_ratio, 4),
            "empty_retrieval_ratio": round(empty_ratio, 4),
            "warnings": sorted(str(warning) for warning in trace_warnings if warning),
        },
        "decay_risk_above_threshold": {
            "resolved": decay_resolved,
            "resolution": "monitor_only_low_risk_decay_classified" if decay_resolved and "decay_risk_above_threshold" in blocked_reasons else ("not_blocked" if decay_resolved else "unresolved"),
            "candidate_count": decay_candidate_count,
            "monitor_only_candidate_count": monitor_only_count,
            "max_score": round(decay_max_score, 4),
            "raw_content_included": candidate_decomposition.get("raw_content_included") is True,
        },
        "background_quality_warnings_present": {
            "resolved": background_resolved,
            "resolution": "no_background_quality_warnings" if background_resolved else "unresolved",
            "warning_count": len(quality_warnings),
            "warnings": sorted(str(warning) for warning in quality_warnings if warning),
        },
    }
    unresolved = [key for key in blocked_reasons if not resolutions.get(key, {"resolved": False}).get("resolved")]
    passed = not unresolved
    payload = {
        "kind": "dogfood_scheduled_blocker_resolution",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "report_path": str(report_path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "original_blocked_reasons": blocked_reasons,
        "resolutions": resolutions,
        "resolution_gate": {
            "pass": passed,
            "decision": "scheduled_blockers_resolved_for_bounded_partial_automation_only" if passed else "scheduled_blockers_still_unresolved",
            "unresolved_blockers": unresolved,
        },
        "automation_policy": {
            "broad_g4_apply_allowed": False,
            "bounded_partial_automation_allowed": passed,
            "ordinary_conversation_auto_approval": False,
            "requires_reviewed_candidates": True,
            "requires_backup_audit_rollback": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_report_included": False,
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
        },
        "suggested_next_steps": [
            "Use this only as evidence for bounded reviewed-candidate automation, not broad G4 apply.",
            "Keep ordinary conversation auto-approval disabled.",
            "Require backup/audit/rollback for every mutation corridor.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _scheduled_dry_run_comparison_report(
    *,
    report_paths: list[Path],
    output_path: Path | None,
    min_report_count: int,
    max_decay_risk: int,
) -> dict[str, Any]:
    if not report_paths:
        raise ValueError("dogfood scheduled-compare requires at least one --report path")
    if min_report_count < 1:
        raise ValueError("dogfood scheduled-compare min-report-count must be >= 1")
    if max_decay_risk < 0:
        raise ValueError("dogfood scheduled-compare max-decay-risk must be >= 0")

    summaries = [_scheduled_dry_run_report_summary(path) for path in report_paths]
    gate_counter = Counter(str(summary.get("quality_gate_decision", "unknown")) for summary in summaries)
    trace_recommendation_counter = Counter(str(summary.get("trace_quality_recommendation", "unknown")) for summary in summaries)
    storage_status_counter = Counter(str(summary.get("storage_health_status", "unknown")) for summary in summaries)
    blocked_reasons = sorted({reason for summary in summaries for reason in summary.get("blocked_reasons", [])})
    background_quality_warnings = sorted(
        {warning for summary in summaries for warning in summary.get("background_quality_warnings", [])}
    )
    trace_coverage_ratios = [summary["trace_coverage_ratio"] for summary in summaries]
    empty_retrieval_ratios = [summary["empty_retrieval_ratio"] for summary in summaries]
    pass_count = sum(1 for summary in summaries if summary.get("quality_gate_pass") is True)
    decay_risk_candidate_count_max = max((summary["decay_risk_candidate_count"] for summary in summaries), default=0)

    comparison_blocked_reasons: list[str] = []
    if len(summaries) < min_report_count:
        comparison_blocked_reasons.append("not_enough_scheduled_reports")
    if pass_count < len(summaries):
        comparison_blocked_reasons.append("scheduled_quality_gate_not_stable")
    if blocked_reasons:
        comparison_blocked_reasons.append("blocked_reasons_present")
    if decay_risk_candidate_count_max > max_decay_risk:
        comparison_blocked_reasons.append("decay_risk_above_threshold")
    if background_quality_warnings:
        comparison_blocked_reasons.append("background_quality_warnings_present")
    if any(summary.get("kind") != "dogfood_scheduled_dry_run" for summary in summaries):
        comparison_blocked_reasons.append("non_scheduled_report_present")
    if any(summary.get("mutated") is True for summary in summaries):
        comparison_blocked_reasons.append("report_claims_mutation")
    if any(summary.get("default_retrieval_unchanged") is False for summary in summaries):
        comparison_blocked_reasons.append("default_retrieval_changed")
    if any(any(summary.get("privacy_flags", {}).values()) for summary in summaries):
        comparison_blocked_reasons.append("privacy_flag_claims_raw_content")

    passed = not comparison_blocked_reasons
    trace_blocker_count = sum(
        1 for summary in summaries if "trace_quality_needs_more_dogfooding" in summary.get("blocked_reasons", [])
    )
    blocker_diagnostics = {
        "trace_quality_needs_more_dogfooding": {
            "blocked": trace_blocker_count > 0,
            "source": "aggregate.blocked_reasons",
            "report_count": len(summaries),
            "affected_report_count": trace_blocker_count,
            "next_action": "Keep comparing scheduled reports until trace-quality blockers disappear consistently.",
        },
        "decay_risk_above_threshold": {
            "blocked": "decay_risk_above_threshold" in comparison_blocked_reasons,
            "source": "aggregate.decay_risk_candidate_count_max",
            "candidate_count_max": decay_risk_candidate_count_max,
            "max_allowed": max_decay_risk,
            "excess": max(0, decay_risk_candidate_count_max - max_decay_risk),
            "next_action": "Inspect decay-risk candidates before broad G4 planning.",
        },
        "background_quality_warnings_present": {
            "blocked": "background_quality_warnings_present" in comparison_blocked_reasons,
            "source": "aggregate.background_quality_warnings",
            "warning_count": len(background_quality_warnings),
            "warnings": background_quality_warnings,
            "next_action": "Resolve or classify recurring background warnings before broad G4 planning.",
        },
    }
    payload = {
        "kind": "dogfood_scheduled_dry_run_comparison",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "report_count": len(summaries),
        "reports": summaries,
        "aggregate": {
            "quality_gate_pass_count": pass_count,
            "quality_gate_decision_counts": {key: gate_counter[key] for key in sorted(gate_counter)},
            "trace_quality_recommendation_counts": {
                key: trace_recommendation_counter[key] for key in sorted(trace_recommendation_counter)
            },
            "storage_health_status_counts": {key: storage_status_counter[key] for key in sorted(storage_status_counter)},
            "candidate_count_max": max((summary["candidate_count"] for summary in summaries), default=0),
            "reinforcement_candidate_count_max": max(
                (summary["reinforcement_candidate_count"] for summary in summaries), default=0
            ),
            "decay_risk_candidate_count_max": decay_risk_candidate_count_max,
            "trace_coverage_ratio_min": min(trace_coverage_ratios, default=0.0),
            "trace_coverage_ratio_max": max(trace_coverage_ratios, default=0.0),
            "empty_retrieval_ratio_min": min(empty_retrieval_ratios, default=0.0),
            "empty_retrieval_ratio_max": max(empty_retrieval_ratios, default=0.0),
            "blocked_reasons": blocked_reasons,
            "background_quality_warnings": background_quality_warnings,
            "safe_remember_intent_count_total": sum(summary["safe_remember_intent_count"] for summary in summaries),
            "rejected_remember_intent_count_total": sum(summary["rejected_remember_intent_count"] for summary in summaries),
        },
        "thresholds": {
            "min_report_count": min_report_count,
            "max_decay_risk": max_decay_risk,
        },
        "quality_gate": {
            "pass": passed,
            "decision": (
                "scheduled_report_collection_stable_plan_g4_only"
                if passed
                else "continue_scheduled_report_collection_before_g4"
            ),
            "blocked_reasons": comparison_blocked_reasons,
            "blocker_diagnostics": blocker_diagnostics,
        },
        "automation_policy": {
            "apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
        },
        "suggested_next_steps": [
            "Keep collecting scheduled dry-run reports until the comparison gate is stable.",
            "Treat a stable comparison only as permission to write a separate G4 apply-mode plan.",
            "Do not infer broad preferences or change default retrieval from this comparison report.",
        ],
    }
    _write_json_report(output_path, payload)
    return payload


def _dogfood_scheduled_dry_run_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.since_hours < 1:
        raise ValueError("dogfood scheduled-dry-run since-hours must be >= 1")
    if not 0 <= args.min_trace_coverage <= 1:
        raise ValueError("dogfood scheduled-dry-run min-trace-coverage must be between 0 and 1")
    if args.min_evidence_count < 1:
        raise ValueError("dogfood scheduled-dry-run min-evidence-count must be >= 1")
    if args.limit < 1:
        raise ValueError("dogfood scheduled-dry-run limit must be >= 1")
    if args.top < 1:
        raise ValueError("dogfood scheduled-dry-run top must be >= 1")
    if args.frequent_threshold < 1:
        raise ValueError("dogfood scheduled-dry-run frequent-threshold must be >= 1")
    if args.candidate_min < 0:
        raise ValueError("dogfood scheduled-dry-run candidate-min must be >= 0")
    if args.max_decay_risk < 0:
        raise ValueError("dogfood scheduled-dry-run max-decay-risk must be >= 0")

    storage_health = _dogfood_storage_health_payload(
        argparse.Namespace(db_path=args.db_path, hermes_config=args.hermes_config)
    )
    trace_quality = _dogfood_trace_quality_payload(
        argparse.Namespace(
            db_path=args.db_path,
            since_hours=args.since_hours,
            epoch_start=getattr(args, "epoch_start", None),
            min_trace_coverage=args.min_trace_coverage,
            min_evidence_count=args.min_evidence_count,
        )
    )
    remember_intent = _remember_intent_dogfood_report(
        args.db_path,
        limit=args.limit,
        sample_limit=args.remember_sample_limit,
    )
    lock_path = args.lock_path or args.db_path.with_suffix(".scheduled-dry-run.lock")
    background_dry_run = _consolidation_background_dry_run_report(
        args.db_path,
        limit=args.limit,
        top=args.top,
        min_evidence=args.min_evidence_count,
        frequent_threshold=args.frequent_threshold,
        output_path=None,
        lock_path=lock_path,
    )
    quality_gate = _scheduled_dry_run_quality_decision(
        storage_health=storage_health,
        trace_quality=trace_quality,
        background_dry_run=background_dry_run,
        candidate_min=args.candidate_min,
        max_decay_risk=args.max_decay_risk,
    )
    payload = {
        "kind": "dogfood_scheduled_dry_run",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "reports_included": ["storage_health", "trace_quality", "remember_intent", "background_dry_run"],
        "reports": {
            "storage_health": storage_health,
            "trace_quality": trace_quality,
            "remember_intent": remember_intent,
            "background_dry_run": background_dry_run,
        },
        "thresholds": {
            "since_hours": args.since_hours,
            "epoch_start": getattr(args, "epoch_start", None),
            "min_trace_coverage": args.min_trace_coverage,
            "min_evidence_count": args.min_evidence_count,
            "candidate_min": args.candidate_min,
            "max_decay_risk": args.max_decay_risk,
        },
        "quality_gate": quality_gate,
        "automation_policy": {
            "apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
        },
        "suggested_next_steps": [
            "Schedule this command repeatedly before planning any G4 apply mode.",
            "Treat a passing quality gate only as permission to write a separate G4 plan with RED tests.",
            "Keep ordinary conversation traces metadata-only and keep default retrieval approved-only.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _background_dry_run_dogfood_report(
    db_path: Path,
    *,
    report_paths: list[Path],
    output_path: Path | None,
    candidate_min: int,
    max_decay_risk: int,
    min_completed_runs: int,
) -> dict[str, Any]:
    if not report_paths:
        raise ValueError("dogfood background-dry-run requires at least one --report path")
    if candidate_min < 0:
        raise ValueError("dogfood background-dry-run candidate-min must be >= 0")
    if max_decay_risk < 0:
        raise ValueError("dogfood background-dry-run max-decay-risk must be >= 0")
    if min_completed_runs < 1:
        raise ValueError("dogfood background-dry-run min-completed-runs must be >= 1")

    summaries = [_background_dry_run_report_summary(path) for path in report_paths]
    status_counter = Counter(str(summary.get("status", "unknown")) for summary in summaries)
    status_counts = {status: status_counter[status] for status in sorted(status_counter)}
    quality_warnings = sorted({warning for summary in summaries for warning in summary.get("quality_warnings", [])})
    candidate_count_max = max((summary["candidate_count"] for summary in summaries), default=0)
    reinforcement_candidate_count_max = max((summary["reinforcement_candidate_count"] for summary in summaries), default=0)
    decay_risk_candidate_count_max = max((summary["decay_risk_candidate_count"] for summary in summaries), default=0)
    activation_count_max = max((summary["activation_count"] for summary in summaries), default=0)
    decay_decompositions = [
        summary.get("decay_risk_candidate_decomposition", {})
        for summary in summaries
        if isinstance(summary.get("decay_risk_candidate_decomposition"), dict)
        and summary.get("decay_risk_candidate_decomposition")
    ]
    empty_retrieval_activation_diagnostics = [
        summary.get("empty_retrieval_activation_diagnostics", {})
        for summary in summaries
        if isinstance(summary.get("empty_retrieval_activation_diagnostics"), dict)
        and summary.get("empty_retrieval_activation_diagnostics")
    ]
    decay_top_factor_names = sorted(
        {name for decomposition in decay_decompositions for name in decomposition.get("top_factor_names", []) if name}
    )
    completed_count = status_counter.get("completed", 0)

    blocked_reasons: list[str] = []
    if completed_count < min_completed_runs:
        blocked_reasons.append("not_enough_completed_background_runs")
    if any(status != "completed" for status in status_counter):
        blocked_reasons.append("background_reports_have_failures_or_skips")
    if candidate_count_max < candidate_min:
        blocked_reasons.append("candidate_signal_below_threshold")
    if decay_risk_candidate_count_max > max_decay_risk:
        blocked_reasons.append("decay_risk_above_threshold")
    if quality_warnings:
        blocked_reasons.append("quality_warnings_present")
    if any(summary.get("mutated") is True for summary in summaries):
        blocked_reasons.append("background_report_claims_mutation")
    if any(summary.get("default_retrieval_unchanged") is False for summary in summaries):
        blocked_reasons.append("default_retrieval_changed")

    passed = not blocked_reasons
    blocker_diagnostics = {
        "candidate_signal_below_threshold": {
            "blocked": "candidate_signal_below_threshold" in blocked_reasons,
            "source": "aggregate.candidate_count_max",
            "candidate_count_max": candidate_count_max,
            "min_required": candidate_min,
            "deficit": max(0, candidate_min - candidate_count_max),
            "next_action": "Collect or explain more read-only consolidation candidates before broad G4 planning.",
        },
        "decay_risk_above_threshold": {
            "blocked": "decay_risk_above_threshold" in blocked_reasons,
            "source": "aggregate.decay_risk_candidate_count_max",
            "candidate_count_max": decay_risk_candidate_count_max,
            "max_allowed": max_decay_risk,
            "excess": max(0, decay_risk_candidate_count_max - max_decay_risk),
            "candidate_decomposition": {
                "report_count": len(decay_decompositions),
                "top_factor_names": decay_top_factor_names,
                "max_score": max((_safe_float(item.get("max_score")) for item in decay_decompositions), default=0.0),
                "raw_content_included": False,
            },
            "next_action": "Inspect aggregate decay-risk candidates before broad G4 planning.",
        },
        "quality_warnings_present": {
            "blocked": "quality_warnings_present" in blocked_reasons,
            "source": "aggregate.quality_warnings",
            "warning_count": len(quality_warnings),
            "warnings": quality_warnings,
            "empty_retrieval_activation_diagnostics": empty_retrieval_activation_diagnostics[:5],
            "next_action": "Resolve, classify, or document each warning with RED tests before broad G4 planning.",
        },
    }
    payload = {
        "kind": "background_dry_run_dogfood_report",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(db_path),
        "report_count": len(summaries),
        "status_counts": status_counts,
        "reports": summaries,
        "aggregate": {
            "completed_count": completed_count,
            "candidate_count_max": candidate_count_max,
            "reinforcement_candidate_count_max": reinforcement_candidate_count_max,
            "decay_risk_candidate_count_max": decay_risk_candidate_count_max,
            "activation_count_max": activation_count_max,
            "quality_warnings": quality_warnings,
        },
        "thresholds": {
            "candidate_min": candidate_min,
            "max_decay_risk": max_decay_risk,
            "min_completed_runs": min_completed_runs,
        },
        "quality_gate": {
            "pass": passed,
            "decision": "dry_run_quality_gate_passed_plan_g4_only" if passed else "continue_dry_run_dogfooding_before_g4",
            "blocked_reasons": blocked_reasons,
            "blocker_diagnostics": blocker_diagnostics,
        },
        "automation_policy": {
            "apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "suggested_next_steps": [
            "Do not enable background apply mode from this report.",
            "Use passing quality gates only to justify a separate G4 plan with RED tests, audit, and rollback.",
            "Keep G3 dry-run reports read-only and review samples manually before any policy expansion.",
        ],
    }
    _write_json_report(output_path, payload)
    return payload


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
    empty_by_surface = Counter(str(getattr(activation, "surface", None) or "unknown") for activation in empty_retrieval_activations)
    empty_by_scope = Counter(str(getattr(activation, "scope", None) or "global") for activation in empty_retrieval_activations)
    empty_observation_ids = {
        activation.observation_id for activation in empty_retrieval_activations if activation.observation_id is not None
    }
    empty_observations = [
        observation for observation in list_retrieval_observations(db_path, limit=limit) if observation.id in empty_observation_ids
    ]
    empty_by_response_mode = Counter(str(observation.response_mode or "unknown") for observation in empty_observations)
    empty_by_hook_event_name = Counter(
        str(observation.metadata.get("hook_event_name") or "unknown") for observation in empty_observations
    )
    empty_by_retrieval_outcome = Counter(
        str(observation.metadata.get("retrieval_outcome") or "unknown") for observation in empty_observations
    )
    linked_observation_ids: set[int] = set()
    with _open_readonly_sqlite(db_path) as connection:
        if _table_exists(connection, "experience_traces"):
            rows = connection.execute(
                """
                SELECT related_observation_ids_json
                FROM experience_traces
                WHERE related_observation_ids_json != '[]'
                """
            ).fetchall()
            for row in rows:
                for observation_id in _safe_json_list_from_db(row["related_observation_ids_json"]):
                    if isinstance(observation_id, int):
                        linked_observation_ids.add(observation_id)
    empty_linked_to_trace_count = len(empty_observation_ids & linked_observation_ids)
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
            "by_surface": {key: empty_by_surface[key] for key in sorted(empty_by_surface)},
            "by_scope": {key: empty_by_scope[key] for key in sorted(empty_by_scope)},
            "by_response_mode": {key: empty_by_response_mode[key] for key in sorted(empty_by_response_mode)},
            "by_hook_event_name": {key: empty_by_hook_event_name[key] for key in sorted(empty_by_hook_event_name)},
            "by_retrieval_outcome": {key: empty_by_retrieval_outcome[key] for key in sorted(empty_by_retrieval_outcome)},
            "trace_linkage": {
                "linked_to_trace_count": empty_linked_to_trace_count,
                "unlinked_to_trace_count": max(0, len(empty_observation_ids) - empty_linked_to_trace_count),
            },
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


def _open_readonly_sqlite(db_path: Path) -> sqlite3.Connection:
    resolved = db_path.expanduser().resolve(strict=False)
    connection = sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _readonly_table_count(connection: sqlite3.Connection, table_name: str) -> int:
    if not _table_exists(connection, table_name):
        return 0
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _readonly_latest_created_at(connection: sqlite3.Connection, table_name: str) -> str | None:
    if not _table_exists(connection, table_name):
        return None
    row = connection.execute(f"SELECT MAX(created_at) FROM {table_name}").fetchone()
    return row[0]


def _readonly_memory_status_counts(connection: sqlite3.Connection) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for payload_name, table_name in (
        ("facts", "facts"),
        ("procedures", "procedures"),
        ("episodes", "episodes"),
    ):
        if not _table_exists(connection, table_name):
            counts[payload_name] = {}
            continue
        rows = connection.execute(
            f"SELECT status, COUNT(*) AS count FROM {table_name} GROUP BY status ORDER BY status"
        ).fetchall()
        counts[payload_name] = {str(row["status"]): int(row["count"]) for row in rows}
    return counts


def _metadata_json_validity(connection: sqlite3.Connection) -> dict[str, Any]:
    invalid_counts: dict[str, int] = {}
    checked_counts: dict[str, int] = {}
    for table_name in ("retrieval_observations", "memory_activations", "experience_traces"):
        invalid_counts[table_name] = 0
        checked_counts[table_name] = 0
        if not _table_exists(connection, table_name):
            continue
        rows = connection.execute(f"SELECT metadata_json FROM {table_name}").fetchall()
        checked_counts[table_name] = len(rows)
        for row in rows:
            try:
                parsed = json.loads(row["metadata_json"] or "{}")
            except json.JSONDecodeError:
                invalid_counts[table_name] += 1
                continue
            if not isinstance(parsed, dict):
                invalid_counts[table_name] += 1
    return {
        "status": "pass" if sum(invalid_counts.values()) == 0 else "warning",
        "checked_counts": checked_counts,
        "invalid_counts": invalid_counts,
    }


def _stored_query_excerpt_invariant(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "retrieval_observations"):
        return {"status": "warning", "checked_count": 0, "violation_count": 0, "latest_violation_at": None}
    row = connection.execute(
        """
        SELECT COUNT(*) AS count, MAX(created_at) AS latest
        FROM retrieval_observations
        WHERE COALESCE(query_preview, '') <> ''
        """
    ).fetchone()
    checked = _readonly_table_count(connection, "retrieval_observations")
    violation_count = int(row["count"])
    return {
        "status": "pass" if violation_count == 0 else "warning",
        "checked_count": checked,
        "violation_count": violation_count,
        "latest_violation_at": row["latest"],
    }


def _query_hash_presence_invariant(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "retrieval_observations"):
        return {"status": "warning", "checked_count": 0, "violation_count": 0, "latest_violation_at": None}
    row = connection.execute(
        """
        SELECT COUNT(*) AS count, MAX(created_at) AS latest
        FROM retrieval_observations
        WHERE COALESCE(query_sha256, '') = ''
        """
    ).fetchone()
    checked = _readonly_table_count(connection, "retrieval_observations")
    violation_count = int(row["count"])
    return {
        "status": "pass" if violation_count == 0 else "warning",
        "checked_count": checked,
        "violation_count": violation_count,
        "latest_violation_at": row["latest"],
    }


def _activation_link_invariant(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "memory_activations"):
        return {
            "status": "warning",
            "checked_count": 0,
            "orphan_observation_count": 0,
            "orphan_trace_count": 0,
        }
    checked = _readonly_table_count(connection, "memory_activations")
    orphan_observations = 0
    orphan_traces = 0
    if _table_exists(connection, "retrieval_observations"):
        orphan_observations = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM memory_activations AS activation
                LEFT JOIN retrieval_observations AS observation ON observation.id = activation.observation_id
                WHERE activation.observation_id IS NOT NULL AND observation.id IS NULL
                """
            ).fetchone()[0]
        )
    if _table_exists(connection, "experience_traces"):
        orphan_traces = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM memory_activations AS activation
                LEFT JOIN experience_traces AS trace ON trace.id = activation.trace_id
                WHERE activation.trace_id IS NOT NULL AND trace.id IS NULL
                """
            ).fetchone()[0]
        )
    violation_count = orphan_observations + orphan_traces
    return {
        "status": "pass" if violation_count == 0 else "warning",
        "checked_count": checked,
        "orphan_observation_count": orphan_observations,
        "orphan_trace_count": orphan_traces,
    }


def _safe_metadata_from_json(metadata_json: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(metadata_json or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _ordinary_trace_metadata_only_invariant(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "experience_traces"):
        return {"status": "warning", "checked_count": 0, "violation_count": 0, "violations": {}}
    rows = connection.execute(
        """
        SELECT summary, retention_policy, metadata_json
        FROM experience_traces
        WHERE event_kind = 'turn'
        """
    ).fetchall()
    violations: Counter[str] = Counter()
    for row in rows:
        metadata = _safe_metadata_from_json(row["metadata_json"])
        if row["summary"] is not None:
            violations["summary_present"] += 1
        if row["retention_policy"] != "ephemeral":
            violations["retention_not_ephemeral"] += 1
        if metadata.get("candidate_policy") != "evidence_only":
            violations["candidate_policy_not_evidence_only"] += 1
        if metadata.get("auto_approved") is not False:
            violations["auto_approved_not_false"] += 1
    violation_count = sum(violations.values())
    return {
        "status": "pass" if violation_count == 0 else "warning",
        "checked_count": len(rows),
        "violation_count": violation_count,
        "violations": dict(sorted(violations.items())),
    }


def _remember_intent_safety_invariant(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "experience_traces"):
        return {
            "status": "warning",
            "checked_count": 0,
            "review_ready_count": 0,
            "rejected_secret_like_count": 0,
            "violation_count": 0,
            "violations": {},
        }
    rows = connection.execute(
        """
        SELECT summary, retention_policy, metadata_json
        FROM experience_traces
        WHERE event_kind = 'remember_intent'
        """
    ).fetchall()
    violations: Counter[str] = Counter()
    review_ready_count = 0
    rejected_secret_like_count = 0
    for row in rows:
        metadata = _safe_metadata_from_json(row["metadata_json"])
        candidate_policy = metadata.get("candidate_policy")
        if candidate_policy == "review_required":
            if (
                row["summary"] is not None
                and row["retention_policy"] == "review"
                and metadata.get("auto_approved") is False
                and metadata.get("secret_scan") == "passed"
                and not _contains_secret_like_report_text(row["summary"])
            ):
                review_ready_count += 1
            else:
                violations["review_required_shape"] += 1
        elif candidate_policy == "rejected":
            if (
                row["summary"] is None
                and metadata.get("auto_approved") is False
                and metadata.get("rejected_reason") == "secret_like_text"
            ):
                rejected_secret_like_count += 1
            else:
                violations["rejected_shape"] += 1
        else:
            violations["unknown_candidate_policy"] += 1
    violation_count = sum(violations.values())
    return {
        "status": "pass" if violation_count == 0 else "warning",
        "checked_count": len(rows),
        "review_ready_count": review_ready_count,
        "rejected_secret_like_count": rejected_secret_like_count,
        "violation_count": violation_count,
        "violations": dict(sorted(violations.items())),
    }


def _safe_json_list_from_db(value: str | None) -> list[Any]:
    try:
        parsed = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _safe_json_dict_from_db(value: str | None) -> dict[str, Any]:
    try:
        parsed = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _dogfood_trace_quality_recommendation(
    *,
    observation_count: int,
    trace_count: int,
    coverage_ratio: float,
    empty_retrieval_ratio: float,
    repeated_memory_ref_count: int,
    invariant_violation_count: int,
    min_trace_coverage: float,
) -> str:
    if (
        observation_count > 0
        and trace_count > 0
        and coverage_ratio >= min_trace_coverage
        and repeated_memory_ref_count > 0
        and empty_retrieval_ratio <= 0.5
        and invariant_violation_count == 0
    ):
        return "consider_g4_plan"
    if trace_count > 0 and invariant_violation_count == 0 and coverage_ratio >= min_trace_coverage:
        return "ready_for_more_dry_runs"
    return "continue_dogfooding"


def _parse_epoch_start(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("dogfood fresh-epoch epoch-start must be non-empty")
    parse_value = normalized[:-1] + "+00:00" if normalized.endswith("Z") else normalized
    try:
        parsed = datetime.fromisoformat(parse_value)
    except ValueError as exc:
        raise ValueError("dogfood fresh-epoch epoch-start must be ISO-8601, e.g. 2026-05-10T06:57:33Z") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")


def _dogfood_trace_quality_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    epoch_start = _parse_epoch_start(args.epoch_start) if getattr(args, "epoch_start", None) else None
    since_hours = args.since_hours
    min_trace_coverage = args.min_trace_coverage
    min_evidence_count = args.min_evidence_count
    if not db_path.exists():
        return {
            "kind": "dogfood_trace_quality",
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }

    if epoch_start:
        time_filter_sql = "created_at >= ?"
        time_filter_params = (epoch_start,)
        time_window = {"epoch_start": epoch_start}
    else:
        since_modifier = f"-{since_hours} hours"
        time_filter_sql = "created_at >= datetime('now', ?)"
        time_filter_params = (since_modifier,)
        time_window = {"since_hours": since_hours, "sqlite_since_modifier": since_modifier}

    with _open_readonly_sqlite(db_path) as connection:
        observation_rows = (
            connection.execute(
                f"""
                SELECT id, retrieved_memory_refs_json
                FROM retrieval_observations
                WHERE {time_filter_sql}
                ORDER BY id ASC
                """,
                time_filter_params,
            ).fetchall()
            if _table_exists(connection, "retrieval_observations")
            else []
        )
        trace_rows = (
            connection.execute(
                f"""
                SELECT event_kind, retention_policy, related_memory_refs_json, related_observation_ids_json
                FROM experience_traces
                WHERE {time_filter_sql}
                ORDER BY id ASC
                """,
                time_filter_params,
            ).fetchall()
            if _table_exists(connection, "experience_traces")
            else []
        )
        activation_rows = (
            connection.execute(
                f"""
                SELECT activation_kind, memory_ref, observation_id
                FROM memory_activations
                WHERE {time_filter_sql}
                ORDER BY id ASC
                """,
                time_filter_params,
            ).fetchall()
            if _table_exists(connection, "memory_activations")
            else []
        )
        if epoch_start:
            time_window["historical_rows_excluded"] = {
                table: int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE created_at < ?", (epoch_start,)).fetchone()[0])
                if _table_exists(connection, table)
                else 0
                for table in ("experience_traces", "memory_activations", "retrieval_observations")
            }
        ordinary_invariant = _ordinary_trace_metadata_only_invariant(connection)
        metadata_invariant = _metadata_json_validity(connection)

    observation_count = len(observation_rows)
    trace_count = len(trace_rows)
    activation_count = len(activation_rows)
    empty_retrieval_count = 0
    retrieved_memory_ref_counter: Counter[str] = Counter()
    for row in observation_rows:
        refs = [str(ref) for ref in _safe_json_list_from_db(row["retrieved_memory_refs_json"])]
        if not refs:
            empty_retrieval_count += 1
        retrieved_memory_ref_counter.update(refs)

    linked_observation_ids: set[int] = set()
    related_memory_ref_counter: Counter[str] = Counter()
    event_kind_counts: Counter[str] = Counter()
    retention_policy_counts: Counter[str] = Counter()
    for row in trace_rows:
        event_kind_counts[str(row["event_kind"])] += 1
        retention_policy_counts[str(row["retention_policy"])] += 1
        for observation_id in _safe_json_list_from_db(row["related_observation_ids_json"]):
            if isinstance(observation_id, int):
                linked_observation_ids.add(observation_id)
        related_memory_ref_counter.update(str(ref) for ref in _safe_json_list_from_db(row["related_memory_refs_json"]))

    repeated_memory_refs = {
        ref: count for ref, count in retrieved_memory_ref_counter.items() if count >= min_evidence_count
    }
    observation_trace_coverage_ratio = round(len(linked_observation_ids) / observation_count, 4) if observation_count else 0.0
    empty_retrieval_ratio = round(empty_retrieval_count / observation_count, 4) if observation_count else 0.0
    activation_observation_ids = {
        int(row["observation_id"])
        for row in activation_rows
        if row["observation_id"] is not None
    }
    activations_linked_to_traces = len(activation_observation_ids & linked_observation_ids)
    activation_trace_link_coverage_ratio = (
        round(activations_linked_to_traces / len(activation_observation_ids), 4) if activation_observation_ids else 0.0
    )
    unlinked_observation_count = max(0, observation_count - len(linked_observation_ids))
    trace_without_observation_link_count = sum(
        1 for row in trace_rows if not _safe_json_list_from_db(row["related_observation_ids_json"])
    )
    if trace_without_observation_link_count and unlinked_observation_count:
        likely_gap = "traces_missing_observation_links"
    elif unlinked_observation_count:
        likely_gap = "observations_missing_trace_links"
    elif trace_without_observation_link_count:
        likely_gap = "trace_rows_missing_observation_ids"
    else:
        likely_gap = "no_linkage_gap_detected"
    invariant_violation_count = int(ordinary_invariant.get("violation_count", 0)) + sum(
        int(value) for value in metadata_invariant.get("invalid_counts", {}).values()
    )
    recommendation = _dogfood_trace_quality_recommendation(
        observation_count=observation_count,
        trace_count=trace_count,
        coverage_ratio=observation_trace_coverage_ratio,
        empty_retrieval_ratio=empty_retrieval_ratio,
        repeated_memory_ref_count=len(repeated_memory_refs),
        invariant_violation_count=invariant_violation_count,
        min_trace_coverage=min_trace_coverage,
    )
    warnings: list[str] = []
    if observation_count and observation_trace_coverage_ratio < min_trace_coverage:
        warnings.append("low_observation_trace_coverage")
    if invariant_violation_count:
        warnings.append("trace_quality_invariant_warnings")
    if not trace_count:
        warnings.append("no_traces_in_window")
    return {
        "kind": "dogfood_trace_quality",
        "read_only": True,
        "mutated": False,
        "status": "healthy" if not warnings else "warning",
        "database": {"path": str(db_path), "exists": True},
        "time_window": time_window,
        "thresholds": {
            "min_trace_coverage": min_trace_coverage,
            "min_evidence_count": min_evidence_count,
        },
        "coverage": {
            "observation_count": observation_count,
            "trace_count": trace_count,
            "activation_count": activation_count,
            "observations_linked_from_traces": len(linked_observation_ids),
            "observation_trace_coverage_ratio": observation_trace_coverage_ratio,
        },
        "coverage_diagnostics": {
            "unlinked_observation_count": unlinked_observation_count,
            "trace_without_observation_link_count": trace_without_observation_link_count,
            "activation_count": activation_count,
            "activations_linked_to_traces": activations_linked_to_traces,
            "activation_trace_link_coverage_ratio": activation_trace_link_coverage_ratio,
            "likely_gap": likely_gap,
            "next_action": "Verify the runtime links new metadata-only turn traces to retrieval observation ids before broad G4 planning.",
        },
        "retrieval_quality": {
            "empty_retrieval_count": empty_retrieval_count,
            "empty_retrieval_ratio": empty_retrieval_ratio,
            "repeated_memory_ref_count": len(repeated_memory_refs),
            "max_retrieval_repetition": max(retrieved_memory_ref_counter.values(), default=0),
        },
        "trace_distribution": {
            "event_kind_counts": dict(sorted(event_kind_counts.items())),
            "retention_policy_counts": dict(sorted(retention_policy_counts.items())),
        },
        "invariants": {
            "ordinary_trace_metadata_only": ordinary_invariant,
            "metadata_json_valid": metadata_invariant,
        },
        "candidate_signals": {
            "related_memory_ref_count": len(related_memory_ref_counter),
            "related_memory_ref_repetition_count": sum(1 for count in related_memory_ref_counter.values() if count >= min_evidence_count),
            "retrieved_memory_ref_repetition_count": len(repeated_memory_refs),
        },
        "recommendation": recommendation,
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "aggregate_only": True,
        },
        "warnings": warnings,
    }


def _dogfood_fresh_epoch_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    epoch_start = _parse_epoch_start(args.epoch_start)
    min_trace_coverage = args.min_trace_coverage
    min_evidence_count = args.min_evidence_count
    if not db_path.exists():
        payload = {
            "kind": "dogfood_fresh_epoch_readiness",
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }
        _write_json_report(args.output, payload)
        return payload

    with _open_readonly_sqlite(db_path) as connection:
        observation_rows = (
            connection.execute(
                """
                SELECT id, created_at, surface, preferred_scope, retrieved_memory_refs_json, response_mode, metadata_json
                FROM retrieval_observations
                WHERE created_at >= ?
                ORDER BY id ASC
                """,
                (epoch_start,),
            ).fetchall()
            if _table_exists(connection, "retrieval_observations")
            else []
        )
        trace_rows = (
            connection.execute(
                """
                SELECT id, created_at, surface, event_kind, scope, retention_policy,
                       related_memory_refs_json, related_observation_ids_json, metadata_json
                FROM experience_traces
                WHERE created_at >= ?
                ORDER BY id ASC
                """,
                (epoch_start,),
            ).fetchall()
            if _table_exists(connection, "experience_traces")
            else []
        )
        activation_rows = (
            connection.execute(
                """
                SELECT id, created_at, surface, activation_kind, memory_ref, observation_id, trace_id, scope, metadata_json
                FROM memory_activations
                WHERE created_at >= ?
                ORDER BY id ASC
                """,
                (epoch_start,),
            ).fetchall()
            if _table_exists(connection, "memory_activations")
            else []
        )
        historical_excluded = {
            table: int(
                connection.execute(f"SELECT COUNT(*) FROM {table} WHERE created_at < ?", (epoch_start,)).fetchone()[0]
            )
            if _table_exists(connection, table)
            else 0
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }
        latest_created_at = {
            table: connection.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]
            if _table_exists(connection, table)
            else None
            for table in ("retrieval_observations", "memory_activations", "experience_traces")
        }

    observation_count = len(observation_rows)
    trace_count = len(trace_rows)
    activation_count = len(activation_rows)
    empty_observation_rows = [row for row in observation_rows if not _safe_json_list_from_db(row["retrieved_memory_refs_json"])]
    empty_retrieval_count = len(empty_observation_rows)
    empty_retrieval_ratio = round(empty_retrieval_count / observation_count, 4) if observation_count else 0.0

    linked_observation_ids: set[int] = set()
    trace_without_observation_link_count = 0
    trace_event_kind_counts: Counter[str] = Counter()
    trace_surface_counts: Counter[str] = Counter()
    trace_retention_counts: Counter[str] = Counter()
    related_memory_ref_counter: Counter[str] = Counter()
    for row in trace_rows:
        trace_event_kind_counts[str(row["event_kind"])] += 1
        trace_surface_counts[str(row["surface"])] += 1
        trace_retention_counts[str(row["retention_policy"])] += 1
        related_ids = _safe_json_list_from_db(row["related_observation_ids_json"])
        if not related_ids:
            trace_without_observation_link_count += 1
        for observation_id in related_ids:
            if isinstance(observation_id, int):
                linked_observation_ids.add(observation_id)
        related_memory_ref_counter.update(str(ref) for ref in _safe_json_list_from_db(row["related_memory_refs_json"]))

    activation_observation_ids = {
        int(row["observation_id"])
        for row in activation_rows
        if row["observation_id"] is not None
    }
    activations_linked_to_traces = len(activation_observation_ids & linked_observation_ids)
    activation_trace_link_coverage_ratio = (
        round(activations_linked_to_traces / len(activation_observation_ids), 4) if activation_observation_ids else 0.0
    )
    observation_trace_coverage_ratio = round(len(linked_observation_ids) / observation_count, 4) if observation_count else 0.0
    unlinked_observation_count = max(0, observation_count - len(linked_observation_ids))

    empty_by_response_mode = Counter(str(row["response_mode"] or "unknown") for row in empty_observation_rows)
    empty_by_surface = Counter(str(row["surface"] or "unknown") for row in empty_observation_rows)
    empty_by_scope = Counter(str(row["preferred_scope"] or "none") for row in empty_observation_rows)
    empty_by_hook_event_name: Counter[str] = Counter()
    empty_by_retrieval_outcome: Counter[str] = Counter()
    empty_by_likely_cause: Counter[str] = Counter()
    empty_unknown_outcome_drilldown: Counter[str] = Counter()
    for row in empty_observation_rows:
        metadata = _safe_metadata_from_json(row["metadata_json"])
        hook_event_name = str(metadata.get("hook_event_name") or "unknown")
        response_mode = str(row["response_mode"] or "unknown")
        retrieval_outcome = str(metadata.get("retrieval_outcome") or "unknown")
        empty_by_hook_event_name[hook_event_name] += 1
        empty_by_retrieval_outcome[retrieval_outcome] += 1
        if retrieval_outcome == "no_reliable_memory":
            likely_cause = "expected_no_reliable_memory"
        elif retrieval_outcome == "retrieval_disabled_or_unavailable":
            likely_cause = "retrieval_unavailable"
        elif retrieval_outcome in {"query_scope_gap", "adapter_payload_gap"}:
            likely_cause = retrieval_outcome
        elif retrieval_outcome == "unknown" and hook_event_name == "pre_llm_call" and response_mode == "verify_first":
            likely_cause = "legacy_missing_outcome_no_reliable_memory"
        elif retrieval_outcome == "unknown" and hook_event_name == "pre_llm_call":
            likely_cause = "legacy_missing_outcome_metadata_gap"
        elif retrieval_outcome == "unknown":
            likely_cause = "adapter_payload_gap"
        else:
            likely_cause = "other_empty_retrieval_outcome"
        empty_by_likely_cause[likely_cause] += 1
        if retrieval_outcome == "unknown":
            empty_unknown_outcome_drilldown[likely_cause] += 1

    retrieved_memory_ref_counter: Counter[str] = Counter()
    for row in observation_rows:
        retrieved_memory_ref_counter.update(str(ref) for ref in _safe_json_list_from_db(row["retrieved_memory_refs_json"]))

    warnings: list[str] = []
    if observation_count and observation_trace_coverage_ratio < min_trace_coverage:
        warnings.append("low_epoch_observation_trace_coverage")
    if not observation_count:
        warnings.append("no_epoch_observations")
    if not trace_count:
        warnings.append("no_epoch_traces")
    if empty_retrieval_ratio >= args.high_empty_threshold and observation_count:
        warnings.append("high_epoch_empty_retrieval_ratio")
    unknown_empty_outcome_count = empty_by_retrieval_outcome.get("unknown", 0) + empty_by_retrieval_outcome.get("", 0)
    unresolved_unknown_empty_outcome_count = empty_unknown_outcome_drilldown.get("adapter_payload_gap", 0)
    classified_missing_outcome_count = max(0, unknown_empty_outcome_count - unresolved_unknown_empty_outcome_count)
    if unresolved_unknown_empty_outcome_count:
        dominant_blocker = "adapter_payload_gap"
        classification_confidence = "partial" if classified_missing_outcome_count else "low"
        metadata_gap_next_action = (
            "Fix adapter payload metadata for unresolved empty observations before treating classified legacy gaps as reset-safe."
        )
    elif unknown_empty_outcome_count:
        dominant_blocker = "classified_legacy_missing_outcome"
        classification_confidence = "classified"
        metadata_gap_next_action = "Collect more fresh metadata-rich dogfood before telemetry reset; no adapter payload gap detected."
    else:
        dominant_blocker = "none"
        classification_confidence = "complete"
        metadata_gap_next_action = "No unknown empty-retrieval outcome metadata gap detected."
    if unresolved_unknown_empty_outcome_count:
        warnings.append("epoch_empty_retrieval_outcome_unknown")
    elif unknown_empty_outcome_count:
        warnings.append("epoch_empty_retrieval_outcome_metadata_gap_classified")

    ready_for_reset_avoidance = bool(
        observation_count
        and trace_count
        and observation_trace_coverage_ratio >= min_trace_coverage
        and not unknown_empty_outcome_count
    )
    decision = "fresh_epoch_ready_to_compare_against_historical" if ready_for_reset_avoidance else "continue_fresh_epoch_dogfooding"

    payload = {
        "kind": "dogfood_fresh_epoch_readiness",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "database": {"path": str(db_path), "exists": True},
        "epoch": {
            "started_at": epoch_start,
            "historical_rows_excluded": historical_excluded,
            "latest_created_at": latest_created_at,
        },
        "thresholds": {
            "min_trace_coverage": min_trace_coverage,
            "min_evidence_count": min_evidence_count,
            "high_empty_threshold": args.high_empty_threshold,
        },
        "coverage": {
            "observation_count": observation_count,
            "trace_count": trace_count,
            "activation_count": activation_count,
            "observations_linked_from_traces": len(linked_observation_ids),
            "observation_trace_coverage_ratio": observation_trace_coverage_ratio,
        },
        "coverage_diagnostics": {
            "unlinked_observation_count": unlinked_observation_count,
            "trace_without_observation_link_count": trace_without_observation_link_count,
            "activation_count": activation_count,
            "activations_linked_to_traces": activations_linked_to_traces,
            "activation_trace_link_coverage_ratio": activation_trace_link_coverage_ratio,
            "likely_gap": "no_linkage_gap_detected"
            if not unlinked_observation_count and not trace_without_observation_link_count
            else "fresh_epoch_linkage_gap_detected",
        },
        "empty_retrieval_diagnostics": {
            "count": empty_retrieval_count,
            "ratio": empty_retrieval_ratio,
            "by_response_mode": {key: empty_by_response_mode[key] for key in sorted(empty_by_response_mode)},
            "by_retrieval_outcome": {key: empty_by_retrieval_outcome[key] for key in sorted(empty_by_retrieval_outcome)},
            "by_likely_cause": {key: empty_by_likely_cause[key] for key in sorted(empty_by_likely_cause)},
            "unknown_outcome_drilldown": {
                "count": unknown_empty_outcome_count,
                "unresolved_count": unresolved_unknown_empty_outcome_count,
                "by_likely_cause": {
                    key: empty_unknown_outcome_drilldown[key] for key in sorted(empty_unknown_outcome_drilldown)
                },
                "classification_rule": "metadata-only aggregate inference from hook_event_name and response_mode",
                "next_action": "Prefer more v0.1.129+ dogfood or a targeted metadata backfill preview before telemetry reset.",
            },
            "metadata_gap_diagnostic": {
                "unknown_empty_outcome_count": unknown_empty_outcome_count,
                "unresolved_adapter_payload_gap_count": unresolved_unknown_empty_outcome_count,
                "classified_missing_outcome_count": classified_missing_outcome_count,
                "dominant_blocker": dominant_blocker,
                "classification_confidence": classification_confidence,
                "next_action": metadata_gap_next_action,
            },
            "by_hook_event_name": {key: empty_by_hook_event_name[key] for key in sorted(empty_by_hook_event_name)},
            "by_surface": {key: empty_by_surface[key] for key in sorted(empty_by_surface)},
            "by_scope": {key: empty_by_scope[key] for key in sorted(empty_by_scope)},
        },
        "trace_distribution": {
            "event_kind_counts": dict(sorted(trace_event_kind_counts.items())),
            "surface_counts": dict(sorted(trace_surface_counts.items())),
            "retention_policy_counts": dict(sorted(trace_retention_counts.items())),
        },
        "candidate_signals": {
            "related_memory_ref_count": len(related_memory_ref_counter),
            "retrieved_memory_ref_count": len(retrieved_memory_ref_counter),
            "retrieved_memory_ref_repetition_count": sum(
                1 for count in retrieved_memory_ref_counter.values() if count >= min_evidence_count
            ),
        },
        "quality_gate": {
            "pass": ready_for_reset_avoidance,
            "decision": decision,
            "blocked_reasons": warnings,
        },
        "automation_policy": {
            "apply_supported": False,
            "telemetry_reset_apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "aggregate_only": True,
        },
        "suggested_next_steps": [
            "Use this epoch-filtered report before deleting telemetry; historical rows are excluded, not mutated.",
            "If fresh-epoch linkage is healthy but historical blockers remain, design telemetry-only reset as a separate preview/apply corridor.",
            "Keep broad G4 apply blocked until fresh-epoch empty retrievals and isolated decay-risk candidates are classified.",
        ],
        "warnings": warnings,
    }
    _write_json_report(args.output, payload)
    return payload



def _classify_g4_linkage_gap(
    *,
    observation_row: Any,
    trace_count: int,
    latest_trace_created_at: str | None,
    has_later_linked_observation: bool = False,
) -> tuple[str, str]:
    metadata = _safe_metadata_from_json(observation_row["metadata_json"])
    retrieval_outcome = str(metadata.get("retrieval_outcome") or "unknown")
    hook_event_name = str(metadata.get("hook_event_name") or "unknown")
    response_mode = str(observation_row["response_mode"] or "unknown")
    created_at = str(observation_row["created_at"])
    if retrieval_outcome in {"adapter_payload_gap", "query_scope_gap", "retrieval_disabled_or_unavailable"}:
        return "metadata_classification_gap", "empty observation carries adapter/scope payload-gap outcome metadata"
    if retrieval_outcome == "unknown" and hook_event_name in {"unknown", ""}:
        return "metadata_classification_gap", "empty observation is missing hook/outcome metadata needed for ref-safe linkage diagnosis"
    if retrieval_outcome == "unknown" and hook_event_name == "pre_llm_call" and response_mode == "unknown":
        return (
            "metadata_classification_gap",
            "hook observation is missing retrieval outcome/response mode metadata needed for ref-safe linkage diagnosis",
        )
    if retrieval_outcome == "unknown" and hook_event_name == "pre_llm_call" and response_mode == "verify_first":
        return "historical_or_rollout_telemetry", "legacy verify-first empty retrieval can be classified only by rollout-era metadata"
    if not trace_count:
        return "hook_runtime_linkage_bug", "fresh observations exist but no fresh trace rows were recorded"
    if has_later_linked_observation:
        return "historical_or_rollout_telemetry", "older unlinked observation is followed by later linked hook telemetry in the same selected epoch/window"
    if latest_trace_created_at is not None and created_at > latest_trace_created_at:
        return "expected_race_or_window_artifact", "latest observation is newer than the latest trace in the selected epoch/window"
    if retrieval_outcome == "no_reliable_memory":
        return "hook_runtime_linkage_bug", "expected negative-evidence observation was not linked from any metadata-only trace"
    return "hook_runtime_linkage_bug", "observation falls inside a traced epoch but is absent from trace related_observation_ids"



def _dogfood_g4_linkage_gap_diagnose_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    epoch_start = _parse_epoch_start(args.epoch_start)
    surface_filter = args.surface
    if not db_path.exists():
        payload = {
            "kind": "g4_linkage_gap_diagnosis",
            "read_only": True,
            "mutated": False,
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }
        _write_json_report(args.output, payload)
        return payload

    with _open_readonly_sqlite(db_path) as connection:
        surface_clause = "AND surface = ?" if surface_filter else ""
        params: tuple[Any, ...] = (epoch_start, surface_filter) if surface_filter else (epoch_start,)
        observation_rows = (
            connection.execute(
                f"""
                SELECT id, created_at, surface, preferred_scope, retrieved_memory_refs_json, response_mode, metadata_json
                FROM retrieval_observations
                WHERE datetime(created_at) >= datetime(?) {surface_clause}
                ORDER BY datetime(created_at) ASC, id ASC
                """,
                params,
            ).fetchall()
            if _table_exists(connection, "retrieval_observations")
            else []
        )
        trace_rows = (
            connection.execute(
                f"""
                SELECT id, created_at, surface, related_observation_ids_json, related_memory_refs_json
                FROM experience_traces
                WHERE datetime(created_at) >= datetime(?) {surface_clause}
                ORDER BY datetime(created_at) ASC, id ASC
                """,
                params,
            ).fetchall()
            if _table_exists(connection, "experience_traces")
            else []
        )
        activation_rows = (
            connection.execute(
                f"""
                SELECT id, created_at, surface, activation_kind, memory_ref, observation_id
                FROM memory_activations
                WHERE datetime(created_at) >= datetime(?) {surface_clause}
                ORDER BY datetime(created_at) ASC, id ASC
                """,
                params,
            ).fetchall()
            if _table_exists(connection, "memory_activations")
            else []
        )

    observation_ids = {int(row["id"]) for row in observation_rows}
    linked_observation_ids: set[int] = set()
    trace_without_observation_link_count = 0
    related_memory_ref_counter: Counter[str] = Counter()
    for row in trace_rows:
        related_ids = _safe_json_list_from_db(row["related_observation_ids_json"])
        if not related_ids:
            trace_without_observation_link_count += 1
        for observation_id in related_ids:
            if isinstance(observation_id, int):
                linked_observation_ids.add(observation_id)
        related_memory_ref_counter.update(str(ref) for ref in _safe_json_list_from_db(row["related_memory_refs_json"]))

    linked_observation_ids &= observation_ids
    unlinked_rows = [row for row in observation_rows if int(row["id"]) not in linked_observation_ids]
    activation_refs_by_observation: dict[int, list[str]] = defaultdict(list)
    activation_observation_ids: set[int] = set()
    for row in activation_rows:
        observation_id = row["observation_id"]
        if observation_id is None:
            continue
        observation_id = int(observation_id)
        activation_observation_ids.add(observation_id)
        activation_refs_by_observation[observation_id].append(f"activation:{row['id']}")

    latest_trace_created_at = max((str(row["created_at"]) for row in trace_rows), default=None)
    linked_observation_created_ats = [
        str(row["created_at"])
        for row in observation_rows
        if int(row["id"]) in linked_observation_ids
    ]
    classification_counts: Counter[str] = Counter()
    unlinked_details: list[dict[str, Any]] = []
    for row in unlinked_rows:
        created_at = str(row["created_at"])
        classification, classification_reason = _classify_g4_linkage_gap(
            observation_row=row,
            trace_count=len(trace_rows),
            latest_trace_created_at=latest_trace_created_at,
            has_later_linked_observation=any(linked_created_at > created_at for linked_created_at in linked_observation_created_ats),
        )
        classification_counts[classification] += 1
        metadata = _safe_metadata_from_json(row["metadata_json"])
        observation_id = int(row["id"])
        unlinked_details.append(
            {
                "observation_ref": f"observation:{observation_id}",
                "activation_refs": activation_refs_by_observation.get(observation_id, [])[:5],
                "created_at": str(row["created_at"]),
                "surface": str(row["surface"]),
                "response_mode": str(row["response_mode"] or "unknown"),
                "hook_event_name": str(metadata.get("hook_event_name") or "unknown"),
                "retrieval_outcome": str(metadata.get("retrieval_outcome") or "unknown"),
                "classification": classification,
                "classification_reason": classification_reason,
                "raw_content_included": False,
                "sample_values_included": False,
            }
        )

    latest_unlinked_observation = unlinked_details[-1] if unlinked_details else None
    unlinked_observation_count = len(unlinked_rows)
    only_resolved_rollout_telemetry = bool(unlinked_observation_count) and set(classification_counts) == {
        "historical_or_rollout_telemetry"
    }
    blocked_reasons = (
        ["resolved_rollout_telemetry_requires_review"]
        if only_resolved_rollout_telemetry
        else ["fresh_trace_linkage_gap_present"]
        if unlinked_observation_count
        else []
    )
    if classification_counts.get("hook_runtime_linkage_bug"):
        decision = "investigate_hook_runtime_linkage_before_g4_apply"
    elif classification_counts.get("metadata_classification_gap"):
        decision = "classify_or_backfill_metadata_before_g4_apply"
    elif only_resolved_rollout_telemetry:
        decision = "review_resolved_rollout_telemetry_before_g4_apply"
    elif classification_counts.get("expected_race_or_window_artifact") and len(classification_counts) == 1:
        decision = "collect_next_epoch_to_confirm_race_window_resolution"
    elif unlinked_observation_count:
        decision = "review_linkage_gap_classification_before_g4_apply"
    else:
        decision = "fresh_trace_linkage_gap_not_detected"

    payload = {
        "kind": "g4_linkage_gap_diagnosis",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "database": {"path": str(db_path), "exists": True},
        "filters": {"epoch_start": epoch_start, "surface": surface_filter},
        "coverage": {
            "observation_count": len(observation_rows),
            "trace_count": len(trace_rows),
            "activation_count": len(activation_rows),
            "linked_observation_count": len(linked_observation_ids),
            "unlinked_observation_count": unlinked_observation_count,
            "trace_without_observation_link_count": trace_without_observation_link_count,
            "activation_trace_link_coverage_ratio": round(
                len(activation_observation_ids & linked_observation_ids) / len(activation_observation_ids), 4
            )
            if activation_observation_ids
            else 0.0,
        },
        "classification_counts": {key: classification_counts[key] for key in sorted(classification_counts)},
        "latest_unlinked_observation": latest_unlinked_observation,
        "sample_unlinked_observations": unlinked_details[: min(5, len(unlinked_details))],
        "candidate_signals": {
            "related_memory_ref_count": len(related_memory_ref_counter),
            "linked_observation_refs": [f"observation:{value}" for value in sorted(linked_observation_ids)[:5]],
            "unlinked_observation_refs": [f"observation:{int(row['id'])}" for row in unlinked_rows[:5]],
        },
        "quality_gate": {
            "pass": not unlinked_observation_count,
            "decision": decision,
            "blocked_reasons": blocked_reasons,
        },
        "automation_policy": {
            "apply_supported": False,
            "telemetry_reset_apply_supported": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
        "suggested_next_steps": [
            "If hook_runtime_linkage_bug appears, inspect hook/runtime observation-to-trace propagation before any G4 apply.",
            "If only expected_race_or_window_artifact appears, compare the next fresh epoch before changing telemetry.",
            "If metadata_classification_gap or historical_or_rollout_telemetry appears, use a separate reviewed backfill/reset corridor; do not silently rewrite telemetry.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload



def _g4_review_queue_entry(
    *,
    queue_id: str,
    proposal_type: str,
    memory_ref: str | None,
    reason_codes: list[str],
    priority_score: float,
    evidence_refs: list[str],
    proposed_action: str,
    operator_commands: list[str],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        "queue_id": queue_id,
        "proposal_type": proposal_type,
        "proposed_action": proposed_action,
        "target_ref": memory_ref,
        "priority_score": round(priority_score, 4),
        "policy": {
            "requires_human_review": True,
            "auto_apply_allowed": False,
            "approval_required": True,
            "approval_phrase": "approve-g4-review-queue-item",
        },
        "reason_codes": reason_codes,
        "ref_safe_evidence": {
            "memory_ref": memory_ref,
            "evidence_refs": evidence_refs,
            "raw_content_included": False,
            "sample_values_included": False,
        },
        "audit_contract": {
            "required_fields": ["actor", "reason", "policy", "evidence_refs", "source_queue_id"],
            "status_before_required": True,
            "status_after_required": True,
            "rollback_hint_required": True,
        },
        "operator_commands": operator_commands,
        "metadata": metadata,
    }


def _g4_background_quality_warning_analysis(
    dry_run: dict[str, Any],
    *,
    queue_count: int,
    fresh_epoch: dict[str, Any] | None = None,
) -> dict[str, Any]:
    reports = dry_run.get("reports", {}) if isinstance(dry_run.get("reports"), dict) else {}
    candidates_report = reports.get("candidates", {}) if isinstance(reports.get("candidates"), dict) else {}
    activation_report = reports.get("activation_summary", {}) if isinstance(reports.get("activation_summary"), dict) else {}
    reinforcement_report = reports.get("reinforcement", {}) if isinstance(reports.get("reinforcement"), dict) else {}
    decay_report = reports.get("decay_risk", {}) if isinstance(reports.get("decay_risk"), dict) else {}
    scan = dry_run.get("scan", {}) if isinstance(dry_run.get("scan"), dict) else {}

    source_reports = {
        "scan": scan,
        "candidates": candidates_report,
        "activation_summary": activation_report,
        "reinforcement": reinforcement_report,
        "decay_risk": decay_report,
    }

    warning_sources: dict[str, list[str]] = defaultdict(list)
    for source_name, source_report in source_reports.items():
        warnings = source_report.get("quality_warnings", []) if isinstance(source_report, dict) else []
        if not isinstance(warnings, list):
            continue
        for warning in warnings:
            if warning:
                warning_sources[str(warning)].append(source_name)

    empty = activation_report.get("empty_retrieval", {}) if isinstance(activation_report.get("empty_retrieval"), dict) else {}
    by_outcome = empty.get("by_retrieval_outcome", {}) if isinstance(empty.get("by_retrieval_outcome"), dict) else {}
    trace_linkage = empty.get("trace_linkage", {}) if isinstance(empty.get("trace_linkage"), dict) else {}
    empty_count = _safe_int(empty.get("count"))
    unknown_outcome_count = _safe_int(by_outcome.get("unknown"))
    unlinked_trace_count = _safe_int(trace_linkage.get("unlinked_to_trace_count"))
    linked_trace_count = _safe_int(trace_linkage.get("linked_to_trace_count"))
    fresh_empty = (fresh_epoch or {}).get("empty_retrieval_diagnostics", {}) if isinstance(fresh_epoch, dict) else {}
    fresh_unknown = (fresh_empty.get("unknown_outcome_drilldown", {}) if isinstance(fresh_empty.get("unknown_outcome_drilldown"), dict) else {})
    fresh_unresolved_unknown = _safe_int(fresh_unknown.get("unresolved_count"))
    fresh_classified_unknown = max(0, _safe_int(fresh_unknown.get("count")) - fresh_unresolved_unknown)
    fresh_coverage = (fresh_epoch or {}).get("coverage_diagnostics", {}) if isinstance(fresh_epoch, dict) else {}
    fresh_unlinked_observations = _safe_int(fresh_coverage.get("unlinked_observation_count"))

    analyses: list[dict[str, Any]] = []
    blocking_reasons: list[str] = []
    for warning in sorted(warning_sources):
        severity = "diagnostic"
        gate_effect = "does_not_block_queue_preview"
        likely_causes: list[str] = []
        next_actions: list[str] = []
        ref_safe_metrics: dict[str, Any] = {}

        if warning == "high_empty_retrieval_activation_ratio":
            likely_causes = []
            historical_unknown_resolved = fresh_epoch is not None and fresh_unresolved_unknown == 0
            historical_trace_gap_resolved = fresh_epoch is not None and fresh_unlinked_observations == 0
            if unknown_outcome_count:
                if historical_unknown_resolved:
                    likely_causes.append("historical_or_classified_empty_retrieval_outcome_rows")
                else:
                    likely_causes.append("unknown_empty_retrieval_outcome_rows")
                    blocking_reasons.append("background_empty_retrieval_outcome_unknown")
            if unlinked_trace_count:
                if historical_trace_gap_resolved:
                    likely_causes.append("historical_empty_retrieval_observation_trace_gap")
                else:
                    likely_causes.append("empty_retrieval_observations_missing_trace_links")
                    blocking_reasons.append("background_empty_retrieval_trace_linkage_gap")
            if _safe_int(by_outcome.get("no_reliable_memory")):
                likely_causes.append("expected_no_reliable_memory_negative_evidence")
            if not likely_causes:
                likely_causes.append("classified_empty_retrieval_negative_evidence")
            blocking = (unknown_outcome_count and not historical_unknown_resolved) or (unlinked_trace_count and not historical_trace_gap_resolved)
            severity = "blocking" if blocking else "diagnostic"
            gate_effect = "blocks_until_unknown_or_unlinked_empty_evidence_is_resolved" if severity == "blocking" else "diagnostic_only_after_fresh_epoch_resolution"
            ref_safe_metrics = {
                "empty_retrieval_count": empty_count,
                "empty_retrieval_ratio": round(_safe_float(empty.get("ratio")), 4),
                "by_retrieval_outcome": {str(key): _safe_int(value) for key, value in sorted(by_outcome.items())},
                "trace_linkage": {
                    "linked_to_trace_count": linked_trace_count,
                    "unlinked_to_trace_count": unlinked_trace_count,
                },
                "fresh_epoch_comparison": {
                    "enabled": fresh_epoch is not None,
                    "fresh_unresolved_unknown_empty_outcome_count": fresh_unresolved_unknown,
                    "fresh_classified_unknown_empty_outcome_count": fresh_classified_unknown,
                    "fresh_unlinked_observation_count": fresh_unlinked_observations,
                    "reset_resolution_hint": "historical_telemetry_resolved_by_fresh_epoch_or_reset"
                    if fresh_epoch is not None and fresh_unresolved_unknown == 0 and fresh_unlinked_observations == 0 else "collect_more_classified_fresh_epoch_evidence",
                },
                "sample_activation_ids": empty.get("sample_activation_ids", [])[:5] if isinstance(empty.get("sample_activation_ids"), list) else [],
                "sample_observation_ids": empty.get("sample_observation_ids", [])[:5] if isinstance(empty.get("sample_observation_ids"), list) else [],
                "raw_content_included": False,
                "sample_values_included": False,
            }
            next_actions = [
                "Prefer fresh-epoch or telemetry-reset-preview comparison before any apply path.",
                "Resolve unknown retrieval outcomes by collecting new classified hook data or retiring historical telemetry only through a separate reviewed reset corridor.",
                "Resolve trace-linkage gaps before treating empty-retrieval volume as safe negative evidence.",
            ]
        elif warning == "no_clusters_meet_min_evidence":
            severity = "blocking" if queue_count == 0 else "diagnostic"
            gate_effect = "blocks_when_no_queue_candidates_exist" if queue_count == 0 else "does_not_block_when_review_queue_has_candidates"
            if severity == "blocking":
                blocking_reasons.append("background_cluster_signal_below_threshold")
            likely_causes = ["trace_clusters_below_min_evidence"]
            ref_safe_metrics = {
                "trace_count": _safe_int(candidates_report.get("trace_count")),
                "candidate_count": _safe_int(candidates_report.get("candidate_count")),
                "min_evidence": _safe_int(candidates_report.get("min_evidence")),
                "queue_count": queue_count,
            }
            next_actions = ["Collect more metadata-only traces or lower thresholds only with a RED-tested plan."]
        elif warning in {"low_activation_count", "low_observation_count"}:
            severity = "blocking" if queue_count == 0 else "diagnostic"
            gate_effect = "blocks_when_evidence_is_too_sparse_for_queue" if queue_count == 0 else "does_not_block_existing_review_queue_preview"
            if severity == "blocking":
                blocking_reasons.append("background_evidence_volume_below_threshold")
            likely_causes = ["bounded_recent_window_sparse"]
            ref_safe_metrics = {
                "activation_count": _safe_int(activation_report.get("activation_count")),
                "queue_count": queue_count,
            }
            next_actions = ["Collect more dogfood runs and compare aggregate trends."]
        elif warning in {"no_activations", "no_observations", "no_traces"}:
            severity = "blocking"
            gate_effect = "blocks_until_required_telemetry_exists"
            blocking_reasons.append(f"background_{warning}")
            likely_causes = ["required_telemetry_missing"]
            ref_safe_metrics = {
                "activation_count": _safe_int(activation_report.get("activation_count")),
                "trace_count": _safe_int(candidates_report.get("trace_count")),
                "queue_count": queue_count,
            }
            next_actions = ["Verify Hermes hook/runtime telemetry writes before queue persistence planning."]
        else:
            severity = "blocking"
            gate_effect = "blocks_until_warning_is_explicitly_classified"
            blocking_reasons.append("background_unclassified_quality_warning")
            likely_causes = ["unclassified_background_warning"]
            next_actions = ["Add a ref-safe classifier for this warning before reducing the gate."]

        analyses.append(
            {
                "warning": warning,
                "sources": sorted(set(warning_sources[warning])),
                "severity": severity,
                "gate_effect": gate_effect,
                "likely_causes": likely_causes,
                "ref_safe_metrics": ref_safe_metrics,
                "next_actions": next_actions,
            }
        )

    unique_blocking = sorted(set(blocking_reasons))
    return {
        "kind": "g4_background_quality_warning_analysis",
        "aggregate_or_ref_only": True,
        "raw_content_included": False,
        "raw_query_text_included": False,
        "raw_trace_summary_included": False,
        "sample_values_included": False,
        "warning_count": len(warning_sources),
        "blocking_warning_count": sum(1 for item in analyses if item["severity"] == "blocking"),
        "diagnostic_warning_count": sum(1 for item in analyses if item["severity"] == "diagnostic"),
        "blocking_reasons": unique_blocking,
        "warnings": analyses,
    }


def _read_g4_gate_artifact(path: Path | None, expected_kind: str) -> dict[str, Any]:
    if path is None:
        return {"provided": False, "path": None, "kind": None, "pass": False, "blocked_reasons": ["artifact_not_provided"]}
    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:
        return {
            "provided": True,
            "path": str(path),
            "kind": None,
            "pass": False,
            "blocked_reasons": ["artifact_unreadable"],
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(payload, dict):
        return {
            "provided": True,
            "path": str(path),
            "kind": None,
            "pass": False,
            "blocked_reasons": ["artifact_not_json_object"],
        }
    blocked_reasons: list[str] = []
    if payload.get("kind") != expected_kind:
        blocked_reasons.append("artifact_kind_mismatch")
    if payload.get("read_only") is not True:
        blocked_reasons.append("artifact_not_read_only")
    if payload.get("mutated") is True:
        blocked_reasons.append("artifact_claims_mutation")
    if payload.get("default_retrieval_unchanged") is False:
        blocked_reasons.append("default_retrieval_changed")
    privacy = payload.get("privacy", {}) if isinstance(payload.get("privacy"), dict) else {}
    if any(
        privacy.get(flag) is True
        for flag in (
            "raw_conversation_content_included",
            "raw_query_text_included",
            "raw_trace_summary_included",
            "sample_values_included",
        )
    ):
        blocked_reasons.append("privacy_flag_claims_raw_content")

    if expected_kind == "dogfood_retrieval_ranking_experiment":
        shadow = payload.get("shadow_compare", {}) if isinstance(payload.get("shadow_compare"), dict) else {}
        fixture = payload.get("fixture_expansion", {}) if isinstance(payload.get("fixture_expansion"), dict) else {}
        if _safe_int(fixture.get("task_count")) < 1:
            blocked_reasons.append("ranking_fixture_empty")
        if fixture.get("live_runtime_safe") is False:
            blocked_reasons.append("ranking_fixture_not_live_runtime_safe")
        if _safe_int(shadow.get("baseline_regression_count")) != 0:
            blocked_reasons.append("ranking_baseline_regression_present")
        if shadow.get("protected_default_order_returned") is False:
            blocked_reasons.append("ranking_default_order_not_protected")
        if shadow.get("durable_memory_mutated") is True:
            blocked_reasons.append("ranking_artifact_claims_durable_mutation")
    else:
        quality_gate = payload.get("quality_gate", {}) if isinstance(payload.get("quality_gate"), dict) else {}
        if quality_gate.get("pass") is not True:
            blocked_reasons.append("quality_gate_not_green")
        blocked_reasons.extend(str(reason) for reason in quality_gate.get("blocked_reasons", []) if reason)

    return {
        "provided": True,
        "path": str(path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "kind": payload.get("kind"),
        "pass": not blocked_reasons,
        "blocked_reasons": sorted(set(blocked_reasons)),
    }


def _g4_artifact_gate_evidence(args: argparse.Namespace) -> dict[str, Any]:
    reports = {
        "retrieval_ranking_gate_pass": _read_g4_gate_artifact(
            getattr(args, "retrieval_ranking_report", None), "dogfood_retrieval_ranking_experiment"
        ),
        "rollback_confidence_pass": _read_g4_gate_artifact(
            getattr(args, "rollback_confidence_report", None), "dogfood_rollback_confidence"
        ),
        "rollback_replay_validate_pass": _read_g4_gate_artifact(
            getattr(args, "rollback_replay_report", None), "dogfood_rollback_replay_validate"
        ),
        "live_telemetry_reconciliation_pass": _read_g4_gate_artifact(
            getattr(args, "telemetry_reconciliation_report", None), "dogfood_telemetry_reconciliation"
        ),
    }
    human_approval_report = _read_g4_gate_artifact(
        getattr(args, "human_review_approval_report", None), "dogfood_g4_review_queue_approval_report"
    )
    gate_evidence = {key: report["pass"] is True for key, report in reports.items()}
    gate_evidence["human_review_queue_approval_pass"] = human_approval_report["pass"] is True
    missing = sorted(key for key, report in reports.items() if not report.get("provided"))
    failed = sorted(key for key, report in reports.items() if report.get("provided") and report.get("pass") is not True)
    artifact_reports: dict[str, Any] = dict(reports)
    if human_approval_report.get("provided"):
        artifact_reports["human_review_queue_approval_pass"] = human_approval_report
        if human_approval_report.get("pass") is not True:
            failed.append("human_review_queue_approval_pass")
    return {
        "artifact_reports": artifact_reports,
        "artifact_gate_evidence": gate_evidence,
        "missing_gate_artifacts": missing,
        "failed_gate_artifacts": sorted(set(failed)),
        "provided_gate_artifacts_pass": not missing and not failed,
        "human_review_queue_approval_source": "artifact" if human_approval_report.get("provided") else "not_supported_by_preview",
    }


def _dogfood_g4_review_queue_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.limit < 1:
        raise ValueError("dogfood g4-review-queue-preview limit must be >= 1")
    if args.top < 1:
        raise ValueError("dogfood g4-review-queue-preview top must be >= 1")
    if args.min_evidence_count < 1:
        raise ValueError("dogfood g4-review-queue-preview min-evidence-count must be >= 1")
    if args.frequent_threshold < 1:
        raise ValueError("dogfood g4-review-queue-preview frequent-threshold must be >= 1")

    lock_path = args.lock_path or args.db_path.with_suffix(".g4-review-queue-preview.lock")
    fresh_epoch_report = None
    if getattr(args, "epoch_start", None):
        fresh_epoch_report = _dogfood_fresh_epoch_payload(
            argparse.Namespace(
                db_path=args.db_path,
                epoch_start=args.epoch_start,
                output=None,
                min_trace_coverage=0.25,
                min_evidence_count=args.min_evidence_count,
                high_empty_threshold=0.5,
            )
        )
    dry_run = _consolidation_background_dry_run_report(
        args.db_path,
        limit=args.limit,
        top=args.top,
        min_evidence=args.min_evidence_count,
        frequent_threshold=args.frequent_threshold,
        output_path=None,
        lock_path=lock_path,
    )
    reports = dry_run.get("reports", {}) if isinstance(dry_run.get("reports"), dict) else {}
    reinforcement_report = reports.get("reinforcement", {}) if isinstance(reports.get("reinforcement"), dict) else {}
    decay_report = reports.get("decay_risk", {}) if isinstance(reports.get("decay_risk"), dict) else {}

    queue_entries: list[dict[str, Any]] = []
    for index, candidate in enumerate(reinforcement_report.get("reinforcement_candidates", [])[: args.queue_limit], start=1):
        if not isinstance(candidate, dict):
            continue
        memory_ref = candidate.get("memory_ref")
        activation_ids = [f"activation:{value}" for value in candidate.get("sample_activation_ids", [])]
        observation_ids = [f"observation:{value}" for value in candidate.get("sample_observation_ids", [])]
        reason_codes = ["reinforcement_review_candidate"] + [str(value) for value in candidate.get("signals", [])]
        queue_entries.append(
            _g4_review_queue_entry(
                queue_id=f"g4-review:reinforcement:{index}",
                proposal_type="reinforcement_review",
                memory_ref=str(memory_ref) if memory_ref is not None else None,
                reason_codes=reason_codes,
                priority_score=float(candidate.get("score", 0.0) or 0.0),
                evidence_refs=activation_ids + observation_ids,
                proposed_action="review_reinforcement_signal_only",
                operator_commands=[
                    f"agent-memory activations summary {args.db_path} --memory-ref {memory_ref}",
                    f"agent-memory review explain {str(memory_ref).split(':', 1)[0]} {args.db_path} {str(memory_ref).split(':', 1)[1]}"
                    if isinstance(memory_ref, str) and ':' in memory_ref
                    else f"agent-memory graph inspect {args.db_path} {memory_ref} --depth 1",
                ],
                metadata={
                    "score": candidate.get("score"),
                    "activation_count": candidate.get("activation_count"),
                    "current_status": candidate.get("current_status"),
                },
            )
        )

    remaining_slots = max(0, args.queue_limit - len(queue_entries))
    for index, candidate in enumerate(decay_report.get("decay_risk_candidates", [])[:remaining_slots], start=1):
        if not isinstance(candidate, dict):
            continue
        memory_ref = candidate.get("memory_ref")
        ref_safe = candidate.get("ref_safe_evidence", {}) if isinstance(candidate.get("ref_safe_evidence"), dict) else {}
        evidence_refs = [
            f"activation:{value}" for value in ref_safe.get("sample_activation_ids", [])
        ] + [f"observation:{value}" for value in ref_safe.get("sample_observation_ids", [])]
        queue_entries.append(
            _g4_review_queue_entry(
                queue_id=f"g4-review:decay-risk:{index}",
                proposal_type="decay_risk_review",
                memory_ref=str(memory_ref) if memory_ref is not None else None,
                reason_codes=["decay_risk_review_candidate"] + [str(value) for value in candidate.get("signals", [])],
                priority_score=float(candidate.get("score", 0.0) or 0.0),
                evidence_refs=evidence_refs,
                proposed_action=str(candidate.get("resolution_hint") or "review_decay_risk_signal_only"),
                operator_commands=(candidate.get("review_support", {}) or {}).get("operator_commands", [])
                if isinstance(candidate.get("review_support"), dict)
                else [f"agent-memory graph inspect {args.db_path} {memory_ref} --depth 1"],
                metadata={
                    "score": candidate.get("score"),
                    "current_status": candidate.get("current_status"),
                    "resolution_hint": candidate.get("resolution_hint"),
                },
            )
        )

    warning_analysis = _g4_background_quality_warning_analysis(
        dry_run,
        queue_count=len(queue_entries),
        fresh_epoch=fresh_epoch_report,
    )
    blocked_reasons: list[str] = []
    if dry_run.get("status") != "completed":
        blocked_reasons.append("background_dry_run_not_completed")
    if not queue_entries:
        blocked_reasons.append("no_review_queue_candidates")
    blocked_reasons.extend(str(reason) for reason in warning_analysis.get("blocking_reasons", []))
    blocked_reasons = sorted(set(blocked_reasons))
    broad_g4_required_green_gates = [
        "retrieval_ranking_gate_pass",
        "rollback_confidence_pass",
        "rollback_replay_validate_pass",
        "live_telemetry_reconciliation_pass",
        "human_review_queue_approval_pass",
    ]
    artifact_gate_evidence = _g4_artifact_gate_evidence(args)
    broad_g4_decision = (
        "broad_g4_apply_still_blocked_pending_separate_apply_corridor"
        if artifact_gate_evidence["provided_gate_artifacts_pass"]
        and artifact_gate_evidence["artifact_gate_evidence"].get("human_review_queue_approval_pass") is True
        and not blocked_reasons
        else "broad_g4_apply_still_blocked_pending_explicit_human_queue_approval"
        if artifact_gate_evidence["provided_gate_artifacts_pass"] and not blocked_reasons
        else "broad_g4_apply_still_blocked_until_all_live_safety_gates_pass"
    )

    payload = {
        "kind": "dogfood_g4_review_queue_preview",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(args.db_path),
        "mode": "preview_only",
        "queue_contract_version": 1,
        "background_dry_run_status": dry_run.get("status"),
        "fresh_epoch_comparison_enabled": fresh_epoch_report is not None,
        "candidate_sources": ["reinforcement_candidates", "decay_risk_candidates"],
        "queue_limit": args.queue_limit,
        "queue_count": len(queue_entries),
        "queue": queue_entries,
        "background_quality_warning_analysis": warning_analysis,
        "quality_gate": {
            "pass": not blocked_reasons,
            "decision": "review_queue_ready_for_manual_review" if not blocked_reasons else "continue_read_only_dogfood_before_review_queue",
            "blocked_reasons": blocked_reasons,
        },
        "broad_g4_apply_reassessment": {
            "broad_g4_apply_allowed": False,
            "decision": broad_g4_decision,
            "required_green_gates": broad_g4_required_green_gates,
            "current_report_green": not blocked_reasons,
            "default_retrieval_unchanged": True,
            "ordinary_conversation_auto_approval": False,
            **artifact_gate_evidence,
        },
        "automation_policy": {
            "apply_supported": False,
            "queue_persistence_supported": False,
            "ordinary_conversation_auto_approval": False,
            "requires_human_review": True,
            "default_retrieval_policy": "approved_only_unchanged",
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "sample_values_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "aggregate_or_ref_only": True,
        },
        "suggested_next_steps": [
            "Review queue entries manually; this command never persists or applies queue items.",
            "Promote only through explicit follow-up commands that require actor, reason, policy, and evidence refs.",
            "Keep broad G4 apply blocked until review queue persistence and rollback contracts have separate tests.",
        ],
    }
    _write_json_report(args.output, payload)
    return payload


def _ensure_g4_review_queue_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS g4_review_queue_items (
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


def _dogfood_g4_review_queue_persist_payload(args: argparse.Namespace) -> dict[str, Any]:
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood g4-review-queue-persist requires non-empty --actor and --reason")
    preview = _dogfood_g4_review_queue_preview_payload(
        argparse.Namespace(
            db_path=args.db_path,
            limit=args.limit,
            top=args.top,
            queue_limit=args.queue_limit,
            min_evidence_count=args.min_evidence_count,
            frequent_threshold=args.frequent_threshold,
            epoch_start=args.epoch_start,
            retrieval_ranking_report=None,
            rollback_confidence_report=None,
            rollback_replay_report=None,
            telemetry_reconciliation_report=None,
            human_review_approval_report=None,
            output=None,
            lock_path=args.lock_path,
        )
    )
    source_preview_sha256 = hashlib.sha256(json.dumps(preview, sort_keys=True).encode("utf-8")).hexdigest()
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    inserted = 0
    existing = 0
    queue = preview.get("queue", []) if isinstance(preview.get("queue"), list) else []
    with sqlite3.connect(args.db_path) as connection:
        _ensure_g4_review_queue_table(connection)
        for entry in queue:
            if not isinstance(entry, dict):
                continue
            queue_id = str(entry.get("queue_id") or "")
            if not queue_id:
                continue
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO g4_review_queue_items (
                    queue_id, status, proposal_type, target_ref, proposal_json, source_preview_sha256, actor, reason_sha256, audit_json
                ) VALUES (?, 'pending', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    str(entry.get("proposal_type") or "unknown"),
                    entry.get("target_ref"),
                    json.dumps(entry, sort_keys=True),
                    source_preview_sha256,
                    args.actor.strip(),
                    reason_sha256,
                    json.dumps([{"action": "persist", "actor": args.actor.strip(), "reason_sha256": reason_sha256}]),
                ),
            )
            if connection.total_changes > before:
                inserted += 1
            else:
                existing += 1
    payload = {
        "kind": "dogfood_g4_review_queue_persist",
        "read_only": False,
        "mutated": inserted > 0,
        "default_retrieval_unchanged": True,
        "apply_supported": False,
        "queue_persistence_supported": True,
        "db_path": str(args.db_path),
        "source_preview_sha256": source_preview_sha256,
        "queue_count": len(queue),
        "inserted_count": inserted,
        "existing_count": existing,
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "reason_stored_as_sha256": True,
        },
        "quality_gate": preview.get("quality_gate", {}),
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_g4_review_queue_list_payload(args: argparse.Namespace) -> dict[str, Any]:
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_g4_review_queue_table(connection)
        rows = connection.execute(
            """
            SELECT queue_id, status, proposal_type, target_ref, source_preview_sha256, created_at, updated_at
            FROM g4_review_queue_items
            WHERE (? IS NULL OR status = ?)
            ORDER BY created_at DESC, queue_id
            LIMIT ?
            """,
            (args.status, args.status, args.limit),
        ).fetchall()
    return {
        "kind": "dogfood_g4_review_queue_list",
        "read_only": True,
        "mutated": False,
        "db_path": str(args.db_path),
        "count": len(rows),
        "items": [dict(row) for row in rows],
        "privacy": {
            "proposal_json_included": False,
            "raw_content_included": False,
            "sample_values_included": False,
        },
    }


def _dogfood_g4_review_queue_update_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.status not in {"approved", "rejected"}:
        raise ValueError("dogfood g4-review-queue-update status must be approved or rejected")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood g4-review-queue-update requires non-empty --actor and --reason")
    policy = args.policy or "g4-review-queue-transition-v1"
    expected_phrase = f"{args.status}-g4-review-queue-item-v1"
    if args.approval_phrase is not None and args.approval_phrase != expected_phrase:
        raise ValueError(f"dogfood g4-review-queue-update requires --approval-phrase {expected_phrase} when provided")
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_g4_review_queue_table(connection)
        row = connection.execute(
            "SELECT status, proposal_type, target_ref, source_preview_sha256, audit_json FROM g4_review_queue_items WHERE queue_id = ?",
            (args.queue_id,),
        ).fetchone()
        if row is None:
            raise ValueError(f"review queue item not found: {args.queue_id}")
        status_before = row["status"]
        audit = _safe_json_list_from_db(row["audit_json"])
        audit.append({
            "action": args.status,
            "actor": args.actor.strip(),
            "policy": policy,
            "reason_sha256": reason_sha256,
            "source_queue_id": args.queue_id,
            "status_before": status_before,
            "status_after": args.status,
            "target_ref": row["target_ref"],
            "source_preview_sha256": row["source_preview_sha256"],
        })
        connection.execute(
            """
            UPDATE g4_review_queue_items
            SET status = ?, updated_at = CURRENT_TIMESTAMP, actor = ?, reason_sha256 = ?, audit_json = ?
            WHERE queue_id = ?
            """,
            (args.status, args.actor.strip(), reason_sha256, json.dumps(audit, sort_keys=True), args.queue_id),
        )
    return {
        "kind": "dogfood_g4_review_queue_update",
        "read_only": False,
        "mutated": status_before != args.status,
        "default_retrieval_unchanged": True,
        "apply_supported": False,
        "queue_id": args.queue_id,
        "status_before": status_before,
        "status_after": args.status,
        "status": args.status,
        "policy": policy,
        "approval_phrase_matched": args.approval_phrase == expected_phrase if args.approval_phrase is not None else None,
        "reason_sha256": reason_sha256,
        "ref_safe_audit": {
            "target_ref": row["target_ref"],
            "proposal_type": row["proposal_type"],
            "source_preview_sha256": row["source_preview_sha256"],
            "raw_content_included": False,
            "sample_values_included": False,
        },
        "privacy": {"raw_reason_included": False, "raw_content_included": False, "sample_values_included": False},
    }


def _dogfood_g4_review_queue_approval_report_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy = "g4-review-queue-approval-artifact-v1"
    approval_phrase = "report-approved-g4-review-queue-v1"
    if args.policy != policy:
        raise ValueError(f"dogfood g4-review-queue-approval-report requires --policy {policy}")
    if args.approval_phrase != approval_phrase:
        raise ValueError(f"dogfood g4-review-queue-approval-report requires --approval-phrase {approval_phrase}")
    if not args.actor.strip():
        raise ValueError("dogfood g4-review-queue-approval-report requires non-empty --actor")

    with sqlite3.connect(args.db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_g4_review_queue_table(connection)
        rows = connection.execute(
            """
            SELECT queue_id, status, proposal_type, target_ref, source_preview_sha256, actor, reason_sha256, updated_at
            FROM g4_review_queue_items
            ORDER BY queue_id
            """
        ).fetchall()

    status_counts = Counter(str(row["status"]) for row in rows)
    actor_counts = Counter(str(row["actor"]) for row in rows)
    proposal_type_counts = Counter(str(row["proposal_type"]) for row in rows)
    total_count = len(rows)
    approved_count = status_counts.get("approved", 0)
    rejected_count = status_counts.get("rejected", 0)
    pending_count = status_counts.get("pending", 0)
    reviewed_count = approved_count + rejected_count
    blocked_reasons: list[str] = []
    if total_count == 0:
        blocked_reasons.append("review_queue_empty")
    if pending_count > 0:
        blocked_reasons.append("pending_review_queue_items_present")
    elif reviewed_count != total_count:
        blocked_reasons.append("unreviewed_queue_items_present")
    if approved_count == 0:
        blocked_reasons.append("no_approved_queue_items")

    human_review_queue_approval_pass = not blocked_reasons
    decision = (
        "human_review_queue_approval_artifact_green"
        if human_review_queue_approval_pass
        else "human_review_queue_still_has_pending_items"
        if pending_count > 0
        else "human_review_queue_not_ready_for_apply_gate"
    )
    payload = {
        "kind": "dogfood_g4_review_queue_approval_report",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "apply_supported": False,
        "db_path": str(args.db_path),
        "policy": policy,
        "approval_phrase_matched": True,
        "actor": args.actor.strip(),
        "human_review_queue_approval_pass": human_review_queue_approval_pass,
        "queue_summary": {
            "total_count": total_count,
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "pending_count": pending_count,
            "reviewed_count": reviewed_count,
        },
        "status_counts": {key: status_counts[key] for key in sorted(status_counts)},
        "proposal_type_counts": {key: proposal_type_counts[key] for key in sorted(proposal_type_counts)},
        "review_actor_counts": {key: actor_counts[key] for key in sorted(actor_counts)},
        "source_preview_sha256s": sorted({str(row["source_preview_sha256"]) for row in rows}),
        "approved_queue_refs": [
            {
                "queue_id": row["queue_id"],
                "proposal_type": row["proposal_type"],
                "target_ref": row["target_ref"],
                "source_preview_sha256": row["source_preview_sha256"],
            }
            for row in rows
            if row["status"] == "approved"
        ],
        "quality_gate": {
            "pass": human_review_queue_approval_pass,
            "decision": decision,
            "blocked_reasons": sorted(set(blocked_reasons)),
        },
        "privacy": {
            "proposal_json_included": False,
            "raw_content_included": False,
            "raw_reason_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
        "next_step": "Use this artifact as the human_review_queue_approval_pass input to preview reassessment; do not apply from this report.",
    }
    _write_json_report(args.output, payload)
    return payload


def _read_g4_preview_readiness_artifact(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"provided": False, "path": None, "pass": False, "blocked_reasons": ["queue_preview_report_not_provided"]}
    try:
        raw_text = path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:
        return {
            "provided": True,
            "path": str(path),
            "pass": False,
            "blocked_reasons": ["queue_preview_report_unreadable"],
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(payload, dict):
        return {
            "provided": True,
            "path": str(path),
            "pass": False,
            "blocked_reasons": ["queue_preview_report_not_json_object"],
        }

    blocked_reasons: list[str] = []
    if payload.get("kind") != "dogfood_g4_review_queue_preview":
        blocked_reasons.append("queue_preview_kind_mismatch")
    if payload.get("read_only") is not True:
        blocked_reasons.append("queue_preview_not_read_only")
    if payload.get("mutated") is True:
        blocked_reasons.append("queue_preview_claims_mutation")
    if payload.get("default_retrieval_unchanged") is False:
        blocked_reasons.append("queue_preview_default_retrieval_changed")
    if _safe_int(payload.get("queue_count")) < 1:
        blocked_reasons.append("queue_preview_empty")

    quality_gate = payload.get("quality_gate", {}) if isinstance(payload.get("quality_gate"), dict) else {}
    if quality_gate.get("pass") is not True:
        blocked_reasons.append("queue_preview_quality_gate_not_green")
    blocked_reasons.extend(str(reason) for reason in quality_gate.get("blocked_reasons", []) if reason)

    privacy = payload.get("privacy", {}) if isinstance(payload.get("privacy"), dict) else {}
    if any(
        privacy.get(flag) is True
        for flag in (
            "raw_conversation_content_included",
            "raw_query_text_included",
            "raw_trace_summary_included",
            "raw_content_included",
            "sample_values_included",
        )
    ):
        blocked_reasons.append("queue_preview_privacy_flag_claims_raw_content")

    reassessment = payload.get("broad_g4_apply_reassessment", {}) if isinstance(payload.get("broad_g4_apply_reassessment"), dict) else {}
    if reassessment.get("broad_g4_apply_allowed") is not False:
        blocked_reasons.append("queue_preview_claims_broad_apply_allowed")
    if reassessment.get("current_report_green") is not True:
        blocked_reasons.append("queue_preview_current_report_not_green")
    if reassessment.get("provided_gate_artifacts_pass") is not True:
        blocked_reasons.append("queue_preview_artifact_gates_not_green")
    if reassessment.get("human_review_queue_approval_source") != "artifact":
        blocked_reasons.append("queue_preview_missing_human_approval_artifact")
    blocked_reasons.extend(str(reason) for reason in reassessment.get("missing_gate_artifacts", []) if reason)
    blocked_reasons.extend(str(reason) for reason in reassessment.get("failed_gate_artifacts", []) if reason)

    gate_evidence = reassessment.get("artifact_gate_evidence", {}) if isinstance(reassessment.get("artifact_gate_evidence"), dict) else {}
    required_gates = [
        "retrieval_ranking_gate_pass",
        "rollback_confidence_pass",
        "rollback_replay_validate_pass",
        "live_telemetry_reconciliation_pass",
        "human_review_queue_approval_pass",
    ]
    for gate_name in required_gates:
        if gate_evidence.get(gate_name) is not True:
            blocked_reasons.append(f"{gate_name}_not_green")

    return {
        "provided": True,
        "path": str(path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "pass": not blocked_reasons,
        "blocked_reasons": sorted(set(blocked_reasons)),
        "queue_count": _safe_int(payload.get("queue_count")),
        "required_green_gates": required_gates,
        "artifact_gate_evidence": {gate: gate_evidence.get(gate) is True for gate in required_gates},
    }


def _dogfood_g4_apply_readiness_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_apply < 1:
        raise ValueError("dogfood g4-apply-readiness max-apply must be >= 1")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")
    preview_evidence = _read_g4_preview_readiness_artifact(args.queue_preview_report)
    blocked_reasons = list(preview_evidence.get("blocked_reasons", []))
    bounded_ready = not blocked_reasons
    payload = {
        "kind": "dogfood_g4_apply_readiness",
        "read_only": True,
        "mutated": False,
        "db_path": str(db_path),
        "apply_supported": False,
        "broad_g4_apply_allowed": False,
        "bounded_partial_apply_ready": bounded_ready,
        "default_retrieval_unchanged": True,
        "ordinary_conversation_auto_approval": False,
        "preview_evidence": preview_evidence,
        "quality_gate": {
            "pass": bounded_ready,
            "decision": "bounded_apply_ready_pending_exact_operator_approval" if bounded_ready else "continue_read_only_gate_evidence_before_apply_readiness",
            "blocked_reasons": sorted(set(blocked_reasons)),
        },
        "required_operator_approval": {
            "command": "g4-review-queue-apply",
            "policy": "g4-review-queue-apply-v1",
            "approval_phrase": "apply-approved-g4-review-queue-items-v1",
            "backup_required": True,
            "max_apply": args.max_apply,
        },
        "safety_exclusions": {
            "broad_g4_background_apply": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_migration": False,
            "collapse_delete_apply": False,
            "live_telemetry_reset": False,
        },
        "next_step": "If and only if an operator explicitly approves, run g4-review-queue-apply with the exact policy, phrase, actor, reason, backup, and max-apply bound.",
        "privacy": {
            "raw_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _read_json_artifact_summary(path: Path | None) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    if path is None:
        return None, {
            "provided": False,
            "path": None,
            "report_sha256": None,
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "error": None,
        }
    report_path = path.expanduser().resolve(strict=False)
    try:
        raw_text = report_path.read_text(encoding="utf-8")
        payload = json.loads(raw_text)
    except Exception as exc:
        return None, {
            "provided": True,
            "path": str(report_path),
            "report_sha256": None,
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "error": {"type": exc.__class__.__name__, "message": str(exc)},
        }
    if not isinstance(payload, dict):
        return None, {
            "provided": True,
            "path": str(report_path),
            "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
            "kind": None,
            "read_only": None,
            "mutated": None,
            "default_retrieval_unchanged": None,
            "error": {"type": "ValueError", "message": "artifact is not a JSON object"},
        }
    return payload, {
        "provided": True,
        "path": str(report_path),
        "report_sha256": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "kind": payload.get("kind"),
        "read_only": payload.get("read_only"),
        "mutated": payload.get("mutated"),
        "default_retrieval_unchanged": payload.get("default_retrieval_unchanged"),
        "error": None,
    }


def _privacy_flags_are_ref_safe(privacy: dict[str, Any]) -> bool:
    unsafe_keys = (
        "proposal_json_included",
        "raw_content_included",
        "raw_conversation_content_included",
        "raw_reason_included",
        "raw_query_text_included",
        "raw_trace_summary_included",
        "sample_values_included",
        "raw_report_included",
    )
    return not any(privacy.get(key) is True for key in unsafe_keys)


def _dogfood_g4_readiness_gate_summary_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")

    ranking_payload, ranking_base = _read_json_artifact_summary(args.retrieval_ranking_report)
    bundle_payload, bundle_base = _read_json_artifact_summary(args.operator_apply_bundle_report)
    ranking_payload = ranking_payload or {}
    bundle_payload = bundle_payload or {}

    fixture_gate = ranking_payload.get("fixture_gate_comparison", {})
    if not isinstance(fixture_gate, dict):
        fixture_gate = {}
    shadow_compare = ranking_payload.get("shadow_compare", {})
    if not isinstance(shadow_compare, dict):
        shadow_compare = {}
    ranking_blocked_reasons: list[str] = []
    if not ranking_base["provided"]:
        ranking_blocked_reasons.append("retrieval_ranking_report_not_provided")
    if ranking_base["error"] is not None:
        ranking_blocked_reasons.append("retrieval_ranking_report_unreadable")
    if ranking_base["kind"] != "dogfood_retrieval_ranking_experiment":
        ranking_blocked_reasons.append("retrieval_ranking_report_kind_invalid")
    if ranking_base["read_only"] is not True:
        ranking_blocked_reasons.append("retrieval_ranking_report_not_read_only")
    if ranking_base["mutated"] is not False:
        ranking_blocked_reasons.append("retrieval_ranking_report_mutated")
    if ranking_base["default_retrieval_unchanged"] is not True:
        ranking_blocked_reasons.append("retrieval_ranking_default_changed")
    baseline_regression_count = _safe_int(
        fixture_gate.get("baseline_regression_count", shadow_compare.get("baseline_regression_count", 0))
    )
    if baseline_regression_count > 0:
        ranking_blocked_reasons.append("retrieval_ranking_baseline_regressions_present")
    if fixture_gate.get("default_ranking_mutated") is True:
        ranking_blocked_reasons.append("retrieval_ranking_default_mutated")
    if fixture_gate.get("ordinary_conversation_auto_enable") is True:
        ranking_blocked_reasons.append("retrieval_ranking_ordinary_conversation_auto_enabled")
    ranking_gate = {
        **ranking_base,
        "pass": not ranking_blocked_reasons,
        "blocked_reasons": sorted(set(ranking_blocked_reasons)),
        "fixture_task_count": _safe_int(fixture_gate.get("fixture_task_count", ranking_payload.get("fixture_expansion", {}).get("task_count", 0) if isinstance(ranking_payload.get("fixture_expansion"), dict) else 0)),
        "baseline_regression_count": baseline_regression_count,
        "rank_change_count": _safe_int(fixture_gate.get("rank_change_count", ranking_payload.get("rank_change_count", 0))),
        "default_ranking_mutated": fixture_gate.get("default_ranking_mutated") is True,
        "ordinary_conversation_auto_enable": fixture_gate.get("ordinary_conversation_auto_enable") is True,
    }
    ranking_gate.pop("error", None)

    bundle_quality = bundle_payload.get("quality_gate", {}) if isinstance(bundle_payload.get("quality_gate"), dict) else {}
    bundle_privacy = bundle_payload.get("privacy", {}) if isinstance(bundle_payload.get("privacy"), dict) else {}
    bundle_blocked_reasons: list[str] = []
    if not bundle_base["provided"]:
        bundle_blocked_reasons.append("operator_apply_bundle_report_not_provided")
    if bundle_base["error"] is not None:
        bundle_blocked_reasons.append("operator_apply_bundle_report_unreadable")
    if bundle_base["kind"] != "dogfood_g4_operator_apply_bundle":
        bundle_blocked_reasons.append("operator_apply_bundle_kind_invalid")
    if bundle_base["read_only"] is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_read_only")
    if bundle_base["mutated"] is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_mutated")
    if bundle_base["default_retrieval_unchanged"] is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_default_retrieval_changed")
    if bundle_quality.get("pass") is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_green")
    for reason in bundle_quality.get("blocked_reasons", []) if isinstance(bundle_quality.get("blocked_reasons"), list) else []:
        if reason:
            bundle_blocked_reasons.append(str(reason))
    if bundle_payload.get("bounded_partial_apply_ready") is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_bounded_ready")
    if bundle_payload.get("broad_g4_apply_allowed") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_broad_apply_allowed")
    if bundle_payload.get("apply_executed") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_apply_executed")
    if bundle_payload.get("apply_supported") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_apply_supported")
    if bundle_payload.get("ordinary_conversation_auto_approval") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_ordinary_auto_approval_enabled")
    if not _privacy_flags_are_ref_safe(bundle_privacy):
        bundle_blocked_reasons.append("operator_apply_bundle_privacy_flags_not_ref_safe")
    bundle_gate = {
        **bundle_base,
        "pass": not bundle_blocked_reasons,
        "blocked_reasons": sorted(set(bundle_blocked_reasons)),
        "bounded_partial_apply_ready": bundle_payload.get("bounded_partial_apply_ready") is True,
        "broad_g4_apply_allowed": bundle_payload.get("broad_g4_apply_allowed") is True,
        "apply_executed": bundle_payload.get("apply_executed") is True,
        "apply_supported": bundle_payload.get("apply_supported") is True,
        "ordinary_conversation_auto_approval": bundle_payload.get("ordinary_conversation_auto_approval") is True,
    }
    bundle_gate.pop("error", None)

    blocked_reasons = sorted(set([*ranking_gate["blocked_reasons"], *bundle_gate["blocked_reasons"]]))
    green = not blocked_reasons
    payload = {
        "kind": "dogfood_g4_readiness_gate_summary",
        "read_only": True,
        "mutated": False,
        "db_path": str(db_path),
        "default_retrieval_unchanged": True,
        "automation_stage": "bounded_operator_apply_preflight_summary",
        "retrieval_ranking_gate": ranking_gate,
        "operator_apply_bundle_gate": bundle_gate,
        "quality_gate": {
            "pass": green,
            "decision": "bounded_g4_preflight_summary_green_for_manual_operator_apply" if green else "bounded_g4_preflight_summary_blocked",
            "blocked_reasons": blocked_reasons,
        },
        "next_step": "manual_operator_apply_requires_separate_explicit_approval",
        "safety_exclusions": {
            "broad_g4_background_apply": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_migration": False,
            "collapse_delete_apply": False,
            "live_telemetry_reset": False,
        },
        "privacy": {
            "raw_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "raw_reason_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_g4_operator_apply_packet_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_apply < 1:
        raise ValueError("dogfood g4-operator-apply-packet max-apply must be >= 1")
    if not args.actor.strip():
        raise ValueError("dogfood g4-operator-apply-packet requires non-empty --actor")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")

    bundle_payload, bundle_base = _read_json_artifact_summary(args.operator_apply_bundle_report)
    readiness_payload, readiness_base = _read_json_artifact_summary(args.readiness_gate_summary_report)
    bundle_payload = bundle_payload or {}
    readiness_payload = readiness_payload or {}
    bundle_quality = bundle_payload.get("quality_gate", {}) if isinstance(bundle_payload.get("quality_gate"), dict) else {}
    readiness_quality = readiness_payload.get("quality_gate", {}) if isinstance(readiness_payload.get("quality_gate"), dict) else {}
    bundle_privacy = bundle_payload.get("privacy", {}) if isinstance(bundle_payload.get("privacy"), dict) else {}
    readiness_privacy = readiness_payload.get("privacy", {}) if isinstance(readiness_payload.get("privacy"), dict) else {}

    bundle_blocked_reasons: list[str] = []
    if not bundle_base["provided"]:
        bundle_blocked_reasons.append("operator_apply_bundle_report_not_provided")
    if bundle_base["error"] is not None:
        bundle_blocked_reasons.append("operator_apply_bundle_report_unreadable")
    if bundle_base["kind"] != "dogfood_g4_operator_apply_bundle":
        bundle_blocked_reasons.append("operator_apply_bundle_kind_invalid")
    if bundle_base["read_only"] is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_read_only")
    if bundle_base["mutated"] is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_mutated")
    if bundle_base["default_retrieval_unchanged"] is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_default_retrieval_changed")
    if bundle_quality.get("pass") is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_green")
    for reason in bundle_quality.get("blocked_reasons", []) if isinstance(bundle_quality.get("blocked_reasons"), list) else []:
        if reason:
            bundle_blocked_reasons.append(str(reason))
    if bundle_payload.get("bounded_partial_apply_ready") is not True:
        bundle_blocked_reasons.append("operator_apply_bundle_not_bounded_ready")
    if bundle_payload.get("broad_g4_apply_allowed") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_broad_apply_allowed")
    if bundle_payload.get("apply_executed") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_apply_executed")
    if bundle_payload.get("apply_supported") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_apply_supported")
    if bundle_payload.get("ordinary_conversation_auto_approval") is not False:
        bundle_blocked_reasons.append("operator_apply_bundle_ordinary_auto_approval_enabled")
    if not _privacy_flags_are_ref_safe(bundle_privacy):
        bundle_blocked_reasons.append("operator_apply_bundle_privacy_flags_not_ref_safe")
    bundle_gate = {
        **bundle_base,
        "pass": not bundle_blocked_reasons,
        "blocked_reasons": sorted(set(bundle_blocked_reasons)),
        "bounded_partial_apply_ready": bundle_payload.get("bounded_partial_apply_ready") is True,
        "broad_g4_apply_allowed": bundle_payload.get("broad_g4_apply_allowed") is True,
        "apply_executed": bundle_payload.get("apply_executed") is True,
        "apply_supported": bundle_payload.get("apply_supported") is True,
        "ordinary_conversation_auto_approval": bundle_payload.get("ordinary_conversation_auto_approval") is True,
    }
    bundle_gate.pop("error", None)

    readiness_blocked_reasons: list[str] = []
    if not readiness_base["provided"]:
        readiness_blocked_reasons.append("readiness_gate_summary_report_not_provided")
    if readiness_base["error"] is not None:
        readiness_blocked_reasons.append("readiness_gate_summary_report_unreadable")
    if readiness_base["kind"] != "dogfood_g4_readiness_gate_summary":
        readiness_blocked_reasons.append("readiness_gate_summary_kind_invalid")
    if readiness_base["read_only"] is not True:
        readiness_blocked_reasons.append("readiness_gate_summary_not_read_only")
    if readiness_base["mutated"] is not False:
        readiness_blocked_reasons.append("readiness_gate_summary_mutated")
    if readiness_base["default_retrieval_unchanged"] is not True:
        readiness_blocked_reasons.append("readiness_gate_summary_default_retrieval_changed")
    if readiness_quality.get("pass") is not True:
        readiness_blocked_reasons.append("readiness_gate_summary_not_green")
    for reason in readiness_quality.get("blocked_reasons", []) if isinstance(readiness_quality.get("blocked_reasons"), list) else []:
        if reason:
            readiness_blocked_reasons.append(str(reason))
    if not _privacy_flags_are_ref_safe(readiness_privacy):
        readiness_blocked_reasons.append("readiness_gate_summary_privacy_flags_not_ref_safe")
    readiness_gate = {
        **readiness_base,
        "pass": not readiness_blocked_reasons,
        "blocked_reasons": sorted(set(readiness_blocked_reasons)),
    }
    readiness_gate.pop("error", None)

    blocked_reasons = sorted(set([*bundle_gate["blocked_reasons"], *readiness_gate["blocked_reasons"]]))
    green = not blocked_reasons
    manual_apply_command_preview = [
        "agent-memory",
        "dogfood",
        "g4-review-queue-apply",
        str(db_path),
        "--policy",
        "g4-review-queue-apply-v1",
        "--approval-phrase",
        "apply-approved-g4-review-queue-items-v1",
        "--actor",
        args.actor.strip(),
        "--reason",
        "<operator-private-reason>",
        "--backup-path",
        "<required-backup-path>",
        "--max-apply",
        str(args.max_apply),
        "--output",
        "<apply-audit-output.json>",
    ]
    post_apply_verification_command_template = [
        "agent-memory",
        "dogfood",
        "g4-post-apply-verification",
        str(db_path),
        "--apply-report",
        "<apply-audit-output.json>",
        "--post-apply-bundle-report",
        "<post-apply-operator-bundle.json>",
        "--rollback-replay-report",
        "<post-apply-rollback-replay.json>",
        "--output",
        "<post-apply-verification.json>",
    ]
    manual_apply_required_flags = {
        "--policy",
        "--approval-phrase",
        "--actor",
        "--reason",
        "--backup-path",
        "--max-apply",
        "--output",
    }
    post_apply_verification_required_flags = {
        "--apply-report",
        "--post-apply-bundle-report",
        "--rollback-replay-report",
        "--output",
    }
    payload = {
        "kind": "dogfood_g4_operator_apply_packet",
        "read_only": True,
        "mutated": False,
        "apply_executed": False,
        "apply_supported": False,
        "broad_g4_apply_allowed": False,
        "default_retrieval_unchanged": True,
        "ordinary_conversation_auto_approval": False,
        "db_path": str(db_path),
        "artifact_gates": {
            "operator_apply_bundle": bundle_gate,
            "readiness_gate_summary": readiness_gate,
        },
        "quality_gate": {
            "pass": green,
            "decision": "operator_apply_packet_ready_for_manual_review_only" if green else "operator_apply_packet_blocked_before_manual_apply",
            "blocked_reasons": blocked_reasons,
        },
        "operator_checklist": {
            "pre_authorization_required": True,
            "required_policy": "g4-review-queue-apply-v1",
            "required_approval_phrase": "apply-approved-g4-review-queue-items-v1",
            "actor_required": True,
            "private_reason_required": True,
            "backup_path_required": True,
            "audit_output_path_required": True,
            "max_apply": args.max_apply,
            "post_apply_verification_required": True,
            "repeated_apply_requires_new_packet": True,
        },
        "manual_apply_command_preview": manual_apply_command_preview,
        "post_apply_verification_command_template": post_apply_verification_command_template,
        "runbook_contract": {
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
            "manual_apply_command_contains_all_required_flags": manual_apply_required_flags.issubset(manual_apply_command_preview),
            "post_apply_verification_template_contains_all_required_flags": post_apply_verification_required_flags.issubset(
                post_apply_verification_command_template
            ),
            "readiness_is_not_authorization": True,
        },
        "safety_exclusions": {
            "broad_g4_background_apply": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_migration": False,
            "collapse_delete_apply": False,
            "live_telemetry_reset": False,
            "apply_without_exact_operator_approval": False,
        },
        "privacy": {
            "raw_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "raw_reason_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
        "next_step": "manual_review_only_until_exact_operator_apply_approval_is_provided",
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_g4_post_apply_verification_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")

    apply_payload, apply_base = _read_json_artifact_summary(args.apply_report)
    bundle_payload, bundle_base = _read_json_artifact_summary(args.post_apply_bundle_report)
    replay_payload, replay_base = _read_json_artifact_summary(args.rollback_replay_report)
    apply_payload = apply_payload or {}
    bundle_payload = bundle_payload or {}
    replay_payload = replay_payload or {}

    apply_privacy = apply_payload.get("privacy", {}) if isinstance(apply_payload.get("privacy"), dict) else {}
    apply_blocked_reasons: list[str] = []
    if not apply_base["provided"]:
        apply_blocked_reasons.append("apply_report_not_provided")
    if apply_base["error"] is not None:
        apply_blocked_reasons.append("apply_report_unreadable")
    if apply_base["kind"] != "dogfood_g4_review_queue_apply":
        apply_blocked_reasons.append("apply_report_kind_invalid")
    if apply_base["read_only"] is not False:
        apply_blocked_reasons.append("apply_report_not_mutating_artifact")
    if apply_base["mutated"] is not True:
        apply_blocked_reasons.append("apply_report_mutation_not_confirmed")
    if apply_base["default_retrieval_unchanged"] is not True:
        apply_blocked_reasons.append("apply_report_default_retrieval_changed")
    if apply_payload.get("policy") != "g4-review-queue-apply-v1":
        apply_blocked_reasons.append("apply_report_policy_invalid")
    if apply_payload.get("approval_phrase_matched") is not True:
        apply_blocked_reasons.append("apply_report_approval_phrase_not_matched")
    applied_count = _safe_int(apply_payload.get("applied_count"))
    max_apply = _safe_int(apply_payload.get("max_apply"))
    if applied_count < 1:
        apply_blocked_reasons.append("apply_report_no_applied_items")
    if max_apply < 1:
        apply_blocked_reasons.append("apply_report_max_apply_invalid")
    if max_apply > 0 and applied_count > max_apply:
        apply_blocked_reasons.append("apply_report_exceeds_max_apply")
    if apply_payload.get("memory_status_mutated") is not False:
        apply_blocked_reasons.append("apply_report_memory_status_mutated")
    if apply_payload.get("ordinary_conversation_auto_approval") is not False:
        apply_blocked_reasons.append("apply_report_ordinary_auto_approval_enabled")
    if not _privacy_flags_are_ref_safe(apply_privacy):
        apply_blocked_reasons.append("apply_report_privacy_flags_not_ref_safe")

    backup = apply_payload.get("backup", {}) if isinstance(apply_payload.get("backup"), dict) else {}
    backup_path_value = backup.get("path") if isinstance(backup.get("path"), str) else None
    backup_sha256_value = backup.get("sha256") if isinstance(backup.get("sha256"), str) else None
    backup_exists = False
    backup_sha256_matches = False
    backup_blocked_reasons: list[str] = []
    if not backup_path_value:
        backup_blocked_reasons.append("backup_path_missing")
    else:
        backup_path = Path(backup_path_value).expanduser().resolve(strict=False)
        backup_exists = backup_path.exists()
        if not backup_exists:
            backup_blocked_reasons.append("backup_missing")
        elif not backup_sha256_value:
            backup_blocked_reasons.append("backup_sha256_missing")
        else:
            backup_sha256_matches = _sha256_file(backup_path) == backup_sha256_value
            if not backup_sha256_matches:
                backup_blocked_reasons.append("backup_sha256_mismatch")
    backup_gate = {
        "pass": not backup_blocked_reasons,
        "blocked_reasons": sorted(set(backup_blocked_reasons)),
        "backup_path_provided": backup_path_value is not None,
        "backup_exists": backup_exists,
        "backup_sha256_matches": backup_sha256_matches,
        "backup_sha256": backup_sha256_value,
    }

    apply_gate = {
        **apply_base,
        "pass": not apply_blocked_reasons,
        "blocked_reasons": sorted(set(apply_blocked_reasons)),
        "policy": apply_payload.get("policy"),
        "approval_phrase_matched": apply_payload.get("approval_phrase_matched") is True,
        "applied_count": applied_count,
        "already_applied_count": _safe_int(apply_payload.get("already_applied_count")),
        "skipped_count": _safe_int(apply_payload.get("skipped_count")),
        "max_apply": max_apply,
        "memory_status_mutated": apply_payload.get("memory_status_mutated") is True,
        "memory_reinforcement_mutated": apply_payload.get("memory_reinforcement_mutated") is True,
        "ordinary_conversation_auto_approval": apply_payload.get("ordinary_conversation_auto_approval") is True,
    }
    apply_gate.pop("error", None)

    bundle_quality = bundle_payload.get("quality_gate", {}) if isinstance(bundle_payload.get("quality_gate"), dict) else {}
    bundle_privacy = bundle_payload.get("privacy", {}) if isinstance(bundle_payload.get("privacy"), dict) else {}
    bundle_blocked_reasons: list[str] = []
    if not bundle_base["provided"]:
        bundle_blocked_reasons.append("post_apply_bundle_report_not_provided")
    if bundle_base["error"] is not None:
        bundle_blocked_reasons.append("post_apply_bundle_report_unreadable")
    if bundle_base["kind"] != "dogfood_g4_operator_apply_bundle":
        bundle_blocked_reasons.append("post_apply_bundle_kind_invalid")
    if bundle_base["read_only"] is not True:
        bundle_blocked_reasons.append("post_apply_bundle_not_read_only")
    if bundle_base["mutated"] is not False:
        bundle_blocked_reasons.append("post_apply_bundle_mutated")
    if bundle_base["default_retrieval_unchanged"] is not True:
        bundle_blocked_reasons.append("post_apply_bundle_default_retrieval_changed")
    if bundle_quality.get("pass") is not True:
        bundle_blocked_reasons.append("post_apply_bundle_not_green")
    for reason in bundle_quality.get("blocked_reasons", []) if isinstance(bundle_quality.get("blocked_reasons"), list) else []:
        if reason:
            bundle_blocked_reasons.append(str(reason))
    if bundle_payload.get("broad_g4_apply_allowed") is not False:
        bundle_blocked_reasons.append("post_apply_bundle_broad_apply_allowed")
    if bundle_payload.get("apply_executed") is not False:
        bundle_blocked_reasons.append("post_apply_bundle_apply_executed")
    if bundle_payload.get("apply_supported") is not False:
        bundle_blocked_reasons.append("post_apply_bundle_apply_supported")
    if bundle_payload.get("ordinary_conversation_auto_approval") is not False:
        bundle_blocked_reasons.append("post_apply_bundle_ordinary_auto_approval_enabled")
    if not _privacy_flags_are_ref_safe(bundle_privacy):
        bundle_blocked_reasons.append("post_apply_bundle_privacy_flags_not_ref_safe")
    bundle_gate = {
        **bundle_base,
        "pass": not bundle_blocked_reasons,
        "blocked_reasons": sorted(set(bundle_blocked_reasons)),
        "bounded_partial_apply_ready": bundle_payload.get("bounded_partial_apply_ready") is True,
        "broad_g4_apply_allowed": bundle_payload.get("broad_g4_apply_allowed") is True,
        "apply_executed": bundle_payload.get("apply_executed") is True,
        "apply_supported": bundle_payload.get("apply_supported") is True,
        "ordinary_conversation_auto_approval": bundle_payload.get("ordinary_conversation_auto_approval") is True,
    }
    bundle_gate.pop("error", None)

    replay_quality = replay_payload.get("quality_gate", {}) if isinstance(replay_payload.get("quality_gate"), dict) else {}
    replay_privacy = replay_payload.get("privacy", {}) if isinstance(replay_payload.get("privacy"), dict) else {}
    replay_blocked_reasons: list[str] = []
    if not replay_base["provided"]:
        replay_blocked_reasons.append("rollback_replay_report_not_provided")
    if replay_base["error"] is not None:
        replay_blocked_reasons.append("rollback_replay_report_unreadable")
    if replay_base["kind"] != "dogfood_rollback_replay_validate":
        replay_blocked_reasons.append("rollback_replay_kind_invalid")
    if replay_base["read_only"] is not True:
        replay_blocked_reasons.append("rollback_replay_not_read_only")
    if replay_base["mutated"] is not False:
        replay_blocked_reasons.append("rollback_replay_mutated")
    if replay_base["default_retrieval_unchanged"] is not True:
        replay_blocked_reasons.append("rollback_replay_default_retrieval_changed")
    if replay_quality.get("pass") is not True:
        replay_blocked_reasons.append("rollback_replay_not_green")
    for reason in replay_quality.get("blocked_reasons", []) if isinstance(replay_quality.get("blocked_reasons"), list) else []:
        if reason:
            replay_blocked_reasons.append(str(reason))
    if not _privacy_flags_are_ref_safe(replay_privacy):
        replay_blocked_reasons.append("rollback_replay_privacy_flags_not_ref_safe")
    replay_gate = {
        **replay_base,
        "pass": not replay_blocked_reasons,
        "blocked_reasons": sorted(set(replay_blocked_reasons)),
    }
    replay_gate.pop("error", None)

    blocked_reasons = sorted(
        set(
            [
                *apply_gate["blocked_reasons"],
                *backup_gate["blocked_reasons"],
                *bundle_gate["blocked_reasons"],
                *replay_gate["blocked_reasons"],
            ]
        )
    )
    green = not blocked_reasons
    payload = {
        "kind": "dogfood_g4_post_apply_verification",
        "read_only": True,
        "mutated": False,
        "verified_apply_mutated": apply_payload.get("mutated") is True,
        "db_path": str(db_path),
        "default_retrieval_unchanged": apply_base["default_retrieval_unchanged"] is True and bundle_base["default_retrieval_unchanged"] is True and replay_base["default_retrieval_unchanged"] is True,
        "automation_stage": "bounded_operator_apply_post_apply_verification",
        "apply_artifact_gate": apply_gate,
        "backup_integrity_gate": backup_gate,
        "post_apply_bundle_gate": bundle_gate,
        "rollback_replay_gate": replay_gate,
        "quality_gate": {
            "pass": green,
            "decision": "g4_post_apply_verification_green_stop_before_next_mutation" if green else "g4_post_apply_verification_blocked",
            "blocked_reasons": blocked_reasons,
        },
        "next_step": "stop_or_collect_operator_review_before_any_further_mutation",
        "safety_exclusions": {
            "broad_g4_background_apply": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_migration": False,
            "collapse_delete_apply": False,
            "live_telemetry_reset": False,
            "additional_apply_without_new_approval": False,
        },
        "privacy": {
            "raw_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "raw_reason_included": False,
            "sample_values_included": False,
            "aggregate_or_ref_only": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_g4_operator_apply_bundle_payload(args: argparse.Namespace) -> dict[str, Any]:
    if args.max_apply < 1:
        raise ValueError("dogfood g4-operator-apply-bundle max-apply must be >= 1")
    if args.limit < 1:
        raise ValueError("dogfood g4-operator-apply-bundle limit must be >= 1")
    if args.top < 1:
        raise ValueError("dogfood g4-operator-apply-bundle top must be >= 1")
    if args.queue_limit < 1:
        raise ValueError("dogfood g4-operator-apply-bundle queue-limit must be >= 1")
    if args.min_evidence_count < 1:
        raise ValueError("dogfood g4-operator-apply-bundle min-evidence-count must be >= 1")
    if args.frequent_threshold < 1:
        raise ValueError("dogfood g4-operator-apply-bundle frequent-threshold must be >= 1")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood g4-operator-apply-bundle requires non-empty --actor and --reason")

    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")
    report_dir = args.report_dir.expanduser().resolve(strict=False)
    report_dir.mkdir(parents=True, exist_ok=True)
    approval_report_path = report_dir / "g4-review-queue-approval-report.json"
    queue_preview_path = report_dir / "g4-review-queue-preview.json"
    readiness_path = report_dir / "g4-apply-readiness.json"

    approval_payload = _dogfood_g4_review_queue_approval_report_payload(
        argparse.Namespace(
            db_path=db_path,
            actor=args.actor,
            policy="g4-review-queue-approval-artifact-v1",
            approval_phrase="report-approved-g4-review-queue-v1",
            output=approval_report_path,
        )
    )
    preview_payload = _dogfood_g4_review_queue_preview_payload(
        argparse.Namespace(
            db_path=db_path,
            limit=args.limit,
            top=args.top,
            queue_limit=args.queue_limit,
            min_evidence_count=args.min_evidence_count,
            frequent_threshold=args.frequent_threshold,
            epoch_start=args.epoch_start,
            retrieval_ranking_report=args.retrieval_ranking_report,
            rollback_confidence_report=args.rollback_confidence_report,
            rollback_replay_report=args.rollback_replay_report,
            telemetry_reconciliation_report=args.telemetry_reconciliation_report,
            human_review_approval_report=approval_report_path,
            output=queue_preview_path,
            lock_path=args.lock_path,
        )
    )
    readiness_payload = _dogfood_g4_apply_readiness_payload(
        argparse.Namespace(
            db_path=db_path,
            queue_preview_report=queue_preview_path,
            max_apply=args.max_apply,
            output=readiness_path,
        )
    )

    readiness_gate = readiness_payload.get("quality_gate", {}) if isinstance(readiness_payload.get("quality_gate"), dict) else {}
    approval_gate = approval_payload.get("quality_gate", {}) if isinstance(approval_payload.get("quality_gate"), dict) else {}
    blocked_reasons = sorted(
        set(
            str(reason)
            for reason in [
                *approval_gate.get("blocked_reasons", []),
                *readiness_gate.get("blocked_reasons", []),
            ]
            if reason
        )
    )
    bounded_ready = readiness_payload.get("bounded_partial_apply_ready") is True and not blocked_reasons
    payload = {
        "kind": "dogfood_g4_operator_apply_bundle",
        "read_only": True,
        "mutated": False,
        "apply_executed": False,
        "apply_supported": False,
        "broad_g4_apply_allowed": False,
        "bounded_partial_apply_ready": bounded_ready,
        "default_retrieval_unchanged": True,
        "ordinary_conversation_auto_approval": False,
        "db_path": str(db_path),
        "report_dir": str(report_dir),
        "artifact_paths": {
            "human_review_approval_report": str(approval_report_path),
            "queue_preview_report": str(queue_preview_path),
            "apply_readiness_report": str(readiness_path),
        },
        "artifact_sha256s": {
            "human_review_approval_report": hashlib.sha256(approval_report_path.read_text(encoding="utf-8").encode()).hexdigest(),
            "queue_preview_report": hashlib.sha256(queue_preview_path.read_text(encoding="utf-8").encode()).hexdigest(),
            "apply_readiness_report": hashlib.sha256(readiness_path.read_text(encoding="utf-8").encode()).hexdigest(),
        },
        "quality_gate": {
            "pass": bounded_ready,
            "decision": "operator_apply_bundle_ready_for_exact_manual_apply" if bounded_ready else "operator_apply_bundle_blocked_before_exact_manual_apply",
            "blocked_reasons": blocked_reasons,
        },
        "artifact_summaries": {
            "human_review_approval_pass": approval_payload.get("human_review_queue_approval_pass") is True,
            "human_review_quality_gate": approval_payload.get("quality_gate", {}),
            "queue_preview_pass": (preview_payload.get("quality_gate", {}) if isinstance(preview_payload.get("quality_gate"), dict) else {}).get("pass") is True,
            "queue_count": _safe_int(preview_payload.get("queue_count")),
            "apply_readiness_pass": readiness_gate.get("pass") is True,
        },
        "exact_apply_command_preview": [
            "agent-memory",
            "dogfood",
            "g4-review-queue-apply",
            str(db_path),
            "--policy",
            "g4-review-queue-apply-v1",
            "--approval-phrase",
            "apply-approved-g4-review-queue-items-v1",
            "--actor",
            args.actor.strip(),
            "--reason",
            "<operator-provided-reason>",
            "--backup-path",
            "<required-backup-path>",
            "--max-apply",
            str(args.max_apply),
            "--output",
            "<apply-audit-output.json>",
        ],
        "safety_exclusions": {
            "broad_g4_background_apply": False,
            "ordinary_conversation_auto_approval": False,
            "default_retrieval_migration": False,
            "collapse_delete_apply": False,
            "live_telemetry_reset": False,
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
        "next_step": "Review the generated artifacts, then run the exact apply command manually only if the operator approves and supplies a backup path and private reason.",
    }
    _write_json_report(args.output, payload)
    return payload


def _dogfood_telemetry_reset_preview_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    epoch_start = _parse_epoch_start(args.epoch_start) if args.epoch_start else None
    telemetry_tables = ("retrieval_observations", "memory_activations", "experience_traces")
    protected_tables = ("facts", "procedures", "episodes", "relations", "source_records", "memory_status_transitions")
    if not db_path.exists():
        payload = {
            "kind": "dogfood_telemetry_reset_preview",
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }
        _write_json_report(args.output, payload)
        return payload

    with _open_readonly_sqlite(db_path) as connection:
        telemetry_preview: dict[str, Any] = {}
        total_candidate_rows = 0
        for table in telemetry_tables:
            if not _table_exists(connection, table):
                telemetry_preview[table] = {"exists": False, "candidate_rows": 0, "retained_rows": 0}
                continue
            total_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            if epoch_start is None:
                candidate_rows = total_rows
                retained_rows = 0
                earliest = connection.execute(f"SELECT MIN(created_at) FROM {table}").fetchone()[0]
                latest = connection.execute(f"SELECT MAX(created_at) FROM {table}").fetchone()[0]
            else:
                candidate_rows = int(connection.execute(f"SELECT COUNT(*) FROM {table} WHERE created_at < ?", (epoch_start,)).fetchone()[0])
                retained_rows = total_rows - candidate_rows
                earliest = connection.execute(f"SELECT MIN(created_at) FROM {table} WHERE created_at < ?", (epoch_start,)).fetchone()[0]
                latest = connection.execute(f"SELECT MAX(created_at) FROM {table} WHERE created_at < ?", (epoch_start,)).fetchone()[0]
            total_candidate_rows += candidate_rows
            telemetry_preview[table] = {
                "exists": True,
                "candidate_rows": candidate_rows,
                "retained_rows": retained_rows,
                "total_rows": total_rows,
                "candidate_earliest_created_at": earliest,
                "candidate_latest_created_at": latest,
            }
        protected_counts = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if _table_exists(connection, table) else 0
            for table in protected_tables
        }

    warnings: list[str] = []
    if total_candidate_rows == 0:
        warnings.append("no_telemetry_rows_match_preview")
    if epoch_start is None:
        warnings.append("full_telemetry_reset_preview_no_epoch_filter")

    payload = {
        "kind": "dogfood_telemetry_reset_preview",
        "read_only": True,
        "mutated": False,
        "database": {"path": str(db_path), "exists": True},
        "mode": "preview_only",
        "reset_scope": "telemetry_only",
        "epoch_filter": {
            "enabled": epoch_start is not None,
            "retain_rows_created_at_gte": epoch_start,
        },
        "telemetry_tables": telemetry_preview,
        "candidate_delete_total": total_candidate_rows,
        "protected_tables": protected_counts,
        "guardrails": {
            "apply_supported": False,
            "requires_backup_before_future_apply": True,
            "default_retrieval_unchanged": True,
            "protected_memory_tables_mutated": False,
            "telemetry_tables_only": list(telemetry_tables),
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "aggregate_only": True,
        },
        "suggested_next_steps": [
            "Compare this preview against dogfood fresh-epoch before designing any apply command.",
            "Future apply must require an explicit approval phrase and a verified backup path.",
            "Never delete facts, procedures, episodes, relations, source records, or status history in telemetry-only reset.",
        ],
        "warnings": warnings,
    }
    _write_json_report(args.output, payload)
    return payload




def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _default_backup_path(db_path: Path, *, label: str) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return db_path.with_name(f"{db_path.name}.bak-{label}-{stamp}")


def _create_sqlite_backup(db_path: Path, backup_path: Path) -> dict[str, Any]:
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_path, backup_path)
    return {
        "path": str(backup_path),
        "sha256": _sha256_file(backup_path),
        "size_bytes": backup_path.stat().st_size,
        "raw_content_included": False,
    }


def _dogfood_telemetry_reset_apply_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy = "telemetry-reset-v1"
    approval_phrase = "apply-telemetry-reset-v1"
    if args.policy != policy:
        raise ValueError(f"dogfood telemetry-reset-apply requires --policy {policy}")
    if args.approval_phrase != approval_phrase:
        raise ValueError(f"dogfood telemetry-reset-apply requires --approval-phrase {approval_phrase}")
    if not args.epoch_start:
        raise ValueError("dogfood telemetry-reset-apply requires --epoch-start")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood telemetry-reset-apply requires non-empty --actor and --reason")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")

    preview = _dogfood_telemetry_reset_preview_payload(
        argparse.Namespace(db_path=db_path, epoch_start=args.epoch_start, output=None)
    )
    candidate_total = _safe_int(preview.get("candidate_delete_total"))
    backup_path = args.backup_path.expanduser().resolve(strict=False) if args.backup_path else _default_backup_path(db_path, label="telemetry-reset")
    backup = _create_sqlite_backup(db_path, backup_path)
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    epoch_start = _parse_epoch_start(args.epoch_start)
    telemetry_tables = ("retrieval_observations", "memory_activations", "experience_traces")
    protected_tables = ("facts", "procedures", "episodes", "relations", "source_records", "memory_status_transitions", "g4_review_queue_items")

    with sqlite3.connect(db_path) as connection:
        protected_before = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if _table_exists(connection, table) else 0
            for table in protected_tables
        }
        deleted_by_table: dict[str, int] = {}
        for table in telemetry_tables:
            if not _table_exists(connection, table):
                deleted_by_table[table] = 0
                continue
            before = connection.total_changes
            connection.execute(f"DELETE FROM {table} WHERE created_at < ?", (epoch_start,))
            deleted_by_table[table] = connection.total_changes - before
        protected_after = {
            table: int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if _table_exists(connection, table) else 0
            for table in protected_tables
        }
    protected_unchanged = protected_before == protected_after
    deleted_total = sum(deleted_by_table.values())
    after_preview = _dogfood_telemetry_reset_preview_payload(
        argparse.Namespace(db_path=db_path, epoch_start=args.epoch_start, output=None)
    )
    blocked_reasons: list[str] = []
    if not protected_unchanged:
        blocked_reasons.append("protected_table_count_changed")
    if deleted_total != candidate_total:
        blocked_reasons.append("deleted_total_does_not_match_preview")
    if _safe_int(after_preview.get("candidate_delete_total")) != 0:
        blocked_reasons.append("post_apply_preview_still_has_candidates")
    if blocked_reasons:
        raise RuntimeError("telemetry reset apply failed safety gate: " + ",".join(blocked_reasons))
    payload = {
        "kind": "dogfood_telemetry_reset_apply",
        "read_only": False,
        "mutated": deleted_total > 0,
        "db_path": str(db_path),
        "policy": policy,
        "approval_phrase_matched": True,
        "actor": args.actor.strip(),
        "reason_sha256": reason_sha256,
        "backup": backup,
        "reset_scope": "telemetry_only",
        "epoch_filter": preview.get("epoch_filter", {}),
        "candidate_delete_total": candidate_total,
        "deleted_total": deleted_total,
        "deleted_by_table": deleted_by_table,
        "protected_tables_before": protected_before,
        "protected_tables_after": protected_after,
        "protected_memory_tables_mutated": False,
        "default_retrieval_unchanged": True,
        "post_apply_preview": {
            "candidate_delete_total": after_preview.get("candidate_delete_total"),
            "warnings": after_preview.get("warnings", []),
        },
        "quality_gate": {
            "pass": True,
            "decision": "telemetry_only_reset_applied_with_protected_tables_verified",
            "blocked_reasons": [],
        },
        "privacy": {
            "raw_conversation_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "sample_values_included": False,
            "raw_reason_included": False,
            "reason_stored_as_sha256": True,
        },
    }
    _write_json_report(args.output, payload)
    return payload


def _ensure_g4_review_queue_applications_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS g4_review_queue_applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            queue_id TEXT NOT NULL,
            proposal_type TEXT NOT NULL,
            target_ref TEXT,
            policy TEXT NOT NULL,
            action TEXT NOT NULL,
            actor TEXT NOT NULL,
            reason_sha256 TEXT NOT NULL,
            source_preview_sha256 TEXT NOT NULL,
            backup_path TEXT NOT NULL,
            backup_sha256 TEXT NOT NULL,
            rollback_hint_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(queue_id, policy)
        )
        """
    )


def _dogfood_g4_review_queue_apply_payload(args: argparse.Namespace) -> dict[str, Any]:
    policy = "g4-review-queue-apply-v1"
    approval_phrase = "apply-approved-g4-review-queue-items-v1"
    if args.policy != policy:
        raise ValueError(f"dogfood g4-review-queue-apply requires --policy {policy}")
    if args.approval_phrase != approval_phrase:
        raise ValueError(f"dogfood g4-review-queue-apply requires --approval-phrase {approval_phrase}")
    if not args.actor.strip() or not args.reason.strip():
        raise ValueError("dogfood g4-review-queue-apply requires non-empty --actor and --reason")
    if args.max_apply < 1:
        raise ValueError("dogfood g4-review-queue-apply max-apply must be >= 1")
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        raise ValueError(f"database missing: {db_path}")
    backup_path = args.backup_path.expanduser().resolve(strict=False) if args.backup_path else _default_backup_path(db_path, label="g4-review-queue-apply")
    backup = _create_sqlite_backup(db_path, backup_path)
    reason_sha256 = hashlib.sha256(args.reason.strip().encode("utf-8")).hexdigest()
    queue_filter = list(args.queue_id or [])
    applied: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    with sqlite3.connect(db_path) as connection:
        connection.row_factory = sqlite3.Row
        _ensure_g4_review_queue_table(connection)
        _ensure_g4_review_queue_applications_table(connection)
        if queue_filter:
            placeholders = ", ".join("?" for _ in queue_filter)
            rows = connection.execute(
                f"SELECT * FROM g4_review_queue_items WHERE queue_id IN ({placeholders}) ORDER BY queue_id",
                tuple(queue_filter),
            ).fetchall()
        else:
            rows = connection.execute(
                "SELECT * FROM g4_review_queue_items WHERE status = 'approved' ORDER BY queue_id LIMIT ?",
                (args.max_apply,),
            ).fetchall()
        found_ids = {row["queue_id"] for row in rows}
        for missing in sorted(set(queue_filter) - found_ids):
            skipped.append({"queue_id": missing, "reason": "not_found"})
        for row in rows:
            queue_id = row["queue_id"]
            if row["status"] != "approved":
                skipped.append({"queue_id": queue_id, "reason": f"status_{row['status']}"})
                continue
            proposal = _safe_json_dict_from_db(row["proposal_json"])
            parsed_target = _parse_memory_ref(str(row["target_ref"] or "")) if row["target_ref"] else None
            action = "apply_reinforcement_marker" if row["proposal_type"] == "reinforcement_review" and parsed_target else "record_review_outcome_only"
            rollback_hint = {
                "restore_backup_path": str(backup_path),
                "queue_id": queue_id,
                "policy": policy,
                "memory_status_mutated": False,
                "memory_reinforcement_mutated": action == "apply_reinforcement_marker",
                "default_retrieval_mutated": False,
            }
            before = connection.total_changes
            connection.execute(
                """
                INSERT OR IGNORE INTO g4_review_queue_applications (
                    queue_id, proposal_type, target_ref, policy, action, actor, reason_sha256,
                    source_preview_sha256, backup_path, backup_sha256, rollback_hint_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    queue_id,
                    row["proposal_type"],
                    row["target_ref"],
                    policy,
                    action,
                    args.actor.strip(),
                    reason_sha256,
                    row["source_preview_sha256"],
                    str(backup_path),
                    backup["sha256"],
                    json.dumps(rollback_hint, sort_keys=True),
                ),
            )
            inserted = connection.total_changes > before
            reinforcement_mutated = False
            if inserted and action == "apply_reinforcement_marker" and parsed_target is not None:
                memory_type, memory_id = parsed_target
                table_name = {"fact": "facts", "procedure": "procedures", "episode": "episodes"}[memory_type]
                before_reinforcement = connection.total_changes
                connection.execute(
                    f"""
                    UPDATE {table_name}
                    SET reinforcement_count = COALESCE(reinforcement_count, 0.0) + 1.0,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (memory_id,),
                )
                reinforcement_mutated = connection.total_changes > before_reinforcement
            audit = _safe_json_list_from_db(row["audit_json"])
            audit.append({
                "action": "apply" if inserted else "apply_already_recorded",
                "actor": args.actor.strip(),
                "policy": policy,
                "reason_sha256": reason_sha256,
                "application_action": action,
                "memory_reinforcement_mutated": reinforcement_mutated,
            })
            connection.execute(
                "UPDATE g4_review_queue_items SET updated_at = CURRENT_TIMESTAMP, actor = ?, reason_sha256 = ?, audit_json = ? WHERE queue_id = ?",
                (args.actor.strip(), reason_sha256, json.dumps(audit), queue_id),
            )
            applied.append({
                "queue_id": queue_id,
                "proposal_type": row["proposal_type"],
                "target_ref": row["target_ref"],
                "action": action,
                "inserted": inserted,
                "memory_reinforcement_mutated": reinforcement_mutated,
                "reason_codes": proposal.get("reason_codes", []) if isinstance(proposal.get("reason_codes"), list) else [],
            })
    payload = {
        "kind": "dogfood_g4_review_queue_apply",
        "read_only": False,
        "mutated": any(item["inserted"] for item in applied),
        "db_path": str(db_path),
        "policy": policy,
        "approval_phrase_matched": True,
        "actor": args.actor.strip(),
        "reason_sha256": reason_sha256,
        "backup": backup,
        "apply_mode": "bounded_partial_automation_reviewed_queue_items_only",
        "max_apply": args.max_apply,
        "applied_count": len([item for item in applied if item["inserted"]]),
        "already_applied_count": len([item for item in applied if not item["inserted"]]),
        "skipped_count": len(skipped),
        "applied_items": applied,
        "skipped_items": skipped,
        "memory_status_mutated": False,
        "memory_reinforcement_mutated": any(item.get("memory_reinforcement_mutated") for item in applied),
        "default_retrieval_unchanged": True,
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
    }
    _write_json_report(args.output, payload)
    return payload

def _ordinary_trace_metadata_cleanup_privacy_payload() -> dict[str, bool]:
    return {
        "raw_trace_content_included": False,
        "sample_values_included": False,
        "hash_only": True,
    }


def _ordinary_trace_metadata_cleanup_scan(connection: sqlite3.Connection) -> dict[str, Any]:
    if not _table_exists(connection, "experience_traces"):
        return {
            "checked_count": 0,
            "affected_count": 0,
            "fixable_row_count": 0,
            "violation_counts": {},
            "fixable_ids": [],
            "earliest_fixable_at": None,
            "latest_fixable_at": None,
        }
    rows = connection.execute(
        """
        SELECT id, summary, retention_policy, metadata_json, created_at
        FROM experience_traces
        WHERE event_kind = 'turn'
        ORDER BY id
        """
    ).fetchall()
    violations: Counter[str] = Counter()
    fixable_ids: list[int] = []
    fixable_created_at: list[str] = []
    for row in rows:
        metadata = _safe_metadata_from_json(row["metadata_json"])
        row_reasons: list[str] = []
        if row["summary"] is not None:
            row_reasons.append("summary_present")
        if row["retention_policy"] != "ephemeral":
            row_reasons.append("retention_not_ephemeral")
        if metadata.get("candidate_policy") != "evidence_only":
            row_reasons.append("candidate_policy_not_evidence_only")
        if metadata.get("auto_approved") is not False:
            row_reasons.append("auto_approved_not_false")
        for reason in row_reasons:
            violations[reason] += 1
        metadata_only_fixable = (
            row["summary"] is None
            and row["retention_policy"] == "ephemeral"
            and any(reason in row_reasons for reason in {"candidate_policy_not_evidence_only", "auto_approved_not_false"})
            and not any(reason in row_reasons for reason in {"summary_present", "retention_not_ephemeral"})
        )
        if metadata_only_fixable:
            fixable_ids.append(int(row["id"]))
            if row["created_at"]:
                fixable_created_at.append(str(row["created_at"]))
    affected_count = sum(violations.values())
    return {
        "checked_count": len(rows),
        "affected_count": affected_count,
        "fixable_row_count": len(fixable_ids),
        "violation_counts": dict(sorted(violations.items())),
        "fixable_ids": fixable_ids,
        "earliest_fixable_at": min(fixable_created_at) if fixable_created_at else None,
        "latest_fixable_at": max(fixable_created_at) if fixable_created_at else None,
    }


def _dogfood_ordinary_trace_metadata_cleanup_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    apply_cleanup = bool(getattr(args, "apply", False))
    actor = getattr(args, "actor", None)
    reason = getattr(args, "reason", None)
    kind = (
        "dogfood_ordinary_trace_metadata_cleanup_apply"
        if apply_cleanup
        else "dogfood_ordinary_trace_metadata_cleanup_preview"
    )
    if apply_cleanup and not actor:
        raise ValueError("dogfood ordinary-trace-metadata-cleanup --apply requires --actor")
    if apply_cleanup and not reason:
        raise ValueError("dogfood ordinary-trace-metadata-cleanup --apply requires --reason")
    if not db_path.exists():
        return {
            "kind": kind,
            "read_only": not apply_cleanup,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }
    if not apply_cleanup:
        with _open_readonly_sqlite(db_path) as connection:
            scan = _ordinary_trace_metadata_cleanup_scan(connection)
        warnings: list[str] = []
        if scan["affected_count"]:
            warnings.append("ordinary_trace_metadata_only_violations_present")
        if scan["fixable_row_count"]:
            warnings.append("ordinary_trace_metadata_only_rows_eligible_for_cleanup")
        return {
            "kind": kind,
            "read_only": True,
            "mutated": False,
            "status": "healthy" if not warnings else "warning",
            "database": {"path": str(db_path), "exists": True},
            "checked_count": scan["checked_count"],
            "affected_count": scan["affected_count"],
            "fixable_row_count": scan["fixable_row_count"],
            "violation_counts": scan["violation_counts"],
            "earliest_fixable_at": scan["earliest_fixable_at"],
            "latest_fixable_at": scan["latest_fixable_at"],
            "cleanup_preview": {
                "mutation_required": scan["fixable_row_count"] > 0,
                "recommended_operation": "fill_ordinary_turn_trace_metadata_defaults",
                "apply_command_available": True,
                "apply_guardrails": ["--apply", "--actor", "--reason"],
            },
            "privacy": _ordinary_trace_metadata_cleanup_privacy_payload(),
            "warnings": warnings,
            "suggested_next_steps": [
                "Review this read-only preview before running the explicit cleanup apply command.",
                "Only metadata-only ordinary turn traces with summary=None and retention_policy=ephemeral are eligible.",
            ],
        }

    with connect(db_path) as connection:
        before = _ordinary_trace_metadata_cleanup_scan(connection)
        fixable_ids = list(before["fixable_ids"])
        for trace_id in fixable_ids:
            row = connection.execute(
                "SELECT metadata_json FROM experience_traces WHERE id = ? AND event_kind = 'turn'",
                (trace_id,),
            ).fetchone()
            if row is None:
                continue
            metadata = _safe_metadata_from_json(row["metadata_json"])
            metadata["candidate_policy"] = "evidence_only"
            metadata["auto_approved"] = False
            connection.execute(
                "UPDATE experience_traces SET metadata_json = ? WHERE id = ?",
                (json.dumps(metadata, sort_keys=True), trace_id),
            )
        after = _ordinary_trace_metadata_cleanup_scan(connection)
        reason_sha256 = hashlib.sha256(reason.encode()).hexdigest()
        fixable_ids_sha256 = hashlib.sha256(",".join(str(value) for value in fixable_ids).encode()).hexdigest()
        audit_metadata = {
            "operation": "fill_ordinary_turn_trace_metadata_defaults",
            "actor": actor,
            "reason_sha256": reason_sha256,
            "checked_count": before["checked_count"],
            "affected_before_count": before["affected_count"],
            "fixable_row_count": before["fixable_row_count"],
            "normalized_row_count": len(fixable_ids),
            "remaining_violation_count": after["affected_count"],
            "fixable_ids_sha256": fixable_ids_sha256,
            "raw_trace_content_included": False,
            "sample_values_included": False,
        }
        audit_content_sha256 = hashlib.sha256(json.dumps(audit_metadata, sort_keys=True).encode()).hexdigest()
        cursor = connection.execute(
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
                "dogfood",
                "dogfood_ordinary_trace_metadata_cleanup_apply",
                audit_content_sha256,
                None,
                0.0,
                0.0,
                json.dumps([]),
                json.dumps([]),
                "review",
                json.dumps(audit_metadata, sort_keys=True),
            ),
        )
        audit_trace_id = int(cursor.lastrowid)
    warnings = []
    if after["affected_count"]:
        warnings.append("ordinary_trace_metadata_only_violations_remain_after_cleanup")
    return {
        "kind": kind,
        "read_only": False,
        "mutated": bool(fixable_ids),
        "status": "healthy" if not warnings else "warning",
        "database": {"path": str(db_path), "exists": True},
        "checked_count": before["checked_count"],
        "affected_count": before["affected_count"],
        "fixable_row_count": before["fixable_row_count"],
        "normalized_row_count": len(fixable_ids),
        "remaining_violation_count": after["affected_count"],
        "violation_counts": before["violation_counts"],
        "apply": {
            "actor": actor,
            "reason_sha256": reason_sha256,
            "audit_trace_id": audit_trace_id,
            "fixable_ids_sha256": fixable_ids_sha256,
            "operation": "fill_ordinary_turn_trace_metadata_defaults",
        },
        "privacy": _ordinary_trace_metadata_cleanup_privacy_payload(),
        "warnings": warnings,
        "suggested_next_steps": [
            "Run dogfood storage-health and scheduled-dry-run after apply to confirm ordinary trace metadata warnings are cleared.",
            "Keep cleanup output aggregate-only; never print trace content or metadata sample values.",
        ],
    }


QUERY_PREVIEW_CLEANUP_POLICY = "legacy-query-preview-cleanup-v1"
QUERY_PREVIEW_CLEANUP_RESTORE_POLICY = "legacy-query-preview-cleanup-restore-v1"


def _query_preview_cleanup_privacy_payload() -> dict[str, bool]:
    return {
        "raw_query_preview_included": False,
        "sample_values_included": False,
        "hash_only": True,
    }


def _query_preview_cleanup_counts(connection: sqlite3.Connection, *, older_than: str) -> tuple[sqlite3.Row, sqlite3.Row]:
    affected = connection.execute(
        """
        SELECT COUNT(*) AS count, MIN(created_at) AS earliest, MAX(created_at) AS latest
        FROM retrieval_observations
        WHERE COALESCE(query_preview, '') <> ''
        """
    ).fetchone()
    eligible = connection.execute(
        """
        SELECT COUNT(*) AS count, MIN(created_at) AS earliest, MAX(created_at) AS latest
        FROM retrieval_observations
        WHERE COALESCE(query_preview, '') <> '' AND created_at < ?
        """,
        (older_than,),
    ).fetchone()
    return affected, eligible


def _query_preview_cleanup_eligible_rows(connection: sqlite3.Connection, *, older_than: str) -> list[dict[str, Any]]:
    return [
        {"id": int(row["id"]), "query_preview": row["query_preview"], "created_at": row["created_at"]}
        for row in connection.execute(
            """
            SELECT id, query_preview, created_at
            FROM retrieval_observations
            WHERE COALESCE(query_preview, '') <> '' AND created_at < ?
            ORDER BY id
            """,
            (older_than,),
        ).fetchall()
    ]


def _query_preview_cleanup_ids_sha256(eligible_ids: list[int]) -> str:
    return hashlib.sha256(",".join(str(value) for value in eligible_ids).encode()).hexdigest()


def _query_preview_cleanup_source_database_fingerprint(db_path: Path) -> dict[str, Any]:
    resolved_path = db_path.expanduser().resolve(strict=False)
    fingerprint_sha256 = hashlib.sha256(
        f"query-preview-cleanup-source-db-v1\0{resolved_path}".encode()
    ).hexdigest()
    return {
        "fingerprint_sha256": fingerprint_sha256,
        "fingerprint_version": "query-preview-cleanup-source-db-v1",
        "path_sha256": hashlib.sha256(str(resolved_path).encode()).hexdigest(),
        "path_basename": resolved_path.name,
    }


def _write_query_preview_cleanup_rollback_manifest(
    *,
    db_path: Path,
    older_than: str,
    policy: str,
    eligible_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    eligible_ids = [row["id"] for row in eligible_rows]
    source_database = _query_preview_cleanup_source_database_fingerprint(db_path)
    rollback_artifact = {
        "kind": "query_preview_cleanup_rollback_artifact",
        "policy": policy,
        "operation": "restore_stored_query_excerpts",
        "parameters": {"older_than": older_than},
        "source_database": source_database,
        "row_count": len(eligible_rows),
        "rows": eligible_rows,
        "privacy": {
            "artifact_contains_private_query_preview": True,
            "do_not_commit": True,
        },
    }
    rollback_artifact_text = json.dumps(rollback_artifact, sort_keys=True, indent=2)
    rollback_artifact_sha256 = hashlib.sha256(rollback_artifact_text.encode()).hexdigest()
    rollback_dir = db_path.parent / ".agent-memory-query-preview-cleanup-rollbacks"
    rollback_dir.mkdir(parents=True, exist_ok=True)
    rollback_artifact_path = rollback_dir / f"query-preview-cleanup-{rollback_artifact_sha256[:16]}.json"
    rollback_artifact_path.write_text(rollback_artifact_text)
    return {
        "kind": "query_preview_cleanup_rollback_manifest",
        "policy": policy,
        "operation": "restore_stored_query_excerpts",
        "artifact_path": str(rollback_artifact_path),
        "artifact_sha256": rollback_artifact_sha256,
        "source_database": source_database,
        "row_count": len(eligible_rows),
        "eligible_ids_sha256": _query_preview_cleanup_ids_sha256(eligible_ids),
        "privacy": {
            "raw_query_preview_included_in_output": False,
            "artifact_contains_private_query_preview": True,
        },
    }


def _apply_query_preview_cleanup_to_connection(
    connection: sqlite3.Connection,
    *,
    older_than: str,
    db_path: Path,
    policy: str,
) -> tuple[list[int], sqlite3.Row, dict[str, Any]]:
    eligible_rows = _query_preview_cleanup_eligible_rows(connection, older_than=older_than)
    eligible_ids = [row["id"] for row in eligible_rows]
    rollback_manifest = _write_query_preview_cleanup_rollback_manifest(
        db_path=db_path,
        older_than=older_than,
        policy=policy,
        eligible_rows=eligible_rows,
    )
    if eligible_ids:
        connection.execute(
            """
            UPDATE retrieval_observations
            SET query_preview = NULL
            WHERE COALESCE(query_preview, '') <> '' AND created_at < ?
            """,
            (older_than,),
        )
    affected_after, _eligible_after = _query_preview_cleanup_counts(connection, older_than=older_than)
    return eligible_ids, affected_after, rollback_manifest


def _run_query_preview_cleanup_disposable_apply_check(
    *,
    db_path: Path,
    older_than: str,
    policy: str,
    expected_eligible_count: int,
    expected_remaining_affected_count: int,
) -> dict[str, Any]:
    disposable_dir = db_path.parent / ".agent-memory-query-preview-cleanup-disposable-checks"
    disposable_dir.mkdir(parents=True, exist_ok=True)
    source_fingerprint = hashlib.sha256(f"{db_path}:{older_than}:{policy}".encode()).hexdigest()[:16]
    disposable_db_path = disposable_dir / f"query-preview-cleanup-check-{source_fingerprint}.db"
    if disposable_db_path.exists():
        disposable_db_path.unlink()
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source_connection:
        with sqlite3.connect(disposable_db_path) as backup_connection:
            source_connection.backup(backup_connection)
    with connect(disposable_db_path) as disposable_connection:
        disposable_affected_before, disposable_eligible_before = _query_preview_cleanup_counts(
            disposable_connection,
            older_than=older_than,
        )
        disposable_eligible_ids, disposable_affected_after, disposable_rollback_manifest = (
            _apply_query_preview_cleanup_to_connection(
                disposable_connection,
                older_than=older_than,
                db_path=disposable_db_path,
                policy=policy,
            )
        )
    cleared_count = len(disposable_eligible_ids)
    remaining_affected_count = int(disposable_affected_after["count"])
    checks_passed = (
        int(disposable_eligible_before["count"]) == expected_eligible_count
        and cleared_count == expected_eligible_count
        and remaining_affected_count == expected_remaining_affected_count
        and disposable_rollback_manifest["row_count"] == expected_eligible_count
    )
    return {
        "kind": "query_preview_cleanup_disposable_apply_check",
        "status": "passed" if checks_passed else "failed",
        "live_database_mutated_before_check": False,
        "checked_database_path": str(disposable_db_path),
        "affected_before_count": int(disposable_affected_before["count"]),
        "eligible_count": int(disposable_eligible_before["count"]),
        "cleared_count": cleared_count,
        "remaining_affected_count": remaining_affected_count,
        "expected": {
            "eligible_count": expected_eligible_count,
            "cleared_count": expected_eligible_count,
            "remaining_affected_count": expected_remaining_affected_count,
        },
        "rollback_manifest": disposable_rollback_manifest,
        "privacy": {
            "raw_query_preview_included_in_output": False,
            "disposable_copy_contains_private_query_preview": True,
        },
    }



def _run_query_preview_cleanup_restore_disposable_rehearsal(
    *,
    db_path: Path,
    artifact_sha256: str,
    candidate_rows: list[dict[str, Any]],
    expected_restorable_count: int,
) -> dict[str, Any]:
    disposable_dir = db_path.parent / ".agent-memory-query-preview-restore-disposable-checks"
    disposable_dir.mkdir(parents=True, exist_ok=True)
    source_fingerprint = hashlib.sha256(f"{db_path}:{artifact_sha256}".encode()).hexdigest()[:16]
    disposable_db_path = disposable_dir / f"query-preview-restore-check-{source_fingerprint}.db"
    if disposable_db_path.exists():
        disposable_db_path.unlink()
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as source_connection:
        with sqlite3.connect(disposable_db_path) as backup_connection:
            source_connection.backup(backup_connection)

    restored_count = 0
    post_restore_missing_count = 0
    post_restore_still_empty_count = 0
    with connect(disposable_db_path) as disposable_connection:
        if not _table_exists(disposable_connection, "retrieval_observations"):
            post_restore_missing_count = len(candidate_rows)
        else:
            for row in candidate_rows:
                target_row = disposable_connection.execute(
                    "SELECT query_preview FROM retrieval_observations WHERE id = ?",
                    (row["id"],),
                ).fetchone()
                if target_row is None:
                    post_restore_missing_count += 1
                    continue
                if target_row["query_preview"] in (None, ""):
                    disposable_connection.execute(
                        "UPDATE retrieval_observations SET query_preview = ? WHERE id = ?",
                        (row["query_preview"], row["id"]),
                    )
                    restored_count += 1
            for row in candidate_rows:
                target_row = disposable_connection.execute(
                    "SELECT query_preview FROM retrieval_observations WHERE id = ?",
                    (row["id"],),
                ).fetchone()
                if target_row is not None and target_row["query_preview"] in (None, ""):
                    post_restore_still_empty_count += 1

    checks_passed = (
        restored_count == expected_restorable_count
        and post_restore_missing_count == 0
        and post_restore_still_empty_count == 0
    )
    return {
        "kind": "query_preview_cleanup_restore_disposable_rehearsal",
        "status": "passed" if checks_passed else "failed",
        "live_database_mutated_before_check": False,
        "checked_database_path": str(disposable_db_path),
        "candidate_restore_count": len(candidate_rows),
        "restored_count": restored_count,
        "post_restore_missing_count": post_restore_missing_count,
        "post_restore_still_empty_count": post_restore_still_empty_count,
        "expected": {
            "restored_count": expected_restorable_count,
        },
        "privacy": {
            "raw_query_preview_included_in_output": False,
            "disposable_copy_contains_private_query_preview": True,
        },
    }


def _dogfood_query_preview_cleanup_restore_dry_run_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    artifact_path = args.rollback_artifact_path.expanduser().resolve(strict=False)
    dry_run = bool(getattr(args, "dry_run", False))
    apply_restore = bool(getattr(args, "apply", False))
    actor = getattr(args, "actor", None)
    reason = getattr(args, "reason", None)
    restore_policy = getattr(args, "restore_policy", None)
    approval_token = getattr(args, "approval_token", None)
    approval_token_present = bool(approval_token)
    approval_token_sha256 = hashlib.sha256(approval_token.encode()).hexdigest() if approval_token_present else None
    approval_token_expected_sha256_raw = getattr(args, "approval_token_expected_sha256", None)
    approval_token_expected_sha256 = (
        approval_token_expected_sha256_raw.strip().lower() if approval_token_expected_sha256_raw else None
    )
    approval_token_expected_sha256_present = bool(approval_token_expected_sha256)
    approval_token_hash_matches_expected = (
        approval_token_sha256 == approval_token_expected_sha256
        if approval_token_present and approval_token_expected_sha256_present
        else None
    )
    approval_token_expected_sha256_fingerprint_sha256 = (
        hashlib.sha256(approval_token_expected_sha256.encode()).hexdigest()
        if approval_token_expected_sha256_present
        else None
    )
    approval_token_validated = approval_token_hash_matches_expected is True
    if not approval_token_present:
        approval_token_validation_status = "missing"
    elif not approval_token_expected_sha256_present:
        approval_token_validation_status = "expected_hash_missing"
    elif not approval_token_hash_matches_expected:
        approval_token_validation_status = "hash_mismatch"
    else:
        approval_token_validation_status = "validated_by_expected_sha256"
    approval_token_invalid = approval_token_present and not approval_token_validated
    if not dry_run and not apply_restore:
        raise ValueError("dogfood query-preview-cleanup-restore currently requires --dry-run or --apply")
    if apply_restore and restore_policy != QUERY_PREVIEW_CLEANUP_RESTORE_POLICY:
        raise ValueError(
            "dogfood query-preview-cleanup-restore --apply requires "
            f"--policy {QUERY_PREVIEW_CLEANUP_RESTORE_POLICY}"
        )
    if apply_restore and not actor:
        raise ValueError("dogfood query-preview-cleanup-restore --apply requires --actor")
    if apply_restore and not reason:
        raise ValueError("dogfood query-preview-cleanup-restore --apply requires --reason")
    kind = (
        "dogfood_query_preview_cleanup_restore_apply_blocked"
        if apply_restore
        else "dogfood_query_preview_cleanup_restore_dry_run"
    )
    if not db_path.exists():
        return {
            "kind": kind,
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "artifact": {"path": str(artifact_path), "exists": artifact_path.exists()},
            "warnings": ["database_missing"],
        }
    if not artifact_path.exists():
        return {
            "kind": kind,
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": True},
            "artifact": {"path": str(artifact_path), "exists": False},
            "warnings": ["rollback_artifact_missing"],
        }
    artifact_text = artifact_path.read_text()
    artifact_sha256 = hashlib.sha256(artifact_text.encode()).hexdigest()
    try:
        artifact_payload = json.loads(artifact_text)
    except json.JSONDecodeError as exc:
        raise ValueError("query-preview-cleanup restore artifact must be valid JSON") from exc
    artifact_kind = artifact_payload.get("kind")
    if artifact_kind != "query_preview_cleanup_rollback_artifact":
        return {
            "kind": kind,
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": True},
            "artifact": {
                "kind": artifact_kind,
                "path": str(artifact_path),
                "exists": True,
                "artifact_sha256": artifact_sha256,
            },
            "restore_preview": {
                "operation": "restore_stored_query_excerpts",
                "dry_run": True,
                "restore_apply_available": False,
                "candidate_restore_count": 0,
                "target_rows_found_count": 0,
                "restorable_count": 0,
                "already_has_query_preview_count": 0,
                "missing_row_count": 0,
                "skipped_count": 0,
            },
            "privacy": {
                "raw_query_preview_included": False,
                "sample_values_included": False,
                "artifact_contains_private_query_preview": False,
            },
            "blocked_reasons": ["artifact_kind_invalid", "live_restore_not_implemented"],
            "warnings": ["artifact_kind_invalid", "live_restore_not_implemented"],
        }
    policy = artifact_payload.get("policy")
    if policy != QUERY_PREVIEW_CLEANUP_POLICY:
        return {
            "kind": kind,
            "read_only": True,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": True},
            "artifact": {
                "kind": artifact_kind,
                "path": str(artifact_path),
                "exists": True,
                "policy": policy,
                "artifact_sha256": artifact_sha256,
            },
            "restore_preview": {
                "operation": "restore_stored_query_excerpts",
                "dry_run": True,
                "restore_apply_available": False,
                "candidate_restore_count": 0,
                "target_rows_found_count": 0,
                "restorable_count": 0,
                "already_has_query_preview_count": 0,
                "missing_row_count": 0,
                "skipped_count": 0,
            },
            "privacy": {
                "raw_query_preview_included": False,
                "sample_values_included": False,
                "artifact_contains_private_query_preview": False,
            },
            "blocked_reasons": ["artifact_policy_invalid", "live_restore_not_implemented"],
            "warnings": ["artifact_policy_invalid", "live_restore_not_implemented"],
        }
    rows = artifact_payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("query-preview-cleanup restore artifact rows must be a list")
    candidate_rows: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("id"), int):
            raise ValueError("query-preview-cleanup restore artifact rows must include integer id values")
        query_preview = row.get("query_preview")
        if not isinstance(query_preview, str) or query_preview == "":
            raise ValueError("query-preview-cleanup restore artifact rows must include non-empty query_preview values")
        created_at = row.get("created_at")
        candidate_rows.append({"id": int(row["id"]), "query_preview": query_preview, "created_at": created_at})
    candidate_ids = [row["id"] for row in candidate_rows]
    duplicate_id_count = len(candidate_ids) - len(set(candidate_ids))
    declared_row_count = artifact_payload.get("row_count")
    declared_row_count_matches = declared_row_count == len(candidate_rows)
    operation = artifact_payload.get("operation")
    operation_valid = operation == "restore_stored_query_excerpts"
    eligible_ids_sha256 = _query_preview_cleanup_ids_sha256(candidate_ids)
    artifact_source_database = artifact_payload.get("source_database")
    artifact_source_fingerprint = (
        artifact_source_database.get("fingerprint_sha256") if isinstance(artifact_source_database, dict) else None
    )
    target_source_database = _query_preview_cleanup_source_database_fingerprint(db_path)
    source_database_matched = artifact_source_fingerprint == target_source_database["fingerprint_sha256"]
    target_rows_found_count = 0
    restorable_count = 0
    restorable_ids: list[int] = []
    already_has_query_preview_count = 0
    missing_row_count = 0
    artifact_integrity_passed = duplicate_id_count == 0 and declared_row_count_matches and operation_valid
    if source_database_matched and artifact_integrity_passed:
        with _open_readonly_sqlite(db_path) as connection:
            if not _table_exists(connection, "retrieval_observations"):
                missing_row_count = len(candidate_rows)
            else:
                for row in candidate_rows:
                    target_row = connection.execute(
                        "SELECT query_preview FROM retrieval_observations WHERE id = ?",
                        (row["id"],),
                    ).fetchone()
                    if target_row is None:
                        missing_row_count += 1
                        continue
                    target_rows_found_count += 1
                    if target_row["query_preview"] in (None, ""):
                        restorable_count += 1
                        restorable_ids.append(row["id"])
                    else:
                        already_has_query_preview_count += 1
    skipped_count = already_has_query_preview_count + missing_row_count
    if not source_database_matched:
        skipped_count = len(candidate_rows)
    if source_database_matched and not artifact_integrity_passed:
        skipped_count = len(candidate_rows)
    warnings = ["live_restore_not_implemented"]
    blocked_reasons = ["live_restore_not_implemented"]
    if artifact_source_fingerprint is None:
        warnings.append("source_database_fingerprint_missing")
        blocked_reasons.append("source_database_fingerprint_missing")
    elif not source_database_matched:
        warnings.append("source_database_mismatch")
        blocked_reasons.append("source_database_mismatch")
    if not operation_valid:
        warnings.append("artifact_operation_invalid")
        blocked_reasons.append("artifact_operation_invalid")
    if not declared_row_count_matches:
        warnings.append("artifact_row_count_mismatch")
        blocked_reasons.append("artifact_row_count_mismatch")
    if duplicate_id_count:
        warnings.append("duplicate_artifact_row_ids")
        blocked_reasons.append("duplicate_artifact_row_ids")
    if skipped_count and source_database_matched and artifact_integrity_passed:
        warnings.append("some_artifact_rows_are_not_currently_restorable")
    restore_disposable_rehearsal = None
    if apply_restore and source_database_matched and artifact_integrity_passed:
        restore_disposable_rehearsal = _run_query_preview_cleanup_restore_disposable_rehearsal(
            db_path=db_path,
            artifact_sha256=artifact_sha256,
            candidate_rows=candidate_rows,
            expected_restorable_count=restorable_count,
        )
        if restore_disposable_rehearsal["status"] != "passed":
            warnings.append("restore_disposable_rehearsal_failed")
            blocked_reasons.append("restore_disposable_rehearsal_failed")
    status = "error" if apply_restore or not source_database_matched or not artifact_integrity_passed else "warning"
    if apply_restore and (not source_database_matched or not artifact_integrity_passed):
        warnings.append("restore_apply_contract_checkpoint_only")
        blocked_reasons.append("restore_apply_contract_checkpoint_only")
    payload = {
        "kind": kind,
        "read_only": True,
        "mutated": False,
        "status": status,
        "database": {"path": str(db_path), "exists": True},
        "artifact": {
            "kind": artifact_payload["kind"],
            "path": str(artifact_path),
            "exists": True,
            "policy": policy,
            "operation": operation,
            "parameters": artifact_payload.get("parameters", {}),
            "row_count": len(candidate_rows),
            "declared_row_count": declared_row_count,
            "artifact_sha256": artifact_sha256,
            "eligible_ids_sha256": eligible_ids_sha256,
            "source_database": artifact_source_database if isinstance(artifact_source_database, dict) else None,
        },
        "artifact_integrity": {
            "passed": artifact_integrity_passed,
            "operation_valid": operation_valid,
            "declared_row_count_matches": declared_row_count_matches,
            "duplicate_id_count": duplicate_id_count,
        },
        "source_database_match": {
            "matched": source_database_matched,
            "artifact_fingerprint_sha256": artifact_source_fingerprint,
            "target_fingerprint_sha256": target_source_database["fingerprint_sha256"],
            "fingerprint_version": target_source_database["fingerprint_version"],
            "target_path_basename": target_source_database["path_basename"],
        },
        "restore_preview": {
            "operation": "restore_stored_query_excerpts",
            "dry_run": dry_run,
            "apply_requested": apply_restore,
            "restore_apply_available": False,
            "candidate_restore_count": len(candidate_rows),
            "target_rows_found_count": target_rows_found_count,
            "restorable_count": restorable_count,
            "already_has_query_preview_count": already_has_query_preview_count,
            "missing_row_count": missing_row_count,
            "skipped_count": skipped_count,
        },
        "privacy": {
            "raw_query_preview_included": False,
            "sample_values_included": False,
            "artifact_contains_private_query_preview": True,
        },
        "blocked_reasons": blocked_reasons,
        "warnings": warnings,
        "suggested_next_steps": [
            "Inspect this dry-run summary before considering any future explicit restore apply command.",
            "Keep rollback artifacts private; they contain stored query preview values.",
        ],
    }
    if apply_restore:
        payload["restore_apply_contract"] = {
            "policy": restore_policy,
            "actor": actor,
            "reason_sha256": hashlib.sha256(reason.encode()).hexdigest(),
            "reason_raw_stored": False,
            "disposable_restore_check_required": True,
            "disposable_restore_rehearsal": restore_disposable_rehearsal,
            "source_database_match_required": True,
            "artifact_integrity_required": True,
            "audit_raw_query_preview_allowed": False,
            "rollback_artifact_private_required": True,
            "broad_g4_apply_allowed": False,
        }
        audit_preview_fields = {
            "policy": restore_policy,
            "actor": actor,
            "reason_sha256": payload["restore_apply_contract"]["reason_sha256"],
            "artifact_sha256": artifact_sha256,
            "source_database_fingerprint_sha256": target_source_database["fingerprint_sha256"],
            "source_database_match": source_database_matched,
            "artifact_integrity_passed": artifact_integrity_passed,
            "rehearsal_status": restore_disposable_rehearsal["status"] if restore_disposable_rehearsal else None,
            "restored_ids_sha256": _query_preview_cleanup_ids_sha256(restorable_ids),
            "restored_count": restorable_count,
        }
        audit_metadata_json = json.dumps(audit_preview_fields, sort_keys=True)
        audit_metadata_json_sha256 = hashlib.sha256(audit_metadata_json.encode()).hexdigest()
        audit_write_privacy = {
            "raw_query_preview_included": False,
            "raw_reason_included": False,
            "sample_values_included": False,
        }
        audit_insert_preview = {
            "surface": "dogfood",
            "event_kind": "dogfood_query_preview_cleanup_restore_apply",
            "content_sha256": audit_metadata_json_sha256,
            "summary": None,
            "salience": 0.0,
            "user_emphasis": 0.0,
            "related_memory_refs_json": [],
            "related_observation_ids_json": [],
            "retention_policy": "review",
            "metadata_json_sha256": audit_metadata_json_sha256,
        }
        audit_row_materialization = {
            "kind": "query_preview_cleanup_restore_audit_row_materialization",
            "status": "dry_run_blocked",
            "target_table": "experience_traces",
            "would_insert": False,
            "write_allowed": False,
            "schema_version": "query-preview-cleanup-restore-audit-row-v1",
            "duplicate_key": {
                "surface": audit_insert_preview["surface"],
                "event_kind": audit_insert_preview["event_kind"],
                "content_sha256": audit_insert_preview["content_sha256"],
                "metadata_json_sha256": audit_insert_preview["metadata_json_sha256"],
            },
            "columns": [
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
            ],
            "values": {
                "surface": audit_insert_preview["surface"],
                "event_kind": audit_insert_preview["event_kind"],
                "content_sha256": audit_insert_preview["content_sha256"],
                "summary": audit_insert_preview["summary"],
                "salience": audit_insert_preview["salience"],
                "user_emphasis": audit_insert_preview["user_emphasis"],
                "related_memory_refs_json": json.dumps(audit_insert_preview["related_memory_refs_json"]),
                "related_observation_ids_json": json.dumps(audit_insert_preview["related_observation_ids_json"]),
                "retention_policy": audit_insert_preview["retention_policy"],
                "metadata_json": audit_metadata_json,
            },
            "metadata_json_canonical": audit_metadata_json,
            "metadata_json_sha256": audit_metadata_json_sha256,
            "content_sha256": audit_metadata_json_sha256,
            "privacy": audit_write_privacy,
        }
        duplicate_audit_event_count = 0
        with _open_readonly_sqlite(db_path) as connection:
            if _table_exists(connection, "experience_traces"):
                duplicate_audit_event_count = connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM experience_traces
                    WHERE surface = ?
                      AND event_kind = ?
                      AND content_sha256 = ?
                      AND metadata_json = ?
                    """,
                    (
                        audit_insert_preview["surface"],
                        audit_insert_preview["event_kind"],
                        audit_insert_preview["content_sha256"],
                        audit_metadata_json,
                    ),
                ).fetchone()[0]
        audit_write_apply_blocked_reasons = ["live_restore_not_implemented"]
        audit_write_conflict_policy = {
            "duplicate_audit_event": "fail_closed",
            "content_hash_mismatch": "fail_closed",
            "metadata_hash_mismatch": "fail_closed",
            "source_database_mismatch": "fail_closed",
            "artifact_integrity_failure": "fail_closed",
            "disposable_rehearsal_failure": "fail_closed",
            "privacy_leak_risk": "fail_closed",
        }
        audit_write_preflight_checks = {
            "policy_matches_required": True,
            "actor_present": bool(actor),
            "reason_sha256_matches_restore_contract": True,
            "source_database_match_passed": source_database_matched,
            "artifact_integrity_passed": artifact_integrity_passed,
            "disposable_rehearsal_passed": bool(
                restore_disposable_rehearsal and restore_disposable_rehearsal["status"] == "passed"
            ),
            "content_sha256_matches_insert_preview": audit_metadata_json_sha256
            == audit_insert_preview["content_sha256"],
            "metadata_json_sha256_matches_insert_preview": audit_metadata_json_sha256
            == audit_insert_preview["metadata_json_sha256"],
            "duplicate_audit_event_absent": duplicate_audit_event_count == 0,
            "raw_query_preview_allowed": False,
            "raw_reason_allowed": False,
            "sample_values_allowed": False,
            "broad_g4_apply_allowed": False,
        }
        required_audit_write_preflight_checks = (
            "policy_matches_required",
            "actor_present",
            "reason_sha256_matches_restore_contract",
            "source_database_match_passed",
            "artifact_integrity_passed",
            "disposable_rehearsal_passed",
            "content_sha256_matches_insert_preview",
            "metadata_json_sha256_matches_insert_preview",
            "duplicate_audit_event_absent",
        )
        audit_write_preflight_failed_checks = [
            key for key in required_audit_write_preflight_checks if audit_write_preflight_checks[key] is not True
        ]
        if audit_write_preflight_failed_checks:
            audit_write_apply_blocked_reasons.append("restore_audit_write_preflight_failed")
        if not audit_write_preflight_checks["duplicate_audit_event_absent"]:
            audit_write_apply_blocked_reasons.append("duplicate_restore_audit_event")
        if not audit_write_preflight_checks["content_sha256_matches_insert_preview"]:
            audit_write_apply_blocked_reasons.append("restore_audit_write_content_hash_mismatch")
        if not audit_write_preflight_checks["metadata_json_sha256_matches_insert_preview"]:
            audit_write_apply_blocked_reasons.append("restore_audit_write_metadata_hash_mismatch")
        if not audit_write_preflight_checks["source_database_match_passed"]:
            audit_write_apply_blocked_reasons.append("restore_audit_write_source_database_mismatch")
        if not audit_write_preflight_checks["artifact_integrity_passed"]:
            audit_write_apply_blocked_reasons.append("restore_audit_write_artifact_integrity_failed")
        if not audit_write_preflight_checks["disposable_rehearsal_passed"]:
            audit_write_apply_blocked_reasons.append("restore_audit_write_disposable_rehearsal_failed")
        audit_write_preflight_passed = not audit_write_preflight_failed_checks
        audit_write_preflight = {
            "kind": "query_preview_cleanup_restore_audit_write_preflight",
            "status": "passed_but_write_blocked" if audit_write_preflight_passed else "failed_blocked",
            "passed": audit_write_preflight_passed,
            "write_allowed": False,
            "write_blocked_by_preflight": not audit_write_preflight_passed,
            "duplicate_audit_event_count": duplicate_audit_event_count,
            "checked_content_sha256": audit_metadata_json_sha256,
            "checked_metadata_json_sha256": audit_metadata_json_sha256,
            "checks": audit_write_preflight_checks,
            "failed_checks": audit_write_preflight_failed_checks,
            "conflict_policy": audit_write_conflict_policy,
            "blocked_reasons": audit_write_apply_blocked_reasons,
        }
        if approval_token_present and approval_token_expected_sha256_present and not approval_token_hash_matches_expected:
            audit_write_apply_blocked_reasons.append("restore_audit_write_approval_token_hash_mismatch")
        elif approval_token_present and approval_token_expected_sha256_present:
            pass
        elif approval_token_present:
            audit_write_apply_blocked_reasons.append("restore_audit_write_approval_token_expected_hash_missing")
        else:
            audit_write_apply_blocked_reasons.append("restore_audit_write_approval_token_missing")
        audit_write_allowed = (
            apply_restore
            and audit_write_preflight_passed
            and approval_token_validated
            and source_database_matched
            and artifact_integrity_passed
        )
        audit_inserted_trace_id = None
        if audit_write_allowed:
            audit_trace = insert_experience_trace(
                db_path,
                surface=audit_insert_preview["surface"],
                event_kind=audit_insert_preview["event_kind"],
                content_sha256=audit_insert_preview["content_sha256"],
                summary=audit_insert_preview["summary"],
                salience=audit_insert_preview["salience"],
                user_emphasis=audit_insert_preview["user_emphasis"],
                related_memory_refs=audit_insert_preview["related_memory_refs_json"],
                related_observation_ids=audit_insert_preview["related_observation_ids_json"],
                retention_policy=audit_insert_preview["retention_policy"],
                metadata=audit_preview_fields,
            )
            audit_inserted_trace_id = audit_trace.id
            payload.update(
                {
                    "read_only": False,
                    "mutated": True,
                    "status": "audit_written_restore_blocked",
                    "audit_trace_mutated": True,
                    "live_restore_mutated": False,
                    "blocked_reasons": ["live_restore_not_implemented"],
                    "warnings": ["live_restore_not_implemented"],
                }
            )
        else:
            payload.update({"audit_trace_mutated": False, "live_restore_mutated": False})
        audit_write_preflight["status"] = (
            "passed" if audit_write_allowed else "passed_but_write_blocked" if audit_write_preflight_passed else "failed_blocked"
        )
        audit_write_preflight["write_allowed"] = audit_write_allowed
        audit_row_materialization["status"] = "inserted" if audit_write_allowed else "dry_run_blocked"
        audit_row_materialization["would_insert"] = audit_write_allowed
        audit_row_materialization["write_allowed"] = audit_write_allowed
        if audit_inserted_trace_id is not None:
            audit_row_materialization["inserted_trace_id"] = audit_inserted_trace_id
        audit_write_single_row_apply_policy_packet = {
            "kind": "query_preview_cleanup_restore_audit_write_single_row_apply_policy_packet",
            "status": "validated_write_allowed" if audit_write_allowed else "approval_required_write_blocked",
            "requires_explicit_operator_approval": True,
            "approval_token_required": True,
            "approval_token_present": approval_token_present,
            "approval_token_sha256": approval_token_sha256,
            "approval_token_expected_sha256_required": True,
            "approval_token_expected_sha256_present": approval_token_expected_sha256_present,
            "approval_token_expected_sha256": approval_token_expected_sha256,
            "approval_token_expected_sha256_fingerprint_sha256": approval_token_expected_sha256_fingerprint_sha256,
            "approval_token_hash_matches_expected": approval_token_hash_matches_expected,
            "approval_token_validated": approval_token_validated,
            "approval_token_validation_status": approval_token_validation_status,
            "write_blocked_by_missing_approval": not approval_token_present,
            "write_blocked_by_unvalidated_approval": approval_token_present and not approval_token_validated,
            "write_blocked_by_invalid_approval": approval_token_invalid,
            "write_blocked_by_missing_expected_approval_hash": approval_token_present
            and not approval_token_expected_sha256_present,
            "write_blocked_by_approval_hash_mismatch": approval_token_hash_matches_expected is False,
            "write_blocked_by_unimplemented_approval_validation": False,
            "would_insert": audit_write_allowed,
            "write_allowed": audit_write_allowed,
            "inserted_trace_id": audit_inserted_trace_id,
            "expected_insert_count": 1,
            "required_policy": "legacy-query-preview-cleanup-restore-audit-write-v1",
            "actor": actor,
            "reason_sha256": payload["restore_apply_contract"]["reason_sha256"],
            "source_database_fingerprint_sha256": target_source_database["fingerprint_sha256"],
            "artifact_sha256": artifact_sha256,
            "rehearsal_status": restore_disposable_rehearsal["status"] if restore_disposable_rehearsal else None,
            "preflight_passed": audit_write_preflight_passed,
            "duplicate_audit_event_count": duplicate_audit_event_count,
            "row_materialization_sha256": audit_row_materialization["metadata_json_sha256"],
            "row_schema_version": audit_row_materialization["schema_version"],
            "blocked_reasons": audit_write_apply_blocked_reasons,
            "rollback": {
                "undo_requires_manual_audit_trace_review": True,
                "live_restore_enabled": False,
                "inserted_trace_id": audit_inserted_trace_id,
                "audit_row_delete_enabled": False,
            },
            "privacy": audit_write_privacy,
        }
        payload["restore_apply_contract"]["audit_preview"] = {
            "kind": "query_preview_cleanup_restore_audit_preview",
            "audit_write_available": audit_write_allowed,
            "audit_row_would_be_written": audit_write_allowed,
            "audit_row_written": audit_write_allowed,
            "fields": audit_preview_fields,
            "write_dry_run": {
                "kind": "query_preview_cleanup_restore_audit_write_dry_run",
                "status": "inserted" if audit_write_allowed else "blocked",
                "would_insert": audit_write_allowed,
                "inserted": audit_write_allowed,
                "inserted_trace_id": audit_inserted_trace_id,
                "target_table": "experience_traces",
                "event_kind": "dogfood_query_preview_cleanup_restore_apply",
                "retention_policy": "review",
                "content_sha256": audit_metadata_json_sha256,
                "metadata_json_sha256": audit_metadata_json_sha256,
                "metadata_json_preview": audit_preview_fields,
                "row_materialization": audit_row_materialization,
                "apply_contract": {
                    "kind": "query_preview_cleanup_restore_audit_write_apply_contract",
                    "audit_write_apply_available": audit_write_allowed,
                    "would_insert": audit_write_allowed,
                    "inserted": audit_write_allowed,
                    "inserted_trace_id": audit_inserted_trace_id,
                    "required_policy": "legacy-query-preview-cleanup-restore-audit-write-v1",
                    "required_actor": actor,
                    "required_reason_sha256": payload["restore_apply_contract"]["reason_sha256"],
                    "target_table": "experience_traces",
                    "event_kind": "dogfood_query_preview_cleanup_restore_apply",
                    "retention_policy": "review",
                    "blocked_reasons": audit_write_apply_blocked_reasons,
                    "requirements": {
                        "restore_apply_contract_required": True,
                        "source_database_match_required": True,
                        "artifact_integrity_required": True,
                        "disposable_restore_rehearsal_required": True,
                        "audit_metadata_json_sha256_required": True,
                        "raw_query_preview_allowed": False,
                        "raw_reason_allowed": False,
                        "sample_values_allowed": False,
                        "broad_g4_apply_allowed": False,
                    },
                    "insert_preview": audit_insert_preview,
                    "preflight": audit_write_preflight,
                    "single_row_apply_policy_packet": audit_write_single_row_apply_policy_packet,
                    "privacy": audit_write_privacy,
                },
                "privacy": audit_write_privacy,
            },
            "privacy": {
                "raw_query_preview_allowed": False,
                "raw_reason_allowed": False,
                "sample_values_allowed": False,
            },
        }
        payload["suggested_next_steps"] = [
            "Do not run live restore yet; this command is a contract checkpoint only.",
            "Implement a separate disposable-restore rehearsal and audit path before enabling any mutation.",
            "Keep rollback artifacts private; they contain stored query preview values.",
        ]
    return payload


def _dogfood_query_preview_cleanup_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    older_than = args.older_than
    apply_cleanup = bool(getattr(args, "apply", False))
    actor = getattr(args, "actor", None)
    reason = getattr(args, "reason", None)
    policy = getattr(args, "policy", None)
    kind = "dogfood_query_preview_cleanup_apply" if apply_cleanup else "dogfood_query_preview_cleanup_preview"
    if apply_cleanup and not policy:
        raise ValueError("dogfood query-preview-cleanup --apply requires --policy")
    if apply_cleanup and policy != QUERY_PREVIEW_CLEANUP_POLICY:
        raise ValueError(
            "dogfood query-preview-cleanup --apply requires "
            f"--policy {QUERY_PREVIEW_CLEANUP_POLICY}"
        )
    if apply_cleanup and not actor:
        raise ValueError("dogfood query-preview-cleanup --apply requires --actor")
    if apply_cleanup and not reason:
        raise ValueError("dogfood query-preview-cleanup --apply requires --reason")
    if not db_path.exists():
        return {
            "kind": kind,
            "read_only": not apply_cleanup,
            "mutated": False,
            "status": "error",
            "database": {"path": str(db_path), "exists": False},
            "warnings": ["database_missing"],
        }
    if apply_cleanup:
        with connect(db_path) as connection:
            if not _table_exists(connection, "retrieval_observations"):
                return {
                    "kind": kind,
                    "read_only": False,
                    "mutated": False,
                    "status": "warning",
                    "database": {"path": str(db_path), "exists": True},
                    "eligible_count": 0,
                    "cleared_count": 0,
                    "remaining_affected_count": 0,
                    "latest_eligible_at": None,
                    "apply": {
                        "policy": policy,
                        "actor": actor,
                        "reason_sha256": hashlib.sha256(reason.encode()).hexdigest(),
                    },
                    "privacy": _query_preview_cleanup_privacy_payload(),
                    "warnings": ["retrieval_observations_missing"],
                }
            affected_before, eligible_before = _query_preview_cleanup_counts(connection, older_than=older_than)
            expected_remaining_affected_count = int(affected_before["count"]) - int(eligible_before["count"])
            disposable_apply_check = _run_query_preview_cleanup_disposable_apply_check(
                db_path=db_path,
                older_than=older_than,
                policy=policy,
                expected_eligible_count=int(eligible_before["count"]),
                expected_remaining_affected_count=expected_remaining_affected_count,
            )
            if disposable_apply_check["status"] != "passed":
                return {
                    "kind": kind,
                    "read_only": False,
                    "mutated": False,
                    "status": "error",
                    "database": {"path": str(db_path), "exists": True},
                    "affected_count": int(affected_before["count"]),
                    "eligible_count": int(eligible_before["count"]),
                    "cleared_count": 0,
                    "remaining_affected_count": int(affected_before["count"]),
                    "apply": {
                        "policy": policy,
                        "actor": actor,
                        "reason_sha256": hashlib.sha256(reason.encode()).hexdigest(),
                        "disposable_apply_check": disposable_apply_check,
                    },
                    "privacy": _query_preview_cleanup_privacy_payload(),
                    "warnings": ["query_preview_cleanup_disposable_apply_check_failed"],
                }
            eligible_ids, affected_after, rollback_manifest = _apply_query_preview_cleanup_to_connection(
                connection,
                older_than=older_than,
                db_path=db_path,
                policy=policy,
            )
            reason_sha256 = hashlib.sha256(reason.encode()).hexdigest()
            eligible_ids_sha256 = _query_preview_cleanup_ids_sha256(eligible_ids)
            audit_metadata = {
                "operation": "clear_stored_query_excerpts",
                "policy": policy,
                "actor": actor,
                "reason_sha256": reason_sha256,
                "older_than": older_than,
                "eligible_count": int(eligible_before["count"]),
                "cleared_count": len(eligible_ids),
                "affected_before_count": int(affected_before["count"]),
                "remaining_affected_count": int(affected_after["count"]),
                "eligible_ids_sha256": eligible_ids_sha256,
                "disposable_apply_check": disposable_apply_check,
                "rollback_manifest": rollback_manifest,
                "raw_query_preview_included": False,
                "sample_values_included": False,
            }
            audit_content_sha256 = hashlib.sha256(json.dumps(audit_metadata, sort_keys=True).encode()).hexdigest()
            cursor = connection.execute(
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
                    "dogfood",
                    "dogfood_query_preview_cleanup_apply",
                    audit_content_sha256,
                    None,
                    0.0,
                    0.0,
                    json.dumps([]),
                    json.dumps([]),
                    "review",
                    json.dumps(audit_metadata, sort_keys=True),
                ),
            )
            audit_trace_id = int(cursor.lastrowid)
        cleared_count = len(eligible_ids)
        remaining_affected_count = int(affected_after["count"])
        warnings: list[str] = []
        if remaining_affected_count:
            warnings.append("legacy_stored_query_excerpts_remain_after_cleanup_window")
        return {
            "kind": kind,
            "read_only": False,
            "mutated": cleared_count > 0,
            "status": "healthy" if not warnings else "warning",
            "database": {"path": str(db_path), "exists": True},
            "affected_count": int(affected_before["count"]),
            "eligible_count": int(eligible_before["count"]),
            "cleared_count": cleared_count,
            "remaining_affected_count": remaining_affected_count,
            "earliest_eligible_at": eligible_before["earliest"],
            "latest_eligible_at": eligible_before["latest"],
            "apply": {
                "policy": policy,
                "actor": actor,
                "reason_sha256": reason_sha256,
                "audit_trace_id": audit_trace_id,
                "eligible_ids_sha256": eligible_ids_sha256,
                "disposable_apply_check": disposable_apply_check,
                "rollback_manifest": rollback_manifest,
                "operation": "clear_stored_query_excerpts",
                "parameters": {"older_than": older_than},
            },
            "privacy": _query_preview_cleanup_privacy_payload(),
            "warnings": warnings,
            "suggested_next_steps": [
                "Run dogfood storage-health and query-preview-cleanup preview after apply to confirm only intended legacy rows remain.",
                "Keep cleanup output aggregate-only; never print stored query excerpt values.",
            ],
        }
    with _open_readonly_sqlite(db_path) as connection:
        if not _table_exists(connection, "retrieval_observations"):
            return {
                "kind": kind,
                "read_only": True,
                "mutated": False,
                "status": "warning",
                "database": {"path": str(db_path), "exists": True},
                "affected_count": 0,
                "eligible_count": 0,
                "latest_affected_at": None,
                "latest_eligible_at": None,
                "cleanup_preview": {
                    "mutation_required": False,
                    "recommended_operation": "clear_stored_query_excerpts",
                    "parameters": {"older_than": older_than},
                },
                "privacy": _query_preview_cleanup_privacy_payload(),
                "warnings": ["retrieval_observations_missing"],
            }
        affected, eligible = _query_preview_cleanup_counts(connection, older_than=older_than)
    affected_count = int(affected["count"])
    eligible_count = int(eligible["count"])
    warnings: list[str] = []
    if affected_count:
        warnings.append("legacy_stored_query_excerpts_present")
    if eligible_count:
        warnings.append("legacy_stored_query_excerpts_eligible_for_cleanup")
    return {
        "kind": kind,
        "read_only": True,
        "mutated": False,
        "status": "healthy" if not warnings else "warning",
        "database": {"path": str(db_path), "exists": True},
        "affected_count": affected_count,
        "eligible_count": eligible_count,
        "earliest_affected_at": affected["earliest"],
        "latest_affected_at": affected["latest"],
        "earliest_eligible_at": eligible["earliest"],
        "latest_eligible_at": eligible["latest"],
        "cleanup_preview": {
            "mutation_required": eligible_count > 0,
            "recommended_operation": "clear_stored_query_excerpts",
            "parameters": {"older_than": older_than},
            "apply_command_available": True,
            "apply_policy": QUERY_PREVIEW_CLEANUP_POLICY,
            "apply_guardrails": ["--apply", "--policy", "--actor", "--reason"],
        },
        "privacy": _query_preview_cleanup_privacy_payload(),
        "warnings": warnings,
        "suggested_next_steps": [
            "Review this read-only preview before running the explicit cleanup apply command.",
            "Keep cleanup output aggregate-only; never print stored query excerpt values.",
        ]
        if warnings
        else [],
    }



def _storage_health_hermes_payload(*, hermes_config: Path | None, db_path: Path) -> dict[str, Any]:
    if hermes_config is None:
        return {"config_checked": False, "config_exists": None, "agent_memory_hook_present": None}
    resolved_config = hermes_config.expanduser().resolve(strict=False)
    payload: dict[str, Any] = {
        "config_checked": True,
        "config_path": str(resolved_config),
        "config_exists": resolved_config.exists(),
        "agent_memory_hook_present": False,
        "configured_db_path_present": False,
    }
    if not resolved_config.exists():
        return payload
    text = resolved_config.read_text()
    payload["agent_memory_hook_present"] = "agent-memory" in text and "hermes-pre-llm-hook" in text
    payload["configured_db_path_present"] = str(db_path.expanduser().resolve(strict=False)) in text
    return payload


def _dogfood_storage_health_payload(args: argparse.Namespace) -> dict[str, Any]:
    db_path = args.db_path.expanduser().resolve(strict=False)
    if not db_path.exists():
        return {
            "kind": "dogfood_storage_health",
            "read_only": True,
            "mutated": False,
            "status": "error",
            "agent_memory_version": __version__,
            "database": {"path": str(db_path), "path_exists": False, "schema_user_version": None},
            "warnings": ["database_missing"],
        }

    with _open_readonly_sqlite(db_path) as connection:
        database = {"path": str(db_path), "path_exists": True, "schema_user_version": connection.execute("PRAGMA user_version").fetchone()[0]}
        table_names = (
            "retrieval_observations",
            "memory_activations",
            "experience_traces",
            "facts",
            "procedures",
            "episodes",
        )
        table_counts = {table_name: _readonly_table_count(connection, table_name) for table_name in table_names}
        latest_records = {table_name: _readonly_latest_created_at(connection, table_name) for table_name in table_names}
        invariants = {
            "stored_query_excerpt_empty": _stored_query_excerpt_invariant(connection),
            "query_hash_presence": _query_hash_presence_invariant(connection),
            "metadata_json_valid": _metadata_json_validity(connection),
            "activation_links": _activation_link_invariant(connection),
            "ordinary_trace_metadata_only": _ordinary_trace_metadata_only_invariant(connection),
            "remember_intent_safety": _remember_intent_safety_invariant(connection),
        }
        memory_counts = _readonly_memory_status_counts(connection)

    warnings: list[str] = []
    for invariant_name, invariant in invariants.items():
        if invariant.get("status") != "pass":
            warnings.append(f"{invariant_name}:{invariant.get('status')}")
    if table_counts["retrieval_observations"] == 0:
        warnings.append("no_retrieval_observations")
    if table_counts["experience_traces"] == 0:
        warnings.append("no_experience_traces")

    return {
        "kind": "dogfood_storage_health",
        "read_only": True,
        "mutated": False,
        "status": "healthy" if not warnings else "warning",
        "agent_memory_version": __version__,
        "database": database,
        "table_counts": table_counts,
        "latest_records": latest_records,
        "memory_counts": memory_counts,
        "invariants": invariants,
        "hermes": _storage_health_hermes_payload(hermes_config=args.hermes_config, db_path=db_path),
        "warnings": warnings,
        "suggested_next_steps": [
            "Fix storage-health warnings before enabling broader background consolidation automation.",
            "Keep this report read-only and raw-content-free; use focused diagnostics for deeper investigation.",
        ]
        if warnings
        else ["Storage health invariants are clean; continue G3c dogfooding before G4 apply-mode planning."],
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


def _node_type_from_ref(ref: str) -> str:
    prefix, _, _identifier = ref.partition(":")
    return prefix or "memory"


def _add_graph_node(
    nodes: dict[str, dict[str, Any]],
    *,
    node_id: str,
    node_type: str,
    label: str | None = None,
    status: str | None = None,
    scope: str | None = None,
    strength: float = 1.0,
) -> None:
    existing = nodes.get(node_id)
    if existing is None:
        nodes[node_id] = {
            "id": node_id,
            "type": node_type,
            "label": label or node_id,
            "status": status,
            "scope": scope,
            "strength": strength,
        }
        return
    existing["strength"] = max(float(existing.get("strength", 0.0)), strength)
    if existing.get("status") is None and status is not None:
        existing["status"] = status
    if existing.get("scope") is None and scope is not None:
        existing["scope"] = scope
    if existing.get("label") == node_id and label is not None:
        existing["label"] = label


def _memory_graph_snapshot(db_path: Path, *, limit: int, include_memory_labels: bool) -> dict[str, Any]:
    if limit < 1:
        raise ValueError("graph export limit must be >= 1")
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    seen_edges: set[tuple[str, str, str]] = set()
    skipped_empty_retrieval_edges = 0
    truncated = False

    def should_skip_ref(memory_ref: str) -> bool:
        return memory_ref in {"empty_retrieval", "memory:empty_retrieval"}

    def edge(from_id: str, to_id: str, edge_type: str, *, weight: float = 1.0) -> None:
        nonlocal truncated
        key = (from_id, to_id, edge_type)
        if key in seen_edges:
            return
        if len(edges) >= limit:
            truncated = True
            return
        seen_edges.add(key)
        edges.append({"from": from_id, "to": to_id, "type": edge_type, "weight": weight})

    with connect(db_path) as connection:
        for table_name, memory_type, label_sql in (
            ("facts", "fact", "subject_ref || ' ' || predicate || ' ' || object_ref_or_value"),
            ("procedures", "procedure", "name"),
            ("episodes", "episode", "title"),
        ):
            rows = connection.execute(
                f"""
                SELECT id, status, scope, reinforcement_count, retrieval_count, {label_sql} AS memory_label
                FROM {table_name}
                ORDER BY status = 'approved' DESC, reinforcement_count DESC, retrieval_count DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            for row in rows:
                ref = f"{memory_type}:{row['id']}"
                label = str(row["memory_label"]) if include_memory_labels else ref
                strength = 1.0 + float(row["reinforcement_count"] or 0.0) + float(row["retrieval_count"] or 0) * 0.25
                _add_graph_node(
                    nodes,
                    node_id=ref,
                    node_type=memory_type,
                    label=label,
                    status=str(row["status"]),
                    scope=str(row["scope"]),
                    strength=strength,
                )

        for row in connection.execute(
            """
            SELECT from_ref, relation_type, to_ref, weight
            FROM relations
            ORDER BY weight DESC, id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall():
            from_ref = str(row["from_ref"])
            to_ref = str(row["to_ref"])
            _add_graph_node(nodes, node_id=from_ref, node_type=_node_type_from_ref(from_ref))
            _add_graph_node(nodes, node_id=to_ref, node_type=_node_type_from_ref(to_ref))
            edge(from_ref, to_ref, str(row["relation_type"]), weight=float(row["weight"] or 1.0))

        for row in connection.execute(
            """
            SELECT id, event_kind, scope, salience, user_emphasis, related_memory_refs_json, related_observation_ids_json
            FROM experience_traces
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall():
            trace_ref = f"trace:{row['id']}"
            _add_graph_node(
                nodes,
                node_id=trace_ref,
                node_type="trace",
                label=f"trace:{row['id']} {row['event_kind']}",
                scope=row["scope"],
                strength=1.0 + float(row["salience"] or 0.0) + float(row["user_emphasis"] or 0.0),
            )
            try:
                related_memory_refs = json.loads(row["related_memory_refs_json"] or "[]")
            except json.JSONDecodeError:
                related_memory_refs = []
            for memory_ref in related_memory_refs:
                memory_ref = str(memory_ref)
                _add_graph_node(nodes, node_id=memory_ref, node_type=_node_type_from_ref(memory_ref))
                edge(trace_ref, memory_ref, "trace_supports")
            try:
                related_observation_ids = json.loads(row["related_observation_ids_json"] or "[]")
            except json.JSONDecodeError:
                related_observation_ids = []
            for observation_id in related_observation_ids:
                observation_ref = f"observation:{int(observation_id)}"
                _add_graph_node(nodes, node_id=observation_ref, node_type="observation")
                edge(trace_ref, observation_ref, "trace_observed")

        for row in connection.execute(
            """
            SELECT id, retrieved_memory_refs_json, top_memory_ref
            FROM retrieval_observations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall():
            observation_ref = f"observation:{row['id']}"
            _add_graph_node(nodes, node_id=observation_ref, node_type="observation", label=observation_ref)
            try:
                memory_refs = json.loads(row["retrieved_memory_refs_json"] or "[]")
            except json.JSONDecodeError:
                memory_refs = []
            for memory_ref in memory_refs:
                memory_ref = str(memory_ref)
                if should_skip_ref(memory_ref):
                    skipped_empty_retrieval_edges += 1
                    continue
                _add_graph_node(nodes, node_id=memory_ref, node_type=_node_type_from_ref(memory_ref))
                edge(observation_ref, memory_ref, "retrieved")
            top_ref = row["top_memory_ref"]
            if top_ref:
                top_ref = str(top_ref)
                if should_skip_ref(top_ref):
                    skipped_empty_retrieval_edges += 1
                    continue
                _add_graph_node(nodes, node_id=top_ref, node_type=_node_type_from_ref(top_ref))
                edge(observation_ref, top_ref, "top_retrieval", weight=1.5)

        for row in connection.execute(
            """
            SELECT id, activation_kind, memory_ref, observation_id, trace_id, strength
            FROM memory_activations
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall():
            activation_ref = f"activation:{row['id']}"
            _add_graph_node(
                nodes,
                node_id=activation_ref,
                node_type="activation",
                label=f"activation:{row['id']} {row['activation_kind']}",
                strength=float(row["strength"] or 0.0) + 0.5,
            )
            if row["memory_ref"]:
                memory_ref = str(row["memory_ref"])
                if should_skip_ref(memory_ref):
                    skipped_empty_retrieval_edges += 1
                else:
                    _add_graph_node(nodes, node_id=memory_ref, node_type=_node_type_from_ref(memory_ref))
                    edge(activation_ref, memory_ref, str(row["activation_kind"]), weight=float(row["strength"] or 1.0))
            if row["observation_id"] is not None:
                observation_ref = f"observation:{row['observation_id']}"
                _add_graph_node(nodes, node_id=observation_ref, node_type="observation")
                edge(activation_ref, observation_ref, "activation_observed")
            if row["trace_id"] is not None:
                trace_ref = f"trace:{row['trace_id']}"
                _add_graph_node(nodes, node_id=trace_ref, node_type="trace")
                edge(activation_ref, trace_ref, "activation_traced")

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "truncated": truncated,
        "skipped_empty_retrieval_edges": skipped_empty_retrieval_edges,
    }


def _render_memory_graph_html(graph_data: dict[str, Any], *, title: str) -> str:
    nodes = list(graph_data.get("nodes", []))
    edges = list(graph_data.get("edges", []))
    nodes_by_type = Counter(str(node.get("type", "memory")) for node in nodes)
    edges_by_type = Counter(str(edge.get("type", "related")) for edge in edges)
    degree_by_ref: Counter[str] = Counter()
    for edge in edges:
        from_ref = str(edge.get("from", ""))
        to_ref = str(edge.get("to", ""))
        if from_ref:
            degree_by_ref[from_ref] += 1
        if to_ref:
            degree_by_ref[to_ref] += 1
    by_id = {str(node.get("id")): node for node in nodes}
    memory_types = {"fact", "procedure", "episode", "memory"}
    dominant_hubs = [
        {
            "id": node_id,
            "type": str(by_id[node_id].get("type", "memory")),
            "label": str(by_id[node_id].get("label") or node_id),
            "degree": degree,
            "status": by_id[node_id].get("status"),
            "strength": by_id[node_id].get("strength", 0),
        }
        for node_id, degree in degree_by_ref.most_common(8)
        if node_id in by_id and str(by_id[node_id].get("type")) in memory_types
    ]
    isolated_memory_refs = sorted(
        str(node.get("id"))
        for node in nodes
        if str(node.get("type")) in memory_types and degree_by_ref[str(node.get("id"))] == 0
    )[:12]
    graph_summary = {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes_by_type": dict(sorted(nodes_by_type.items())),
        "edges_by_type": dict(sorted(edges_by_type.items())),
        "dominant_hubs": dominant_hubs,
        "isolated_memory_refs": isolated_memory_refs,
        "definitions": {
            "Fact": "검토/승인된 사실형 장기 기억: 승인되면 기본 retrieval에 들어갈 수 있는 안정적인 사실/상태/선호/환경 정보입니다.",
            "Procedure": "검토된 절차형 기억: 특정 상황에서 따라야 하는 how-to 단계 기억입니다. 현재 row가 없으면 그래프에 연결될 procedure 노드도 없습니다.",
            "Trace": "대화/진단/훅 이벤트의 lightweight 흔적입니다. 일반 trace는 raw transcript 없이 metadata/hash/ref 중심으로 저장됩니다.",
            "Observation": "retrieval이 일어났다는 secret-safe 관찰 기록입니다. raw query text가 아니라 hash/count/ref 중심입니다.",
            "Activation": "어떤 memory가 조회/강화/empty retrieval 등에서 활성화된 런타임 신호입니다.",
        },
    }
    graph_json = html.escape(json.dumps(graph_data, sort_keys=True), quote=False)
    summary_json = html.escape(json.dumps(graph_summary, sort_keys=True), quote=False)
    escaped_title = html.escape(title)
    template = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__</title>
<style>
:root { color-scheme: dark; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; min-height: 100vh; background: radial-gradient(circle at 52% 30%, #263a73 0, #0a1020 42%, #02040b 100%); color: #e8edff; overflow: hidden; }
body.low-power { background: #03050d; }
canvas { width: 100vw; height: 100vh; display: block; }
.panel { position: fixed; z-index: 2; background: rgba(6, 10, 24, 0.78); border: 1px solid rgba(125, 153, 255, 0.23); border-radius: 18px; padding: 14px 16px; backdrop-filter: blur(16px); box-shadow: 0 20px 70px rgba(0,0,0,.32); }
.low-power .panel { backdrop-filter: none; box-shadow: 0 8px 24px rgba(0,0,0,.22); background: rgba(6, 10, 24, 0.9); }
.header { left: 22px; top: 18px; max-width: 620px; }
h1 { margin: 0 0 8px; font-size: 22px; letter-spacing: .03em; }
.meta { color: #aebcff; font-size: 13px; line-height: 1.45; }
.controls { right: 22px; top: 18px; width: 340px; }
.controls h2, .inspector h2 { margin: 0 0 10px; font-size: 14px; color: #f2f5ff; }
.row { display: flex; flex-wrap: wrap; gap: 7px; margin: 8px 0; }
.chip { display: inline-flex; gap: 6px; align-items: center; padding: 5px 8px; border-radius: 999px; background: rgba(255,255,255,.065); color: #cdd7ff; font-size: 12px; user-select: none; }
.chip input { accent-color: #7cf7c8; }
.search { width: 100%; padding: 9px 10px; border-radius: 10px; border: 1px solid rgba(160,180,255,.25); background: rgba(3,6,16,.8); color: #eaf0ff; }
.stats { color: #aebcff; font-size: 12px; line-height: 1.55; margin-top: 8px; }
.inspector { left: 22px; bottom: 18px; width: min(640px, calc(100vw - 44px)); max-height: min(260px, 28vh); overflow: auto; }
.inspector p { margin: 6px 0; color: #c9d4ff; font-size: 12px; line-height: 1.42; }
.kv { display: grid; grid-template-columns: 110px 1fr; gap: 4px 10px; color: #c9d4ff; font-size: 12px; }
.warn { color: #ffd166; }
.dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 6px; }
button { border: 1px solid rgba(160,180,255,.24); background: rgba(124,247,200,.12); color: #e8edff; border-radius: 10px; padding: 7px 10px; cursor: pointer; }
button:hover, button.active { background: rgba(124,247,200,.24); border-color: rgba(124,247,200,.5); }
.quality button { font-size: 12px; padding: 6px 8px; }
</style>
</head>
<body>
<div class="panel header">
  <h1>agent-memory 기억 그래프</h1>
  <div class="meta"><strong>뇌형 기억 그래프</strong>. 읽기 전용 local visualization입니다. deterministic organic lobes, event-driven canvas redraw, viewport culling을 사용하고 browser force simulation은 실행하지 않습니다. raw source content, raw query text, trace summary는 HTML에 넣지 않습니다.</div>
</div>
<div class="panel controls">
  <h2>필터 & 실시간 렌더</h2>
  <input id="search" class="search" placeholder="ref 검색, 예: fact:1 또는 trace:196" />
  <div id="typeFilters" class="row"></div>
  <div class="row"><button id="resetView">화면 초기화</button><button id="fitHub">주요 기억 허브 보기</button></div>
  <div class="row quality" aria-label="render quality">
    <button id="qualityAuto" data-quality="auto" class="active">품질: 자동</button>
    <button id="qualityPerformance" data-quality="performance">성능 우선</button>
    <button id="qualitySharp" data-quality="sharp">선명도 우선</button>
  </div>
  <div id="stats" class="stats"></div>
</div>
<div class="panel inspector" id="inspector"></div>
<canvas id="graph"></canvas>
<script id="graph-data" type="application/json">__GRAPH_JSON__</script>
<script id="graph-data-summary" type="application/json">__SUMMARY_JSON__</script>
<script>
const data = JSON.parse(document.getElementById('graph-data').textContent);
const summary = JSON.parse(document.getElementById('graph-data-summary').textContent);
const canvas = document.getElementById('graph');
const ctx = canvas.getContext('2d', { alpha: false });
const palette = { fact:'#7cf7c8', procedure:'#ffd166', episode:'#9ad1ff', trace:'#f78cbe', observation:'#a78bfa', activation:'#ff8f70', memory:'#d7e0ff' };
const nodes = data.nodes.map((n, index) => ({...n, index, x:0, y:0, hidden:false, hover:false}));
const byId = new Map(nodes.map(n => [n.id, n]));
const edges = data.edges.map(e => ({...e, source: byId.get(e.from), target: byId.get(e.to)})).filter(e => e.source && e.target);
const degree = new Map();
for (const n of nodes) degree.set(n.id, 0);
for (const e of edges) { degree.set(e.source.id, (degree.get(e.source.id)||0)+1); degree.set(e.target.id, (degree.get(e.target.id)||0)+1); }
const memoryTypes = new Set(['fact','procedure','episode','memory']);
const enabledTypes = new Set(Object.keys(summary.nodes_by_type));
const CSS_CLASS_LOW_POWER = 'low-power';
const QUALITY = {
  auto: { label: '자동', dpr: Math.min(window.devicePixelRatio || 1, 1.5), lowPower: (window.devicePixelRatio || 1) > 1.5, glow: 5, selectedGlow: 12, labels: 'memory' },
  performance: { label: '성능 우선', dpr: 1, lowPower: true, glow: 0, selectedGlow: 6, labels: 'selected' },
  sharp: { label: '선명도 우선', dpr: Math.min(window.devicePixelRatio || 1, 2), lowPower: false, glow: 9, selectedGlow: 22, labels: 'memory' },
};
const state = { scale:1, ox:0, oy:0, selected:null, hovered:null, search:'', dirty:false, drawMs:0, visibleNodes:0, visibleEdges:0, quality:'auto', effectiveDpr:1, interacting:false };
function hash01(value) { let h=2166136261; for (let i=0;i<value.length;i++) { h ^= value.charCodeAt(i); h = Math.imul(h, 16777619); } return (h >>> 0) / 4294967295; }
function effectiveDpr() { return Math.max(1, Math.min(QUALITY[state.quality].dpr, 2)); }
function resize() { const scale = effectiveDpr(); state.effectiveDpr = scale; canvas.width = Math.floor(innerWidth * scale); canvas.height = Math.floor(innerHeight * scale); ctx.setTransform(scale,0,0,scale,0,0); document.body.classList.toggle(CSS_CLASS_LOW_POWER, QUALITY[state.quality].lowPower); }
function setQualityMode(mode) { if (!QUALITY[mode]) return; state.quality = mode; for (const button of document.querySelectorAll('[data-quality]')) button.classList.toggle('active', button.dataset.quality === mode); resize(); requestDraw(); }
function layoutBrain() {
  const cx = innerWidth * .52, cy = innerHeight * .52;
  const rx = Math.max(260, innerWidth * .31), ry = Math.max(170, innerHeight * .23);
  const hubs = nodes.filter(n => memoryTypes.has(n.type)).sort((a,b)=>(degree.get(b.id)||0)-(degree.get(a.id)||0));
  const hubById = new Map(hubs.map(h => [h.id, h]));
  hubs.forEach((h, i) => { const t = hubs.length <= 1 ? .5 : i / Math.max(1, hubs.length - 1); const a = Math.PI * (1.12 + .76 * t); h.x = cx + Math.cos(a) * rx * .42; h.y = cy + Math.sin(a) * ry * .35; if (i === 0) { h.x = cx; h.y = cy - ry*.08; } });
  const parentOf = new Map();
  for (const e of edges) {
    if (hubById.has(e.source.id) && !hubById.has(e.target.id)) parentOf.set(e.target.id, e.source);
    if (hubById.has(e.target.id) && !hubById.has(e.source.id)) parentOf.set(e.source.id, e.target);
  }
  const childrenByHub = new Map();
  for (const n of nodes) if (!memoryTypes.has(n.type)) { const p = parentOf.get(n.id); if (p) (childrenByHub.get(p.id) || childrenByHub.set(p.id, []).get(p.id)).push(n); }
  for (const [hubId, children] of childrenByHub) {
    const hub = byId.get(hubId); const base = hash01(hubId) * Math.PI * 2;
    children.forEach((n, i) => { const local = i / Math.max(1, children.length); const shell = n.type === 'trace' ? 1.05 : n.type === 'observation' ? 1.45 : 1.78; const a = base + local * Math.PI * 2.0 + hash01(n.id)*.35; const r = Math.min(rx, ry) * (.34 + shell*.16) + Math.sqrt(i)*1.8; n.x = hub.x + Math.cos(a) * r; n.y = hub.y + Math.sin(a) * r * .72; });
  }
  const orphans = nodes.filter(n => !memoryTypes.has(n.type) && !parentOf.has(n.id));
  orphans.forEach((n, i) => { const a = i * 2.399963229728653; const r = Math.min(rx, ry) * (.9 + .18*Math.sqrt(i)); n.x = cx + Math.cos(a)*r; n.y = cy + Math.sin(a)*r*.72 + ry*.30; });
  for (const n of nodes) { n.x = Math.max(40, Math.min(innerWidth-40, n.x)); n.y = Math.max(44, Math.min(innerHeight-44, n.y)); }
}
function screen(n) { return { x: n.x * state.scale + state.ox, y: n.y * state.scale + state.oy }; }
function visible(n) { if (!enabledTypes.has(n.type)) return false; if (state.search && !String(n.id+' '+(n.label||'')).toLowerCase().includes(state.search)) return false; const p = screen(n); return p.x > -80 && p.x < innerWidth+80 && p.y > -80 && p.y < innerHeight+80; }
function nodeRadius(n) { return Math.max(4, Math.min(18, 4 + Math.sqrt(Math.max(1, n.strength || degree.get(n.id) || 1))*2.3)); }
function drawScene() {
  const t0 = performance.now(); state.dirty = false; ctx.globalCompositeOperation='source-over'; ctx.fillStyle='#03050d'; ctx.fillRect(0,0,innerWidth,innerHeight);
  const quality = QUALITY[state.quality];
  if (!quality.lowPower) { const grad = ctx.createRadialGradient(innerWidth*.52, innerHeight*.38, 20, innerWidth*.52, innerHeight*.48, Math.max(innerWidth, innerHeight)*.7); grad.addColorStop(0,'#17295a'); grad.addColorStop(.52,'#081020'); grad.addColorStop(1,'#02040b'); ctx.fillStyle=grad; ctx.fillRect(0,0,innerWidth,innerHeight); }
  state.visibleEdges = 0; state.visibleNodes = 0; ctx.globalCompositeOperation='lighter';
  for (const e of edges) { if (!enabledTypes.has(e.source.type) || !enabledTypes.has(e.target.type)) continue; if (state.search && !visible(e.source) && !visible(e.target)) continue; const a=screen(e.source), b=screen(e.target); if ((a.x<-120&&b.x<-120)||(a.x>innerWidth+120&&b.x>innerWidth+120)||(a.y<-120&&b.y<-120)||(a.y>innerHeight+120&&b.y>innerHeight+120)) continue; const color = palette[e.source.type] || '#8994c7'; ctx.strokeStyle = color + (e.type === 'top_retrieval' ? '88' : '42'); ctx.lineWidth = Math.max(.45, Math.min(2.2, (e.weight || 1) * state.scale)); ctx.beginPath(); const mx=(a.x+b.x)/2, my=(a.y+b.y)/2 - 24*state.scale; ctx.moveTo(a.x,a.y); ctx.quadraticCurveTo(mx,my,b.x,b.y); ctx.stroke(); state.visibleEdges++; }
  const showLabels = !state.interacting && (quality.labels === 'memory' ? state.scale > .95 || nodes.length <= 260 : Boolean(state.selected || state.hovered));
  for (const n of nodes) { if (!visible(n)) continue; const p=screen(n); const r=nodeRadius(n)*Math.sqrt(state.scale); const c=palette[n.type] || palette.memory; ctx.fillStyle=c; ctx.shadowColor=c; ctx.shadowBlur = n === state.hovered || n === state.selected ? quality.selectedGlow : quality.glow; ctx.beginPath(); ctx.arc(p.x,p.y,r,0,Math.PI*2); ctx.fill(); ctx.shadowBlur=0; if (memoryTypes.has(n.type)) { ctx.strokeStyle='#ffffffaa'; ctx.lineWidth=1.2; ctx.stroke(); } if (showLabels && (quality.labels === 'memory' ? memoryTypes.has(n.type) || n === state.hovered || n === state.selected : n === state.hovered || n === state.selected)) { ctx.fillStyle='#eef3ff'; ctx.font='11px ui-sans-serif, system-ui'; ctx.fillText(n.label || n.id, p.x+r+5, p.y+4); } state.visibleNodes++; }
  ctx.globalCompositeOperation='source-over'; state.drawMs = Math.round((performance.now()-t0)*10)/10; renderStats();
}
function requestDraw() { if (state.dirty) return; state.dirty = true; requestAnimationFrame(drawScene); }
function renderStats() { const hubs = summary.dominant_hubs || []; const top = hubs[0]; document.getElementById('stats').innerHTML = `${state.visibleNodes}/${nodes.length} 표시 노드 · ${state.visibleEdges}/${edges.length} 표시 엣지<br>렌더 ${state.drawMs}ms · event-driven canvas · DPR ${state.effectiveDpr}<br>${top ? '주요 기억 허브: '+top.id+' 연결수 '+top.degree : '주요 기억 허브 없음'}<br>${(summary.isolated_memory_refs||[]).length ? '<span class="warn">고립된 기억 ref: '+summary.isolated_memory_refs.join(', ')+'</span>' : ''}`; }
function renderInspector(n) { const top = (summary.dominant_hubs||[])[0]; document.getElementById('inspector').innerHTML = `<h2>이 그래프를 읽는 법</h2><p><strong>Fact = 검토/승인된 사실형 장기 기억</strong>. Procedure = 검토된 절차형 기억. Trace = lightweight 이벤트 흔적. Observation = secret-safe retrieval 관찰 기록. Activation = retrieval/reinforcement 신호.</p><p>${top ? `현재 구조: <strong>${top.id}</strong>가 주요 기억 허브입니다. 많은 trace/observation이 이 ref를 가리킨다는 뜻이고, 현재 live DB에서 이 fact가 대부분의 retrieval/support 신호를 받고 있다는 의미입니다. deprecated fact나 아직 생성되지 않은 procedure는 고립되어 보일 수 있습니다.` : '현재 구조: 아직 지배적인 기억 허브가 없습니다.'}</p>${n ? `<div class="kv"><div>선택</div><div>${n.id}</div><div>유형</div><div>${n.type}</div><div>상태</div><div>${n.status ?? ''}</div><div>연결수</div><div>${degree.get(n.id)||0}</div><div>강도</div><div>${n.strength ?? ''}</div></div>` : '<p>노드를 클릭하면 ref-only metadata를 볼 수 있습니다. raw source/query/trace text는 이 artifact에 포함하지 않습니다.</p>'}<p class="warn">Procedure count: ${summary.nodes_by_type.procedure || 0}. 0이면 export된 그래프에 procedure row가 없으므로 연결될 procedure node도 없습니다.</p>`; }
function installControls() { const wrap=document.getElementById('typeFilters'); for (const [type,count] of Object.entries(summary.nodes_by_type)) { const label=document.createElement('label'); label.className='chip'; label.innerHTML=`<input type="checkbox" checked data-type="${type}"><span class="dot" style="background:${palette[type]||palette.memory}"></span>${type} ${count}`; wrap.appendChild(label); } wrap.addEventListener('change', e => { const t=e.target.dataset.type; if (!t) return; e.target.checked ? enabledTypes.add(t) : enabledTypes.delete(t); requestDraw(); }); document.getElementById('search').addEventListener('input', e => { state.search = e.target.value.trim().toLowerCase(); requestDraw(); }); document.getElementById('resetView').onclick = () => { state.scale=1; state.ox=0; state.oy=0; requestDraw(); }; document.getElementById('fitHub').onclick = () => { const h=(summary.dominant_hubs||[])[0]; const n=h && byId.get(h.id); if (!n) return; state.scale=1.35; state.ox=innerWidth*.5-n.x*state.scale; state.oy=innerHeight*.45-n.y*state.scale; state.selected=n; renderInspector(n); requestDraw(); }; for (const button of document.querySelectorAll('[data-quality]')) button.addEventListener('click', () => setQualityMode(button.dataset.quality)); }
function pick(x,y) { let best=null, bestD=Infinity; for (const n of nodes) { if (!enabledTypes.has(n.type)) continue; const p=screen(n); const dx=p.x-x, dy=p.y-y; const d=dx*dx+dy*dy; const r=nodeRadius(n)+10; if (d<r*r && d<bestD) { best=n; bestD=d; } } return best; }
let dragging=false, lastX=0, lastY=0, interactionTimer=null;
function markInteracting() { state.interacting = true; if (interactionTimer) clearTimeout(interactionTimer); interactionTimer = setTimeout(() => { state.interacting = false; requestDraw(); }, 120); }
canvas.addEventListener('mousemove', e => { if (dragging) { markInteracting(); state.ox += e.clientX-lastX; state.oy += e.clientY-lastY; lastX=e.clientX; lastY=e.clientY; requestDraw(); return; } const h=pick(e.clientX,e.clientY); if (h !== state.hovered) { state.hovered=h; requestDraw(); } });
canvas.addEventListener('mousedown', e => { dragging=true; markInteracting(); lastX=e.clientX; lastY=e.clientY; });
window.addEventListener('mouseup', () => { dragging=false; });
canvas.addEventListener('click', e => { const n=pick(e.clientX,e.clientY); state.selected=n; renderInspector(n); requestDraw(); });
canvas.addEventListener('wheel', e => { e.preventDefault(); markInteracting(); const before={x:(e.clientX-state.ox)/state.scale, y:(e.clientY-state.oy)/state.scale}; const factor = Math.exp(-e.deltaY * .001); state.scale = Math.max(.35, Math.min(4, state.scale * factor)); state.ox = e.clientX - before.x * state.scale; state.oy = e.clientY - before.y * state.scale; requestDraw(); }, { passive:false });
function boot() { resize(); layoutBrain(); installControls(); renderInspector(null); requestDraw(); }
window.addEventListener('resize', () => { resize(); layoutBrain(); requestDraw(); });
boot();
</script>
</body>
</html>
"""
    return (
        template.replace("__TITLE__", escaped_title)
        .replace("__GRAPH_JSON__", graph_json)
        .replace("__SUMMARY_JSON__", summary_json)
    )


def _export_memory_graph_html(
    db_path: Path,
    *,
    output_path: Path,
    limit: int,
    include_memory_labels: bool,
) -> dict[str, Any]:
    graph_data = _memory_graph_snapshot(db_path, limit=limit, include_memory_labels=include_memory_labels)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    html_text = _render_memory_graph_html(graph_data, title="agent-memory neural graph")
    output_path.write_text(html_text)
    return {
        "kind": "memory_graph_html_export",
        "read_only": True,
        "mutated": False,
        "default_retrieval_unchanged": True,
        "db_path": str(db_path),
        "output_path": str(output_path),
        "node_count": len(graph_data["nodes"]),
        "edge_count": len(graph_data["edges"]),
        "truncated": graph_data["truncated"],
        "skipped_empty_retrieval_edges": graph_data.get("skipped_empty_retrieval_edges", 0),
        "privacy": {
            "raw_source_content_included": False,
            "raw_query_text_included": False,
            "raw_trace_summary_included": False,
            "memory_labels_included": include_memory_labels,
        },
        "performance": {
            "layout_mode": "interactive_brain_static",
            "continuous_physics_enabled": False,
            "rendering": "dirty_rect_event_driven_canvas",
            "device_pixel_ratio_cap": 1.5,
            "sharp_device_pixel_ratio_cap": 2,
            "quality_modes": ["auto", "performance", "sharp"],
        },
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

    backup_parser = subparsers.add_parser("backup", help="Export, inspect, and restore local agent-memory SQLite backups.")
    backup_subparsers = backup_parser.add_subparsers(dest="backup_action", required=True)
    backup_export_parser = backup_subparsers.add_parser("export")
    backup_export_parser.add_argument("db_path", type=Path)
    backup_export_parser.add_argument("output_path", type=Path)
    backup_inspect_parser = backup_subparsers.add_parser("inspect")
    backup_inspect_parser.add_argument("bundle_path", type=Path)
    backup_restore_parser = backup_subparsers.add_parser("restore")
    backup_restore_parser.add_argument("bundle_path", type=Path)
    backup_restore_parser.add_argument("output_db_path", type=Path)
    backup_restore_parser.add_argument("--overwrite", action="store_true")

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
    dogfood_storage_health_parser = dogfood_subparsers.add_parser(
        "storage-health",
        help="Build a read-only raw-content-safe storage health report for dogfood DB invariants before G4 automation.",
    )
    dogfood_storage_health_parser.add_argument("db_path", type=Path)
    dogfood_storage_health_parser.add_argument("--hermes-config", type=Path)
    dogfood_query_preview_cleanup_parser = dogfood_subparsers.add_parser(
        "query-preview-cleanup",
        help="Preview read-only aggregate cleanup for legacy stored query excerpts without printing raw values.",
    )
    dogfood_query_preview_cleanup_parser.add_argument("db_path", type=Path)
    dogfood_query_preview_cleanup_parser.add_argument("--older-than", default="9999-12-31T23:59:59")
    dogfood_query_preview_cleanup_parser.add_argument("--apply", action="store_true")
    dogfood_query_preview_cleanup_parser.add_argument("--policy")
    dogfood_query_preview_cleanup_parser.add_argument("--actor")
    dogfood_query_preview_cleanup_parser.add_argument("--reason")
    dogfood_query_preview_cleanup_restore_parser = dogfood_subparsers.add_parser(
        "query-preview-cleanup-restore",
        help="Dry-run validation for private query-preview cleanup rollback artifacts without printing raw values.",
    )
    dogfood_query_preview_cleanup_restore_parser.add_argument("db_path", type=Path)
    dogfood_query_preview_cleanup_restore_parser.add_argument("rollback_artifact_path", type=Path)
    dogfood_query_preview_cleanup_restore_parser.add_argument("--dry-run", action="store_true")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--apply", action="store_true")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--policy", dest="restore_policy")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--actor")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--reason")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--approval-token")
    dogfood_query_preview_cleanup_restore_parser.add_argument("--approval-token-expected-sha256")
    dogfood_ordinary_trace_metadata_cleanup_parser = dogfood_subparsers.add_parser(
        "ordinary-trace-metadata-cleanup",
        help="Preview/apply raw-content-safe normalization for legacy ordinary turn trace metadata defaults.",
    )
    dogfood_ordinary_trace_metadata_cleanup_parser.add_argument("db_path", type=Path)
    dogfood_ordinary_trace_metadata_cleanup_parser.add_argument("--apply", action="store_true")
    dogfood_ordinary_trace_metadata_cleanup_parser.add_argument("--actor")
    dogfood_ordinary_trace_metadata_cleanup_parser.add_argument("--reason")
    dogfood_trace_quality_parser = dogfood_subparsers.add_parser(
        "trace-quality",
        help="Build a read-only aggregate trace quality report before G4 automation planning.",
    )
    dogfood_trace_quality_parser.add_argument("db_path", type=Path)
    dogfood_trace_quality_parser.add_argument("--since-hours", type=int, default=24)
    dogfood_trace_quality_parser.add_argument("--epoch-start", help="Optional ISO-8601 cutoff for fresh-epoch trace quality measurement.")
    dogfood_trace_quality_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_trace_quality_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_trace_cluster_preview_parser = dogfood_subparsers.add_parser(
        "trace-cluster-preview",
        help="Build a read-only ref-safe preview of trace clusters for the G5 reviewed-candidate runway.",
    )
    dogfood_trace_cluster_preview_parser.add_argument("db_path", type=Path)
    dogfood_trace_cluster_preview_parser.add_argument("--output", type=Path)
    dogfood_trace_cluster_preview_parser.add_argument("--limit", type=int, default=200)
    dogfood_trace_cluster_preview_parser.add_argument("--top", type=int, default=20)
    dogfood_trace_cluster_preview_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_trace_candidate_generate_parser = dogfood_subparsers.add_parser(
        "trace-candidate-generate",
        help="Generate ref-safe fact/procedure/preference candidate skeletons from graph trace clusters without mutation.",
    )
    dogfood_trace_candidate_generate_parser.add_argument("db_path", type=Path)
    dogfood_trace_candidate_generate_parser.add_argument("--output", type=Path)
    dogfood_trace_candidate_generate_parser.add_argument("--limit", type=int, default=200)
    dogfood_trace_candidate_generate_parser.add_argument("--top", type=int, default=20)
    dogfood_trace_candidate_generate_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_reinforcement_refinement_preview_parser = dogfood_subparsers.add_parser(
        "reinforcement-refinement-preview",
        help="Build a read-only G5d preview of repeated activation -> reinforcement refinement candidates.",
    )
    dogfood_reinforcement_refinement_preview_parser.add_argument("db_path", type=Path)
    dogfood_reinforcement_refinement_preview_parser.add_argument("--output", type=Path)
    dogfood_reinforcement_refinement_preview_parser.add_argument("--limit", type=int, default=200)
    dogfood_reinforcement_refinement_preview_parser.add_argument("--top", type=int, default=20)
    dogfood_reinforcement_refinement_preview_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_decay_collapse_preview_parser = dogfood_subparsers.add_parser(
        "decay-collapse-preview",
        help="Build a read-only G5e preview of stale weak-evidence decay/collapse candidates.",
    )
    dogfood_decay_collapse_preview_parser.add_argument("db_path", type=Path)
    dogfood_decay_collapse_preview_parser.add_argument("--output", type=Path)
    dogfood_decay_collapse_preview_parser.add_argument("--limit", type=int, default=200)
    dogfood_decay_collapse_preview_parser.add_argument("--top", type=int, default=20)
    dogfood_decay_collapse_preview_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_decay_collapse_preview_parser.add_argument("--min-decay-score", type=float, default=0.5)
    dogfood_supersession_preview_parser = dogfood_subparsers.add_parser(
        "supersession-preview",
        help="Build a read-only G5f preview of conflict -> supersession/replacement candidates.",
    )
    dogfood_supersession_preview_parser.add_argument("db_path", type=Path)
    dogfood_supersession_preview_parser.add_argument("--output", type=Path)
    dogfood_supersession_preview_parser.add_argument("--limit", type=int, default=200)
    dogfood_supersession_preview_parser.add_argument("--top", type=int, default=20)
    dogfood_lifecycle_candidate_persist_parser = dogfood_subparsers.add_parser(
        "lifecycle-candidate-persist",
        help="Persist reinforcement/decay/supersession lifecycle candidates for explicit review without apply.",
    )
    dogfood_lifecycle_candidate_persist_parser.add_argument("db_path", type=Path)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--candidate-kind", required=True, choices=["reinforcement", "decay", "supersession"])
    dogfood_lifecycle_candidate_persist_parser.add_argument("--actor", required=True)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--reason", required=True)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--output", type=Path)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--limit", type=int, default=200)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--top", type=int, default=20)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_lifecycle_candidate_persist_parser.add_argument("--min-decay-score", type=float, default=0.5)
    dogfood_lifecycle_candidate_list_parser = dogfood_subparsers.add_parser(
        "lifecycle-candidate-list",
        help="List persisted lifecycle candidates without raw candidate/review payloads.",
    )
    dogfood_lifecycle_candidate_list_parser.add_argument("db_path", type=Path)
    dogfood_lifecycle_candidate_list_parser.add_argument("--candidate-kind", choices=["reinforcement", "decay", "supersession"])
    dogfood_lifecycle_candidate_list_parser.add_argument("--status", choices=["pending", "approved", "rejected", "promoted"])
    dogfood_lifecycle_candidate_list_parser.add_argument("--limit", type=int, default=50)
    dogfood_lifecycle_candidate_update_parser = dogfood_subparsers.add_parser(
        "lifecycle-candidate-update",
        help="Approve or reject a persisted lifecycle candidate; does not apply mutation.",
    )
    dogfood_lifecycle_candidate_update_parser.add_argument("db_path", type=Path)
    dogfood_lifecycle_candidate_update_parser.add_argument("candidate_id")
    dogfood_lifecycle_candidate_update_parser.add_argument("--status", required=True, choices=["approved", "rejected"])
    dogfood_lifecycle_candidate_update_parser.add_argument("--actor", required=True)
    dogfood_lifecycle_candidate_update_parser.add_argument("--reason", required=True)
    dogfood_lifecycle_candidate_update_parser.add_argument("--approval-phrase", required=True)
    dogfood_lifecycle_candidate_update_parser.add_argument(
        "--collapse-proof-artifact-json",
        help="Optional JSON object or path persisted into reviewed_json for decay collapse proof replay.",
    )
    dogfood_lifecycle_candidate_apply_parser = dogfood_subparsers.add_parser(
        "lifecycle-candidate-apply",
        help="Apply approved supersession lifecycle candidates through a narrow guarded backup/audit corridor.",
    )
    dogfood_lifecycle_candidate_apply_parser.add_argument("db_path", type=Path)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--candidate-id", action="append")
    dogfood_lifecycle_candidate_apply_parser.add_argument("--policy", required=True)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--approval-phrase", required=True)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--actor", required=True)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--reason", required=True)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--backup-path", type=Path)
    dogfood_lifecycle_candidate_apply_parser.add_argument("--output", type=Path)
    dogfood_retrieval_ranking_gate_parser = dogfood_subparsers.add_parser(
        "retrieval-ranking-gate",
        help="Run retrieval eval as a read-only gate before any opt-in ranking policy change.",
    )
    dogfood_retrieval_ranking_gate_parser.add_argument("db_path", type=Path)
    dogfood_retrieval_ranking_gate_parser.add_argument("--fixtures", type=Path, required=True)
    dogfood_retrieval_ranking_gate_parser.add_argument("--baseline-mode")
    dogfood_retrieval_ranking_gate_parser.add_argument("--max-baseline-regressions", type=int, default=0)
    dogfood_retrieval_ranking_gate_parser.add_argument("--output", type=Path)
    dogfood_rollback_confidence_parser = dogfood_subparsers.add_parser(
        "rollback-confidence",
        help="Inspect backup/checksum rollback confidence for reviewed lifecycle applications without mutation.",
    )
    dogfood_rollback_confidence_parser.add_argument("db_path", type=Path)
    dogfood_rollback_confidence_parser.add_argument("--limit", type=int, default=50)
    dogfood_rollback_confidence_parser.add_argument("--output", type=Path)
    dogfood_rollback_replay_validate_parser = dogfood_subparsers.add_parser(
        "rollback-replay-validate",
        help="Replay lifecycle application backups into temporary SQLite restores and verify rollback readiness without mutation.",
    )
    dogfood_rollback_replay_validate_parser.add_argument("db_path", type=Path)
    dogfood_rollback_replay_validate_parser.add_argument("--limit", type=int, default=50)
    dogfood_rollback_replay_validate_parser.add_argument("--output", type=Path)
    dogfood_retrieval_ranking_experiment_parser = dogfood_subparsers.add_parser(
        "retrieval-ranking-experiment",
        help="Run the retrieval ranking gate and, only if it passes, produce opt-in ranker previews from fixtures.",
    )
    dogfood_retrieval_ranking_experiment_parser.add_argument("db_path", type=Path)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--fixtures", type=Path, required=True)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--baseline-mode")
    dogfood_retrieval_ranking_experiment_parser.add_argument("--max-baseline-regressions", type=int, default=0)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--max-tasks", type=int, default=5)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--limit", type=int, default=5)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--reinforcement-weight", type=float, default=1.5)
    dogfood_retrieval_ranking_experiment_parser.add_argument("--reinforcement-cap", type=float, default=1.0)
    dogfood_retrieval_ranking_experiment_parser.add_argument(
        "--ranking-policy",
        choices=list(RANKING_POLICIES),
        default=RANKING_DEFAULT_POLICY,
        help="Candidate ranking policy to compare while keeping the conservative legacy default returned.",
    )
    dogfood_retrieval_ranking_experiment_parser.add_argument(
        "--shadow-compare",
        action="store_true",
        help="Run candidate ranking only as a shadow comparison; do not mutate defaults or returned order.",
    )
    dogfood_retrieval_ranking_experiment_parser.add_argument("--output", type=Path)
    dogfood_retrieval_ranking_migrate_parser = dogfood_subparsers.add_parser(
        "retrieval-ranking-migrate-default",
        help="Explicitly migrate retrieval ranking default config after fixture/shadow/rollback gates pass.",
    )
    dogfood_retrieval_ranking_migrate_parser.add_argument("db_path", type=Path)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--fixtures", type=Path, required=True)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--policy", required=True, choices=["conservative_legacy", "graph_reinforced_v1"])
    dogfood_retrieval_ranking_migrate_parser.add_argument("--config-path", type=Path, required=True)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--actor", required=True)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--reason", required=True)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--approval-phrase", required=True)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--baseline-mode")
    dogfood_retrieval_ranking_migrate_parser.add_argument("--max-baseline-regressions", type=int, default=0)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--max-tasks", type=int, default=5)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--limit", type=int, default=5)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--reinforcement-weight", type=float, default=1.5)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--reinforcement-cap", type=float, default=1.0)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--audit-output", type=Path)
    dogfood_retrieval_ranking_migrate_parser.add_argument("--output", type=Path)
    dogfood_decay_collapse_decision_parser = dogfood_subparsers.add_parser(
        "decay-collapse-decision",
        help="Summarize the safe decision boundary after decay/collapse preview: deprecate only; collapse/delete blocked.",
    )
    dogfood_decay_collapse_decision_parser.add_argument("db_path", type=Path)
    dogfood_decay_collapse_decision_parser.add_argument("--limit", type=int, default=200)
    dogfood_decay_collapse_decision_parser.add_argument("--top", type=int, default=20)
    dogfood_decay_collapse_decision_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_decay_collapse_decision_parser.add_argument("--min-decay-score", type=float, default=0.5)
    dogfood_decay_collapse_decision_parser.add_argument("--fixtures", type=Path)
    dogfood_decay_collapse_decision_parser.add_argument("--baseline-mode")
    dogfood_decay_collapse_decision_parser.add_argument("--max-baseline-regressions", type=int, default=0)
    dogfood_decay_collapse_decision_parser.add_argument("--output", type=Path)
    dogfood_trace_candidate_persist_parser = dogfood_subparsers.add_parser(
        "trace-candidate-persist",
        help="Persist G5 trace-cluster candidates for explicit human review without promoting memories.",
    )
    dogfood_trace_candidate_persist_parser.add_argument("db_path", type=Path)
    dogfood_trace_candidate_persist_parser.add_argument("--actor", required=True)
    dogfood_trace_candidate_persist_parser.add_argument("--reason", required=True)
    dogfood_trace_candidate_persist_parser.add_argument("--output", type=Path)
    dogfood_trace_candidate_persist_parser.add_argument("--limit", type=int, default=200)
    dogfood_trace_candidate_persist_parser.add_argument("--top", type=int, default=20)
    dogfood_trace_candidate_persist_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_trace_candidate_list_parser = dogfood_subparsers.add_parser(
        "trace-candidate-list", help="List persisted G5 trace candidates without raw cluster/review payloads."
    )
    dogfood_trace_candidate_list_parser.add_argument("db_path", type=Path)
    dogfood_trace_candidate_list_parser.add_argument("--status", choices=["pending", "approved", "rejected", "promoted"])
    dogfood_trace_candidate_list_parser.add_argument("--limit", type=int, default=50)
    dogfood_trace_candidate_update_parser = dogfood_subparsers.add_parser(
        "trace-candidate-update", help="Approve or reject a persisted G5 trace candidate; does not apply promotion."
    )
    dogfood_trace_candidate_update_parser.add_argument("db_path", type=Path)
    dogfood_trace_candidate_update_parser.add_argument("candidate_id")
    dogfood_trace_candidate_update_parser.add_argument("--status", required=True, choices=["approved", "rejected"])
    dogfood_trace_candidate_update_parser.add_argument("--actor", required=True)
    dogfood_trace_candidate_update_parser.add_argument("--reason", required=True)
    dogfood_trace_candidate_update_parser.add_argument("--approval-phrase", required=True)
    dogfood_trace_candidate_update_parser.add_argument("--promotion-type", choices=["fact", "preference", "procedure", "episode"])
    dogfood_trace_candidate_update_parser.add_argument("--subject")
    dogfood_trace_candidate_update_parser.add_argument("--predicate")
    dogfood_trace_candidate_update_parser.add_argument("--object")
    dogfood_trace_candidate_update_parser.add_argument("--name")
    dogfood_trace_candidate_update_parser.add_argument("--trigger-context")
    dogfood_trace_candidate_update_parser.add_argument("--precondition", action="append")
    dogfood_trace_candidate_update_parser.add_argument("--step", action="append")
    dogfood_trace_candidate_update_parser.add_argument("--success-rate", type=float, default=0.0)
    dogfood_trace_candidate_update_parser.add_argument("--title")
    dogfood_trace_candidate_update_parser.add_argument("--summary")
    dogfood_trace_candidate_update_parser.add_argument("--tag", action="append")
    dogfood_trace_candidate_update_parser.add_argument("--importance-score", type=float, default=0.0)
    dogfood_trace_candidate_update_parser.add_argument("--scope", default="global")
    dogfood_trace_candidate_update_parser.add_argument("--confidence", type=float, default=0.7)
    dogfood_trace_candidate_apply_parser = dogfood_subparsers.add_parser(
        "trace-candidate-apply", help="Promote approved reviewed G5 trace candidates with explicit policy and backup."
    )
    dogfood_trace_candidate_apply_parser.add_argument("db_path", type=Path)
    dogfood_trace_candidate_apply_parser.add_argument("--candidate-id", action="append")
    dogfood_trace_candidate_apply_parser.add_argument("--policy", required=True)
    dogfood_trace_candidate_apply_parser.add_argument("--approval-phrase", required=True)
    dogfood_trace_candidate_apply_parser.add_argument("--actor", required=True)
    dogfood_trace_candidate_apply_parser.add_argument("--reason", required=True)
    dogfood_trace_candidate_apply_parser.add_argument("--backup-path", type=Path)
    dogfood_trace_candidate_apply_parser.add_argument("--output", type=Path)
    dogfood_fresh_epoch_parser = dogfood_subparsers.add_parser(
        "fresh-epoch",
        help="Build a read-only epoch-filtered readiness report so new telemetry can be judged apart from historical rows.",
    )
    dogfood_fresh_epoch_parser.add_argument("db_path", type=Path)
    dogfood_fresh_epoch_parser.add_argument("--epoch-start", required=True, help="ISO timestamp for the fresh telemetry epoch.")
    dogfood_fresh_epoch_parser.add_argument("--output", type=Path)
    dogfood_fresh_epoch_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_fresh_epoch_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_fresh_epoch_parser.add_argument("--high-empty-threshold", type=float, default=0.5)

    dogfood_fresh_epoch_compare_parser = dogfood_subparsers.add_parser(
        "fresh-epoch-compare",
        help="Compare saved fresh-epoch JSON reports with read-only stability gates before historical telemetry decisions.",
    )
    dogfood_fresh_epoch_compare_parser.add_argument(
        "--report",
        type=Path,
        action="append",
        required=True,
        dest="reports",
        help="Path to a JSON report produced by dogfood fresh-epoch; repeat for multiple runs.",
    )
    dogfood_fresh_epoch_compare_parser.add_argument("--output", type=Path)
    dogfood_fresh_epoch_compare_parser.add_argument("--min-report-count", type=int, default=2)

    dogfood_fresh_epoch_runway_parser = dogfood_subparsers.add_parser(
        "fresh-epoch-runway",
        help="Run the read-only fresh-epoch -> comparison -> telemetry-reconciliation artifact workflow.",
    )
    dogfood_fresh_epoch_runway_parser.add_argument("db_path", type=Path)
    dogfood_fresh_epoch_runway_parser.add_argument("--epoch-start", required=True, help="ISO timestamp for the fresh telemetry epoch.")
    dogfood_fresh_epoch_runway_parser.add_argument("--report-dir", type=Path, required=True)
    dogfood_fresh_epoch_runway_parser.add_argument(
        "--baseline-report",
        type=Path,
        action="append",
        default=[],
        dest="baseline_reports",
        help="Existing dogfood fresh-epoch report to include in the comparison; repeat for multiple saved runs.",
    )
    dogfood_fresh_epoch_runway_parser.add_argument("--output", type=Path)
    dogfood_fresh_epoch_runway_parser.add_argument("--artifact-prefix")
    dogfood_fresh_epoch_runway_parser.add_argument("--min-report-count", type=int, default=2)
    dogfood_fresh_epoch_runway_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_fresh_epoch_runway_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_fresh_epoch_runway_parser.add_argument("--high-empty-threshold", type=float, default=0.5)
    dogfood_telemetry_reset_preview_parser = dogfood_subparsers.add_parser(
        "telemetry-reset-preview",
        help="Preview aggregate telemetry-only reset candidates without deleting or mutating rows.",
    )
    dogfood_telemetry_reset_preview_parser.add_argument("db_path", type=Path)
    dogfood_telemetry_reset_preview_parser.add_argument("--epoch-start", help="Optional ISO timestamp; preview deleting telemetry older than this while retaining fresh epoch rows.")
    dogfood_telemetry_reset_preview_parser.add_argument("--output", type=Path)
    dogfood_telemetry_reset_apply_parser = dogfood_subparsers.add_parser(
        "telemetry-reset-apply",
        help="Apply a guarded telemetry-only reset with backup, explicit phrase, actor, reason, and post-reset verification.",
    )
    dogfood_telemetry_reset_apply_parser.add_argument("db_path", type=Path)
    dogfood_telemetry_reset_apply_parser.add_argument("--epoch-start", required=True)
    dogfood_telemetry_reset_apply_parser.add_argument("--policy", required=True)
    dogfood_telemetry_reset_apply_parser.add_argument("--approval-phrase", required=True)
    dogfood_telemetry_reset_apply_parser.add_argument("--actor", required=True)
    dogfood_telemetry_reset_apply_parser.add_argument("--reason", required=True)
    dogfood_telemetry_reset_apply_parser.add_argument("--backup-path", type=Path)
    dogfood_telemetry_reset_apply_parser.add_argument("--output", type=Path)
    dogfood_telemetry_reconciliation_parser = dogfood_subparsers.add_parser(
        "telemetry-reconciliation",
        help="Build a read-only historical telemetry reconciliation report and telemetry-only apply corridor summary.",
    )
    dogfood_telemetry_reconciliation_parser.add_argument("db_path", type=Path)
    dogfood_telemetry_reconciliation_parser.add_argument("--epoch-start", required=True)
    dogfood_telemetry_reconciliation_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_telemetry_reconciliation_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_telemetry_reconciliation_parser.add_argument("--high-empty-threshold", type=float, default=0.5)
    dogfood_telemetry_reconciliation_parser.add_argument(
        "--fresh-epoch-comparison-report",
        type=Path,
        help="Optional dogfood fresh-epoch-compare JSON report used as reset-avoidance evidence.",
    )
    dogfood_telemetry_reconciliation_parser.add_argument("--output", type=Path)
    dogfood_g4_review_queue_preview_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-preview",
        help="Build a read-only broad G4 review queue preview with ref-safe evidence and no queue persistence/apply.",
    )
    dogfood_g4_review_queue_preview_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--output", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--retrieval-ranking-report", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--rollback-confidence-report", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--rollback-replay-report", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--telemetry-reconciliation-report", type=Path)
    dogfood_g4_review_queue_preview_parser.add_argument("--human-review-approval-report", type=Path)
    dogfood_g4_review_queue_persist_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-persist",
        help="Persist preview queue items for manual approve/reject review without applying memory mutations.",
    )
    dogfood_g4_review_queue_persist_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_persist_parser.add_argument("--limit", type=int, default=200)
    dogfood_g4_review_queue_persist_parser.add_argument("--top", type=int, default=20)
    dogfood_g4_review_queue_persist_parser.add_argument("--queue-limit", type=int, default=20)
    dogfood_g4_review_queue_persist_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_g4_review_queue_persist_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_g4_review_queue_persist_parser.add_argument("--epoch-start")
    dogfood_g4_review_queue_persist_parser.add_argument("--lock-path", type=Path)
    dogfood_g4_review_queue_persist_parser.add_argument("--actor", required=True)
    dogfood_g4_review_queue_persist_parser.add_argument("--reason", required=True)
    dogfood_g4_review_queue_persist_parser.add_argument("--output", type=Path)
    dogfood_g4_review_queue_list_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-list", help="List persisted G4 review queue items without proposal raw JSON."
    )
    dogfood_g4_review_queue_list_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_list_parser.add_argument("--status", choices=["pending", "approved", "rejected"])
    dogfood_g4_review_queue_list_parser.add_argument("--limit", type=int, default=50)
    dogfood_g4_review_queue_update_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-update", help="Approve or reject a persisted G4 review queue item; does not apply it."
    )
    dogfood_g4_review_queue_update_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_update_parser.add_argument("queue_id")
    dogfood_g4_review_queue_update_parser.add_argument("--status", required=True, choices=["approved", "rejected"])
    dogfood_g4_review_queue_update_parser.add_argument("--actor", required=True)
    dogfood_g4_review_queue_update_parser.add_argument("--reason", required=True)
    dogfood_g4_review_queue_update_parser.add_argument("--policy")
    dogfood_g4_review_queue_update_parser.add_argument("--approval-phrase")
    dogfood_g4_review_queue_approval_report_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-approval-report",
        help="Emit a ref-safe read-only human approval artifact for the persisted G4 review queue; does not apply memory mutations.",
    )
    dogfood_g4_review_queue_approval_report_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_approval_report_parser.add_argument("--actor", required=True)
    dogfood_g4_review_queue_approval_report_parser.add_argument("--policy", required=True)
    dogfood_g4_review_queue_approval_report_parser.add_argument("--approval-phrase", required=True)
    dogfood_g4_review_queue_approval_report_parser.add_argument("--output", type=Path)
    dogfood_g4_apply_readiness_parser = dogfood_subparsers.add_parser(
        "g4-apply-readiness",
        help="Read-only bounded G4 apply readiness report from a green queue preview artifact; does not apply mutations.",
    )
    dogfood_g4_apply_readiness_parser.add_argument("db_path", type=Path)
    dogfood_g4_apply_readiness_parser.add_argument("--queue-preview-report", type=Path, required=True)
    dogfood_g4_apply_readiness_parser.add_argument("--max-apply", type=int, default=1)
    dogfood_g4_apply_readiness_parser.add_argument("--output", type=Path)
    dogfood_g4_readiness_gate_summary_parser = dogfood_subparsers.add_parser(
        "g4-readiness-gate-summary",
        help="Summarize retrieval-ranking and G4 operator bundle artifacts as a read-only preflight gate; does not apply mutations.",
    )
    dogfood_g4_readiness_gate_summary_parser.add_argument("db_path", type=Path)
    dogfood_g4_readiness_gate_summary_parser.add_argument("--retrieval-ranking-report", type=Path, required=True)
    dogfood_g4_readiness_gate_summary_parser.add_argument("--operator-apply-bundle-report", type=Path, required=True)
    dogfood_g4_readiness_gate_summary_parser.add_argument("--output", type=Path)
    dogfood_g4_post_apply_verification_parser = dogfood_subparsers.add_parser(
        "g4-post-apply-verification",
        help="Validate saved G4 apply, post-apply bundle, and rollback replay artifacts as a read-only stop gate; does not apply mutations.",
    )
    dogfood_g4_post_apply_verification_parser.add_argument("db_path", type=Path)
    dogfood_g4_post_apply_verification_parser.add_argument("--apply-report", type=Path, required=True)
    dogfood_g4_post_apply_verification_parser.add_argument("--post-apply-bundle-report", type=Path, required=True)
    dogfood_g4_post_apply_verification_parser.add_argument("--rollback-replay-report", type=Path, required=True)
    dogfood_g4_post_apply_verification_parser.add_argument("--output", type=Path)
    dogfood_g4_operator_apply_packet_parser = dogfood_subparsers.add_parser(
        "g4-operator-apply-packet",
        help="Emit a read-only machine-readable G4 manual apply checklist packet from green pre-apply artifacts; does not apply mutations.",
    )
    dogfood_g4_operator_apply_packet_parser.add_argument("db_path", type=Path)
    dogfood_g4_operator_apply_packet_parser.add_argument("--operator-apply-bundle-report", type=Path, required=True)
    dogfood_g4_operator_apply_packet_parser.add_argument("--readiness-gate-summary-report", type=Path, required=True)
    dogfood_g4_operator_apply_packet_parser.add_argument("--actor", required=True)
    dogfood_g4_operator_apply_packet_parser.add_argument("--max-apply", type=int, default=1)
    dogfood_g4_operator_apply_packet_parser.add_argument("--output", type=Path)
    dogfood_g4_operator_apply_bundle_parser = dogfood_subparsers.add_parser(
        "g4-operator-apply-bundle",
        help="Generate read-only G4 approval, preview, readiness artifacts and an exact manual apply command preview; does not apply mutations.",
    )
    dogfood_g4_operator_apply_bundle_parser.add_argument("db_path", type=Path)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--report-dir", type=Path, required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--retrieval-ranking-report", type=Path, required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--rollback-confidence-report", type=Path, required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--rollback-replay-report", type=Path, required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--telemetry-reconciliation-report", type=Path, required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--actor", required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--reason", required=True)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--max-apply", type=int, default=1)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--limit", type=int, default=200)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--top", type=int, default=20)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--queue-limit", type=int, default=20)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--epoch-start")
    dogfood_g4_operator_apply_bundle_parser.add_argument("--lock-path", type=Path)
    dogfood_g4_operator_apply_bundle_parser.add_argument("--output", type=Path)
    dogfood_g4_review_queue_apply_parser = dogfood_subparsers.add_parser(
        "g4-review-queue-apply",
        help="Apply approved G4 review queue items through a guarded audit-only corridor with backup and rollback hint.",
    )
    dogfood_g4_review_queue_apply_parser.add_argument("db_path", type=Path)
    dogfood_g4_review_queue_apply_parser.add_argument("--queue-id", action="append")
    dogfood_g4_review_queue_apply_parser.add_argument("--policy", required=True)
    dogfood_g4_review_queue_apply_parser.add_argument("--approval-phrase", required=True)
    dogfood_g4_review_queue_apply_parser.add_argument("--actor", required=True)
    dogfood_g4_review_queue_apply_parser.add_argument("--reason", required=True)
    dogfood_g4_review_queue_apply_parser.add_argument("--backup-path", type=Path)
    dogfood_g4_review_queue_apply_parser.add_argument("--output", type=Path)
    dogfood_g4_review_queue_apply_parser.add_argument("--max-apply", type=int, default=1)
    dogfood_g4_review_queue_preview_parser.add_argument("--limit", type=int, default=200)
    dogfood_g4_review_queue_preview_parser.add_argument("--top", type=int, default=20)
    dogfood_g4_review_queue_preview_parser.add_argument("--queue-limit", type=int, default=20)
    dogfood_g4_review_queue_preview_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_g4_review_queue_preview_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_g4_review_queue_preview_parser.add_argument("--epoch-start", help="Optional ISO-8601 cutoff for fresh-epoch comparison of historical blockers.")
    dogfood_g4_review_queue_preview_parser.add_argument("--lock-path", type=Path)
    dogfood_g4_linkage_gap_diagnose_parser = dogfood_subparsers.add_parser(
        "g4-linkage-gap-diagnose",
        help="Explain fresh trace-linkage gaps in aggregate/ref-only form before any broad G4 apply path.",
    )
    dogfood_g4_linkage_gap_diagnose_parser.add_argument("db_path", type=Path)
    dogfood_g4_linkage_gap_diagnose_parser.add_argument("--epoch-start", required=True)
    dogfood_g4_linkage_gap_diagnose_parser.add_argument("--surface")
    dogfood_g4_linkage_gap_diagnose_parser.add_argument("--output", type=Path)
    dogfood_scheduled_parser = dogfood_subparsers.add_parser(
        "scheduled-dry-run",
        help="Run a cron-friendly read-only G3e dogfood bundle before any G4 apply-mode plan.",
    )
    dogfood_scheduled_parser.add_argument("db_path", type=Path)
    dogfood_scheduled_parser.add_argument("--output", type=Path)
    dogfood_scheduled_parser.add_argument("--hermes-config", type=Path)
    dogfood_scheduled_parser.add_argument("--since-hours", type=int, default=24)
    dogfood_scheduled_parser.add_argument("--epoch-start", help="Optional ISO-8601 cutoff for fresh-epoch trace quality inside the scheduled bundle.")
    dogfood_scheduled_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_scheduled_parser.add_argument("--min-evidence-count", type=int, default=2)
    dogfood_scheduled_parser.add_argument("--limit", type=int, default=200)
    dogfood_scheduled_parser.add_argument("--top", type=int, default=20)
    dogfood_scheduled_parser.add_argument("--frequent-threshold", type=int, default=3)
    dogfood_scheduled_parser.add_argument("--remember-sample-limit", type=int, default=10)
    dogfood_scheduled_parser.add_argument("--candidate-min", type=int, default=1)
    dogfood_scheduled_parser.add_argument("--max-decay-risk", type=int, default=0)
    dogfood_scheduled_parser.add_argument("--lock-path", type=Path)
    dogfood_scheduled_compare_parser = dogfood_subparsers.add_parser(
        "scheduled-compare",
        help="Compare saved scheduled-dry-run JSON reports with read-only G3f stability gates before any G4 plan.",
    )
    dogfood_scheduled_compare_parser.add_argument(
        "--report",
        type=Path,
        action="append",
        required=True,
        dest="reports",
        help="Path to a JSON report produced by dogfood scheduled-dry-run; repeat for multiple runs.",
    )
    dogfood_scheduled_compare_parser.add_argument("--output", type=Path)
    dogfood_scheduled_compare_parser.add_argument("--min-report-count", type=int, default=2)
    dogfood_scheduled_compare_parser.add_argument("--max-decay-risk", type=int, default=0)
    dogfood_scheduled_blocker_resolution_parser = dogfood_subparsers.add_parser(
        "scheduled-blocker-resolution",
        help="Classify scheduled dry-run blockers from aggregate-safe evidence for bounded partial automation only.",
    )
    dogfood_scheduled_blocker_resolution_parser.add_argument("--report", type=Path, required=True)
    dogfood_scheduled_blocker_resolution_parser.add_argument("--output", type=Path)
    dogfood_scheduled_blocker_resolution_parser.add_argument("--accept-ready-trace-quality", action="store_true")
    dogfood_scheduled_blocker_resolution_parser.add_argument("--allow-monitor-only-decay", action="store_true")
    dogfood_scheduled_blocker_resolution_parser.add_argument("--min-trace-coverage", type=float, default=0.25)
    dogfood_scheduled_blocker_resolution_parser.add_argument("--max-empty-retrieval-ratio", type=float, default=0.5)
    dogfood_scheduled_blocker_resolution_parser.add_argument("--max-monitor-decay-score", type=float, default=0.25)
    dogfood_background_parser = dogfood_subparsers.add_parser(
        "background-dry-run",
        help="Evaluate G3 background dry-run reports with read-only dogfood quality gates before any G4 plan.",
    )
    dogfood_background_parser.add_argument("db_path", type=Path)
    dogfood_background_parser.add_argument(
        "--report",
        type=Path,
        action="append",
        required=True,
        dest="reports",
        help="Path to a JSON report produced by consolidation background dry-run; repeat for multiple runs.",
    )
    dogfood_background_parser.add_argument("--output", type=Path)
    dogfood_background_parser.add_argument("--candidate-min", type=int, default=1)
    dogfood_background_parser.add_argument("--max-decay-risk", type=int, default=0)
    dogfood_background_parser.add_argument("--min-completed-runs", type=int, default=1)

    graph_parser = subparsers.add_parser("graph")
    graph_subparsers = graph_parser.add_subparsers(dest="graph_action", required=True)
    graph_inspect_parser = graph_subparsers.add_parser("inspect")
    graph_inspect_parser.add_argument("db_path", type=Path)
    graph_inspect_parser.add_argument("start_ref")
    graph_inspect_parser.add_argument("--depth", type=int, default=1)
    graph_inspect_parser.add_argument("--limit", type=int, default=100)
    graph_export_html_parser = graph_subparsers.add_parser(
        "export-html",
        help="Write a standalone read-only neural-style local HTML graph visualization without raw source/query text.",
    )
    graph_export_html_parser.add_argument("db_path", type=Path)
    graph_export_html_parser.add_argument("--output", type=Path, required=True)
    graph_export_html_parser.add_argument("--limit", type=int, default=200)
    graph_export_html_parser.add_argument(
        "--include-memory-labels",
        action="store_true",
        help="Opt in to embedding curated memory labels in the local HTML. Raw source/query/trace text is still excluded.",
    )

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
        default=True,
        help="Record sanitized metadata-only experience traces for real Hermes turns. Raw prompts are never stored.",
    )
    hermes_pre_llm_hook_parser.add_argument(
        "--no-record-trace",
        action="store_false",
        dest="record_trace",
        help="Disable Hermes turn trace recording for this hook invocation.",
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
        help="Include the backwards-compatible --record-trace flag in the rendered hook command. Sanitized metadata-only trace recording is enabled by default at runtime.",
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
        help="Install the hook with the backwards-compatible --record-trace flag. Sanitized metadata-only trace recording is enabled by default at runtime.",
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
        help="Install the hook with the backwards-compatible --record-trace flag. Sanitized metadata-only trace recording is enabled by default at runtime.",
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

    if args.command == "backup":
        if args.backup_action == "export":
            print(export_backup(db_path=args.db_path, output_path=args.output_path).model_dump_json(indent=2))
            return
        if args.backup_action == "inspect":
            print(inspect_backup(args.bundle_path).model_dump_json(indent=2))
            return
        if args.backup_action == "restore":
            print(
                restore_backup(
                    bundle_path=args.bundle_path,
                    output_db_path=args.output_db_path,
                    overwrite=args.overwrite,
                ).model_dump_json(indent=2)
            )
            return
        raise ValueError(f"Unsupported backup action: {args.backup_action}")

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
        if args.dogfood_action == "storage-health":
            print(json.dumps(_dogfood_storage_health_payload(args), indent=2))
            return
        if args.dogfood_action == "query-preview-cleanup":
            print(json.dumps(_dogfood_query_preview_cleanup_payload(args), indent=2))
            return
        if args.dogfood_action == "query-preview-cleanup-restore":
            print(json.dumps(_dogfood_query_preview_cleanup_restore_dry_run_payload(args), indent=2))
            return
        if args.dogfood_action == "ordinary-trace-metadata-cleanup":
            print(json.dumps(_dogfood_ordinary_trace_metadata_cleanup_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-quality":
            if args.since_hours < 1:
                raise ValueError("dogfood trace-quality since-hours must be >= 1")
            if getattr(args, "epoch_start", None):
                _parse_epoch_start(args.epoch_start)
            if not 0 <= args.min_trace_coverage <= 1:
                raise ValueError("dogfood trace-quality min-trace-coverage must be between 0 and 1")
            if args.min_evidence_count < 1:
                raise ValueError("dogfood trace-quality min-evidence-count must be >= 1")
            print(json.dumps(_dogfood_trace_quality_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-cluster-preview":
            print(json.dumps(_dogfood_trace_cluster_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-candidate-generate":
            print(json.dumps(_dogfood_trace_candidate_generate_payload(args), indent=2))
            return
        if args.dogfood_action == "reinforcement-refinement-preview":
            print(json.dumps(_dogfood_reinforcement_refinement_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "decay-collapse-preview":
            print(json.dumps(_dogfood_decay_collapse_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "supersession-preview":
            print(json.dumps(_dogfood_supersession_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "lifecycle-candidate-persist":
            print(json.dumps(_dogfood_lifecycle_candidate_persist_payload(args), indent=2))
            return
        if args.dogfood_action == "lifecycle-candidate-list":
            if args.limit < 1:
                raise ValueError("dogfood lifecycle-candidate-list limit must be >= 1")
            print(json.dumps(_dogfood_lifecycle_candidate_list_payload(args), indent=2))
            return
        if args.dogfood_action == "lifecycle-candidate-update":
            print(json.dumps(_dogfood_lifecycle_candidate_update_payload(args), indent=2))
            return
        if args.dogfood_action == "lifecycle-candidate-apply":
            print(json.dumps(_dogfood_lifecycle_candidate_apply_payload(args), indent=2))
            return
        if args.dogfood_action == "retrieval-ranking-gate":
            print(json.dumps(_dogfood_retrieval_ranking_gate_payload(args), indent=2))
            return
        if args.dogfood_action == "rollback-confidence":
            print(json.dumps(_dogfood_rollback_confidence_payload(args), indent=2))
            return
        if args.dogfood_action == "rollback-replay-validate":
            print(json.dumps(_dogfood_rollback_replay_validate_payload(args), indent=2))
            return
        if args.dogfood_action == "retrieval-ranking-experiment":
            print(json.dumps(_dogfood_retrieval_ranking_experiment_payload(args), indent=2))
            return
        if args.dogfood_action == "retrieval-ranking-migrate-default":
            print(json.dumps(_dogfood_retrieval_ranking_migrate_default_payload(args), indent=2))
            return
        if args.dogfood_action == "decay-collapse-decision":
            print(json.dumps(_dogfood_decay_collapse_decision_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-candidate-persist":
            print(json.dumps(_dogfood_trace_candidate_persist_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-candidate-list":
            if args.limit < 1:
                raise ValueError("dogfood trace-candidate-list limit must be >= 1")
            print(json.dumps(_dogfood_trace_candidate_list_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-candidate-update":
            print(json.dumps(_dogfood_trace_candidate_update_payload(args), indent=2))
            return
        if args.dogfood_action == "trace-candidate-apply":
            print(json.dumps(_dogfood_trace_candidate_apply_payload(args), indent=2))
            return
        if args.dogfood_action == "fresh-epoch":
            if not 0 <= args.min_trace_coverage <= 1:
                raise ValueError("dogfood fresh-epoch min-trace-coverage must be between 0 and 1")
            if args.min_evidence_count < 1:
                raise ValueError("dogfood fresh-epoch min-evidence-count must be >= 1")
            if not 0 <= args.high_empty_threshold <= 1:
                raise ValueError("dogfood fresh-epoch high-empty-threshold must be between 0 and 1")
            print(json.dumps(_dogfood_fresh_epoch_payload(args), indent=2))
            return

        if args.dogfood_action == "fresh-epoch-compare":
            print(
                json.dumps(
                    _fresh_epoch_comparison_report(
                        report_paths=args.reports,
                        output_path=args.output,
                        min_report_count=args.min_report_count,
                    ),
                    indent=2,
                )
            )
            return
        if args.dogfood_action == "fresh-epoch-runway":
            if args.min_report_count < 1:
                raise ValueError("dogfood fresh-epoch-runway min-report-count must be >= 1")
            if not 0 <= args.min_trace_coverage <= 1:
                raise ValueError("dogfood fresh-epoch-runway min-trace-coverage must be between 0 and 1")
            if args.min_evidence_count < 1:
                raise ValueError("dogfood fresh-epoch-runway min-evidence-count must be >= 1")
            if not 0 <= args.high_empty_threshold <= 1:
                raise ValueError("dogfood fresh-epoch-runway high-empty-threshold must be between 0 and 1")
            print(json.dumps(_dogfood_fresh_epoch_runway_payload(args), indent=2))
            return
        if args.dogfood_action == "telemetry-reset-preview":
            print(json.dumps(_dogfood_telemetry_reset_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "telemetry-reset-apply":
            print(json.dumps(_dogfood_telemetry_reset_apply_payload(args), indent=2))
            return
        if args.dogfood_action == "telemetry-reconciliation":
            print(json.dumps(_dogfood_telemetry_reconciliation_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-preview":
            if args.queue_limit < 1:
                raise ValueError("dogfood g4-review-queue-preview queue-limit must be >= 1")
            print(json.dumps(_dogfood_g4_review_queue_preview_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-linkage-gap-diagnose":
            print(json.dumps(_dogfood_g4_linkage_gap_diagnose_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-persist":
            if args.queue_limit < 1:
                raise ValueError("dogfood g4-review-queue-persist queue-limit must be >= 1")
            print(json.dumps(_dogfood_g4_review_queue_persist_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-list":
            if args.limit < 1:
                raise ValueError("dogfood g4-review-queue-list limit must be >= 1")
            print(json.dumps(_dogfood_g4_review_queue_list_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-update":
            print(json.dumps(_dogfood_g4_review_queue_update_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-approval-report":
            print(json.dumps(_dogfood_g4_review_queue_approval_report_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-apply-readiness":
            print(json.dumps(_dogfood_g4_apply_readiness_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-readiness-gate-summary":
            print(json.dumps(_dogfood_g4_readiness_gate_summary_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-post-apply-verification":
            print(json.dumps(_dogfood_g4_post_apply_verification_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-operator-apply-packet":
            print(json.dumps(_dogfood_g4_operator_apply_packet_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-operator-apply-bundle":
            print(json.dumps(_dogfood_g4_operator_apply_bundle_payload(args), indent=2))
            return
        if args.dogfood_action == "g4-review-queue-apply":
            print(json.dumps(_dogfood_g4_review_queue_apply_payload(args), indent=2))
            return
        if args.dogfood_action == "scheduled-dry-run":
            print(json.dumps(_dogfood_scheduled_dry_run_payload(args), indent=2))
            return
        if args.dogfood_action == "scheduled-compare":
            print(
                json.dumps(
                    _scheduled_dry_run_comparison_report(
                        report_paths=args.reports,
                        output_path=args.output,
                        min_report_count=args.min_report_count,
                        max_decay_risk=args.max_decay_risk,
                    ),
                    indent=2,
                )
            )
            return
        if args.dogfood_action == "scheduled-blocker-resolution":
            print(json.dumps(_dogfood_scheduled_blocker_resolution_payload(args), indent=2))
            return
        if args.dogfood_action == "background-dry-run":
            print(
                json.dumps(
                    _background_dry_run_dogfood_report(
                        args.db_path,
                        report_paths=args.reports,
                        output_path=args.output,
                        candidate_min=args.candidate_min,
                        max_decay_risk=args.max_decay_risk,
                        min_completed_runs=args.min_completed_runs,
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
        if args.graph_action == "export-html":
            print(
                json.dumps(
                    _export_memory_graph_html(
                        args.db_path,
                        output_path=args.output,
                        limit=args.limit,
                        include_memory_labels=args.include_memory_labels,
                    ),
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
