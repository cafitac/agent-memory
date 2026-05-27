# Post-v0.1.162 copy-live one-item G4 apply verification

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-27 18:55 KST

## Context

The previous live scheduled evidence-chain pass was green for bounded partial automation evidence but stopped before the exact one-item copy-live apply because the local macOS volume was out of space. Disk pressure is no longer the blocker, so this pass re-ran the next documented action on a copy of the real live DB rather than on mocks or synthetic fixtures.

## Real-data artifacts

Run directory: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z`

Primary artifacts:

- Copy DB: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/copy-live.db`
- Queue persistence: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/queue-persist.json`
- Human review approval artifact: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/queue-approval-report.json`
- Approved queue preview with gate artifacts: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/queue-preview-approved.json`
- Apply readiness: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/apply-readiness.json`
- Exact one-item apply audit: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/apply-one.json`
- Post-apply operator bundle: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/post-apply-operator-bundle.json`
- Post-apply verification: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/post-apply-verification.json`
- Targeted health checks: `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/live-storage-health-after-copy-apply.json`, `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/copy-storage-health-after-apply.json`, `/tmp/agent-memory-next-real/copy-live-one-item-20260527T095441Z/copy-trace-quality-after-apply.json`

## Observed result

- Source for the copy was the real live DB: `/Users/reddit/.agent-memory/memory.db`.
- The exact apply command targeted only the copy DB and used explicit `--queue-id g4-review:reinforcement:2`, policy `g4-review-queue-apply-v1`, approval phrase `apply-approved-g4-review-queue-items-v1`, actor, reason, backup path, and `--max-apply 1`.
- The copied DB already contained two historical reviewed/applied queue rows (`g4-review:decay-risk:1`, `g4-review:reinforcement:1`). This pass inserted two fresh queue rows, approved the selected new reinforcement item, rejected the other new reinforcement item, and then applied only the selected queue id.
- Apply result on the copy: `mutated=true`, `applied_count=1`, `already_applied_count=0`, `skipped_count=0`, `memory_status_mutated=false`, `default_retrieval_unchanged=true`.
- The applied item was `g4-review:reinforcement:2` targeting `fact:4` with action `apply_reinforcement_marker`. It incremented the copy's reinforcement marker only (`memory_reinforcement_mutated=true`).
- Post-apply verification is green: `quality_gate.pass=true`, decision `g4_post_apply_verification_green_stop_before_next_mutation`, `verified_apply_mutated=true`.
- Copy storage health is `healthy`; copy trace quality over the real 24h telemetry window is `healthy` with recommendation `consider_g4_plan`.
- Live storage health after the pass is `healthy`.

## Source DB boundary

- No `g4-review-queue-apply` command was run against `/Users/reddit/.agent-memory/memory.db` in this pass.
- The live DB did change at the file-hash level during the session because normal Hermes/agent-memory runtime telemetry advanced while the agent was operating. Therefore file SHA alone is not a clean source-preservation proof for this interactive session.
- Targeted table verification shows the live `g4_review_queue_items` and `g4_review_queue_applications` tables still contain only the two historical rows copied at the start; the fresh queue rows and the new application row exist only in the copy DB.

## Decision

The exact one-item copy-live corridor is now green through post-apply verification using real data. This is stronger than the prior readiness-only checkpoint, but it still is not authorization for broad/default/background mutation.

Next safe work:

1. If a live mutation is intentionally taken, keep it to one exact reviewed item with explicit live approval, backup, audit, reason hash, and immediate post-apply verification.
2. Prefer refreshing the pre-apply evidence bundle just before any live one-item corridor because live telemetry is advancing during normal Hermes turns.
3. Keep broad G4 apply, ordinary conversation auto-approval, background/unattended apply, repeated apply without new approval, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.
