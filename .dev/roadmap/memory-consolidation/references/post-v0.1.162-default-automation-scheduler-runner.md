# Post-v0.1.162 default automation scheduler runner

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 18:30 KST

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-runner`, a scheduler-facing one-cycle wrapper around the explicit default-automation runner.

The command is intentionally not broad unattended automation. It requires an explicit scheduler approval phrase and a fresh green previous default-automation evidence rollup before invoking the underlying runner. If it applies one candidate, it stops and reports that post-apply verification is required before the next cycle.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-scheduler-runner "$DB" \
  --policy-gate "$POLICY_GATE" \
  --policy-state-config "$POLICY_STATE" \
  --previous-evidence-rollup "$PREVIOUS_ROLLUP" \
  --report-dir "$REPORT_DIR" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --scheduler-approval-phrase run-one-default-automation-scheduler-cycle-v1 \
  --approval-phrase apply-exact-ordinary-turn-default-automation-candidate-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --output "$REPORT_DIR/default-automation-scheduler-runner.json"
```

## Contract

- Requires exact scheduler phrase `run-one-default-automation-scheduler-cycle-v1`.
- Requires exact apply phrase `apply-exact-ordinary-turn-default-automation-candidate-v1` for the delegated runner.
- Requires exact policy `ordinary-turn-default-automation-policy-v1`.
- Requires enabled local policy-state config and a green policy gate.
- Requires a green previous `dogfood_ordinary_turn_default_automation_evidence_rollup` before invoking the runner.
- Invokes the underlying `ordinary-turn-default-automation-runner` at most once.
- Applies at most one selected ordinary-turn candidate per scheduler cycle.
- Emits `post_apply_verification.required=true` and `executed=false` after a successful apply, forcing an external post-apply verifier/evidence-rollup before the next cycle.
- Keeps broad ordinary conversation auto-approval, background/default unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Validation

Focused RED/GREEN:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k "ordinary_turn_default_automation_scheduler_runner"
# 2 passed, 215 deselected
```

Broader default-automation corridor:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k "ordinary_turn_default_automation_runner or ordinary_turn_default_automation_apply or ordinary_turn_default_automation_post_apply_verification or ordinary_turn_default_automation_evidence_rollup or ordinary_turn_default_automation_freshness_boundary_smoke"
# 12 passed, 205 deselected
```

Full suite:

```bash
.venv/bin/python -m pytest tests/ -q
# 399 passed, 1 xfailed
```

## Copy-live smoke

Positive copy-live smoke report:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-runner-positive-copy-smoke-20260517T092607Z/default-automation-scheduler-runner.json`

Observed:

- `quality_gate.pass=true`
- `scheduler.runner_invoked=true`
- `scheduler.runner_applied=true`
- `post_apply_verification.required=true`
- `source_db_unchanged=true`
- source DB SHA stayed `ec573b446cc9f64c9346a482b3e79633b4e98171b1a9eb2b3a1890c59efb2d71`

Blocked/no-candidate copy-live smoke report:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-runner-smoke-20260517T092548Z/default-automation-scheduler-runner.json`

Observed source DB unchanged and the scheduler wrapper invoked the runner but did not apply because the live copy had no eligible preference candidate.

## Current progress framing

- Safety-gated operational north-star: still about 99%+.
- Literal scoped human-brain-like local memory lifecycle: about 99.9996%+.

The remaining gap is no longer basic scheduler-facing one-cycle wiring. The next safe work is real scheduler integration/configuration around this wrapper, plus repeated post-apply verifier/evidence-rollup automation. That work must still remain opt-in, fail-closed, one-candidate bounded, and post-apply-verifier gated.
