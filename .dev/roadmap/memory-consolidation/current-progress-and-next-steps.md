# agent-memory memory-consolidation current progress and next steps

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 01:05 KST

## Checkpoint: ordinary-turn classifier evaluation gate

The remaining ordinary-turn lane now has a concrete read-only evaluation harness. `dogfood ordinary-turn-classifier-eval <db_path>` evaluates ordinary-turn memory-worthiness classification against optional `metadata.expected_memory_worthy` labels, reports aggregate prediction/evaluation metrics, and keeps ordinary conversation auto-approval blocked.

Source hardening added in this checkpoint:

- Added the `ordinary-turn-memory-worthiness-heuristic-v1` aggregate classifier/eval payload.
- Added parser and dispatcher support for `dogfood ordinary-turn-classifier-eval`.
- Added RED/GREEN CLI coverage proving labeled ordinary turns are scored without mutation or raw-content leakage.
- Preserved all forbidden authority flags: no apply execution, no broad/background apply, no default-ranking mutation, no collapse/delete, no telemetry reset, no unreviewed promotion, and no ordinary conversation auto-approval.

Live evidence artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-classifier-eval-20260516T160146Z/ordinary-turn-classifier-eval.json`.
  - Correctly red because no live ordinary-turn labels exist yet.
  - `ordinary_turn=995`, `labeled_ordinary_turn=0`, `unlabeled_ordinary_turn=995`.
  - `blocked_secret_like=0`, `mutated=false`, aggregate-only privacy.
  - Blocked reasons: `labeled_ordinary_turn_count_below_minimum`, `precision_below_minimum`.

Verification run from source checkout:

- New focused test: passed after RED invalid-subcommand failure.
- Focused ordinary-turn coverage: `2 passed, 174 deselected`.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%+.
- Literal fully autonomous human-brain-like memory is approximately 98.7-99% for the scoped local lifecycle. The system now has the evaluation substrate for ordinary-turn inference, but the live gate proves that labels/evidence are still missing.

Next after this slice:

1. Commit/push and watch CI.
2. Add a read-only ordinary-turn label/evidence packet so humans can label candidate ordinary turns safely.
3. Rerun classifier eval over repeated labeled windows and only then design a separate inferred-approval readiness/apply corridor.
4. Keep broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and ordinary-turn inferred apply blocked behind separate gates.

## Checkpoint: remember-preferences bounded-batch post-apply verifier

The G2 remember-preferences lane now has the missing post-batch stop gate. After a future operator-approved bounded batch, `consolidation auto-approve remember-preferences-batch-post-apply-verification` can validate the green operator packet, the actual batch apply artifact, and the post-apply dry-run artifact before any next batch is allowed.

Source hardening added in this checkpoint:

- Added the read-only batch post-apply verification command for `remember-preferences-v1`.
- Added regression tests for both green verification and blocked bad-batch verification.
- Preserved the important boundary: this verifier validates a separately approved batch; it does not execute apply and does not grant unattended authority.
- Output is aggregate/ref-only: artifact summaries, counts, memory refs, source/relation ids, and topic keys only. No raw preference text, raw trace summaries, raw reason text, raw candidate JSON, trace id inventory, backup contents, or raw source content.

Live evidence artifacts:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-batch-apply-verifier-20260516T154738Z-agent-memory-scope/pre-batch-dry-run.json`.
  - `eligible_count=0`, `blocked_count=0`, `skipped_count=5`, `mutated=false`.
- `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-batch-apply-verifier-20260516T154738Z-agent-memory-scope/graduation-readiness.json`.
  - Correctly red: `current_dry_run_has_no_eligible_candidates`.
  - This is expected because the explicit preference queue was already drained.
- `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-batch-apply-verifier-20260516T154702Z/batch-post-apply-verification.json`.
  - Correctly red for the no-op exploratory run because `approved_count=0` and no real batch mutation was available to verify.

Verification run from source checkout:

- New focused tests: `2 passed, 173 deselected` after RED parser failures.
- Remember-preferences focused coverage: `11 passed, 164 deselected`.
- Full suite: `357 passed, 1 xfailed`.
- Release metadata and release-readiness smoke passed on `0.1.162`.
- `npm pack --dry-run` passed.
- `git diff --check` passed.

Current interpretation:

- Safety-gated operational north-star is approximately 99%+.
- Literal fully autonomous human-brain-like memory is approximately 98.5% for the currently scoped local memory lifecycle. The explicit-memory lane now has end-to-end reviewed automation up through batch-stop verification; the remaining gap is the higher-risk inferred/unattended layer.

Next after this slice:

1. Commit/push and watch CI.
2. Build a read-only ordinary-turn classifier/evaluation harness to prove high precision for inferred memory-worthy turns.
3. Do not enable ordinary-turn inferred approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, or unreviewed promotion until separate gates prove safety.

## Checkpoint: preference topic-slot semantics + second bounded G2 auto-approval

The prior G2 smoke proved that explicit remember-intent preference approval could write one safe fact, but the generic `subject=user,predicate=prefers,scope=project` conflict slot was too conservative and blocked all remaining independent preferences. This checkpoint narrows only the G2 remember-preferences conflict preflight by deriving a conservative preference topic key from the proposed preference value. Same-topic contradictions still block; different topics can coexist and continue through the existing stop-after-one apply corridor.

Source hardening added in this checkpoint:

- Added preference topic-slot derivation for the `remember-preferences-v1` policy.
- Kept same-topic conflict braking for examples like `verbose handoffs` vs `concise handoffs`.
- Allowed independent topics to proceed without `claim_slot_conflict`.
- Preserved duplicate `auto_approved_as` skip and `--max-apply 1` bounded mutation.
- Added regression coverage for two independent explicit preference topics being approved across two separate apply runs.

Live evidence artifacts:

- Before apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-dry-run-before-apply.json`.
  - `eligible_count=4`, `blocked_count=0`, `skipped_count=1`, `mutated=false`.
- Bounded apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-apply.json`.
  - `approved_count=1`, `deferred_count=3`, `skipped_count=1`, `mutated=true`.
  - Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/pre-topic-slot-auto-approval-memory-backup.db`.
- Post-apply dry-run: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-post-dry-run.json`.
  - `eligible_count=3`, `blocked_count=0`, `skipped_count=2`, `mutated=false`.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%.
- Literal fully autonomous human-brain-like memory is approximately 96-97% after proving a second explicit low-risk preference can be approved through topic-aware conflict semantics.
- The remaining gap is mostly verification/scale: post-apply verifier for remember-preferences, repeated one-at-a-time applies, then a separately RED-tested bounded batch corridor. Ordinary conversation inference and broad unattended mutation are still intentionally blocked.

Next after this slice:

1. Commit/push and watch CI.
2. Apply the remaining explicit safe preferences one at a time only if the dry-run stays `blocked_count=0`, with a fresh backup each time.
3. Add a read-only remember-preferences post-apply verifier before increasing `--max-apply`.
4. Keep broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and ordinary-turn inferred approval blocked behind separate gates.

## Checkpoint: explicit remember-intent evidence + bounded G2 auto-approval smoke

The live source DB now has the missing explicit remember-intent evidence that previously kept ordinary-turn readiness red. Five safe `remember_intent` review traces were recorded through the source Hermes hook path, the ordinary-turn readiness gate passed at `--min-explicit-ready 5`, and one narrow preference was auto-approved through the default-off G2 policy after adding stop-after-one and duplicate guards.

Live evidence artifacts:

- G1 remember-intent report: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-intent-evidence-20260516T053416Z/remember-intent-dogfood.json`.
  - `remember_intent=5`, `review_ready_count=5`, inspected total `300`.
- Ordinary-turn readiness: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-intent-evidence-20260516T053416Z/ordinary-turn-auto-approval-readiness.json`.
  - `explicit_remember_intent=5`, `review_ready_remember_intent=5`, `ordinary_turn=995`, quality gate passed with decision `ordinary_turn_auto_approval_readiness_measured_keep_blocked`.
- G2 dry-run before apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-intent-evidence-20260516T053416Z/remember-preferences-auto-approve-dry-run.json`.
  - `eligible_count=5`, `mutated=false`.
- G2 bounded apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/remember-preferences-auto-approve-apply.json`.
  - `approved_count=1`, `deferred_count=4`, `max_apply=1`, `mutated=true`.
  - Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/pre-auto-approval-memory-backup.db`.
- Duplicate-guard post dry-run: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/remember-preferences-auto-approve-post-dry-run-after-duplicate-guard.json`.
  - `eligible_count=0`, `skipped_count=1`, `blocked_count=4`.

Source hardening added in this checkpoint:

- `consolidation auto-approve remember-preferences` now accepts `--max-apply`, defaulting to `1`.
- Additional eligible traces are reported as `deferred` instead of being approved in the same run.
- Already approved traces are detected through `auto_approved_as` relations and reported as `skipped` so repeat apply runs cannot duplicate facts, sources, or relations.
- Tests cover stop-after-one behavior and duplicate fail-closed behavior.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%.
- Literal fully autonomous human-brain-like memory is approximately 95-96%: explicit remember-intent evidence, readiness, and a first bounded low-risk auto-approval write now work end-to-end, but generic ordinary-turn inference and broad/background mutation remain intentionally blocked.
- The remaining meaningful gap is not plumbing; it is safe semantics for multiple independent preferences/procedures and unattended operation without over-broad claim-slot conflicts or duplicate writes.

Next after this slice:

1. Commit/push and watch CI.
2. Add a read-only multi-preference semantics/design gate or narrower claim-slot model so independent preferences can coexist safely.
3. Only after that, consider a second exact-bounded G2 apply.
4. Keep broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and ordinary-turn inferred approval blocked behind separate gates.

## Checkpoint: repeated recurrent reinforcement applies + ordinary-turn readiness gate

After the first recurrent reinforcement proof, the live DB was advanced through two more exact-approved recurrent reinforcement applies, each one-at-a-time and each followed by rollback replay, recurrent-policy application audit, and recurrent post-apply verification. A new read-only ordinary-turn auto-approval readiness gate now measures the remaining gap to unattended brain-like consolidation without enabling ordinary-turn auto-approval.

Live recurrent results:

- Second recurrent apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-recurrent-reinforcement-apply-20260516T044243Z/lifecycle-recurrent-reinforcement-apply.json`.
  - `eligible_target_count=3`, `selected_target_count=1`, `applied_count=1`.
  - Backup SHA-256: `af5d903f5040036fc1a2f9e75995a9ff59b65494eaa91c8b609626e60114e588`.
  - Rollback replay: green, `checked_application_count=9`, `failed_replay_count=0`.
  - Recurrent-policy application audit: green, `application_count=2`.
  - Recurrent post-apply verifier: green, `recurrent_reinforcement_post_apply_verification_green_stop`.
- Third recurrent apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-recurrent-reinforcement-apply-20260516T044336Z/lifecycle-recurrent-reinforcement-apply.json`.
  - `eligible_target_count=2`, `selected_target_count=1`, `applied_count=1`.
  - Backup SHA-256: `4358b9c876ead3edfce12baecf9ec39f4aa6e231fd831478695025ad6c60f963`.
  - Rollback replay: green, `checked_application_count=10`, `failed_replay_count=0`.
  - Recurrent-policy application audit: green, `application_count=3`.
  - Recurrent post-apply verifier: green, `recurrent_reinforcement_post_apply_verification_green_stop`.

New source gate:

- Added `dogfood ordinary-turn-auto-approval-readiness <db_path>`.
- The command is read-only/no-mutation/default-unchanged and reports aggregate counts only: ordinary turns, explicit remember-intent traces, review-ready remember-intent traces, ordinary preference-like turns, secret-like ordinary turns, and a bounded readiness score.
- It always keeps `ordinary_conversation_auto_approval=false` and includes forbidden-authority flags for broad/background apply, default ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion.
- Live artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-auto-approval-readiness-20260516T044849Z/ordinary-turn-auto-approval-readiness.json`.
- Live result: `ordinary_turn=1000`, `explicit_remember_intent=0`, `review_ready_remember_intent=0`, `secret_like_ordinary_turns=0`, score `75`, quality gate red with `explicit_remember_intent_ready_count_below_minimum`.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%.
- Literal fully autonomous human-brain-like memory is approximately 93-94%: recurrent reinforcement can now repeat safely with verifier stops, and the next missing substrate is explicit remember-intent evidence for ordinary-turn automation. Ordinary conversation auto-approval remains intentionally blocked.

Next after this slice:

1. Commit/push and watch CI if GitHub rate limits allow.
2. Add an explicit remember-intent evidence path or classifier that can turn user-approved memory requests into review-ready `remember_intent` traces, report-first and read-only.
3. Rerun ordinary-turn readiness; do not add apply until explicit-ready evidence exists and stays secret-free.
4. Keep broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and ordinary-turn apply blocked behind separate RED-tested gates.

## Checkpoint: exact-approved recurrent reinforcement apply

The source checkout now has a narrow recurrent-reinforcement apply corridor for the case exposed by source-novelty scoring: fresh evidence exists, but all generated lifecycle candidates point at already-applied targets. Instead of bypassing target-aware persistence or requeueing duplicate target refs, `dogfood lifecycle-recurrent-reinforcement-apply` uses a separate exact policy and fresh-window selector.

What changed:

- Added `dogfood lifecycle-recurrent-reinforcement-apply <db_path>`.
- Policy: `g5-lifecycle-recurrent-reinforcement-apply-v1`.
- Required phrase: `apply-approved-g5-lifecycle-recurrent-reinforcement-v1`.
- Required metadata: `--actor`, private `--reason`, backup path/output when used live.
- Guardrails: `--max-apply` is capped at 2; target selection requires at least `--min-observations` fresh retrieval observations after the target's latest base/recurrent lifecycle application.
- Mutation: increment the selected target memory's `reinforcement_count` only and record a lifecycle application row with backup/checksum/rollback hint.
- Still no status mutation, retrieval default mutation, candidate review requeue, ordinary conversation auto-approval, broad/background apply, collapse/delete, telemetry reset, or unreviewed promotion.

Live artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-recurrent-reinforcement-apply-20260516T041353Z/lifecycle-recurrent-reinforcement-apply.json`.

