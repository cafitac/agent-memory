# Post-v0.1.162 default automation freshness-boundary copy-live smoke

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-17
Branch: `develop`

## Summary

This source checkpoint adds `dogfood ordinary-turn-default-automation-freshness-boundary-smoke`, a copy-DB smoke command for the ordinary-turn default automation apply boundary.

The command verifies, without mutating the source/live DB, that:

- an enabled exact opt-in policy-state file is honored;
- a first exact reviewed default-automation apply can run only on the copied DB;
- a second apply is blocked when a previous evidence rollup is missing;
- the second apply succeeds only after a green previous `dogfood_ordinary_turn_default_automation_evidence_rollup` artifact is supplied;
- the source DB SHA-256 and table counts remain unchanged.

This is smoke/report hardening only. It does not enable ordinary conversation auto-approval, unattended default/background apply, default retrieval ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion.

## New CLI

```bash
agent-memory dogfood ordinary-turn-default-automation-freshness-boundary-smoke \
  /Users/reddit/.agent-memory/memory.db \
  --report-dir /Users/reddit/.agent-memory/reports/<dir> \
  --policy ordinary-turn-default-automation-policy-v1 \
  --actor hermes-agent \
  --reason "copy-live smoke for default automation freshness boundary" \
  --output /Users/reddit/.agent-memory/reports/<dir>/freshness-boundary-smoke.json
```

The command copies the input DB into the report directory, initializes only the copy, writes local test artifacts under the report directory, inserts two synthetic preference-shaped ordinary turns into the copy, and exercises the boundary there.

## Live copy smoke

Live/source smoke output:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-freshness-boundary-smoke-20260517T083948Z/freshness-boundary-smoke.json`

Ref-safe result summary:

```json
{
  "kind": "dogfood_ordinary_turn_default_automation_freshness_boundary_smoke",
  "quality_gate": {
    "pass": true,
    "decision": "ordinary_turn_default_automation_freshness_boundary_copy_smoke_green",
    "blocked_reasons": []
  },
  "source_db_mutated": false,
  "copied_db_mutated": true,
  "boundary_checks": {
    "policy_state_enabled": true,
    "prior_apply_simulated": true,
    "missing_rollup_blocked": true,
    "fresh_rollup_apply_passed": true,
    "source_db_unchanged": true
  }
}
```

## Verification

RED observed:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_freshness_boundary_smoke_uses_copy_and_requires_rollup -q
```

Initially failed because `ordinary-turn-default-automation-freshness-boundary-smoke` was not a registered dogfood action.

GREEN verification:

```bash
.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_freshness_boundary_smoke_uses_copy_and_requires_rollup -q
# 1 passed

.venv/bin/python -m pytest tests/test_cli.py -q -k "ordinary_turn_default_automation"
# 20 passed, 192 deselected

.venv/bin/python -m pytest tests/ -q
# 394 passed, 1 xfailed
```

## Progress framing

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.999%+.
- Remaining gap: only explicit-opt-in scheduler/default wiring, if any, under the same fail-closed policy state and fresh-evidence boundary. This must still not become unattended background/default apply.

## Next safe slice

If continuing toward 100%, add explicit opt-in scheduler/default wiring as a read-only or one-candidate bounded runner that consumes the policy-state file and fresh evidence gate. It must keep:

- `ordinary_conversation_auto_approval=false`;
- `default_background_auto_approval_allowed=false`;
- `unattended_default_apply_allowed=false`;
- `max_apply_without_fresh_post_apply_verification=0`;
- no broad/background apply, default-ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion.
