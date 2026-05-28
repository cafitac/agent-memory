# Post-v0.1.162 live G4 stable review queue classified; telemetry gate still blocks apply

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 18:15 KST

## Scope

Continued from the persisted G4 review queue checkpoint using the real live DB `/Users/reddit/.agent-memory/memory.db`.

Preference boundary honored: no mock DB and no copy-DB smoke was used for the live decision. The only live mutations were G4 review-queue metadata transitions and stable current queue persistence; no memory apply was executed.

Run directory: `/tmp/agent-memory-g4-review-classify-20260528T085711Z`.

## What changed

1. Reviewed/classified the 8 pending queue rows from the prior persisted queue:
   - approved 3 `reinforcement_review` rows: `g4-review:reinforcement:4`, `g4-review:reinforcement:5`, `g4-review:reinforcement:6`
   - rejected 5 `decay_risk_review` rows: `g4-review:decay-risk:2` through `g4-review:decay-risk:6`
   - reason: reinforcement rows are signal-only review items; decay rows proposed `monitor_only_no_mutation` and had protected/frequently-activated/connected evidence, so they do not support decay apply.

2. Ran live safety gates:
   - live retrieval fixtures: 9 tasks from approved live memories (`facts=7`, `procedures=1`, `episodes=1`), retrieval diagnostics green, baseline regressions `0`
   - retrieval ranking shadow experiment: pass, `task_count=9`, `baseline_regression_count=0`, `rank_change_count=29`, default retrieval unchanged
   - rollback confidence: green
   - rollback replay validate: green
   - fresh epoch: individual report pass but includes `high_epoch_empty_retrieval_ratio`
   - fresh-epoch comparison: red on `blocked_reasons_present`
   - telemetry reconciliation: red on `fresh_epoch_comparison_not_green`

3. Found and fixed a G4 queue contract bug before any apply:
   - old queue IDs were ordinal (`g4-review:reinforcement:4`, etc.) and could drift to different targets across fresh previews
   - approval reports did not include `reviewed_queue_refs`, so a green human approval artifact could be stale relative to the current preview
   - code now emits target-stable queue IDs such as `g4-review:reinforcement:fact:6` and `g4-review:decay-risk:fact:6`
   - `g4-review-queue-approval-report` now includes `reviewed_queue_refs`
   - `g4-review-queue-preview` now fails the human-review gate if reviewed refs are missing or do not cover the current preview queue

4. Persisted and classified the current stable-ID review queue:
   - persisted 12 stable queue rows; `inserted_count=12`, `existing_count=0`
   - approved 8 current `reinforcement_review` rows: `procedure:1`, `episode:1`, `fact:1`, `fact:4`, `fact:5`, `fact:6`, `fact:7`, `fact:8`
   - rejected 4 current `decay_risk_review` rows: `fact:1`, `fact:4`, `fact:5`, `fact:6`
   - final queue approval report: `total_count=24`, `approved=14`, `rejected=10`, `pending=0`, `human_review_queue_approval_pass=true`

## Final gate state

Latest stable artifacts:

- approval report: `/tmp/agent-memory-g4-review-classify-20260528T085711Z/g4-review-queue-approval-report-stable-after-classification.json`
- queue preview with gates: `/tmp/agent-memory-g4-review-classify-20260528T085711Z/g4-review-queue-preview-stable-with-reviewed-refs.json`
- apply readiness: `/tmp/agent-memory-g4-review-classify-20260528T085711Z/g4-apply-readiness-stable-after-classification.json`
- operator bundle: `/tmp/agent-memory-g4-review-classify-20260528T085711Z/g4-operator-apply-bundle-stable.json`
- readiness summary: `/tmp/agent-memory-g4-review-classify-20260528T085711Z/g4-readiness-gate-summary-stable.json`

Green:

- current queue preview quality gate
- human review queue approval artifact
- retrieval ranking shadow gate
- rollback confidence
- rollback replay validation

Red / hard blocker:

- live telemetry reconciliation remains red because fresh-epoch comparison is not green
- apply readiness remains red:
  - `live_telemetry_reconciliation_pass`
  - `live_telemetry_reconciliation_pass_not_green`
  - `queue_preview_artifact_gates_not_green`
- operator apply bundle remains red with the same telemetry blocker

## Safety boundary

No fact/procedure/episode promotion, memory apply, relation write, default ranking mutation, core memory-status write, collapse/delete/deprecate, telemetry reset, or ordinary-turn/background/default automation enablement was executed.

The stable queue approval is not apply authorization. Any apply still requires all gates green plus exact explicit operator approval, backup, policy, phrase, reason, and max-apply bound.

## Verification

- RED observed: `test_python_module_cli_dogfood_g4_review_queue_preview_rejects_stale_human_approval_refs` failed before the contract fix because stale approval refs were accepted.
- Focused G4 CLI tests: `uv run pytest tests/test_cli.py -q -k 'g4_review_queue_preview or g4_operator_apply_bundle or g4_review_queue_approval_report or g4_apply_readiness or g4_readiness_gate_summary'` -> `12 passed, 250 deselected`
- Roadmap contract: `uv run pytest tests/test_roadmap_contract.py -q` -> `3 passed`
- `git diff --check` -> pass

## Next step

Do not apply G4 queue items yet. The next fast real-data task is to resolve or collect enough fresh live telemetry evidence for the telemetry reconciliation gate. If the fresh-epoch comparison remains red, stop at telemetry evidence and do not run `g4-review-queue-apply`.
