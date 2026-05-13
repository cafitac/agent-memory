# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 17:09 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.153`; the `personal-oss` Hermes hook is healthy on the v0.1.153 runtime. The current verified runway now has a 50-task expanded retrieval fixture gate, 75 checked-in retrieval eval tasks across the fixture directory, persisted/replayed per-candidate collapse proof artifacts with supersession-chain evidence, one fresh non-idempotent narrow live reviewed-candidate promotion, copy/live-safe explicit-approval corridor evidence, an idempotent live G4 queue apply, named ranking policy/shadow-compare diagnostics, approval-gated config-only default-ranking migrate/rollback mechanics, a live Hermes DB 50-task representative fact shadow corpus, and a new live Hermes DB 50-task mixed fact/procedure/episode shadow corpus. Broad G4/background apply, collapse/delete apply, live telemetry reset, default ranking migration, and ordinary conversation auto-approval remain blocked. Live default ranking remains `conservative_legacy`.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 78-80%.
- Substrate/evidence plumbing: about 87%.
- Safe automatic mutation/promotion: about 66-70%.
- Remaining work: about 20-22% overall.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, G5b reviewed trace-candidate persist/list/update/apply for explicit fact/preference/procedure promotion, G5c read-only cluster scoring, G5d read-only repeated activation -> reinforcement refinement preview, G5e read-only stale weak evidence -> decay/collapse candidate preview, G5f conflict -> supersession/replacement candidate preview plus lifecycle registry/bounded partial automation, G5g reviewed decay deprecate / ranking gate / rollback confidence, G5h/G5i rollback replay validation / eval-gated opt-in ranking experiment / decay-collapse decision boundary / richer candidate skeleton annotations / telemetry reconciliation/reset safety reporting / broad-G4 reassessment report fields, 50-task expanded retrieval fixture gate with 75 checked-in eval tasks across the directory, per-candidate collapse proof artifact replay with supersession-chain evidence, and narrow explicit-approval corridor copy/live-safe smokes including one fresh non-idempotent live reviewed-candidate promotion.
- Not done: broad background consolidation apply, fully automatic long-term memory promotion, default retrieval-ranking policy changes, automatic ordinary-conversation approval, collapse/delete apply, and large-scope autonomous rollback/replay on real runtime evidence.

## Latest verified checkpoint

- Release: `v0.1.153`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.153`
- npm: `@cafitac/agent-memory@0.1.153`
- PyPI: `cafitac-agent-memory==0.1.153`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.153/.venv/bin/agent-memory`
- Runtime smoke: PyPI install smoke passed after simple-index propagation, npm installed-bin smoke passed, GitHub release exists, and `hermes --profile personal-oss hooks doctor` is green after `--accept-hooks` approval for the v0.1.153 hook command. v0.1.153 runtime QA artifacts: `/Users/reddit/.agent-memory/reports/v0.1.153-runtime-qa-20260513T080729/`.
- Current source follow-up reports: `/tmp/agent-memory-g4-corridor-smoke/`, `/tmp/agent-memory-telemetry-reset-decision/`, `/tmp/agent-memory-fresh-epoch-v0149/`, and `/tmp/agent-memory-apply-corridor-v0150/`.
- Fresh report directory retained from G4 diagnostics: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.
- Fresh linkage diagnosis retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json` with decision `fresh_trace_linkage_gap_not_detected`.
- Fresh epoch readiness retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`.
- Fresh review queue preview retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`.
- Historical scheduled dry-run retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`.
- Source G5a-G5i checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, read-only `review_score`/`review_recommendation`, `dogfood reinforcement-refinement-preview`, `dogfood decay-collapse-preview`, `dogfood supersession-preview`, lifecycle candidate registry/apply, decay deprecate apply, ranking gate/experiment, rollback confidence, `rollback-replay-validate`, `retrieval-ranking-experiment`, `decay-collapse-decision`, `telemetry-reconciliation`, telemetry reconciliation/reset safety reporting, and G4 reviewed queue preview/persist/update/apply are merged and released through v0.1.150.
- Current local follow-up evidence: expanded fixture file `tests/fixtures/retrieval_eval/expanded/live-compatible-50-gate.json` has 50 live-compatible tasks; checked-in fixture directory evaluates at 75/75 pass; opt-in ranking experiment report `/Users/reddit/.agent-memory/reports/g5i-ranking-experiment-expanded-50-20260513T1355/ranking-experiment-expanded-50.json` is read-only with `expanded_fixture_gate_met=true`, `eval_gate_pass=true`, and `default_ranking_mutated=false`; fresh live reviewed candidate `candidate:29db0390b2f81bdb` promoted to `fact:4` only through the guarded explicit-approval corridor.
- Current source/runtime ranking evidence: `retrieval-ranking-experiment` has named policy/shadow-compare diagnostics; `retrieval-ranking-migrate-default` provides an approval-gated config-only migration with protected table hashes, audit output, and rollback metadata. v0.1.153 published and installed this path. Live default remains `conservative_legacy`. Live shadow reports under `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/` include `live-fact4-shadow.json`, `live-hermes-approved-fact-50-corpus-v1-shadow.json`, and `live-hermes-mixed-approved-50-corpus-v1-shadow.json`; the mixed corpus replayed 50 live tasks across approved facts/procedure/episode with 50/50 pass, zero baseline regressions, protected default order, and no durable mutation. The checked-in 50-task fixture still is not directly runnable against the tiny live Hermes DB because project-M1 references are absent there; the gap artifact is `checked-in-expanded-50-live-gap.stderr.txt`.

