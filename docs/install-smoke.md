# Install smoke recipes

This document records the approved post-publish smoke paths for agent-memory.

## Goal

Verify that published install surfaces work in a clean shell or clean machine without relying on the source checkout.

When validating multiple install surfaces on the same machine, run each path in a fresh shell or sanitize `PATH` so an earlier `agent-memory` binary does not shadow the surface under test.

Maintainer note: if you also isolate `HOME` during smoke runs, restore your normal maintainer shell context before using `gh` or `git push` against the repo again. For example, run GitHub operations from a fresh maintainer shell or temporarily set `HOME=/path/to/maintainer/home` for that command. Repositories maintained with SSH remotes and host aliases are less sensitive to `gh` HTTPS credential lookup, but the principle still applies to any tooling that reads credentials from `HOME`.

## npm path

Use this as the primary end-user onboarding path for Hermes-oriented CLI users.

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Expected outcomes:
- `agent-memory bootstrap` initializes `~/.agent-memory/memory.db` if missing
- Hermes config is created or merged at `~/.hermes/config.yaml`
- `agent-memory doctor` reports healthy setup status
- `hermes hooks doctor` reports that shell hooks are healthy

Optional cleanup:

```bash
npm uninstall -g @cafitac/agent-memory
```

## pipx path

Use this when the operator prefers Python-native installation while still avoiding a source checkout.

```bash
pipx install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Optional cleanup:

```bash
pipx uninstall cafitac-agent-memory
```

## uv tool path

Use this for users already standardizing on uv-managed CLI tools.

```bash
uv tool install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Optional cleanup:

```bash
uv tool uninstall cafitac-agent-memory
```


## Automated published smoke

The fast release path does not run the slow published install matrix by default. Feature PRs and release-sync PRs already run `ci.yml`; docs/workflow-only pushes are ignored by `auto-release.yml`; `publish.yml` is reserved for tag/manual publish, package build, registry publish, and GitHub Release creation. This keeps GitHub Actions minutes bounded while still leaving an explicit external-install gate when needed.

Run the published install matrix manually before a high-confidence external-user checkpoint, after a suspicious publish, or when changing launcher/install behavior:

```bash
gh workflow run published-install-smoke.yml \
  --repo cafitac/agent-memory \
  -f version=<version> \
  -f attempts=6 \
  -f propagation_attempts=12 \
  -f propagation_delay_seconds=10
```

For an inline smoke during a manual publish dispatch, opt in explicitly:

```bash
gh workflow run publish.yml \
  --repo cafitac/agent-memory \
  --ref v<version> \
  -f publish_pypi=true \
  -f publish_npm=true \
  -f run_published_install_smoke=true
```

The workflows execute `scripts/smoke_published_install.py`, which validates the exact published version through npm registry lookup, `npx`, `npm exec`, `uvx`, and `pipx` from isolated temporary homes. Smoke artifacts are uploaded as `published-install-smoke-result` and include failure summaries plus registry propagation diagnostics.

Local maintainer smoke for the current `package.json` version:

```bash
uv run python scripts/smoke_published_install.py --attempts 3 --delay-seconds 10
```

## Fresh-user trust matrix

Before treating a release as ready for external users, validate these surfaces from an external temp directory, not from the source checkout:

| Surface | Required checks | Expected safety property |
| --- | --- | --- |
| npm | `npm exec --yes --package @cafitac/agent-memory@<version> agent-memory -- --help`; seed one approved memory; run `hermes-context` | direct `agent-memory [command]` UX works and prompt text includes only approved memory content |
| npx | `npx --yes @cafitac/agent-memory@<version> --help` | no source checkout or local PATH dependency |
| uvx | `uvx --refresh cafitac-agent-memory==<version> agent-memory --help` | PyPI package resolves independently of npm wrapper |
| Hermes | `agent-memory bootstrap`; `agent-memory doctor`; `hermes hooks doctor`; one QA prompt with hooks accepted | hook install is merge-safe, bounded by conservative prompt budgets, and fails closed if memory DB is unavailable |
| Codex/Claude prompts | `agent-memory codex-prompt ...`; `agent-memory claude-prompt ...` after seeding approved memory | prompt wrappers include actual approved snippets and exclude disputed/deprecated content by default |
| Forensic review | `agent-memory retrieve ... --status all`; `agent-memory review conflicts fact ...`; `agent-memory review history fact ...`; `agent-memory review replacements fact ...`; `agent-memory review relate-conflict fact ... --actor ... --reason ...`; `agent-memory review explain fact ...` | obsolete/conflicting memory can be inspected intentionally with status-transition reason/evidence history, same-claim alternatives, default-retrieval visibility, reviewed supersedes/replaces chains, and explicit reviewed conflict relation refs without entering normal prompts |

## What to capture if smoke fails

