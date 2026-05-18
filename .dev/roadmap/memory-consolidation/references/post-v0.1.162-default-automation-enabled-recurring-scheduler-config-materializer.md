# post-v0.1.162 default automation enabled recurring scheduler config materializer

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 09:31 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-materialize`, an exact-approved materializer for the enabled recurring scheduler config file.

The command consumes a green `dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_validate` report and exact phrase `materialize-enabled-recurring-default-automation-scheduler-config-v1`.

It writes only the enabled scheduler config JSON. It does not invoke the scheduler, does not execute apply, and does not install or enable background/cron.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-materialize \
  --enabled-config-validation-report "$VALIDATION_JSON" \
  --scheduler-config "$REPORT_DIR/ordinary-turn-default-automation-recurring-scheduler.enabled.json" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --approval-phrase materialize-enabled-recurring-default-automation-scheduler-config-v1 \
  --output "$REPORT_DIR/enabled-recurring-scheduler-config-materialize.json"
```

## Written config shape

The materialized config is intentionally narrow:

- `kind=ordinary_turn_default_automation_scheduler_config`
- `policy=ordinary-turn-default-automation-policy-v1`
- `enabled=true`
- `mode=enabled_recurring_scheduler_contract_v1`
- `recurring_scheduler_enabled=true`
- `background_or_cron_enabled=false`
- `max_candidates_per_cycle=1`
- requires enabled policy state
- requires green policy gate
- requires previous evidence rollup
- requires package-stop after each cycle
- requires post-apply verification before the next cycle
- requires bounded cadence policy
- requires kill-switch policy
- requires CI health watch
- requires rollback evidence
- later background/cron still requires separate approval
- ordinary conversation auto-approval remains false
- default/background unattended apply remains false
- config flags report `executes_scheduler_cycle=false` and `executes_apply=false` because materialization itself does not run anything

## Safety contract

The materializer may mutate only the requested config file:

- output `read_only=false`
- output `mutated=true`
- `automation_authority.writes_scheduler_config=true`
- `automation_authority.writes_enabled_config_only=true`
- `automation_authority.executes_scheduler_cycle=false`
- `automation_authority.executes_apply=false`
- `automation_authority.background_or_cron_enabled=false`
- `automation_authority.enables_unattended_default_authority=false`

Wrong approval phrase fails non-zero before writing the config file.

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_materialize_green_enabled_config_written_no_background`

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_materialize_writes_enabled_config_only -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 7 passed, 227 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 42 passed, 192 deselected
```

Full suite: `uv run pytest tests/ -q` -> `416 passed, 1 xfailed`.

## Remaining gap toward 100%

The next safe slice is a materialized enabled-config validation/smoke gate that reads the enabled config and proves it is usable for a single explicit scheduler cycle without actually installing background/cron. The later background/cron activation still needs its own exact approval, kill-switch, CI-watchdog, rollback, cadence, and post-apply verifier contracts.
