# post-v0.1.162 default automation enabled recurring scheduler OS activation boundary and verifier

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 12:11 KST

## Summary

This checkpoint adds two commands:

- `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-boundary`
- `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-verify`

The boundary command consumes a green local-start smoke report and exact OS activation approval, then writes an OS activation definition JSON. It still does not load launchd, install cron, execute a scheduler cycle, apply memory, rewrite scheduler config, or grant unattended/default authority.

The verifier command consumes the boundary report plus activation definition and verifies hash binding, scheduler-command hash, kill-switch state, max-one-candidate bound, package-stop requirement, post-apply-verification requirement, and no widened authority.

## Command shapes

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-boundary \
  --local-start-smoke "$REPORT_DIR/enabled-recurring-scheduler-local-start-smoke.json" \
  --approval-phrase activate-os-background-or-cron-default-automation-scheduler-v1 \
  --activation-kind launchd \
  --scheduler-command "agent-memory dogfood ordinary-turn-default-automation-scheduler-one-shot ..." \
  --schedule-expression "StartInterval=900" \
  --ci-health-status green \
  --kill-switch-path "$REPORT_DIR/STOP-DEFAULT-AUTOMATION" \
  --rollback-plan "unload exact launchd definition and restore previous package evidence" \
  --max-candidates-per-cycle 1 \
  --report-dir "$REPORT_DIR" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-os-activation-boundary.json"

agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-verify \
  --os-activation-boundary "$REPORT_DIR/enabled-recurring-scheduler-os-activation-boundary.json" \
  --expected-scheduler-command "agent-memory dogfood ordinary-turn-default-automation-scheduler-one-shot ..." \
  --output "$REPORT_DIR/enabled-recurring-scheduler-os-activation-verification.json"
```

## Green contracts

Boundary green decision:

`ordinary_turn_default_automation_enabled_recurring_scheduler_os_activation_boundary_green_definition_materialized_for_verification_only`

Verifier green decision:

`ordinary_turn_default_automation_enabled_recurring_scheduler_os_activation_verification_green_ready_for_operator_load_or_install`

A green boundary report proves:

- local-start smoke was green and ready for exact OS activation boundary only;
- exact phrase `activate-os-background-or-cron-default-automation-scheduler-v1` was supplied;
- CI status was explicitly `green`;
- kill-switch path was absent before definition materialization;
- scheduler command and rollback plan are stored only as SHA-256 hashes;
- max candidates per cycle remains `1`;
- package-stop per cycle and post-apply verification before next cycle remain required;
- only an activation definition JSON was written.

A green verifier report proves:

- the activation definition is hash-bound to the boundary report;
- expected scheduler-command hash matches the definition;
- no raw scheduler command was included in the activation definition/report;
- OS service/cron is not loaded/installed by this verifier;
- kill switch remains absent;
- max candidates per cycle remains `1`;
- package-stop and post-apply verification gates remain present.

## Safety contract

The boundary writes a local activation-definition JSON only:

- `writes_os_activation_definition=true` when green
- `loads_os_service_or_installs_cron=false`
- `executes_scheduler_cycle=false`
- `executes_apply=false`
- `writes_scheduler_config=false`
- `enables_unattended_default_authority=false`

The verifier is read-only:

- `read_only=true`
- `mutated=false`
- `loads_os_service_or_installs_cron=false`
- `executes_scheduler_cycle=false`
- `executes_apply=false`

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_os_activation_boundary_and_verifier_are_hash_bound -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "os_activation or local_start_smoke or final_start_boundary or activation_packet or recurrence_install_preflight or post_run_verification or one_cycle_execute or one_cycle_smoke"
# 8 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 50 passed, 192 deselected
```

Full suite:

```bash
git diff --check
uv run pytest tests/ -q
# 424 passed, 1 xfailed

uv run pytest tests/test_release_smoke.py -q
# 3 passed
```

## Progress framing

This reaches the practical 100% design boundary for the scoped local human-brain-like lifecycle if “100%” means bounded, verified, kill-switchable, rollbackable, evidence-chained, one-candidate, package-stopped, and post-apply-verifier-gated recurring memory automation.

It does not mean broad unattended cognition or unbounded autonomous memory mutation. Operator load/install of the verified OS definition remains deliberately outside the automated command path and must be performed only if the green verifier is accepted.
