# Post-v0.1.162 live ordinary-turn readiness: no positive predictions gate

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 12:45 KST

## Scope

Continued from the live decay decision checkpoint using the real live DB `/Users/reddit/.agent-memory/memory.db`. No mock DB or copy-DB smoke was used for the live decision. The slice followed the documented next fast path: read-only ordinary-turn readiness / explicit remember-intent evidence collection, then a report-contract tightening because live evidence exposed an ambiguous gate.

Primary run directory: `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z`.

## Live evidence

Artifacts:

- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/storage-health.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/trace-quality.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/remember-intent.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-auto-approval-readiness.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-label-packet.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-classifier-eval-post-contract.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-eval-window-summary-post-contract.json`

Findings:

- Storage health and trace quality remained healthy.
- `remember-intent` over the latest 500 traces found `remember_intent=0`, `ordinary_turn=500`, `review_ready_count=0`, `unsafe_sample_count=0`.
- Ordinary-turn auto-approval readiness remains red only on `explicit_remember_intent_ready_count_below_minimum`: `explicit_remember_intent=0`, `ordinary_turn=500`, `secret_like_ordinary_turns=0`, readiness score `75`.
- The live label packet was green for manual labeling, privacy-safe, and ref/hash-only: 500 eligible non-secret unlabeled ordinary turns, 20 review items, 480 deferred, 0 secret-like blocks.
- Reviewed the 20 exact packet refs under a conservative local rule: empty summary hash, no preference/procedure/durable marker, non-secret, low-salience => `expected_memory_worthy=false`.
- Applied 20 `ordinary-turn-label-update` metadata labels with exact phrase `label-approved-ordinary-turn-v1`. This changed only experience-trace metadata labels; it did not promote facts/procedures/episodes, apply memory, mutate ranking/default retrieval, write core memory status, collapse/delete, or enable auto-approval.
- Post-label classifier eval over 500 traces has `labeled_ordinary_turn=20`, `true_negative=20`, `false_positive=0`, `false_negative=0`, `predicted_memory_worthy=0`, `predicted_not_memory_worthy=500`.

## Contract tightening

The first live eval reported `precision_percent=0` and blocked with `precision_below_minimum` even though there were no positive predictions and no false positives. That was technically safe but operator-ambiguous: the problem was absence of positive-prediction evidence, not bad precision.

Code change:

- `dogfood ordinary-turn-classifier-eval` now emits:
  - `evaluation.positive_prediction_count`
  - `evaluation.precision_applicable`
- If `positive_prediction_count == 0`, the quality gate blocks with `positive_prediction_count_below_minimum` instead of `precision_below_minimum`.
- `dogfood ordinary-turn-eval-window-summary` propagates the same distinction and adds `labeled_window.positive_prediction_total` plus per-report positive-prediction fields.

Post-fix live result:

- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-classifier-eval-post-contract.json`
  - `positive_prediction_count=0`
  - `precision_applicable=false`
  - `true_negative=20`
  - `false_positive=0`
  - `false_negative=0`
  - `quality_gate.pass=false`
  - blocked reason `positive_prediction_count_below_minimum`
- `/tmp/agent-memory-ordinary-turn-live-20260528T033203Z/ordinary-turn-eval-window-summary-post-contract.json`
  - `positive_prediction_total=0`
  - blocked reasons `eval_report_quality_gate_not_green`, `positive_prediction_count_below_minimum`

## Verification

Focused test:

```bash
uv run pytest tests/test_cli.py -q -k 'ordinary_turn_classifier_eval or ordinary_turn_eval_window_summary or ordinary_turn_inferred_approval_readiness'
```

Result: `6 passed, 253 deselected`.

## Stop gates

Keep blocked:

- ordinary conversation auto-approval
- broad/background/default apply
- fact/procedure/episode promotion from ordinary turns
- unreviewed promotion
- default-ranking mutation
- retrieval-ranking writes
- core memory-status writes
- collapse/delete/deprecate
- telemetry reset apply

## Next step

Continue collecting/labeling real ordinary-turn evidence from the live DB. The current live window has enough true-negative evidence to show the classifier is conservative on low-salience turns, but it has no positive-prediction evidence and no explicit remember-intent traces. Do not open an inferred or auto-approval corridor until a future real window contains positive predictions and/or explicit remember-intent evidence with green eval/window summaries.
