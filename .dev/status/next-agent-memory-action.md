# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 14:05 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.150`; the installed Hermes hooks are healthy on the v0.1.150 runtime across default, personal-oss, earlypay, and infra-admin profiles. The current verified runway now has a 50-task expanded retrieval fixture gate, 75 checked-in retrieval eval tasks across the fixture directory, persisted/replayed per-candidate collapse proof artifacts with supersession-chain evidence, one fresh non-idempotent narrow live reviewed-candidate promotion, copy/live-safe explicit-approval corridor evidence, and an idempotent live G4 queue apply. Broad G4/background apply, default ranking changes, collapse/delete apply, live telemetry reset, and ordinary conversation auto-approval remain blocked.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 74-76%.
- Substrate/evidence plumbing: about 85%.
- Safe automatic mutation/promotion: about 62-66%.
- Remaining work: about 24-26% overall, concentrated in larger-scope eval-backed automation, safer automatic review decisions, default-ranking rollout, collapse/delete proof completion, and broader rollback/replay validation.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, G5b reviewed trace-candidate persist/list/update/apply for explicit fact/preference/procedure promotion, G5c read-only cluster scoring, G5d read-only repeated activation -> reinforcement refinement preview, G5e read-only stale weak evidence -> decay/collapse candidate preview, G5f conflict -> supersession/replacement candidate preview plus lifecycle registry/bounded partial automation, G5g reviewed decay deprecate / ranking gate / rollback confidence, G5h/G5i rollback replay validation / eval-gated opt-in ranking experiment / decay-collapse decision boundary / richer candidate skeleton annotations / telemetry reconciliation/reset safety reporting / broad-G4 reassessment report fields, 50-task expanded retrieval fixture gate with 75 checked-in eval tasks across the directory, per-candidate collapse proof artifact replay with supersession-chain evidence, and narrow explicit-approval corridor copy/live-safe smokes including one fresh non-idempotent live reviewed-candidate promotion.
- Not done: broad background consolidation apply, fully automatic long-term memory promotion, default retrieval-ranking policy changes, automatic ordinary-conversation approval, collapse/delete apply, and large-scope autonomous rollback/replay on real runtime evidence.

## Latest verified checkpoint

- Release: `v0.1.150`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.150`
- npm: `@cafitac/agent-memory@0.1.150`
- PyPI: `cafitac-agent-memory==0.1.150`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.150/.venv/bin/agent-memory`
- Runtime smoke: published-install smoke passed; Hermes hook doctor is green across default, personal-oss, earlypay, and infra-admin profiles.
- Current source follow-up reports: `/tmp/agent-memory-g4-corridor-smoke/`, `/tmp/agent-memory-telemetry-reset-decision/`, `/tmp/agent-memory-fresh-epoch-v0149/`, and `/tmp/agent-memory-apply-corridor-v0150/`.
- Fresh report directory retained from G4 diagnostics: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.
- Fresh linkage diagnosis retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json` with decision `fresh_trace_linkage_gap_not_detected`.
- Fresh epoch readiness retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`.
- Fresh review queue preview retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`.
- Historical scheduled dry-run retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`.
- Source G5a-G5i checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, read-only `review_score`/`review_recommendation`, `dogfood reinforcement-refinement-preview`, `dogfood decay-collapse-preview`, `dogfood supersession-preview`, lifecycle candidate registry/apply, decay deprecate apply, ranking gate/experiment, rollback confidence, `rollback-replay-validate`, `retrieval-ranking-experiment`, `decay-collapse-decision`, `telemetry-reconciliation`, telemetry reconciliation/reset safety reporting, and G4 reviewed queue preview/persist/update/apply are merged and released through v0.1.150.
- Current local follow-up evidence: expanded fixture file `tests/fixtures/retrieval_eval/expanded/live-compatible-50-gate.json` has 50 live-compatible tasks; checked-in fixture directory evaluates at 75/75 pass; opt-in ranking experiment report `/Users/reddit/.agent-memory/reports/g5i-ranking-experiment-expanded-50-20260513T1355/ranking-experiment-expanded-50.json` is read-only with `expanded_fixture_gate_met=true`, `eval_gate_pass=true`, and `default_ranking_mutated=false`; fresh live reviewed candidate `candidate:29db0390b2f81bdb` promoted to `fact:4` only through the guarded explicit-approval corridor.

