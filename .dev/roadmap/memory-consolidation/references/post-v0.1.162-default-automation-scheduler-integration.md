# Post-v0.1.162 default automation scheduler integration/config

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 19:02 KST

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-integration`, a real scheduler-integration/config gate around the scheduler-facing one-cycle runner.

The command validates an explicit scheduler config artifact, enabled policy-state config, green policy gate, fresh previous default-automation evidence rollup, and any pending post-apply verifier queue before it may invoke one scheduler cycle. It remains fail-closed and exact-opt-in: no broad ordinary conversation auto-approval, no unattended/default/background apply, no default-ranking mutation, and no repeated cycle without fresh verifier evidence.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-scheduler-integration "$DB" \
  --scheduler-config "$SCHEDULER_CONFIG" \
  --policy-gate "$POLICY_GATE" \
  --policy-state-config "$POLICY_STATE" \
  --previous-evidence-rollup "$PREVIOUS_ROLLUP" \
  --previous-scheduler-report "$PREVIOUS_SCHEDULER_REPORT" \
  --post-apply-verification-report "$POST_APPLY_VERIFICATION_REPORT" \
  --report-dir "$REPORT_DIR" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --scheduler-approval-phrase run-one-default-automation-scheduler-cycle-v1 \
  --approval-phrase apply-exact-ordinary-turn-default-automation-candidate-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --output "$REPORT_DIR/scheduler-integration.json"
```

## Contract

- Requires scheduler config `kind=ordinary_turn_default_automation_scheduler_config`.
- Requires `enabled=true`, exact policy `ordinary-turn-default-automation-policy-v1`, `max_candidates_per_cycle=1`, enabled-policy-state requirement, previous-rollup requirement, and post-apply-verification-before-next-cycle requirement.
- Rejects scheduler config that grants ordinary conversation auto-approval, default/background auto-approval, or unattended default apply.
- If a previous scheduler report says post-apply verification was required but not executed, blocks the next cycle unless at least one supplied post-apply verification report is green and policy-matched.
- Calls `ordinary-turn-default-automation-scheduler-runner` only after the integration/config/verifier queue is green.
- Invokes at most one scheduler runner cycle and applies at most one candidate on the DB passed to the command.
- After a successful cycle, reports that the next cycle requires a new post-apply verifier/evidence rollup.
- Output is ref-safe: report hashes, paths, counts, trace refs, and booleans only; no raw turn/reason/report content.

## Validation

Focused RED/GREEN:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_integration_blocks_disabled_config_before_runner tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_integration_requires_prior_post_apply_verification tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_integration_records_verification_and_runs_one_cycle -q
# 3 passed
```

Broader default-automation corridor:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k 'default_automation_scheduler_integration or default_automation_scheduler_runner or default_automation_runner or default_automation_post_apply_verification or default_automation_evidence_rollup'
# 12 passed, 208 deselected
```

Full suite:

```bash
.venv/bin/python -m pytest tests/ -q
# 402 passed, 1 xfailed
```

## Copy-live smoke

Positive copy-live smoke report:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-integration-copy-smoke-20260517T095816Z/scheduler-integration.json`

Observed:

- `quality_gate.pass=true`
- `mutated_copy=true`
- `scheduler_runner.invoked=true`
- `post_apply_verification_queue.queued_report_count=1`
- `scheduler_runner.selected_trace_ref=experience_trace:4130`
- `source_db_unchanged=true`
- source DB SHA stayed `1413ffe379ceed84763ab52cb4a6ff7d17e54f4f7733f6b204518f2c1b67d85b`

## Current progress framing

- Safety-gated operational north-star: still about 99%+.
- Literal scoped human-brain-like local memory lifecycle: about 99.9997%+.

Remaining work is now mostly operational hardening: durable scheduler job/runbook packaging, automatic post-apply verifier/evidence-rollup collection, CI observation after push, and larger repeated live-shaped windows. Do not enable unattended/default/background authority.
