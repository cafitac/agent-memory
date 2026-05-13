# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 12:44 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.149`; the installed Hermes hooks are healthy on the v0.1.149 runtime across default, personal-oss, earlypay, and infra-admin profiles. The current local follow-up slice expands checked-in retrieval eval coverage from 21 to 25 tasks, persists/replays per-candidate collapse proof artifacts, and verifies narrow explicit-approval corridors on live-compatible copies plus an idempotent live G4 queue apply. Broad G4/background apply, default ranking changes, collapse/delete apply, live telemetry reset, and ordinary conversation auto-approval remain blocked.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 72-74% checkpoint baseline; this local slice moves the practical estimate toward 74-76%.
- Substrate/evidence plumbing: about 83-85%.
- Safe automatic mutation/promotion: about 62-65%.
- Remaining work: about 24-26% overall, concentrated in larger-scope eval-backed automation, safer automatic review decisions, default-ranking rollout, collapse/delete proof completion, and broader rollback/replay validation.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, G5b reviewed trace-candidate persist/list/update/apply for explicit fact/preference/procedure promotion, G5c read-only cluster scoring, G5d read-only repeated activation -> reinforcement refinement preview, G5e read-only stale weak evidence -> decay/collapse candidate preview, G5f conflict -> supersession/replacement candidate preview plus lifecycle registry/bounded partial automation, G5g reviewed decay deprecate / ranking gate / rollback confidence, G5h/G5i rollback replay validation / eval-gated opt-in ranking experiment / decay-collapse decision boundary / richer candidate skeleton annotations / telemetry reconciliation/reset safety reporting / broad-G4 reassessment report fields, and local follow-up coverage for 25 checked-in eval tasks plus per-candidate collapse proof artifact replay.
- Not done: broad background consolidation apply, fully automatic long-term memory promotion, default retrieval-ranking policy changes, automatic ordinary-conversation approval, collapse/delete apply, and large-scope autonomous rollback/replay on real runtime evidence.

## Latest verified checkpoint

- Release: `v0.1.149`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.149`
- npm: `@cafitac/agent-memory@0.1.149`
- PyPI: `cafitac-agent-memory==0.1.149`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.149/.venv/bin/agent-memory`
- Runtime smoke: published-install smoke passed; Hermes hook doctor is green across default, personal-oss, earlypay, and infra-admin profiles.
- Current source follow-up reports: `/tmp/agent-memory-g4-corridor-smoke/`, `/tmp/agent-memory-telemetry-reset-decision/`, `/tmp/agent-memory-fresh-epoch-v0149/`, and `/tmp/agent-memory-apply-corridor-v0150/`.
- Fresh report directory retained from G4 diagnostics: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.
- Fresh linkage diagnosis retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json`
- Fresh epoch readiness retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`
- Fresh review queue preview retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`
- Historical scheduled dry-run retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`
- Source G5a-G5i checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, read-only `review_score`/`review_recommendation`, `dogfood reinforcement-refinement-preview`, `dogfood decay-collapse-preview`, `dogfood supersession-preview`, lifecycle candidate registry/apply, decay deprecate apply, ranking gate/experiment, rollback confidence/replay validation, telemetry reconciliation/reset safety reporting, and G4 reviewed queue preview/persist/update/apply are merged and released through v0.1.149. Local follow-up adds 25-task retrieval eval coverage and per-candidate collapse proof artifact replay.
- Release/published-install smoke passed; manual true-distribution PyPI/npm smoke passed; runtime rollout is doctor-green across default, personal-oss, earlypay, and infra-admin Hermes profiles.

## Current blocker

The v0.1.149 runtime is healthy, and the local follow-up slice is full-test-green, but broad brain-like automation is still intentionally blocked:

