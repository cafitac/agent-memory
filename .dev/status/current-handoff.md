# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-05 18:03 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory is currently verified through `v0.1.74`: PR #132 (read-only `dogfood trace-quality`), release-sync PR #133, GitHub Release, npm, PyPI, published install smoke, pinned local Hermes runtime install, live Hermes E2E, and `hermes hooks doctor` are complete. The active runtime is `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`, and `/Users/reddit/.hermes/config.yaml` points to the live DB at `/Users/reddit/.agent-memory/memory.db`. Storage-health, query-preview cleanup preview, and trace-quality now make live DB invariants, legacy stored-query-excerpt cleanup scope, and trace usefulness inspectable without ad hoc SQL, raw query leakage, or mutation. The live 24h trace-quality report currently recommends `continue_dogfooding`, so the next recommended PR-sized slice is G3e: collect scheduled dry-run dogfood reports over time before any G4 apply-mode planning.

## Current next slice

Next slice: G3e scheduled dry-run dogfood reports.

Goal: collect several read-only background consolidation and dogfood quality reports over time so the decision to continue, tune, or plan G4 is data-backed.

Candidate manual command shape:

```bash
agent-memory consolidation background dry-run /Users/reddit/.agent-memory/memory.db \
  --limit 200 \
  --top 20 \
  --min-evidence 2 \
  --output /Users/reddit/.agent-memory/reports/background-consolidation-YYYYMMDD-HHMMSS.json \
  --lock-path /Users/reddit/.agent-memory/background-consolidation.lock

agent-memory dogfood background-dry-run /Users/reddit/.agent-memory/memory.db \
  --report /Users/reddit/.agent-memory/reports/background-consolidation-YYYYMMDD-HHMMSS.json \
  --output /Users/reddit/.agent-memory/reports/background-quality-YYYYMMDD-HHMMSS.json
```

Expected scope:

- run/read-only report generation with lock safety;
- aggregate multiple report outputs over time;
- explain whether candidate signals remain sparse/noisy or are becoming stable;
- keep privacy checks clean;
- optionally add a cron-ready wrapper only if it remains dry-run/no-mutation.

Do not implement cleanup apply mode, G4 apply mode, ordinary-conversation auto-approval, raw transcript storage, broad preference inference, or default retrieval ranking changes yet.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should normally be on `main` unless a docs/feature branch is active.
- Latest merged release-sync PR: #133 `chore: release v0.1.74 [skip release]`.
- Latest completed release: `v0.1.74`.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for `gh` commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.74`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.74`
- npm package: `@cafitac/agent-memory@0.1.74`
- PyPI package: `cafitac-agent-memory==0.1.74`
- Current Hermes runtime path: `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`
- Hermes config path: `/Users/reddit/.hermes/config.yaml`
- Hermes config backup before v0.1.74 path update: `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.74-20260505180302`
- `hermes hooks doctor` reports all shell hooks healthy.

Latest raw-content-safe live DB snapshot, checked 2026-05-05 18:03 KST:

- `retrieval_observations`: 772, latest `2026-05-05 09:03:31` UTC
- `memory_activations`: 677, latest `2026-05-05 09:03:31` UTC
- `experience_traces`: 91, latest `2026-05-05 09:03:31` UTC
- `facts`: 3, latest `2026-04-30 17:26:00` UTC
- `procedures`: 0
- `episodes`: 0
- `relations`: 0
- legacy non-empty `query_preview` rows: 70, latest `2026-05-01 12:57:54` UTC
- non-empty `query_preview` rows since the v0.1.69 privacy-safe live path window: 0

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/`

Do not delete or commit these unless the user explicitly asks.

## Completed v0.1.74 trace-quality release

PR #132 `feat: add dogfood trace quality report` merged and released through release-sync PR #133.

Completed behavior:

- New command: `agent-memory dogfood trace-quality <db> --since-hours <hours> --min-trace-coverage <ratio> --min-evidence-count <count>`.
- The report opens SQLite read-only and emits `kind=dogfood_trace_quality`, `read_only=true`, `mutated=false`.
- It reports aggregate observation/trace/activation coverage, observation-to-trace coverage ratio, empty-retrieval ratio, repeated memory-ref counts, trace event-kind and retention-policy distributions, ordinary metadata-only invariants, metadata JSON validity, candidate-signal proxy counts, warnings, and recommendation.
- It never prints raw conversation content, raw queries, raw trace summaries, prompts, transcripts, API keys, token-like values, or sample values.
- It does not create candidates/approvals, mutate rows, alter retrieval ranking, or change hook behavior.
- Live 24h v0.1.74 smoke returned `status=warning`, `recommendation=continue_dogfooding`, `observation_count=174`, `trace_count=87`; the warning is expected because recent observations are not linked from traces strongly enough yet.

Verification completed:

- Focused trace-quality test passed.
- `tests/test_cli.py` passed.
- Full `tests/` passed: `247 passed`.
- Targeted ruff passed on `src/agent_memory/api/cli.py` and `tests/test_cli.py`.
- PR #132 CI passed and merged.
- PR #133 release-sync validation CI passed and merged.
- GitHub Release `v0.1.74`, npm `@cafitac/agent-memory@0.1.74`, and PyPI `cafitac-agent-memory==0.1.74` verified.
- Published install smokes passed for npm, PyPI fresh venv, and `uvx --refresh`.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reports all shell hooks healthy.

## Completed v0.1.70-v0.1.71 remember-intent diagnostics release

PR #122 `feat: add debuggable remember intent diagnostics` merged and released through v0.1.70. PR #124 `fix: reject freeform secret-like remember intents` then hardened the secret scanner and released through v0.1.71.

Completed behavior:

- Korean explicit remember prefixes (`기억해둬:`, `기억해줘:` plus spaced/full-width-colon variants) are recognized as review-ready `remember_intent` traces when content passes secret scanning.
- Safe explicit remember requests store a sanitized human-readable summary so reviewers can see the explicit request without storing ordinary raw conversation turns.
- Secret-like explicit remember requests store only a rejected metadata-only diagnostic: `candidate_policy=rejected`, `secret_scan=blocked`, `rejected_reason=secret_like_text`, `summary=NULL`.
- Freeform secret labels such as `api key <value>` are rejected even without `:` or `=`.
- `agent-memory dogfood remember-intent` reports safe `rejection_counts` without raw prompt/query/user-message leakage.
- Ordinary conversation still records only hash/metadata evidence and does not create approved facts/procedures/episodes.

Verification completed:

- PR #122 CI passed and merged.
- PR #123 release-sync merged and published v0.1.70.
- Published smoke for v0.1.70 found the freeform secret-like scanner gap before live runtime rollout.
- PR #124 added regression coverage for the freeform gap, CI passed, and merged.
- PR #125 release-sync merged and published v0.1.71.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.71` plus Korean safe remember and secret-like rejected diagnostics.
- npm `npm exec --package=@cafitac/agent-memory@0.1.71` smoke verified command/help surfaces.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.71/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool` returned `OK` and advanced observations, activations, and metadata-only ordinary traces without changing facts.
- `hermes hooks doctor` reports all hooks healthy.

## Completed v0.1.69 empty-context trace hotfix

PR #120 `chore: release v0.1.69 [skip release]` merged after commit `fix: record hermes turn traces before empty context return` landed on main.

- Root cause: v0.1.68 recorded ordinary metadata-only traces after checking whether rendered memory context was empty, so no-injected-context turns could store retrieval observations/activations without storing an ordinary `experience_traces` row.
- Fix: call `_record_pre_llm_experience_trace(...)` before `if not context.prompt_text.strip(): return {}`. Hook output remains `{}` when no memory context is injected.
- Regression test: `test_hermes_pre_llm_hook_records_trace_even_when_no_context_is_injected`.
- CI passed on the feature commit and release-sync PR.
- GitHub Release `v0.1.69` published.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.69`.
- Clean npm temp-dir smoke verified `@cafitac/agent-memory@0.1.69`.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.69/.venv/bin/agent-memory` and `/Users/reddit/.hermes/config.yaml` now points to it.
- `hermes hooks doctor` reports all shell hooks healthy.
- Real Hermes chat smoke recorded one new retrieval observation, one activation, and one metadata-only ordinary trace; latest ordinary trace has `summary=NULL`, `retention_policy=ephemeral`, `candidate_policy=evidence_only`, and `auto_approved=false`. Latest retrieval observations keep `query_preview` empty.

## Completed Stage G/G3a slice

PR #114 `feat: add background dry-run dogfood gates` merged and released in v0.1.67. Release-sync PR #115 merged.

- New command: `agent-memory dogfood background-dry-run <db> --report <json> [--output <path>]`.
- It evaluates one or more saved G3 background dry-run JSON reports into aggregate quality gates.
- Output kind is `background_dry_run_dogfood_report` with `read_only=true`, `mutated=false`, and `default_retrieval_unchanged=true`.
- It summarizes only secret-safe report metadata, per-report counts, warnings, and gate decisions; it does not echo raw report payloads, raw prompts, transcripts, query previews, tokens, or credentials.
- Conservative gate decision `continue_dry_run_dogfooding_before_g4` is expected when reports are sparse/noisy; passing the gate is advisory and does not enable apply mode.
- G3a does not mutate DB rows, create facts/relations/traces/retrieval observations, infer ordinary conversation preferences, or change Hermes/default retrieval behavior.

Verification completed for G3a/v0.1.67:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'dogfood_background_dry_run'
# 2 passed, 73 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'dogfood_background_dry_run or background_dry_run or dogfood or remember_intent or consolidation or activation or reinforcement or decay_risk'
# 14 passed, 66 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 239 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #114 CI succeeded and merged. A push-event CI run initially hit a known flaky retrieval-eval fixture assertion, while the pull_request run passed; an empty retry commit made both push and pull_request checks pass.
- Release-sync PR #115 validation workflow_dispatch CI succeeded and merged.
- GitHub Release `v0.1.67` published.
- npm registry shows `@cafitac/agent-memory@0.1.67`; clean `npm exec --package=@cafitac/agent-memory@0.1.67` smoke verified G3 + G3a command surfaces after normal PyPI/uvx propagation lag.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.67`, G3 background dry-run, and G3a background-dry-run dogfood report.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.67/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.67.
- Direct `hermes-pre-llm-hook` smoke succeeded.
- Runtime G3a live dogfood smoke against the latest saved local report succeeded with read-only/no-mutation/default-retrieval-unchanged assertions.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.67 agent-memory pre-LLM hook.

