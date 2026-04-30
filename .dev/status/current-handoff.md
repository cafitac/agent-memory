# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 15:55 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘

> 다음으로 진행할거 해줘

> 다음 거 진행해줘

> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업 Priority 1~3을 대부분 마쳤고, Priority 4 `Conflict, obsolete, and truth lifecycle`를 진행 중이야.

완료된 최신 공개 릴리스는 v0.1.28이야. v0.1.27에서 status transition history가 들어갔고, v0.1.28에서 npm wrapper stdin forwarding과 published smoke의 Hermes hook QA 경로가 보강됐어. 현재 slice는 `feat: add supersedes/replaces relation for facts`야. 목적은 새 fact가 옛 fact를 대체했음을 구조적으로 남겨서 deprecated memory가 왜 폐기됐고 무엇으로 대체됐는지 설명할 수 있게 하는 것. graph/hybrid retrieval 전에 stale memory가 graph를 타고 퍼지지 않게 하는 truth lifecycle 기반이야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Current verified base before this slice:

- branch: `main`
- HEAD: `1467d24 chore: release v0.1.28 [skip release]`
- tag/release: `v0.1.28`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.28`
- npm: `@cafitac/agent-memory@0.1.28`
- PyPI: `cafitac-agent-memory==0.1.28`
- v0.1.28 published smoke artifact: passed; includes npm/uvx/pipx Hermes hook commands.

Active slice/worktree:

- branch: `feat/fact-supersedes-replaces`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/fact-supersedes-replaces`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.28

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- main merge auto-release is active but protected `main` can block release metadata write-back; if that happens, use release-sync PR + tag push.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28 smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.28/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
- Hermes hook fails closed: unavailable DB/schema returns `{}` and exit 0 instead of breaking prompt flow.
- Conservative preset remains default: small prompt budgets, one top memory, no alternative-memory detail, no reason-code noise.
- `--preset balanced` is explicit opt-in for more context/noise.

### Retrieval eval and quality visibility

- `agent-memory eval retrieval` exists with JSON/text reporting, baseline comparators, regression gates, failure triage, and structured `advisory_report`.
- On regression gate failure, CLI stderr prints a human-readable advisory report when available.

### Memory lifecycle and conflict handling

- Memory statuses: `candidate`, `approved`, `disputed`, `deprecated`.
- Default retrieval remains approved-only.
- `retrieve --status approved|candidate|disputed|deprecated|all` supports intentional forensic retrieval.
- `review conflicts fact ...` shows same-slot fact lifecycle across statuses.
- `review history ...` shows status transition history with reason/actor/evidence/timestamp.
- Current slice adds fact replacement chains: old fact `superseded_by` new fact, old fact deprecated, replacement fact approved.

## Immediate next work: finish fact supersedes/replaces PR

Goal:

Land the second Priority 4 truth-lifecycle slice: record when one fact supersedes/replaces another, preserve status-transition history, and expose replacement chains through CLI review surfaces while keeping normal retrieval approved-only.

Active branch/worktree:

```bash
cd /Users/reddit/Project/agent-memory/.worktrees/fact-supersedes-replaces
```

Implemented in this slice so far:

1. Tests
   - storage/curation test for `supersede_fact(...)` recording `superseded_by` relation, deprecating old fact, approving replacement fact, and preserving transition history.
   - CLI test for `agent-memory review supersede fact ...` and `agent-memory review replacements fact ...`.

2. Storage/curation/CLI
   - `get_fact(...)`
   - `list_fact_replacement_relations(...)`
   - `supersede_fact(...)`
   - `review supersede fact` command
   - `review replacements fact` command

3. Docs
   - README forensic review examples mention replacement chains.
   - `docs/install-smoke.md` forensic review surface mentions `review replacements`.

Focused tests passed:

```bash
uv run pytest tests/test_review_and_scope_ranking.py::test_supersede_fact_records_replacement_relation_and_status_history tests/test_cli.py::test_python_module_cli_review_supersede_fact_shows_replacement_chain -q
# 2 passed
```

Remaining verification:

```bash
uv run pytest tests/test_review_and_scope_ranking.py tests/test_cli.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
```

Then commit, push, open PR, watch CI, merge when green, verify auto-release/publish, and verify npm/PyPI/GitHub Release/published-smoke artifact. If auto-release cannot push protected `main`, use release-sync PR + tag push.

## Roadmap position

Final goal:

agent-memory should be credible as an OSS default memory layer for Hermes, Codex, and Claude Code: safe to install, safe to leave on, measurable, debuggable, conservative by default, and able to explain why memories are trusted or obsolete.

### Priority 1 — Retrieval quality measurement and triage

Status: core complete; broader corpus/flake hardening remain.

### Priority 2 — Always-on hook safety and conservative defaults

Status: mostly complete; real dogfood observations can continue.

### Priority 3 — Fresh-user onboarding matrix automation

Status: mostly complete; published smoke gate is active and now includes Hermes hook stdin QA.

### Priority 4 — Conflict, obsolete, and truth lifecycle

Status: in progress.

Completed:

- v0.1.27: memory transition history.

Current:

- fact supersedes/replaces relation.

Likely next candidates:

1. conflict review decision explanation UX.
2. retrieval eval determinism/flake hardening.
3. graph-centered foundation only after lifecycle chains are strong enough.

### Priority 5 — Long-run dogfood and noise monitoring

Status: not started beyond docs/checklists.