Record:
- install command used
- platform / shell
- full stdout/stderr
- whether `~/.agent-memory/memory.db` was created
- whether `~/.hermes/config.yaml` was created or merged
- output of `agent-memory doctor`
- output of `hermes hooks doctor`

## Retrieval preview smoke

Published install smoke should include the read-only Stage F surfaces when validating a release that changes retrieval diagnostics:

```bash
agent-memory retrieval policy-preview "$DB" "install smoke query" --limit 5
agent-memory retrieval ranker-preview "$DB" "install smoke query" --limit 5 --reinforcement-weight 0.15
agent-memory retrieval decay-preview "$DB" "install smoke query" --limit 5 --decay-weight 0.2
agent-memory retrieval graph-neighborhood-preview "$DB" "install smoke query" --limit 5 --depth 1 --graph-weight 0.15
```

All four commands must report `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`; none should print raw query previews or mutate retrieval counters.

## Release note

As of the latest validated public install smoke, the validated tag is `v0.1.69`. The primary npm path is expected to leave users with a direct shell command: `agent-memory [command]`; docs should not require users to type `uv`, `uvx`, or `python -m` after npm installation.

## Optional v0.1.66 remember-intent smoke

After installing `cafitac-agent-memory==0.1.66` or `@cafitac/agent-memory@0.1.66`, initialize a temporary DB and run `hermes-pre-llm-hook --record-trace` with a synthetic payload whose `user_message` starts with `Remember this:`. Then verify `agent-memory traces list <db> --event-kind remember_intent` returns a review trace with `retention_policy=review` and `auto_approved=false`. This smoke should not create facts, procedures, episodes, or approved long-term memory.

For the G1a report gate, seed or capture at least one safe remember-intent trace, then run `agent-memory dogfood remember-intent <db> --limit 200 --sample-limit 10`. The report should return `kind: remember_intent_dogfood_report`, `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, sanitized samples only, safe `rejection_counts` for blocked explicit remember requests, and no fact/procedure/episode/approval mutations.

For the G2 narrow auto-approval smoke, seed a safe review-ready remember-intent trace whose summary is shaped like `User prefers concise Korean handoffs.`. First run `agent-memory consolidation auto-approve remember-preferences <db> --policy remember-preferences-v1 --scope <scope>` and verify the report is read-only with a `would_approve` candidate and no fact/source/relation/status mutation. Then run the same command with `--apply --actor <actor> --reason <reason>` and verify exactly one approved `fact` with predicate `prefers`, a status transition, and an `auto_approved_as` graph relation are created. Also smoke a conflicting same-slot approved fact and verify the apply command exits non-zero without mutation.

For the G3 background dry-run smoke, seed at least two safe review traces with matching sanitized summaries, then run:

```bash
agent-memory consolidation background dry-run <db> \
  --limit 50 \
  --top 10 \
  --min-evidence 2 \
  --output <tmp-report.json> \
  --lock-path <tmp-lock>
```

Verify the command exits zero, prints `kind: memory_consolidation_background_dry_run`, `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, `status: completed`, and writes the same JSON to `<tmp-report.json>`. Also hold the lock file from another process and verify a second run exits zero with `status: skipped_lock_busy` rather than mutating memory or failing cron.

For the G3 dogfood quality-gate smoke, run the read-only evaluator over the saved report:

```bash
agent-memory dogfood background-dry-run <db> \
  --report <tmp-report.json> \
  --candidate-min 1 \
  --max-decay-risk 0 \
  --output <tmp-quality-report.json>
```

Verify it prints `kind: background_dry_run_dogfood_report`, `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, per-report summaries only, and no raw report payloads or `raw_prompt`/query fields. `quality_gate.pass: true` only means a separate G4 plan may be drafted; it does not apply, approve, or change retrieval.

For the G3c storage-health smoke, run the read-only live-DB health gate:

```bash
agent-memory dogfood storage-health <db> --hermes-config ~/.hermes/config.yaml
```

Verify it prints `kind: dogfood_storage_health`, `read_only: true`, `mutated: false`, table counts, latest timestamps, memory status counts, Hermes hook markers, and aggregate invariant checks without raw query values, query preview values, prompts, transcripts, user messages, rejected secret-like text, or raw metadata payloads. Any `status: warning` should be investigated before G4 planning; the command itself must not mutate observations, activations, traces, facts, procedures, episodes, relations, retrieval ranking, or hook config.

If the storage-health report warns about legacy stored query excerpts, run the read-only cleanup preview:

```bash
agent-memory dogfood query-preview-cleanup <db> --older-than 2030-01-01T00:00:00
```

Verify it prints `kind: dogfood_query_preview_cleanup_preview`, `read_only: true`, `mutated: false`, aggregate affected/eligible counts, no sample values, no raw query previews, no `api key`, no token-like values, and no DB mutation. This is a diagnostic preview only; it does not expose an apply mode.