- Fresh epoch report `/tmp/agent-memory-fresh-epoch-v0149/fresh-epoch.json`: quality gate fails with `high_epoch_empty_retrieval_ratio` and `epoch_empty_retrieval_outcome_metadata_gap_classified`; continue dogfooding before trusting epoch-wide automation.
- G4 review queue copy/live-safe smoke `/tmp/agent-memory-apply-corridor-v0150/`: live preview/list/reconciliation were read-only; copy telemetry reset and copy G4 queue apply preserved durable memory (`mutated=false`); live G4 queue apply was idempotent with `applied_count=0`, `already_applied_count=1`, `mutated=false`, and `default_retrieval_unchanged=true`.
- Telemetry reset copy smoke `/tmp/agent-memory-telemetry-reset-decision/copy-apply.json`: deleting 1773 historical telemetry rows on a DB copy passed with protected durable memory tables unchanged. Live DB was not reset because the fresh epoch gate still fails; live reset remains manual-only behind `telemetry-reset-v1` and `apply-telemetry-reset-v1`.
- Collapse equivalence proof is now evidence-driven and can persist/replay per-candidate proof artifacts in local source. Live report `/tmp/agent-memory-fresh-epoch-v0149/decay-collapse-decision.json` remains only `partially_satisfied`; relation-equivalence/supersession-chain evidence is still missing. Collapse/delete apply remains blocked.
- Retrieval fixture coverage now has 25 checked-in tasks, including source-noise and cross-surface guardrails. Default retrieval ranking is still unchanged and blocked until larger 50+ eval coverage passes.

## Recommended next work

Proceed in this sequence:

1. Finish this local follow-up branch: commit, PR, release, published-install smoke, and runtime rollout.
2. Expand real retrieval eval fixtures from 25 tasks toward a broader 50+ task gate before any default ranking change.
3. Add relation-equivalence or reviewed supersession-chain proof artifact evidence so collapse proof can move from `partially_satisfied` to `satisfied` while keeping collapse/delete apply disabled.
4. Add a non-idempotent but still narrow live-approved mutation only after a fresh candidate is reviewed and backed up; do not use broad apply.
5. Keep broad G4/background apply blocked until ranking gate, rollback replay, telemetry reconciliation, fresh epoch, and reviewed queue approvals all pass on real runtime evidence.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, G5c review scores, G5d reinforcement-refinement preview, or G5e decay-collapse preview as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating review scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.146까지 릴리즈/설치/스모크가 끝났고 Hermes hook도 default/personal-oss/earlypay/infra-admin 전부 doctor-green입니다. G5a-G5g는 merged/released이고, local G5h는 구현/test-green이고, local G5i도 live rollback replay rollup, retrieval fixture expansion, collapse equivalence proof surface, telemetry apply safety gate, broad G4 reassessment report fields까지 구현/test-green인 상태입니다. 전체 목표 대비 대략 72-74% 정도 왔고, 남은 26-28%는 default ranking 변경, collapse/delete apply, 자동 승인/승격, broad G4/background apply를 안전하게 여는 쪽입니다. 다음은 G5h를 리뷰/릴리즈하고 live runtime smoke를 도는 게 맞습니다. broad G4/background apply는 아직 금지입니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.146/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.146/.venv/bin/agent-memory dogfood supersession-preview \
  /Users/reddit/.agent-memory/memory.db \
  --limit 200 --top 10 \
  --output /tmp/agent-memory-next-g5f-supersession-preview.json
```

Expected: read-only/no-mutation. G5e should remain a decay/collapse review-priority preview (`read_only=true`, `mutated=false`, default retrieval unchanged); fresh linkage should remain `fresh_trace_linkage_gap_not_detected`; broad apply remains blocked until the reviewed contract/reconciliation/apply runway is explicitly completed.


## G5i local command surface

Local G5h/G5i command surface includes `rollback-replay-validate`, `retrieval-ranking-experiment`, `decay-collapse-decision`, `telemetry-reconciliation`, rollback confidence reporting, reviewed decay deprecate gates, and the G4 broad apply contract as blocked guardrail-only reporting. Historical telemetry reconciliation remains telemetry-only.
