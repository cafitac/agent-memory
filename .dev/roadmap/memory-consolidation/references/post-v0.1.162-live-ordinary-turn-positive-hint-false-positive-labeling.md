# Post-v0.1.162 live ordinary-turn evidence: positive hint false positives labeled

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 14:52 KST

## Scope

Continued from the live ordinary-turn no-positive-prediction checkpoint using the real live DB `/Users/reddit/.agent-memory/memory.db`. No mock DB or copy-DB smoke was used for the live decision. The slice prioritized speed and real evidence by expanding the ordinary-turn window to 1000/2000 traces and labeling the next available real ordinary-turn evidence.

Primary run directory: `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z`.

## Live evidence

Artifacts:

- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/storage-health.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/trace-quality.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/remember-intent-1000.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-auto-approval-readiness-1000.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-label-packet-40.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-positive-candidate-local-review.json` (local raw/metadata review artifact; do not publish raw contents)
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-label-targets.txt`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-label-update-artifacts.txt`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-classifier-eval-after-43-labels.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-eval-window-summary-after-43-labels.json`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-label-packet-priority-after-43-labels.json`

Findings:

- Storage health and trace quality remained healthy.
- `remember-intent` over the latest 1000 traces still found no explicit remember-intent evidence.
- Ordinary-turn auto-approval readiness over 1000 traces remains blocked on `explicit_remember_intent_ready_count_below_minimum`: `explicit_remember_intent=0`, `ordinary_turn=1000`, `secret_like_ordinary_turns=0`, readiness score `75`.
- Pre-label classifier eval over 1000 traces had 20 labels from the prior slice and one unlabeled predicted-memory-worthy trace, but no labeled positive predictions; gate remained red on `positive_prediction_count_below_minimum`.
- Generated a 40-item real live ordinary-turn label packet: 980 eligible non-secret unlabeled ordinary turns, 40 review items, 940 deferred, 0 secret-like blocks, 20 already labeled.
- Separately found 3 unlabeled predicted-memory-worthy traces in a 2000-trace window. They were metadata-hint-only durable-context positives with empty summary/raw text unavailable for exact local review.
- Applied 43 exact `ordinary-turn-label-update` metadata labels with approval phrase `label-approved-ordinary-turn-v1`:
  - 40 low-salience packet refs labeled `expected_memory_worthy=false`.
  - 3 metadata-hint-only positive refs labeled `expected_memory_worthy=false` because exact durable human fields were unavailable for local review.
- This changed only `experience_traces.metadata_json` label metadata; it did not promote facts/procedures/episodes, apply memory changes, mutate ranking/default retrieval, write core memory status, collapse/delete/deprecate, reset telemetry, or enable auto-approval.

Post-label eval:

- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-classifier-eval-after-43-labels.json`
  - `labeled_ordinary_turn=63`
  - `predicted_memory_worthy=3`
  - `true_negative=60`
  - `false_positive=3`
  - `false_negative=0`
  - `positive_prediction_count=3`
  - `precision_applicable=true`
  - `precision_percent=0`
  - `quality_gate.pass=false`
  - blocked reasons: `false_positive_predictions_present`, `precision_below_minimum`
- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-eval-window-summary-after-43-labels.json`
  - `labeled_ordinary_turn_total=103`
  - `labeled_ordinary_turn_max=63`
  - `positive_prediction_total=3`
  - `false_positive_total=3`
  - gate remains red.

## Contract tightening

Live evidence showed the label packet selected the newest unlabeled ordinary turns first, so rare predicted-positive candidates could stay hidden behind many low-salience recent turns. The packet now prioritizes predicted-memory-worthy non-secret unlabeled traces before other unlabeled non-secret traces while keeping raw text out of the report and preserving all forbidden-authority blocks.

Code change:

- `dogfood ordinary-turn-label-packet` now computes classification for eligible unlabeled non-secret traces before selection and sorts predicted positives first.
- Added a focused test proving a positive predicted trace is selected when `--max-items 1` even if a non-positive ordinary turn was inserted earlier in the live-style window.

Post-change live packet after the 43 labels:

- `/tmp/agent-memory-ordinary-turn-live-20260528T054657Z/ordinary-turn-label-packet-priority-after-43-labels.json`
  - `already_labeled_count=63`
  - `eligible_unlabeled_nonsecret_count=1937`
  - `review_item_count=40`
  - `blocked_secret_like_count=0`
  - `predicted_review_items=0` after the 3 available predicted positives were labeled.

## Verification

Focused test:

```bash
uv run pytest tests/test_cli.py -q -k 'ordinary_turn_label_packet or ordinary_turn_classifier_eval or ordinary_turn_eval_window_summary or ordinary_turn_inferred_approval_readiness'
```

Result: `8 passed, 252 deselected`.

## Stop gates

Keep blocked:

- ordinary conversation auto-approval
- inferred approval/apply
- broad/background/default apply
- fact/procedure/episode promotion from ordinary turns
- unreviewed promotion
- default-ranking mutation
- retrieval-ranking writes
- core memory-status writes
- collapse/delete/deprecate
- telemetry reset apply

## Next step

Do not open ordinary-turn inferred/apply or auto-approval corridors from this window. It now contains real positive predictions, but the positive predictions are false positives from metadata-hint-only traces without exact durable local evidence. Continue with real live evidence collection after more natural turns, using the positive-prioritized label packet so any future predicted positives surface quickly. If a future packet contains raw-reviewable positive evidence, label it and rerun the classifier/window summaries before considering any inferred approval corridor.
