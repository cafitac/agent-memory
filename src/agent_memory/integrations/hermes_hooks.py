from __future__ import annotations

import hashlib
import json
import shutil
import shlex
import sys
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agent_memory.adapters import prepare_hermes_memory_context
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def scope_from_cwd(cwd: str | Path | None) -> str | None:
    """Return a stable, privacy-preserving scope identifier for a working directory.

    The raw path is not embedded in the scope string. This lets a global user-level
    memory database still separate memories by project/worktree path without leaking
    local usernames or repository names through rendered prompts or OSS examples.
    """
    if cwd is None:
        return None
    raw = str(cwd).strip()
    if not raw:
        return None
    resolved = str(Path(raw).expanduser().resolve(strict=False))
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]
    return f"cwd:{digest}"


def resolve_effective_preferred_scope(payload: "HermesShellHookPayload", options: "HermesPreLlmHookOptions") -> str | None:
    return options.preferred_scope or scope_from_cwd(payload.cwd)

class HermesShellHookPayload(BaseModel):
    hook_event_name: str
    tool_name: str | None = None
    tool_input: dict[str, Any] | None = None
    session_id: str = ""
    cwd: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class HermesPreLlmHookOptions(BaseModel):
    db_path: Path
    limit: int = 5
    preferred_scope: str | None = None
    top_k: int = 1
    max_prompt_lines: int | None = None
    max_prompt_chars: int | None = None
    max_prompt_tokens: int | None = None
    max_verification_steps: int | None = None
    max_alternatives: int | None = None
    max_guidelines: int | None = None
    include_reason_codes: bool = True


class HermesHookConfigSnippetOptions(BaseModel):
    db_path: Path
    python_executable: str | None = None
    limit: int = 5
    preferred_scope: str | None = None
    top_k: int = 1
    max_prompt_lines: int | None = None
    max_prompt_chars: int | None = None
    max_prompt_tokens: int | None = None
    max_verification_steps: int | None = None
    max_alternatives: int | None = None
    max_guidelines: int | None = None
    include_reason_codes: bool = True
    timeout: int = 10


class HermesHookInstallOptions(BaseModel):
    config_path: Path
    snippet_options: HermesHookConfigSnippetOptions


class HermesHookInstallResult(BaseModel):
    config_path: str
    changed: bool
    reason: str
    backup_path: str | None = None
    snippet: str
    db_initialized: bool = False


class HermesDoctorResult(BaseModel):
    db_path: str
    config_path: str
    hook_command_marker: str = "hermes-pre-llm-hook"
    db_exists: bool
    config_exists: bool
    hook_installed: bool
    hook_occurrences: int = 0
    status: str
    recommended_command: str
    checks: list[dict[str, Any]]


def build_hermes_hook_config_snippet(options: HermesHookConfigSnippetOptions) -> str:
    db_path = options.db_path.expanduser().resolve(strict=False)
    argv = [
        "agent-memory",
        "hermes-pre-llm-hook",
        str(db_path),
    ]
    if options.python_executable:
        argv = [
            options.python_executable,
            "-m",
            "agent_memory.api.cli",
            "hermes-pre-llm-hook",
            str(db_path),
        ]
    if options.limit != 5:
        argv.extend(["--limit", str(options.limit)])
    if options.preferred_scope:
        argv.extend(["--preferred-scope", options.preferred_scope])
    if options.top_k != 1:
        argv.extend(["--top-k", str(options.top_k)])
    if options.max_prompt_lines is not None:
        argv.extend(["--max-prompt-lines", str(options.max_prompt_lines)])
    if options.max_prompt_chars is not None:
        argv.extend(["--max-prompt-chars", str(options.max_prompt_chars)])
    if options.max_prompt_tokens is not None:
        argv.extend(["--max-prompt-tokens", str(options.max_prompt_tokens)])
    if options.max_verification_steps is not None:
        argv.extend(["--max-verification-steps", str(options.max_verification_steps)])
    if options.max_alternatives is not None:
        argv.extend(["--max-alternatives", str(options.max_alternatives)])
    if options.max_guidelines is not None:
        argv.extend(["--max-guidelines", str(options.max_guidelines)])
    if not options.include_reason_codes:
        argv.append("--no-reason-codes")

    command = " ".join(shlex.quote(part) for part in argv)
    return "\n".join(
        [
            "hooks:",
            "  pre_llm_call:",
            f"    - command: {json.dumps(command)}",
            f"      timeout: {options.timeout}",
            "",
        ]
    )


