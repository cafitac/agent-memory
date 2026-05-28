# Post-v0.1.162 live decay decision no-reviewed-candidate gate

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 11:12 KST

## Scope

Continued from the topic-aware supersession preview checkpoint using the real live DB `/Users/reddit/.agent-memory/memory.db`.

Primary run directory: `/tmp/agent-memory-next-live-readonly-20260528T110416`

No mock DB was used for the live decision. No copy-DB smoke was used. Focused tests were used only because the decay decision report contract changed.

## Live evidence

Fresh read-only live artifacts:

- `/tmp/agent-memory-next-live-readonly-20260528T110416/storage-health.json`
  - `kind=dogfood_storage_health`
  - `read_only=true`, `mutated=false`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/trace-quality.json`
  - `kind=dogfood_trace_quality`
  - `read_only=true`, `mutated=false`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/reinforcement-refinement-preview.json`
  - `candidate_count=7`
  - high-tier candidates remain `procedure:1`, `fact:1`, `episode:1`, `fact:6`, `fact:4`, `fact:8`
  - low-tier `fact:5` remains activation-count `1`
  - preview is review-only and mutation-supported is false
- `/tmp/agent-memory-next-live-readonly-20260528T110416/lifecycle-fresh-evidence-preview.json`
  - `quality_gate.pass=true`
  - `post_apply_observation_count=46`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/lifecycle-refresh-reinforcement-preview.json`
  - `preview_candidate_count=7`
  - `new_unapplied_target_candidate_count=0`
  - `target_already_applied_count=7`
  - decision `no_new_lifecycle_review_persistence_ready`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/lifecycle-apply-readiness.json`
  - decision `no_exact_lifecycle_apply_candidates_ready`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/supersession-preview.json`
  - `candidate_count=0`
  - red only on `no_supersession_candidates_ready`

Decay evidence:

- `/tmp/agent-memory-next-live-readonly-20260528T110416/decay-collapse-preview.json`
  - `candidate_count=1`
  - only candidate remains `fact:5`
  - `resolution_hint=collect_more_activation_evidence_before_decay_action`
  - preview remains read-only, no deprecate/collapse/delete mutation supported
- `/tmp/agent-memory-next-live-readonly-20260528T110416/live-retrieval-ranking-fixtures-report.json`
  - generated 9 live approved-memory fixture tasks (`facts=7`, `procedures=1`, `episodes=1`)
  - `retrieval_diagnostics.pass=true`, baseline regressions `0`
- `/tmp/agent-memory-next-live-readonly-20260528T110416/decay-collapse-decision-topic-aware-gate.json`
  - `candidate_count=1`
  - `reviewed_deprecate_candidate_count=0`
  - `quality_gate.pass=false`
  - blocked reason: `no_reviewed_approved_decay_candidates`
  - `deprecate_corridor=blocked_until_reviewed_approved_decay_candidate`
  - `allowed_next_policy=null`
  - collapse proof is still missing `relation_equivalence_or_supersession_chain` and `human_reviewed_candidate_payload`
  - `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`

## Code change

`dogfood decay-collapse-decision` now distinguishes a green preview from an actually actionable reviewed deprecate corridor.

Added report fields:

- `reviewed_deprecate_candidate_count`
- `quality_gate`
- `deprecate_apply_readiness`
- `allowed_next_policy=null` when no reviewed/approved decay candidate exists

This prevents the live `fact:5` collect-more-evidence candidate from looking like an immediately allowed deprecate corridor. The command remains read-only and does not mutate core memories, status rows, relations, retrieval ranking, telemetry, or ordinary-turn automation.

## Verification

Focused tests:

```text
uv run pytest tests/test_cli.py -q -k 'decay_collapse_decision or decay_collapse_preview'
3 passed, 255 deselected
```

Live real-DB verification:

```text
uv run agent-memory dogfood decay-collapse-decision /Users/reddit/.agent-memory/memory.db \
  --fixtures /tmp/agent-memory-next-live-readonly-20260528T110416/live-retrieval-ranking-fixtures.jsonl \
  --baseline-mode lexical \
  --max-baseline-regressions 0 \
  --output /tmp/agent-memory-next-live-readonly-20260528T110416/decay-collapse-decision-topic-aware-gate.json \
  --top 20
```

Result: live decay lane is explicitly blocked for deprecate/apply because there is no reviewed approved decay candidate; collapse/delete remain blocked.

## Stop gates

- Do not deprecate, collapse, or delete `fact:5` from the current decay preview.
- Do not persist duplicate lifecycle reinforcement candidates; all seven preview targets are already applied.
- Do not open supersession/replacement; current supersession candidate count is zero.
- Keep broad/background/default mutation, ordinary conversation auto-approval, default-ranking mutation, telemetry reset, core memory-status writes, retrieval-ranking writes, and unreviewed promotion blocked.

## Next safe action

Continue with real live evidence. Since reinforcement, decay, supersession, and lifecycle apply lanes do not currently expose a new exact apply candidate, the next useful fast path is read-only ordinary-turn readiness / explicit remember-intent evidence collection, or implementing another report-contract tightening only if live evidence shows an ambiguity similar to the decay-decision gap.
