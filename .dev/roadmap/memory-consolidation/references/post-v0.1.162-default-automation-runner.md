# Post-v0.1.162 default automation runner

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-17

## Summary

The source checkout now has `dogfood ordinary-turn-default-automation-runner`, an explicit opt-in runner for the ordinary-turn default automation corridor.

The runner wires together the existing fail-closed pieces:

1. enabled local policy-state config;
2. green default-automation policy gate;
3. read-only default-automation dry-run;
4. at most one selected candidate;
5. exact approval phrase, actor, and private reason;
6. existing one-candidate apply corridor;
7. previous evidence rollup requirement after any prior default-automation apply.

This is not broad ordinary conversation auto-approval and not unattended/background default apply. It only runs when a caller explicitly invokes the command with the exact apply approval phrase and required artifacts.

## Command contract

New command:

```bash
agent-memory dogfood ordinary-turn-default-automation-runner "$DB" \
  --policy-gate "$POLICY_GATE" \
  --policy-state-config "$POLICY_STATE" \
  --report-dir "$REPORT_DIR" \
  --policy ordinary-turn-default-automation-policy-v1 \
  --approval-phrase apply-exact-ordinary-turn-default-automation-candidate-v1 \
  --actor "$ACTOR" \
  --reason "$PRIVATE_REASON" \
  --previous-evidence-rollup "$PREVIOUS_ROLLUP" \
  --output "$REPORT_DIR/default-automation-runner.json"
```

`--previous-evidence-rollup` is optional only before the first prior default-automation apply. Once any `ordinary_turn_default_automation_approved_as` relation exists in the target DB, the runner inherits the apply corridor's hard block until a green `dogfood_ordinary_turn_default_automation_evidence_rollup` is supplied.

## Safety boundary

The runner must keep:

- `ordinary_conversation_auto_approval=false`
- `default_background_auto_approval_allowed=false`
- `unattended_default_apply_allowed=false`
- `max_default_candidates_per_run=1`
- `repeated_apply_without_new_approval_allowed=false`
- default retrieval unchanged
- no collapse/delete, telemetry reset, default ranking mutation, or unreviewed promotion

A green runner report means exactly one exact-approved preference-shaped ordinary-turn candidate was applied and the process must stop for post-apply verification/evidence rollup before any next run.

## Verification

RED:

- New tests initially failed because `ordinary-turn-default-automation-runner` was not a registered dogfood subcommand.

Focused/source verification:

```bash
.venv/bin/python -m pytest tests/test_cli.py -q -k "ordinary_turn_default_automation_runner"
# 3 passed, 212 deselected

.venv/bin/python -m pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 23 passed, 192 deselected

.venv/bin/python -m pytest tests/ -q
# 397 passed, 1 xfailed
```

Copy-live smoke:

- Script: `/tmp/agent_memory_default_runner_smoke.py`
- Report directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-runner-smoke-20260517T090307Z`
- Runner report: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-runner-smoke-20260517T090307Z/default-automation-runner.json`
- Result: `quality_gate.pass=true`, `apply_executed=true`, `mutated_copy=true`, `source_db_mutated=false`, `ordinary_conversation_auto_approval=false`, `unattended_default_apply_allowed=false`.

## Next safe slice

The next safe slice is a scheduler-facing wrapper/runbook that invokes this runner only after fresh post-apply verification/evidence rollup is present, or a copy-live smoke for repeated runner invocation with `--previous-evidence-rollup`.

Do not implement broad/background unattended apply, ordinary conversation auto-approval, default ranking rollout, collapse/delete, telemetry reset, or unreviewed promotion from this runner checkpoint.