Live result:

- `eligible_target_count=3`.
- `selected_target_count=1`.
- `applied_count=1`.
- Backup SHA-256: `aafb6a0144ed792428bf34bc618f248c21de3c41711e2fd5bda44c0f766e7187`.
- Rollback confidence: green.
- Rollback replay: green, `checked_application_count=8`, `failed_replay_count=0`.
- Recurrent-policy application audit: green, `application_count=1`.
- Recurrent post-apply verifier: green, `recurrent_reinforcement_post_apply_verification_green_stop`.

Current interpretation:

- Safety-gated operational north-star remains approximately 99% but is now closer to the last mutation loop: recurrence evidence can be converted into a bounded exact-approved reinforcement update without duplicate target requeueing.
- Literal fully autonomous human-brain-like memory is approximately 92-93%. The system now has a first explicit recurrent reinforcement write path plus its post-apply verifier, but it still depends on exact operator approval and lacks ordinary-turn auto-approval.

Next after this slice:

1. Commit/push and watch CI.
2. Repeat at most one or two additional exact-approved recurrent applies if fresh windows remain, but run the recurrent post-apply verifier after each apply.
3. Add ordinary-turn auto-approval readiness scoring as the next read-only gate toward unattended consolidation.
4. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked behind separate gates.

## Checkpoint: lifecycle refresh source-novelty scoring

The candidate refresh preview now contains a source-level novelty section. This closes the immediate ambiguity after fresh-evidence went green: the live DB has fresh post-apply retrieval activity, but the generated reinforcement candidates still point at the same four already-applied targets. The preview can now say that explicitly with aggregate counts instead of forcing operators to infer it from candidate ids or target refs.

Live artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-source-novelty-preview-20260516T035332Z/lifecycle-candidate-refresh-preview-source-novelty.json`.

Live source-novelty result:

- `preview_candidate_count=4`.
- `target_already_applied_count=4`.
- `new_unapplied_target_candidate_count=0`.
- `fresh_observation_count_for_preview_targets=42`.
- `fresh_observation_target_count=4`.
- `applied_target_with_fresh_window_count=4`.
- `source_level_novelty_decision=fresh_evidence_recycles_already_applied_targets`.

Safety facts:

- The command remains read-only/no-mutation/default-unchanged.
- It does not include candidate ids, target refs, raw observation values, raw query text, query previews, source text, raw candidate JSON, or backup contents.
- The quality gate remains red because there are no new unapplied target candidates. Fresh windows over already-applied targets are evidence for a future explicit recurrent-reinforcement policy, not permission to silently requeue or batch apply those same targets.
- The lifecycle bounded-batch operator packet also now reports nested artifact `mutated` flags as the actual nested report mutation values.

Current interpretation:

- Overall safety-gated north-star progress remains approximately 99%.
- Literal fully autonomous human-brain-like progress is approximately 89-90%. The system can now separate fresh evidence from target novelty, which is a necessary brain-like recurrence signal, but the write path still intentionally refuses same-target requeueing without a separate recurrent-reinforcement policy.

Next after this slice:

1. Commit/push and watch CI.
2. Implement an explicit recurrent-reinforcement review/apply policy for already-applied targets with fresh post-apply evidence windows, with its own exact approval phrase and post-apply verifier, or broaden candidate generation until genuinely new target refs appear.
3. Keep bounded batch live apply blocked until reviewed approved candidates exist and the operator packet is green.
4. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion behind separate gates.

## Checkpoint: target-aware lifecycle persistence + bounded-batch source gates

A read-only pre-apply operator packet now exists for the exact-approved lifecycle bounded-batch corridor. It bridges the gap between the source-level bounded-batch apply command and the bounded-batch post-apply verifier by producing one machine-readable packet with graduation status, apply readiness, candidate inventory, command preview, and verification template.




A new read-only fresh-evidence preview now gates refresh attempts after lifecycle applies. It checks whether enough aggregate retrieval observations have accumulated after the latest application for a policy, without exposing raw query text, query previews, candidate ids, target refs, or backup details. Live reinforcement evidence is green with 53 post-apply observations.

Fresh-evidence artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-fresh-evidence-preview-20260516T033110Z/lifecycle-fresh-evidence-preview-reinforcement.json`.

Target-aware persistence is now enforced in the mutating review-queue insertion command itself. `lifecycle-candidate-persist` skips already-applied target refs before inserting review rows, reports the skip counts, and returns a red quality gate when no new unapplied lifecycle candidates were persisted. Live reinforcement smoke skipped all four already-applied targets with no mutation.

Target-aware persistence artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-target-aware-lifecycle-persist-20260516T030945Z/lifecycle-candidate-persist-target-aware-reinforcement.json`.

A second read-only refresh preview source gate now exists for candidate generation hygiene. It reports preview candidates, existing review rows by status, target refs already applied, and the count of new candidates whose targets have not already been applied. Live reinforcement refresh is correctly blocked because all four current preview targets have already been applied (`new_unapplied_target_candidate_count=0`).

Refresh artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-refresh-preview-20260516T025334Z/lifecycle-candidate-refresh-preview-reinforcement.json`.

Live artifact:

- `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-batch-operator-packet-20260516T022916Z/lifecycle-bounded-batch-operator-packet.json`.

Safety facts:

- The source command is `dogfood lifecycle-bounded-batch-operator-packet`.
- It is read-only/no-mutation and keeps `default_retrieval_unchanged=true`.
- It does not approve candidates, apply candidates, emit raw candidate JSON, emit raw source/query/trace content, emit raw reason text, or emit backup contents.
- It requires the normal lifecycle apply policy and exposes the exact bounded batch approval phrase `apply-approved-g5-lifecycle-bounded-batch-v1` only as an operator checklist/command preview.
- Live packet against the source DB is correctly blocked: graduation proof is green, but there are no eligible approved lifecycle candidates (`approved_eligible_count=0`).

Current interpretation:

- Overall safety-gated north-star progress is approximately 99%.
- Literal fully autonomous human-brain-like progress is approximately 88-89%. The batch corridor now has pre-apply and post-apply automation scaffolding, but cannot run live until fresh reviewed candidates exist; ordinary conversation auto-approval also remains intentionally blocked.

Next after this slice:

1. Commit/push and watch CI.
2. Run refresh/persist from the fresh-evidence gate, then add source-level novelty scoring if candidate generation still recycles applied target refs.
3. Then use the operator packet to prove when a bounded live batch is truly ready.
4. Still forbidden without separate gates: ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Checkpoint: fourth live exact-approved reinforcement lifecycle apply and batch graduation readiness

The fourth and final initial live G5 lifecycle reinforcement apply has completed through the same explicit reviewed-candidate corridor. The live one-at-a-time loop is now proven across four targets (`fact:4`, `episode:1`, `procedure:1`, and `fact:1`) with backup, rollback replay, audit, live evidence bundle, and post-apply verification green. A new read-only source gate, `dogfood lifecycle-batch-graduation-readiness`, summarizes those prior proofs and says the next step is designing a separate exact-approval bounded-batch corridor; it does not support or execute batch apply.

Live artifacts:

- Apply directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/`.
- Backup path: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `774765d9b1fec9df76f7582232c14967e92b8e50afbfd5b550b700ec79e56690`.
- New batch-graduation report: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/lifecycle-batch-graduation-readiness.json`.

Safety facts:

- Candidate `g5-reinforcement-84541df977996b35164b682a` targeting `fact:1` was approved with `approve-g5-lifecycle-candidate-v1`.
- The candidate was applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=4`, `pending=0`, `approved=0`.
- Rollback replay passed with `checked_application_count=7`, `passed_replay_count=7`, and `failed_replay_count=0`.
- The post-apply live evidence bundle passed for the bounded artifact set with fixture task count `4`, baseline regressions `0`, rollback checked applications `7`, and audit application count `4`.
- `lifecycle-post-apply-verification` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- `lifecycle-batch-graduation-readiness` passed for the reinforcement policy with `prior_one_at_a_time_apply_count=4`, but still reports `bounded_batch_apply_supported=false` and `requires_separate_exact_approval_corridor=true`.
- `lifecycle-bounded-batch-apply` now exists as that separate exact-approval source corridor with `--max-apply <= 2`; source tests cover two approved candidates after graduation proof. The live no-op smoke returned `no_eligible_approved_lifecycle_candidates` without mutation.
- `lifecycle-bounded-batch-post-apply-verification` now exists as a read-only source stop gate for bounded-batch artifacts: it validates applied count, backup file/SHA, rollback replay, application audit, default retrieval unchanged, privacy, and forbidden-authority flags before any further apply.

Current interpretation:

- Overall safety-gated north-star progress is approximately 97-98%.
- Literal fully autonomous human-brain-like progress is approximately 82-84%. The system has repeated real reviewed lifecycle reinforcement mutation four times on the live source DB, has a read-only batch-graduation classifier, a bounded batch source corridor, and a bounded-batch post-apply verifier, but it still relies on exact approvals and lacks fresh approved candidates for a live batch proof.
- The next safe engineering slice is either fresh candidate generation/review for the next lifecycle batch or a read-only batch operator packet; not broad/background apply.

Next after this slice:

1. Commit/push this bounded-batch post-apply verifier checkpoint and watch CI.
2. Generate/review new lifecycle candidates from fresh dogfood evidence, or add a read-only lifecycle batch operator packet that bundles graduation readiness, candidate inventory, exact apply command preview, and post-apply verifier command preview.
3. Do not live-batch-apply anything until there are reviewed approved candidates and exact operator approval for the batch.
4. Still forbidden until their own gates exist: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, and unreviewed promotion.

## Checkpoint: third live exact-approved reinforcement lifecycle apply

A third live G5 lifecycle reinforcement apply completed through the same explicit reviewed-candidate corridor. The live one-at-a-time loop was proven across three targets (`fact:4`, `episode:1`, and `procedure:1`) with backup, rollback replay, audit, and post-apply verification green.

Live artifacts:

- Apply directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/`.
- Backup path: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `5a18d345734798790ffa5bdd678901975792534a906d4e8df343dd75f174201c`.

Safety facts:

- Candidate `g5-reinforcement-da820f3c712f508c084d3137` targeting `procedure:1` was approved with `approve-g5-lifecycle-candidate-v1`.
- The candidate was applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=3`, `pending=1`, `approved=0`.
- Rollback replay passed with `checked_application_count=6`, `passed_replay_count=6`, and `failed_replay_count=0`.
- The post-apply live evidence bundle passed for the bounded artifact set with fixture task count `4`, baseline regressions `0`, rollback checked applications `6`, and audit application count `3`.
- `lifecycle-post-apply-verification` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.

Current interpretation at that checkpoint:

- Overall safety-gated north-star progress was approximately 96-97%.
- Literal fully autonomous human-brain-like progress was approximately 76-78%.

## Checkpoint: second live exact-approved reinforcement lifecycle apply

A second live G5 lifecycle reinforcement apply has completed through the same explicit reviewed-candidate corridor. The repeated one-at-a-time loop is now proven on the real source DB, while broad autonomy remains intentionally blocked.

Live artifacts:

- Apply directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/`.
- Backup path: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `c1f7dab326276a91b4b9b89818a96280dd050525987b3bf26ce2733b3c121387`.

Live result:

- Candidate `g5-reinforcement-3c9f30f85f8bdb80c9f3474f` targeting `episode:1` was approved with `approve-g5-lifecycle-candidate-v1`.
- The candidate was applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=2`, `pending=2`, `approved=0`.
- Rollback replay passed.
- `lifecycle-post-apply-verification` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- A broader post-apply `live-evidence-bundle` still stayed red on `live_fixture_reliability_gate_not_green`; this is a live fixture/evidence-quality blocker for broader ranking/automation, not a rollback/apply failure.

Current interpretation:

- Overall safety-gated north-star progress is approximately 95-96%.
- Literal fully autonomous human-brain-like progress is approximately 74-76%. The system has now repeated real reviewed lifecycle reinforcement mutation on the live source DB, but it still relies on exact approvals and stop-after-one verification.
- The next proof is one more one-candidate apply after this checkpoint is committed and CI is green. Do not jump directly to ordinary auto-approval or broad/background apply.

Next after this slice:

1. Commit/push this second live apply checkpoint and watch CI.
2. Then approve/apply at most one additional pending reinforcement candidate through the same exact phrase corridor.
3. Immediately rerun `lifecycle-post-apply-verification` and stop again.
4. Still forbidden until their own gates exist: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without fresh approval.

## Checkpoint: first live exact-approved reinforcement lifecycle apply

The first live G5 lifecycle reinforcement apply has completed through the explicit reviewed-candidate corridor. This is a real memory DB mutation, but it remained bounded to one candidate, with backup, rollback, and post-apply audit evidence.

Live artifacts:

- Apply directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/`.
- Backup path: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `5c44d39611e613b04bd0bb984b0bdd11fd8acd26b5bee6b3fb2f8b3ab26bec0d`.

Live result:

