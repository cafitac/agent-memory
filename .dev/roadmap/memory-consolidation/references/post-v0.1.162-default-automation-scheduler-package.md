# Post-v0.1.162 default automation scheduler package/collector

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 00:37 KST

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-package`, a durable scheduler package/collector command for the explicit default-automation scheduler corridor.

The command does not run a scheduler cycle and does not apply memory. It consumes a green `ordinary-turn-default-automation-scheduler-integration` report from a previous one-cycle run, validates that the nested scheduler runner actually applied exactly one candidate, then automatically collects the required post-apply evidence for the next cycle:

1. `dogfood rollback-replay-validate`
2. `dogfood ordinary-turn-default-automation-post-apply-verification`
3. `dogfood ordinary-turn-default-automation-evidence-rollup`

The resulting package is read-only, ref-safe, and usable as the fresh previous evidence before a later explicit scheduler cycle.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-scheduler-package "$DB" \
  --scheduler-integration-report "$SCHEDULER_INTEGRATION_REPORT" \
  --expected-policy ordinary-turn-default-automation-policy-v1 \
  --report-dir "$REPORT_DIR" \
  --output "$REPORT_DIR/scheduler-package.json"
```

## Contract

- Requires scheduler integration `kind=dogfood_ordinary_turn_default_automation_scheduler_integration`.
- Requires integration `quality_gate.pass=true`, `mutated=true`, exact policy `ordinary-turn-default-automation-policy-v1`, default retrieval unchanged, ordinary conversation auto-approval false, and ref-safe privacy flags.
- Requires nested scheduler runner invoked/applied/green and a readable runner report path.
- Derives the one-cycle apply report from the nested runner report directory and validates it via the existing post-apply verifier.
- Automatically writes:
  - `rollback-replay-validate.json`
  - `ordinary-turn-default-automation-post-apply-verification.json`
  - `ordinary-turn-default-automation-evidence-rollup.json`
- Package output is read-only and non-mutating; `collector.executes_scheduler_cycle=false` and `collector.executes_apply=false`.
- Keeps broad ordinary conversation auto-approval, unattended/default/background apply, default-ranking mutation, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without new approval blocked.
- Output is ref-safe: paths, hashes, trace refs, counts, and booleans only; no raw trace/reason/report content.

## Validation

Focused RED/GREEN:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_package_blocks_red_integration \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_package_collects_verifier_and_rollup \
  -q
# 2 passed
```

Broader default-automation corridor:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k 'default_automation_scheduler_package or default_automation_scheduler_integration or default_automation_scheduler_runner or default_automation_runner or default_automation_post_apply_verification or default_automation_evidence_rollup'
# 14 passed, 208 deselected
```

Full suite:

```bash
.venv/bin/python -m pytest tests/ -q
# 404 passed, 1 xfailed
```

## Copy-live smoke

Package collector copy-live smoke report:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-package-copy-smoke-20260517T153723Z/scheduler-package.json`

Observed:

- `quality_gate.pass=true`
- `collector.rollback_replay_executed=true`
- `collector.post_apply_verification_executed=true`
- `collector.evidence_rollup_executed=true`
- `evidence_rollup.green_report_count=1`
- source DB unchanged: `true`
- source DB SHA stayed `f20a8a8c7746e4dc257e0165df8e506827e2cb4761b45272774f94dd6fe94dda`

## Current progress framing

- Safety-gated operational north-star: still about 99%+.
- Literal scoped human-brain-like local memory lifecycle: about 99.99975%+.

Remaining work is now almost entirely operational: CI observation after push, repeated live-shaped scheduler windows using the generated package evidence as the next previous rollup, and runbook/operator ergonomics. Do not enable unattended/default/background authority.
