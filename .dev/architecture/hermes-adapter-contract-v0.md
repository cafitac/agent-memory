# Hermes Adapter Contract v0

Status: AI draft (`.dev/`)

## Goal

Define the thinnest useful contract for consuming `agent-memory` retrieval output from Hermes.

The adapter should not re-rank memory. It should translate an already-built `MemoryPacket` into a Hermes-consumable decision payload for answer planning.

## Current implementation surface

Code:
- `src/agent_memory/adapters/hermes.py`
- `src/agent_memory/integrations/hermes_hooks.py`
- `src/agent_memory/api/cli.py` (`agent-memory hermes-context`, `agent-memory hermes-pre-llm-hook`, `agent-memory hermes-hook-config-snippet`, `agent-memory hermes-install-hook`)

Primary entrypoints:
- `build_hermes_adapter_payload(packet: MemoryPacket, top_k: int = 1) -> HermesAdapterPayload`
- `prepare_hermes_memory_context(packet: MemoryPacket, top_k: int = 1, *, max_prompt_lines: int | None = None, max_prompt_chars: int | None = None, max_prompt_tokens: int | None = None, max_verification_steps: int | None = None, max_alternatives: int | None = None, max_guidelines: int | None = None, include_reason_codes: bool = True) -> HermesMemoryContext`
- `apply_hermes_verification_results(context: HermesMemoryContext, results: list[HermesVerificationResult]) -> HermesVerificationOutcome`
- `render_hermes_prompt_lines(payload: HermesAdapterPayload, *, max_prompt_lines: int | None = None, max_prompt_chars: int | None = None, max_prompt_tokens: int | None = None, max_verification_steps: int | None = None, max_alternatives: int | None = None, max_guidelines: int | None = None, include_reason_codes: bool = True) -> list[str]`
- `render_hermes_prompt_text(payload: HermesAdapterPayload, *, max_prompt_lines: int | None = None, max_prompt_chars: int | None = None, max_prompt_tokens: int | None = None, max_verification_steps: int | None = None, max_alternatives: int | None = None, max_guidelines: int | None = None, include_reason_codes: bool = True) -> str`
- `build_pre_llm_hook_context(payload: HermesShellHookPayload, options: HermesPreLlmHookOptions) -> dict[str, str]`
- `build_hermes_hook_config_snippet(options: HermesHookConfigSnippetOptions) -> str`
- `install_hermes_hook_config(options: HermesHookInstallOptions) -> HermesHookInstallResult`

## Contract objects

### HermesTopMemory

Fields:
- `memory_type`: `fact | procedure | episode`
- `memory_id`: integer ID of the memory
- `label`: human-readable label
- `trust_band`: `high | medium | low`
- `has_hidden_alternatives`: whether hidden disputed/deprecated alternatives exist

Purpose:
- Give Hermes a compact memory target without shipping the full retrieval packet into every downstream branch.

### HermesAdapterPayload

Fields:
- `query`
- `response_mode`: `direct | cautious | verify_first`
- `prompt_prefix`
- `pre_answer_checks`: backward-compatible ordered string actions Hermes can map to runtime checks
- `verification_plan`: typed `VerificationPlan` with executable/loggable verification steps
- `answer_guidelines`: ordered natural-language guidance for prompt injection
- `policy_reason_codes`: stable machine-readable cause list derived from `decision_summary.reason_codes`
- `top_memory`: optional `HermesTopMemory`
- `alternative_memories`: ordered list of additional ranked memories, derived from retrieval trace order after the top memory

Purpose:
- Bridge `MemoryPacket` to Hermes answer orchestration.
- Preserve top-N memory context without requiring Hermes to understand full retrieval trace semantics.

### HermesMemoryContext

Fields:
- `payload`: full `HermesAdapterPayload`
- `prompt_text`: rendered prompt text from the payload
- `should_answer_now`: `true` when no blocking verification path is required
- `should_verify_first`: `true` when `response_mode=verify_first` or blocking verification steps exist
- `blocking_steps`: filtered `VerificationStep` list where `blocking=true`

Purpose:
- Give Hermes and similar harnesses a one-call integration surface for answer orchestration.
- Keep the harness from re-deriving execution decisions from low-level payload fields.

### HermesVerificationResult

Fields:
- `step_action`: `gather_more_evidence | cross_check_hidden_alternatives | corroborate_before_answer`
- `status`: `passed | failed | skipped | unavailable`
- `evidence_summary`: human-readable summary of what the harness found or why verification could not run
- `target_memory_type`: optional `fact | procedure | episode`
- `target_memory_id`: optional integer memory ID

