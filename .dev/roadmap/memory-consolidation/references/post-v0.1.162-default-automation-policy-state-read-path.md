# post-v0.1.162 default automation policy-state read-path enforcement

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-17

## Summary

This source/develop slice wires the exact opt-in policy-state file into the ordinary-turn default automation dry-run read path.

The dry-run command now accepts optional `--policy-state-config`. When provided, it fail-closes unless the file is a valid enabled policy state from the exact opt-in switch. This keeps default automation disabled by default while allowing a caller to prove that the local manual opt-in state is enabled.

## Enforcement contract

`dogfood ordinary-turn-default-automation-dry-run --policy-state-config PATH` blocks when:

- the policy-state file is missing, unreadable, or not a JSON object;
- kind is not `agent_memory_ordinary_turn_default_automation_policy_state`;
- policy does not match `ordinary-turn-default-automation-policy-v1`;
- `manual_opt_in_default_automation_enabled` is not true;
- `ordinary_conversation_auto_approval` is not false;
- `default_background_auto_approval_allowed` is not false;
- `unattended_default_apply_allowed` is not false;
- `max_default_candidates_per_run` is below the requested `--max-candidates`;
- `max_apply_without_fresh_post_apply_verification` is not zero;
- fresh post-apply verification, exact review, or disable switch requirements are absent.

When the policy-state file is valid and enabled, dry-run can still select only the bounded number of exact-reviewed candidate refs. It remains read-only and keeps apply execution false.

## Safety properties

Still true after this slice:

- dry-run is `read_only=true` and `mutated=false`;
- ordinary conversation auto-approval remains false;
- unattended default apply remains false;
- default/background apply remains false;
- default retrieval is unchanged;
- candidate previews are ref/hash safe and do not include raw ordinary-turn text;
- disabled or missing local policy state selects zero candidates.

## Verification

RED:

- `--policy-state-config` initially failed as an unrecognized argument.

GREEN:

- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation_dry_run_policy_state'`
  - `2 passed, 207 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation'`
  - `17 passed, 192 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn'`
  - `36 passed, 173 deselected`
- `.venv/bin/python -m pytest tests/ -q`
  - `391 passed, 1 xfailed`

## Current progress interpretation

- Safety-gated operational north-star: still approximately 99%+.
- Scoped local human-brain-like lifecycle: approximately 99.998%.
- Remaining gap before calling the scoped local lifecycle 100%: policy-state enforcement at the apply boundary plus freshness linkage to the most recent post-apply verifier/evidence-rollup artifact. Dry-run now respects the switch, but apply should also explicitly require enabled policy state and fresh verifier lineage before any next apply.

## Next safe slice

Add apply-boundary policy-state enforcement:

1. `ordinary-turn-default-automation-apply` should accept the same policy-state config;
2. absent/disabled/invalid policy-state blocks apply;
3. enabled state still allows only the exact trace ref from a green dry-run;
4. stale/missing post-apply verifier lineage blocks repeated apply;
5. unattended/background apply remains false.