- Candidate `g5-reinforcement-255f68c152b76d844c6720cc` targeting `fact:4` was approved with `approve-g5-lifecycle-candidate-v1`.
- Before apply, readiness was green for exactly one reinforcement candidate: `eligible_approved_count=1`.
- The candidate was applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=1`, `pending=3`, `approved=0`.
- Rollback confidence and rollback replay validation passed after apply.
- Application audit passed after providing rollback replay plus retrieval-ranking evidence.
- Added and ran `dogfood lifecycle-post-apply-verification`; it passed on the live artifact directory with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- A broader post-apply `live-evidence-bundle` stayed red on `live_fixture_reliability_gate_not_green`; this is a live fixture/evidence-quality blocker for broader ranking/automation, not a rollback/apply failure.

Current interpretation:

- Overall safety-gated north-star progress is approximately 94-95%.
- Literal fully autonomous human-brain-like progress is approximately 72-74%. The system has now performed its first real reviewed lifecycle reinforcement apply on the live source DB, but it is still not autonomous: the approval/apply corridor used exact phrases and stopped after one candidate.
- The next proof should be a second one-candidate reinforcement apply after this source/test/docs checkpoint is committed and CI is green. Do not jump directly to ordinary auto-approval or broad/background apply.

Next after this slice:

1. Commit/push the `dogfood lifecycle-post-apply-verification` source/test/docs checkpoint and watch CI.
2. Then approve/apply at most one additional pending reinforcement candidate through the same exact phrase corridor.
3. Immediately rerun `lifecycle-post-apply-verification` and stop again.
4. Still forbidden until their own gates exist: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without fresh approval.

## Checkpoint: live lifecycle readiness smoke and pending reinforcement review queue

The new readiness gate has been exercised against the real source memory DB. It correctly refused to greenlight apply when no candidates had been approved, then the safest available next step persisted reinforcement candidates for explicit review without changing retrieval defaults or applying lifecycle mutation.

Live artifacts:

- Initial readiness: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-apply-readiness-20260515T092750Z/lifecycle-apply-readiness.json`.
- Lifecycle previews: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-preview-20260515T092837Z/`.
- Candidate persistence/list/after-readiness: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-persist-20260515T092910Z/`.

Live result:

- Initial readiness stayed red with `decision=no_exact_lifecycle_apply_candidates_ready` because all lifecycle candidate counts were zero.
- Read-only reinforcement preview found four reviewable candidates and passed its quality gate; decay and supersession found no candidates.
- `lifecycle-candidate-persist --candidate-kind reinforcement` persisted four pending reinforcement candidates for review only. This was a narrow candidate-registry mutation, not memory apply: raw content was not emitted, the reason was stored as SHA-256, and `default_retrieval_unchanged=true`.
- After-persist readiness reports reinforcement `pending=4`, `approved=0`, `eligible_approved_count=0`, and still does not allow apply.

Current interpretation:

- Overall safety-gated north-star progress remains approximately 93-94%.
- Literal fully autonomous human-brain-like progress remains approximately 70-72%: the live DB now has pending lifecycle review objects, but approval/apply is still exact-gated rather than autonomous.
- The next proof is one explicit human-reviewed reinforcement approval followed by at most one exact guarded reinforcement apply with backup/audit/rollback checks. Do not batch-approve or broad-apply from this checkpoint.

Next after this slice:

1. Review one pending reinforcement candidate from `lifecycle-candidate-list-reinforcement.json`.
2. If approved by the operator, use `dogfood lifecycle-candidate-update` with approval phrase `approve-g5-lifecycle-candidate-v1`.
3. Then apply only that candidate with policy `g5-lifecycle-reinforcement-apply-v1` and apply phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
4. Rerun `lifecycle-apply-readiness`, rollback replay/confidence, and record the post-apply artifact before considering another candidate.
5. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without fresh approval.

## Checkpoint: lifecycle apply readiness/audit gate

The roadmap lanes 3-7 are now cleaned up behind an explicit read-only gate. Reinforcement, decay, and supersession share reviewed lifecycle candidate corridors, while ordinary conversation auto-approval and automatic default-ranking rollout remain blocked by policy.

Implemented:

- `dogfood lifecycle-apply-readiness <db_path> --output <path>`.
- Aggregates lifecycle candidate status counts for reinforcement, decay, and supersession.
- Reports exact policy readiness for each reviewed apply lane, including eligible approved candidates, already-applied candidates, blocked candidates, policy, phrase, and decision.
- Emits a quality gate indicating whether exact reviewed lifecycle apply candidates are ready.
- Confirms forbidden authority: no apply execution, broad/background apply, ordinary auto-approval, default ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion.

Verification:

- RED observed: command did not exist.
- Focused readiness test: `1 passed`.
- Related lifecycle/policy subset: `10 passed, 146 deselected`.
- Full source gate: `338 passed, 1 xfailed`.

Current interpretation:

- Overall safety-gated north-star progress is approximately 93-94%.
- Literal fully autonomous human-brain-like progress is approximately 70-72%. The project now has consistent reviewed lifecycle gates, but true autonomous ordinary-turn learning, destructive forgetting, and autonomous default policy rollout remain intentionally unimplemented.
- The next proof should be real-source readiness smoke plus one single-family exact apply only if the gate finds eligible reviewed candidates.

Next after this slice:

1. Commit/push and watch CI.
2. Run live source `lifecycle-apply-readiness` and archive the report.
3. If green, perform only one exact guarded reviewed apply family at a time.
4. Still forbidden without later guarded slices: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without new approval.

## Checkpoint: narrow reviewed reinforcement lifecycle apply

The first low-risk narrow auto-apply unification slice is implemented in source. Reinforcement can now use the G5 lifecycle candidate apply corridor, matching the reviewed-candidate pattern already used for decay deprecation and supersession.

Implemented:

- `dogfood lifecycle-candidate-apply` now accepts policy `g5-lifecycle-reinforcement-apply-v1`.
- It requires exact phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- It applies only approved lifecycle candidates with `candidate_kind=reinforcement` and `proposal_type=reinforcement_review`.
- It increments the target memory `reinforcement_count`, records a `g5_trace_candidate_applications` audit row, stores backup/rollback metadata, and leaves memory status/default retrieval unchanged.

Verification:

- RED observed: the reinforcement lifecycle apply policy was rejected before implementation.
- Focused reinforcement lifecycle apply test: `1 passed`.
- Related lifecycle/policy subset: `6 passed, 149 deselected`.
- Full source gate: `337 passed, 1 xfailed`.

Current interpretation:

- Overall safety-gated north-star progress is approximately 92-93%.
- Literal fully autonomous human-brain-like progress is approximately 68-70%. Reviewed candidate apply is becoming consistent across the safer lifecycle lanes, but ordinary turns are not auto-approved and broad mutation/default rollout remains blocked.
- The next proof should be an aggregate lifecycle apply readiness/audit report before opening any additional mutation lane.

Next after this slice:

1. Commit/push and watch CI.
2. Next code slice: read-only lifecycle apply readiness/audit report across reinforcement, decay, and supersession, including already-applied detection and missing-proof blockers.
3. Still forbidden without later guarded slices: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without new approval.

## Checkpoint: read-only automation policy readiness classifier

The policy-classification slice is implemented in source. It closes the gap after repeated-window live evidence comparison: a saved green comparison can now be turned into a lane-by-lane automation readiness artifact before any mutation or default change.

Implemented:

- Added `dogfood automation-policy-readiness --comparison-report <path> --output <path>`.
- The command reads only the comparison report and summarizes comparison evidence by path, SHA-256, kind, read-only/mutation/default flags, quality decision, report/pass counts, fixture coverage, regression max, rollback/audit minima, and audit evidence pass count.
- Lane decisions now explicitly cover the requested 1-7 path: readiness complete; narrow reviewed apply eligible only for later exact approval; reinforcement candidate generation only; decay reviewed-deprecate only; supersession reviewed-corridor only; ordinary conversation auto-approval blocked; default ranking migration exact-review only.
- The command is explicitly read-only and no-apply: no durable memory mutation, default ranking mutation, broad G4 apply, collapse/delete, telemetry reset, unreviewed promotion, repeated apply, raw report embedding, or ordinary-conversation auto-approval.

Verification:

- RED observed: `automation-policy-readiness` was not a recognized dogfood action.
- Focused readiness test: `1 passed`.
- Evidence/policy subset: `9 passed, 145 deselected`.
- Full source gate: `336 passed, 1 xfailed`.
- Live read-only readiness smoke passed at `/Users/reddit/.agent-memory/reports/source-automation-policy-readiness-20260515T084816Z/automation-policy-readiness.json` from the existing green bundle comparison.

Current interpretation:

- Overall safety-gated north-star progress is approximately 91-92%.
- Literal fully autonomous human-brain-like progress is approximately 66-68% because the system can now classify the next automation lane, but actual autonomous mutation/default migration/ordinary-auto-approval remain deliberately split into exact guarded policy slices.
- The next proof is the first narrow reviewed-candidate apply automation lane, not broader background apply.

Next after this slice:

1. Commit/push and watch CI.
2. Next code slice: exact narrow reviewed-candidate apply automation lane with backup/audit/rollback, constrained to already-reviewed candidates and no repeated apply without new approval.
3. Still forbidden without later guarded slices: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking migration, collapse/delete, unreviewed promotion, and repeated apply without new approval.

## Checkpoint: read-only live evidence bundle comparison

The repeated-window accumulation slice is implemented in source. It closes the immediate gap after `dogfood live-evidence-bundle`: saved live bundle reports can now be compared as a ref-safe trend artifact before any broader automation-policy decision.

Implemented:

- Added `dogfood live-evidence-bundle-compare --report <path> [--report <path> ...] --output <path>`.
- The comparison summarizes each input report with the report path, top-level SHA-256, generated timestamp, quality-gate decision, ref-safe rollup counts, and nested artifact hashes.
- The aggregate block reports quality-gate pass counts, decision counts, fixture count min/max, retrieval/reliability pass counts, ranking baseline regression total/max, rollback/audit count ranges, audit evidence pass count, and blocker trends.
- The command is explicitly read-only and no-apply: no durable memory mutation, default ranking mutation, broad G4 apply, collapse/delete, telemetry reset, unreviewed promotion, repeated apply, raw report embedding, or ordinary-conversation auto-approval.

Verification:

- RED observed: `live-evidence-bundle-compare` was not a recognized dogfood action.
- Focused compare test: `1 passed`.
- Evidence/audit subset: `6 passed, 147 deselected`.
- Full source gate: `335 passed, 1 xfailed`.
- Live read-only comparison smoke passed at `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-compare-20260515T074353Z/live-evidence-bundle-comparison.json` with report count `2`, quality gate green, fixture task count min/max `4/4`, zero ranking baseline regressions, rollback count min/max `3/3`, and audit count min/max `3/3`.

Current interpretation:

- Overall safety-gated north-star progress is approximately 90-91%.
- Literal fully autonomous human-brain-like progress is approximately 63-66% because trend evidence is now automated, but autonomous mutation/apply/default-ranking/ordinary-auto-approval remain intentionally blocked.
- The next proof is not more raw evidence plumbing; it is a read-only automation-policy readiness classifier that decides which narrow auto-decision lane can be safely implemented next.

Next after this slice:

1. Commit/push and watch CI.
2. Next code slice: read-only automation-policy readiness report over green live evidence bundle comparisons. It should classify eligible next lanes, preserve all false authority flags, and not execute apply.
3. Still forbidden without a later guarded implementation slice: ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default ranking migration, collapse/delete, repeated apply without new approval, and unreviewed promotion.

## Checkpoint: read-only live evidence bundle

The repeated-evidence bundling slice is now implemented in source. It closes the immediate operational gap where an operator had to manually chain live fixture generation, ranking experiment, rollback replay, and application audit before comparing evidence.

Implemented:

- Added `dogfood live-evidence-bundle <db_path> --output-dir <dir>`.
- The command produces and links these artifacts with paths and SHA-256 hashes:
  - live retrieval fixture JSON;
  - live fixture diagnostics report;
  - retrieval-ranking experiment report;
  - rollback replay validation report;
  - trace-candidate application audit report;
  - optional top-level bundle report.
- The top-level bundle reports aggregate rollups for fixture count/type coverage, fixture retrieval/reliability pass, ranking baseline regressions, rollback checked applications, audit applications, and audit required evidence gate.
- The command is explicitly read-only and no-apply: no durable memory mutation, default ranking mutation, broad G4 apply, collapse/delete, telemetry reset, unreviewed promotion, repeated apply, or ordinary-conversation auto-approval.

Verification:

- Focused bundle test: `1 passed`.
- Evidence/audit subset: `5 passed, 147 deselected`.
- Full source gate: `334 passed, 1 xfailed`.
- Live read-only source smoke passed at `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-20260515T072811Z/live-evidence-bundle.json` with quality gate green, fixture task count `4`, zero ranking baseline regressions, rollback checked application count `3`, audit application count `3`, and audit required evidence gate pass.

Current interpretation:

- Overall safety-gated north-star progress is approximately 89-90%.
- This reaches the edge of 90% because live evidence can now be collected as a single repeatable, hash-addressed, read-only bundle.
- Still not beyond 90% because the next proof is repeated-window stability and the mutation/automation lanes remain exact-approved or blocked.

Next after this slice:

1. Commit/push and watch CI.
2. Next code slice: add read-only repeated-run comparison/accumulation over saved live evidence bundle reports, including artifact hashes, pass counts, blocker trends, and no mutation.
3. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply without exact operator corridor, telemetry reset, default ranking migration, collapse/delete, repeated apply without new approval, and unreviewed promotion.

## Checkpoint: live retrieval-ranking fixture diagnostics hardening

The live fixture generator is now hardened with explicit skip/blocker and retrieval-eval diagnostics. This closes the immediate gap where live fixture generation could succeed with too little explanation about sparse DB coverage or generated-task retrieval failures.

Implemented:

