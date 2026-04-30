from __future__ import annotations

from math import ceil
from typing import Literal, TypeVar

from pydantic import BaseModel, Field

from agent_memory.core.models import MemoryPacket, PolicyHintReasonCode, VerificationPlan, VerificationStep


T = TypeVar("T")


class HermesTopMemory(BaseModel):
    memory_type: Literal["fact", "procedure", "episode"]
    memory_id: int
    label: str
    trust_band: Literal["high", "medium", "low"]
    has_hidden_alternatives: bool = False


class HermesAdapterPayload(BaseModel):
    query: str
    response_mode: Literal["direct", "cautious", "verify_first"]
    prompt_prefix: str
    pre_answer_checks: list[str] = Field(default_factory=list)
    answer_guidelines: list[str] = Field(default_factory=list)
    policy_reason_codes: list[PolicyHintReasonCode] = Field(default_factory=list)
    top_memory: HermesTopMemory | None = None
    alternative_memories: list[HermesTopMemory] = Field(default_factory=list)
    verification_plan: VerificationPlan = Field(default_factory=VerificationPlan)


class HermesMemoryContext(BaseModel):
    payload: HermesAdapterPayload
    prompt_text: str
    should_answer_now: bool
    should_verify_first: bool
    blocking_steps: list[VerificationStep] = Field(default_factory=list)


class HermesVerificationResult(BaseModel):
    step_action: Literal[
        "gather_more_evidence",
        "cross_check_hidden_alternatives",
        "corroborate_before_answer",
    ]
    status: Literal["passed", "failed", "skipped", "unavailable"]
    evidence_summary: str
    target_memory_type: Literal["fact", "procedure", "episode"] | None = None
    target_memory_id: int | None = None


class HermesVerificationOutcome(BaseModel):
    context: HermesMemoryContext
    results: list[HermesVerificationResult] = Field(default_factory=list)
    prompt_text: str
    should_answer_now: bool
    should_verify_first: bool
    response_mode_after_verification: Literal["direct", "cautious", "verify_first"]
    unresolved_blocking_steps: list[VerificationStep] = Field(default_factory=list)


def _render_verification_step(step: VerificationStep) -> str:
    target = "none"
    if step.target_memory_type is not None and step.target_memory_id is not None:
        target = f"{step.target_memory_type} #{step.target_memory_id}"
    compare_against = ",".join(str(memory_id) for memory_id in step.compare_against_memory_ids) or "none"
    blocking = "yes" if step.blocking else "no"
    reason = step.reason_code or "none"
    return (
        f"Verification step: {step.action}, severity={step.severity}, blocking={blocking}, "
        f"target={target}, compare_against={compare_against}, reason={reason}"
    )


def _render_verification_result(result: HermesVerificationResult) -> str:
    target = "none"
    if result.target_memory_type is not None and result.target_memory_id is not None:
        target = f"{result.target_memory_type} #{result.target_memory_id}"
    return (
        f"Verification result: {result.step_action}, status={result.status}, "
        f"target={target}, evidence={result.evidence_summary}"
    )


def _verification_result_key(
    action: str,
    target_memory_type: str | None,
    target_memory_id: int | None,
) -> tuple[str, str | None, int | None]:
    return (action, target_memory_type, target_memory_id)


def _step_result_key(step: VerificationStep) -> tuple[str, str | None, int | None]:
    return _verification_result_key(step.action, step.target_memory_type, step.target_memory_id)


def _result_key(result: HermesVerificationResult) -> tuple[str, str | None, int | None]:
    return _verification_result_key(result.step_action, result.target_memory_type, result.target_memory_id)


def _response_mode_after_resolved_verification(
    original_response_mode: Literal["direct", "cautious", "verify_first"],
) -> Literal["direct", "cautious", "verify_first"]:
    if original_response_mode == "verify_first":
        return "cautious"
    return original_response_mode