Purpose:
- Let Hermes or another harness report verification execution outcomes back into the adapter loop.
- Keep result identity small and stable: action + optional target memory reference.

### HermesVerificationOutcome

Fields:
- `context`: original `HermesMemoryContext`
- `results`: ordered `HermesVerificationResult` list supplied by the harness
- `prompt_text`: original context prompt plus rendered verification-result lines
- `should_answer_now`: `true` when all blocking steps have matching `passed` results
- `should_verify_first`: `true` when any blocking step is missing or not `passed`
- `response_mode_after_verification`: `direct | cautious | verify_first`
- `unresolved_blocking_steps`: blocking steps without a matching `passed` result

Purpose:
- Turn verification execution results into a concrete next-step answer decision.
- Preserve the original context while adding result-aware prompt text for final answer planning.

## Mapping from MemoryPacket

Source layer:
- `packet.decision_summary`
- `packet.policy_hints`
- `packet.working_hints`
- `packet.retrieval_trace`
- `packet.trust_summaries`
- `packet.verification_plan`

Current logic:
- `decision_summary` still determines answer mode and answer policy.
- `retrieval_trace` + `trust_summaries` determine the ordered `top_memory` + `alternative_memories` list.
- `verification_plan` turns mandatory cross-check/corroboration requirements into typed steps while preserving `pre_answer_checks` for backward compatibility.
- `top_k` controls how many ranked memories are exported.
  - `top_k=1` means top memory only.
  - `top_k=3` means top memory plus up to two alternatives.

### If no `decision_summary`
Return safe fallback:
- `response_mode = verify_first`
- `pre_answer_checks = ["gather_more_evidence"]`
- `verification_plan.required = true`
- `verification_plan.steps = [gather_more_evidence]`
- `top_memory = None`
- `alternative_memories = []`
- answer should defer, clarify, or gather evidence

### `response_mode = direct`
Conditions:
- high-confidence path
- no explicit uncertainty handling needed
- no mandatory cross-check requirement

Current prompt prefix:
- `Answer directly using the top-ranked memory.`

### `response_mode = cautious`
Conditions:
- typically medium trust
- uncertainty should be surfaced
- no mandatory cross-check gate

Current prompt prefix:
- `Answer using the top-ranked memory, but explicitly mention uncertainty.`

### `response_mode = verify_first`
Conditions:
- hidden alternatives require cross-check, and/or
- low trust requires corroboration before definitive answer

Current prompt prefix:
- `Do not answer definitively yet; verify hidden alternatives or corroborating evidence first.`

## Pre-answer checks vocabulary v0

Current strings:
- `gather_more_evidence`
- `cross_check_hidden_alternatives`
- `corroborate_before_answer`

These are intentionally adapter-facing action tags, not user-facing copy.

## Verification plan v0

Core objects:
- `VerificationPlan`
  - `required`: whether at least one blocking verification step exists
  - `fallback_answer_mode`: answer mode to use if the harness cannot execute the plan
  - `steps`: ordered `VerificationStep` list
- `VerificationStep`
  - `action`: `gather_more_evidence | cross_check_hidden_alternatives | corroborate_before_answer`
  - `severity`: `low | medium | high`
  - `target_memory_type`, `target_memory_id`, `target_label`: optional target memory reference
  - `reason_code`: optional stable reason code
  - `blocking`: whether this must run before a definitive answer
  - `compare_against_memory_ids`: ranked same-type alternatives when available
  - `instruction`: human-readable execution guidance

Current generation rules:
- no retrieved decision: emit blocking `gather_more_evidence` in the Hermes fallback payload
- hidden alternatives / cross-check required: emit blocking `cross_check_hidden_alternatives`
- low trust / avoid definitive required: emit blocking `corroborate_before_answer`
- direct/cautious paths without blocking checks: emit an empty non-required plan

## Answer guideline behavior v0

Always include:
- primary memory selection statement

Conditionally include:
- uncertainty mention
- hidden alternative surfacing
- avoid-definitive instruction
- direct-answer allowance

## Prompt renderer behavior v0

The renderer emits stable line-oriented output in this default unbudgeted order:
1. `Memory response mode: ...`
2. `Prompt prefix: ...`
3. `Top memory: ...`
4. zero or more `Pre-answer check: ...`
5. zero or more `Verification step: ...`
6. zero or more `Alternative memory: ...`
7. zero or more `Guideline: ...`
8. `Reason codes: ...`

This default ordering is intentional:
- high-level answer mode first
- backward-compatible pre-answer tags before typed verification details
- extra ranked context before answer instructions
- reason codes last for logging/debug attachment

