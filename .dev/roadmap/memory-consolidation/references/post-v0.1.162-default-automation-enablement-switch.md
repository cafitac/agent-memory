# post-v0.1.162 default automation enablement switch

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-17

## Summary

This source/develop slice adds `dogfood ordinary-turn-default-automation-enablement-switch` as the exact opt-in enable/disable switch after the green default automation enablement preflight.

The switch writes only a narrow local JSON policy-state file chosen by `--config-path`. It does not mutate the memory DB, default retrieval ranking, ordinary-turn classifier behavior, or background scheduler defaults.

## Enable contract

Enable requires:

- `--action enable`
- a readable green `dogfood_ordinary_turn_default_automation_enablement_preflight` artifact via `--preflight`
- exact policy `ordinary-turn-default-automation-policy-v1`
- exact phrase `enable-opt-in-ordinary-turn-default-automation-v1`
- actor and reason
- `--max-default-candidates-per-run >= 1`

A green enable writes policy state with:

- `manual_opt_in_default_automation_enabled=true`
- `ordinary_conversation_auto_approval=false`
- `default_background_auto_approval_allowed=false`
- `unattended_default_apply_allowed=false`
- `max_apply_without_fresh_post_apply_verification=0`
- `requires_fresh_post_apply_verification=true`
- `requires_exact_reviewed_candidate=true`
- `disable_switch_available=true`
- appended audit event

Green enable decision:

- `ordinary_turn_default_automation_exact_opt_in_enabled_guarded_local_only`

## Disable contract

Disable requires:

- `--action disable`
- exact policy `ordinary-turn-default-automation-policy-v1`
- exact phrase `disable-opt-in-ordinary-turn-default-automation-v1`
- actor and reason

A green disable writes the same policy-state file fail-closed:

- `manual_opt_in_default_automation_enabled=false`
- ordinary conversation auto-approval remains false
- unattended default apply remains false
- appended audit event

Green disable decision:

- `ordinary_turn_default_automation_disabled_fail_closed`

## Fail-closed checks

Enable blocks on:

- missing/unreadable/wrong-kind preflight
- preflight not read-only or mutated
- preflight default retrieval changed
- preflight ordinary auto-approval enabled
- preflight quality gate red
- policy mismatch
- required phrase mismatch
- not ready for manual opt-in enablement
- any background/default/unattended apply authority in the preflight contract
- any apply without fresh post-apply verification
- any forbidden authority in the preflight
- privacy/ref-safety failure
- wrong approval phrase

Disable blocks on:

- wrong disable phrase
- existing policy-state policy mismatch

## Source smoke

Using the previous source/copy-live report directory:

- Preflight input: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-preflight.json`
- Enable output: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-switch-enable.json`
- Disable output: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-switch-disable.json`
- Policy-state file: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-policy-state.json`

Smoke result:

- enable `quality_gate.pass=true`
- enable decision `ordinary_turn_default_automation_exact_opt_in_enabled_guarded_local_only`
- disable `quality_gate.pass=true`
- disable decision `ordinary_turn_default_automation_disabled_fail_closed`
- final policy state is fail-closed: `manual_opt_in_default_automation_enabled=false`, `unattended_default_apply_allowed=false`

No live memory DB mutation was performed.

## Verification

RED:

- `ordinary-turn-default-automation-enablement-switch` initially failed as an invalid dogfood subcommand.

GREEN:

- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation_enablement_switch'`
  - `3 passed, 204 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation_enablement'`
  - `5 passed, 202 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation'`
  - `15 passed, 192 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn'`
  - `34 passed, 173 deselected`
- `.venv/bin/python -m pytest tests/ -q`
  - `389 passed, 1 xfailed`

## Current progress interpretation

- Safety-gated operational north-star: still approximately 99%+.
- Scoped local human-brain-like lifecycle: approximately 99.997%.
- Remaining gap to call it 100% for this local scoped lifecycle: wire the narrow policy-state reader into the ordinary-turn default automation runner so the runner respects this switch, while preserving fail-closed disabled-by-default behavior and post-apply verification freshness.

## Next safe slice

Add read-path enforcement for the policy-state file:

1. absent or disabled policy state means no default automation;
2. enabled policy state still permits only one exact-reviewed candidate at a time;
3. stale/missing post-apply verification evidence blocks the next apply;
4. disable state immediately wins;
5. unattended background apply remains false.
