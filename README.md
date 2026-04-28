# agent-memory

A universal memory and knowledge runtime for AI agents.

agent-memory is an open-source memory layer for multi-agent and multi-harness systems.
It is designed to work with Hermes, Codex-like runtimes, Claude-style runtimes, and any
other agent harness that can emit events and call a retrieval API.

Important repository convention:
- `.dev/` contains AI-authored draft documents, design spikes, research notes, and unapproved plans.
- `docs/` is reserved for human-reviewed, promoted, approved documentation.

## Product thesis

Most agent systems are still weak at memory because they treat memory as one of these:
- raw session logs
- a flat key-value note store
- one-shot RAG over loosely related documents

agent-memory takes a different approach:
- separate memory into working, episodic, semantic, and procedural layers
- preserve provenance and confidence for every memory item
- connect memories into a graph instead of only storing chunks
- combine lexical search, graph traversal, metadata filters, and optional embedding recall
- curate durable knowledge instead of stuffing every transcript into prompt context

## Non-goals

- replacing the host agent runtime
- owning the user's entire wiki lifecycle
- forcing one storage engine or one embedding vendor
- pretending every transcript line is durable knowledge

## Initial scope

1. Event ingestion from external harnesses
2. Memory normalization and storage
3. Retrieval API for prompt-time context
4. Curation lifecycle: raw -> candidate -> approved -> deprecated
5. Graph links between entities, episodes, concepts, tasks, and rules
6. Thin adapters for Hermes and other harnesses

## CLI quick start

Current status: the repository already exposes a Python CLI (`agent-memory`) and now also includes a thin npm launcher scaffold (`bin/agent-memory.js` + `package.json`). The intended dual-distribution posture is:
- npm as the shortest onboarding path for Hermes / Claude Code / Codex style CLI users
- PyPI as the canonical Python runtime package for direct installs, CI, and power users

Chosen distribution names:
- npm package: `@cafitac/agent-memory`
- PyPI package: `cafitac-agent-memory`
- installed CLI command on both surfaces: `agent-memory`

Target npm UX after publish:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

The npm launcher is intentionally thin:
- `bootstrap` maps to the Python CLI command `hermes-bootstrap`
- `doctor` maps to the Python CLI command `hermes-doctor`
- runtime resolution prefers `AGENT_MEMORY_PYTHON_EXECUTABLE`, then `uvx`, then `pipx`

Until the npm package is actually published, the reliable path is the source or Python-install flow below.

Initialize a SQLite memory database. For real use, prefer one global user-level database and let scopes/provenance separate projects:

```bash
uv run agent-memory init ~/.agent-memory/memory.db
```

If you want the shortest real Hermes onboarding path, `hermes-bootstrap` is the primary one-line command. It initializes the database if missing, writes or merges the Hermes hook config, and keeps existing Hermes hooks intact.

```bash
uv run agent-memory hermes-bootstrap
```

If you want a one-line health check for that setup:

```bash
uv run agent-memory hermes-doctor
```

If you want the same flow with explicit paths and budgets, `hermes-install-hook` remains available:

```bash
uv run agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300 --max-alternatives 2 --timeout 12
```

For throwaway experiments, a temp database is fine:

```bash
uv run agent-memory init /tmp/agent-memory.db
```

Scope model:
- `user:default` is the recommended durable default for memories that should travel with the user across projects and harnesses.
- `cwd:<hash>` is used by the Hermes hook when no explicit `--preferred-scope` is provided. It is derived from the runtime `cwd`, but stores a hash instead of the raw folder path so local usernames and repository names do not leak into prompts or examples.
- `project:*` / `workspace:*` scopes are still supported for explicit narrowing, but they are not the primary storage boundary.

Retrieve the raw `MemoryPacket` for a query:

```bash
uv run agent-memory retrieve ~/.agent-memory/memory.db "What does Project X use?" --preferred-scope user:default
```

Render a Hermes-consumable adapter context:

```bash
uv run agent-memory hermes-context ~/.agent-memory/memory.db "What does Project X use?" --preferred-scope user:default --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300 --max-alternatives 2
```

The `hermes-context` output is JSON with:
- `context`: `HermesMemoryContext`, including `prompt_text`, answer flags, blocking steps, and full adapter payload
- `outcome`: `null` unless verification results are supplied

Apply harness-supplied verification results and print a `HermesVerificationOutcome`:

```bash
uv run agent-memory hermes-context ~/.agent-memory/memory.db "What does Project X use?" --verification-results-json '[{"step_action":"cross_check_hidden_alternatives","status":"passed","evidence_summary":"No approved alternative contradicted the primary memory.","target_memory_type":"fact","target_memory_id":1}]'
```

The CLI does not execute verification itself; it only applies result objects supplied by the calling harness.

Generate a mergeable Hermes hook config snippet without modifying any existing config file:

```bash
uv run agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300 --max-alternatives 2 --no-reason-codes
```

The snippet command only prints YAML. It does not read, write, or merge `~/.hermes/config.yaml`.