Budget options:
- `max_prompt_lines`: hard cap on rendered prompt line count. The full `HermesAdapterPayload` is not mutated.
- `max_prompt_chars`: hard cap on rendered prompt character count after line/item budgeting. It preserves whole lines and drops later lines rather than truncating a line mid-string. The full `HermesAdapterPayload` is not mutated.
- `max_prompt_tokens`: approximate cap on rendered prompt tokens after line/item budgeting, using `ceil(len(rendered_text) / 4)`. It preserves whole lines and drops later lines. The full `HermesAdapterPayload` is not mutated.
- `max_verification_steps`: cap rendered typed verification steps only.
- `max_alternatives`: cap rendered alternative memories only.
- `max_guidelines`: cap rendered answer guidelines only.
- `include_reason_codes`: include or suppress final reason-code line.

When `max_prompt_lines` is set, typed `Verification step` lines are rendered before backward-compatible `Pre-answer check` lines so blocking verification instructions are not starved by duplicate legacy tags. The lower-level payload still preserves the original `pre_answer_checks` and full `verification_plan`.

## Verification result application v0

`apply_hermes_verification_results(context, results)` does not execute verification itself. It only evaluates harness-supplied results against `context.blocking_steps`.

Matching rule:
- A result matches a blocking step by `(action, target_memory_type, target_memory_id)`.
- A blocking step is resolved only when the matching result has `status=passed`.
- Missing, `failed`, `skipped`, and `unavailable` results keep that step unresolved.

Decision rule:
- If any blocking step remains unresolved:
  - `should_verify_first = true`
  - `should_answer_now = false`
  - `response_mode_after_verification = verify_first`
- If all blocking steps are resolved:
  - `should_verify_first = false`
  - `should_answer_now = true`
  - existing `direct` and `cautious` modes are preserved
  - existing `verify_first` mode is downgraded to `cautious`, not `direct`, because verification cleared the block but the underlying memory may still be low-trust or conflict-prone

Prompt behavior:
- The outcome prompt appends ordered `Verification result: ...` lines to the original context prompt.
- Full original `context.payload` and `context.blocking_steps` remain available for logging and auditing.

## Reason code flow

Current reason codes come from core retrieval policy generation:
- `top_ranked_memory`
- `no_hidden_alternatives_detected`
- `hidden_alternatives_present`
- `medium_uncertainty`
- `low_trust_requires_corroboration`

Adapter behavior:
- preserve ordering
- deduplicated upstream in `decision_summary`
- treat as stable machine-readable control signals

## Intended Hermes consumption pattern

Lowest-friction path:

1. Call `prepare_hermes_memory_context(packet, top_k=...)`
2. If `context.should_verify_first`, execute or surface `context.blocking_steps`
3. If verification was executed, call `apply_hermes_verification_results(context, results)`
4. Inject `outcome.prompt_text` when an outcome exists; otherwise inject `context.prompt_text`
5. Log `context.payload.policy_reason_codes`, `context.blocking_steps[*].reason_code`, and verification result statuses

Lower-level path:

1. Read `response_mode`
2. Read `verification_plan`; execute blocking steps when the harness supports them
3. Fall back to `pre_answer_checks` string tags for older integrations
4. Inject `prompt_prefix`
5. Inject `alternative_memories` if a branch needs extra ranked context
6. Inject `answer_guidelines`
7. Log `policy_reason_codes` and `verification_plan.steps[*].reason_code`
8. Optionally keep full `MemoryPacket` only for debug/explanations

### Example runtime mapping

- `direct`
  - answer now
  - no extra caution wrapper required
  - alternatives are optional extra context, not gating context

- `cautious`
  - answer now
  - include uncertainty phrasing
  - alternatives can be surfaced if helpful but are not mandatory

- `verify_first`
  - execute `verification_plan.steps` when possible
  - call `apply_hermes_verification_results` with harness-supplied results
  - if all blocking steps pass, continue with `response_mode_after_verification=cautious`
  - if execution is unavailable or a blocking result is not `passed`, keep `verify_first` and answer only with explicit non-definitive wording
  - consume `alternative_memories` preferentially when available

## Scope model v0

The recommended OSS/default deployment is global-first and user-owned:

- Store one durable SQLite database in a user-level location such as `~/.agent-memory/memory.db`.
- Use `user:default` for memories that should follow the user across projects and harnesses.
- Use `cwd:<hash>` for path-sensitive retrieval when a harness supplies a working directory. The hash is derived from the resolved path, but the raw path is not stored in the scope string or rendered prompt context.
- Keep `project:*` and `workspace:*` as explicit narrowing scopes for callers that already have stable non-private project identifiers.

