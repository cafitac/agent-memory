# post-v0.1.162 ordinary-turn default automation apply corridor

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 10:55 KST

## Summary

Added `dogfood ordinary-turn-default-automation-apply`, a separate exact-reviewed one-candidate apply corridor that consumes a saved `dogfood_ordinary_turn_default_automation_dry_run` artifact.

This is intentionally not default auto-approval. It is a stop-after-one mutation path with explicit policy, approval phrase, actor, reason, backup, conflict preflight, audit row, and relation evidence.

## Contract

Command:

`agent-memory dogfood ordinary-turn-default-automation-apply <db_path> --trace-ref experience_trace:<id> --dry-run-report <json> --policy ordinary-turn-default-automation-policy-v1 --approval-phrase apply-exact-ordinary-turn-default-automation-candidate-v1 --actor <operator> --reason <reason> [--backup-path <db.bak>] [--output <json>]`

Green output:

- `kind=dogfood_ordinary_turn_default_automation_apply`
- `read_only=false`
- `mutated=true`
- `default_retrieval_unchanged=true`
- `ordinary_conversation_auto_approval=false`
- `quality_gate.decision=ordinary_turn_default_automation_exact_candidate_applied_stop_after_one`
- `apply.applied_count=1`
- `dry_run_evidence` is ref/hash-only and validates the exact candidate trace ref.

Mutation evidence:

- Creates one approved `fact` from a non-secret preference-shaped ordinary turn.
- Creates one `ordinary_turn_default_automation_approved_as` relation from trace ref to fact ref.
- Writes one `g5_trace_candidate_applications` audit row with backup path/SHA and rollback hint.
- Copies the DB before mutation and reports backup SHA-256.

Still blocked:

- ordinary conversation auto-approval
- broad/background apply
- default/background auto-approval
- unattended default apply
- unattended batch apply
- unreviewed promotion
- default ranking mutation
- collapse/delete apply
- telemetry reset apply
- repeated apply without fresh exact approval

## Validation

- RED observed: focused test failed because `ordinary-turn-default-automation-apply` was not a registered dogfood subcommand.
- Focused GREEN: `2 passed` for default automation apply corridor tests.
- Default automation GREEN: `6 passed, 192 deselected` for `-k ordinary_turn_default_automation`.
- Broader ordinary-turn GREEN: `25 passed, 173 deselected` for `-k ordinary_turn`.
- Full suite GREEN: `380 passed, 1 xfailed`.

## Remaining gap toward 100%

This closes the dry-run-to-one-candidate apply corridor, but it is not enough to enable default/background automation. Next required checkpoint is a read-only post-apply verifier for this default automation corridor, plus rollback replay evidence, then repeated independent green windows before any opt-in default enablement.
