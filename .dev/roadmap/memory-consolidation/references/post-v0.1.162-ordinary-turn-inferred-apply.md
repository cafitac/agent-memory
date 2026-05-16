# post-v0.1.162 ordinary-turn inferred exact apply corridor

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 03:28 KST

## What changed

Added `dogfood ordinary-turn-inferred-apply`, the first mutating ordinary-turn inferred corridor.

It is intentionally narrow:

- applies exactly one `experience_trace:<id>` at a time;
- requires a saved green `dogfood_ordinary_turn_inferred_approval_readiness` report;
- requires exact policy `ordinary-turn-inferred-preference-apply-v1`;
- requires exact approval phrase `apply-exact-ordinary-turn-inferred-preference-v1`;
- requires non-empty `--actor` and `--reason`;
- creates a SQLite backup before mutation and records the backup SHA-256;
- only supports the low-risk ordinary preference shape parsed from summaries like `User prefers ...`;
- runs preference conflict preflight before mutation;
- creates an approved fact, an `ordinary_turn_inferred_approved_as` relation, and a `g5_trace_candidate_applications` audit row;
- fails closed on red readiness, secret-like trace summaries, non-turn traces, unsupported shapes, conflicts, or duplicate trace application.

## What it does not allow

This is not default ordinary conversation auto-approval.

Still blocked:

- ordinary conversation auto-approval;
- broad/background apply;
- unattended batch apply;
- default-ranking mutation;
- collapse/delete apply;
- telemetry reset apply;
- unreviewed promotion;
- repeated apply without fresh exact approval.

## Validation so far

RED/GREEN source tests:

- RED: focused tests first failed because `ordinary-turn-inferred-apply` was not a valid dogfood subcommand.
- GREEN: `.venv/bin/python -m pytest tests/test_cli.py -q -k ordinary_turn_inferred_apply` => `2 passed, 184 deselected`.
- GREEN broader ordinary-turn focus: `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_inferred or ordinary_turn_classifier or ordinary_turn_eval_window'` => `7 passed, 179 deselected`.
- GREEN full suite: `.venv/bin/python -m pytest tests/ -q` => `368 passed, 1 xfailed`.

Copy-DB smoke:

- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-apply-smoke-20260516T182955Z/`.
- The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
- Inserted one synthetic ordinary-turn preference trace into the copy DB only.
- Applied it with exact policy/phrase/actor/reason and backup.
- Apply report: `ordinary-turn-inferred-apply.json`.
- Backup: `pre-apply-memory-backup.db`.
- Backup SHA-256: `4b532122ea6f065d5524f147354fb3fae8598e0b29236702a6764f4415107e75`.
- Result: `quality_gate.pass=true`, `decision=ordinary_turn_inferred_exact_preference_applied_stop_after_one`, `mutated=true`, `ordinary_conversation_auto_approval=false`, `memory_ref=fact:10`.
- Rollback replay on the copy DB passed: `rollback_restore_replay_sufficient_for_bounded_partial_automation`.

Generic `trace-candidate-application-audit` is not yet green for this new lane because it expects reviewed trace-candidate status and a retrieval-ranking report. That is an audit-tool compatibility gap, not a failed backup/rollback replay.

## Current estimate

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.75-99.85%.

This slice closes the prior missing ordinary-turn exact-approval apply corridor for the safest preference-shaped ordinary turns. The remaining gap is a dedicated post-apply verifier/audit compatibility layer for this ordinary-turn lane, followed by repeated copy/live-safe evidence before considering any broader ordinary-turn automation.

## Recommended next work

1. Add `ordinary-turn-inferred-post-apply-verification` so this lane has a dedicated green stop gate like remember-preferences and lifecycle reinforcement.
2. Keep applying at most one exact ordinary-turn inferred preference per run, with a fresh readiness report and backup each time.
3. Make generic application audit understand `ordinary_turn_inferred_preference`, or keep it separate from trace-candidate reviewed-promotion audit.
4. Do not enable default/background ordinary conversation auto-approval.
