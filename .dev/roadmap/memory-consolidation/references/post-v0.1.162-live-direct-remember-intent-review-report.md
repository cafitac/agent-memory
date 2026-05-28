# Post-v0.1.162 live direct remember-intent review report

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 16:12 KST

## Scope

Implemented and exercised a narrow read-only report contract that surfaces explicit `remember_intent` traces directly as review material instead of relying on broad graph-cluster generation.

Live DB: `/Users/reddit/.agent-memory/memory.db`
Run directory: `/tmp/agent-memory-explicit-remember-direct-20260528T160312Z`

No mock DB or copy-DB smoke was used for the live decision.

## Code change

Added CLI command:

```bash
agent-memory dogfood remember-intent-direct-review <DB> \
  --policy remember-preferences-v1 \
  --scope project:agent-memory \
  --limit 5000 \
  --sample-limit 20
```

Report contract:

- `kind=remember_intent_direct_review_report`
- read-only, non-mutating
- surfaces direct `experience_trace:<id>` material
- includes sanitized summary, proposed fact for eligible items, or existing `memory_ref`/`relation_id` for already-linked items
- suppresses secret-like summaries
- does not authorize batch apply, ordinary-turn auto-approval, default ranking mutation, or background mutation

## Live evidence

Artifacts:

- `/tmp/agent-memory-explicit-remember-direct-20260528T160312Z/remember-intent.json`
- `/tmp/agent-memory-explicit-remember-direct-20260528T160312Z/remember-preferences-dry-run.json`
- `/tmp/agent-memory-explicit-remember-direct-20260528T160312Z/remember-intent-direct-review.json`

`remember-intent` over the latest 5000 traces:

- total traces observed: 4953
- `remember_intent=5`
- `ordinary_turn=4948`
- `review_ready_count=5`
- `unsafe_sample_count=0`

Existing narrow remember-preferences dry-run:

- `eligible_count=0`
- `skipped_count=5`
- `blocked_count=0`
- all five skipped because `already_auto_approved`

New direct review report:

- `review_ready_count=5`
- `direct_material_count=5`
- `eligible_count=0`
- `skipped_count=5`
- `blocked_count=0`
- `status_counts={"skipped": 5}`
- `reason_counts={"already_auto_approved": 5}`
- `quality_gate.pass=true`
- decision: `remember_intent_direct_review_material_ready`
- next step: all direct review-ready remember-intent traces are already linked to approved memories; stop before duplicate promotion.

Trace-to-memory links:

- `experience_trace:3768` -> `fact:5`, relation `2`
- `experience_trace:3767` -> `fact:6`, relation `3`
- `experience_trace:3766` -> `fact:7`, relation `4`
- `experience_trace:3765` -> `fact:8`, relation `5`
- `experience_trace:3764` -> `fact:9`, relation `6`

## Interpretation

The previous graph-cluster candidate cross-check was accurate for that lane: broad `trace-candidate-generate` did not surface exact candidates for the five explicit traces. However, direct trace material shows these five explicit remember-intent traces are already linked through the narrow remember-preferences path to approved facts.

Therefore:

- Do not promote from broad graph-cluster generated skeletons.
- Do not create duplicate facts for traces `3764`-`3768`.
- Treat the direct review report as the correct diagnostic for explicit remember-intent trace material.
- Keep ordinary-turn auto-approval and inferred/apply corridors blocked.

## Verification

Focused tests:

```bash
uv run pytest tests/test_cli.py -q -k 'remember_intent_direct_review or remember_intent_report'
```

Result:

- `2 passed, 259 deselected`

## Not done

- No live mutation in this slice.
- No candidate persistence.
- No fact/procedure/episode promotion.
- No memory apply.
- No ranking/default retrieval mutation.
- No core memory-status write.
- No relation write.
- No collapse/delete/deprecate.
- No telemetry reset.
- No ordinary-turn auto-approval or default-background enablement.

## Next step

Stop the explicit remember-intent promotion lane for now because all five direct review-ready traces are already linked to approved memories. Continue with real live evidence in another lane only if `.dev` identifies exact new review material; otherwise keep collecting natural-turn evidence and avoid duplicate promotions.
