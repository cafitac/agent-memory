# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 21:49 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업 Priority 1~4의 주요 truth lifecycle 조각과 retrieval-eval read-only hardening을 v0.1.31까지 완료했고, 현재 slice는 protected `main` 때문에 반복되던 release metadata sync 수동 절차를 자동 fallback PR 흐름으로 줄이는 작업이야.

최신 검증 완료 릴리스는 v0.1.31이야. v0.1.27에서 status transition history, v0.1.28에서 npm wrapper stdin forwarding과 published Hermes hook smoke, v0.1.29에서 fact supersession/replacement relation, v0.1.30에서 `agent-memory review explain fact ...` decision explanation UX, v0.1.31에서 retrieval eval read-only behavior가 들어갔어. 로컬 Hermes hook도 v0.1.31 runtime으로 업데이트되어 doctor/hook smoke가 통과한 상태야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- branch: `main`
- HEAD: `6d955bb chore: release v0.1.31 [skip release] (#30)`
- tag/release: `v0.1.31`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.31`
- npm: `@cafitac/agent-memory@0.1.31`
- PyPI: `cafitac-agent-memory==0.1.31`
- v0.1.31 published smoke artifact: passed after a propagation retry; includes npm/uvx/pipx Hermes hook commands.

Active slice/worktree:

- branch: `ci/auto-release-sync-pr`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/auto-release-sync-pr`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.31

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28+ smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.
- Known repeated pain point before this slice: protected `main` blocked auto-release metadata write-back, requiring manual release-sync PR + manual tag push.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.31/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
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

## Current slice: protected-main release fallback automation

Planned behavior:

- Main merge auto-release still tries the direct metadata write-back first.
- If `git push origin HEAD:main` is rejected by GitHub rules/protected `main`, auto-release should not fail the whole release path immediately.
- It should create a `release-sync/vX.Y.Z` branch from the already-bumped commit and open a PR titled `chore: release vX.Y.Z [skip release]`.
- The direct publish dispatch should run only when direct main push/tag push succeeds.
- After the release-sync PR is merged, a separate auto-release job should recognize the `[skip release]` release-sync commit, create/push the missing annotated tag, and dispatch `publish.yml`.
- If the tag already exists, the release-sync follow-up job should no-op rather than republishing.

Implementation direction:

- Update `.github/workflows/auto-release.yml` permissions to include `pull-requests: write`.
- Add `id: push_release` and a protected-main rejection branch around the direct push step.
- Add a `gh pr create` fallback step guarded by `steps.push_release.outputs.release_sync_required == 'true'`.
- Add a `tag-and-publish-release-sync` job for merged `chore: release v... [skip release]` commits.
- Keep `[skip release]` as the anti-recursion marker.
- Keep publish creation inside `publish.yml`; auto-release should only dispatch it.

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

This slice changes only release automation/docs/tests, but it affects the release path and should be treated as a patch release candidate, likely v0.1.32 after PR merge.

Expected live verification after merge:

1. The auto-release run for the PR merge should bump metadata to v0.1.32.
2. If protected `main` still rejects direct write-back, the run should open `release-sync/v0.1.32` PR automatically.
3. Merge that PR.
4. Confirm the release-sync follow-up job creates tag `v0.1.32`, dispatches publish, and published smoke passes.
5. Verify GitHub Release/npm/PyPI/published-install-smoke artifact.
6. Update local Hermes runtime to v0.1.32 only after package release is verified.

## Next likely slices after this

1. Published smoke propagation handling improvement: make first-run simple-index lag less noisy.
2. Actual Hermes dogfood observations and noise/latency notes.
3. Graph foundation read-only slice: graph inspection CLI or bounded relation traversal eval fixtures.
4. PyPI Trusted Publisher later; user deferred it.
