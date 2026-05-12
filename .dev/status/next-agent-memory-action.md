# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-12 13:30 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.138`; the installed Hermes hook is using `/Users/reddit/.agent-memory/runtime/v0.1.138/.venv/bin/agent-memory`, fresh v0.1.138 linkage diagnostics report `fresh_trace_linkage_gap_not_detected`, and broad G4/background apply remains blocked while historical telemetry debt and narrow reviewed-apply contracts are handled explicitly.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 50-55%.
- Substrate/evidence plumbing: about 70%.
- Safe automatic mutation/promotion: about 30-35%.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), and fresh v0.1.138 linkage health.
- Not done: broad background consolidation apply, automatic long-term memory promotion, conflict-aware automatic supersession, weak-trace decay/collapse apply, graph-cluster-to-fact/procedure/preference generation, and large-scope rollback confidence.

## Latest verified checkpoint

- Release: `v0.1.138`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.138`
- npm: `@cafitac/agent-memory@0.1.138`
- PyPI: `cafitac-agent-memory==0.1.138`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.138/.venv/bin/agent-memory`
- Hermes config backups from rollout: `/Users/reddit/.hermes/config.yaml.agent-memory-v0138-backup-20260512-132119` plus matching `personal-oss`, `earlypay`, and `infra-admin` profile backups.
- Fresh report directory: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`
- Fresh linkage diagnosis: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json`
- Fresh epoch readiness: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`
- Fresh review queue preview: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`
- Historical scheduled dry-run: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`

## Current blocker

Fresh v0.1.138 telemetry is healthy enough for G4 planning:

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

1. Docs/status refresh: keep `.dev/status/current-handoff.md`, this file, and `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md` aligned to the v0.1.138 runtime, fresh-linkage result, and 50-55% north-star estimate.
2. G4 broad apply contract: keep broad apply as a contract/guardrail surface first. Required shape: explicit policy, approval phrase, actor, reason hash, backup path, expected queue ids/hash, audit row, rollback hint, raw-content exclusion, and ordinary-conversation auto-approval forbidden.
3. Historical telemetry reconciliation: prefer reviewed `telemetry-reset-v1` preview/apply only for historical telemetry rows older than a chosen epoch; never delete facts/procedures/episodes/relations/source records/status history.
4. first narrow reviewed apply slice: only approved persisted review-queue items may use `g4-review-queue-apply-v1`, and the first mutation class remains `apply_reinforcement_marker`; decay, promotion, supersession, and broad consolidation remain blocked.
5. Brain-like automation runway: next safe design axis is `trace cluster -> consolidation candidate`, `candidate -> reviewed fact/procedure/preference promotion`, repeated activation -> reinforcement, stale weak evidence -> decay/summary candidate, and conflict -> supersession review. Retrieval ranking changes stay opt-in/evaluated before default.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat the fresh v0.1.138 pass as approval for automatic memory creation. It only removes the fresh linkage blocker.

Do not live-apply persisted queue mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, or retrieval-ranking changes.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.138까지 릴리즈/설치/스모크가 끝났고 fresh epoch에서는 `fresh_trace_linkage_gap_not_detected`라서 버그 막힘은 풀렸어요. 그래도 broad G4/background apply는 아직 historical scheduled-dry-run debt 때문에 막혀 있습니다. 다음은 G4 broad apply contract, historical telemetry reconciliation, 첫 narrow reviewed apply slice, 그리고 brain-like consolidation runway를 순서대로 진행하는 게 맞습니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.138/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.138/.venv/bin/agent-memory dogfood g4-linkage-gap-diagnose   /Users/reddit/.agent-memory/memory.db   --epoch-start 2026-05-12T04:21:00Z   --surface hermes-pre-llm-hook   --output /tmp/agent-memory-next-g4-linkage-gap-diagnose.json
```

Expected: read-only/no-mutation. Fresh linkage should remain `fresh_trace_linkage_gap_not_detected`; broad apply remains blocked until the reviewed contract/reconciliation/apply runway is explicitly completed.