- `dogfood live-retrieval-ranking-fixtures <db_path> --fixture-output <json>` now reports:
  - `generation_diagnostics` for approved counts, generated counts, skipped counts, and skip reasons by memory type;
  - `retrieval_diagnostics` for immediate read-only eval pass/failure, failed task count, baseline regression count, and ref/count-only failure diagnostics;
  - diagnostic-only `reliability_gate` with configurable `--min-reliable-tasks`.
- Added optional flags `--baseline-mode` and `--max-baseline-regressions` so generated live fixtures can be checked against lexical/source baselines before downstream audit use.
- Sparse/limited generation no longer looks silently successful: it reports `insufficient_approved_memory`, `generation_limit_reached`, and/or `no_generated_fixture_tasks` as appropriate.
- Failure diagnostics avoid raw source/query/content and include only task ids, preferred-scope presence, missing/avoid/retrieved counts, and reason labels.

Verification:

- Focused diagnostics tests: `3 passed`.
- Evidence/audit subset: `4 passed, 147 deselected`.
- Full source gate: `333 passed, 1 xfailed`.
- Live read-only source smoke passed at `/Users/reddit/.agent-memory/reports/source-live-ranking-fixture-diagnostics-20260515T065526Z/` with generated fixture count `4`, retrieval diagnostics pass, no baseline regressions, reliability gate pass at `--min-reliable-tasks 4`, and downstream ranking `ranking_change_allowed=true`.

Current interpretation:

- Overall safety-gated north-star progress is approximately 89%.
- This moves the system closer to 90% because the live evidence path now explains coverage and eval blockers instead of relying on manually inspecting tiny generated fixtures.
- Still below 90% because repeated end-to-end evidence bundles and larger-volume stability are not automated yet, and all mutation paths remain exact-approved or blocked.

Next after this slice:

1. Commit/push and watch CI.
2. Next code slice: add read-only repeated evidence bundling from live fixture diagnostics to ranking experiment to application audit, with artifact hashes and no mutation.
3. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply without exact operator corridor, telemetry reset, default ranking migration, collapse/delete, repeated apply without new approval, and unreviewed promotion.

## Checkpoint: live retrieval-ranking fixture generation

The next read-only live evidence slice is implemented in source. It generates retrieval-eval fixture tasks from approved memories already present in the target DB, so application-audit ranking evidence can be generated from real live refs instead of a hand-shaped compatible artifact.

Implemented:

- Added `dogfood live-retrieval-ranking-fixtures <db_path> --fixture-output <json>`.
- Generates fact/procedure/episode tasks with live numeric expected refs, preferred scopes, ref-safe rationales, and no raw source/transcript/review payload data.
- Generated fixture can be passed directly to `dogfood retrieval-ranking-experiment --fixtures <json>`.
- `trace-candidate-application-audit` can now consume the generated ranking report plus rollback replay evidence and satisfy the required evidence gate.

Verification so far:

- Focused RED observed: command was not a recognized dogfood action.
- Focused generator test passed: `1 passed`.
- Evidence/audit subset passed: `2 passed, 147 deselected`.
- Live read-only source smoke passed at `/Users/reddit/.agent-memory/reports/source-live-ranking-fixtures-20260515T054056Z/` with generated fixture count `4`, ranking `baseline_regression_count=0`, and application audit `required_evidence_gate.pass=true`.

Current interpretation:

- Overall safety-gated north-star progress is approximately 88%.
- The system is closer to 90% because the application-audit evidence gate can now be backed by generated live DB ranking evidence.
- Still below 90% because generated live coverage is small on the current DB and needs skip/blocker diagnostics plus repeated green runs before any broader automation decision.

Next after this slice:

1. Run full source test gate, commit/push, and watch CI.
2. Next code slice: harden generated live retrieval fixtures with explicit skipped-task/blocker diagnostics and realistic-volume reporting.
3. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply without exact operator corridor, telemetry reset, default ranking migration, collapse/delete, repeated apply without new approval, and unreviewed promotion.

## Checkpoint: G5 trace candidate application audit

The next read-only post-apply comparison slice is implemented in source. It audits reviewed trace-candidate application records before any broader automation can be considered.

Implemented:

- Added `dogfood trace-candidate-application-audit <db>`.
- The report includes application refs, policy/action rollups, review status rollups, current memory status, backup checksum confidence, rollback hints, and a quality gate.
- The report is read-only and asserts `mutated=false`, `default_retrieval_unchanged=true`, and ordinary conversation auto-approval false.
- Quality gate fails on missing backup, backup checksum mismatch, or application records whose review state is not `promoted`.
- Privacy flags confirm no cluster JSON, reviewed payload, raw content, raw reason, or backup content is emitted.

Verification:

- Focused audit/apply tests passed: `2 passed`.
- Trace candidate regression subset passed: `8 passed, 140 deselected`.
- Full source gate passed: `330 passed, 1 xfailed`.
- Live read-only source smoke passed: `/Users/reddit/.agent-memory/reports/source-g5-trace-candidate-application-audit-smoke-20260515T041836Z.json` with `read_only=true`, `mutated=false`, application count `3`, and quality gate pass.

Current interpretation:

- Overall north-star progress is approximately 85-87%.
- The system is closer to 90% because reviewed promotion now has both a contradiction preflight and a post-apply audit surface.
- Still below 90% because rollback replay and retrieval-ranking evidence are not yet linked into this application audit, and broader/background apply remains intentionally blocked.

Next after this slice:

1. Finish full source test gate, docs, commit/push, and CI watch.
2. Next code slice: wire application audit into rollback replay validation and retrieval-ranking gate evidence as read-only required artifacts.
3. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply without exact operator corridor, telemetry reset, default ranking migration, collapse/delete, and unreviewed promotion.

## Checkpoint: G5 trace candidate apply conflict preflight

The next E1/D5 safety boundary is implemented in source. It keeps reviewed trace-candidate promotion exact-approved, but now blocks silent same-claim contradictions at apply time.

Implemented:

- `dogfood trace-candidate-apply` runs claim-slot conflict preflight for reviewed fact/preference promotions.
- A candidate whose reviewed payload conflicts with an existing fact in the same `subject_ref` + `predicate` + `scope` is skipped with `reason=claim_slot_conflict` by default.
- `--allow-conflict` is an explicit reviewer override and is reported in `conflict_preflight_policy`.
- The blocked path leaves facts, status transitions, and application audit rows unchanged.
- Procedure/episode promotion behavior is unchanged.

Verification:

- Focused conflict test passed: `uv run pytest tests/test_cli.py::test_dogfood_trace_candidate_apply_blocks_fact_claim_slot_conflicts_by_default -q` -> `1 passed`.
- Trace-candidate regression subset passed: `uv run pytest tests/test_cli.py -q -k 'trace_candidate_apply or trace_candidate_update or trace_candidate_generate or trace_candidate_review_flow'` -> `7 passed, 140 deselected`.
- Full source gate passed: `329 passed, 1 xfailed`.
- Live read-only source smoke passed: `/Users/reddit/.agent-memory/reports/source-g5-trace-candidate-conflict-preflight-smoke-20260515T040859Z.json` with `read_only=true`, `mutated=false`, and default retrieval unchanged.

Current interpretation:

- Overall north-star progress is approximately 83-85%.
- The system is closer to safe autonomous consolidation because reviewed promotion now has a contradiction brake, but 90% still requires post-apply impact comparison, stronger rollback/report replay, and more default-off background dry-run/apply gates.

Next after this slice:

1. Finish full source test gate and live read-only smoke.
2. Commit/push this source/test/docs checkpoint and watch CI.
3. Next code slice: read-only trace candidate application audit/comparison report that proves reviewed promotions did not unexpectedly alter default retrieval/ranking behavior.
4. Still forbidden: ordinary conversation auto-approval, broad/background apply, live G4 apply without exact operator corridor, telemetry reset, default ranking migration, collapse/delete, and unreviewed promotion.

## Checkpoint: G5 consolidation explainability source slice

The next read-only G5 brainlike consolidation runway slice is implemented in source. It does not mutate memory; it makes candidate evidence easier to inspect and reason about before any future human-reviewed promotion/apply corridor.

Implemented:

- `dogfood consolidation-explainability <db_path>` combines existing G5 read-only signals into one explainability report:
  - trace-cluster candidates;
  - reinforcement/refinement candidates;
  - decay/collapse candidates;
  - same-claim-slot supersession candidates;
  - human-review gate summary.
- The report includes `signal_counts`, `explainability_ladder`, `top_review_candidates`, `quality_gate`, `automation_policy`, `privacy`, and `suggested_next_steps`.
- It is explicitly ref-safe and report-only: no raw conversation content, trace summaries, sample values, object values, review-queue writes, long-term promotion, deprecation/delete, default-ranking change, or ordinary conversation auto-approval.
- Supersession enriched evidence was corrected for the current activation model by matching activation rows through `memory_ref`.

Verification:

- Focused new test passed: `test_dogfood_consolidation_explainability_reports_stage_reasons_without_mutation`.
- Focused G5 preview suite passed: consolidation explainability, trace cluster preview, reinforcement/refinement preview, decay/collapse preview, and supersession preview -> `5 passed`.
- Source-checkout live read-only smoke wrote `/Users/reddit/.agent-memory/reports/source-g5-consolidation-explainability-smoke.json`; quality gate passed with `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, trace cluster candidates `5`, reinforcement candidates `4`, decay/collapse candidates `0`, supersession candidates `0`.

Current interpretation:

- Overall north-star progress is approximately 80-82%.
- Compared with the previous 78-80% estimate, this adds a small but important G5 explainability layer: candidates are now easier to inspect across multiple consolidation signals, but still cannot promote/apply themselves.
- Remaining gap to “actual human-brain-like fully automated memory” is not raw signal detection anymore; it is safe autonomous judgement: reviewed promotion, redaction/provenance/conflict checks, rollback, opt-in ranking, background comparison, and narrowly scoped auto-approval.

Next after this slice:

1. Commit/push this G5 source/test/docs checkpoint and watch CI.
2. Do not cut a release solely for this checkpoint; keep accumulating until the G5 review/promotion corridor is stable enough to justify a milestone release.
3. Next code slice: explicit review-state path for consolidation candidates, likely D4/E1 boundary:
   - reject/snooze candidate;
   - manual promote a reviewed candidate into long-term memory;
   - require provenance, conflict/supersession checks, actor/reason, backup/audit output, rollback proof;
   - keep ordinary conversation auto-approval blocked.
4. Later slices before true automation: retrieval explanation/ranking opt-in, background dry-run report comparison, explicit remember-intent auto-candidate, and only then narrow opt-in auto-approval.

## Checkpoint: v0.1.162 milestone released and externally verified

Priority 1 from the recommended sequence is complete: the accumulated G4 bounded operator apply readiness corridor was released as `v0.1.162`, published to npm/PyPI, and verified from real installed artifacts outside the source checkout. This was a release/QA action only; it did not authorize or execute live bounded G4 apply.

Release artifacts:

- Release commit: `cda5696` (`chore: release v0.1.162 [skip release]`).
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.162`.
- npm latest: `@cafitac/agent-memory@0.1.162`.
- PyPI latest: `cafitac-agent-memory==0.1.162`.

Workflow evidence:

- Source `main` push `ci`: run `25896978955`, success.
- Source `main` push `auto-release`: run `25896978967`, success.
- Release-sync validation `ci`: run `25897050696`, success.
- Release metadata commit `ci`: run `25897160173`, success.
- Release-sync `auto-release`: run `25897160181`, success.
- Publish workflow: run `25897165575`, success; verify, PyPI publish, npm publish, and GitHub Release jobs passed.

Published-install QA:

- Local exact-version smoke artifact: `/tmp/agent-memory-v0162-published-smoke/published-install-smoke.json`.
- Result: `status=ok`, attempt `1`, no propagation retry needed after the initial early manual npm-wrapper resolver miss.
- Covered `npx`, `npm exec`, `uvx`, and `pipx run` against exact version `0.1.162`.
- Bootstrap/doctor/hook surfaces passed on isolated temp DB/config paths; no source checkout import was used by the published smoke.

Current interpretation:

- Overall north-star remains about 78-80% complete.
- The release strengthens the operational trust boundary but does not by itself increase automation authority.
- The next meaningful progress toward brain-like automation is either one exact-approved bounded G4 live apply, or, without live-apply approval, a read-only G5 consolidation-candidate/explainability slice.

Next after this release:

