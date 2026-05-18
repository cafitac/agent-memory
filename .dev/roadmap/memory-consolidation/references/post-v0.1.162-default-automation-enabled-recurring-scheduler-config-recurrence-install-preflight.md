# post-v0.1.162 default automation enabled recurring scheduler recurrence-install preflight

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 11:10 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-recurrence-install-preflight`.

The command consumes a green one-cycle post-run verification artifact and emits a read-only recurrence-install preflight packet. It still does not install background/cron, start a scheduler, apply memory, or write scheduler config.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-recurrence-install-preflight \
  --post-run-verification "$REPORT_DIR/enabled-recurring-scheduler-config-one-cycle-post-run-verification.json" \
  --approval-phrase preflight-recurrence-install-default-automation-scheduler-v1 \
  --cadence-policy "$PRIVATE_CADENCE_POLICY" \
  --kill-switch-policy "$PRIVATE_KILL_SWITCH_POLICY" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-config-recurrence-install-preflight.json"
```

`--cadence-policy` and `--kill-switch-policy` are hashed only. The report stores SHA-256 values and does not echo the raw policy text.

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_recurrence_install_preflight_green_ready_for_activation_packet_only`

A green report proves:

- the post-run verifier artifact is green/read-only/non-mutating;
- one-cycle execute, one-shot, one-shot hash binding, package, evidence rollup, source/copy boundary, and package-stop checks are all green;
- the post-run verifier still states background/cron install is not allowed;
- the post-run verifier still states unattended/default authority is not allowed;
- exact install approval and fresh post-run verification requirements are present;
- cadence and kill-switch policy inputs are present but hash-only;
- CI health watch, rollback evidence, stale-evidence prevention, and max one candidate per cycle are explicit activation-packet requirements.

## Safety contract

The command is readiness-only:

- `read_only=true`
- `mutated=false`
- `automation_authority.executes_scheduler_cycle=false`
- `automation_authority.executes_apply=false`
- `automation_authority.writes_scheduler_config=false`
- `automation_authority.installs_background_or_cron=false`
- `automation_authority.enables_unattended_default_authority=false`

Even when green, it emits:

- `recurrence_install_gate.installs_background_or_cron=false`
- `recurrence_install_gate.activation_allowed=false`
- `recurrence_install_gate.requires_exact_activation_approval=true`

So this slice prepares the activation-packet boundary but does not activate recurrence.

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_recurrence_install_preflight_requires_green_post_run_verifier -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "recurrence_install_preflight or post_run_verification or one_cycle_execute or one_cycle_smoke"
# 4 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 11 passed, 227 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 46 passed, 192 deselected
```

Full suite:

```bash
uv run pytest tests/ -q
# 420 passed, 1 xfailed
```

## Remaining gap toward 100%

The next safe slice is an exact-approved activation packet that consumes this preflight and still does not start cron/background by default. It should encode the future activation command, bounded cadence, kill-switch, CI watchdog, rollback evidence, stale evidence prevention, package-stop, and per-cycle post-apply verification as activation requirements.

Actual background/cron start remains blocked until a final exact activation/start slice.
