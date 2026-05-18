# post-v0.1.162 default automation enabled recurring scheduler activation packet

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 11:13 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet`.

The command consumes a green recurrence-install preflight artifact and emits an exact-approved activation packet for the final start boundary. It still does not start background/cron, run the scheduler, apply memory, write scheduler config, or grant unattended/default authority.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet \
  --recurrence-install-preflight "$REPORT_DIR/enabled-recurring-scheduler-config-recurrence-install-preflight.json" \
  --approval-phrase activate-recurring-default-automation-scheduler-packet-v1 \
  --activation-window-policy "$PRIVATE_ACTIVATION_WINDOW_POLICY" \
  --ci-watchdog-policy "$PRIVATE_CI_WATCHDOG_POLICY" \
  --rollback-policy "$PRIVATE_ROLLBACK_POLICY" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-activation-packet.json"
```

`--activation-window-policy`, `--ci-watchdog-policy`, and `--rollback-policy` are hashed only. The report stores SHA-256 values and does not echo raw policy text.

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_activation_packet_green_ready_for_final_start_slice_only`

A green report proves:

- the recurrence-install preflight artifact is green/read-only/non-mutating;
- the preflight remains activation-packet-only and has not already allowed activation;
- background/cron install/start authority is still false;
- unattended/default authority is still false;
- exact final start approval is still required;
- CI health watch, rollback evidence, stale-evidence prevention, per-cycle package stop, and per-cycle post-apply verification remain required;
- max candidates per scheduler cycle remains `1`;
- activation window, CI watchdog, and rollback policies are present but hash-only.

## Safety contract

The command is readiness-only:

- `read_only=true`
- `mutated=false`
- `automation_authority.executes_scheduler_cycle=false`
- `automation_authority.executes_apply=false`
- `automation_authority.writes_scheduler_config=false`
- `automation_authority.installs_background_or_cron=false`
- `automation_authority.starts_background_or_cron=false`
- `automation_authority.enables_unattended_default_authority=false`

Even when green, it emits:

- `activation_packet.ready_for_final_start_slice=true`
- `activation_packet.background_or_cron_start_allowed=false`
- `activation_packet.starts_background_or_cron=false`
- `activation_packet.requires_exact_final_start_approval=true`

So this slice prepares the final start boundary but does not activate recurrence.

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_activation_packet_requires_green_preflight -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "activation_packet or recurrence_install_preflight or post_run_verification or one_cycle_execute or one_cycle_smoke"
# 5 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 11 passed, 228 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 47 passed, 192 deselected
```

Full suite:

```bash
uv run pytest tests/ -q
# 421 passed, 1 xfailed
```

## Remaining gap toward 100%

The next safe slice is a final exact start packet/verifier or disabled-by-default local start boundary that consumes this activation packet and still fail-closes unless the operator supplies the exact final start approval.

Actual recurring background/cron start remains blocked until that final exact start slice is implemented and verified.
