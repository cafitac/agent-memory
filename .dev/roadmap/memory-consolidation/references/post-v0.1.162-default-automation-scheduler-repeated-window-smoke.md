# Post-v0.1.162 default automation scheduler repeated-window smoke

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 00:53 KST

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-repeated-window-smoke`, a copy-DB smoke command for the explicit default-automation scheduler corridor.

It proves that a completed scheduler package can feed the next scheduler window as fresh previous evidence:

1. copy the source DB;
2. write explicit scheduler config, enabled policy state, policy gate, and seed previous evidence rollup artifacts;
3. run scheduler integration window 1 on the copied DB;
4. package window 1 post-apply evidence with rollback replay, post-apply verifier, and evidence rollup;
5. run scheduler integration window 2 using window 1 package evidence rollup as `--previous-evidence-rollup`, window 1 scheduler runner as `--previous-scheduler-report`, and window 1 package verifier as `--post-apply-verification-report`;
6. package window 2 post-apply evidence;
7. assert the source DB is unchanged and both copied-DB windows used unique trace refs.

This is still not unattended/default/background authority. It is a live-shaped copy smoke for repeated scheduler evidence chaining.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-scheduler-repeated-window-smoke "$SOURCE_DB" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --report-dir "$REPORT_DIR" \
  --output "$REPORT_DIR/scheduler-repeated-window-smoke.json"
```

Optional:

```bash
  --copy-db-path "$COPY_DB"
```

## Contract

- Mutates only the copied DB; source DB SHA/table counts must remain unchanged.
- Runs exactly two scheduler integration windows on the copy.
- Each window can apply at most one preference-shaped ordinary-turn candidate.
- Window 2 must consume window 1 package outputs:
  - package evidence rollup as next `previous_evidence_rollup`;
  - scheduler runner report as `previous_scheduler_report`;
  - post-apply verifier as `post_apply_verification_report`.
- Each package remains a collector only: it does not run another scheduler cycle and does not apply.
- Output is ref-safe: report paths, hashes, trace refs, counts, and booleans only; no raw trace/reason/report content.
- Keeps broad ordinary conversation auto-approval, unattended/default/background apply, default-ranking mutation, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without fresh evidence blocked.

## Validation

RED:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_repeated_window_smoke_uses_package_evidence \
  -q
# failed: invalid choice ordinary-turn-default-automation-scheduler-repeated-window-smoke
```

GREEN/focused:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_scheduler_repeated_window_smoke_uses_package_evidence \
  -q
# 1 passed
```

Broader default-automation corridor:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k 'scheduler_repeated_window_smoke or default_automation_scheduler_package or default_automation_scheduler_integration or default_automation_scheduler_runner or default_automation_runner or default_automation_post_apply_verification or default_automation_evidence_rollup'
# 15 passed, 208 deselected
```

Full suite:

```bash
.venv/bin/python -m pytest tests/ -q
# 405 passed, 1 xfailed
```

## Copy-live smoke

Repeated-window copy-live smoke report:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-repeated-window-smoke-20260517T155339Z/scheduler-repeated-window-smoke.json`

Observed:

- `quality_gate.pass=true`
- decision `ordinary_turn_default_automation_scheduler_repeated_window_copy_smoke_green`
- `window_count=2`
- `green_integration_count=2`
- `green_package_count=2`
- `unique_trace_ref_count=2`
- `all_rollups_reused_as_next_previous_evidence=true`
- source DB unchanged: `true`
- source DB SHA stayed `0d753d3c89f6c4a2a2efa2117b95dd2e4cb6738039df020c64f75efe08627135`

## Current progress framing

- Safety-gated operational north-star: still about 99%+.
- Literal scoped human-brain-like local memory lifecycle: about 99.99985%+.

Remaining work is now operator/runtime ergonomics: make the scheduler/runbook/status surface this repeated-window evidence clearly, then consider a real local opt-in schedule that only invokes the one-cycle runner when all gates are already green and stops after packaging. Do not enable unattended/default/background authority.
