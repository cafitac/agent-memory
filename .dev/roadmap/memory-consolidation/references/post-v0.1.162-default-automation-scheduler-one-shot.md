# post-v0.1.162 default automation scheduler one-shot

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 01:47 KST

## Summary

This checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-one-shot`, the first real local opt-in schedule wrapper over the default-automation scheduler corridor.

The command consumes a green `dogfood_ordinary_turn_default_automation_scheduler_status` artifact, validates the status packet and all next-cycle inputs, then runs exactly one scheduler integration cycle and immediately runs the required scheduler package collector. It stops after packaging fresh rollback/post-apply/evidence-rollup artifacts.

## Command

```bash
agent-memory dogfood ordinary-turn-default-automation-scheduler-one-shot "$DB_PATH" \
  --scheduler-status "$SCHEDULER_STATUS_JSON" \
  --db-approval-mode copy \
  --report-dir "$REPORT_DIR" \
  --schedule-approval-phrase run-one-local-default-automation-schedule-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --output "$REPORT_DIR/scheduler-one-shot.json"
```

`--db-approval-mode` is intentionally explicit:

- `copy`: copies the supplied DB to the report directory and mutates only that copy.
- `explicit-approved-db`: uses the supplied DB directly, reserved for a separately approved local/manual run.

## Safety boundary

The one-shot wrapper is not unattended or recurring automation. It requires:

- a green scheduler-status artifact;
- exact schedule phrase `run-one-local-default-automation-schedule-v1`;
- explicit `copy` or `explicit-approved-db` mode;
- enabled policy-state, policy-gate, previous evidence rollup, previous scheduler report, and post-apply verifier paths from the status packet;
- exactly one scheduler integration cycle;
- immediate scheduler package collection after that cycle.

It still blocks by design:

- unattended/default/background authority;
- background or recurring schedule enablement;
- broad ordinary conversation auto-approval;
- more than one scheduler cycle per invocation;
- repeated apply without fresh package/post-apply evidence;
- default-ranking mutation;
- collapse/delete;
- telemetry reset;
- unreviewed promotion.

## Positive copy smoke

Smoke report directory:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-one-shot-positive-copy-smoke-20260517T164220Z/`

One-shot output:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-one-shot-positive-copy-smoke-20260517T164220Z/scheduler-one-shot.json`

Result:

- `quality_gate.pass=true`
- `db_approval_mode=copy`
- `source_db_mutated=false`
- `copy_db_mutated=true`
- `scheduler_status.quality_gate_pass=true`
- `scheduler_integration.quality_gate_pass=true`
- `scheduler_integration.selected_trace_ref=experience_trace:4201`
- `scheduler_package.quality_gate_pass=true`
- `scheduler_package.evidence_rollup_quality_gate_pass=true`
- `automation_authority.executes_scheduler_cycle=true`
- `automation_authority.executes_apply=true`
- `automation_authority.max_scheduler_cycles=1`
- `automation_authority.enables_unattended_default_authority=false`
- `automation_authority.background_or_recurring_schedule_enabled=false`

A live-source copy-mode run against `/Users/reddit/.agent-memory/memory.db` also correctly stayed fail-closed when no eligible preference candidate existed at that moment: source DB SHA/table counts were unchanged and the only blocker was `scheduler_integration_not_green` from `no_eligible_preference_candidates`.

## Validation

RED observed:

- `ordinary-turn-default-automation-scheduler-one-shot` was initially an invalid dogfood subcommand.

GREEN validation:

- `tests/test_cli.py -q -k "scheduler_one_shot"`: `1 passed, 224 deselected`
- `tests/test_cli.py -q -k "ordinary_turn_default_automation_scheduler"`: `10 passed, 215 deselected`
- `tests/test_cli.py -q -k "ordinary_turn_default_automation"`: `33 passed, 192 deselected`
- `tests/ -q`: `407 passed, 1 xfailed`

## Current estimate

- Safety-gated operational north-star: still 99%+.
- Scoped local human-brain-like memory lifecycle: about 99.99995%+.

The remaining gap is now extremely narrow: durable local operator ergonomics/CI watch around this one-shot wrapper, plus a later explicit decision on whether any real recurring scheduler should ever be enabled. The code still does not enable unattended/default/background authority.

## Recommended next safe slice

Add a read-only one-shot history/status rollup that consumes one or more `scheduler-one-shot.json` artifacts and proves repeated one-shot invocations stopped after packaging, used fresh evidence, and did not mutate source DB in copy mode. Keep real recurring/background scheduling blocked until that rollup is green across repeated local one-shot artifacts.
