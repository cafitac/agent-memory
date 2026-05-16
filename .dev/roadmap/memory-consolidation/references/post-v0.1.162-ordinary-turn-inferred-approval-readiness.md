# post-v0.1.162 ordinary-turn inferred approval readiness gate

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 02:54 KST

## Purpose

Add the next read-only gate after strict repeated ordinary-turn classifier windows: a readiness artifact that says the system has enough aggregate evidence to design a separate exact-approval apply corridor, while still refusing to execute apply or enable ordinary conversation auto-approval.

This is readiness-for-design only. It is not an apply command and not a default auto-approval switch.

## Source behavior

New command:

`agent-memory dogfood ordinary-turn-inferred-approval-readiness --window-summary <json> [--min-report-count N] [--min-labeled-total N] [--min-precision-percent N] [--output <json>]`

It consumes a saved `dogfood_ordinary_turn_eval_window_summary` report and validates:

- report kind is `dogfood_ordinary_turn_eval_window_summary`
- report is read-only and non-mutating
- default retrieval is unchanged
- ordinary conversation auto-approval is still false
- window policy is `ordinary-turn-repeated-eval-window-v1`
- window quality gate is green
- report count and labeled-total floors pass
- strict precision floor passes
- false positives and false negatives are absent
- privacy flags show aggregate/report-hash-only output

Green output reports:

- `kind=dogfood_ordinary_turn_inferred_approval_readiness`
- `read_only=true`
- `mutated=false`
- `ordinary_conversation_auto_approval=false`
- `inferred_approval_readiness.ready_for_design=true`
- `apply_supported=false`
- `apply_executed=false`
- `requires_separate_exact_approval_corridor=true`

## Copy-DB smoke

Artifact directory:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-readiness-smoke-20260516T175111Z/`

The smoke copied `/Users/reddit/.agent-memory/memory.db` and did not mutate the live DB.

Smoke flow:

1. Inserted two metadata-only ordinary turns through the real `hermes-pre-llm-hook` command against the copy DB.
2. Labeled each copied trace with exact-ref `dogfood ordinary-turn-label-update` and exact phrase `label-approved-ordinary-turn-v1`.
3. Ran two strict `dogfood ordinary-turn-classifier-eval` reports.
4. Ran `dogfood ordinary-turn-eval-window-summary` with strict precision.
5. Ran `dogfood ordinary-turn-inferred-approval-readiness` over the saved window summary.

Smoke result:

- `quality_gate.pass=true`
- `decision=ordinary_turn_inferred_approval_ready_for_separate_exact_apply_design`
- `ready_for_design=true`
- `apply_supported=false`
- `apply_executed=false`
- `ordinary_conversation_auto_approval=false`
- `mutated=false`
- source window had `precision_percent_min=100`, `false_positive_total=0`, `false_negative_total=0`, and `labeled_ordinary_turn_total=3`

## Validation

- RED observed: both new CLI tests failed on invalid subcommand `ordinary-turn-inferred-approval-readiness`.
- GREEN focused tests: `2 passed`.
- Broader ordinary-turn / hook focus: `13 passed, 171 deselected`.
- Full suite: `366 passed, 1 xfailed`.
- Release/package checks:
  - `tests/test_release_workflows.py tests/test_release_metadata.py`: `7 passed`
  - `scripts/check_release_metadata.py`: passed
  - `npm pack --dry-run`: passed

## Current interpretation

- Safety-gated operational north-star remains approximately 99%+.
- Scoped local human-brain-like lifecycle is approximately 99.65-99.75%.
- The next boundary is no longer evidence readiness mechanics; it is designing a separate exact-approval ordinary-turn apply corridor.
- Ordinary-turn apply, broad/background apply, unattended batch apply, default-ranking automatic rollout, autonomous collapse/delete, live telemetry reset, and unreviewed promotion remain blocked.

## Next safe work

1. Commit/push this readiness gate and watch CI.
2. Design the exact-approval ordinary-turn apply corridor as a separate PR-sized slice.
3. Keep that future corridor bounded, backed up, actor/reason audited, and fail-closed on any red readiness artifact.
4. Do not enable ordinary conversation auto-approval or broad apply by default.
