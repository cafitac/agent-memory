# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 23:00 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 v0.1.33까지 release fallback rerun idempotency와 Hermes v0.1.33 QA까지 끝났고, 현재 진행 중인 통합 slice는 v0.1.34 후보야. 세 가지를 한 PR로 묶어 진행 중이야: published smoke propagation/backoff hardening, release-sync PR CI validation dispatch, read-only relation graph inspect CLI.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- branch: `main`
- latest completed release: `v0.1.33`
- v0.1.33 included release-sync fallback rerun idempotency.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.33/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.

Active slice/worktree:

- branch: `feat/release-graph-hardening`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/release-graph-hardening`
- intended release after merge: likely `v0.1.34`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.33

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28+ smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.
- Protected `main` fallback is automated: auto-release creates `release-sync/vX.Y.Z` PR when direct metadata write-back is rejected; after merge, auto-release tags and dispatches publish.
- v0.1.33 made that fallback safe to rerun when the branch or PR already exists.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.33/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
- Hermes hook fails closed: unavailable DB/schema returns `{}` and exit 0 instead of breaking prompt flow.
- Conservative preset remains default: small prompt budgets, one top memory, no alternative-memory detail, no reason-code noise.
- `--preset balanced` is explicit opt-in for more context/noise.

### Truth lifecycle and eval readiness

- Normal retrieval is approved-only by default.
- Candidate/disputed/deprecated facts remain available only behind explicit forensic/review surfaces.
- `memory_status_transitions` records status changes with from/to status, reason, actor, evidence IDs, and timestamp.
- `agent-memory review history fact|procedure|episode ...` exposes transition history.
- `agent-memory review supersede fact <db> <old> <new>` records fact replacement as a relation edge.
- Replacement relation direction: `fact:<old> --superseded_by--> fact:<new>`.
- Superseding a fact deprecates the old fact and approves the replacement fact, preserving reason/actor/evidence in transition history.
- `agent-memory review replacements fact ...` exposes replacement chains.
- `agent-memory review explain fact ...` explains status, default retrieval visibility, same claim-slot alternatives, replacement chain, and review follow-up commands.
- Retrieval eval calls the real retrieval path but suppresses retrieval bookkeeping writes (`retrieval_count`, `reinforcement_count`, `last_accessed_at`).

## Current slice: release/package/graph hardening

User asked to do all three next recommended tasks:

1. Published smoke propagation/backoff improvement.
2. release-sync PR CI dispatch/status automation.
3. Graph foundation first safe slice: read-only relation graph inspect CLI.

Current implementation direction:

### Published smoke propagation/backoff

Files:

- `scripts/smoke_published_install.py`
- `tests/test_published_install_smoke.py`
- `.github/workflows/publish.yml`
- `.github/workflows/published-install-smoke.yml`

Behavior:

- Detect resolver/package-index propagation-like failures such as `No solution found`, `No matching distribution found`, npm 404/ETARGET/NOTARGET, and exact `cafitac-agent-memory==X.Y.Z` misses.
- Apply a separate longer retry budget only for propagation-like failures:
  - normal attempts remain bounded
  - propagation attempts can extend with exponential backoff
- Failure artifacts include registry probe diagnostics:
  - npm version present/latest
  - PyPI JSON release present
  - PyPI simple index mentions version
  - probe errors
- `publish.yml` uses `--attempts 12`, `--propagation-attempts 36`, `--propagation-delay-seconds 20`.
- Manual `published-install-smoke.yml` exposes propagation attempt/delay inputs.

### release-sync PR CI validation dispatch

Files:

- `.github/workflows/auto-release.yml`
- `tests/test_release_workflows.py`

Behavior:

- When fallback creates a new `release-sync/vX.Y.Z` PR, capture the PR URL.
- Dispatch `ci.yml` explicitly on `release-sync/vX.Y.Z` with `gh workflow run ci.yml --ref "${RELEASE_SYNC_BRANCH}"`.
- Comment on the PR explaining that bot-created refs may suppress automatic PR checks and that maintainers should wait for the dispatched `ci.yml` run before merging.

### read-only relation graph inspect CLI

Files:

- `src/agent_memory/api/cli.py`
- `src/agent_memory/storage/sqlite.py`
- `tests/test_cli.py`
- `README.md`

New command:

```bash
agent-memory graph inspect <db_path> <start_ref> --depth 1 --limit 100
```

Example:

```bash
agent-memory graph inspect ~/.agent-memory/memory.db fact:1 --depth 2 --limit 50
```

Behavior:

- Traverses stored `Relation` edges only.
- JSON output includes:
  - `kind: relation_graph_inspection`
  - `start_ref`
  - `depth`
  - `limit`
  - `read_only: true`
  - `nodes`
  - `edges`
  - `truncated`
- Does not change retrieval behavior.
- Does not mutate memory state.
- Intended as the first safe graph-foundation slice before default retrieval graph traversal.

## Verification checklist for this slice

Run from the active worktree:

```bash
uv run pytest tests/test_published_install_smoke.py -q
uv run pytest tests/test_release_workflows.py -q
uv run pytest tests/test_cli.py::test_python_module_cli_graph_inspect_returns_read_only_relation_neighborhood -q
uv run pytest tests/test_published_install_smoke.py tests/test_release_workflows.py tests/test_cli.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
node --check bin/agent-memory.js
```

Before PR, run a static diff secret scan and confirm finding_count 0.

## PR/release notes

This slice affects release automation, published install smoke, and a new read-only CLI command. Treat it as a patch release candidate, likely v0.1.34 after PR merge.

Expected live verification after merge:

1. PR merge should trigger auto-release and bump metadata to v0.1.34.
2. Protected `main` should trigger fallback.
3. Fallback should create `release-sync/v0.1.34` PR and dispatch `ci.yml` on that branch.
4. Wait for the dispatched CI run before merging release-sync PR.
5. Merge the release-sync PR.
6. Confirm release-sync follow-up creates tag `v0.1.34`, dispatches publish, and published smoke passes.
7. Verify GitHub Release/npm/PyPI/published-install-smoke artifact.
8. Update local Hermes runtime to v0.1.34 only after package release is verified.

## Next likely slices after this

1. Actual Hermes dogfood observations and noise/latency notes.
2. Expand graph inspection with node metadata/status summaries, still read-only.
3. Later graph retrieval eval fixtures before any default graph expansion.
4. PyPI Trusted Publisher later; user deferred it.
