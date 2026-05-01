from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

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
    get_fact,
    get_memory_status,
    initialize_database,
    list_candidate_episodes,
    list_candidate_facts,
    list_candidate_procedures,
    list_fact_replacement_relations,
    list_facts_by_claim_slot,
    list_memory_status_history,
    list_relations_for_node,
    list_retrieval_observations,
)


def _dump_models(models: list[Any]) -> str:
    return json.dumps([model.model_dump(mode="json") for model in models], indent=2)


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
    empty_retrieval_count = 0
    for observation in observations:
        if not observation.retrieved_memory_refs:
            empty_retrieval_count += 1
        for memory_ref in observation.retrieved_memory_refs:
            memory_ref_counts[memory_ref] += 1
            sample_ids = sample_observation_ids_by_ref[memory_ref]
            if len(sample_ids) < 5:
                sample_ids.append(observation.id)

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
        "observation_audit": audit,
        "candidates": candidates,
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
    observations_review_candidates_parser = observations_subparsers.add_parser(
        "review-candidates",
        help="Build a read-only forensic review report from top retrieval observation refs.",
    )
    observations_review_candidates_parser.add_argument("db_path", type=Path)
    observations_review_candidates_parser.add_argument("--limit", type=int, default=200)
    observations_review_candidates_parser.add_argument("--top", type=int, default=10)
    observations_review_candidates_parser.add_argument("--frequent-threshold", type=int, default=3)

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
