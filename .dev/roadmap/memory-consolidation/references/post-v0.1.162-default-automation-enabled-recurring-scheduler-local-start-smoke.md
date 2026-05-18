# post-v0.1.162 default automation enabled recurring scheduler local start smoke

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 11:57 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-local-start-smoke`.

The command consumes the final-start-boundary report and its local start manifest, verifies the manifest is hash-bound and still constrained, and emits a read-only smoke report. It does not install OS cron, start background processes, execute a scheduler cycle, apply memory, rewrite scheduler config, or grant unattended/default authority.

## Command shape

```bash
agent-memory dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-local-start-smoke \
  --final-start-boundary "$REPORT_DIR/enabled-recurring-scheduler-final-start-boundary.json" \
  --report-dir "$REPORT_DIR/local-start-smoke" \
  --output "$REPORT_DIR/enabled-recurring-scheduler-local-start-smoke.json"
```

Optionally pass `--local-start-manifest` to override the manifest path recorded by the final-start boundary report.

## Green contract

The green decision is:

`ordinary_turn_default_automation_enabled_recurring_scheduler_local_start_smoke_green_ready_for_exact_os_activation_boundary_only`

A green report proves:

- the final-start-boundary report is green and ready for local-start smoke only;
- its local start manifest exists and is hash-bound to the boundary report;
- OS background/cron installation and start are still false;
- scheduler cycle and apply execution are still false;
- max candidates per cycle remains `1`;
- package-stop per cycle and post-apply verification before the next cycle remain required;
- stale evidence prevention remains required;
- forbidden authority and privacy flags remain ref-safe.

## Safety contract

The command is read-only:

- `read_only=true`
- `mutated=false`
- `executes_scheduler_cycle=false`
- `executes_apply=false`
- `writes_scheduler_config=false`
- `installs_background_or_cron=false`
- `starts_background_or_cron=false`
- `enables_unattended_default_authority=false`

If the manifest is tampered, missing, not hash-bound, or widens max candidates, the smoke fails closed and keeps OS activation blocked.

## Validation

Focused validation:

```bash
uv run pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_enabled_recurring_scheduler_final_start_boundary_writes_local_manifest_only -q
# 1 passed

uv run pytest tests/test_cli.py -q -k "local_start_smoke or final_start_boundary or activation_packet or recurrence_install_preflight or post_run_verification or one_cycle_execute or one_cycle_smoke"
# 7 passed, 234 deselected

uv run pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 49 passed, 192 deselected
```

Full suite:

```bash
git diff --check
uv run pytest tests/ -q
# 423 passed, 1 xfailed

uv run pytest tests/test_release_smoke.py -q
# 3 passed
```

## Remaining gap toward 100%

The next safe slice is the separately exact-gated OS background/cron activation boundary. It should be the only command allowed to materialize an OS-level launch definition, and it must remain kill-switchable, CI-green gated, rollback-evidence gated, stale-evidence gated, max-one-candidate bounded, package-stop constrained, and post-apply-verifier constrained.
