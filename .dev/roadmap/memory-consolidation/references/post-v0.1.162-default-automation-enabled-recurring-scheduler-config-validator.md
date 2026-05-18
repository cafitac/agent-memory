# post-v0.1.162 default automation enabled recurring scheduler config validator

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 09:31 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-validate`, a read-only fail-closed validator for the data-only enabled recurring scheduler config contract.

The command consumes a green `dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_contract` report and confirms that the later materialization contract is still narrow enough to proceed to a separate enabled-config materialization design.

It does not write an enabled config, does not invoke the scheduler, does not execute apply, and does not enable background/cron.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-validate \
  --enabled-config-contract-report "$CONTRACT_JSON" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --output "$REPORT_DIR/enabled-recurring-scheduler-config-validate.json"
```

## Green contract

A green validator requires:

- source report kind is `dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_contract`
- source report is read-only and non-mutating
- source quality gate is green with no blocked reasons
- `config_contract.target_state=enabled`
- `config_contract.recurring_scheduler_enabled=true`
- `config_contract.background_or_cron_enabled=false`
- scheduler/apply are allowed only when a later materialized config is explicitly used
- max candidates per cycle remains `1`
- enabled policy state, green policy gate, fresh previous evidence rollup, package-stop, post-apply verification, bounded cadence, kill-switch, CI watch, and rollback evidence remain required
- materialization and background/cron still require separate approvals
- contract authority remains status-only and does not write config or run cycles
- privacy and forbidden-authority blocks remain ref-safe

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_validate_green_materialization_design_ready`

## Red/tamper behavior

The validator fails closed if a contract drifts toward unsafe recurrence. Covered tamper examples include:

- `background_or_cron_enabled=true`
- `max_candidates_per_cycle > 1`
- `automation_authority.writes_scheduler_config=true`

The red decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_validate_red_keep_materialization_blocked`

## Safety contract

The validator itself remains status-only:

- `read_only=true`
- `mutated=false`
- `automation_authority.executes_scheduler_cycle=false`
- `automation_authority.executes_apply=false`
- `automation_authority.writes_scheduler_config=false`
- `automation_authority.recurring_scheduler_enabled=false`
- `automation_authority.background_or_cron_enabled=false`
- `approval_boundary.current_validation_writes_enabled_config=false`
- `approval_boundary.current_validation_executes_scheduler_cycle=false`

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_validate_is_fail_closed -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 6 passed, 227 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 41 passed, 192 deselected
```

Full suite: `uv run pytest tests/ -q` -> `415 passed, 1 xfailed`.

## Remaining gap toward 100%

The next safe slice is enabled recurring scheduler config materialization with a separate exact approval phrase. That slice may write an enabled config file but must still not install background/cron or run unattended recurrence. Background/cron activation remains a later, separate boundary with kill-switch, CI-watchdog, rollback, bounded cadence, and post-apply verification contracts.