Install the same hook explicitly into a Hermes config file. For the shortest onboarding flow, prefer `uv run agent-memory hermes-bootstrap` and only drop to `hermes-install-hook` when you want to pin explicit paths or budgets. `hermes-bootstrap` uses the same installer with user-level defaults:

```bash
uv run agent-memory hermes-bootstrap
```

The lower-level explicit form remains available:

```bash
uv run agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300 --max-alternatives 2 --no-reason-codes
```

## Release and distribution notes

Current release surfaces in the repository:
- Python package metadata in `pyproject.toml`
- runtime module version in `src/agent_memory/__init__.py`
- npm launcher metadata in `package.json`
- release metadata checker in `scripts/check_release_metadata.py`
- release-readiness smoke in `scripts/smoke_release_readiness.py`
- GitHub Actions workflows in `.github/workflows/ci.yml` and `.github/workflows/publish.yml`
- release checklist draft in `.dev/release/release-checklist-v0.md`

Release rule: keep the Python package version, npm package version, and module `__version__` identical. CI and publish workflows validate that sync before building artifacts. The Python distribution name and npm distribution name differ intentionally (`cafitac-agent-memory` vs `@cafitac/agent-memory`), but both must point at the same runtime version. The publish workflow now also creates a GitHub Release on tag-driven runs after the package publishes finish. The explicit gate for switching the README to true npm-first quickstart is now documented in `.dev/release/release-checklist-v0.md`.

First publish checklist summary:
- confirm GitHub Actions has `NPM_TOKEN`
- confirm PyPI trusted publishing is enabled for this repository, or set `PYPI_API_TOKEN` in GitHub Actions secrets as the fallback path
- run `uv run python scripts/check_release_metadata.py`
- run `uv run pytest tests/ -q`
- run `uv run python scripts/smoke_release_readiness.py`
- run `uvx --from build python -m build`
- run `npm pack --dry-run`
- push a `vX.Y.Z` tag or trigger `publish.yml` manually

Recommended post-publish smoke on a clean machine/session:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

`hermes-install-hook` is intentionally conservative. It creates a missing config, initializes a missing database, backs up changed existing config files to `*.agent-memory.bak`, and no-ops if the hook command is already installed. `hermes-bootstrap` is just the one-line convenience wrapper over the same behavior with recommended defaults. `hermes-doctor` is the matching read-only validator: it checks whether the DB exists, whether the Hermes config exists, whether the hook command is present, and prints the exact one-line bootstrap command to run when setup is incomplete. If a top-level `hooks:` block already exists, the installer performs a simple structured merge: it preserves existing hook events, appends the agent-memory command to an existing `pre_llm_call:` list, or creates `pre_llm_call:` under `hooks:` when missing. After installing, validate with `hermes hooks list`, then run Hermes with hook consent enabled (for example `hermes --accept-hooks ...`) or approve the hook through Hermes's normal shell-hook consent flow. The merge is text-based and intended for ordinary Hermes YAML config; for unusual YAML anchors or multiline hook definitions, inspect the backup and generated snippet before relying on it.

Use `agent-memory` directly from a Hermes `pre_llm_call` shell hook:

```yaml
hooks:
  pre_llm_call:
    - command: "uv run agent-memory hermes-pre-llm-hook ~/.agent-memory/memory.db --top-k 3 --max-prompt-lines 8 --max-prompt-chars 1200 --max-prompt-tokens 300"
      timeout: 10
```

Hermes passes a JSON hook payload on stdin. `hermes-pre-llm-hook` reads `extra.user_message`, retrieves memory, and prints either:

```json
{"context":"<agent_memory_context>...rendered memory context...</agent_memory_context>"}
```

or `{}` for unsupported/non-`pre_llm_call` payloads. Hermes injects the returned `context` into the current user message as ephemeral context; it is not written back to Hermes session storage.

When `--preferred-scope` is omitted in a Hermes hook, agent-memory derives a privacy-preserving `cwd:<hash>` preferred scope from the hook payload's `cwd`. This makes one global user database behave differently per folder/project without embedding raw local paths in prompt context.

Prompt budgets are renderer-level and do not mutate the full adapter payload. `--max-prompt-tokens` is an approximate local estimate (`ceil(rendered_chars / 4)`) that preserves whole rendered lines; combine it with `--max-prompt-chars` when you want both model-ish and hard character caps.

## Draft design documents

- `.dev/product/thesis-and-scope.md`
- `.dev/architecture/architecture-v0.md`
- `.dev/architecture/graph-vs-hybrid-retrieval.md`
- `.dev/roadmap/roadmap-v0.md`
- `.dev/research/brain-and-llm-memory-notes.md`

## Core idea

RAG is part of the story, but not the whole story.

The long-term goal is not just "retrieve similar text chunks".
The long-term goal is memory that behaves more like a connected system:
- an event can become an episode
- an episode can produce facts
- facts can update entities and concepts
- entities can be linked by relations
- repeated successful behaviors can become procedural memory
- retrieval can walk these links and rank by relevance, recency, confidence, and task fit
