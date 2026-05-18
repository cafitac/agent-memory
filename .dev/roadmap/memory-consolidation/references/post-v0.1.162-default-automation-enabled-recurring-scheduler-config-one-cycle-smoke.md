# post-v0.1.162 default automation enabled recurring scheduler one-cycle smoke gate

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 09:58 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-smoke`, a read-only gate over the materialized enabled recurring scheduler config.

The command verifies that the materialized config is suitable for exactly one explicit scheduler one-shot boundary, but it does not run that cycle, does not execute apply, and does not install or enable background/cron.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-smoke \
  --materialize-report "$REPORT_DIR/enabled-recurring-scheduler-config-materialize.json" \
  --scheduler-config "$REPORT_DIR/ordinary-turn-default-automation-recurring-scheduler.enabled.json" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --report-dir "$REPORT_DIR/one-cycle" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-config-one-cycle-smoke.json"
```

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_one_cycle_smoke_green_ready_for_explicit_one_shot_only`

A green report proves:

- materialize report is green and config-writing-only
- materialized config path and SHA-256 match the config file read by the smoke gate
- config has `enabled=true`
- config has `recurring_scheduler_enabled=true`
- config has `background_or_cron_enabled=false`
- config limits one cycle to `max_candidates_per_cycle=1`
- config requires enabled policy state, green policy gate, previous evidence rollup, package-stop, post-apply verification, bounded cadence policy, kill-switch policy, CI health watch, and rollback evidence
- ordinary conversation auto-approval remains false
- default/background unattended apply remains false

## Safety contract

This command is read-only:

- `read_only=true`
- `mutated=false`
- no scheduler cycle is executed
- no apply is executed
- no scheduler config is written
- no background or cron is installed or enabled

The report includes a command-preview payload for the later explicit one-shot boundary:

- dogfood action: `ordinary-turn-default-automation-scheduler-one-shot`
- schedule phrase: `run-one-local-default-automation-schedule-v1`
- apply phrase: `apply-exact-ordinary-turn-default-automation-candidate-v1`
- actor required
- private reason placeholder required
- previous evidence rollup required
- post-apply verification required after run
- background/cron install remains false

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_one_cycle_smoke_is_read_only_gate -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 8 passed, 227 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 43 passed, 192 deselected
```

Full suite: `uv run pytest tests/ -q` -> `417 passed, 1 xfailed`.

## Remaining gap toward 100%

The next safe slice is the exact one-cycle execution boundary that consumes this green smoke gate and the existing scheduler one-shot path. It must still stop after one package, require private operator inputs, require previous evidence rollup where applicable, and force immediate post-apply verification before any next cycle.

Background/cron activation remains blocked until a later exact-approved install preflight with kill-switch, CI watchdog, rollback evidence, bounded cadence, and explicit separate activation phrase.
