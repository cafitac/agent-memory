# agent-memory

[![CI](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/@cafitac/agent-memory.svg)](https://www.npmjs.com/package/@cafitac/agent-memory)
[![PyPI](https://img.shields.io/pypi/v/cafitac-agent-memory.svg)](https://pypi.org/project/cafitac-agent-memory/)
[![Python](https://img.shields.io/pypi/pyversions/cafitac-agent-memory.svg)](https://pypi.org/project/cafitac-agent-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local-first memory for AI agents.

agent-memory gives Hermes, Codex-style CLIs, Claude-style CLIs, and custom agent harnesses a shared SQLite memory runtime with curation, provenance, retrieval, prompt rendering, and regression evaluation.

It is intentionally small and local-first: your memory database lives on your machine unless you choose to sync or copy it elsewhere.

## Why use it?

Most agent memory systems end up as raw logs, ad-hoc notes, or one-shot RAG. agent-memory separates durable knowledge into semantic facts, procedures, episodes, source records, scopes, and lifecycle states so an agent can remember useful context without blindly stuffing every transcript into future prompts.

Use it when you want:

- one user-level memory store shared across multiple agent harnesses
- local SQLite storage instead of a hosted memory service
- approved-only prompt context by default
- candidate/disputed/deprecated memory review flows
- source/provenance metadata for every curated memory
- bounded prompt rendering for Hermes/Codex/Claude wrappers
- retrieval regression fixtures with lexical/source baselines and failure triage

Docs for first-run and operational validation:

- [First-run memory layer setup](docs/first-run-memory-layer.md)
- [Hermes dogfood and operations guide](docs/hermes-dogfood.md)
- [Install smoke recipes](docs/install-smoke.md)

## 30-second install

Recommended path for CLI agent users:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

What this does:

- installs the `agent-memory` command
- initializes `~/.agent-memory/memory.db` when missing
- creates or merges the Hermes hook config at `~/.hermes/config.yaml`
- preserves existing Hermes hooks and appends the agent-memory pre-LLM hook
- lets you verify setup with `agent-memory doctor`

Python-first alternatives:

```bash
pipx install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
```

```bash
uv tool install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
```

## First memory in 60 seconds

```bash
DB=~/.agent-memory/memory.db

agent-memory init "$DB"
agent-memory create-fact "$DB" "agent-memory" "primary-install-path" "npm install -g @cafitac/agent-memory" "user:default"
agent-memory approve-fact "$DB" 1
agent-memory retrieve "$DB" "How should I install agent-memory?" --preferred-scope user:default
```

Normal retrieval is approved-only by default. Candidate, disputed, and deprecated memories stay out of prompt context unless you intentionally ask for a forensic view:

```bash
agent-memory retrieve "$DB" "What obsolete install notes exist?" --status all
agent-memory review conflicts fact "$DB" "agent-memory" "primary-install-path"
```

Review transitions can carry operator context and remain inspectable later. If one fact replaces another, record the replacement chain so stale facts can be explained without entering normal retrieval:

```bash
agent-memory review approve fact "$DB" 1 --reason "Verified from current setup guide." --actor maintainer --evidence-ids-json '[1]'
agent-memory review history fact "$DB" 1
agent-memory review supersede fact "$DB" 1 2 --reason "Newer source replaces the old install path." --actor maintainer --evidence-ids-json '[2]'
agent-memory review replacements fact "$DB" 1
agent-memory review explain fact "$DB" 1
```

`review explain` combines the current status, default retrieval visibility, transition history, same claim-slot alternatives, and replacement chain into one decision context so a reviewer can see why a stale or conflicting fact is hidden.

## Hermes quickstart

For most Hermes users:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

On first real Hermes use, Hermes may ask you to approve the shell hook or require `--accept-hooks` depending on your local Hermes policy.

The installed hook calls:

```bash
agent-memory hermes-pre-llm-hook ~/.agent-memory/memory.db --top-k 1 --max-prompt-lines 6 --max-prompt-chars 800 --max-prompt-tokens 200 --max-verification-steps 1 --max-alternatives 0 --max-guidelines 1 --no-reason-codes
```

The hook receives the Hermes event JSON on stdin, retrieves relevant approved memories, and returns bounded ephemeral context for the current prompt. It does not write back to Hermes session storage. `agent-memory bootstrap` uses the conservative Hermes preset by default: one top memory, small prompt budgets, no alternative-memory detail in the prompt, no reason-code noise, and fail-closed behavior if retrieval is unavailable.

If you only want to inspect the YAML snippet and not modify config:

```bash
agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db
```

If you want explicit paths and budgets:

```bash
agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --preset conservative --timeout 8
agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --preset balanced
```

Use `--preset balanced` if you intentionally want the older, more verbose hook shape (`--top-k 3`, larger budgets, and reason codes). Explicit flags such as `--top-k`, `--max-prompt-tokens`, or `--no-reason-codes` override the selected preset.

## Codex and Claude prompt wrappers

For harnesses that want a plain prompt prefix rather than a Hermes hook response:

```bash
agent-memory codex-prompt ~/.agent-memory/memory.db "What should I remember about this project?" --preferred-scope user:default
agent-memory claude-prompt ~/.agent-memory/memory.db "What should I remember about this project?" --preferred-scope user:default
```

The command prints prompt text only, so wrappers can prepend it to the live user request before invoking Codex, Claude Code, or another CLI.

This repository also includes source-checkout helper scripts for maintainers:

```bash
python scripts/run_codex_with_memory.py ~/.agent-memory/memory.db "What should I do next?" --dry-run
python scripts/run_claude_with_memory.py ~/.agent-memory/memory.db "What should I do next?" --dry-run
```

End users should prefer the installed `agent-memory` command unless they are developing this repository.

## Data and privacy model

- Default database: `~/.agent-memory/memory.db`
- Default Hermes config path: `~/.hermes/config.yaml`
- Storage: local SQLite
- Network behavior: the core CLI does not upload your memory database to an agent-memory cloud service
- Prompt policy: approved memories are retrieved by default; candidate/disputed/deprecated memories are excluded unless requested
- Scope policy: `user:default` is the recommended durable cross-project scope; Hermes can also derive privacy-preserving `cwd:<hash>` scopes without exposing raw local paths in prompt context

See `PRIVACY.md` and `SECURITY.md` for the external-user trust model, sensitive-data guidance, and vulnerability reporting instructions.

## Uninstall and rollback

Uninstall the CLI:

```bash
npm uninstall -g @cafitac/agent-memory
# or
pipx uninstall cafitac-agent-memory
# or
uv tool uninstall cafitac-agent-memory
```

Remove the Hermes hook by editing `~/.hermes/config.yaml` and deleting the `agent-memory hermes-pre-llm-hook ...` command from `hooks.pre_llm_call`.

Keep or remove local data explicitly:

```bash
# inspect first
ls -lh ~/.agent-memory/memory.db

# destructive: removes the local memory database
rm ~/.agent-memory/memory.db
```

`agent-memory bootstrap` backs up changed Hermes config files to `*.agent-memory.bak` when it modifies an existing config.

## Retrieval evaluation and regression gates

agent-memory includes a fixture-based retrieval evaluator so retrieval behavior can be tested like application code:

```bash
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --baseline-mode lexical
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --baseline-mode lexical --format text
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --fail-on-regression
```

Supported baseline modes include:

- `lexical`: preferred-scope lexical comparator
- `lexical-global`: lexical comparator that ignores preferred scope
- `source-lexical`: lexical comparator over linked source content within preferred scope
- `source-global`: source-linked comparator that ignores preferred scope

Reports include per-task retrieved IDs, expected hits, missing IDs, avoid hits, pass/fail state, aggregate summaries, soft-threshold advisories, and failure triage details such as snippets, lifecycle status, scopes, and policy signals. Every JSON result also includes an `advisory_report` with severity, affected task IDs, and recommended next actions. Text reports render the same advisory report as terminal-friendly guidance for maintainers reviewing failed retrieval tasks; JSON is the stable machine-readable surface.

The evaluator calls the real retrieval path but suppresses retrieval bookkeeping side effects while it runs. Eval tasks do not increment `retrieval_count`, `reinforcement_count`, or `last_accessed_at`, so fixture order and repeated local/CI runs do not perturb later ranking results.

## Current maturity

agent-memory is alpha software, but the public install path is validated.

What is ready:

- npm and PyPI releases from the same versioned source
- GitHub Release artifacts
- CI and release metadata checks
- published-install smoke checks
- local SQLite storage
- Hermes bootstrap/doctor flow
- Codex/Claude prompt rendering commands
- approved-only retrieval policy by default
- retrieval regression fixtures and diagnostic reports

Known limitations:

- no hosted sync service
- no built-in encryption-at-rest wrapper around the SQLite file
- no automatic secret detection/redaction before users create memories
- no stable 1.0 API guarantee yet
- advanced graph/semantic retrieval behavior is still evolving
- multi-machine sharing is currently a user-managed file/sync concern

## Development

```bash
git clone https://github.com/cafitac/agent-memory.git
cd agent-memory
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
uv run pytest tests/test_published_install_smoke.py -q
npm pack --dry-run
```

After a release publishes, the `published-install-smoke` workflow verifies the exact npm/PyPI version through npm registry lookup, `npx`, `npm exec`, `uvx`, and `pipx`. Maintainers can also run it manually with `gh workflow run published-install-smoke.yml -f version=<version>`.

Release automation expects protected `main`: if the auto-release workflow cannot push its bumped metadata commit directly, it opens a `release-sync/vX.Y.Z` PR instead. After that PR is merged, the same workflow tags the synced version and dispatches `publish.yml`, keeping the release path automated without requiring a permanent branch-protection bypass. The fallback is safe to rerun: if the `release-sync/vX.Y.Z` branch or PR already exists, the workflow reuses it instead of failing on a non-fast-forward push or opening a duplicate PR.

Useful source-checkout commands:

```bash
uv run python -m agent_memory.api.cli --help
uv run python -m agent_memory.api.cli hermes-bootstrap /tmp/agent-memory.db --config-path /tmp/hermes-config.yaml
uv run python -m agent_memory.api.cli hermes-doctor /tmp/agent-memory.db --config-path /tmp/hermes-config.yaml
```

## Repository docs

- `docs/install-smoke.md`: published install smoke recipes
- `SECURITY.md`: vulnerability reporting and local security model
- `PRIVACY.md`: local data, prompt, and hook privacy model
- `CONTRIBUTING.md`: contribution workflow
- `.dev/`: AI-authored drafts, design spikes, research notes, and unapproved plans
- `docs/`: human-reviewed promoted documentation

## License

MIT. See `LICENSE`.