def apply_hermes_verification_results(
    context: HermesMemoryContext,
    results: list[HermesVerificationResult],
) -> HermesVerificationOutcome:
    result_by_key = {_result_key(result): result for result in results}
    unresolved_blocking_steps = [
        step
        for step in context.blocking_steps
        if result_by_key.get(_step_result_key(step)) is None
        or result_by_key[_step_result_key(step)].status != "passed"
    ]
    should_verify_first = bool(unresolved_blocking_steps)
    response_mode_after_verification = (
        "verify_first"
        if should_verify_first
        else _response_mode_after_resolved_verification(context.payload.response_mode)
    )
    result_lines = [_render_verification_result(result) for result in results]
    prompt_text = context.prompt_text
    if result_lines:
        prompt_text = "\n".join([prompt_text, *result_lines])
    return HermesVerificationOutcome(
        context=context,
        results=results,
        prompt_text=prompt_text,
        should_answer_now=not should_verify_first,
        should_verify_first=should_verify_first,
        response_mode_after_verification=response_mode_after_verification,
        unresolved_blocking_steps=unresolved_blocking_steps,
    )


def _limit_items(items: list[T], max_items: int | None) -> list[T]:
    if max_items is None:
        return items
    return items[: max(0, max_items)]


def _append_with_line_budget(lines: list[str], line: str, max_prompt_lines: int | None) -> bool:
    if max_prompt_lines is not None and len(lines) >= max(0, max_prompt_lines):
        return False
    lines.append(line)
    return True


def _apply_char_budget_to_lines(lines: list[str], max_prompt_chars: int | None) -> list[str]:
    if max_prompt_chars is None:
        return lines

    remaining = max(0, max_prompt_chars)
    budgeted_lines: list[str] = []
    for line in lines:
        line_cost = len(line) if not budgeted_lines else len(line) + 1
        if line_cost > remaining:
            break
        budgeted_lines.append(line)
        remaining -= line_cost
    return budgeted_lines


def estimate_prompt_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, ceil(len(text) / 4))


def _apply_token_budget_to_lines(lines: list[str], max_prompt_tokens: int | None) -> list[str]:
    if max_prompt_tokens is None:
        return lines

    max_tokens = max(0, max_prompt_tokens)
    budgeted_lines: list[str] = []
    for line in lines:
        candidate_lines = [*budgeted_lines, line]
        if estimate_prompt_tokens("\n".join(candidate_lines)) > max_tokens:
            break
        budgeted_lines.append(line)
    return budgeted_lines


def _apply_size_budgets_to_lines(
    lines: list[str],
    *,
    max_prompt_chars: int | None,
    max_prompt_tokens: int | None,
) -> list[str]:
    token_budgeted_lines = _apply_token_budget_to_lines(lines, max_prompt_tokens)
    return _apply_char_budget_to_lines(token_budgeted_lines, max_prompt_chars)


def render_hermes_prompt_lines(
    payload: HermesAdapterPayload,
    *,
    max_prompt_lines: int | None = None,
    max_prompt_chars: int | None = None,
    max_prompt_tokens: int | None = None,
    max_verification_steps: int | None = None,
    max_alternatives: int | None = None,
    max_guidelines: int | None = None,
    include_reason_codes: bool = True,
) -> list[str]:
    lines: list[str] = []
    for line in [
        f"Memory response mode: {payload.response_mode}",
        f"Prompt prefix: {payload.prompt_prefix}",
    ]:
        if not _append_with_line_budget(lines, line, max_prompt_lines):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    if payload.top_memory is None:
        if not _append_with_line_budget(lines, "Top memory: none", max_prompt_lines):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)
    else:
        hidden_alternatives = "yes" if payload.top_memory.has_hidden_alternatives else "no"
        if not _append_with_line_budget(
            lines,
            "Top memory: "
            f"{payload.top_memory.memory_type} #{payload.top_memory.memory_id} "
            f"({payload.top_memory.label}), trust={payload.top_memory.trust_band}, "
            f"hidden_alternatives={hidden_alternatives}",
            max_prompt_lines,
        ):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    checks_before_steps = max_prompt_lines is None
    if checks_before_steps:
        for check in payload.pre_answer_checks:
            if not _append_with_line_budget(lines, f"Pre-answer check: {check}", max_prompt_lines):
                return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    for step in _limit_items(payload.verification_plan.steps, max_verification_steps):
        if not _append_with_line_budget(lines, _render_verification_step(step), max_prompt_lines):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    if not checks_before_steps:
        for check in payload.pre_answer_checks:
            if not _append_with_line_budget(lines, f"Pre-answer check: {check}", max_prompt_lines):
                return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    for memory in _limit_items(payload.alternative_memories, max_alternatives):
        hidden_alternatives = "yes" if memory.has_hidden_alternatives else "no"
        if not _append_with_line_budget(
            lines,
            "Alternative memory: "
            f"{memory.memory_type} #{memory.memory_id} "
            f"({memory.label}), trust={memory.trust_band}, "
            f"hidden_alternatives={hidden_alternatives}",
            max_prompt_lines,
        ):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    for guideline in _limit_items(payload.answer_guidelines, max_guidelines):
        if not _append_with_line_budget(lines, f"Guideline: {guideline}", max_prompt_lines):
            return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)

    if include_reason_codes:
        if payload.policy_reason_codes:
            _append_with_line_budget(lines, f"Reason codes: {', '.join(payload.policy_reason_codes)}", max_prompt_lines)
        else:
            _append_with_line_budget(lines, "Reason codes: none", max_prompt_lines)

    return _apply_size_budgets_to_lines(lines, max_prompt_chars=max_prompt_chars, max_prompt_tokens=max_prompt_tokens)


