# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-04 16:46 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.66까지 PR/CI/merge/release/npm/PyPI/published smoke/Hermes QA가 완료됐다. Stage G/G3 background consolidation dry-run도 완료되어 cron-friendly/read-only/report-only wrapper `agent-memory consolidation background dry-run`을 제공한다. 다음 문서상 후보는 G4 background consolidation apply mode지만, 자동 적용은 위험도가 높으므로 먼저 G3 dry-run report를 실제 dogfood DB/cron에서 며칠 운영하며 lock/노이즈/추천 품질을 관찰하거나, G1-G3 신호를 함께 측정하는 eval/dogfood slice를 진행하는 편이 안전하다.

## Current in-progress slice

Stage G/G3a dogfood quality-gate slice is in progress on branch/worktree:

- Branch: `feat/g3-dogfood-quality-gates`
- Worktree: `/Users/reddit/Project/agent-memory/.worktrees/g3-dogfood-quality-gates`

Goal: add a read-only `agent-memory dogfood background-dry-run <db> --report <json>` evaluator that summarizes saved G3 dry-run reports into conservative quality gates before any G4 apply-mode plan.

Recommended next slice after this merges:

- Preferred conservative path: keep collecting G3/G3a reports on the real local DB and use the quality-gate output to write a separate G4 plan only if reports are clean.
- Alternative roadmap path: Stage G/G4 background consolidation apply mode, but only behind explicit flags/policy/audit/rollback and after a fresh RED-tested plan.

Do not broaden the completed G2/G3 slices into procedures, inferred preferences from ordinary conversation, background apply mode, or default retrieval ranking changes without a new RED-tested roadmap slice.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main`.
- `main` and `origin/main` include v0.1.66 release-sync PR #112.
- No active feature worktree is required after G3 cleanup.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.66`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.66`
- npm package: `@cafitac/agent-memory@0.1.66`
- PyPI package: `cafitac-agent-memory==0.1.66`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.66/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.66.
- Hermes config backup before this update: `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.66-20260504161000`.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`

Do not delete or commit these unless the user explicitly asks.

## Completed Stage G/G3 slice

PR #111 `feat: add background consolidation dry run` merged and released in v0.1.66. Release-sync PR #112 merged.

- New command: `agent-memory consolidation background dry-run <db> [--output <path>] [--lock-path <path>]`.
- It bundles read-only `consolidation candidates`, `activations summary`, `activations reinforcement-report`, and `activations decay-risk-report` into one cron-friendly JSON report.
- It uses a non-blocking file lock; overlapping runs exit zero with `status: skipped_lock_busy` and write a readable skipped report when `--output` is supplied.
- It is report-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, no apply mode, and no fact/source/relation/status/trace/retrieval-observation mutation.
- Failure reports are readable JSON and do not introduce memory mutations.
- G3 does not infer from ordinary conversation and does not change default retrieval/Hermes hook behavior.

Verification completed for G3/v0.1.66:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'background_dry_run'
# 2 passed, 71 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'background_dry_run or consolidation or activation or reinforcement or decay_risk or remember_intent'
# 10 passed, 68 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 237 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #111 CI succeeded and merged.
- Release-sync PR #112 validation succeeded and merged.
- GitHub Release `v0.1.66` published.
- npm registry shows `@cafitac/agent-memory@0.1.66`.
- PyPI JSON and fresh install show `cafitac-agent-memory==0.1.66`; first pip install attempt hit normal index propagation lag, retry succeeded.
- PyPI fresh venv smoke verified G3 background dry-run on a seeded temp DB and confirmed no facts/source records were created.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.66` smoke verified the G3 command surface.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.66/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.66.
- Runtime G3 background dry-run smoke succeeded on a temp DB.
- `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.66 agent-memory pre-LLM hook.

## Completed Stage G/G2 slice

PR #108 `feat: add remember preference auto approval` merged and released in v0.1.65. Release-sync PR #109 merged.

- New command: `agent-memory consolidation auto-approve remember-preferences <db> --policy remember-preferences-v1 --scope <scope>`.
- Default mode is dry-run/read-only and reports `would_approve` candidates without mutation.
- Apply mode requires explicit `--apply --actor ... --reason ...`.
- Eligible rows are explicit/review-ready `remember_intent` traces in the selected scope with sanitized summaries shaped like `User prefers ...` or `I prefer ...`.
- The only auto-approved memory shape is `fact(user, prefers, <value>, <scope>)`.
- Guardrails block secret-like summaries, unsupported summary shapes, non-selected scopes, ordinary turns, and claim-slot conflicts.
- Successful apply writes approval/status history and an `auto_approved_as` relation from the trace to the fact.
- Default retrieval and Hermes hook ranking behavior remain unchanged.