def _hook_item_lines(snippet: str, indent: str = "    ") -> list[str]:
    lines = [line for line in snippet.splitlines() if line.startswith("    ")]
    if indent == "    ":
        return lines
    return [f"{indent}{line[4:]}" for line in lines]


def _detect_event_item_indent(lines: list[str], event_index: int) -> str:
    end_index = _find_next_hooks_event_or_top_level_line(lines, event_index)
    for index in range(event_index + 1, end_index):
        line = lines[index]
        stripped = line.lstrip()
        if stripped.startswith("- "):
            return line[: len(line) - len(stripped)]
    return "    "


def _find_top_level_hooks_line(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if line.strip() == "hooks:" and not line.startswith(" "):
            return index
    return None


def _find_next_top_level_line(lines: list[str], start_index: int) -> int:
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip() and not lines[index].startswith(" "):
            return index
    return len(lines)


def _find_hooks_event_line(lines: list[str], hooks_index: int, event_name: str) -> int | None:
    hooks_end = _find_next_top_level_line(lines, hooks_index)
    target = f"  {event_name}:"
    for index in range(hooks_index + 1, hooks_end):
        if lines[index].rstrip() == target:
            return index
    return None


def _find_next_hooks_event_or_top_level_line(lines: list[str], start_index: int) -> int:
    for index in range(start_index + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if not line.startswith(" "):
            return index
        if line.startswith("  ") and not line.startswith("    ") and not line.startswith("  -"):
            return index
    return len(lines)


def _merge_hook_snippet_into_config(current: str, snippet: str) -> str:
    lines = current.splitlines()
    snippet_lines = snippet.splitlines()
    hooks_index = _find_top_level_hooks_line(lines)
    if hooks_index is None:
        separator = [""] if lines and lines[-1].strip() else []
        return "\n".join([*lines, *separator, "# agent-memory Hermes hook", *snippet_lines, ""])

    event_index = _find_hooks_event_line(lines, hooks_index, "pre_llm_call")
    if event_index is None:
        insert_index = _find_next_top_level_line(lines, hooks_index)
        hook_item_lines = _hook_item_lines(snippet)
        merged_lines = [*lines[:insert_index], "  pre_llm_call:", *hook_item_lines, *lines[insert_index:]]
    else:
        insert_index = _find_next_hooks_event_or_top_level_line(lines, event_index)
        hook_item_lines = _hook_item_lines(snippet, indent=_detect_event_item_indent(lines, event_index))
        merged_lines = [*lines[:insert_index], *hook_item_lines, *lines[insert_index:]]
    return "\n".join([*merged_lines, ""])


def _replace_existing_hook_snippet_in_config(current: str, snippet: str, command_marker: str) -> str | None:
    lines = current.splitlines()
    hooks_index = _find_top_level_hooks_line(lines)
    if hooks_index is None:
        return None
    event_index = _find_hooks_event_line(lines, hooks_index, "pre_llm_call")
    if event_index is None:
        return None
    event_end = _find_next_hooks_event_or_top_level_line(lines, event_index)
    for index in range(event_index + 1, event_end):
        line = lines[index]
        if command_marker not in line:
            continue
        stripped = line.lstrip()
        item_indent = line[: len(line) - len(stripped)] if stripped.startswith("- ") else _detect_event_item_indent(lines, event_index)
        item_end = event_end
        for next_index in range(index + 1, event_end):
            next_line = lines[next_index]
            if next_line.startswith(f"{item_indent}- "):
                item_end = next_index
                break
        hook_item_lines = _hook_item_lines(snippet, indent=item_indent)
        merged_lines = [*lines[:index], *hook_item_lines, *lines[item_end:]]
        return "\n".join([*merged_lines, ""])
    return None


def install_hermes_hook_config(options: HermesHookInstallOptions) -> HermesHookInstallResult:
    config_path = options.config_path.expanduser().resolve(strict=False)
    snippet = build_hermes_hook_config_snippet(options.snippet_options)
    command_marker = "hermes-pre-llm-hook"
    db_path = options.snippet_options.db_path.expanduser().resolve(strict=False)
    db_initialized = False

    if not db_path.exists():
        initialize_database(db_path)
        db_initialized = True

    if config_path.exists():
        current = config_path.read_text()
        if command_marker in current:
            next_text = _replace_existing_hook_snippet_in_config(current, snippet, command_marker)
            if next_text is None or next_text == current or next_text == f"{current.rstrip()}\n":
                return HermesHookInstallResult(
                    config_path=str(config_path),
                    changed=False,
                    reason="already_installed",
                    backup_path=None,
                    snippet=snippet,
                    db_initialized=db_initialized,
                )
            backup_path = config_path.with_suffix(config_path.suffix + ".agent-memory.bak")
            shutil.copy2(config_path, backup_path)
            config_path.write_text(next_text)
            return HermesHookInstallResult(
                config_path=str(config_path),
                changed=True,
                reason="updated_existing_hook",
                backup_path=str(backup_path),
                snippet=snippet,
                db_initialized=db_initialized,
            )
        backup_path = config_path.with_suffix(config_path.suffix + ".agent-memory.bak")
        shutil.copy2(config_path, backup_path)
        next_text = _merge_hook_snippet_into_config(current, snippet)
        reason = "merged_existing_hooks_block" if _find_top_level_hooks_line(current.splitlines()) is not None else "appended_hooks_block"
        config_path.write_text(next_text)
        return HermesHookInstallResult(
            config_path=str(config_path),
            changed=True,
            reason=reason,
            backup_path=str(backup_path),
            snippet=snippet,
            db_initialized=db_initialized,
        )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(snippet)
    return HermesHookInstallResult(
        config_path=str(config_path),
        changed=True,
        reason="created_config",
        backup_path=None,
        snippet=snippet,
        db_initialized=db_initialized,
    )


def diagnose_hermes_hook_setup(options: HermesHookInstallOptions) -> HermesDoctorResult:
    db_path = options.snippet_options.db_path.expanduser().resolve(strict=False)
    config_path = options.config_path.expanduser().resolve(strict=False)
    command_marker = "hermes-pre-llm-hook"
    config_text = config_path.read_text() if config_path.exists() else ""
    hook_occurrences = config_text.count(command_marker)
    db_exists = db_path.exists()
    config_exists = config_path.exists()
    hook_installed = hook_occurrences > 0
    checks = [
        {
            "name": "database_exists",
            "ok": db_exists,
            "detail": str(db_path),
        },
        {
            "name": "config_exists",
            "ok": config_exists,
            "detail": str(config_path),
        },
        {
            "name": "hook_installed",
            "ok": hook_installed,
            "detail": f"occurrences={hook_occurrences}",
        },
    ]
    status = "ok" if all(check["ok"] for check in checks) else "needs_setup"
    recommended_command = f"agent-memory bootstrap {shlex.quote(str(db_path))} --config-path {shlex.quote(str(config_path))}"
    return HermesDoctorResult(
        db_path=str(db_path),
        config_path=str(config_path),
        db_exists=db_exists,
        config_exists=config_exists,
        hook_installed=hook_installed,
        hook_occurrences=hook_occurrences,
        status=status,
        recommended_command=recommended_command,
        checks=checks,
    )


def load_hermes_shell_hook_payload(stdin_text: str | None = None) -> HermesShellHookPayload:
    raw = sys.stdin.read() if stdin_text is None else stdin_text
    data = json.loads(raw or "{}")
    return HermesShellHookPayload.model_validate(data)


def build_pre_llm_hook_context(
    payload: HermesShellHookPayload,
    options: HermesPreLlmHookOptions,
) -> dict[str, str]:
    if payload.hook_event_name != "pre_llm_call":
        return {}

    user_message = payload.extra.get("user_message")
    if not isinstance(user_message, str) or not user_message.strip():
        return {}

    effective_preferred_scope = resolve_effective_preferred_scope(payload, options)
    try:
        packet = retrieve_memory_packet(
            db_path=options.db_path,
            query=user_message,
            limit=options.limit,
            preferred_scope=effective_preferred_scope,
        )
        context = prepare_hermes_memory_context(
            packet,
            top_k=options.top_k,
            max_prompt_lines=options.max_prompt_lines,
            max_prompt_chars=options.max_prompt_chars,
            max_prompt_tokens=options.max_prompt_tokens,
            max_verification_steps=options.max_verification_steps,
            max_alternatives=options.max_alternatives,
            max_guidelines=options.max_guidelines,
            include_reason_codes=options.include_reason_codes,
        )
    except Exception:
        return {}

    if not context.prompt_text.strip():
        return {}

    return {
        "context": "\n".join(
            [
                "<agent_memory_context>",
                context.prompt_text,
                "</agent_memory_context>",
            ]
        )
    }