def render_hermes_prompt_text(
    payload: HermesAdapterPayload,
    *,
    max_prompt_lines: int | None = None,
    max_prompt_chars: int | None = None,
    max_prompt_tokens: int | None = None,
    max_verification_steps: int | None = None,
    max_alternatives: int | None = None,
    max_guidelines: int | None = None,
    include_reason_codes: bool = True,
) -> str:
    return "\n".join(
        render_hermes_prompt_lines(
            payload,
            max_prompt_lines=max_prompt_lines,
            max_prompt_chars=max_prompt_chars,
            max_prompt_tokens=max_prompt_tokens,
            max_verification_steps=max_verification_steps,
            max_alternatives=max_alternatives,
            max_guidelines=max_guidelines,
            include_reason_codes=include_reason_codes,
        )
    )


def _render_memory_snippet_lines(packet: MemoryPacket, *, top_k: int) -> list[str]:
    facts_by_id = {fact.id: fact for fact in packet.semantic_facts}
    procedures_by_id = {procedure.id: procedure for procedure in packet.procedural_guidance}
    episodes_by_id = {episode.id: episode for episode in packet.episodic_context}

    lines: list[str] = []
    for trace in packet.retrieval_trace[: max(0, top_k)]:
        if trace.memory_type == "fact":
            fact = facts_by_id.get(trace.memory_id)
            if fact is not None:
                lines.append(
                    f"Retrieved fact #{fact.id}: {fact.subject_ref} | {fact.predicate} | {fact.object_ref_or_value}"
                )
            continue
        if trace.memory_type == "procedure":
            procedure = procedures_by_id.get(trace.memory_id)
            if procedure is not None:
                step_preview = "; ".join(procedure.steps[:2]) or procedure.trigger_context
                lines.append(
                    f"Retrieved procedure #{procedure.id}: {procedure.name} | trigger={procedure.trigger_context} | steps={step_preview}"
                )
            continue
        if trace.memory_type == "episode":
            episode = episodes_by_id.get(trace.memory_id)
            if episode is not None:
                lines.append(f"Retrieved episode #{episode.id}: {episode.title} | {episode.summary}")
    return lines

def _build_ranked_memories(packet: MemoryPacket, top_k: int) -> list[HermesTopMemory]:
    trust_by_key = {
        (trust.memory_type, trust.memory_id): trust
        for trust in packet.trust_summaries
    }
    ranked_memories: list[HermesTopMemory] = []
    for trace in packet.retrieval_trace[: max(0, top_k)]:
        trust = trust_by_key.get((trace.memory_type, trace.memory_id))
        if trust is None:
            continue
        ranked_memories.append(
            HermesTopMemory(
                memory_type=trace.memory_type,
                memory_id=trace.memory_id,
                label=trace.label,
                trust_band=trust.trust_band,
                has_hidden_alternatives=trust.has_hidden_alternatives,
            )
        )
    return ranked_memories


