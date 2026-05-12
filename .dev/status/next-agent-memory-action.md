# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-12 21:31 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.139`; the installed Hermes hooks are healthy on the v0.1.139 runtime, fresh linkage diagnostics no longer show a hook linkage bug, G5a/G5b are merged for ref-safe trace-cluster previews plus explicit reviewed trace-candidate persist/list/update/apply, and the current `g5c-trace-candidate-scoring` branch adds read-only review scoring/recommendations to those ref-safe clusters while broad G4/background apply remains blocked.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 56-59%.
- Substrate/evidence plumbing: about 72%.
- Safe automatic mutation/promotion: about 38-42%.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, merged G5b reviewed trace-candidate flow for explicit fact/preference/procedure promotion, and current G5c source work that scores/refines ref-safe clusters for human review without mutation.
- Not done: broad background consolidation apply, automatic long-term memory promotion, conflict-aware automatic supersession, weak-trace decay/collapse apply, automatic graph-cluster-to-fact/procedure/preference generation, and large-scope rollback confidence.

## Latest verified checkpoint

- Release: `v0.1.139`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.139`
- npm: `@cafitac/agent-memory@0.1.139`
- PyPI: `cafitac-agent-memory==0.1.139`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.139/.venv/bin/agent-memory`
- Hermes config backups from rollout: `/Users/reddit/.hermes/config.yaml.agent-memory-v0138-backup-20260512-132119` plus matching `personal-oss`, `earlypay`, and `infra-admin` profile backups.
- Fresh report directory: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`
- Fresh linkage diagnosis: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json`
- Fresh epoch readiness: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`
- Fresh review queue preview: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`
- Historical scheduled dry-run: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`
- Source G5a/G5b checkpoint: `dogfood trace-cluster-preview` and `dogfood trace-candidate-persist/list/update/apply` are merged through PR #294/#295; v0.1.139 smoke passes.
- Current G5c source checkpoint: branch `g5c-trace-candidate-scoring`, commit `aabc145`, adds `review_score` and `review_recommendation` to ref-safe trace clusters; full suite `294 passed, 1 xfailed`.

## Current blocker

Fresh v0.1.139 runtime plus v0.1.138 fresh telemetry evidence are healthy enough for G4 planning:

- `g4-linkage-gap-diagnose-v0138-fresh.json`: quality gate pass, decision `fresh_trace_linkage_gap_not_detected`, observation/trace linkage coverage `1.0`, unlinked observations `0`.
- `fresh-epoch-v0138.json`: quality gate pass, decision `fresh_epoch_ready_to_compare_against_historical`.
- `g4-review-queue-preview-v0138-fresh.json`: quality gate pass, decision `review_queue_ready_for_manual_review`, `read_only=true`, `mutated=false`.

However, historical scheduled-dry-run still blocks broad G4/background apply on:

- `trace_quality_needs_more_dogfooding`
- `decay_risk_above_threshold`
- `background_quality_warnings_present`

Interpretation: this is no longer a fresh hook linkage bug. It is historical telemetry/review debt plus still-narrow mutation safety work.

## Recommended next work

Proceed in this sequence:

1. Finish G5c: push `g5c-trace-candidate-scoring` and open a PR for read-only trace-cluster review scoring/recommendations.
2. Keep G5c semantics narrow: scoring is only a ref-safe review-priority signal (`review_score`, `review_recommendation`); it does not persist review state, promote memories, auto-approve ordinary conversation, or change retrieval defaults.
3. Next safe source slice after G5c is repeated activation -> reinforcement refinement, still as preview/review-only unless an explicit narrow apply policy is added with backup/audit/rollback.
4. G4 broad apply contract remains blocked/guardrail-only. Required future shape: explicit policy, approval phrase, actor, reason hash, backup path, expected queue ids/hash, audit row, rollback hint, raw-content exclusion, and ordinary-conversation auto-approval forbidden.
5. Historical telemetry reconciliation remains a separate reviewed `telemetry-reset-v1` corridor for historical telemetry rows older than a chosen epoch; never delete facts/procedures/episodes/relations/source records/status history.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, or G5c review scores as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating G5c scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.139까지 릴리즈/설치/스모크가 끝났고 fresh linkage에서는 `fresh_trace_linkage_gap_not_detected`라서 hook linkage 버그 막힘은 풀렸어요. G5a/G5b는 merged/released, 현재 G5c는 ref-safe review scoring만 추가하는 read-only 브랜치입니다. 그래도 broad G4/background apply는 historical scheduled-dry-run debt 때문에 아직 막혀 있습니다. 다음은 G5c PR을 마무리하고, 그 다음 repeated activation -> reinforcement를 review/preview-first로 진행하는 게 맞습니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.139/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.139/.venv/bin/agent-memory dogfood g4-linkage-gap-diagnose   /Users/reddit/.agent-memory/memory.db   --epoch-start 2026-05-12T04:21:00Z   --surface hermes-pre-llm-hook   --output /tmp/agent-memory-next-g4-linkage-gap-diagnose.json
```

Expected: read-only/no-mutation. Fresh linkage should remain `fresh_trace_linkage_gap_not_detected`; broad apply remains blocked until the reviewed contract/reconciliation/apply runway is explicitly completed.