## Current blocker

The v0.1.150 runtime is healthy, but broad brain-like automation is still intentionally blocked:

- Fresh epoch report `/tmp/agent-memory-fresh-epoch-v0149/fresh-epoch.json`: quality gate fails with `high_epoch_empty_retrieval_ratio` and `epoch_empty_retrieval_outcome_metadata_gap_classified`; continue dogfooding before trusting epoch-wide automation.
- G4 review queue copy/live-safe smoke `/tmp/agent-memory-apply-corridor-v0150/`: live preview/list/reconciliation were read-only; copy telemetry reset and copy G4 queue apply preserved durable memory (`mutated=false`); live G4 queue apply was idempotent with `applied_count=0`, `already_applied_count=1`, `mutated=false`, and `default_retrieval_unchanged=true`.
- Historical telemetry reconciliation via the telemetry reset copy smoke `/tmp/agent-memory-telemetry-reset-decision/copy-apply.json`: deleting 1773 historical telemetry rows on a DB copy passed with protected durable memory tables unchanged. Live DB was not reset because the fresh epoch gate still fails; live reset remains manual-only behind `telemetry-reset-v1` and `apply-telemetry-reset-v1`.
- Collapse proof is evidence-driven and can persist/replay per-candidate proof artifacts. The current local proof path can reach `satisfied` when supersession-chain/relation evidence exists, but collapse/delete apply remains disabled even after proof satisfaction.
- Retrieval fixture coverage now includes a 50-task live-compatible expanded gate and 75 checked-in eval tasks across the directory. The opt-in ranking experiment passed the expanded gate as a read-only comparison, but default retrieval ranking is still unchanged and blocked until a separate default-rollout decision is made.
- G4 broad apply contract remains blocked by policy even when a report is individually green. The guardrail now requires all of these to be green on real runtime evidence before reconsideration: retrieval ranking gate, rollback replay validation, live telemetry reconciliation, and human-reviewed queue approval; ordinary conversation auto-approval remains false.

## Recommended next work

Proceed in this sequence:

1. Review and commit/release the current local safety slice: 50-task expanded retrieval fixture, 75-task checked-in eval assertions, ranking-experiment comparison payload, collapse proof supersession-chain evidence, fresh live reviewed-candidate promotion evidence, and broad-G4 blocked reassessment assertions.
2. Run the full standard test suite before release (`uv run --python 3.11 pytest tests/ -q`).
3. If green, publish the next release/runtime and repeat the Hermes hook doctor/runtime smoke.
4. After release, start the next safe slice: default-ranking rollout design as an explicit opt-in-to-default migration with rollback/replay and fixture gates; do not silently enable default ranking.
5. Keep broad G4/background apply blocked until ranking gate, rollback replay, telemetry reconciliation/fresh epoch, and reviewed queue approvals all pass on real runtime evidence.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, G5c review scores, G5d reinforcement-refinement preview, or G5e decay-collapse preview as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating review scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.150까지 릴리즈/설치/스모크가 끝났고 Hermes hook도 default/personal-oss/earlypay/infra-admin 전부 doctor-green입니다. 전체 목표 대비 대략 74-76% 정도 왔습니다. 방금 로컬 safety slice에서 retrieval eval은 expanded 50-task gate / checked-in 75-task pass까지 올라갔고, opt-in ranking experiment도 read-only 비교로 통과했지만 default ranking은 아직 변경하지 않았습니다. collapse proof는 supersession-chain evidence로 satisfied까지 갈 수 있게 됐지만 collapse/delete apply는 계속 금지입니다. 다음은 이 로컬 slice를 전체 테스트 후 커밋/릴리즈하고, 그 다음 default-ranking rollout을 별도 opt-in-to-default migration으로 설계하는 순서가 맞습니다. broad G4/background apply는 아직 금지입니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.150/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.150/.venv/bin/agent-memory dogfood supersession-preview   /Users/reddit/.agent-memory/memory.db   --limit 200 --top 10   --output /tmp/agent-memory-next-g5f-supersession-preview.json
```

Expected: read-only/no-mutation. Collapse proof may become satisfied only through proof artifacts; collapse/delete apply and broad G4/background apply remain blocked.
