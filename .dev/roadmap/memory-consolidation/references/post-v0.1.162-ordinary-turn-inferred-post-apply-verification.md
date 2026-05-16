# post-v0.1.162 ordinary-turn inferred post-apply verification

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 03:48 KST

## What changed

Added `dogfood ordinary-turn-inferred-post-apply-verification`, a read-only green stop gate for the narrow ordinary-turn inferred exact apply lane.

The verifier consumes:

- the saved `dogfood_ordinary_turn_inferred_apply` report;
- a saved green `dogfood_rollback_replay_validate` report;
- the target DB, checked only for the matching `g5_trace_candidate_applications` audit row and the `ordinary_turn_inferred_approved_as` relation.

It validates:

- apply report kind/read-only/mutation contract (`read_only=false`, `mutated=true` for the prior apply artifact only);
- expected policy `ordinary-turn-inferred-preference-apply-v1`;
- exactly bounded `applied_count <= --max-applied`;
- ordinary conversation auto-approval remains false;
- apply quality gate is green;
- apply privacy flags are ref-safe and do not include backup/raw/reason content;
- backup file exists and SHA-256 matches the apply report;
- rollback replay is green with checked application count at least the apply count and zero failed replays;
- DB audit row exists with action `apply_ordinary_turn_inferred_preference`, matching promoted ref and backup SHA;
- relation exists from `experience_trace:<id>` to the approved `fact:<id>`.

The verifier itself is strictly read-only: `read_only=true`, `mutated=false`, `executes_apply=false`.

## What it still does not allow

Still blocked:

- ordinary conversation auto-approval;
- broad/background apply;
- unattended batch apply;
- default-ranking mutation;
- collapse/delete apply;
- telemetry reset apply;
- unreviewed promotion;
- repeated apply without fresh exact approval and a fresh post-apply stop gate.

## Validation

RED/GREEN source tests:

- RED: `.venv/bin/python -m pytest tests/test_cli.py -q -k ordinary_turn_inferred_post_apply_verification` initially failed because `ordinary-turn-inferred-post-apply-verification` was not a valid dogfood subcommand.
- Focused GREEN: `.venv/bin/python -m pytest tests/test_cli.py -q -k ordinary_turn_inferred_post_apply_verification` => `2 passed, 186 deselected`.
- Broader ordinary-turn GREEN: `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_inferred or ordinary_turn_classifier or ordinary_turn_eval_window'` => `9 passed, 179 deselected`.
- Full suite GREEN: `.venv/bin/python -m pytest tests/ -q` => `370 passed, 1 xfailed`.

Copy-DB smoke:

- Reused previous copy DB artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-apply-smoke-20260516T182955Z/`.
- Verification output: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-apply-smoke-20260516T182955Z/ordinary-turn-inferred-post-apply-verification.json`.
- Input DB was the copied DB, not live `/Users/reddit/.agent-memory/memory.db`.
- Result: `quality_gate.pass=true`, `decision=ordinary_turn_inferred_post_apply_verification_green_stop`, backup SHA-256 matched, rollback replay passed, audit row found, and ordinary-turn inferred relation found.

## Current estimate

- Safety-gated operational north-star: approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.85-99.9%.

This closes the dedicated post-apply verifier/audit compatibility gap for the safest ordinary-turn inferred preference lane. The remaining gap is repeated one-at-a-time evidence and a separate design decision before any broader ordinary-turn automation. Default/background ordinary conversation auto-approval remains blocked.