1. Do not republish `v0.1.162`; it is complete.
2. Released-runtime priority 2 packet preparation is complete: `/Users/reddit/.agent-memory/reports/v0.1.162-published-g4-operator-packet-20260515T024457Z/g4-operator-apply-packet.json` is green for manual review only, with `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, and runbook contract alignment true.
3. If the operator explicitly authorizes live apply later, execute only the bounded `g4-review-queue-apply` corridor with exact phrase/policy/actor/private reason/backup/audit/max-apply inputs, then stop at `g4-post-apply-verification`.
4. If those exact live-apply inputs are not present, do not infer authorization from this release or packet. Continue read-only/source work on the G5 brainlike consolidation runway.
5. Keep broad/background G4 apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: G4 milestone release readiness review

The accumulated `develop` G4 corridor after `v0.1.161` was reviewed for release readiness. This was a review-only checkpoint; no release, publish, or live memory mutation was executed.

Review artifact:

- `.dev/roadmap/memory-consolidation/g4-milestone-release-readiness-review.md`

Reviewed scope:

- Git range: `main..develop`.
- Commits: 10 commits from `539f929` through `e6eb7c1`.
- Theme: G4 bounded operator apply readiness corridor.
- Candidate next version if explicitly released later: `v0.1.162`.

Readiness result:

- Source-ready for a human-approved milestone release.
- Not auto-approved for publish.
- Not authorization for live bounded apply.

Evidence:

- Full source gate: `326 passed, 1 xfailed`.
- Release metadata synced at `0.1.161` before release bump.
- Release readiness smoke passed for Python and Node bootstrap/doctor in isolated HOME.
- npm dry-run package contents remain minimal and public-safe: `LICENSE`, `README.md`, `bin/agent-memory.js`, `package.json`.
- Focused release/package tests: `34 passed`.

Next after this review:

- Commit this release-readiness review checkpoint.
- If releasing, require explicit release approval and then run the project release process plus real downloaded install QA after publish.
- If not releasing, continue read-only source/docs hardening.
- Keep live bounded G4 apply, repeated apply, broad/background apply, default-ranking migration, live telemetry reset, collapse/delete, unreviewed promotion, and ordinary conversation auto-approval blocked unless their exact approval corridors are separately satisfied.

## Previous checkpoint: packet/runbook cross-check contract

Source follow-up after commit `d92b2e9` hardened the final pre-apply packet so the bounded operator apply runbook is represented directly in the generated JSON.

Implemented/evidence:

- `dogfood g4-operator-apply-packet` now emits `runbook_contract`.
- The contract records the required authorization inputs, pre-apply evidence checklist, post-apply stop checklist, command-preview flag checks, and `readiness_is_not_authorization=true`.
- The manual apply preview still requires exact policy/approval phrase, actor, private reason placeholder, backup path placeholder, bounded max apply, and audit output placeholder.
- The post-apply verifier template still requires apply report, post-apply operator bundle, rollback replay report, and verifier output.
- Source live smoke wrote `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-packet-runbook-crosscheck-20260514T145334Z/g4-operator-apply-packet.json` with `quality_gate.pass=true`, runbook contract alignment true, read-only/no-mutation/no-apply state, and no broad apply.

Verification:

- RED observed: focused packet test failed before source implementation because `runbook_contract` was missing.
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_packet_emits_machine_readable_checklist_without_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_packet_blocks_unsafe_or_stale_artifacts -q` -> `2 passed`.
- Full source gate: `PYTHONPATH=src .venv/bin/python -m compileall src && PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` -> `326 passed, 1 xfailed`.

Next after this slice:

- Commit this source/docs checkpoint.
- Do not release solely for this checkpoint.
- Generic continuation still must not execute live apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, or ordinary conversation auto-approval.
- Live apply remains blocked unless separately approved with exact operator phrase `apply-approved-g4-review-queue-items-v1`, policy `g4-review-queue-apply-v1`, actor, private reason, backup path, bounded max-apply, and audit output.

## Previous checkpoint: read-only operator apply packet/checklist command

Source commit `c7b6e0c` completed the safe B-direction follow-up after the runbook/checklist hardening slice. It makes the manual G4 bounded apply corridor inspectable as JSON without granting or executing apply authority.

Implemented/evidence:

- Added `dogfood g4-operator-apply-packet`.
- The command validates a saved green `dogfood_g4_operator_apply_bundle` artifact plus a saved green `dogfood_g4_readiness_gate_summary` artifact.
- It emits a machine-readable `operator_checklist`, an exact manual `g4-review-queue-apply` command preview, and a `g4-post-apply-verification` command template.
- It refuses unsafe/stale artifacts through blocked reasons such as `operator_apply_bundle_apply_executed`, `operator_apply_bundle_broad_apply_allowed`, `operator_apply_bundle_privacy_flags_not_ref_safe`, and `readiness_gate_summary_not_green`.
- It remains read-only/report-only: `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, and ordinary conversation auto-approval false.
- Source live smoke wrote `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-operator-apply-packet-20260514T141141Z/g4-operator-apply-packet.json` with `quality_gate.pass=true` and decision `operator_apply_packet_ready_for_manual_review_only`.

Verification:

- RED observed: focused packet tests initially failed because `g4-operator-apply-packet` was not a valid dogfood action.
- `PYTHONPATH=src .venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_packet_emits_machine_readable_checklist_without_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_packet_blocks_unsafe_or_stale_artifacts -q` -> `2 passed`.
- `PYTHONPATH=src .venv/bin/python -m compileall src && PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` -> `326 passed, 1 xfailed`.
- Source live smoke against saved pre-apply artifacts passed and did not mutate live memory.

Next after this slice:

- Commit the docs/status checkpoint.
- Do not release solely for this checkpoint.
- Generic continuation still must not execute live apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, or ordinary conversation auto-approval.
- Live apply remains blocked unless separately approved with exact operator phrase `apply-approved-g4-review-queue-items-v1`, policy `g4-review-queue-apply-v1`, actor, private reason, backup path, bounded max-apply, and audit output.

## Docs checkpoint: operator runbook catches up to post-apply verifier

After source commit `e0bc642` added `dogfood g4-post-apply-verification`, the G4 bounded operator apply runbook was hardened so future sessions do not treat readiness artifacts as authorization.

Implemented/evidence:

- Updated `.dev/roadmap/memory-consolidation/g4-bounded-operator-apply-runbook.md`.
- Added one-screen operator checklist for authorization, pre-apply evidence, post-apply stop gate, and repeated-apply prevention.
- Pre-apply verification now checks both green evidence artifacts: operator bundle and readiness summary.
- Post-apply verification now uses `dogfood g4-post-apply-verification` and requires the green stop decision before any further mutation is discussed.
- The no-live-apply placeholder verifier smoke remains intentionally red and documented as proof that the verifier is not an apply trigger.
- This checkpoint is docs/checklist only; it did not run live apply or mutate live memory.

Next after this slice:

- Commit the docs/checklist checkpoint.
- Do not release solely for this checkpoint.
- If still staying in safe B-direction without explicit apply approval, implement a read-only source command that emits a machine-readable operator apply packet/checklist from saved artifacts while still refusing to apply.
- Live apply remains blocked unless separately approved with exact operator phrase `apply-approved-g4-review-queue-items-v1`, policy `g4-review-queue-apply-v1`, actor, private reason, backup path, bounded max-apply, and audit output.

## Source-checkout smoke: G4 operator bundle consumes saved green v0.1.161 gate artifacts

This follow-up validates the newly added source-checkout operator bundle against the already collected live/runtime v0.1.161 evidence, without applying any mutation.

Implemented/evidence:

- Ran source checkout `dogfood g4-operator-apply-bundle` against `/Users/reddit/.agent-memory/memory.db`.
- Report directory: `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/`.
- Input artifacts were the saved green v0.1.161 retrieval ranking, rollback confidence, rollback replay, and telemetry reconciliation reports.
- Generated artifacts: `g4-review-queue-approval-report.json`, `g4-review-queue-preview.json`, `g4-apply-readiness.json`, and `g4-operator-apply-bundle.json`.
- Bundle quality gate passed with decision `operator_apply_bundle_ready_for_exact_manual_apply`.
- Child artifact summaries: human-review approval pass true, queue preview pass true, apply-readiness pass true, queue count `8`, `bounded_partial_apply_ready=true`.
- Privacy/safety stayed ref-safe: no raw proposal JSON, raw content, raw query text, raw trace summary, raw reason, or sample values; `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, ordinary conversation auto-approval false.

Next after this smoke:

- Do not release solely for this smoke/doc checkpoint.
- The exact bounded operator-approved G4 queue apply runbook has been drafted at `.dev/roadmap/memory-consolidation/g4-bounded-operator-apply-runbook.md`. It separates readiness from authorization and requires the exact policy/approval phrase, actor, private reason, backup path, bounded `--max-apply`, audit output, and post-apply verification before any live apply can be run.
- Generic continuation still must not execute live apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, or ordinary conversation auto-approval.

## Source checkpoint: G4 read-only operator apply bundle

This source slice makes the final pre-apply operator workflow easier without changing the safety boundary.

Implemented and verified in source:

- `dogfood g4-operator-apply-bundle` generates the G4 approval artifact, queue preview, bounded apply-readiness artifact, and exact manual apply command preview in one read-only workflow.
- The bundle requires explicit green artifact inputs for retrieval ranking, rollback confidence, rollback replay, and telemetry reconciliation, then generates the human-review approval report internally from the persisted review queue.
- The output remains aggregate/ref-safe: it records artifact paths, hashes, quality-gate decisions, queue counts, and a command preview, but no raw proposal JSON, raw content, raw query text, raw trace summary, sample values, or raw reason.
- The command explicitly reports `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, and ordinary conversation auto-approval false. Actual mutation remains only through the separate exact `g4-review-queue-apply` corridor.

Verification:

- RED observed before implementation: focused operator-bundle tests failed because `g4-operator-apply-bundle` was not a valid dogfood action.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `2 passed`.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_preview_consumes_green_gate_artifacts_without_broad_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_approval_report_is_ref_safe_read_only_gate tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_consumes_green_preview_without_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_blocks_unsafe_preview_artifact tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `6 passed`.
- `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-bundle --help` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `320 passed, 1 xfailed`.

Next after this slice:

- Commit/push/PR this source checkpoint when desired, but do not release solely for this narrow operator-bundle slice.
- If continuing source work first, either add a read-only source-checkout live bundle smoke/runbook against saved v0.1.161 gate artifacts or write the exact operator-approved apply plan. Do not execute live apply, default-ranking migration, telemetry reset, collapse/delete, unreviewed promotion, or ordinary-conversation auto-approval from generic continuation.

## Source checkpoint: fresh-epoch runway bundles comparison and reconciliation

This source slice fixes the operational gap between repeated fresh-epoch reports and the manual telemetry-reconciliation decision.

Implemented and verified in source:

- New read-only `dogfood fresh-epoch-runway` command runs the full artifact workflow in one operator-safe step: `fresh-epoch` -> `fresh-epoch-compare` -> `telemetry-reconciliation`.
- The command writes three durable JSON artifacts under `--report-dir`: fresh-epoch readiness, fresh-epoch comparison, and telemetry reconciliation.
- `--baseline-report` can be repeated so previously saved fresh-epoch reports are included in the comparison before the current report is fed into reconciliation.
- The aggregate runway payload remains ref-safe/privacy-safe: no raw conversation content, raw query text, raw trace summary, sample values, or raw source report body.
- The runway quality gate only turns green when fresh-epoch, comparison, and reconciliation gates are all green. It still sets `telemetry_reset_apply_supported=false`, `apply_supported=false`, keeps default retrieval unchanged, and requires human review.

Verification:

- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_fresh_epoch_runway_writes_artifacts_and_reconciliation -q` -> `1 passed`.
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'fresh_epoch_runway or fresh_epoch_compare or telemetry_reconciliation'` -> `5 passed, 127 deselected`.
- `.venv/bin/python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `314 passed, 1 xfailed`.
- Source-checkout live read-only smoke wrote artifacts to `/Users/reddit/.agent-memory/reports/v0.1.160-source-fresh-epoch-runway-20260514T081138Z/`; it correctly stayed blocked on the current mixed live corpus with `fresh_epoch_quality_gate_not_green`, `fresh_epoch_comparison_not_green`, and `telemetry_reconciliation_not_green`.

Next after this slice:

- Commit/push/PR this source checkpoint.
- After merge/release/runtime rollout, use `dogfood fresh-epoch-runway` for repeated real metadata-rich runtime windows instead of manually chaining three commands.
- Treat a green runway as reset-avoidance evidence only. Do not run live telemetry reset, default ranking migration, broad G4/background apply, collapse/delete, or ordinary-conversation auto-approval without a separate explicit operator approval corridor.

## Source checkpoint: telemetry reconciliation consumes fresh-epoch comparison evidence

This source slice strengthens the historical telemetry reconciliation decision after the fresh-epoch comparison gate.

Implemented and verified in source:

- `dogfood telemetry-reconciliation` now accepts `--fresh-epoch-comparison-report <json>` pointing at a saved `dogfood fresh-epoch-compare` report.
- The reconciliation payload includes aggregate/ref-safe `fresh_epoch_comparison_evidence`: report hash, report count, gate pass count, coverage/empty-retrieval ranges, unresolved unknown-empty totals, blocker counts, privacy flags, and a `usable_for_reset_avoidance` boolean.
- The reconciliation quality gate is green only when the live fresh-epoch gate is green, reset preview is available, and the supplied fresh-epoch comparison report is read-only/no-mutation/default-unchanged, quality-gate green, unresolved-gap-free, and privacy-safe.
- Without a comparison report, or with a failed comparison report, reconciliation stays blocked with explicit `blocked_reasons`; this is still report/gate hardening, not live telemetry reset enablement.
- The apply corridor now states `telemetry_reset_apply_supported=false` and keeps ordinary conversation auto-apply, broad apply, default ranking changes, and collapse/delete blocked.

Verification:

- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'telemetry_reconciliation_accepts_green_fresh_epoch_comparison_evidence or telemetry_reconciliation_blocks_failed_fresh_epoch_comparison_evidence'` -> `2 passed, 129 deselected`.
- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'fresh_epoch_compare or telemetry_reconciliation'` -> `4 passed, 127 deselected`.
- `.venv/bin/python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `313 passed, 1 xfailed`.

Next after this slice:

- Commit/push/PR this stacked source checkpoint after the fresh-epoch comparison gate.
- Collect real repeated metadata-rich live/runtime fresh-epoch reports with explicit `--epoch-start`, compare them with `dogfood fresh-epoch-compare`, then feed the green comparison report into `dogfood telemetry-reconciliation --fresh-epoch-comparison-report ...`.
- Treat a green reconciliation as reset-avoidance evidence only. Do not run live telemetry reset, default ranking migration, broad G4/background apply, collapse/delete, or ordinary-conversation auto-approval without a separate explicit operator approval corridor.

## v0.1.158 npm package metadata/package-contents audit checkpoint

This source slice completes the OSS package-surface follow-up after the npm-install-only README cleanup.

Verified source state before release:

- `package.json` now has an OSS-facing description, keywords, repository, bugs, license, bin, `files`, and public `publishConfig`.
- `npm pack --dry-run --json` shows the npm tarball contains only `LICENSE`, `README.md`, `bin/agent-memory.js`, and `package.json`.
- Internal `.dev`, `.agent-learner`, `.claude`, `.worktrees`, report, cache, and dogfood artifacts remain excluded from the npm package.
- Focused test coverage asserts package metadata and tarball contents in `tests/test_npm_launcher.py`.

Next after this package-surface slice:

- Return to the brain-like memory runway: continue metadata-rich dogfooding with explicit fresh epoch windows, compare fresh trace/retrieval coverage, and keep all broad apply/default ranking/collapse-delete/telemetry-reset automation blocked until real runtime evidence clears the gates.

## v0.1.157 OSS public-surface checkpoint

This checkpoint records the README/npm-install-only cleanup after the v0.1.155 runtime measurement fix. It is a public OSS surface cleanup, not an automation enablement.

Verified release state:

- Release: `v0.1.157` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.157`).
- npm: `@cafitac/agent-memory@0.1.157`.
- PyPI: `cafitac-agent-memory==0.1.157`.
- PR #341: `docs: make README npm-install only`.
- PR #342: `chore: release v0.1.157 [skip release]`.
- CI passed on PR #341, release-sync PR #342, and `main`.
- Published npm smoke passed with `UV_NO_CACHE=1 npm exec --yes --package @cafitac/agent-memory@0.1.157 -- agent-memory doctor`.

OSS README contract:

- Keep README focused on npm installation and first command success.
- Allowed top-level README content: one-line description, npm global install, `agent-memory bootstrap`, `agent-memory doctor`, npm one-shot usage, default local DB path, trust/deeper-doc links, and license.
- Disallowed in README: G-stage/dogfood/operator runbooks, runtime QA artifacts, broad roadmap status, long examples, Hermes integration walkthroughs, Python-first install paths, and internal automation-policy detail.
- Move any necessary detail to `docs/install-smoke.md`, `docs/first-run-memory-layer.md`, other linked docs, or `.dev`.

Recommended next PR-sized slice:

1. Audit `package.json` public metadata: description, keywords, homepage, repository, bugs, license, bin, and files.
2. Run `npm pack --dry-run` and inspect the tarball file list for internal-only `.dev`, report, cache, worktree, or dogfood artifacts.
3. Keep published npm smoke as the user-facing install gate.
4. Do not combine this OSS package cleanup with brain-like memory automation changes.

Automation guardrails remain unchanged:

- Overall north-star remains about 78-80%; substrate/evidence plumbing about 87%; safe automatic mutation/promotion about 66-70%.
- Live default ranking remains `conservative_legacy`; `graph_reinforced_v1` remains shadow-only.
- Broad G4/background apply, collapse/delete apply, live telemetry reset, default ranking migration, unreviewed automatic promotion, and ordinary conversation auto-approval remain blocked.





## v0.1.154 active runtime checkpoint

- Release: `v0.1.155` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`).
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`.
- Hermes `personal-oss` hook accepted and `hermes --profile personal-oss hooks doctor` is green.
- Runtime QA artifacts: `/Users/reddit/.agent-memory/reports/v0.1.154-runtime-qa-20260513T091806/`.
- v0.1.154 fixes episode decay-collapse evidence snapshots by reading episode `source_ids_json`; the v0.1.154 decay-collapse decision over the mixed corpus now runs read-only/no-mutation.
- Runtime QA remains safety-preserving: storage health healthy, mixed 50-task shadow ranking passed `50/50` with zero regressions and no default mutation, decay-collapse decision keeps collapse/delete apply disabled, and telemetry reconciliation remains manual-only.

## v0.1.153 next-step live dogfood checkpoint

Run directory: `/Users/reddit/.agent-memory/reports/v0.1.153-next-steps-20260513T084528/`.

Results from the requested next-step pass:

- Metadata-rich dogfooding produced a clean dogfood-only fresh epoch: `fresh-epoch-dogfood-only-strict.json` passed with trace coverage `1.0`, empty retrieval ratio `0.0`, no unknown/classified metadata gap, no raw query/trace/content samples, and no mutation.
- Wider post-v0.1.152/post-v0.1.153 fresh epochs still fail because old rows remain in the epoch window: post-v0.1.153 has `low_epoch_observation_trace_coverage` plus `epoch_empty_retrieval_outcome_metadata_gap_classified`; dominant blocker remains `classified_legacy_missing_outcome`, not an unresolved adapter payload gap.
- Default ranking remains protected: mixed 50-task shadow eval passed `50/50` with zero baseline regressions, but `active_ranking_policy=conservative_legacy`, `candidate_ranking_policy=graph_reinforced_v1`, `default_retrieval_unchanged=true`, `mutated=false`, and migration still requires the explicit migration command/approval.
- Reviewed trace-candidate promotion remains narrow only: generation/listing are read-only, ordinary conversation auto-approval is false, raw content is not allowed, and bad apply policy/approval exits without mutation.
- Broad G4/background apply remains blocked: dogfood epoch G4 preview is read-only/no-mutation with `broad_g4_apply_allowed=false`; required green gates are retrieval ranking, rollback replay, live telemetry reconciliation/fresh epoch, and human-reviewed queue approval.
- While checking broad G4/decay paths, the live v0.1.153 decay-collapse decision hit an episode evidence snapshot bug (`episodes` use `source_ids_json`, not `evidence_ids_json`). Source now has a regression fix and test; release v0.1.154 is required before relying on live decay-collapse decision over episode candidates.

## v0.1.153 released runtime checkpoint and next runway

This document is the restartable checkpoint after the v0.1.153 release/runtime rollout: 50-task expanded retrieval fixture gate, 75 checked-in retrieval eval tasks across the fixture directory, per-candidate collapse proof artifact persistence/replay with supersession-chain evidence, one fresh non-idempotent narrow live reviewed-candidate fact promotion, one guarded live reviewed procedure/episode promotion pair, copy/live-safe explicit approval corridor evidence, v0.1.153 `personal-oss` Hermes hook rollout, released named ranking policy/shadow-compare diagnostics, approval-gated config-only default-ranking migrate/rollback mechanics, and 50-task live-Hermes-DB representative fact plus mixed fact/procedure/episode shadow corpus evidence while keeping `conservative_legacy` as the live default.

Current verified release state:

- Release: `v0.1.155`.
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`.
- npm: `@cafitac/agent-memory@0.1.153`.
- PyPI: `cafitac-agent-memory==0.1.153`.
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`.
- Hermes hook doctor is green for `personal-oss` on the v0.1.153 runtime after `--accept-hooks`; default/earlypay/infra-admin stayed on prior green runtime unless explicitly upgraded later.
- Fresh G4 report directory retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.

Fresh diagnostics:

- `g4-linkage-gap-diagnose-v0138-fresh.json`: decision `fresh_trace_linkage_gap_not_detected`.
- `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/fresh-epoch-since-v0152-with-metadata-gap-diagnostic.json`: still blocks epoch-wide automation on `low_epoch_observation_trace_coverage` and `epoch_empty_retrieval_outcome_metadata_gap_classified`; metadata-gap drilldown reports `dominant_blocker=classified_legacy_missing_outcome`, `classified_missing_outcome_count=6`, and `unresolved_adapter_payload_gap_count=0`.
- `/tmp/agent-memory-apply-corridor-v0150/`: copy/live-safe explicit approval corridor smoke passed without unintended durable-memory mutation; live apply was idempotent.
- `/tmp/agent-memory-telemetry-reset-decision/copy-apply.json`: copy telemetry reset passed with protected durable memory tables unchanged; live telemetry reset remains blocked.
- 50-task expanded retrieval source fixture gate exists, the checked-in fixture directory evaluates at 75/75 pass, and live-Hermes-DB representative 50-task fact and mixed fact/procedure/episode corpora pass with zero shadow regressions/no durable ranking mutation. The checked-in expanded fixture is still not directly replayable against the tiny live DB because project-M1 references are absent; default ranking remains unchanged until a separate explicit default-rollout decision.
- Collapse proof artifacts can be persisted/replayed and can reach `satisfied` with reviewed supersession-chain/relation evidence, but collapse/delete apply remains disabled.

Progress estimate:

- Overall north-star: 78-80%.
- Substrate/evidence plumbing: about 87%.
- Safe automatic mutation/promotion: about 66-70%.
- Remaining work: about 20-22% overall.

Current interpretation:

Fresh v0.1.153 evidence and merged G5a-G5i plus default-ranking migration mechanics are healthy enough to continue the brain-like reviewed-candidate runway. The current runway has completed the expanded retrieval source fixture gate, stronger read-only opt-in ranking comparison, supersession-chain collapse proof evidence, one fresh guarded live reviewed-candidate fact promotion, one guarded live reviewed procedure/episode promotion pair, the explicit default-ranking opt-in-to-default migration design, released named ranking policy diagnostics plus approval-gated config-only migrate/rollback mechanics, and representative live-Hermes-DB fact plus mixed shadow evidence preserving `conservative_legacy`. Broad G4/background apply remains blocked. Current next work is to improve fresh-epoch telemetry coverage and reduce classified legacy missing-outcome rows through metadata-rich dogfooding before any explicit operator-approved default ranking migration.

Recommended sequence from here:

1. Keep live default ranking on `conservative_legacy`; do not run live `retrieval-ranking-migrate-default` until the operator gives the exact approval phrase and fresh-epoch telemetry is green.
2. Continue metadata-rich dogfooding to lift fresh-epoch observation/trace linkage coverage above threshold and replace classified legacy missing-outcome rows.
3. Keep live mixed fact/procedure/episode corpus work in read-only shadow comparison unless additional representative memories are promoted through guarded review corridors with backup/hash/actor/reason/approval evidence.
4. Keep collapse proof evidence-driven: `satisfied` requires supersession-chain/relation evidence, and collapse/delete apply remains disabled.
5. Keep fresh reviewed candidate promotion limited to the explicit guarded corridor with backup/hash/actor/reason/approval evidence; do not use broad apply.
6. Preserve broad G4/background apply as blocked until ranking, rollback replay, telemetry reconciliation/fresh epoch, and reviewed queue approvals all pass on real runtime evidence.

---

## Purpose

This document is the restartable checkpoint for the current `agent-memory` direction after the v0.1.125 G4 blocker drilldown release/live smoke and the current G4 readiness-blockers slice. Older sections below preserve historical context from the v0.1.77-v0.1.99 transition; the current source of truth is the v0.1.123 snapshot and next-slice guidance in this file plus `.dev/status/current-handoff.md`.

Use it when the user asks:

- "지금까지 진행상황 정리해줘"
- "앞으로 뭐 해야 해?"
- "최종 목표까지 어떤 스텝으로 갈 거야?"
- "agent-memory 이어서 진행해줘"

The goal is to keep future sessions aligned with the north-star while avoiding an unsafe jump from lightweight trace capture to automatic memory approval.

## North-star

`agent-memory` should become a graph-based memory consolidation runtime inspired by human memory, not a raw transcript archive and not a manual-only note database.

Final target:

1. Ordinary experience creates lightweight local traces.
2. Retrieval and use create activation/observation evidence.
3. Repeated, recent, salient, connected, and useful traces strengthen over time.
4. Weak traces decay, expire, or collapse into safe summaries.
5. Strong trace clusters become consolidation candidates.
6. Candidates are explainable and reviewable before long-term promotion.
7. Approved long-term memories become graph nodes/edges with provenance, status history, supersession, and conflict handling.
8. Conservative retrieval uses only safe/approved memory by default.
9. Automation stays opt-in, audited, reversible or reviewable, and never stores raw prompts by default.

## Current verified release state

Latest completed release/runtime rollout: `v0.1.136`

Released artifacts:

- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.136`
- npm: `@cafitac/agent-memory@0.1.136`
- PyPI: `cafitac-agent-memory==0.1.136`

Local Hermes/runtime signal:

- Published PyPI and npm smoke passed for `v0.1.136`.
- Source checkout is based on `v0.1.136` main.
- Main CI, auto-release, release-sync, publish, fresh artifact smoke, installed runtime smoke, live read-only G4 preview, and disposable installed apply smoke succeeded for the v0.1.136 release.
- Short next-action handoff: `.dev/status/next-agent-memory-action.md`.

Current implementation interpretation:

- G4a narrow query-preview cleanup is complete and has been live-applied once.
- Restore/audit safety hardening reached the approval-token positive validation checkpoint in `v0.1.122` and the metadata-only audit trace write checkpoint in `v0.1.123`.
- The v0.1.123 live smoke wrote exactly one metadata-only restore audit trace (`experience_traces.id=1465`) when approval/preflight gates passed; duplicate rerun failed closed with no second row.
- Live restore, broad consolidation apply mode, ordinary-conversation auto-approval, raw transcript storage, raw query-preview output, sample values, and default retrieval ranking changes remain disabled.
- The v0.1.128 release includes the future Hermes hook trace-to-observation linkage, metadata-only `retrieval_outcome` split for empty/retrieved observations, ref-safe review support for isolated approved decay-risk candidates, and Linux/SQLite retrieval-eval CI stabilization.
- The v0.1.136 release adds fallback trace linkage, fresh-vs-historical G4 warning resolution, persisted queue review state, and a first narrow approved `reinforcement_count` mutation for reviewed reinforcement items. It is installed at `/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory`. Broad G4/background apply remains blocked and no ordinary conversation auto-approval is enabled.

## Current live dogfood health snapshot

Read-only aggregate snapshot checked 2026-05-10 20:48 KST against `/Users/reddit/.agent-memory/memory.db`:

- `retrieval_observations`: 181 rows, latest id 2440
- `memory_activations`: 181 rows, latest id 2345
- `experience_traces`: 181 rows, latest id 1723
- `facts`: 3 rows, latest id 3
- `procedures`: 0
- `episodes`: 0
- `g4_review_queue_items`: 2
- `g4_review_queue_applications`: 2
- non-empty legacy `retrieval_observations.query_preview`: expected to remain 0 from prior cleanup; verify again before any live mutation.

Privacy/integrity interpretation:

- Observation, activation, and metadata-only trace evidence has grown substantially since the v0.1.77 checkpoint.
- Approved facts remain intentionally sparse under conservative defaults.
- Legacy stored query previews remain cleared.
- Restore artifacts and backups remain private local files because rollback artifacts can contain raw query previews.
- Broad G4 consolidation apply mode remains blocked.
- v0.1.123 live narrow-audit smoke report: `/Users/reddit/.agent-memory/reports/v0.1.123-live-narrow-audit-write-20260510T041120`; after the write, `retrieval_observations.query_preview` stayed at 0, `experience_traces` increased by exactly 1, `live_restore_mutated=false`, and scheduled dry-run still returned `continue_scheduled_dry_run_dogfooding_before_g4`.
- Current readiness-blockers release `v0.1.128` is installed at `/Users/reddit/.agent-memory/runtime/v0.1.128/.venv/bin/agent-memory` and Hermes config points at it. Manual installed-runtime hook smoke proved a new metadata-only trace can link to its retrieval observation (`retrieval_observations.id=2260`, `experience_traces.id=1543`, `related_observation_ids_json=[2260]`) and records `retrieval_outcome=retrieved_memory`; historical live rows keep aggregate coverage low (`0.0098`) until more new turns accumulate. Empty retrieval diagnostics now include `by_retrieval_outcome`, and decay-risk candidates include ref-safe review support commands for isolated approved candidates such as `fact:1`.

## What is intentionally not happening yet

Do not treat this as a gap to "fix" without a new plan.

Ordinary conversation currently does not:

- create approved facts/procedures/episodes automatically;
- infer preferences from normal chat;
- auto-approve long-term memory;
- change default retrieval ranking;
- store raw prompts, raw queries, transcripts, full user messages, or query previews;
- run background apply mode.

This is deliberate. The project is currently collecting safe weak evidence and measuring its quality before broader automation.

## Completed implementation arc

### Stage A/B: baseline and trace substrate

Completed:

- Lightweight `experience_traces` schema/API.
- `traces record/list` CLI for explicit sanitized local traces.
- Hermes trace recording path.
- Trace retention/safety reporting.

Current behavior:

- Traces are local and bounded.
- No raw transcript archive exists.
- Trace presence does not imply long-term memory approval.

### Stage C: activation/reinforcement/decay evidence

Completed:

- Retrieval observations bridge into `memory_activations`.
- Activation summary report.
- Reinforcement report.
- Decay-risk report.

Current behavior:

- Retrieved memory refs and empty retrievals create evidence rows.
- Reports are read-only and explanatory.
- Ranking/default retrieval is not changed by these reports.

### Stage D: consolidation candidate diagnostics

Completed:

- Read-only consolidation candidates.
- Candidate explanation CLI.

Current behavior:

- Candidate surfaces can explain possible memories from evidence.
- Candidate diagnostics do not mutate memory.

### Stage E: reviewed promotion and graph lifecycle

Completed:

- Manual reviewed promotion.
- Promotion audit/report.
- Lineage relation edges.
- Conflict/supersession preflight.
- Reviewed conflict relation edges.

Current behavior:

- Human/reviewed actions can promote durable memory with provenance.
- Graph edges record lineage and conflict context.
- Unsafe/conflicting promotion is guarded.

### Stage F: retrieval signal previews

Completed:

- Retrieval policy preview.
- Reinforcement ranker preview.
- Decay-risk prompt-time noise penalty preview.
- Bounded graph-neighborhood reinforcement preview.

Current behavior:

- Retrieval signal use is preview/advisory/opt-in.
- Default retrieval behavior remains conservative.

### Stage G: cautious automation and dogfood

Completed:

- G1: explicit `Remember this:` / `Please remember:` remember-intent review traces.
- G1a: read-only remember-intent dogfood quality report.
- G2: narrow opt-in auto-approval for explicit remember-preference traces only.
- G3: background consolidation dry-run report.
- G3a: saved background dry-run dogfood quality gates.
- G3b: ordinary Hermes turns create metadata-only traces by default.
- v0.1.69 hotfix: no-context ordinary turns still record metadata-only traces.
- v0.1.125: aggregate-safe blocker drilldowns for trace coverage, empty retrieval, and decay-risk candidates.
- Current source slice: new Hermes hook traces link to retrieval observation ids, can fall back to same-query observation lookup when packet ids are missing, empty-retrieval diagnostics distinguish fresh unresolved blockers from historical/reset-resolved diagnostics, decay-risk/reinforcement candidates can be persisted/reviewed, and only approved reinforcement-review items may increment `reinforcement_count`. Broad G4 apply remains blocked.
- v0.1.70/v0.1.71: debuggable explicit remember-intent diagnostics, Korean prefixes, and freeform secret-like rejection hardening.
- v0.1.72/v0.1.73: read-only storage-health and legacy query-preview cleanup preview reports.
- v0.1.74: read-only trace-quality report.
- v0.1.75: cron-friendly `dogfood scheduled-dry-run` bundle.
- v0.1.76: read-only `dogfood scheduled-compare` over saved scheduled report artifacts.
- v0.1.77: explicit `dogfood query-preview-cleanup --apply --actor --reason`; live cleanup cleared 70 legacy query-preview rows and left 0 remaining.

Current behavior:

- Explicit remember-intent remains the only path toward narrow auto-approval, and only through guarded commands. Safe explicit requests can be reviewed through sanitized summaries; secret-like requests remain rejected diagnostics.
- Ordinary conversation is evidence-only.
- Background dry-runs are read-only.

## Current decision point

The project is past the first two narrow cleanup mutations and deep into G4a restore/audit safety hardening. The current branch implements the next narrow mutation: a single metadata-only restore audit row write after validated approval and passing preflight, while live restore and broad G4 apply remain blocked.

Sequence from here:

1. Land this narrow audit-row write slice with focused restore/audit tests and full suite verification.
2. Release and smoke the published artifacts.
3. Run a live dry-run/contract check against the Hermes DB before considering any live audit-row write.
4. If a live audit-row write is approved later, take a backup first and use only the named restore/audit corridor; do not restore query previews in the live DB.
5. Reassess broad G4 consolidation apply mode from live scheduled dogfood evidence after the narrow restore/audit corridor is safe.

Why:

- Matching hashes are now a validated approval signal, but only this narrow metadata-only audit trace write is allowed.
- The restore/audit path is a narrow safety corridor; it must prove approval, preflight, duplicate/conflict, audit, and rollback behavior before broader consolidation mutation.
- The human-brain-like goal still requires cautious automation, but the current blocker is safe mutation infrastructure, not more raw evidence capture.


## v0.1.128 checkpoint and next move

Completed:

- PR #266, #267, #268, and #269 are merged; `v0.1.128` is published on GitHub/npm/PyPI and fresh artifact smoke passed.
- Live Hermes config now uses `/Users/reddit/.agent-memory/runtime/v0.1.128/.venv/bin/agent-memory`.
- New hook traces link to retrieval observations and include metadata-only retrieval outcomes.
- Latest scheduled dry-run remains read-only/no-mutation and blocks broad G4 for trace-quality, empty-retrieval, and isolated-decay-risk reasons.

Next:

1. Collect more v0.1.128 Hermes turns so the new linkage path can replace historical unlinked rows in the rolling window.
2. Classify empty retrievals into expected misses vs query/scope gaps using the new `by_retrieval_outcome` diagnostics.
3. Resolve `fact:1` via reviewed relation edge or explicit isolated-memory confirmation.
4. Only after those blockers clear, turn the xfailed broad-G4 review-queue contract into a real preview/apply path; broad apply stays blocked until then.


## Fresh epoch direction after v0.1.128

Decision: prefer an epoch-filtered read-only report before any telemetry reset. Historical rows are preserved because they contain useful audit/release/safety evidence, but broad-G4 readiness can now be judged against a fresh v0.1.128+ telemetry window that excludes older rows missing observation links and `retrieval_outcome` backfill.

Current implementation slice:

- Add `agent-memory dogfood fresh-epoch <db> --epoch-start <ISO>`.
- Output `dogfood_fresh_epoch_readiness` with `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, and no apply support.
- Report aggregate-only epoch coverage, activation trace-link coverage, empty retrieval outcome breakdowns, trace distributions, candidate signals, and historical rows excluded.
- Keep reset/delete/apply out of scope; if needed later, design telemetry-only reset as a separate preview/apply corridor with backup, actor, reason, policy, audit, and rollback.

First live source smoke against `/Users/reddit/.agent-memory/memory.db` used epoch `2026-05-09T21:57:33Z` and wrote `/tmp/agent-memory-fresh-epoch-v0128-source.json`. It stayed read-only/no-mutation and showed 21 observations, 21 traces, 21 activations, coverage ratio `0.2381`, 5 linked observations, 10 empty retrievals, and blockers `low_epoch_observation_trace_coverage` plus `epoch_empty_retrieval_outcome_unknown`. This confirms the historical rows can be excluded safely, but the fresh epoch still needs more dogfood before broad G4 planning.


## v0.1.136 checkpoint and next move

Completed and released/runtime-smoked:

- Fresh trace linkage gap closed with tests for metadata-only empty retrieval turns, no-context injected turns, and same-query fallback linkage when `packet.retrieval_observation_id` is missing.
- G4 quality gate now separates historical/reset-resolved warnings from fresh unresolved evidence under `g4-review-queue-preview --epoch-start <ISO>`; historical unknown/trace-gap evidence can be diagnostic-only when the fresh epoch is clean.
- Persisted approved queue apply now has the first narrow guarded memory mutation: approved `reinforcement_review` queue items can increment only `reinforcement_count` on the target memory. It requires explicit policy, approval phrase, actor, reason hash, backup path, audit row, rollback hint, and leaves status/default retrieval/raw content unchanged.
- Focused tests and full `uv run --python 3.11 pytest tests/ -q` are green (`285 passed, 1 xfailed`). PR #285, release-sync PR #286, publish workflow, fresh npm/PyPI artifact smoke, installed runtime smoke, and live read-only aggregate preview are complete.

Next:

1. Dogfood more v0.1.136 Hermes turns so the fresh epoch has no unlinked observations.
2. Re-run `dogfood g4-review-queue-preview --epoch-start <release_epoch>` from the installed runtime and verify whether `background_empty_retrieval_trace_linkage_gap` clears.
3. Do not live-apply queue mutations without an explicit operator decision and fresh backup. If approved later, start with the persisted `fact:1` reinforcement-review item; this is still a narrow reinforcement marker, not broad consolidation apply.
4. If the trace-linkage gap persists, design a reviewed telemetry backfill/reset corridor rather than silently deleting or rewriting live telemetry.
5. Broad background apply stays blocked until trace quality, empty retrieval quality, and review/rollback behavior are all healthy under installed runtime evidence.


Release/runtime verification details:

- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.136`
- npm: `@cafitac/agent-memory@0.1.136`
- PyPI: `cafitac-agent-memory==0.1.136`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory`
- Hermes config backup: `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.136-20260510T2044`
- Hook smoke artifact: `/tmp/agent-memory-v0136-hook-smoke.json`
- Live G4 preview artifact: `/tmp/agent-memory-v0136-g4-preview-live.json`
- Disposable installed apply smoke artifact: `/tmp/agent-memory-v0136-installed-apply.json`

## Recommended next PR-sized slices

### G3c: Add read-only `dogfood storage-health`

Goal:

Create a one-command health report that answers whether live Hermes/agent-memory storage is functioning correctly without printing raw content.

Candidate command:

```bash
agent-memory dogfood storage-health ~/.agent-memory/memory.db \
  --hermes-config ~/.hermes/config.yaml
```

Current implementation status:

- Completed and released in v0.1.72 via PR #127/#128.
- At release time, the Hermes runtime was updated to `/Users/reddit/.agent-memory/runtime/v0.1.72/.venv/bin/agent-memory`; the current runtime is recorded in the top-level verified state above.
- Live DB smoke reported `kind: dogfood_storage_health`, `read_only=true`, `mutated=false`, Hermes hook present, configured DB path present, and no raw-content marker leakage. The live DB status was `warning` because legacy non-empty stored query excerpts still exist and some old ordinary turn traces predate the final metadata-only shape.

Scope:

- table counts and latest timestamps for observations, activations, traces, facts/procedures/episodes/relations;
- active runtime path/version compatibility fields;
- Hermes hook path marker when available;
- recent non-empty `query_preview` count;
- missing hash counts;
- invalid JSON counts;
- orphan activation links;
- trace metadata shape counts;
- facts unchanged under ordinary turns as an expected conservative signal;
- clear `status` and `warnings` fields.

Acceptance:

- read-only, `mutated=false`;
- never prints raw prompts, query text, query previews, transcripts, full memory content, tokens, or secrets;
- works on the live DB and on temp DB fixtures;
- flags the v0.1.68-style pattern where observations/activations advance but traces do not;
- docs explain that sparse facts are normal unless explicit remember/apply commands ran.

### G3c-followup: Add read-only legacy query-preview cleanup preview

Status: completed and released in v0.1.73 via PR #129/#130. Published npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.73/.venv/bin/agent-memory`, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed.

Goal:

Make the storage-health legacy stored-query-excerpt warning actionable without printing raw stored excerpts or adding an apply mode.

Command shape:

```bash
agent-memory dogfood query-preview-cleanup ~/.agent-memory/memory.db \
  --older-than 2030-01-01T00:00:00
```

Scope:

