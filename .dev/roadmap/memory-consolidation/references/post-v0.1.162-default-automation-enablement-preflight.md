# post-v0.1.162 default automation enablement preflight

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-17

## Summary

This source/develop slice adds `dogfood ordinary-turn-default-automation-enablement-preflight` as the next step toward the scoped human-brain-like local memory lifecycle north-star.

The command consumes a saved green `dogfood_ordinary_turn_default_automation_evidence_rollup` artifact and emits a read-only/manual-opt-in-only preflight packet. It is intentionally not a default switch and not an apply trigger.

Green decision:

- `ordinary_turn_default_automation_enablement_preflight_green_manual_opt_in_only`

The green result means the saved repeated post-apply evidence is sufficient to design the next exact opt-in enablement switch. It does not enable that switch.

## Safety contract

The command always reports:

- `read_only=true`
- `mutated=false`
- `default_retrieval_unchanged=true`
- `ordinary_conversation_auto_approval=false`
- `default_auto_approval_enabled=false`
- `default_background_auto_approval_allowed=false`
- `unattended_default_apply_allowed=false`
- `apply_supported=false`
- `apply_executed=false`
- `max_apply_without_fresh_post_apply_verification=0`
- `enablement_executed=false`

It requires the exact phrase `enable-opt-in-ordinary-turn-default-automation-v1` only to prove that a future opt-in must be explicit. The preflight itself does not write configuration or mutate a DB.

## Fail-closed checks

The preflight blocks on:

- unreadable or wrong-kind evidence rollup
- rollup not read-only or mutated
- default retrieval changed
- ordinary auto-approval already true
- expected policy mismatch
- red rollup quality gate
- rollup not ready for default enablement design
- insufficient green reports or applied-memory evidence
- any apply authority in the rollup
- any default auto-approval already enabled in evidence
- privacy/ref-safety failure
- forbidden authority in evidence
- wrong approval phrase

## Live/source smoke

Input rollup:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-evidence-rollup.json`

Output preflight:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-preflight.json`

Smoke result:

- `quality_gate.pass=true`
- `green_report_count=2`
- `applied_memory_count=2`
- `ready_for_manual_opt_in_enablement=true`
- `default_auto_approval_enabled=false`
- `unattended_default_apply_allowed=false`
- `enablement_executed=false`

No live DB mutation was performed.

## Verification

RED:

- `ordinary-turn-default-automation-enablement-preflight` initially failed as an invalid dogfood subcommand.

GREEN:

- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation_enablement_preflight'`
  - `2 passed, 202 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation'`
  - `12 passed, 192 deselected`
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn'`
  - `31 passed, 173 deselected`
- `.venv/bin/python -m pytest tests/ -q`
  - first run hit macOS temp/disk exhaustion (`No space left on device`), not a code regression
  - after removing transient pytest/build/cache files, rerun passed: `386 passed, 1 xfailed`

## Current progress interpretation

- Safety-gated operational north-star: still approximately 99%+.
- Scoped local human-brain-like lifecycle: approximately 99.995%.
- Remaining gap to call the scoped local lifecycle 100%: an exact opt-in enablement switch with disable/rollback guardrails and hard fail-closed default-on tests. That future switch must still be separate from unattended background apply.

## Next safe slice

Implement an exact opt-in enablement switch that only changes a narrow local configuration/policy state after:

1. green enablement preflight;
2. exact policy `ordinary-turn-default-automation-policy-v1`;
3. exact phrase `enable-opt-in-ordinary-turn-default-automation-v1`;
4. actor/reason/audit record;
5. bounded max candidates per run;
6. disable switch/rollback plan;
7. proof that unattended background apply remains false.

Do not enable broad/background ordinary conversation auto-approval, repeated apply without fresh verifier evidence, default ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion.