Verification completed for G2/v0.1.65:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'auto_approve_remember_preferences or remember_intent'
# 6 passed, 65 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'auto_approve_remember_preferences or dogfood or remember_intent or hermes_pre_llm_hook or experience_trace or consolidation'
# 24 passed, 52 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 235 passed
```

## Completed Stage G/G1a slice

PR #105 `feat: add remember intent dogfood report` merged and released in v0.1.64. Release-sync PR #106 merged.

- New command: `agent-memory dogfood remember-intent <db> --limit 200 --sample-limit 10`.
- Output kind is `remember_intent_dogfood_report` with `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`.
- The report counts inspected traces, `remember_intent` traces, ordinary turn traces, review-ready traces, unsafe samples, and remember-intent scopes.
- Samples include safe sanitized summaries plus compact policy flags only; raw metadata, raw prompts/transcripts, and secret-like summaries are omitted.
- No facts/procedures/episodes, relations, status transitions, candidates, approvals, retrieval observations, or hook behavior are mutated.

## Completed Stage G/G1 slice

PR #102 `feat: add explicit remember intent traces` merged and released in v0.1.63.

- Existing Hermes trace recording remains disabled unless `--record-trace` is enabled.
- With `--record-trace`, explicit `Remember this:` / `Please remember:` messages that pass the conservative secret-like scan are recorded as `experience_traces.event_kind=remember_intent`.
- G1 rows use `retention_policy=review`, high salience/user emphasis, sanitized summary only, hashed session/content refs, and metadata `candidate_policy=review_required`, `auto_approved=false`.
- Secret-like remember requests fall back to ordinary hash-only ephemeral turn traces and do not create remember review traces.
- No facts/procedures/episodes are created or approved automatically; review remains through `consolidation candidates` and `consolidation explain`.

## Current north-star / open roadmap

The north-star remains a human-memory-like lifecycle:

1. Lightweight traces/observations, without storing raw transcripts forever.
2. Activation/reinforcement reports from repeated use, usefulness, recency, and graph connectivity.
3. Consolidation candidates that are explainable and reviewable.
4. Manual or narrow opt-in approval into long-term graph memory.
5. Lifecycle edges for reinforcement, conflict, supersession, decay risk, and audit history.
6. Conservative background/reporting jobs before any background apply mode.

Completed through v0.1.66:

- Stage C: activation evidence, activation summary, reinforcement report, decay risk report.
- Stage D: read-only consolidation candidates and `consolidation explain`.
- Stage E: manual reviewed promotion, promotion audit/report, lineage, conflict/supersession preflight and relation edges.
- Stage F: retrieval policy/ranker/decay/graph-neighborhood preview surfaces.
- Stage G/G1: explicit remember-intent review trace.
- Stage G/G1a: remember-intent dogfood report.
- Stage G/G2: narrow opt-in remember-preference auto-approval.
- Stage G/G3: cron-friendly background consolidation dry-run report.

Open candidates:

- Finish Stage G/G3a: `dogfood background-dry-run` read-only quality gate over saved G3 reports.
- Dogfood G3/G3a dry-run reports on the real local DB and define quality gates/noise thresholds.
- Stage G/G4 background apply mode, only after explicit policy/audit/rollback design.
- Stage H eval/visualization/backup/public docs hardening.

## Useful commands

```bash
cd /Users/reddit/Project/agent-memory

git status --short --branch
git tag --sort=-version:refname | head -5
HOME=/Users/reddit gh pr list --repo cafitac/agent-memory --state open --json number,title,headRefName,url
HOME=/Users/reddit gh run list --repo cafitac/agent-memory --limit 10

/Users/reddit/.agent-memory/runtime/v0.1.66/.venv/bin/agent-memory consolidation background dry-run /Users/reddit/.agent-memory/memory.db \
  --limit 200 \
  --top 20 \
  --min-evidence 2 \
  --output /Users/reddit/.agent-memory/reports/background-dry-run.json \
  --lock-path /Users/reddit/.agent-memory/background-dry-run.lock
```

## Safety rails

- Do not expose secrets/tokens/connection strings; redact as `[REDACTED]`.
- Do not store raw prompts/transcripts/query previews as durable memory artifacts.
- Do not enable ordinary conversation auto-approval.
- Do not change default retrieval/Hermes hook ranking as part of background consolidation.
- Treat G4/background apply as a separate high-risk slice requiring a new RED-tested plan.
- Preserve local-only untracked files listed above.