- aggregate non-empty stored query excerpt counts;
- aggregate cleanup-eligible counts before the supplied cutoff;
- earliest/latest timestamps only;
- explicit privacy markers proving samples/raw values are omitted;
- recommended operation marker for future manual cleanup planning.

Acceptance:

- read-only, `mutated=false`;
- no raw prompts, query text, query previews, transcripts, full memory content, tokens, API keys, or secrets;
- no sample values;
- works on the live DB and on temp DB fixtures;
- no apply mode until explicitly planned and approved.

### G3d: Add read-only `dogfood trace-quality`

Status: completed and released in v0.1.74 via PR #132/#133. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`, published npm/PyPI/uvx smokes, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed. Live 24h report currently returns `status=warning` / `recommendation=continue_dogfooding` because recent observations are still not linked from traces strongly enough; this is an expected conservative gate before G4 planning.

Goal:

Measure whether ordinary conversation traces are useful enough to support later consolidation work.

Candidate command:

```bash
agent-memory dogfood trace-quality ~/.agent-memory/memory.db \
  --since-hours 24 \
  --min-trace-coverage 0.25 \
  --min-evidence-count 2
```

Scope:

- observation-to-trace coverage by time window;
- empty retrieval ratio;
- retrieved evidence repetition counts;
- trace event-kind and retention-policy distribution;
- metadata-only invariant checks;
- candidate-signal proxy counts;
- quality gate recommendation.

Acceptance:

- read-only, `mutated=false`, default retrieval unchanged;
- outputs `continue_dogfooding`, `ready_for_more_dry_runs`, or `consider_g4_plan` style recommendation;
- does not create candidates or approvals;
- does not print raw conversation content.

### G3e: Add cron-friendly `dogfood scheduled-dry-run` bundle

Status: completed and released in v0.1.75 via PR #135/#136. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.75/.venv/bin/agent-memory`, published npm/PyPI/uvx smokes, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed. The first live quality gate returned `continue_scheduled_dry_run_dogfooding_before_g4`, so G4 apply-mode is still not the next implementation step.

Goal:

Collect several G3/G3a/G3d reports over time so the decision to continue, tune, or plan G4 is data-backed without requiring ad hoc command choreography.

Command shape:

```bash
agent-memory dogfood scheduled-dry-run ~/.agent-memory/memory.db \
  --output ~/.agent-memory/reports/scheduled-dry-run-YYYYMMDD-HHMMSS.json \
  --since-hours 24 \
  --min-trace-coverage 0.25 \
  --min-evidence-count 2 \
  --candidate-min 1 \
  --max-decay-risk 0
```

Scope:

- one cron-friendly read-only command;
- bundle `dogfood storage-health`, `dogfood trace-quality`, `dogfood remember-intent`, and inline `consolidation background dry-run`;
- write the same JSON to `--output` when provided;
- expose one conservative `quality_gate` whose pass only means "write a separate G4 plan with RED tests";
- keep privacy markers and no-mutation/default-retrieval-unchanged markers top-level.

Acceptance:

- multiple scheduled reports can complete without lock contention or mutation;
- quality warnings are explainable or decreasing;
- candidate signals become non-zero or the report explains why evidence remains sparse;
- privacy checks stay clean;
- no cleanup apply mode, G4 apply mode, ordinary-conversation auto-approval, raw transcript storage, broad preference inference, or default retrieval ranking change.

### G3f: Collect and compare scheduled dry-run reports

Status: completed and released in v0.1.76 via PR #138/#139. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory`, published npm/PyPI/uvx/npm smokes, live DB scheduled-compare smoke, Hermes E2E, and `hermes hooks doctor` passed. The first comparison decision remains `continue_scheduled_report_collection_before_g4`, so G4 apply-mode is still not the next implementation step.

Goal:

Run the new G3e bundle repeatedly from the live Hermes DB and compare the aggregate quality gate, warning set, candidate counts, trace coverage, and decay-risk signals over time before any G4 apply-mode plan.

Scope:

- save timestamped `dogfood scheduled-dry-run` JSON artifacts;
- add `dogfood scheduled-compare` as a read-only comparison over repeated saved artifacts;
- compare only counts, timestamps, booleans, ratios, hashes, IDs, and warning names;
- no raw content samples or embedded raw report bodies;
- no cleanup/apply mutation;
- no default retrieval or hook config changes.

Command shape:

```bash
agent-memory dogfood scheduled-compare \
  --report ~/.agent-memory/reports/scheduled-dry-run-1.json \
  --report ~/.agent-memory/reports/scheduled-dry-run-2.json \
  --output ~/.agent-memory/reports/scheduled-compare.json \
  --min-report-count 2 \
  --max-decay-risk 0
```

Acceptance:

- multiple reports complete read-only with `mutated=false`;
- warning trends are explainable;
- decision remains conservative unless quality signals improve;
- any G4 plan is a separate RED-tested PR, not bundled into reporting.

### G3g: Optional legacy privacy cleanup apply plan

Goal:

Handle old non-empty `query_preview` rows from earlier versions without touching new privacy-safe rows.

Scope:

- read-only preview first;
- count and timestamp windows only;
- optional backup path;
- no mutation unless a later explicit cleanup command is approved.

Acceptance:

- no raw previews printed;
- cleanup is not bundled with G4 or auto-approval work;
- user approval required before any mutation.

### G3g: Continue scheduled collection and lock the G4 readiness sequence

Status: in progress in this docs checkpoint. Baseline G4-readiness artifacts were created with the v0.1.76 runtime; the latest compare decision remains `continue_scheduled_report_collection_before_g4`. A local Hermes cron job `6894df1bfd4c` is scheduled to collect four more read-only reports every 6 hours under `/Users/reddit/.agent-memory/reports/g4-readiness`.

Goal:

Make the post-G3f path explicit while report artifacts accumulate: collect, compare, write the G4 apply-mode contract, then implement only the first narrow mutation slice.

Detailed plan:

- `.dev/roadmap/memory-consolidation/g4-readiness-and-first-mutation-plan.md`

Acceptance:

- local scheduled artifacts are not committed;
- docs record artifact paths and cron boundary without raw report bodies;
- the first recommended mutation is legacy `query_preview` cleanup apply, not ordinary conversation auto-approval;
- no DB mutation, retrieval change, or Hermes config change lands in this planning slice.

### G4-plan: Draft background apply-mode plan only after G3 quality is trusted

Goal:

Write, not implement, the apply-mode plan once dry-run and trace-quality reports justify it.

Required prerequisites:

- storage-health stable;
- trace-quality stable over multiple sessions;
- G3/G3a reports have enough candidate signal;
- candidate explanations are human-reviewable;
- conflict/supersession preflight works on representative candidates;
- rollback/audit path is documented.

Hard guardrails:

- no ordinary conversation auto-approval by default;
- no raw transcript storage;
- no retrieval ranking default change;
- `--apply` requires explicit actor, reason, policy, and audit;
- background apply may start only with explicit remember-intent or reviewed candidate classes, not broad LLM-extracted ordinary conversation.

## Longer-term path after G4

### Stage H1: consolidation eval fixtures and metrics

Build fixture suites that measure whether consolidation improves memory quality without privacy regression.

### Stage H2: graph/trace visualization export

First MVP complete in PR #149 / v0.1.80. `graph export-html` exports a standalone local neural-style HTML graph over memory refs, relations, traces, observations, and activations. The default is read-only/redacted/ref-only; curated memory labels require explicit `--include-memory-labels`. Visual QA confirms it renders and is useful as an MVP, but richer filtering/search/clustering remains future polish.

### Stage H3: backup/import/export

Make richer memory DB state operationally safe.

### Stage H4: public docs hardening

Promote reviewed behavior into public docs only when defaults are stable and accurately described.

## What future sessions should do first

When resuming from here:

1. Check repo state:

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git log --oneline -8
git tag --sort=-version:refname | head -5
```

2. Verify runtime state:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.80/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
HOME=/Users/reddit hermes hooks doctor
```

3. Do a raw-content-safe live DB health check if the user asks whether data is still accumulating.

4. If implementing, keep collecting/comparing G3f scheduled reports or draft a separate G4 plan only after the report trend justifies it; do not implement apply mode directly from this checkpoint.

5. Preserve local-only untracked artifacts:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`

## Success criteria before broad automation

Do not broaden automation until all of these are true:

- storage-health passes repeatedly;
- trace-quality report shows stable coverage and no privacy regressions;
- background dry-run reports are not dominated by sparse/noisy warnings;
- candidate explanations are understandable without raw transcript access;
- conflict/supersession preflight catches representative conflicts;
- review/rollback/audit paths are exercised;
- default retrieval remains conservative and approved-memory-only unless explicitly opted in.

## Short answer for the current strategy

Yes: for now we keep talking and using Hermes so ordinary traces, retrieval observations, and activation evidence accumulate. Then we inspect the quality of that evidence with read-only reports. Only after the evidence is stable and reviewable do we consider narrow, guarded apply-mode automation.


### Fresh epoch empty retrieval classification slice (2026-05-10 13:39 KST)

Purpose: before telemetry reset, classify fresh-epoch empty retrieval rows that still have `retrieval_outcome=unknown` using aggregate metadata only.

Implemented report additions in the active branch:
- `empty_retrieval_diagnostics.by_likely_cause`
- `empty_retrieval_diagnostics.unknown_outcome_drilldown`

Live source smoke artifact: `/tmp/agent-memory-fresh-epoch-classified-source.json` (local-only, not committed). Current aggregate reading: 22 unknown empty outcomes are classified as `legacy_missing_outcome_metadata_gap`, unresolved unknown count is 0, but fresh-epoch quality still blocks on low linkage/high empty ratio/classified metadata gap.

Next after this release: handle `fact:1` isolated approved memory using relation or intentional-isolation review support, then implement telemetry-only reset preview.


### Telemetry reset preview slice (2026-05-10 13:55 KST)

- Branch: `feat/telemetry-reset-preview`.
- Added `dogfood telemetry-reset-preview` as read-only aggregate preview only; no apply/delete path.
- Guardrails: telemetry tables only (`retrieval_observations`, `memory_activations`, `experience_traces`), protected memory/source/relation/status tables are counted but not mutated, backup required before any future apply design.
- Live source preview artifact: `/tmp/agent-memory-telemetry-reset-preview-source.json`; epoch `2026-05-09T21:57:33Z` would target 5,965 historical telemetry rows and retain 66 rows per telemetry table; protected tables remain out of scope.


### Broad G4 review queue preview slice (2026-05-10 14:11 KST)

- Branch: `feat/g4-review-queue-preview`.
- Added `dogfood g4-review-queue-preview` as read-only queue contract preview only; no queue persistence and no apply path.
- Queue entries require human review and carry policy/audit/ref-safe-evidence/operator-command fields; raw source/query/trace/sample values are excluded.
- Live source preview artifact: `/tmp/agent-memory-g4-review-queue-preview-source.json`; current DB produced 2 ref-only queue entries, but quality gate remains blocked by `background_quality_warnings_present`, so broad G4 apply remains blocked.


### G4 background quality warning decomposition (2026-05-10 14:57 KST)

- Branch: `feat/g4-warning-decomposition`.
- Added ref-safe `background_quality_warning_analysis` to `dogfood g4-review-queue-preview`.
- The old opaque `background_quality_warnings_present` gate is now decomposed into specific blocking reasons when applicable.
- Live source smoke artifact: `/tmp/agent-memory-g4-warning-decomposition-source.json`. Current live result still blocks broad G4, but now specifically on `background_empty_retrieval_outcome_unknown` and `background_empty_retrieval_trace_linkage_gap` instead of the generic warning.
- Output remains aggregate/ref-only with raw content/query/trace/sample values excluded.


### G4 blocker follow-up implementation slice (2026-05-10 15:23 KST)

- Branch: `feat/g4-blocker-followups`.
- Implements all three requested next steps in sequence while keeping broad G4 apply disabled:
  1. `g4-review-queue-preview --epoch-start <ISO>` now compares background blockers against a fresh-epoch report so historical/metadata-classified unknown empty retrievals are split from unresolved fresh unknowns. Live source smoke at `/tmp/agent-memory-g4-followups-preview-source.json` shows `background_empty_retrieval_outcome_unknown` has been reduced to `background_empty_retrieval_outcome_classified_or_reset_previewable`; the remaining live blocker is trace linkage.
  2. Hermes pre-LLM trace recording now has a ref-safe fallback that links a trace to the latest same-query `retrieval_observations` row by SHA-256 when `packet.retrieval_observation_id` is missing. This stores only observation ids and query hashes, not raw prompts.
  3. Adds persisted G4 review queue commands before any apply path: `g4-review-queue-persist`, `g4-review-queue-list`, and `g4-review-queue-update`. Persist/update mutate only the new `g4_review_queue_items` table, store operator reasons as SHA-256, omit proposal raw JSON from list output, and keep `apply_supported=false`.
- Local verification passed: targeted G4/fallback tests and full `uv run --python 3.11 pytest tests/ -q` => `283 passed, 1 xfailed`.
- Broad G4 apply is still intentionally blocked. Review queue persistence is not apply. Next release target: v0.1.134 after PR/CI/publish.


## G5i local checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 11:08 KST

Runtime baseline remains `v0.1.146` at `/Users/reddit/.agent-memory/runtime/v0.1.146/.venv/bin/agent-memory`; fresh linkage evidence still includes `fresh_trace_linkage_gap_not_detected` and report directory `g4-v0138-20260512-132253`. Overall north-star: 72-74%.

Local G5i implements the requested five next steps after G5h: rollback replay rollups, live-compatible retrieval fixture expansion summaries, collapse equivalence proof surface, telemetry-only apply safety-gate reporting, and broad G4 apply reassessment fields. Broad G4/background apply remains blocked; default ranking changes, collapse/delete apply, and ordinary conversation auto-approval remain forbidden.
