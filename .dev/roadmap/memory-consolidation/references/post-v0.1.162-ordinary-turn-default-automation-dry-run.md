# post-v0.1.162 ordinary-turn default automation dry-run

Date: 2026-05-17 10:36 KST
Status: source/develop checkpoint; not released; live DB not mutated.

## Summary

Added `dogfood ordinary-turn-default-automation-dry-run`, a read-only/ref-safe dry-run under the exact default automation policy gate.

The command consumes a saved green `dogfood_ordinary_turn_default_automation_policy_gate` artifact and scans ordinary-turn traces for the narrowest candidate shape: non-secret preference-shaped summaries (`User prefers ...`). It emits only trace refs, content hashes, summary hashes, metadata, and aggregate counts. It does not include raw trace summaries, transcripts, query text, content, raw reasons, backup content, report bodies, or sample values.

Green decision is:

```text
ordinary_turn_default_automation_dry_run_ready_for_exact_single_candidate_review_keep_default_blocked
```

This is still not default automation enablement. It keeps:

- `read_only=true`
- `mutated=false`
- `default_retrieval_unchanged=true`
- `ordinary_conversation_auto_approval=false`
- `default_auto_approval_enabled=false`
- `default_background_auto_approval_allowed=false`
- `unattended_default_apply_allowed=false`
- `apply_supported=false`
- `apply_executed=false`

## Source changes

- `src/agent_memory/api/cli.py`
  - added `_dogfood_ordinary_turn_default_automation_dry_run_payload`
  - added parser/action `dogfood ordinary-turn-default-automation-dry-run`
  - validates policy gate kind/read-only/no-mutation/default-unchanged/privacy/forbidden-authority fields
  - blocks red or not-ready policy gates
  - bounds candidate count by policy gate `max_candidates_per_run`
  - selects only non-secret preference-shaped ordinary turns
- `tests/test_cli.py`
  - added green dry-run test with one selected ref-safe candidate and no DB table-count mutation
  - added red policy-gate blocking test

## Verification

RED observed:

```text
.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_dry_run_lists_ref_safe_candidates -q
# failed: invalid choice 'ordinary-turn-default-automation-dry-run'
```

Focused GREEN:

```text
.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn_default_automation_dry_run or ordinary_turn_default_automation_policy_gate'
# 4 passed, 192 deselected
```

Broader ordinary-turn GREEN:

```text
.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn'
# 23 passed, 173 deselected
```

Full suite GREEN:

```text
.venv/bin/python -m pytest tests/ -q
# 378 passed, 1 xfailed in 194.17s
```

## Progress estimate after this checkpoint

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.97-99.98%.
- Remaining gap: a separate exact-reviewed one-candidate default-automation smoke/apply corridor, then repeated post-apply verification/rollback evidence, before any consideration of opt-in default enablement.

## Next safe slice

Add a separate exact-reviewed one-candidate default-automation smoke/apply corridor, still not unattended and still not default-enabled. It should require:

- saved green `dogfood_ordinary_turn_default_automation_dry_run` artifact
- exact policy `ordinary-turn-default-automation-policy-v1`
- exact enablement phrase only if explicitly intended for opt-in dry-run/smoke, not broad default enablement
- one candidate ref
- actor/reason
- pre-apply backup and SHA-256 audit
- conflict/duplicate preflight
- post-apply verification and rollback replay

Do not enable ordinary conversation auto-approval, unattended default/background apply, broad apply, default retrieval-ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion from this dry-run.