This mirrors the agent-learner global-first direction: store globally, filter locally, and keep filesystem path as provenance or a privacy-preserving scope signal rather than making every project directory its own isolated memory store.

## CLI demo command v0

`agent-memory hermes-context` retrieves a `MemoryPacket`, prepares a `HermesMemoryContext`, and optionally applies harness-supplied verification results.

Arguments:
- positional `db_path`
- positional `query`
- `--limit`: retrieval limit passed to `retrieve_memory_packet`
- `--preferred-scope`: explicit scope hint passed to retrieval. If omitted in the Hermes hook path, the hook derives a privacy-preserving `cwd:<hash>` scope from the runtime payload `cwd`.
- `--top-k`: number of ranked memories exported into the adapter payload
- `--max-prompt-lines`: prompt line cap
- `--max-prompt-chars`: prompt character cap; preserves whole rendered lines
- `--max-prompt-tokens`: approximate prompt token cap; preserves whole rendered lines
- `--max-verification-steps`: rendered verification step cap
- `--max-alternatives`: rendered alternative memory cap
- `--max-guidelines`: rendered guideline cap
- `--no-reason-codes`: suppress rendered reason-code line
- `--verification-results-json`: JSON array of `HermesVerificationResult` objects to apply

Output shape:

```json
{
  "context": { "...": "HermesMemoryContext" },
  "outcome": null
}
```

When `--verification-results-json` is supplied, `outcome` is a `HermesVerificationOutcome` JSON object instead of `null`.

The CLI is intentionally a demo/integration surface, not a verifier. It does not execute lookup tools, inspect external sources, or mutate memories while applying verification results.

## Hermes pre_llm_call shell hook path v0

Hermes shell hooks use this wire protocol:

- stdin: JSON object with `hook_event_name`, `tool_name`, `tool_input`, `session_id`, `cwd`, and event-specific `extra`
- for `pre_llm_call`, the user prompt is available as `extra.user_message`
- stdout: JSON object with a `context` string, or `{}`/empty output for no-op

`agent-memory hermes-pre-llm-hook DB_PATH` implements the lowest-risk direct hook path:

1. Read the Hermes shell hook JSON payload from stdin
2. No-op unless `hook_event_name == "pre_llm_call"`
3. Read the query from `extra.user_message`
4. Resolve retrieval scope: use explicit `--preferred-scope` when supplied; otherwise derive `cwd:<sha256-prefix>` from the hook payload `cwd` so a global user database can still behave differently per folder without rendering raw local paths
5. Retrieve a `MemoryPacket` from `DB_PATH`
6. Prepare a `HermesMemoryContext`
7. Print `{"context":"<agent_memory_context>...prompt_text...</agent_memory_context>"}`

Supported options mirror the renderer/retrieval subset:
- `--limit`
- `--preferred-scope`
- `--top-k`
- `--max-prompt-lines`
- `--max-prompt-chars`
- `--max-prompt-tokens`
- `--max-verification-steps`
- `--max-alternatives`
- `--max-guidelines`
- `--no-reason-codes`

Example Hermes config snippet:

Generate this snippet without touching existing Hermes config:

```bash
agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db \
  --top-k 3 \
  --max-prompt-lines 8 \
  --max-prompt-chars 1200 \
  --max-prompt-tokens 300 \
  --max-alternatives 2
```

Example output:

```yaml
hooks:
  pre_llm_call:
    - command: "uv run agent-memory hermes-pre-llm-hook ~/.agent-memory/memory.db --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300"
      timeout: 10
```

`agent-memory hermes-hook-config-snippet` is intentionally print-only. It does not read, merge, or write `~/.hermes/config.yaml`. The generated command defaults to the current Python executable plus `-m agent_memory.api.cli hermes-pre-llm-hook`, and supports `--python-executable` when the caller wants to pin a different interpreter or wrapper.

`agent-memory hermes-bootstrap` is the highest-convenience entrypoint for end users who want a true one-line setup. With no positional args it targets `~/.agent-memory/memory.db` and `~/.hermes/config.yaml`, initializes the database if missing, and installs the recommended pre-LLM hook budgets (`top_k=3`, `max_prompt_lines=8`, `max_prompt_chars=1200`, `max_prompt_tokens=300`, `max_alternatives=2`, `timeout=12`).

