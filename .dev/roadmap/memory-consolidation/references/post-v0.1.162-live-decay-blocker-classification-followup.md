# post-v0.1.162 live decay blocker classification follow-up

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 02:58 KST

## Scope

Follow-up from the exact live recurrent reinforcement stop gate. The next `.dev` action was to restart from real live read-only evidence and focus on the remaining scheduled/decay blocker, not to repeat live apply.

Live DB: `/Users/reddit/.agent-memory/memory.db`
Run directory: `/tmp/agent-memory-decay-followup-20260527T175543Z`

No mock DB, smoke DB, default-ranking migration, collapse/delete, telemetry reset, or unattended/background mutation was used.

## Read-only live evidence

Artifacts:

- Storage health: `/tmp/agent-memory-decay-followup-20260527T175543Z/storage-health.json`
  - `status=healthy`
  - warnings `[]`
- Trace quality: `/tmp/agent-memory-decay-followup-20260527T175543Z/trace-quality.json`
  - `status=healthy`
  - recommendation `consider_g4_plan`
- Decay risk report: `/tmp/agent-memory-decay-followup-20260527T175543Z/decay-risk-report.json`
  - `read_only=true`
  - activation window size `400`
- Scheduled dry-run: `/tmp/agent-memory-decay-followup-20260527T175543Z/scheduled-dry-run.json`
  - `kind=dogfood_scheduled_dry_run`
  - `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`
  - `quality_gate.pass=false`
  - blocked reason: `decay_risk_above_threshold`
  - decay candidate decomposition: `candidate_count=7`, `collect_more_activation_evidence_before_decay_action=1`, `monitor_only_no_mutation=6`
  - trace/background checks are not blockers.
- Scheduled blocker resolution: `/tmp/agent-memory-decay-followup-20260527T175543Z/scheduled-blocker-resolution.json`
  - `kind=dogfood_scheduled_blocker_resolution`
  - `resolution_gate.pass=false`
  - unresolved blocker: `decay_risk_above_threshold`

## Evidence-blocker packet and classification

Generated the exact read-only evidence-blocker packet:

- Packet: `/tmp/agent-memory-decay-followup-20260527T175543Z/scheduled-evidence-blocker-packet.json`
  - `kind=dogfood_scheduled_evidence_blocker_packet`
  - one evidence-collection candidate: `fact:5`
  - candidate score `0.45`
  - activation count `1`
  - offered classifications:
    - `keep_blocked_collect_more_activation_evidence`
    - `manual_review_harmless_low_activation`
    - `manual_review_stale_or_wrong_follow_up_required`

Inspected the candidate using the packet's ref-safe operator commands:

- Review explain: `/tmp/agent-memory-decay-followup-20260527T175543Z/fact5-review-explain.json`
- Review history: `/tmp/agent-memory-decay-followup-20260527T175543Z/fact5-review-history.json`
- Graph inspect: `/tmp/agent-memory-decay-followup-20260527T175543Z/fact5-graph-inspect.json`

Findings:

- `fact:5` is approved and visible in default retrieval.
- It represents the user preference for real downloaded-install QA for agent-memory milestone releases.
- It has a reviewed approval history and an inbound reviewed evidence edge from the original experience trace.
- The low score is low recent activation, not evidence that the memory is stale, wrong, disconnected, or unsafe.

Classification applied read-only:

- Classification validation: `/tmp/agent-memory-decay-followup-20260527T175543Z/scheduled-evidence-blocker-classification-validation.json`
  - `kind=dogfood_scheduled_evidence_blocker_classification_validation`
  - `classification_gate.pass=true`
  - `fact:5=manual_review_harmless_low_activation`
  - `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`
- Classification resolution: `/tmp/agent-memory-decay-followup-20260527T175543Z/scheduled-evidence-blocker-classification-resolution.json`
  - `kind=dogfood_scheduled_evidence_blocker_classification_resolution`
  - `resolution_gate.pass=true`
  - decision `scheduled_evidence_blockers_resolved_for_bounded_partial_automation_only`
  - unresolved refs `[]`
  - hard-blocked refs `[]`
  - follow-up refs `[]`
  - `bounded_partial_automation_allowed=true`
  - `broad_g4_apply_allowed=false`
  - `ordinary_conversation_auto_approval=false`
  - `writes_memory_status=false`
  - `writes_retrieval_ranking=false`
  - `enables_background_or_unattended_apply=false`

## Lifecycle readiness after classification

