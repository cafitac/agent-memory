"""Hermes plugin entry point for agent-memory.

This repository can be installed directly with `hermes plugins install`.
The plugin reuses the same local-first pre-LLM hook implementation as the
`agent-memory bootstrap` shell-hook path, but avoids editing Hermes config when
users choose the plugin integration surface.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

_PLUGIN_DIR = Path(__file__).resolve().parent
_SRC_DIR = _PLUGIN_DIR / "src"
if _SRC_DIR.exists() and str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def _default_db_path() -> Path:
    configured = os.environ.get("AGENT_MEMORY_DB_PATH", "").strip()
    if configured:
        return Path(configured).expanduser().resolve(strict=False)
    return Path.home() / ".agent-memory" / "memory.db"


def _hook_options():
    from agent_memory.integrations.hermes_hooks import HermesPreLlmHookOptions
    from agent_memory.storage.sqlite import initialize_database

    db_path = _default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    initialize_database(db_path)
    return HermesPreLlmHookOptions(
        db_path=db_path,
        limit=int(os.environ.get("AGENT_MEMORY_HERMES_LIMIT", "5")),
        preferred_scope=os.environ.get("AGENT_MEMORY_HERMES_SCOPE") or None,
        top_k=int(os.environ.get("AGENT_MEMORY_HERMES_TOP_K", "1")),
        max_prompt_lines=_optional_int_env("AGENT_MEMORY_HERMES_MAX_PROMPT_LINES"),
        max_prompt_chars=_optional_int_env("AGENT_MEMORY_HERMES_MAX_PROMPT_CHARS"),
        max_prompt_tokens=_optional_int_env("AGENT_MEMORY_HERMES_MAX_PROMPT_TOKENS"),
        max_verification_steps=_optional_int_env("AGENT_MEMORY_HERMES_MAX_VERIFICATION_STEPS"),
        max_alternatives=_optional_int_env("AGENT_MEMORY_HERMES_MAX_ALTERNATIVES"),
        max_guidelines=_optional_int_env("AGENT_MEMORY_HERMES_MAX_GUIDELINES"),
        include_reason_codes=_bool_env("AGENT_MEMORY_HERMES_REASON_CODES", default=True),
        record_trace=_bool_env("AGENT_MEMORY_HERMES_RECORD_TRACE", default=True),
        followup_fallback=_bool_env("AGENT_MEMORY_HERMES_FOLLOWUP_FALLBACK", default=False),
    )


def _optional_int_env(name: str) -> int | None:
    value = os.environ.get(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _bool_env(name: str, *, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value not in {"0", "false", "no", "off"}


def _pre_llm_call(
    session_id: str = "",
    user_message: str | None = None,
    conversation_history: list[dict[str, Any]] | None = None,
    is_first_turn: bool = False,
    model: str | None = None,
    platform: str | None = None,
    cwd: str | None = None,
    **kwargs: Any,
) -> dict[str, str] | None:
    if not isinstance(user_message, str) or not user_message.strip():
        return None
    try:
        from agent_memory.integrations.hermes_hooks import HermesShellHookPayload, build_pre_llm_hook_context

        payload = HermesShellHookPayload(
            hook_event_name="pre_llm_call",
            session_id=session_id or "",
            cwd=cwd or os.getcwd(),
            extra={
                "user_message": user_message,
                "conversation_history": conversation_history or [],
                "is_first_turn": is_first_turn,
                "model": model or "",
                "platform": platform or "",
                **kwargs,
            },
        )
        context = build_pre_llm_hook_context(payload, _hook_options())
    except Exception:
        return None
    return context or None


def register(ctx: Any) -> None:
    """Register the agent-memory pre-LLM hook with Hermes.

    Hermes plugin hooks are fail-soft: if registration or a later callback fails,
    Hermes should continue the user turn without memory context rather than crash.
    """
    try:
        ctx.register_hook("pre_llm_call", _pre_llm_call)
    except Exception:
        return

    try:
        skill_doc = _PLUGIN_DIR / "docs" / "first-run-memory-layer.md"
        if skill_doc.exists() and hasattr(ctx, "register_skill"):
            ctx.register_skill("agent-memory", skill_doc)
    except Exception:
        pass
