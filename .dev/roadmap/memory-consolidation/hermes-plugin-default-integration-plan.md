# Hermes plugin/default integration completion plan

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 KST

## Goal

Make `agent-memory` usable as a Hermes default plugin path, not only as a shell-hook/bootstrap integration. A Hermes user should be able to install/enable the repository as a Hermes plugin and get pre-LLM memory context injection with the same local-first database, bounded prompt rendering, and fail-soft behavior as the existing `agent-memory bootstrap` hook path.

## Current audit

- Existing default install is npm-first: `npm install -g @cafitac/agent-memory`, then `agent-memory bootstrap`, then `agent-memory doctor`.
- Existing Hermes integration is shell-hook based via `hooks.pre_llm_call` in `~/.hermes/config.yaml`.
- No repo-level `plugin.yaml` or Hermes `register(ctx)` entry point currently exists, so `hermes plugins install cafitac/agent-memory --enable` cannot be the direct/default Hermes integration surface.
- The existing Python hook implementation already has the desired runtime behavior in `agent_memory.integrations.hermes_hooks.build_pre_llm_hook_context`.

## Completion slice

1. Add a repo-level Hermes plugin manifest and `register(ctx)` entry point.
2. Register a `pre_llm_call` hook that adapts Hermes plugin callback args to the existing `HermesShellHookPayload` and `HermesPreLlmHookOptions`.
3. Use `AGENT_MEMORY_DB_PATH` when set; otherwise default to `~/.agent-memory/memory.db`.
4. Initialize the local DB lazily and fail soft: plugin registration/runtime errors must not break Hermes turns.
5. Keep context injected into user-message hook return (`{"context": ...}`), preserving Hermes prompt-cache behavior.
6. Document plugin-first Hermes install while preserving npm/bootstrap as the agent-agnostic path.
7. Verify with focused plugin tests, existing Hermes adapter/npm/release tests, full suite, and release smoke.

## Non-goals / safety boundary

- Do not enable broad ordinary-turn auto-approval or unattended/default memory mutation.
- Do not load/install launchd/cron or any OS background scheduler from the agent.
- Do not move durable plugin behavior into unrelated `.claude`/project control files.
- Do not require API keys or hosted services.
