# Post-v0.1.162 ordinary-turn default automation post-apply verification

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 11:09 KST

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-post-apply-verification`, a read-only stop gate for a separately exact-approved one-candidate default automation apply.

The verifier consumes:

- a saved `dogfood_ordinary_turn_default_automation_apply` report;
- a saved `dogfood_rollback_replay_validate` report;
- the target DB for application audit and relation evidence.

It validates:

- apply artifact kind, `read_only=false`, `mutated=true`, default retrieval unchanged, exact expected policy, green quality gate, one-at-a-time apply bound, valid trace/memory refs, ref-safe privacy, and blocked forbidden authority;
- backup file existence plus SHA-256 match against the apply report;
- rollback replay kind, read-only/no-mutation/default-unchanged contract, green quality gate, enough checked applications, zero failed replays, and ref-safe privacy;
- `g5_trace_candidate_applications` audit row policy/action/promoted ref/backup SHA;
- `ordinary_turn_default_automation_approved_as` relation from the trace to the approved fact.

Green decision:

- `ordinary_turn_default_automation_post_apply_verification_green_stop`

Blocked decision:

- `fix_ordinary_turn_default_automation_post_apply_verification_before_next_apply`

## Safety boundary

This is verification only. It does not execute apply, does not enable ordinary conversation auto-approval, does not allow broad/background apply, does not enable default/background auto-approval, does not allow unattended default apply, does not change default ranking, does not allow collapse/delete, does not reset telemetry, and does not permit repeated apply without fresh exact approval.

## Verification

RED:

- `tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_post_apply_verification_green_stop` initially failed because the subcommand was not registered.

GREEN:

- Focused verifier tests: `2 passed`
- Default automation focus: `8 passed, 192 deselected`
- Broader ordinary-turn focus: `27 passed, 173 deselected`
- Full suite: `382 passed, 1 xfailed`.

## Next safe work

1. Run a real/source or copy-live post-apply verification smoke over an actual saved apply report plus rollback replay artifact.
2. Add repeated verifier/evidence-rollup support for default automation if the first post-apply verifier remains green across independent windows.
3. Keep all unattended/default/background ordinary-turn automation blocked until a separate opt-in enablement gate exists and is explicitly approved.
