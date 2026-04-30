# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 14:34 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘

> 다음으로 진행할거 해줘

> 다음 거 진행해줘

> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업의 Priority 1~3을 대부분 마쳤고, Priority 4 `Conflict, obsolete, and truth lifecycle`에 들어와 있어.

v0.1.26 기준으로 npm/PyPI/GitHub Release, published install smoke gate, Hermes conservative preset, first-run guide, Hermes dogfood/ops guide, retrieval eval advisory report, CLI failure advisory summary, smoke failure JSON artifact까지 확인됐어.

현재 진행 중인 slice는 `feat: add memory transition history`야. 목적은 candidate/approved/disputed/deprecated 상태 전환마다 이유, actor, evidence ids, timestamp를 남겨서 나중에 "왜 이 기억을 믿거나 폐기했는지" 볼 수 있게 하는 것. 이게 graph/hybrid retrieval 전에 필요한 truth lifecycle 기반이야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands:
  - `HOME=/Users/reddit gh auth status`
  - `HOME=/Users/reddit gh auth switch --hostname github.com --user cafitac`
- Remote:
  - `origin` -> `https://github.com/cafitac/agent-memory.git`

Current verified base before this slice:

- branch: `main`
- HEAD: `b9228b9 chore: release v0.1.26 [skip release]`
- tag/release: `v0.1.26`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.26`
- npm: `@cafitac/agent-memory@0.1.26`
- PyPI: `cafitac-agent-memory==0.1.26`
- PR #20 merged: `docs: add onboarding dogfood and diagnostics`

Active slice/worktree:

- branch: `feat/memory-transition-history`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/memory-transition-history`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.26

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented:
  - `npm install -g @cafitac/agent-memory`
  - `npx @cafitac/agent-memory ...`
  - `uvx --from cafitac-agent-memory agent-memory ...`
- main merge auto-release is active:
  - patch bump
  - `[skip release]` release commit
  - tag
  - explicit publish workflow dispatch
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- Hermes hook fails closed: unavailable DB/schema returns `{}` and exit 0 instead of breaking prompt flow.
- Hermes conservative default keeps prompt injection small:
  - `--top-k 1`
  - `--max-prompt-lines 6`
  - `--max-prompt-chars 800`
  - `--max-prompt-tokens 200`
  - `--max-verification-steps 1`
  - `--max-alternatives 0`
  - `--max-guidelines 1`
  - `--no-reason-codes`
  - `timeout: 8`
- `--preset balanced` is explicit opt-in for more context/noise.
- Codex/Claude prompt wrapper commands exist for plain prompt-prefix integration.

### Retrieval eval and quality visibility

- `agent-memory eval retrieval` exists.
- JSON is the machine-readable default; `--format text` is available for human triage.
- Baseline comparators exist:
  - lexical
  - lexical-global
  - source-lexical
  - source-global
- Gating options exist:
  - `--fail-on-regression`
  - `--fail-on-baseline-regression`
  - `--fail-on-baseline-regression-memory-type ...`
- Reports include failure triage details and structured `advisory_report` with severity, affected task IDs, and recommended actions.
- On regression gate failure, CLI stderr prints `retrieval eval failed: ...` plus the text advisory report when available.

### Memory lifecycle and conflict handling before this slice

- Memory statuses exist:
  - `candidate`
  - `approved`
  - `disputed`
  - `deprecated`
- Default retrieval remains approved-only.
- `retrieve --status approved|candidate|disputed|deprecated|all` supports intentional forensic retrieval.
- `review conflicts fact ...` shows same-slot fact lifecycle across statuses.
- Forensic/non-approved retrieval sets verify-first / verification-required signals.
- Hidden alternatives/conflicts can influence risk policy without surfacing stale content by default.

## Immediate next work: finish memory transition history PR

Goal:

Land the first Priority 4 truth-lifecycle slice: record every review status transition with from/to status, reason, actor, evidence ids, and timestamp, then expose it through CLI.

Active branch/worktree:

```bash
cd /Users/reddit/Project/agent-memory/.worktrees/memory-transition-history
```

Implemented or in progress in this slice:

1. Schema/model/storage
   - `memory_status_transitions` table in `src/agent_memory/storage/schema.sql`
   - `MemoryStatusTransition` model in `src/agent_memory/core/models.py`
   - `update_memory_status(..., reason, actor, evidence_ids)` records transitions
   - `list_memory_status_history(...)` returns ordered transition history

