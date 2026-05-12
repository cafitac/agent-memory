# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-12 22:20 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.140`; the installed Hermes hooks are healthy on the v0.1.140 runtime, fresh linkage diagnostics no longer show a hook linkage bug, G5a/G5b/G5c are merged for ref-safe trace-cluster previews, explicit reviewed trace-candidate persist/list/update/apply, and read-only review scoring/recommendations, while broad G4/background apply remains blocked.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 58-60%.
- Substrate/evidence plumbing: about 73%.
- Safe automatic mutation/promotion: about 40-43%.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, merged G5b reviewed trace-candidate flow for explicit fact/preference/procedure promotion, and merged/released G5c scoring that ranks/refines ref-safe clusters for human review without mutation.
- Not done: broad background consolidation apply, automatic long-term memory promotion, conflict-aware automatic supersession, weak-trace decay/collapse apply, automatic graph-cluster-to-fact/procedure/preference generation, and large-scope rollback confidence.

## Latest verified checkpoint

- Release: `v0.1.140`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.140`
- npm: `@cafitac/agent-memory@0.1.140`
- PyPI: `cafitac-agent-memory==0.1.140`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.140/.venv/bin/agent-memory`
- Hermes config backups from rollout: `/Users/reddit/.hermes/config.yaml.agent-memory-v0138-backup-20260512-132119` plus matching `personal-oss`, `earlypay`, and `infra-admin` profile backups.
- Fresh report directory: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`
- Fresh linkage diagnosis: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json`
- Fresh epoch readiness: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`
- Fresh review queue preview: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`
- Historical scheduled dry-run: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`
- Source G5a/G5b/G5c checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, and read-only `review_score`/`review_recommendation` are merged through PR #294/#295/#297 and released through v0.1.140.
- G5d source checkpoint on this branch: `dogfood reinforcement-refinement-preview` adds a read-only repeated activation -> reinforcement refinement preview. It reuses activation reinforcement evidence, emits ref-safe `review_score`/`review_recommendation`, and keeps mutation unsupported (`apply_supported=false`, `mutated=false`, default retrieval unchanged). It is intended for the next release after v0.1.140.
- Release/published-install smoke passed; runtime rollout is doctor-green across default, personal-oss, earlypay, and infra-admin Hermes profiles.

## Current blocker

Fresh v0.1.140 runtime plus v0.1.138 fresh telemetry evidence are healthy enough for G4 planning:

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

1. Land/release the G5d source slice: repeated activation -> reinforcement refinement preview, still preview/review-first by default.
2. Keep G5d semantics narrow in any follow-up: `review_score` and `review_recommendation` are only ref-safe review-priority signals; they do not persist review state, increment reinforcement counts, promote memories, auto-approve ordinary conversation, or change retrieval defaults.
3. If a later G5d apply slice needs mutation, add only a separate explicit narrow apply policy with backup/audit/rollback; generic continuation does not authorize it.
4. G4 broad apply contract remains blocked/guardrail-only. Required future shape: explicit policy, approval phrase, actor, reason hash, backup path, expected queue ids/hash, audit row, rollback hint, raw-content exclusion, and ordinary-conversation auto-approval forbidden.
5. Historical telemetry reconciliation remains a separate reviewed `telemetry-reset-v1` corridor for historical telemetry rows older than a chosen epoch; never delete facts/procedures/episodes/relations/source records/status history.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, or G5c review scores as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating G5c scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.140까지 릴리즈/설치/스모크가 끝났고 fresh linkage에서는 `fresh_trace_linkage_gap_not_detected`라서 hook linkage 버그 막힘은 풀렸어요. G5a/G5b/G5c는 merged/released이고, G5c는 ref-safe review scoring만 추가한 read-only 단계였습니다. 그래도 broad G4/background apply는 historical scheduled-dry-run debt 때문에 아직 막혀 있습니다. 다음은 repeated activation -> reinforcement를 review/preview-first로 진행하는 게 맞습니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.140/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.140/.venv/bin/agent-memory dogfood g4-linkage-gap-diagnose   /Users/reddit/.agent-memory/memory.db   --epoch-start 2026-05-12T04:21:00Z   --surface hermes-pre-llm-hook   --output /tmp/agent-memory-next-g4-linkage-gap-diagnose.json
```

Expected: read-only/no-mutation. Fresh linkage should remain `fresh_trace_linkage_gap_not_detected`; broad apply remains blocked until the reviewed contract/reconciliation/apply runway is explicitly completed.
