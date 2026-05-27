from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent_memory.adapters.hermes import HermesMemoryContext
from agent_memory.core.retrieval import retrieve_memory_packet


FOLLOWUP_FALLBACK_MARKER = "Follow-up fallback: expanded context-poor query with agent-memory handoff terms."

_FOLLOWUP_TERMS = (
    "이후",
    "다음",
    "하던 작업",
    "하고 있었",
    "작업은 뭐",
    "개선",
    "필요한거",
    "필요한 거",
    "뭐지",
    "next",
    "follow up",
    "follow-up",
    "what were we",
    "where were we",
    "what next",
    "next work",
)

_AGENT_MEMORY_SCOPE_TERMS = (
    "agent-memory",
    "agent_memory",
    "memory",
)

_AGENT_MEMORY_HANDOFF_EXPANSION = (
    "agent-memory current handoff next action .dev status roadmap "
    "memory-consolidation current-progress next-agent-memory-action "
    "context-poor follow-up runtime fallback scheduled evidence blocker fact:5 fact:6"
)


@dataclass(frozen=True)
class FollowupFallbackResult:
    context: HermesMemoryContext
    used_fallback: bool


def looks_like_context_poor_followup(query: str) -> bool:
    normalized = " ".join(query.lower().split())
    if not normalized:
        return False
    return any(term in normalized for term in _FOLLOWUP_TERMS)


def cwd_looks_like_agent_memory(cwd: str | Path | None) -> bool:
    if cwd is None:
        return False
    path = Path(cwd).expanduser().resolve(strict=False)
    return path.name == "agent-memory" or path.parent.name == "agent-memory"


def scope_looks_like_agent_memory(preferred_scope: str | None) -> bool:
    if preferred_scope is None:
        return False
    normalized = preferred_scope.lower()
    return any(term in normalized for term in _AGENT_MEMORY_SCOPE_TERMS)


def build_agent_memory_followup_expanded_query(query: str) -> str:
    return f"{query}\n\n{_AGENT_MEMORY_HANDOFF_EXPANSION}"


def apply_followup_fallback_marker(context: HermesMemoryContext) -> HermesMemoryContext:
    payload = context.payload.model_copy(
        update={
            "response_mode": "cautious",
            "prompt_prefix": "Answer using read-only agent-memory handoff fallback evidence.",
            "answer_guidelines": [
                FOLLOWUP_FALLBACK_MARKER,
                *context.payload.answer_guidelines,
                "Do not widen memory mutation or automation authority from this fallback.",
            ],
        }
    )
    prompt_lines = context.prompt_text.splitlines()
    if prompt_lines:
        prompt_lines[0] = "Memory response mode: cautious"
    if len(prompt_lines) >= 2:
        prompt_lines[1] = "Prompt prefix: Answer using read-only agent-memory handoff fallback evidence."
    if FOLLOWUP_FALLBACK_MARKER not in prompt_lines:
        insert_at = 2 if len(prompt_lines) >= 2 else len(prompt_lines)
        prompt_lines.insert(insert_at, FOLLOWUP_FALLBACK_MARKER)
    prompt_text = "\n".join(prompt_lines)
    return context.model_copy(
        update={
            "payload": payload,
            "prompt_text": prompt_text,
            "should_answer_now": True,
            "should_verify_first": False,
            "blocking_steps": [],
        }
    )


def maybe_apply_agent_memory_followup_fallback(
    *,
    db_path,
    query: str,
    preferred_scope: str | None,
    limit: int,
    top_k: int,
    prepare_context,
    current_context: HermesMemoryContext,
    cwd: str | Path | None = None,
) -> FollowupFallbackResult:
    payload = getattr(current_context, "payload", None)
    if payload is None:
        return FollowupFallbackResult(context=current_context, used_fallback=False)
    should_verify_first = bool(getattr(current_context, "should_verify_first", False))
    if payload.top_memory is not None or not should_verify_first:
        return FollowupFallbackResult(context=current_context, used_fallback=False)
    if not looks_like_context_poor_followup(query):
        return FollowupFallbackResult(context=current_context, used_fallback=False)
    if not scope_looks_like_agent_memory(preferred_scope) and not cwd_looks_like_agent_memory(cwd):
        return FollowupFallbackResult(context=current_context, used_fallback=False)

    fallback_packet = retrieve_memory_packet(
        db_path=db_path,
        query=build_agent_memory_followup_expanded_query(query),
        limit=limit,
        preferred_scope=preferred_scope,
        record_retrievals=False,
    )
    fallback_context = prepare_context(fallback_packet)
    if fallback_context.payload.top_memory is None or fallback_context.should_verify_first:
        return FollowupFallbackResult(context=current_context, used_fallback=False)
    return FollowupFallbackResult(
        context=apply_followup_fallback_marker(fallback_context),
        used_fallback=True,
    )
