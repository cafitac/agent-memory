# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 00:07 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.141`; the installed Hermes hooks are healthy on the v0.1.141 runtime across default, personal-oss, earlypay, and infra-admin profiles. Fresh linkage diagnostics no longer show a hook linkage bug, G5a/G5b/G5c/G5d are merged/released for ref-safe trace-cluster previews, reviewed trace-candidate persist/list/update/apply, read-only review scoring, and repeated activation -> reinforcement refinement preview. Broad G4/background apply remains blocked.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 60-62%.
- Substrate/evidence plumbing: about 74-76%.
- Safe automatic mutation/promotion: about 42-45%.
- Remaining work: about 38-40% overall, concentrated in guarded apply, conflict/supersession, decay/collapse, ranking evaluation, and rollback confidence.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, G5b reviewed trace-candidate persist/list/update/apply for explicit fact/preference/procedure promotion, G5c read-only cluster scoring, and G5d read-only repeated activation -> reinforcement refinement preview.
- Not done: broad background consolidation apply, automatic long-term memory promotion, conflict-aware automatic supersession, weak-trace decay/collapse apply, automatic graph-cluster-to-fact/procedure/preference generation, retrieval-ranking changes behind eval, and large-scope rollback confidence.

## Latest verified checkpoint

- Release: `v0.1.141`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.141`
- npm: `@cafitac/agent-memory@0.1.141`
- PyPI: `cafitac-agent-memory==0.1.141`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.141/.venv/bin/agent-memory`
- Runtime smoke report: `/Users/reddit/.agent-memory/runtime/v0.1.141/g5d-live-smoke.json`
- Hermes config backups from v0.1.141 rollout: `/Users/reddit/.hermes/config.yaml.bak-v0141-20260513T000411` plus matching `personal-oss`, `earlypay`, and `infra-admin` profile backups.
- Fresh report directory retained from G4 diagnostics: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`
- Fresh linkage diagnosis retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json`
- Fresh epoch readiness retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`
- Fresh review queue preview retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`
- Historical scheduled dry-run retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`
- Source G5a/G5b/G5c/G5d checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, read-only `review_score`/`review_recommendation`, and `dogfood reinforcement-refinement-preview` are merged and released through v0.1.141.
- Release/published-install smoke passed; runtime rollout is doctor-green across default, personal-oss, earlypay, and infra-admin Hermes profiles.

## Current blocker

Fresh v0.1.141 runtime plus v0.1.138 fresh telemetry evidence are healthy enough for continued brain-like reviewed-candidate planning:

- `g4-linkage-gap-diagnose-v0138-fresh.json`: quality gate pass, decision `fresh_trace_linkage_gap_not_detected`, observation/trace linkage coverage `1.0`, unlinked observations `0`.
- `fresh-epoch-v0138.json`: quality gate pass, decision `fresh_epoch_ready_to_compare_against_historical`.
- `g4-review-queue-preview-v0138-fresh.json`: quality gate pass, decision `review_queue_ready_for_manual_review`, `read_only=true`, `mutated=false`.
- `g5d-live-smoke.json`: quality gate decision `reinforcement_refinement_preview_ready_for_human_review`, `read_only=true`, `mutated=false`, candidate count `1`.

However, historical scheduled-dry-run still blocks broad G4/background apply on:

- `trace_quality_needs_more_dogfooding`
- `decay_risk_above_threshold`
- `background_quality_warnings_present`

Interpretation: this is no longer a fresh hook linkage bug. It is historical telemetry/review debt plus still-narrow mutation safety work.

## Recommended next work

Proceed in this sequence:

1. Start G5e as review/preview-first work: stale weak evidence -> decay/collapse candidate preview. It should be read-only, ref-safe, and should not delete, decay, collapse, or rewrite any memory by default.
2. Keep G5d/G5e semantics narrow: review scores and recommendations are review-priority signals only; they do not persist review state, increment/decrement reinforcement, promote memories, auto-approve ordinary conversation, or change retrieval defaults.
3. Add explicit contract tests for future G5e safety: `read_only=true`, `mutated=false`, `apply_supported=false`, no raw prompt/query/transcript/sample output, and protected memory tables unchanged.
4. If a later G5d/G5e apply slice needs mutation, add only a separate explicit narrow apply policy with backup/audit/rollback; generic continuation does not authorize it.
5. G4 broad apply contract remains blocked/guardrail-only. Required future shape: explicit policy, approval phrase, actor, reason hash, backup path, expected queue ids/hash, audit row, rollback hint, raw-content exclusion, and ordinary-conversation auto-approval forbidden.
6. Historical telemetry reconciliation remains a separate reviewed `telemetry-reset-v1` corridor for historical telemetry rows older than a chosen epoch; never delete facts/procedures/episodes/relations/source records/status history.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, G5c review scores, or G5d reinforcement-refinement preview as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating review scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.141까지 릴리즈/설치/스모크가 끝났고 Hermes hook도 default/personal-oss/earlypay/infra-admin 전부 doctor-green입니다. G5a/G5b/G5c/G5d는 merged/released이고, G5d는 repeated activation -> reinforcement refinement를 read-only preview로 보여주는 단계입니다. 전체 목표 대비 대략 60-62% 정도 왔고, 남은 38-40%는 자동 apply/승격/decay/supersession/rollback 쪽입니다. 다음은 G5e stale weak evidence -> decay/collapse candidate preview를 read-only로 여는 게 맞습니다. broad G4/background apply는 historical scheduled-dry-run debt 때문에 아직 금지입니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.141/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.141/.venv/bin/agent-memory dogfood reinforcement-refinement-preview \
  /Users/reddit/.agent-memory/memory.db \
  --limit 20 --top 3 --frequent-threshold 3 \
  --output /tmp/agent-memory-next-g5d-reinforcement-refinement-preview.json
```

Expected: read-only/no-mutation. G5d should remain `reinforcement_refinement_preview_ready_for_human_review`; fresh linkage should remain `fresh_trace_linkage_gap_not_detected`; broad apply remains blocked until the reviewed contract/reconciliation/apply runway is explicitly completed.