## Current blocker

The v0.1.153 runtime is healthy, but broad brain-like automation is still intentionally blocked:

- Fresh epoch report `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/fresh-epoch-since-v0152-with-metadata-gap-diagnostic.json`: quality gate still fails with `low_epoch_observation_trace_coverage` and `epoch_empty_retrieval_outcome_metadata_gap_classified`. The new metadata-gap diagnostic shows `dominant_blocker=classified_legacy_missing_outcome`, `classified_missing_outcome_count=6`, and `unresolved_adapter_payload_gap_count=0`; continue metadata-rich dogfooding before telemetry reset or default ranking migration.
- G4 review queue copy/live-safe smoke `/tmp/agent-memory-apply-corridor-v0150/`: live preview/list/reconciliation were read-only; copy telemetry reset and copy G4 queue apply preserved durable memory (`mutated=false`); live G4 queue apply was idempotent with `applied_count=0`, `already_applied_count=1`, `mutated=false`, and `default_retrieval_unchanged=true`.
- Historical telemetry reconciliation via the telemetry reset copy smoke `/tmp/agent-memory-telemetry-reset-decision/copy-apply.json`: deleting 1773 historical telemetry rows on a DB copy passed with protected durable memory tables unchanged. Live DB was not reset because the fresh epoch gate still fails; live reset remains manual-only behind `telemetry-reset-v1` and `apply-telemetry-reset-v1`.
- Collapse proof is evidence-driven and can persist/replay per-candidate proof artifacts. The current local proof path can reach `satisfied` when supersession-chain/relation evidence exists, but collapse/delete apply remains disabled even after proof satisfaction.
- Retrieval fixture coverage now includes a 50-task live-compatible expanded source gate, 75 checked-in eval tasks across the directory, a live-Hermes-DB representative 50-task fact corpus, and a live-Hermes-DB representative 50-task mixed fact/procedure/episode corpus. The opt-in ranking experiments passed as read-only comparisons, but default retrieval ranking is still unchanged and blocked until a separate explicit default-rollout decision is made after fresh-epoch telemetry is green.
- G4 broad apply contract remains blocked by policy even when a report is individually green. The guardrail now requires all of these to be green on real runtime evidence before reconsideration: retrieval ranking gate, rollback replay validation, live telemetry reconciliation, and human-reviewed queue approval; ordinary conversation auto-approval remains false.

## Recommended next work

Proceed in this sequence:

1. Keep live default ranking on `conservative_legacy`; do not run `retrieval-ranking-migrate-default` against the live profile until an operator gives the exact approval phrase and fresh-epoch telemetry is green.
2. Continue metadata-rich dogfooding to lift fresh-epoch `observation_trace_coverage_ratio` above threshold and eliminate classified legacy missing-outcome rows; the latest blocker is not an unresolved adapter payload gap.
3. Keep live mixed retrieval corpus coverage in the shadow-only lane; extend it only through guarded reviewed-candidate promotions with backup/audit evidence.
4. Keep fresh reviewed candidate promotion limited to the guarded explicit-approval corridor.
5. Keep broad G4/background apply blocked until ranking gate, rollback replay, telemetry reconciliation/fresh epoch, and reviewed queue approvals all pass on real runtime evidence.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, G5c review scores, G5d reinforcement-refinement preview, or G5e decay-collapse preview as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating review scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.153까지 릴리즈/설치/스모크가 끝났고 `personal-oss` Hermes hook도 doctor-green입니다. 전체 목표 대비 대략 78-80% 정도 왔습니다. live Hermes default는 여전히 `conservative_legacy`이고, `graph_reinforced_v1`은 shadow 후보로만 비교했습니다. 새 live-Hermes-DB mixed 50-task corpus는 approved facts/procedure/episode를 포함해 50/50 pass, zero baseline regression, protected default order, no mutation으로 통과했습니다. 다만 post-v0.1.152 fresh-epoch는 아직 `low_epoch_observation_trace_coverage`와 `epoch_empty_retrieval_outcome_metadata_gap_classified`로 block입니다. 새 diagnostic 기준 unresolved adapter payload gap은 0이고, 남은 핵심은 classified legacy missing-outcome row를 metadata-rich dogfooding으로 밀어내는 것입니다. broad G4/background apply, collapse/delete apply, ordinary conversation auto-approval, default ranking migration, live telemetry reset은 아직 금지입니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.153/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.153/.venv/bin/agent-memory dogfood supersession-preview   /Users/reddit/.agent-memory/memory.db   --limit 200 --top 10   --output /tmp/agent-memory-next-g5f-supersession-preview.json
```

Expected: read-only/no-mutation. Collapse proof may become satisfied only through proof artifacts; collapse/delete apply and broad G4/background apply remain blocked.
