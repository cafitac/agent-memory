# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 16:30 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

지금 agent-memory는 OSS 기본 메모리 레이어 신뢰도 작업 Priority 1~3을 대부분 마쳤고, Priority 4 `Conflict, obsolete, and truth lifecycle`를 진행 중이야.

완료된 최신 공개 릴리스는 v0.1.29야. v0.1.27에서 status transition history가 들어갔고, v0.1.28에서 npm wrapper stdin forwarding과 published smoke의 Hermes hook QA 경로가 보강됐고, v0.1.29에서 fact supersession/replacement relation이 들어갔어.

현재 slice는 `feat: explain conflict review decisions`야. 목적은 reviewer가 특정 fact가 default retrieval에 보이는지/숨겨지는지, 왜 disputed/deprecated 되었는지, 어떤 같은 claim-slot 대안과 replacement chain이 있는지를 한 번에 설명받도록 `agent-memory review explain fact ...` forensic UX를 추가하는 것.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- branch: `main`
- HEAD: `e102865 chore: release v0.1.29 [skip release]`
- tag/release: `v0.1.29`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.29`
- npm: `@cafitac/agent-memory@0.1.29`
- PyPI: `cafitac-agent-memory==0.1.29`
- v0.1.29 published smoke artifact: passed; includes npm/uvx/pipx Hermes hook commands.

Active slice/worktree:

- branch: `feat/conflict-decision-explanations`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/conflict-decision-explanations`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.29

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- main merge auto-release is active but protected `main` can block release metadata write-back; if that happens, use release-sync PR + tag push.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads `published-install-smoke-result` JSON artifact with success/failure diagnostics.
- v0.1.28+ smoke covers npm/npx/npm-exec/uvx/pipx and Hermes hook stdin payload handling.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.29/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
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

## Current slice: explain conflict review decisions

Planned behavior:

```bash
agent-memory review explain fact "$DB" <fact_id>
```

Expected JSON payload:

- `fact`: the selected fact.
- `decision`: current status, whether it is visible in default retrieval, and a short summary.
- `claim_slot`: same subject/predicate/scope alternatives plus status counts.
- `history`: transition history with reason/actor/evidence.
- `replacement_chain`: superseded-by and replaces relation edges.
- `default_retrieval_policy`: `approved_only`.

This is a small UX layer on top of v0.1.27 transition history and v0.1.29 supersession relation. It should not change retrieval behavior.

## Verification checklist for this slice

Run from the active worktree:

```bash
uv run pytest tests/test_cli.py::test_python_module_cli_review_explain_fact_shows_decision_context -q
uv run pytest tests/test_review_and_scope_ranking.py tests/test_cli.py -q
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
git diff --check
```

Before commit, scan the diff for secrets/tokens/credentials and preserve local-only untracked files.

## Recommended next work after this slice

1. Retrieval eval determinism/flake hardening.
   - v0.1.25/v0.1.26 had historical one-off retrieval eval verify failures that passed on rerun.
   - Tighten ordering, fixtures, and failure diagnostics before deeper graph traversal.
2. Release workflow protected-main improvement.
   - Auto-release direct push still fails under current rules.
   - Either codify release-sync PR fallback or adjust permissions/rulesets safely.
3. Graph-centered foundation.
   - Entity/Concept canonicalization.
   - relation edge traversal.
   - graph inspection CLI.
   - graph retrieval eval fixtures.
   - depth/drift controls.
4. Long-run Hermes dogfood/noise monitoring.
   - The v0.1.29 hook is live locally, so collect latency/noise/quality observations before raising prompt-context budgets.

## Known operational issues

- Protected `main` blocks auto-release write-back. Established workaround:
  1. create `release-sync/vX.Y.Z` branch from `origin/main`,
  2. run `scripts/bump_release_version.py --patch`,
  3. run `uv lock`, tests/readiness/npm dry-run/diff checks,
  4. open/merge `chore: release vX.Y.Z [skip release]` PR,
  5. push annotated tag `vX.Y.Z`,
  6. verify publish workflow, registries, GitHub Release, and smoke artifact.
- PyPI Trusted Publisher is deferred by user preference.
- Do not expose secrets/tokens/API keys. If encountered, redact as `[REDACTED]`.
