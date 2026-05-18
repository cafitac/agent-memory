# post-v0.1.162 default automation enabled recurring scheduler activation packet verification

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 11:23 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet-verify`.

The command consumes a green activation packet and emits a read-only verifier for the exact final start boundary. It still does not start background/cron, run the scheduler, apply memory, write scheduler config, or grant unattended/default authority.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet-verify \
  --activation-packet "$REPORT_DIR/enabled-recurring-scheduler-activation-packet.json" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-activation-packet-verification.json"
```

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_activation_packet_verification_green_ready_for_exact_final_start_only`

A green report proves:

- the activation packet artifact is green/read-only/non-mutating;
- the artifact is hash-bound via its JSON report SHA-256;
- the packet is ready only for the exact final start slice;
- background/cron start remains blocked in the packet and in authority flags;
- exact final start approval remains required;
- per-cycle post-apply verification and package-stop remain required;
- max candidates per scheduler cycle remains `1`;
- forbidden authority and privacy flags remain ref-safe.

## Safety contract

The command is verifier-only:

- `read_only=true`
- `mutated=false`
- `automation_authority.executes_scheduler_cycle=false`
- `automation_authority.executes_apply=false`
- `automation_authority.writes_scheduler_config=false`
- `automation_authority.installs_background_or_cron=false`
- `automation_authority.starts_background_or_cron=false`
- `automation_authority.enables_unattended_default_authority=false`

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_activation_packet_verifier_requires_green_packet -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "activation_packet or recurrence_install_preflight or post_run_verification or one_cycle_execute or one_cycle_smoke"
# 6 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 48 passed, 192 deselected
```

Full suite:

```bash
uv run pytest tests/ -q
# 422 passed, 1 xfailed
```

## Remaining gap toward 100%

The next safe slice is the final exact start boundary itself: a disabled-by-default, fail-closed local start mechanism that consumes this verifier and refuses to start unless the exact final start phrase and all per-cycle guards are present.

Actual recurring background/cron start remains blocked until that final exact start slice is implemented and verified.
