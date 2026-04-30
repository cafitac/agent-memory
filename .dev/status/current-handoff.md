# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 17:12 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업 Priority 1~4의 주요 truth lifecycle 조각을 v0.1.30까지 완료했고, 다음 안정화 slice로 retrieval-eval determinism hardening을 진행 중이야.

최신 검증 완료 릴리스는 v0.1.30이야. v0.1.27에서 status transition history, v0.1.28에서 npm wrapper stdin forwarding과 published Hermes hook smoke, v0.1.29에서 fact supersession/replacement relation, v0.1.30에서 `agent-memory review explain fact ...` decision explanation UX가 들어갔어. 로컬 Hermes hook도 v0.1.30 runtime으로 업데이트되어 doctor/hook smoke가 통과한 상태야.

현재 slice는 retrieval evaluation이 실제 retrieval path를 쓰되 eval 실행 자체가 `retrieval_count`, `reinforcement_count`, `last_accessed_at`를 mutate하지 않게 만드는 determinism hardening이야. 목적은 fixture 순서나 반복 실행이 이후 ranking 결과를 흔들지 않게 하는 것.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- branch: `main`
- HEAD: `5011d99 chore: release v0.1.30 [skip release] (#28)`
- tag/release: `v0.1.30`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.30`
- npm: `@cafitac/agent-memory@0.1.30`
- PyPI: `cafitac-agent-memory==0.1.30`
- v0.1.30 published smoke artifact: passed; includes npm/uvx/pipx Hermes hook commands.

Active slice/worktree:

- branch: `fix/retrieval-eval-deterministic-ordering`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/retrieval-eval-deterministic-ordering`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.30

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- main merge auto-release is active but protected `main` can block release metadata write-back; if that happens, use release-sync PR + tag push.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28+ smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.30/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
- Hermes hook fails closed: unavailable DB/schema returns `{}` and exit 0 instead of breaking prompt flow.
- Conservative preset remains default: small prompt budgets, one top memory, no alternative-memory detail, no reason-code noise.
- `--preset balanced` is explicit opt-in for more context/noise.

### Truth lifecycle readiness

- Normal retrieval is approved-only by default.
- Candidate/disputed/deprecated facts remain available only behind explicit forensic/review surfaces.
- `memory_status_transitions` records status changes with from/to status, reason, actor, evidence IDs, and timestamp.
- `agent-memory review history fact|procedure|episode ...` exposes transition history.
- `agent-memory review supersede fact <db> <old> <new>` records fact replacement as a relation edge.
- Replacement relation direction: `fact:<old> --superseded_by--> fact:<new>`.
- Superseding a fact deprecates the old fact and approves the replacement fact, preserving reason/actor/evidence in transition history.
- `agent-memory review replacements fact ...` exposes replacement chains.
- `agent-memory review explain fact ...` explains status, default retrieval visibility, same claim-slot alternatives, replacement chain, and review follow-up commands.

## Current slice: retrieval-eval deterministic ordering hardening

Planned behavior:

- `evaluate_retrieval_fixtures(...)` continues to call the real `retrieve_memory_packet(...)` path.
- Evaluation runs suppress retrieval bookkeeping writes so repeated evals and fixture order cannot change future ranking via reinforcement state.
- Normal runtime retrieval still records approved memory retrievals by default.

Implementation direction:

- Add/keep a default-on `record_retrievals` option on `retrieve_memory_packet(...)`.
- Call `retrieve_memory_packet(..., record_retrievals=False)` from `core/retrieval_eval.py`.
- Test that eval does not mutate `retrieval_count`, `reinforcement_count`, or `last_accessed_at`.

## Verification checklist for this slice

Run from the active worktree:

```bash
uv run pytest tests/test_retrieval_evaluation.py::test_evaluate_retrieval_fixtures_does_not_mutate_retrieval_counters -q
uv run pytest tests/test_retrieval_evaluation.py tests/test_retrieval_trace.py tests/test_hermes_adapter.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
node --check bin/agent-memory.js
```

Before PR, run a static diff secret scan and confirm finding_count 0.

## PR/release notes

This slice should be a patch release candidate, likely v0.1.31 after PR merge. If protected `main` blocks auto-release write-back again, use the existing release-sync PR + tag push workaround.

After release, verify GitHub Release/npm/PyPI/published-install-smoke and update the local Hermes runtime only if the release contains runtime-relevant package changes. This slice changes retrieval/eval behavior in the Python package, so a v0.1.31 runtime update is still preferred for dogfood parity.

## Next likely slices after this

1. Release workflow protected-main automation/fallback improvement.
2. Actual Hermes dogfood observations and noise/latency notes.
3. Graph foundation read-only slice: graph inspection CLI or bounded relation traversal eval fixtures.
4. PyPI Trusted Publisher later; user deferred it.
