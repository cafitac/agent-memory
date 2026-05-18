# post-v0.1.162 default automation enabled recurring scheduler one-cycle execution boundary

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 10:26 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-execute`.

The command consumes the green enabled recurring scheduler config one-cycle smoke gate plus a green scheduler status artifact, then delegates to the existing explicit scheduler one-shot path. It runs at most one scheduler/apply cycle, immediately collects the scheduler package, writes a summary report, and stops.

It is the first boundary after the enabled config smoke gate that actually executes the explicit one-shot. It still does not install cron, start background scheduling, or grant unattended/default authority.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-execute \
  "$DB_PATH" \
  --one-cycle-smoke "$REPORT_DIR/enabled-recurring-scheduler-config-one-cycle-smoke.json" \
  --scheduler-status "$REPORT_DIR/scheduler-status.json" \
  --db-approval-mode copy \
  --report-dir "$REPORT_DIR/one-cycle-execute" \
  --schedule-approval-phrase run-one-local-default-automation-schedule-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-config-one-cycle-execute.json"
```

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_config_one_cycle_execute_green_ran_one_shot_packaged_and_stopped`

A green report proves:

- the one-cycle smoke gate was consumed and green;
- the smoke gate was read-only and had not already executed scheduler/apply;
- the smoke gate still required max one candidate, package-stop, post-apply verification before any later cycle, previous evidence rollup, CI watch, kill-switch, and rollback evidence;
- the command preview still pointed only to `ordinary-turn-default-automation-scheduler-one-shot` with schedule phrase `run-one-local-default-automation-schedule-v1` and apply phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`;
- the delegated scheduler one-shot was green;
- the scheduler package was collected;
- execution stopped after exactly one package;
- copy mode preserves the source DB;
- background/cron and unattended/default authority remain false.

## Safety contract

This command may mutate only the explicit target boundary:

- in `copy` mode, it copies the DB and mutates only the copy;
- in `explicit-approved-db` mode, the caller has explicitly selected the mutable DB;
- `max_scheduler_cycles=1`;
- no background worker is started;
- no cron or OS service is installed;
- no ordinary conversation auto-approval is enabled;
- no repeated apply is allowed without a fresh post-apply verification/evidence rollup chain.

Authority flags preserved:

- `enables_unattended_default_authority=false`
- `background_or_recurring_schedule_enabled=false`
- `ordinary_conversation_auto_approval=false`
- `unattended_default_apply_allowed=false`

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_config_one_cycle_execute_consumes_smoke_gate -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "one_cycle_execute or one_cycle_smoke"
# 2 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "enabled_recurring_scheduler_config or disabled_recurring_scheduler_config"
# 9 passed, 227 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 44 passed, 192 deselected
```

Full suite:

```bash
uv run pytest tests/ -q
# 418 passed, 1 xfailed
```

## Remaining gap toward 100%

The next safe slice is post-run verification hardening over the one-cycle execution report:

1. consume `enabled-recurring-scheduler-config-one-cycle-execute.json`;
2. verify the delegated one-shot report and package evidence rollup are fresh and green;
3. verify source/copy DB mutation boundaries;
4. verify no background/cron/unattended authority flags drifted;
5. emit a read-only readiness packet for recurrence-install preflight only.

Background/cron activation remains blocked until a later exact-approved install preflight and a separate activation phrase with kill-switch, CI watchdog, rollback evidence, bounded cadence, and repeated stale-evidence prevention.
