# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 22:21 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업 Priority 1~4의 주요 truth lifecycle 조각, retrieval-eval read-only hardening, protected-main release fallback 자동화를 v0.1.32까지 완료했고, 현재 slice는 release fallback rerun idempotency 보강이야.

최신 검증 완료 릴리스는 v0.1.32야. v0.1.27에서 status transition history, v0.1.28에서 npm wrapper stdin forwarding과 published Hermes hook smoke, v0.1.29에서 fact supersession/replacement relation, v0.1.30에서 `agent-memory review explain fact ...` decision explanation UX, v0.1.31에서 retrieval eval read-only behavior, v0.1.32에서 protected-main release-sync PR/tag/publish automation이 들어갔어. 로컬 Hermes hook도 v0.1.32 runtime으로 업데이트되어 doctor/hook smoke가 통과한 상태야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- branch: `main`
- HEAD: `654c5d8 chore: release v0.1.32 [skip release] (#32)`
- tag/release: `v0.1.32`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.32`
- npm: `@cafitac/agent-memory@0.1.32`
- PyPI: `cafitac-agent-memory==0.1.32`
- v0.1.32 published smoke artifact: passed; includes npm/uvx/pipx Hermes hook commands.
- repo Actions workflow setting: `can_approve_pull_request_reviews=true`, needed so `GITHUB_TOKEN` can create release-sync PRs.

Active slice/worktree:

- branch: `ci/release-fallback-idempotency`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/release-fallback-idempotency`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.32

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28+ smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.
- Protected `main` fallback is automated: auto-release creates `release-sync/vX.Y.Z` PR when direct metadata write-back is rejected; after merge, auto-release tags and dispatches publish.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.32/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
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

## Current slice: release fallback rerun idempotency

Why this slice exists:

- During the first v0.1.32 live fallback run, GitHub Actions created `release-sync/v0.1.32` but failed to create the PR because the repository Actions setting initially disallowed GitHub Actions from creating PRs.
- After enabling that setting, rerunning the failed job hit a non-fast-forward branch push because the release-sync branch already existed.
- The fallback should be safe to rerun after this kind of partial success.

Planned behavior:

- When protected-main fallback starts, check whether `release-sync/vX.Y.Z` already exists on origin.
- If the branch exists, reuse it instead of pushing and failing with non-fast-forward.
- Check whether an open PR already exists for the release-sync branch.
- If the PR exists, log the URL and exit successfully instead of opening a duplicate PR.
- If neither exists, keep the existing branch push + `gh pr create` behavior.

Implementation direction:

- Update `.github/workflows/auto-release.yml` fallback step with `git ls-remote --heads` branch detection.
- Add `gh pr list --head ... --state open --json url --jq '.[0].url // empty'` before `gh pr create`.
- Keep the direct path and release-sync tag/publish follow-up unchanged.
- Add/keep tests in `tests/test_release_workflows.py` proving idempotency markers exist in the workflow.

## Verification checklist for this slice

Run from the active worktree:

```bash
uv run pytest tests/test_release_workflows.py -q
uv run pytest tests/test_published_install_smoke.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
node --check bin/agent-memory.js
```

Before PR, run a static diff secret scan and confirm finding_count 0.

## PR/release notes

This slice changes only release automation/docs/tests, but it affects the release path and should be treated as a patch release candidate, likely v0.1.33 after PR merge.

Expected live verification after merge:

1. PR merge should trigger auto-release and bump metadata to v0.1.33.
2. Protected `main` should trigger fallback.
3. Fallback should create `release-sync/v0.1.33` PR or reuse it if a partial rerun already created it.
4. Merge the release-sync PR.
5. Confirm release-sync follow-up creates tag `v0.1.33`, dispatches publish, and published smoke passes.
6. Verify GitHub Release/npm/PyPI/published-install-smoke artifact.
7. Update local Hermes runtime to v0.1.33 only after package release is verified.

## Next likely slices after this

1. Published smoke propagation handling improvement: make first-run simple-index lag less noisy.
2. Actual Hermes dogfood observations and noise/latency notes.
3. Graph foundation read-only slice: graph inspection CLI or bounded relation traversal eval fixtures.
4. PyPI Trusted Publisher later; user deferred it.