def build_hermes_adapter_payload(packet: MemoryPacket, top_k: int = 1) -> HermesAdapterPayload:
    decision = packet.decision_summary
    if decision is None:
        return HermesAdapterPayload(
            query=packet.query,
            response_mode="verify_first",
            prompt_prefix="No reliable memory is available yet; gather more evidence before answering.",
            pre_answer_checks=["gather_more_evidence"],
            answer_guidelines=[
                "No reliable memory was retrieved.",
                "Ask for clarification or gather more evidence before answering.",
            ],
            policy_reason_codes=[],
            top_memory=None,
            alternative_memories=[],
            verification_plan=VerificationPlan(
                required=True,
                fallback_answer_mode="verify_first",
                steps=[
                    VerificationStep(
                        action="gather_more_evidence",
                        severity="high",
                        blocking=True,
                        instruction="Gather more evidence before answering because no reliable memory was retrieved.",
                    )
                ],
            ),
        )

    ranked_memories = _build_ranked_memories(packet, top_k=max(1, top_k))
    top_memory = ranked_memories[0] if ranked_memories else HermesTopMemory(
        memory_type=decision.target_memory_type,
        memory_id=decision.target_memory_id,
        label=decision.target_label,
        trust_band=decision.trust_band,
        has_hidden_alternatives=decision.has_hidden_alternatives,
    )
    alternative_memories = ranked_memories[1:]

    answer_guidelines = [
        f"Use {decision.target_memory_type} #{decision.target_memory_id} ({decision.target_label}) as the primary memory for the answer.",
    ]
    pre_answer_checks: list[str] = []

    if decision.requires_cross_check:
        pre_answer_checks.append("cross_check_hidden_alternatives")
        answer_guidelines.append("Surface hidden alternatives before giving the final answer.")

    if decision.should_mention_uncertainty:
        answer_guidelines.append("Explicitly mention uncertainty when presenting this memory.")

    if decision.should_avoid_definitive:
        pre_answer_checks.append("corroborate_before_answer")
        answer_guidelines.append("Avoid definitive claims until corroborating evidence is found.")

    if decision.recommended_answer_mode == "direct":
        prompt_prefix = "Answer directly using the top-ranked memory."
        answer_guidelines.append("Answer directly; no uncertainty qualifier is required.")
    elif decision.recommended_answer_mode == "cautious":
        prompt_prefix = "Answer using the top-ranked memory, but explicitly mention uncertainty."
    else:
        prompt_prefix = "Do not answer definitively yet; verify hidden alternatives or corroborating evidence first."

    return HermesAdapterPayload(
        query=packet.query,
        response_mode=decision.recommended_answer_mode,
        prompt_prefix=prompt_prefix,
        pre_answer_checks=pre_answer_checks,
        answer_guidelines=answer_guidelines,
        policy_reason_codes=decision.reason_codes,
        top_memory=top_memory,
        alternative_memories=alternative_memories,
        verification_plan=packet.verification_plan,
    )


def prepare_hermes_memory_context(
    packet: MemoryPacket,
    top_k: int = 1,
    *,
    max_prompt_lines: int | None = None,
    max_prompt_chars: int | None = None,
    max_prompt_tokens: int | None = None,
    max_verification_steps: int | None = None,
    max_alternatives: int | None = None,
    max_guidelines: int | None = None,
    include_reason_codes: bool = True,
) -> HermesMemoryContext:
    payload = build_hermes_adapter_payload(packet, top_k=top_k)
    blocking_steps = [step for step in payload.verification_plan.steps if step.blocking]
    should_verify_first = payload.response_mode == "verify_first" or bool(blocking_steps)
    prompt_lines = render_hermes_prompt_lines(
        payload,
        max_prompt_lines=max_prompt_lines,
        max_prompt_chars=None,
        max_prompt_tokens=None,
        max_verification_steps=max_verification_steps,
        max_alternatives=max_alternatives,
        max_guidelines=max_guidelines,
        include_reason_codes=include_reason_codes,
    )
    for snippet_line in _render_memory_snippet_lines(packet, top_k=max(1, top_k)):
        if not _append_with_line_budget(prompt_lines, snippet_line, max_prompt_lines):
            break
    prompt_text = "\n".join(
        _apply_size_budgets_to_lines(
            prompt_lines,
            max_prompt_chars=max_prompt_chars,
            max_prompt_tokens=max_prompt_tokens,
        )
    )
    return HermesMemoryContext(
        payload=payload,
        prompt_text=prompt_text,
        should_answer_now=not should_verify_first,
        should_verify_first=should_verify_first,
        blocking_steps=blocking_steps,
    )