2. Curation API
   - `approve_memory`, `dispute_memory`, `deprecate_memory` accept optional `reason`, `actor`, and `evidence_ids`

3. CLI
   - `agent-memory review approve|dispute|deprecate ... --reason ... --actor ... --evidence-ids-json ...`
   - `agent-memory review history <memory_type> <db_path> <memory_id>`

4. Docs/tests
   - README forensic review example mentions `review conflicts` and `review history`
   - `docs/install-smoke.md` includes transition history in forensic review smoke surface
   - `tests/test_review_and_scope_ranking.py` covers persisted transition history
   - `tests/test_cli.py` covers CLI review reason/evidence and history output

Focused tests already passed for the core new behavior:

```bash
uv run pytest tests/test_review_and_scope_ranking.py::test_status_transition_history_records_review_reason_actor_and_evidence tests/test_cli.py::test_python_module_cli_review_history_shows_transition_reasons -q
# 2 passed
```

Remaining steps:

```bash
uv run pytest tests/test_review_and_scope_ranking.py tests/test_cli.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
```

Then commit, push, open PR, watch CI, merge when green, and verify the next auto-release/publish/smoke flow.

## Roadmap position

Final goal:

agent-memory should be credible as an OSS default memory layer for Hermes, Codex, and Claude Code: safe to install, safe to leave on, measurable, debuggable, and conservative by default.

### Priority 1 — Retrieval quality measurement and triage

Status: core complete, follow-up remains.

Completed:

- retrieval eval fixtures
- baseline comparators
- failure triage details
- advisory report
- CLI failure advisory summary

Remaining candidates:

- expand retrieval fixture corpus
- run advisory reports as CI artifacts/summaries
- harden suspected one-off retrieval eval flake

### Priority 2 — Always-on hook safety and conservative defaults

Status: mostly complete.

Completed:

- Hermes conservative default preset
- balanced opt-in preset
- hook fail-closed behavior
- first-run and dogfood/ops docs

Remaining candidates:

- deeper real Hermes dogfood latency/fallback observations
- optional noise/latency telemetry that remains local-only

### Priority 3 — Fresh-user onboarding matrix automation

Status: mostly complete.

Completed:

- first-run guide
- public trust docs
- published install smoke matrix
- publish gate after npm/PyPI publish
- JSON smoke artifact upload

Remaining candidates:

- GitHub Actions summary/annotations from smoke JSON
- more real-world outside-repo examples

### Priority 4 — Conflict, obsolete, and truth lifecycle

Status: active now.

Current PR candidate:

1. `feat: add memory transition history`

Next candidates after this lands:

2. `feat: add supersedes/replaces relation for facts`
3. `feat: add conflict review explanations`

Acceptance:

- Status transitions record reason/evidence.
- Deprecated/disputed memories remain inspectable but do not enter default prompts.
- Replacement chains are visible.
- Review UX supports safe operator decisions.

### Priority 5 — Long-run dogfood and noise monitoring

Status: not started beyond docs/checklists.

Candidates:

1. local dogfood retrieval observation log
2. noisy memory audit command
3. dogfood review cadence

Acceptance:

- No secrets are logged.
- Observations are local by default.
- Users can inspect which memory snippets were injected and why.
- Irrelevant injected memories can be reviewed and deprecated.

## Graph-centered memory context

Original graph/hybrid design is documented mainly in:

- `.dev/architecture/architecture-v0.md`
- `.dev/architecture/graph-vs-hybrid-retrieval.md`
- `.dev/product/thesis-and-scope.md`
- `.dev/research/brain-and-llm-memory-notes.md`
- `.dev/roadmap/roadmap-v0.md`

Current decision:

Do not jump straight to full graph traversal yet. Build truth lifecycle first so graph expansion does not amplify obsolete or wrong memories. The current transition-history slice is the first safe step toward graph-shaped memory because it makes trust state changes explicit and inspectable.

## Known caveats

- PyPI Trusted Publisher warnings are non-blocking; current publish uses API token fallback. User deferred PyPI Trusted Publisher setup.
- v0.1.25 and v0.1.26 each saw a one-off retrieval eval failure in publish verify, but reruns succeeded and local focused/full suites passed. Future work should harden deterministic ordering/isolation.
- Do not print or save GitHub tokens, PyPI tokens, npm tokens, passwords, or credentials.
- For GitHub CLI, use `HOME=/Users/reddit`.
- For local dev, use repo `.venv` through `uv run`; CI job-local `uv venv` is expected on GitHub hosted runners.
