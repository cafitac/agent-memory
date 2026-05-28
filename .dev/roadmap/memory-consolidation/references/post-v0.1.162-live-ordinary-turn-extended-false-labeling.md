# post-v0.1.162 live ordinary-turn extended false labeling

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 16:43 KST

## Scope

Continued from the direct remember-intent review report checkpoint using the real live DB `/Users/reddit/.agent-memory/memory.db`.

The explicit remember-intent promotion lane stayed stopped because all five direct review-ready traces are already linked to approved facts. This slice used the next available real-data lane: fast ordinary-turn evidence expansion through exact metadata labels for non-secret, low-salience ordinary turns.

No mock DB, copy-DB smoke, or synthetic fixture was used for the live decision.

## Run directory

`/tmp/agent-memory-next-live-20260528T074021Z`

## Pre-label evidence

Artifacts:

- `/tmp/agent-memory-next-live-20260528T074021Z/storage-health.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/trace-quality.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/remember-intent.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/remember-intent-direct-review.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-label-packet.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-classifier-eval.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-auto-approval-readiness.json`

Results:

- Storage health: `status=healthy`, warnings `[]`.
- Trace quality: `status=healthy`, warnings `[]`, recommendation `consider_g4_plan`.
- Latest real live trace window had `total=4972`, `remember_intent=5`, `ordinary_turn=4967`.
- Direct remember-intent review remained unchanged: `review_ready_count=5`, `direct_material_count=5`, `eligible_count=0`, `skipped_count=5`, `blocked_count=0`, `reason_counts={"already_auto_approved": 5}`, `quality_gate.pass=true`.
- Ordinary-turn label packet produced 150 review items from 4754 eligible unlabeled non-secret ordinary turns.
- The packet review items were all predicted non-memory-worthy: `predicted_memory_worthy=0`, `classified_reason=none`, `retention_policy=ephemeral`, `summary_length_bucket=empty`, `secret_like=0`, `salience_band=low`, `user_emphasis_band=zero`.
- Pre-label classifier eval over the live window: `labeled_ordinary_turn=213`, `true_negative=210`, `false_positive=3`, `false_negative=0`, `positive_prediction_count=3`, `precision_percent=0`; gate remained red on `false_positive_predictions_present` and `precision_below_minimum`.

## Bounded live mutation performed

Applied 150 exact `ordinary-turn-label-update` metadata labels with approval phrase `label-approved-ordinary-turn-v1`.

Each update set `expected_memory_worthy=false` for an item from the packet because the surfaced real-data evidence was non-secret, low-salience, empty-summary, ordinary-turn metadata with no exact durable human field.

Update artifacts:

- Trace refs: `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-label-trace-refs.txt`
- Per-trace update reports: `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-label-updates/`

This changed only `experience_traces.metadata_json` label metadata. It did not promote memories, apply facts/procedures/episodes, mutate ranking/default retrieval, write core memory status, create relations, collapse/delete/deprecate, reset telemetry, or enable auto-approval/background/default automation.

## Post-label evidence

Artifacts:

- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-classifier-eval-post-label.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-eval-window-summary-post-label.json`
- `/tmp/agent-memory-next-live-20260528T074021Z/ordinary-turn-inferred-approval-readiness-post-label.json`

Post-label classifier eval:

- `total=4973`
- `ordinary_turn=4968`
- `labeled_ordinary_turn=363`
- `unlabeled_ordinary_turn=4605`
- `predicted_memory_worthy=3`
- `true_negative=360`
- `false_positive=3`
- `false_negative=0`
- `positive_prediction_count=3`
- `precision_applicable=true`
- `precision_percent=0`
- `quality_gate.pass=false`
- Blocked reasons: `false_positive_predictions_present`, `precision_below_minimum`

Repeated-window summary:

- `report_count=5`
- `labeled_ordinary_turn_total=772`
- `positive_prediction_total=12`
- `false_positive_total=12`
- `false_negative_total=0`
- `quality_gate.pass=false`
- Blocked reasons include `eval_report_quality_gate_not_green`, `false_positive_predictions_present`, `positive_prediction_count_below_minimum`, and `precision_below_minimum`.

Inferred approval readiness:

- `usable_for_readiness=false`
- `ready_for_design=false`
- `apply_supported=false`
- `quality_gate.pass=false`
- Recommended next step: `design_separate_exact_approval_apply_corridor_keep_ordinary_auto_approval_blocked`

## Decision

This was useful real-data progress but it does not open ordinary-turn auto-approval or inferred apply.

The live dataset now has more true-negative ordinary-turn labels (`363` in the latest eval; `772` across repeated windows), but the same three durable-context predictions remain false positives and precision is still 0 for positive predictions.

## Stop gates

Keep blocked:

- ordinary-turn auto-approval
- inferred ordinary-turn apply
- broad/background/default mutation
- fact/procedure/episode promotion from ordinary turns
- relation writes
- ranking/default retrieval mutation
- core memory-status writes
- collapse/delete/deprecate
- telemetry reset
- unattended scheduler/background enablement

## Next step

Do not spend more time labeling empty low-salience ordinary turns unless a later packet surfaces predicted positives or exact durable human fields.

The next fast useful lane is a narrow exact-approval/apply corridor design or report contract that starts from already reviewed, explicit material and remains separate from ordinary-turn auto-approval. If no exact candidate is surfaced, stop at read-only evidence rather than inventing promotion work.