## Completed Stage G/G3b slice

PR #117 `feat: record ordinary Hermes turn traces` merged and released in v0.1.68. Release-sync PR #118 merged.

- Real non-synthetic Hermes pre-LLM turns now record metadata-only `turn` traces by default.
- Ordinary trace rows use `surface=hermes-pre-llm-hook`, `event_kind=turn`, low salience, `retention_policy=ephemeral`, and metadata `trace_recording=default_metadata_only`, `candidate_policy=evidence_only`, `auto_approved=false`.
- Trace storage remains secret-safe: no raw prompt, raw query, query preview, transcript, user message, or secret-like text is stored or printed.
- Synthetic Hermes doctor/test payloads are skipped.
- Trace write failures remain non-blocking; `--no-record-trace` disables runtime trace recording for a hook invocation.
- Ordinary turns do not create facts/procedures/episodes, do not auto-approve memories, and do not change default retrieval ranking.

Verification completed for G3b/v0.1.68:

- Focused tests: `23 passed, 54 deselected`.
- Full suite: `241 passed`.
- Release readiness: `git diff --check`, `scripts/check_release_metadata.py`, `scripts/smoke_release_readiness.py`, `npm pack --dry-run`, and `node --check bin/agent-memory.js` passed.
- GitHub PR #117 checks passed; main CI after merge passed.
- Release-sync PR #118 main CI and auto-release passed.
- GitHub Release `v0.1.68` published.
- npm smoke verified `@cafitac/agent-memory@0.1.68` can record metadata-only ordinary turn traces through the public wrapper after normal PyPI/uvx propagation.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.68` and metadata-only ordinary turn traces.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up to `/Users/reddit/.hermes/config.yaml.bak-v0.1.68` before updating the hook path to v0.1.68.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK` and recorded a metadata-only ordinary `turn` trace.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.68 agent-memory pre-LLM hook.

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

Completed through v0.1.68:

- Stage C: activation evidence, activation summary, reinforcement report, decay risk report.
- Stage D: read-only consolidation candidates and `consolidation explain`.
- Stage E: manual reviewed promotion, promotion audit/report, lineage, conflict/supersession preflight and relation edges.
- Stage F: retrieval policy/ranker/decay/graph-neighborhood preview surfaces.
- Stage G/G1: explicit remember-intent review trace.
- Stage G/G1a: remember-intent dogfood report.
- Stage G/G2: narrow opt-in remember-preference auto-approval.
- Stage G/G3: cron-friendly background consolidation dry-run report.
- Stage G/G3a: read-only dogfood quality gates over saved G3 reports.

Open candidates:

- Keep dogfooding G3/G3a dry-run reports on the real local DB and define stricter quality gates/noise thresholds before G4.
- Stage G/G4 background apply mode, only after explicit policy/audit/rollback design.
- Stage H eval/visualization/backup/public docs hardening.

## Useful commands

```bash
cd /Users/reddit/Project/agent-memory

git status --short --branch
git tag --sort=-version:refname | head -5
HOME=/Users/reddit gh pr list --repo cafitac/agent-memory --state open --json number,title,headRefName,url
HOME=/Users/reddit gh run list --repo cafitac/agent-memory --limit 10

/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory consolidation background dry-run /Users/reddit/.agent-memory/memory.db \
  --limit 200 \
  --top 20 \
  --min-evidence 2 \
  --output /Users/reddit/.agent-memory/reports/background-dry-run.json \
  --lock-path /Users/reddit/.agent-memory/background-dry-run.lock

/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory dogfood background-dry-run /Users/reddit/.agent-memory/memory.db \
  --report /Users/reddit/.agent-memory/reports/background-dry-run.json \
  --output /Users/reddit/.agent-memory/reports/background-dry-run-quality.json
```

## Safety rails

- Do not expose secrets/tokens/connection strings; redact as `[REDACTED]`.
- Do not store raw prompts/transcripts/query previews as durable memory artifacts.
- Do not enable ordinary conversation auto-approval.
- Do not change default retrieval/Hermes hook ranking as part of background consolidation.
- Treat G4/background apply as a separate high-risk slice requiring a new RED-tested plan.
- Preserve local-only untracked files listed above.