Planned distribution posture:
- Publish the Python package to PyPI as the canonical runtime and library distribution.
- Publish an npm package as a thin onboarding/launcher surface for agent-tooling users who expect `npm install -g` flows.
- The repository now includes an npm launcher scaffold (`package.json` + `bin/agent-memory.js`) that maps `bootstrap` -> `hermes-bootstrap` and `doctor` -> `hermes-doctor`.
- Chosen distribution names are PyPI `cafitac-agent-memory` and npm `@cafitac/agent-memory`, while the installed CLI command stays `agent-memory` on both surfaces.
- Launcher resolution order is: `AGENT_MEMORY_PYTHON_EXECUTABLE` override first, then `uvx --from cafitac-agent-memory agent-memory ...`, then `pipx run cafitac-agent-memory ...`.
- Release hygiene rule: `pyproject.toml`, `package.json`, and `src/agent_memory/__init__.py` must keep the same version string. `scripts/check_release_metadata.py` and `tests/test_release_metadata.py` enforce that contract.
- Release-readiness gate: run a real local smoke over both surfaces with `scripts/smoke_release_readiness.py`; CI and publish workflows should run that script before packaging/publishing.
- GitHub Actions should keep two surfaces: a CI workflow that runs tests, release-metadata validation, release-readiness smoke, Python build, and `npm pack --dry-run`; and a publish workflow that gates PyPI/npm release on the same verification steps.
- The human checklist for flipping the README to npm-first lives in `.dev/release/release-checklist-v0.md`.
- Once the npm launcher is actually published and smoke-tested end-to-end, the README can become npm-first (`npm install -g @cafitac/agent-memory`, then `agent-memory bootstrap` / `agent-memory doctor`) while still keeping direct Python install alternatives for CI and power users.
- Do not advertise npm commands as already available to end users until that publish + smoke-test gate is complete.

`agent-memory hermes-doctor` is the matching read-only validation command. With the same default paths, it reports whether the database exists, whether the Hermes config exists, whether the `hermes-pre-llm-hook` command is present, and prints the exact one-line `hermes-bootstrap` remediation command when setup is incomplete.

`agent-memory hermes-install-hook` is the explicit lower-level installer for real Hermes use when callers want to pin DB/config paths or override those defaults. It accepts the same snippet-generation options plus `--config-path` (default `~/.hermes/config.yaml`) and returns a JSON `HermesHookInstallResult`:

```json
{
  "config_path": "/Users/example/.hermes/config.yaml",
  "changed": true,
  "reason": "created_config",
  "backup_path": null,
  "snippet": "hooks:\n  pre_llm_call:\n    - command: ...",
  "db_initialized": true
}
```

Installer safety rules:
- If the target database is missing, initialize it before writing or merging hook config. This makes `hermes-bootstrap` the shortest fresh-user one-line path, while `hermes-install-hook` remains the explicit lower-level installer.
- If the config file is missing, create it with the generated hook snippet.
- If the config exists and already contains `hermes-pre-llm-hook`, no-op with `reason=already_installed`.
- If the config exists and has no top-level `hooks:` block, create a `*.agent-memory.bak` backup and append a new hook block with `reason=appended_hooks_block`.
- If the config already contains a top-level `hooks:` block, create a `*.agent-memory.bak` backup and perform a simple structured merge with `reason=merged_existing_hooks_block`.
- Existing hook events such as `on_session_end:` are preserved. Existing `pre_llm_call:` hooks are preserved and the agent-memory hook item is appended to that list; if `pre_llm_call:` is missing, it is created under `hooks:`.
- The merge is text-based and targets ordinary Hermes YAML config. Complex YAML anchors, unusual indentation, or multiline hook definitions should be inspected manually against the backup and returned snippet.
- After installation, validate with `hermes hooks list` / `hermes hooks test pre_llm_call`; run with `--accept-hooks` or use Hermes's consent flow before relying on the hook in live sessions.

Runtime behavior:
- Hermes injects the returned `context` into the current turn's user message, not the system prompt.
- The injected context is ephemeral and is not persisted into the Hermes session DB.
- The hook path retrieves and renders memory context only; it does not execute verification steps or mutate memory.
- If `context.should_verify_first` is true, the hook can still inject the verify-first prompt text, but actual verification remains a harness/tool responsibility.

## Non-goals

This adapter does not yet:
- rewrite Hermes core prompts automatically
- execute verification plan steps itself
- expose retrieval trace semantic compression beyond renderer-level line/item/character/token budgets
- install or mutate the user's Hermes `config.yaml` without an explicit `hermes-install-hook` invocation

## Likely next steps

1. Validate structured merge against isolated Hermes homes that resemble real user configs with multiple hook events
2. Add top-N policy hints or alternative-specific reason codes
3. Consider moving verification result models into core if non-Hermes adapters need the same contract
4. Consider a YAML parser dependency if real-world configs need anchor/comment-preserving merges beyond the current text-based ordinary-config path