Re-ran lifecycle checks against the same real live DB:

- Fresh lifecycle evidence: `/tmp/agent-memory-decay-followup-20260527T175543Z/lifecycle-fresh-evidence-preview.json`
  - `quality_gate.pass=true`
  - `post_apply_observation_count=13`
- Lifecycle refresh preview: `/tmp/agent-memory-decay-followup-20260527T175543Z/lifecycle-candidate-refresh-preview.json`
  - `quality_gate.pass=false`
  - decision `no_new_lifecycle_review_persistence_ready`
  - `preview_candidate_count=7`
  - `new_unapplied_target_candidate_count=0`
  - `target_already_applied_count=7`
- Lifecycle apply readiness: `/tmp/agent-memory-decay-followup-20260527T175543Z/lifecycle-apply-readiness.json`
  - `quality_gate.pass=false`
  - decision `no_exact_lifecycle_apply_candidates_ready`
- Pending reinforcement list: `/tmp/agent-memory-decay-followup-20260527T175543Z/lifecycle-pending-reinforcement-list.json`
  - `count=0`

## Read-only automation policy and candidate-lane follow-up

Used the green classification-resolution artifact state to run the next real DB read-only readiness pass.

Artifacts:

- Live evidence bundle: `/tmp/agent-memory-decay-followup-20260527T175543Z/live-evidence-bundle.json`
  - output dir: `/tmp/agent-memory-decay-followup-20260527T175543Z/live-evidence-bundle`
  - `quality_gate.pass=true`
  - fixture task count `7`
  - rollback checked application count `14`
  - application audit count `7`
  - Hermes doctor `ok`, plugin enabled, hook occurrences `0`, duplicate context injection risk `false`
- Live evidence bundle comparison: `/tmp/agent-memory-decay-followup-20260527T175543Z/live-evidence-bundle-compare.json`
  - `quality_gate.pass=true`
  - decision `live_evidence_bundle_stable_for_next_read_only_automation_policy_slice`
  - ranking baseline regressions `0`
- Automation policy readiness: `/tmp/agent-memory-decay-followup-20260527T175543Z/automation-policy-readiness.json`
  - `quality_gate.pass=true`
  - decision `automation_policy_readiness_classified_next_lanes`
  - narrow reviewed apply is eligible only for a future exact approval slice
  - reinforcement refinement, decay forgetting, and supersession remain review-candidate lanes only
  - ordinary conversation auto-approval remains blocked
  - default ranking migration is exact-review-only
  - `executes_apply=false`, `broad_g4_apply_allowed=false`, `ordinary_conversation_auto_approval=false`, `default_ranking_mutated=false`, `collapse_delete_apply_allowed=false`, `telemetry_reset_apply_allowed=false`
- Reinforcement refinement preview: `/tmp/agent-memory-decay-followup-20260527T175543Z/reinforcement-refinement-preview.json`
  - `quality_gate.pass=true`
  - `candidate_count=7`
  - review-only, no apply support
- Trace candidate generation preview: `/tmp/agent-memory-decay-followup-20260527T175543Z/trace-candidate-generate.json`
  - `quality_gate.pass=true`
  - `candidate_count=10`
  - generated skeletons still require human fields and review
- Pending trace-candidate inventory: `/tmp/agent-memory-decay-followup-20260527T175543Z/trace-candidate-list-pending.json`
  - `count=7`

## Decision

The scheduled evidence blocker has been reviewed and resolved only for bounded partial automation evidence. The follow-up automation-policy pass is green as a read-only lane classifier, but it does not create mutation authority and does not produce an exact candidate that can be applied automatically.

Stop state:

- No exact lifecycle apply candidates are ready.
- Normal lifecycle queue remains exhausted.
- Existing trace candidates remain pending review; generated skeletons require exact human fields before promotion.
- Recurrent reinforcement should not be repeated without a fresh recurrent verifier corridor and exact authorization.
- Broad/default/background mutation remains blocked.

## Next safe action

Review existing pending trace candidates or generated candidate skeletons and fill exact human fields if one should be promoted. Without that review, stop at read-only evidence; do not auto-promote ordinary-turn candidates, and do not invent or persist duplicate lifecycle candidates.

Still blocked:

- broad G4/G5 apply
- ordinary conversation auto-approval
- unattended/default/background apply
- repeated apply without fresh verification
- default-ranking mutation
- collapse/delete
- telemetry reset apply
- unreviewed promotion
