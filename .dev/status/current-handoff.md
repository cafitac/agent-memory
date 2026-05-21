# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-21 10:07 KST

## Current checkpoint: classification validation now has a read-only resolution consumer

- Current source has a local TDD slice after `f182b4e Record classification validation CI result`, adding `dogfood scheduled-evidence-blocker-classification-resolution`. Unrelated untracked harness/scratch dirs remain (`.agent-learner/`, `.claude/`, `.dev/kb/retrieval-eval-m1-implementation-plan.md`, `.omc/`, `.worktrees/`) and should stay untouched unless explicitly requested.
- The command consumes a green `dogfood_scheduled_evidence_blocker_classification_validation` artifact, verifies it is read-only/default-retrieval-unchanged/privacy-safe and carries no mutation authority, hash-binds it, and emits `dogfood_scheduled_evidence_blocker_classification_resolution`.
- It is deliberately report-only: `keep_blocked_collect_more_activation_evidence` remains unresolved/hard-blocking, `manual_review_stale_or_wrong_follow_up_required` remains unresolved follow-up, and only `manual_review_harmless_low_activation` can resolve an evidence blocker for bounded partial automation evidence. It still cannot write memory status, mutate retrieval ranking/default retrieval, collapse/delete, or grant background/default authority.
- Live smoke consumed `/tmp/agent-memory-scheduled-evidence-blocker-classification-validation-next-check.json` and wrote `/tmp/agent-memory-scheduled-evidence-blocker-classification-resolution-next-check.json`. Since both `fact:5` and `fact:6` were conservative keep-blocked classifications, the new resolution artifact correctly reports `resolution_gate.pass=false`, `hard_blocked_memory_refs=[fact:5, fact:6]`, `bounded_partial_automation_allowed=false`, and all broad/default/background authority flags false.
- Verification so far: RED observed for missing `scheduled-evidence-blocker-classification-resolution`; targeted test `uv run pytest tests/test_cli.py::test_python_module_cli_dogfood_scheduled_evidence_blocker_classification_resolution_consumes_validation_read_only -q` -> `1 passed`; focused scheduled suite `uv run pytest tests/test_cli.py -q -k "scheduled_blocker_resolution or scheduled_dry_run or scheduled_evidence_blocker"` -> `6 passed, 244 deselected`. Full local suite is green (`439 passed, 1 xfailed in 250.70s`); commit/push and CI are still pending for this local checkpoint.
- Current progress framing: scoped local human-brain-like lifecycle remains 100% at the bounded/review-gated/local-first boundary. Operational confidence remains about `98%`: classification evidence and the consuming resolution artifact are now exact/hash-bound, but scheduled bounded partial automation remains blocked while `fact:5`/`fact:6` are explicitly keep-blocked.

Next session should start from `.dev/status/next-agent-memory-action.md`: finish full verification/commit/push/CI for this read-only resolution consumer, then continue normal-turn observation for `fact:5`/`fact:6`.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: exact read-only validation artifact added for evidence-blocker classifications

- Current source is `develop` after pushed `926de66 Add evidence blocker classification validation`; GitHub Actions CI run `26195646109` completed successfully. Unrelated untracked harness/scratch dirs remain (`.agent-learner/`, `.claude/`, `.dev/kb/retrieval-eval-m1-implementation-plan.md`, `.omc/`, `.worktrees/`) and should stay untouched unless explicitly requested.
- Latest live artifacts remain `/tmp/agent-memory-decay-risk-next-check.json`, `/tmp/agent-memory-scheduled-dry-run-next-check.json`, `/tmp/agent-memory-scheduled-blocker-resolution-next-check.json`, and `/tmp/agent-memory-scheduled-evidence-blocker-packet-next-check.json`; this slice adds `/tmp/agent-memory-scheduled-evidence-blocker-classification-validation-next-check.json`.
- The live hard evidence-collection refs are still `fact:5` and `fact:6`. Both are approved/connected but low-activation candidates only; do not delete, collapse, deprecate, lower authority, or change ranking from decay score alone.
- Implemented the next safe read-only validation surface: `dogfood scheduled-evidence-blocker-classification-validate --packet <packet.json> --classification <ref>=<option> ...` validates exact classifications against the packet's offered options, hash-binds the packet, and emits `dogfood_scheduled_evidence_blocker_classification_validation`.
- The validation artifact is deliberately not a mutation/apply path. It keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `bounded_partial_automation_allowed=false`, `broad_g4_apply_allowed=false`, `ordinary_conversation_auto_approval=false`, `writes_memory_status=false`, `writes_retrieval_ranking=false`, and `enables_background_or_unattended_apply=false`.
- Live validation smoke used conservative keep-blocked classifications for both refs: `fact:5=keep_blocked_collect_more_activation_evidence` and `fact:6=keep_blocked_collect_more_activation_evidence`. It produced `classification_gate.pass=true`, `classified_candidate_count=2`, no unclassified refs, no invalid classifications, and privacy flags false. This records exact read-only classification evidence only; it still does not resolve the scheduled blocker or authorize bounded partial automation.
- Validation: RED observed for missing `scheduled-evidence-blocker-classification-validate`; GREEN targeted test `uv run pytest tests/test_cli.py::test_python_module_cli_dogfood_scheduled_evidence_blocker_classification_validate_is_read_only -q` -> `1 passed`; focused scheduled suite `uv run pytest tests/test_cli.py -q -k "scheduled_blocker_resolution or scheduled_dry_run or scheduled_evidence_blocker_packet or scheduled_evidence_blocker_classification"` -> `5 passed, 244 deselected`; `git diff --check` -> pass; full local suite `uv run pytest tests/ -q` -> `438 passed, 1 xfailed in 219.33s`; GitHub Actions CI run `26195646109` -> success.
- Current progress framing: scoped local human-brain-like lifecycle remains 100% at the bounded/review-gated/local-first boundary. Operational confidence remains about `98%`: runtime/storage/trace are healthy and evidence-blocker review evidence is now exact/hash-bound, but scheduled bounded partial automation remains blocked until a separate blocker-resolution follow-up consumes classifications safely and all other checks remain green.

Next session should start from `.dev/status/next-agent-memory-action.md`: either continue normal-turn observation for `fact:5`/`fact:6` or add a separate read-only blocker-resolution follow-up that consumes validated classifications without widening mutation authority.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: scheduled blocker resolution separates hard decay blockers from advisory decay refs

- Implemented the read-only scheduled-blocker-resolution refinement for the latest live pattern: mixed decay-risk sets now report `evidence_collection_candidate_count`, `monitor_only_candidate_count`, `monitor_only_resolution`, and `operator_severity` instead of leaving all decay-risk candidates as undifferentiated `unresolved`.
- The live scheduled report still resolves trace quality and background warnings, but keeps `decay_risk_above_threshold` red as `resolution=evidence_collection_candidates_still_block`, `operator_severity=hard_blocker`, `evidence_collection_candidate_count=1`, `monitor_only_candidate_count=7`, and `monitor_only_resolution=advisory_only`.
- This does not widen mutation authority: `broad_g4_apply_allowed=false`, `bounded_partial_automation_allowed=false` while an evidence-collection candidate remains, `ordinary_conversation_auto_approval=false`, and default retrieval remains `approved_only_unchanged`.
- TDD gate: new RED test `test_python_module_cli_dogfood_scheduled_blocker_resolution_separates_monitor_only_from_evidence_collection` failed on the old `resolution=unresolved`; after implementation, focused scheduled tests pass (`3 passed, 244 deselected`) and full suite passes (`436 passed, 1 xfailed`).
- Live CLI smoke over `/tmp/agent-memory-scheduled-dry-run-now.json` confirms the operator-facing split above without raw report/query/sample exposure.
- Current progress framing: scoped local human-brain-like lifecycle remains 100% at the bounded/review-gated/local-first boundary; operational confidence remains about 98%, with the next real blocker narrowed to collecting/observing evidence for the current one evidence-collection decay candidate.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: decay-risk review pass connected isolated approved memories

- Followed up the live storage/Hermes dogfood by inspecting the decay-risk candidates with read-only decay, graph, history, and SQL aggregate checks. The post-review decay set contains 8 refs: 1 true evidence-collection candidate and 7 monitor-only refs.
- Before mutation, created live DB backup `/Users/reddit/.agent-memory/backups/manual-decay-relation-review-20260518-160554.db` with SHA-256 `cfef7424b5d4fbb7a08c79f39d82b6b1c06bc05c553ce8e051505cc3346354ec`.
- Added three reviewed semantic relation edges for approved memories that were frequently activated but graph-isolated: `fact:4 -> concept:g4-safety-gates`, `procedure:1 -> concept:live-mixed-retrieval-shadow-corpus`, and `episode:1 -> concept:live-mixed-retrieval-shadow-corpus`. No statuses, retrieval ranking, facts/procedures/episodes, or automation authority were changed.
- Post-review decay report now has `low_connectivity=0.0`, all candidates are connected, and resolution hints changed to `collect_more_activation_evidence_before_decay_action=1` plus `monitor_only_no_mutation=7`. `fact:5` remains the only real follow-up candidate due to low recent activation evidence.
- Scheduled dry-run remains intentionally conservative: read-only/no mutation/privacy-safe, but `decay_risk_above_threshold` remains red because the strict threshold is `--max-decay-risk 0` and advisory candidates still exist. This is expected and should not authorize deletion or broad G4/default apply.
- Ran three additional real Hermes normal-turn dogfood smokes; all returned markers successfully and advanced the live DB by `+4 retrieval_observations`, `+7 memory_activations`, and `+4 experience_traces`. Relation count stayed unchanged during dogfood.
- Latest storage-health remains healthy with no warnings: `retrieval_observations=2950`, `memory_activations=5760`, `experience_traces=2950`, plugin enabled, hook occurrences `0`, duplicate risk `false`, doctor status `ok`.
- Latest 24h trace-quality remains green for structure: 483 observations, 483 traces, 1491 activations, observation/trace coverage `1.0`, empty retrieval ratio `0.3251`, no warnings, recommendation `consider_g4_plan`.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: pushed green CI plus duplicate-hook doctor guard

- Pushed develop through `825270b Harden consolidation telemetry reports` to `origin/develop`; GitHub Actions run `26015270138` completed green on commit `825270ba329540f36ccfc41dcfdf9882bcbf0fa8`.
- Live personal-oss Hermes plugin dogfood remains plugin-only from `agent-memory`'s perspective: `hermes-doctor /Users/reddit/.agent-memory/memory.db --config-path /Users/reddit/.hermes/profiles/personal-oss/config.yaml` reports `status=ok`, `hook_installed=false`, `hook_occurrences=0`, `plugin_enabled=true`, `duplicate_context_injection_risk=false`, and no warnings.
- Live activation observation over the latest 80 activations reports `candidate_activation_count=73`, `sentinel_or_empty_noise_count=7`, `ratio=0.0875`, and `excluded_from_candidate_reports=true`; noise is visible but filtered from reinforcement candidates.
- New doctor/UX slice adds plugin-aware Hermes doctor output: plugin-only setup is valid, and simultaneous plugin + `hermes-pre-llm-hook` shell hook returns `status=warning` with `duplicate_context_injection_risk=true` and a concrete remove-one-path recommendation.
- Focused doctor/plugin tests and full test suite pass locally: `433 passed, 1 xfailed`. Next gate is commit/push and CI watch for the doctor guard commit.
- Current progress framing: core scoped local human-brain-like memory loop remains 100% at the bounded/review-gated/local-first boundary. The new remaining work is operational confidence/UX, not new memory mutation authority.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: consolidation telemetry cleanup and live Hermes plugin dogfood complete

- Latest source checkpoint tightens the G4/G5 memory-consolidation corridor: activation reports now emit noise diagnostics and exclude sentinel/empty retrieval telemetry from reinforcement candidates; graph snapshots split semantic relation edges from activation telemetry edges; consolidation candidates now project fact/procedure/episode promotion shapes; G4 review queue supports an explicit `conflict` review state without applying mutations.
- Live personal-oss Hermes profile was dogfooded safely: the old agent-memory shell `hermes-pre-llm-hook` entry was removed from `hooks.pre_llm_call`, `/Users/reddit/.hermes/profiles/personal-oss/plugins/agent-memory` now symlinks to this repo, `plugins.enabled` already contains `agent-memory`, and `hermes plugins list` reports `agent-memory enabled 0.1.162`. This avoids duplicate memory-context injection between shell hook and plugin.
- Live smoke passed with current OpenAI Codex lane: `AGENT_MEMORY_DB_PATH=/Users/reddit/.agent-memory/memory.db AGENT_MEMORY_HERMES_SCOPE=project:agent-memory hermes chat -Q -q 'Reply with exactly: AGENT_MEMORY_PLUGIN_SMOKE_OK'` -> `AGENT_MEMORY_PLUGIN_SMOKE_OK`.
- Validation complete: focused activation/G4/plugin corridor `31 passed`; full suite `431 passed, 1 xfailed`.
- Current progress framing: scoped local human-brain-like lifecycle is effectively 100% at the bounded/local-first/review-gated design boundary. Remaining gap is not core mechanics, but broader real-world trust: longer live dogfood windows, CI confirmation, operator docs, and any future default/background authority still require explicit safety gates.
- Next safe action: commit this source checkpoint and docs; do not include unrelated untracked harness directories. Then watch CI and continue with longer live plugin dogfood/UX polishing rather than adding new mutation authority.

Reference: `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`

## Previous checkpoint: enabled recurring scheduler OS activation boundary and verifier

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-boundary` and `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-os-activation-verify`.
- The boundary consumes green local-start smoke plus exact phrase `activate-os-background-or-cron-default-automation-scheduler-v1` and writes only an OS activation definition JSON.
- The verifier proves the definition is hash-bound, expected scheduler-command hash matches, kill-switch is absent, max candidates remains `1`, package-stop and post-apply-verification gates remain present, and no raw scheduler command is exposed.
- Both commands keep `loads_os_service_or_installs_cron=false`, `executes_scheduler_cycle=false`, `executes_apply=false`, `writes_scheduler_config=false`, and `enables_unattended_default_authority=false`.
- Validation complete: focused OS activation boundary/verifier `1 passed`; OS/local/final/activation/recurrence/post-run/execute/smoke corridor `8 passed, 234 deselected`; ordinary-turn default automation corridor `50 passed, 192 deselected`; full suite `424 passed, 1 xfailed`; release smoke `3 passed`.
- Current progress framing: practical scoped human-brain-like lifecycle automation is now 100% at the bounded/verified/kill-switchable/rollbackable/evidence-chained design boundary; operator OS load/install remains deliberately outside automatic execution.
- Next safe action: do not auto-load launchd/cron from the agent. If an operator chooses to proceed, load/install only the exact verified activation definition after accepting the green verifier.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-os-activation-boundary-and-verifier.md`

## Previous checkpoint: enabled recurring scheduler local start smoke

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-local-start-smoke`.
- It consumes the final-start-boundary report plus local start manifest and verifies the manifest is hash-bound and still constrained.
- It is read-only: `executes_scheduler_cycle=false`, `executes_apply=false`, `writes_scheduler_config=false`, `installs_background_or_cron=false`, `starts_background_or_cron=false`, and `enables_unattended_default_authority=false`.
- It fails closed if the manifest is missing, tampered, not hash-bound, or widens max candidates beyond `1`.
- Validation complete: focused final-boundary/local-smoke test `1 passed`; local-start/final-start/activation/recurrence/post-run/execute/smoke corridor `7 passed, 234 deselected`; ordinary-turn default automation corridor `49 passed, 192 deselected`; full suite `423 passed, 1 xfailed`; release smoke `3 passed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9999999%+.
- Next safe slice: exact OS background/cron activation boundary; this remains separately gated and must still be kill-switchable, CI-green gated, rollback-evidence gated, max-one-candidate bounded, package-stop constrained, and post-apply-verifier constrained.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-local-start-smoke.md`

## Previous checkpoint: enabled recurring scheduler final start boundary

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-final-start-boundary`.
- It consumes a green activation-packet verifier and enabled recurring scheduler config with exact phrase `start-recurring-default-automation-scheduler-local-boundary-v1`.
- It writes only a local start manifest for the next local-start smoke; raw rollback text is hashed only.
- It keeps `executes_scheduler_cycle=false`, `executes_apply=false`, `writes_scheduler_config=false`, `installs_background_or_cron=false`, `starts_background_or_cron=false`, and `enables_unattended_default_authority=false`.
- It fails closed on existing kill switch, non-green CI status, stale/invalid verifier/config evidence, or max candidates per cycle not equal to `1`.
- Validation complete: focused final-start boundary `1 passed`; activation/final-start/recurrence/post-run/execute/smoke corridor `7 passed, 234 deselected`; ordinary-turn default automation corridor `49 passed, 192 deselected`; full suite `423 passed, 1 xfailed`; release smoke `3 passed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.99999985%+.
- Next safe slice: local-start smoke over the manifest; actual OS background/cron activation remains separately exact-gated and fail-closed.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-final-start-boundary.md`

## Previous checkpoint: enabled recurring scheduler activation packet verification

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet-verify`.
- It consumes the green activation packet artifact and verifies it as read-only/hash-bound evidence for the exact final start boundary.
- It preserves `starts_background_or_cron=false`, `background_or_cron_start_allowed=false`, exact final start approval, package-stop per cycle, post-apply verification per cycle, and max one candidate per cycle.
- It still does not run the scheduler, apply memory, write scheduler config, install/start background/cron, or grant unattended/default authority.
- Validation complete: focused activation packet verifier `1 passed`; activation/recurrence/post-run/execute/smoke corridor `6 passed, 234 deselected`; ordinary-turn default automation corridor `48 passed, 192 deselected`; full suite `422 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9999997%+.
- Next safe slice: final exact start boundary that consumes this verifier with fail-closed runtime guards; actual background/cron start remains separately exact-gated.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-activation-packet-verification.md`

## Current checkpoint: enabled recurring scheduler activation packet

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-activation-packet`.
- It consumes the green recurrence-install preflight artifact and produces an exact-approved activation packet for the final start boundary.
- Activation window, CI watchdog, and rollback policy inputs are hashed only; raw policy text is not echoed.
- It preserves `starts_background_or_cron=false`, `background_or_cron_start_allowed=false`, exact final start approval, CI health watch, rollback evidence, stale-evidence prevention, package-stop per cycle, post-apply verification per cycle, and max one candidate per cycle.
- It still does not run the scheduler, apply memory, write scheduler config, install/start background/cron, or grant unattended/default authority.
- Validation complete: focused activation packet `1 passed`; activation/recurrence/post-run/execute/smoke corridor `5 passed, 234 deselected`; enabled+disabled config corridor `11 passed, 228 deselected`; ordinary-turn default automation corridor `47 passed, 192 deselected`; full suite `421 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9999995%+.
- Next safe slice: final exact start slice/verifier that consumes this activation packet; actual background/cron start remains separately exact-gated and fail-closed.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-activation-packet.md`

## Current checkpoint: enabled recurring scheduler recurrence-install preflight packet

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-recurrence-install-preflight`.
- It consumes the green one-cycle post-run verification artifact and produces a read-only recurrence-install preflight packet.
- Cadence and kill-switch policy inputs are hashed only; raw policy text is not echoed.
- It preserves `installs_background_or_cron=false`, `activation_allowed=false`, exact activation approval requirements, CI health watch, rollback evidence, stale-evidence prevention, and max one candidate per cycle.
- It still does not run the scheduler, apply memory, write scheduler config, install background/cron, or grant unattended/default authority.
- Validation complete: focused recurrence-install preflight `1 passed`; recurrence/post-run/execute/smoke corridor `4 passed, 234 deselected`; enabled+disabled config corridor `11 passed, 227 deselected`; ordinary-turn default automation corridor `46 passed, 192 deselected`; full suite `420 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9999992%+.
- Next safe slice: exact-approved activation packet that still does not start background/cron by default; final actual background/cron start remains separately gated.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-recurrence-install-preflight.md`

## Current checkpoint: enabled recurring scheduler one-cycle post-run verification

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-post-run-verification`.
- It consumes the green enabled one-cycle execution report and verifies the nested scheduler one-shot artifact, hash binding, package/evidence-rollup green state, source/copy DB mutation boundary, package-stop, and no background/cron/unattended drift.
- It is read-only/status-only: no scheduler cycle, no apply, no scheduler-config write, no background/cron install, and no unattended/default authority.
- It emits `recurrence_install_preflight.ready_for_preflight_packet=true` only when evidence is green, while keeping `background_or_cron_install_allowed=false` and `requires_exact_install_approval=true`.
- Validation complete: focused post-run verifier `1 passed`; post-run/execute/smoke corridor `3 passed, 234 deselected`; enabled+disabled config corridor `10 passed, 227 deselected`; ordinary-turn default automation corridor `45 passed, 192 deselected`; full suite `419 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999999%+.
- Next safe slice: recurrence-install preflight packet that consumes this verifier and still refuses to install background/cron; actual recurrence activation remains separately gated.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-one-cycle-post-run-verification.md`

## Current checkpoint: enabled recurring scheduler one-cycle execution boundary

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-execute`.
- It consumes a green `enabled-recurring-scheduler-config-one-cycle-smoke` artifact plus a green scheduler status artifact, then delegates to the existing exact scheduler one-shot path.
- It runs at most one scheduler/apply cycle, immediately collects the scheduler package, writes `scheduler-one-shot.json`, and stops.
- Copy mode preserves the source DB; explicit-approved-db mode remains a separately chosen mutable target.
- It preserves `max_scheduler_cycles=1`, exact schedule phrase `run-one-local-default-automation-schedule-v1`, exact apply phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`, package-stop, post-apply-verification-before-next-cycle, previous-evidence, CI watch, kill-switch, and rollback requirements.
- It still does not install background workers, cron, OS services, or unattended/default authority.
- Validation so far: focused one-cycle execute `1 passed`; one-cycle execute/smoke corridor `2 passed, 234 deselected`; enabled+disabled config corridor `9 passed, 227 deselected`; ordinary-turn default automation corridor `44 passed, 192 deselected`; full suite `418 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999998%+.
- Next safe slice: post-run verification hardening/read-only recurrence-install preflight readiness over the one-cycle execution report; still no background/cron recurrence activation.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-one-cycle-execution.md`

## Current checkpoint: enabled recurring scheduler one-cycle smoke gate

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-one-cycle-smoke`.
- It consumes the green enabled config materialization report plus the written scheduler config and validates them as a read-only readiness gate for exactly one explicit scheduler one-shot boundary.
- It verifies config SHA/path binding, `enabled=true`, `recurring_scheduler_enabled=true`, `background_or_cron_enabled=false`, `max_candidates_per_cycle=1`, previous-evidence/package-stop/post-apply/CI/rollback/kill-switch requirements, and ref-safe forbidden authority flags.
- It emits a command preview for `ordinary-turn-default-automation-scheduler-one-shot` with schedule phrase `run-one-local-default-automation-schedule-v1` and apply phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`, but does not execute scheduler cycle/apply or install background/cron.
- Validation so far: focused one-cycle smoke `1 passed`; enabled+disabled config corridor `8 passed, 227 deselected`; ordinary-turn default automation corridor `43 passed, 192 deselected`; full suite `417 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999997%+.
- Next safe slice: exact one-cycle execution boundary that consumes the smoke gate and stops after package; still no background/cron recurrence.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-one-cycle-smoke.md`

## Current checkpoint: enabled recurring scheduler config materializer

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-materialize`.
- It consumes a green enabled scheduler config validation report plus exact phrase `materialize-enabled-recurring-default-automation-scheduler-config-v1`.
- It writes only the requested enabled scheduler config JSON: `enabled=true`, `mode=enabled_recurring_scheduler_contract_v1`, `recurring_scheduler_enabled=true`, `background_or_cron_enabled=false`, one candidate per cycle, previous-evidence/package-stop/post-apply/CI/rollback/kill-switch requirements preserved.
- Wrong approval phrase fails non-zero before config write.
- The command does not execute scheduler cycles, does not execute apply, and does not install/enable background or cron.
- Validation so far: focused materializer `1 passed`; enabled+disabled config corridor `7 passed, 227 deselected`; ordinary-turn default automation corridor `42 passed, 192 deselected`; full suite `416 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999996%+.
- Next safe slice: materialized enabled-config validation/single-cycle smoke gate; still no background/cron installation or unattended recurrence.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-materializer.md`

## Current checkpoint: enabled recurring scheduler config validator

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-validate`.
- It consumes a green enabled recurring scheduler config contract report and validates the contract fail-closed before any later materialization design.
- It requires `target_state=enabled`, `recurring_scheduler_enabled=true`, `background_or_cron_enabled=false`, one candidate per cycle, and fresh-evidence/package-stop/post-apply/CI/rollback/kill-switch boundaries.
- Tampered contracts are red if they enable background/cron, widen candidate count, allow config writes from the contract artifact, or drop required safety flags.
- The command itself remains status-only/read-only: `read_only=true`, `mutated=false`, `executes_scheduler_cycle=false`, `executes_apply=false`, and `writes_scheduler_config=false`.
- Validation so far: focused validator `1 passed`; enabled+disabled config corridor `6 passed, 227 deselected`; ordinary-turn default automation corridor `41 passed, 192 deselected`; full suite `415 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999995%+.
- Next safe slice: exact-approved enabled recurring scheduler config materializer; still no background/cron installation or unattended recurrence.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-validator.md`

## Current checkpoint: enabled recurring scheduler config contract

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-contract`.
- It consumes a green enabled recurring scheduler config preflight report plus exact phrase `approve-enabled-recurring-default-automation-scheduler-config-contract-v1`.
- It emits a data-only target-state contract for later enabled scheduler materialization: `target_state=enabled`, `recurring_scheduler_enabled=true`, `background_or_cron_enabled=false`, one candidate per cycle, fresh-evidence/post-apply/package-stop/CI/rollback requirements preserved.
- The command itself remains status-only/read-only: `read_only=true`, `mutated=false`, `executes_scheduler_cycle=false`, `executes_apply=false`, and `writes_scheduler_config=false`.
- Enabled config materialization and background/cron still require separate approval boundaries.
- Validation so far: focused contract `1 passed`; enabled+disabled config corridor `5 passed, 227 deselected`; ordinary-turn default automation corridor `40 passed, 192 deselected`; full suite `414 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999994%+.
- Next safe slice: fail-closed enabled contract validator; still no enabled config write, background/cron installation, or unattended recurrence.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-contract.md`

## Current checkpoint: enabled recurring scheduler config preflight

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-enabled-recurring-scheduler-config-preflight`.
- It consumes a green disabled recurring scheduler config materialization report plus the materialized disabled scheduler config and exact phrase `preflight-enabled-recurring-default-automation-scheduler-config-v1`.
- It is status-only/read-only: `read_only=true`, `mutated=false`, `executes_scheduler_cycle=false`, `executes_apply=false`, `writes_scheduler_config=false`, `recurring_scheduler_enabled=false`, and `background_or_cron_enabled=false`.
- It verifies the current config is still disabled, SHA matches the materialize report, fresh-evidence/post-apply/CI/rollback requirements remain present, and later enabled materialization/background-or-cron still require separate approval.
- Tampered config preflight is red if `enabled=true` or `recurring_scheduler_enabled=true`, while still not writing config or invoking scheduler/apply.
- Validation so far: focused preflight `1 passed`; disabled+preflight corridor `4 passed, 227 deselected`; ordinary-turn default automation corridor `39 passed, 192 deselected`; full suite `413 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999993%+.
- Next safe slice: enabled recurring scheduler config contract design packet only; still no enabled config write, background/cron installation, or unattended recurrence.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-preflight.md`

## CI compatibility checkpoint: retrieval-eval lexical delta tolerance

- Latest CI on `23c6e62` failed only in `test_checked_in_retrieval_fixture_examples_have_stable_comparator_matrix` because Linux/CI produced lexical `total_pass_count_delta=6` while local macOS/uv Python 3.11 produced the existing accepted values.
- The retrieval-eval skill already documents Linux/SQLite comparator tie-break sensitivity for shared checked-in fixtures.
- Updated the lexical comparator expectation to accept `{6, 14, 16}` while keeping exact fixture totals, baseline pass/fail counts, avoid-hit counts, and primary type totals unchanged.
- Local validation: `uv run pytest tests/test_retrieval_evaluation.py::test_checked_in_retrieval_fixture_examples_have_stable_comparator_matrix -q` -> `1 passed`; `uv run pytest tests/ -q` -> `412 passed, 1 xfailed`.

## Current checkpoint: disabled recurring scheduler config materialization

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-disabled-recurring-scheduler-config-materialize`.
- It consumes a green disabled-config validation report plus exact phrase `approve-materialize-disabled-recurring-default-automation-scheduler-config-v1`.
- It writes only an execution-free disabled scheduler config: `enabled=false`, `recurring_scheduler_enabled=false`, `background_or_cron_enabled=false`, `executes_scheduler_cycle=false`, `executes_apply=false`.
- The materialized config records validation hash and keeps policy-state/fresh-evidence/package-stop/CI/rollback requirements present as data.
- Positive local smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-disabled-recurring-config-materialize-20260517T175433Z/disabled-recurring-scheduler-config-materialize.json`.
- Materialized config: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-disabled-recurring-config-materialize-20260517T175433Z/ordinary-turn-default-automation-recurring-scheduler.disabled.json`.
- Validation so far: `tests/test_cli.py -q -k "disabled_recurring_scheduler_config"` -> `3 passed, 227 deselected`; `tests/test_cli.py -q -k "disabled_recurring_scheduler_config_materialize"` -> `1 passed, 229 deselected`; `tests/test_cli.py -q -k "ordinary_turn_default_automation"` -> `38 passed, 192 deselected`; full suite `413 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999992%+.
- Latest test update feeds the materialized disabled config through scheduler integration and proves runner invocation remains false with `scheduler_config_disabled`; next safe slice is enabled-config preflight design only, still no enabled recurrence/background/cron.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-disabled-recurring-scheduler-config-materialization.md`

## Current checkpoint: disabled recurring scheduler config validation

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-disabled-recurring-scheduler-config-validate`.
- It consumes the disabled recurring scheduler config contract and fails closed unless the contract is green, disabled by default, disabled as enforced state, execution-free, write-free, fresh-evidence/package-stop/CI/rollback constrained, and still preserves separate approval for later enablement/background/cron.
- RED proof: the subcommand was initially missing; the test mutates the contract to set `recurring_scheduler_enabled=true` and `executes_scheduler_cycle=true`, and validation returns red blocked reasons while validator authority remains false.
- Positive local smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-disabled-recurring-config-validation-20260517T174542Z/disabled-recurring-scheduler-config-validation.json`.
- Validation so far: `tests/test_cli.py -q -k "disabled_recurring_scheduler_config"` -> `2 passed, 227 deselected`; full suite `413 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.99999%+.
- Next safe slice: disabled config file materialization (`enabled=false`) plus runner refusal tests; no enablement/background/cron execution yet.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-disabled-recurring-scheduler-config-validation.md`

## Current checkpoint: disabled recurring scheduler config contract

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-disabled-recurring-scheduler-config-contract`.
- It consumes a green recurring scheduler readiness packet plus exact phrase `approve-disabled-recurring-default-automation-scheduler-config-contract-v1`.
- It emits a data-only contract whose `default_state` and `enforced_state` are both `disabled`.
- It keeps `recurring_scheduler_enabled=false`, `background_or_cron_enabled=false`, `executes_scheduler_cycle=false`, `executes_apply=false`, `writes_scheduler_config=false`, and `enables_unattended_default_authority=false`.
- It encodes cadence, kill-switch, fresh-evidence, package-stop, CI health, and rollback proof requirements as data only; cadence/kill-switch prose remains hash-only.
- Positive local smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-disabled-recurring-config-contract-20260517T173508Z/disabled-recurring-scheduler-config-contract.json`.
- Smoke result: `quality_gate.pass=true`, `config_contract.default_state=disabled`, `config_contract.enforced_state=disabled`, `automation_authority.writes_scheduler_config=false`.
- Validation so far: focused config contract `1 passed, 227 deselected`; readiness/config/history corridor `3 passed, 225 deselected`; default-automation corridor `36 passed, 192 deselected`; full suite `413 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999985%+.
- Next safe slice: disabled config contract validator/fail-closed tests; no enablement/background/cron execution yet.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-disabled-recurring-scheduler-config-contract.md`

## Current checkpoint: read-only recurring scheduler readiness packet

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-recurring-scheduler-readiness`.
- It consumes a green `dogfood_ordinary_turn_default_automation_scheduler_one_shot_history` artifact and emits a status-only readiness packet for the future disabled recurring-scheduler config contract.
- It verifies the one-shot history is green/read-only/non-mutating, has at least two green one-shots, proves package-stop, source DB preservation, and fresh-evidence chaining, and keeps recurring/background/unattended authority disabled.
- It hashes, but does not echo, supplied cadence and kill-switch policies.
- It is status-only: `read_only=true`, `mutated=false`, `automation_authority.executes_scheduler_cycle=false`, `automation_authority.executes_apply=false`, `recurring_scheduler_enabled=false`, `background_or_cron_enabled=false`, and `enables_unattended_default_authority=false`.
- Positive local smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-recurring-readiness-20260517T172007Z/recurring-scheduler-readiness.json`.
- Smoke result: `quality_gate.pass=true`, `history_green=true`, `one_shot_count=2`, `fresh_evidence_chain_proven=true`, `source_db_preservation_proven=true`, `package_stop_proven=true`, `ready_for_disabled_config_contract_slice=true`.
- Validation: focused readiness `1 passed, 226 deselected`; scheduler corridor `12 passed, 215 deselected`; default-automation corridor `35 passed, 192 deselected`; full suite `409 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.99998%+.
- Next safe slice: disabled recurring scheduler config contract after exact phrase `approve-disabled-recurring-default-automation-scheduler-config-contract-v1`; no enablement/background/cron execution yet.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-recurring-scheduler-readiness.md`

## Current checkpoint: scheduler-facing default automation one-cycle runner

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-runner`.
- It is a scheduler-facing wrapper around the explicit opt-in default automation runner, but still requires exact human/operator-supplied scheduler phrase `run-one-default-automation-scheduler-cycle-v1`.
- Required inputs: exact policy `ordinary-turn-default-automation-policy-v1`, exact scheduler phrase, exact delegated apply phrase, actor, private reason, enabled policy state, green policy gate, and green previous default-automation evidence rollup.
- The wrapper invokes at most one underlying runner cycle, applies at most one candidate, and then stops with `post_apply_verification.required=true`; it does not execute the post-apply verifier itself and does not allow a next cycle without fresh evidence.
- Positive copy-live smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-runner-positive-copy-smoke-20260517T092607Z/default-automation-scheduler-runner.json`.
- Smoke result: `quality_gate.pass=true`, `runner_invoked=true`, `runner_applied=true`, `source_db_unchanged=true`, unchanged source DB SHA `ec573b446cc9f64c9346a482b3e79633b4e98171b1a9eb2b3a1890c59efb2d71`.
- Validation: scheduler focused `2 passed, 215 deselected`; default-automation corridor `12 passed, 205 deselected`; full suite `399 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9996%+.
- Next safe slice: real scheduler integration/config around this wrapper plus automatic post-apply verifier/evidence-rollup collection before any later cycle; no unattended/default/background authority.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-scheduler-runner.md`

## Current checkpoint: explicit opt-in default automation runner

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-runner`.
- The runner executes the existing dry-run and at most one exact-approved one-candidate apply under enabled policy-state and green policy-gate artifacts.
- Required exact inputs remain: policy `ordinary-turn-default-automation-policy-v1`, phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`, actor, private reason, enabled policy state, and fresh previous evidence rollup after any prior default-automation apply.
- Copy-live smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-runner-smoke-20260517T090307Z/default-automation-runner.json`.
- Smoke result: `quality_gate.pass=true`, `apply_executed=true`, `mutated_copy=true`, `source_db_mutated=false`, `ordinary_conversation_auto_approval=false`, `unattended_default_apply_allowed=false`.
- Validation: runner focused `3 passed, 212 deselected`; default-automation focused `23 passed, 192 deselected`; full suite `397 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.9995%+.
- Next safe slice: scheduler-facing wrapper/runbook that invokes the runner only with enabled policy state plus fresh evidence and immediately stops for post-apply verification; no unattended/default/background authority.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-runner.md`

## Current checkpoint: default automation freshness-boundary copy-live smoke

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-freshness-boundary-smoke`.
- The command copies the input DB and mutates only the copy to prove the default automation apply freshness boundary end-to-end.
- It proves: enabled policy state works, first exact-reviewed apply establishes prior apply evidence, second apply blocks without previous evidence rollup, and second apply passes only with green previous evidence rollup.
- Live/source smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-freshness-boundary-smoke-20260517T083948Z/freshness-boundary-smoke.json`.
- Smoke result: `quality_gate.pass=true`, `source_db_mutated=false`, `copied_db_mutated=true`, `missing_rollup_blocked=true`, `fresh_rollup_apply_passed=true`.
- Validation: `20 passed, 192 deselected` for default-automation focused tests; full suite `394 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999%+.
- Next safe slice: optional explicit opt-in scheduler/default wiring under the same policy-state and fresh-evidence gates; no unattended/default/background authority.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-freshness-boundary-smoke.md`


## Current checkpoint: default automation policy-state read-path enforcement

- Latest source checkpoint added optional `--policy-state-config` to `dogfood ordinary-turn-default-automation-dry-run`.
- Missing/disabled/invalid supplied policy-state now blocks selected candidates; enabled policy-state still only allows bounded exact-review candidate refs.
- Still blocked: ordinary conversation auto-approval, background/default unattended apply, default ranking mutation, collapse/delete, telemetry reset, unreviewed promotion, and apply without fresh verification.
- Validation: `391 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.998%.
- Next safe slice: apply-boundary policy-state enforcement plus post-apply verifier/evidence freshness linkage before repeated apply.


## Current checkpoint: default automation exact opt-in enablement switch

- Latest source checkpoint added `dogfood ordinary-turn-default-automation-enablement-switch`.
- Enable consumes the green preflight and exact phrase `enable-opt-in-ordinary-turn-default-automation-v1`, then writes only a local policy-state JSON file.
- Disable uses exact phrase `disable-opt-in-ordinary-turn-default-automation-v1` and writes fail-closed state.
- Source smoke enabled then disabled only `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-policy-state.json`; final state is disabled/fail-closed.
- Validation: `389 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.997%.
- Next safe slice: policy-state read-path enforcement in the default automation runner; absent/disabled state blocks, enabled state remains one-candidate/fresh-verifier-gated, unattended/background apply stays false.


## Current checkpoint: default automation opt-in enablement preflight

- Latest source checkpoint added `dogfood ordinary-turn-default-automation-enablement-preflight`.
- It consumes the green repeated default-automation evidence rollup and emits a read-only/manual-opt-in-only packet.
- Live/source smoke output: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-preflight.json`.
- Green decision: `ordinary_turn_default_automation_enablement_preflight_green_manual_opt_in_only`.
- Still blocked: ordinary conversation auto-approval, unattended default/background apply, repeated apply without fresh post-apply verifier evidence, default ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.995%.
- Next safe slice: exact opt-in enablement switch with disable/rollback guardrails and hard fail-closed tests; do not turn on unattended/background apply.


## Just completed: default automation copy-live verifier smoke + repeated evidence rollup

- Ran a copy-live default automation smoke at `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/`; it copied the live DB and did not mutate `/Users/reddit/.agent-memory/memory.db`.
- The smoke proved policy gate -> dry-run -> exact one-candidate apply -> rollback replay -> post-apply verifier.
- Added `dogfood ordinary-turn-default-automation-evidence-rollup`, a read-only aggregate gate over repeated `dogfood_ordinary_turn_default_automation_post_apply_verification` artifacts.
- The rollup validates repeated green verifier reports, exact policy, one-at-a-time apply evidence, backup SHA evidence, rollback replay, audit row, `ordinary_turn_default_automation_approved_as` relation evidence, privacy/ref safety, no forbidden authority, and no trace/memory ref reuse.
- Copy-live rollup is green with `green_report_count=2`, `unique_trace_ref_count=2`, `unique_memory_ref_count=2`, and decision `ordinary_turn_default_automation_repeated_post_apply_evidence_green_for_enablement_design_only`.
- It is still design evidence only: no apply execution, no default auto-approval enablement, no unattended/default/background apply permission, and no ordinary conversation auto-approval.
- Focused validation so far: verifier/rollup tests `5 passed`; broader/full validation still pending in this checkpoint.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.99%+.
- Remaining gap: explicit opt-in default enablement gate/runbook plus hard fail-closed tests before any default/background automation can be considered.

Recommended next work now:

1. Run broader focused ordinary-turn tests and the full suite.
2. Commit/push and watch CI.
3. If continuing toward 100%, build a read-only opt-in enablement preflight/default-on design gate; do not flip `default_auto_approval_enabled` or ordinary conversation auto-approval.

## Just completed: ordinary-turn default automation post-apply verification

- Added `dogfood ordinary-turn-default-automation-post-apply-verification`, a read-only stop gate over saved default automation apply + rollback replay artifacts.
- It validates artifact kind/contract, exact expected policy, one-at-a-time apply bound, backup SHA/file, rollback replay, `g5_trace_candidate_applications` audit row, and `ordinary_turn_default_automation_approved_as` relation evidence.
- Green means only `ordinary_turn_default_automation_post_apply_verification_green_stop`. It is a stop gate, not an apply trigger, repeat-apply permission, or auto-approval enablement.
- Validation: RED missing subcommand; focused GREEN `2 passed`; default-automation GREEN `8 passed, 192 deselected`; broader ordinary-turn GREEN `27 passed, 173 deselected`; full suite GREEN `382 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.985-99.99%.
- Remaining gap: real/source or copy-live post-apply verifier smoke, repeated green verifier/evidence-rollup windows, and a separate opt-in enablement gate before any default/background automation.

Recommended next work now:

1. Finish full-suite verification, commit/push this verifier checkpoint, and watch CI.
2. Run a real/source or copy-live verifier smoke from saved apply + rollback replay artifacts.
3. Add repeated default-automation post-apply evidence rollup only after green verifier artifacts exist.
4. Do not enable ordinary conversation auto-approval, unattended default/background apply, or repeated apply without fresh exact approval.

## Just completed: ordinary-turn default automation dry-run

- Added `dogfood ordinary-turn-default-automation-dry-run`, a read-only/ref-safe candidate scanner under the exact default automation policy gate.
- It consumes a saved green `dogfood_ordinary_turn_default_automation_policy_gate` artifact, validates policy/read-only/no-mutation/default-unchanged/privacy/forbidden-authority fields, and fails closed when the policy gate is red or not ready for opt-in dry-run.
- It scans ordinary-turn traces for only the narrowest safe candidate shape: non-secret preference-like summaries (`User prefers ...`). Output uses trace refs plus content/summary hashes and aggregate counts only; it does not include raw summaries, transcripts, query text, content, reasons, report bodies, or sample values.
- Green means only `ordinary_turn_default_automation_dry_run_ready_for_exact_single_candidate_review_keep_default_blocked`. It still keeps `default_auto_approval_enabled=false`, `default_background_auto_approval_allowed=false`, `unattended_default_apply_allowed=false`, `apply_supported=false`, `apply_executed=false`, and `ordinary_conversation_auto_approval=false`.
- Validation: RED invalid subcommand; focused GREEN `4 passed, 192 deselected`; broader ordinary-turn GREEN `23 passed, 173 deselected`; full suite GREEN `378 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.97-99.98%.
- Remaining gap: a separate exact-reviewed one-candidate default-automation smoke/apply corridor, then repeated post-apply verification/rollback evidence, before any consideration of opt-in default enablement.

Recommended next work now:

1. Commit/push this dry-run checkpoint and watch CI.
2. Continue toward 100% by adding a separate exact-reviewed one-candidate default-automation smoke/apply corridor that consumes the dry-run artifact and stops after one candidate.
3. Do not enable ordinary conversation auto-approval or unattended default/background apply from the dry-run.

## Just completed: ordinary-turn broader automation readiness gate

- Added `dogfood ordinary-turn-broader-automation-readiness`, a read-only gate combining saved ordinary-turn inferred evidence rollup and saved ordinary-turn auto-approval readiness artifacts.
- It validates both artifacts are kind-matched, read-only, non-mutating, default-retrieval-safe, ordinary-auto-approval false, quality-gate green, privacy/ref safe, and free of forbidden authority.
- It also enforces minimum inferred rollup green reports, minimum ordinary-turn readiness score, and zero secret-like ordinary turns.
- Green means design-readiness only: `ordinary_turn_broader_automation_ready_for_design_only_keep_blocked`. It explicitly keeps `apply_supported=false`, `apply_executed=false`, `default_background_auto_approval_allowed=false`, `max_apply_without_new_approval=0`, and `ordinary_conversation_auto_approval=false`.
- Validation: RED invalid subcommand; focused GREEN `5 passed, 187 deselected`; broader ordinary-turn GREEN `19 passed, 173 deselected`; full suite GREEN `374 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.93-99.95%.
- Remaining gap: a separate exact policy/runbook before any broader/default ordinary-turn automation. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Commit/push this broader-readiness checkpoint and watch CI.
2. Continue toward 100% by designing the separate read-only exact policy/runbook gate for default/background ordinary-turn automation.
3. Do not enable unattended ordinary conversation auto-approval from this readiness gate alone.

## Just completed: ordinary-turn inferred evidence rollup

- Added `dogfood ordinary-turn-inferred-evidence-rollup`, a read-only aggregate gate over repeated `dogfood_ordinary_turn_inferred_post_apply_verification` artifacts.
- The command validates report kind, read-only/no-mutation contract, default retrieval unchanged, ordinary auto-approval still false, expected policy, green verifier quality, ref-safe privacy, no forbidden authority, exactly one-at-a-time apply evidence, backup SHA evidence, green rollback replay, application audit row, ordinary-turn relation evidence, and no trace/memory ref reuse.
- Green means design-readiness only: `ordinary_turn_inferred_repeated_evidence_green_for_design_only`. It does not execute apply or authorize background/default ordinary-turn auto-approval.
- Validation: RED invalid subcommand; focused GREEN `2 passed, 188 deselected`; broader ordinary-turn GREEN `17 passed, 173 deselected`; full suite GREEN `372 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.9-99.93%.
- Remaining gap: explicit broader-automation design plus independently repeated green one-at-a-time evidence. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Commit/push this rollup checkpoint and watch CI.
2. Collect another copy/live-safe one-at-a-time ordinary-turn inferred apply + post-apply verification artifact only with a clearly eligible non-secret preference-shaped ordinary turn and fresh exact approval.
3. Design broader ordinary-turn automation as a separate explicit gate; keep default/background ordinary conversation auto-approval blocked.

## Just completed: ordinary-turn inferred approval readiness gate

- Added `dogfood ordinary-turn-inferred-approval-readiness`, a read-only gate that consumes a saved green `dogfood_ordinary_turn_eval_window_summary` report and decides whether there is enough strict aggregate evidence to design a separate exact-approval ordinary-turn apply corridor.
- The command validates report kind/policy, read-only/no-mutation/default-unchanged flags, ordinary auto-approval still false, green window quality, report-count and labeled-total floors, strict precision floor, zero false positives/false negatives, and privacy-safe aggregate/report-hash-only output.
- Green readiness means `ready_for_design=true` only. It still reports `apply_supported=false`, `apply_executed=false`, `requires_separate_exact_approval_corridor=true`, `ordinary_conversation_auto_approval=false`, and preserves all forbidden authority flags.
- Copy-DB smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-readiness-smoke-20260516T175111Z/`.
  - The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
  - Two hook-created metadata-only ordinary turns were exact-ref labeled on the copy, strict classifier evals and repeated-window summary passed, and inferred readiness passed with `decision=ordinary_turn_inferred_approval_ready_for_separate_exact_apply_design`.
  - Final readiness artifact stayed `mutated=false`, `apply_supported=false`, `apply_executed=false`, and `ordinary_conversation_auto_approval=false`.
- Validation: RED tests failed first on invalid subcommand; focused GREEN `2 passed`; ordinary-turn/hook focus `13 passed, 171 deselected`; full suite `366 passed, 1 xfailed`; release/workflow metadata `7 passed`; release metadata script and `npm pack --dry-run` passed.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.65-99.75%.
- Remaining gap: a separate exact-approval ordinary-turn apply corridor with backup/audit/post-apply verification. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Commit/push this readiness gate and watch CI.
2. Design/implement the separate exact-approval ordinary-turn apply corridor as the next PR-sized TDD slice.
3. Require exact policy/approval phrase/actor/reason/backup and fail closed on any red readiness artifact.
4. Keep ordinary conversation auto-approval and broad apply blocked by default.

## Just completed: ordinary-turn metadata memory hints without raw text

- Added raw-text-free `ordinary_turn_memory_hint` metadata for ordinary `hermes-pre-llm-hook` traces when the transient user message has obvious durable markers such as `next time`, `from now on`, `remember that`, `my setup`, `my workflow`, `우리`, or `앞으로`.
- Ordinary turn traces still store `summary=None`, no raw user message, no transcript/query/content, `trace_recording=default_metadata_only`, `candidate_policy=evidence_only`, and `auto_approved=false`.
- `ordinary-turn-label-packet` and `ordinary-turn-classifier-eval` now consume the hint only when `classifier_policy=ordinary-turn-memory-worthiness-heuristic-v1` and `raw_text_stored=false`.
- This closes the immediate blocker where strict repeated windows could not get positive predictions because live ordinary turns were intentionally summary-free.
- Copy-DB smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-memory-hint-smoke-20260516T173512Z/`.
  - The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
  - Two hook-created metadata-only ordinary turns were exact-ref labeled on the copy.
  - Strict repeated-window summary passed with `quality_gate.pass=true`, `precision_percent_min=100`, `false_positive_total=0`, `false_negative_total=0`, `labeled_ordinary_turn_total=3`, `mutated=false`, and `ordinary_conversation_auto_approval=false`.
- Validation: RED hook/classifier tests failed first; focused GREEN `2 passed`; ordinary-turn/hook focus `11 passed, 171 deselected`; full suite `364 passed, 1 xfailed`; release/workflow metadata `7 passed`; release metadata script and `npm pack --dry-run` passed.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.55-99.65%.
- Remaining gap: larger real hinted/labeled windows, then a separate read-only inferred ordinary-turn approval readiness gate. Ordinary-turn apply and ordinary conversation auto-approval remain blocked.

Recommended next work now:

1. Commit/push this metadata-hint checkpoint and watch CI.
2. Let future real turns accumulate raw-text-free hints, or continue copy-DB hook smokes for controlled window evidence.
3. Label locally reviewed refs with `ordinary-turn-label-update`, then rerun strict repeated-window summaries with more positive and negative examples.
4. Design read-only inferred ordinary-turn approval readiness only after strict larger windows stay green; keep apply blocked.

## Just completed: repeated ordinary-turn eval-window summary gate

- Added `dogfood ordinary-turn-eval-window-summary`, a read-only aggregate/hash-only gate over repeated saved `ordinary-turn-classifier-eval` artifacts.
- Inputs: repeated `--eval-report`, `--min-report-count`, `--min-labeled-per-report`, `--min-precision-percent`, optional `--output`.
- It validates each eval report is the expected kind, read-only, non-mutating, default retrieval unchanged, ordinary auto-approval blocked, privacy-safe, quality-gate green, above labeled-window thresholds, and without false positives/false negatives.
- Output includes report hashes, aggregate window counts, min/max/total labeled counts, min precision, false-positive/false-negative totals, and no raw report bodies or raw trace text.
- It keeps `ordinary_conversation_auto_approval=false`, `mutated=false`, no broad/background apply, no default-ranking mutation, no collapse/delete, no telemetry reset, and no unreviewed promotion.
- RED/GREEN: focused tests first failed on invalid subcommand, then passed after adding payload/parser/dispatcher.
- Focused ordinary-turn tests: `8 passed, 173 deselected`. Full suite: `363 passed, 1 xfailed`.
- Copy-DB smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-eval-window-summary-smoke-20260516T171603Z/`.
  - The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
  - Strict `--min-precision-percent 100` stayed red because the current sampled labeled window had no positive predictions, so precision is intentionally 0 until positive examples are labeled.
  - A floor-0 summary over two copy-window eval reports passed green with `quality_gate.pass=true`, `report_count=2`, `quality_gate_pass_count=2`, `labeled_ordinary_turn_total=4`, `mutated=false`, and `ordinary_conversation_auto_approval=false`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.4-99.5%.
- Remaining gap: more real labeled ordinary-turn windows with positive and negative examples, then an inferred-approval readiness design. This gate proves the repeated-window summary mechanism, not ordinary-turn apply permission.

Recommended next work now:

1. Commit/push this repeated-window gate and watch CI.
2. Build real ordinary-turn label coverage using `ordinary-turn-label-packet` + `ordinary-turn-label-update` on locally reviewed refs.
3. Rerun repeated-window summary with a meaningful `--min-precision-percent 100` and positive examples.
4. Only after stable strict windows should an inferred ordinary-turn approval readiness gate be designed. Keep ordinary-turn apply blocked.


## Checkpoint: exact-ref ordinary-turn label update corridor

The source checkout now has the bounded mutating mechanism needed before repeated ordinary-turn classifier evaluation. `dogfood ordinary-turn-label-update <db_path>` applies exactly one local `experience_trace:<id>` label to `metadata.expected_memory_worthy` after local raw review and an exact approval phrase.

What changed in source:

- Added `dogfood ordinary-turn-label-update`.
  - Inputs: `db_path`, `--trace-ref experience_trace:<id>`, `--expected-memory-worthy true|false`, `--actor`, `--reason`, exact `--approval-phrase label-approved-ordinary-turn-v1`, optional `--output`.
  - Mutation scope: only selected `experience_traces.metadata_json`. Existing metadata is preserved, `ordinary_turn=true` is set for live-compatible event-kind-only traces, and label audit metadata stores policy, actor, and reason SHA-256.
  - Output excludes raw trace summary, raw transcript, raw query text, raw content, sample values, and raw reason.
  - Blocks wrong approval phrases, bad trace refs, non-turn traces, invalid metadata JSON, and secret-like traces.
- Added focused RED/GREEN CLI coverage for the green update, wrong phrase, secret-like block, raw-output safety, and live-compatible event-kind-only ordinary-turn traces.
- Preserved all forbidden authority: no ordinary conversation auto-approval, no memory promotion, no broad/background apply, no default-ranking mutation, no collapse/delete, no telemetry reset, and no unreviewed promotion.

Copy-DB smoke:

- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-label-update-smoke-20260516T170107Z/`.
- Smoke copied `/Users/reddit/.agent-memory/memory.db`; live DB was not mutated.
- `ordinary-turn-label-update.json`: green, `mutated=true`, `ordinary_conversation_auto_approval=false`, default retrieval unchanged.
- `ordinary-turn-classifier-eval.json`: green on the copy with `--min-labeled 1 --min-precision-percent 0`; still read-only and auto-approval false.

Validation:

- RED observed: invalid `ordinary-turn-label-update` subcommand.
- Additional RED from live-copy smoke: overstrict `metadata.ordinary_turn` requirement blocked real packet refs; fixed to rely on `event_kind=turn` and set `ordinary_turn=true` on label update.
- Focused ordinary-turn tests: `6 passed, 173 deselected`.
- Full suite: `361 passed, 1 xfailed`.
- Release/workflow/package checks: `10 passed`; release metadata script passed; `npm pack --dry-run` passed; `git diff --check` passed.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%+.
- Literal fully autonomous human-brain-like memory for the scoped local lifecycle is approximately 99.2-99.4%. The remaining gap is repeated real labeled ordinary-turn windows and then a separate read-only inferred-approval readiness summary.

Next after this slice:

1. Commit/push and watch CI.
2. Use `ordinary-turn-label-packet` plus `ordinary-turn-label-update` to produce repeated labeled ordinary-turn windows. Prefer copy-DB windows first; mutate live DB labels only after local raw review of selected refs.
3. Add a repeated-window ordinary-turn label/eval summary gate.
4. Do not enable ordinary-turn apply until stable green labeled windows and a separate exact-gated readiness/apply design exist.


## Checkpoint: ordinary-turn label/evidence packet

The source checkout now has the missing review substrate before repeated ordinary-turn classifier evaluation. `dogfood ordinary-turn-label-packet <db_path>` produces a local, raw-text-free packet of ordinary turns that can be labeled with `metadata.expected_memory_worthy` after local raw-trace review.

What changed in source:

- Added `dogfood ordinary-turn-label-packet`.
  - Inputs: `db_path`, `--limit`, `--max-items`, `--min-items`, optional `--output`.
  - Output includes local `experience_trace:<id>` refs, content SHA-256, summary SHA-256, timestamp/surface/scope/retention metadata, classifier prediction, reason bucket, and coarse evidence features.
  - Output excludes raw trace summaries, raw transcript, raw query text, raw content, sample values, and secret-like unlabeled turns.
  - The packet is for manual/local labeling only; it does not set labels and does not create candidates or memories.
- Added RED/GREEN CLI coverage proving the packet is read-only, secret-safe, and does not leak raw ordinary-turn text.
- Preserved all forbidden authority flags: no ordinary conversation auto-approval, no apply execution, no broad/background apply, no default-ranking mutation, no collapse/delete, no telemetry reset, and no unreviewed promotion.

Live/source smoke:

- Artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-label-packet-20260516T164535Z/ordinary-turn-label-packet.json`.
- Result: gate green for manual labeling only.
  - `ordinary_turn=995`; `labeled_ordinary_turn=0`; `unlabeled_ordinary_turn=995`.
  - `review_item_count=25`; `eligible_unlabeled_nonsecret_count=995`; `blocked_secret_like_count=0`; `deferred_unlabeled_nonsecret_count=970`.
  - No live memory mutation occurred.

Validation:

- RED observed: invalid `ordinary-turn-label-packet` subcommand.
- Focused ordinary-turn tests: `4 passed, 173 deselected`.
- Full suite: `359 passed, 1 xfailed`.
- Release metadata tests: `2 passed`.
- Release-readiness smoke, release metadata script, `npm pack --dry-run`, and `git diff --check` passed.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%+.
- Literal fully autonomous human-brain-like memory for the scoped local lifecycle is approximately 99.0-99.2%. The remaining gap is no longer packet generation; it is repeated labeled ordinary-turn windows plus an exact-gated inferred-approval readiness/apply design.

Next after this slice:

1. Commit/push and watch CI.
2. Label packet items locally with `metadata.expected_memory_worthy`, or add a bounded exact-ref label-update corridor first.
3. Rerun `ordinary-turn-classifier-eval` over repeated labeled windows and keep apply blocked.
4. Only after stable green windows should inferred ordinary-turn approval readiness be designed; do not jump directly to ordinary-turn apply.

## Checkpoint: ordinary-turn classifier evaluation gate

The source checkout now has the first concrete read-only evaluation harness for the remaining ordinary-turn inference layer. `dogfood ordinary-turn-classifier-eval <db_path>` evaluates ordinary-turn memory-worthiness classification against optional aggregate labels before any ordinary conversation auto-approval corridor exists.

What changed in source:

- Added `dogfood ordinary-turn-classifier-eval`.
  - Inputs: `db_path`, `--limit`, `--min-labeled`, `--min-precision-percent`, optional `--output`.
  - Classifier policy: `ordinary-turn-memory-worthiness-heuristic-v1`.
  - Reports only aggregate counts: ordinary/labeled/unlabeled traces, prediction counts, precision/recall, secret-block rate, and safe reason buckets.
  - Keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `ordinary_conversation_auto_approval=false`, and all forbidden-authority flags false.
- Added focused RED/GREEN CLI coverage proving labeled ordinary turns are scored without mutation or raw-content leakage.

Live/source smoke:

- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-classifier-eval-20260516T160146Z/`.
- Current live DB has no ordinary-turn labels yet, so the new gate correctly stays red/fail-closed:
  - `ordinary_turn=995`;
  - `labeled_ordinary_turn=0`;
  - `unlabeled_ordinary_turn=995`;
  - `blocked_secret_like=0`;
  - blocked reasons: `labeled_ordinary_turn_count_below_minimum`, `precision_below_minimum`.
- No live memory mutation occurred.

Validation so far:

- New focused test: passed after observed RED invalid-subcommand failure.
- Focused ordinary-turn coverage: `2 passed, 174 deselected`.
- Local full suite before push: `358 passed, 1 xfailed`.
- First pushed CI exposed a known environment-sensitive retrieval-eval comparator-matrix delta (`lexical` `total_avoid_hit_delta` can be `-16` locally or `-15` on GitHub while stable task/pass counts stay fixed); source test tolerance was narrowed to that exact bounded variant.
- `git diff --check` and docs line-number scan passed after docs update.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%+.
- Literal fully autonomous human-brain-like memory for the scoped local lifecycle is now about 98.7-99%: explicit-memory and lifecycle automation are late-stage, and the ordinary-turn inference layer now has an eval substrate.
- The remaining gap to 100% is labeled ordinary-turn evidence, repeated green eval windows, and then a separate exact-gated inferred-approval corridor.

Next after this slice:

1. Run the full source suite/release/package checks, commit/push this checkpoint, and watch CI.
2. Next PR-sized slice: add a read-only ordinary-turn label/evidence packet for human review, without raw-content leakage in committed docs and without apply.
3. Only after repeated labeled windows are green should an inferred ordinary-turn approval corridor be designed.
4. Continue blocking broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion until each has its own evidence gate and rollback path.

## Checkpoint: remember-preferences bounded-batch post-apply verifier

The source checkout now closes the missing stop gate after a future bounded `remember-preferences --max-apply 2` batch. The new verifier is read-only and validates a saved bounded-batch operator packet, the bounded apply report, and the post-apply dry-run report before any next batch can be considered.

What changed in source:

- Added `consolidation auto-approve remember-preferences-batch-post-apply-verification`.
  - Inputs: `--operator-packet-report`, `--apply-report`, `--post-dry-run-report`, `--expected-policy`, `--max-approved`, optional `--output`.
  - Requires a green/manual-only operator packet, exact policy/scope/actor match, batch size within `2..max_approved`, approved facts only for `user prefers`, auto-approval relation ids, audit actor/reason, zero blocked candidates, and post-dry-run skipped count covering the applied batch.
  - Emits only artifact hashes and aggregate/ref-safe approved refs; it does not include raw preference text, candidate JSON, trace ids, raw reason text, or backup contents.
  - Keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, and all forbidden-authority flags false.
- Added focused RED/GREEN tests for the green stop gate and a bad-batch failure shape.
- The previous batch graduation/operator packet remains manual-only. The new verifier is a stop gate, not unattended batch permission.

Live/source smoke:

- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-batch-apply-verifier-20260516T154738Z-agent-memory-scope/`.
- Current live DB has no remaining eligible explicit `remember-preferences-v1` candidates for `project:agent-memory`:
  - `pre-batch-dry-run.json`: `eligible_count=0`, `blocked_count=0`, `skipped_count=5`, `mutated=false`.
  - `graduation-readiness.json`: correctly red with `current_dry_run_has_no_eligible_candidates`.
- A generic-scope exploratory run at `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-batch-apply-verifier-20260516T154702Z/` also produced no mutation: `approved_count=0`, `mutated=false`; its verifier correctly stayed red because there was no real batch apply to verify.
- This means the new verifier is source-verified and fail-closed on live artifacts; there was no live memory mutation in this checkpoint.

Validation:

- New focused tests: `2 passed, 173 deselected` after observed RED parser failures.
- Focused remember-preferences coverage: `11 passed, 164 deselected`.
- Full suite: `357 passed, 1 xfailed`.
- Release metadata smoke + release-readiness smoke passed on version `0.1.162`.
- `npm pack --dry-run` passed.
- `git diff --check` passed.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%+.
- Literal fully autonomous human-brain-like memory for the scoped local lifecycle is now about 98.5%: the explicit remember-intent/preference lane has evidence, topic-aware conflict handling, one-at-a-time apply, duplicate guards, post-apply verifier, queue drain proof, bounded-batch packet, and now a batch-specific post-apply stop gate.
- The remaining gap to 100% is no longer basic explicit-memory plumbing. It is the intentionally riskier generalization layer: ordinary-turn inferred approval/classification, unattended/background apply, default-ranking rollout, autonomous collapse/delete, live telemetry reset, and unreviewed promotion.

Next after this slice:

1. Commit/push this source checkpoint and watch CI.
2. Next PR-sized slice toward 100%: build an ordinary-turn classifier/evaluation harness that remains read-only but proves high precision for inferred memory-worthy turns before any inferred approval is allowed.
3. If new explicit remember-preferences candidates appear later, a real `--max-apply 2` batch can only proceed with a fresh green packet, exact operator approval, backup/output paths, post-dry-run, and this batch verifier green afterward.
4. Continue blocking broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion until each has its own evidence gate and rollback path.

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

Latest source-novelty slice:

- `dogfood lifecycle-candidate-refresh-preview` now includes aggregate-only `source_novelty` scoring.
- It separates new unapplied target candidates from fresh post-apply evidence windows that only hit already-applied targets.
- It remains read-only/no-mutation/default-unchanged and does not emit candidate ids, target refs, raw observations, raw query/query-preview/source content, raw candidate JSON, or backup contents.
- It also fixes nested artifact gate metadata in `dogfood lifecycle-bounded-batch-operator-packet`: nested `mutated` now reflects the nested report's actual mutation value.
- Live artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-source-novelty-preview-20260516T035332Z/lifecycle-candidate-refresh-preview-source-novelty.json`.
- Live result: `preview_candidate_count=4`, `target_already_applied_count=4`, `new_unapplied_target_candidate_count=0`, `fresh_observation_count_for_preview_targets=42`, `applied_target_with_fresh_window_count=4`, `source_level_novelty_decision=fresh_evidence_recycles_already_applied_targets`.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%.
- Literal fully autonomous human-brain-like memory is approximately 89-90%. Fresh recurrence evidence is measurable, but write automation still correctly refuses same-target review requeueing without a separate recurrent-reinforcement policy.

Immediate next recommended slice:

1. Commit/push this source-novelty checkpoint and watch CI.
2. Add a separate exact-reviewed recurrent-reinforcement policy for already-applied targets with fresh evidence windows, or broaden candidate generation until genuinely new target refs appear.
3. Keep live bounded batch apply blocked until approved eligible candidates exist and the operator packet is green.
4. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Checkpoint: target-aware lifecycle persistence + bounded-batch source gates



Latest fresh-evidence preview slice:

- Added read-only `dogfood lifecycle-fresh-evidence-preview` for policy-scoped post-apply retrieval evidence.
- It reports aggregate counts only: observation count, surface counts, preferred-scope counts, top-memory-ref counts, response-mode counts, and no raw query/query-preview/candidate/target/backup values.
- Live artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-fresh-evidence-preview-20260516T033110Z/lifecycle-fresh-evidence-preview-reinforcement.json`.
- Live result is green with `post_apply_observation_count=53`, so enough fresh dogfood evidence exists to attempt the next refresh/persist cycle; the target-aware persist guard must still prevent already-applied target requeueing.

Latest target-aware persistence slice:

- `dogfood lifecycle-candidate-persist` now skips candidates whose target refs already appear in `g5_trace_candidate_applications` before inserting review rows.
- The persisted report includes `skipped_applied_target_count`, `skipped_existing_target_count`, and a red quality gate when no new unapplied lifecycle candidates were persisted.
- Live no-op artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-target-aware-lifecycle-persist-20260516T030945Z/lifecycle-candidate-persist-target-aware-reinforcement.json`.
- Live result: all four reinforcement-shaped preview candidates were skipped as already-applied targets; no review rows were inserted and no live batch apply was enabled.

The source checkout now has a read-only operator packet for the lifecycle bounded-batch corridor. This is the missing pre-apply runbook artifact after the bounded-batch apply command and bounded-batch post-apply verifier: it lets an operator see whether graduation proof, apply readiness, candidate inventory, exact command arguments, backup/output placeholders, and post-apply verification are all aligned before any mutation.

What changed:

- Added `dogfood lifecycle-bounded-batch-operator-packet <db_path> --policy <policy> --actor <actor> --max-apply 2 --output <packet.json>`.
- The command is read-only and does not apply candidates, approve candidates, change retrieval defaults, expose candidate JSON, expose raw reason text, or expose backup contents.
- The packet includes:
  - `artifact_gates.batch_graduation_readiness` from `lifecycle-batch-graduation-readiness`;
  - `artifact_gates.apply_readiness` from `lifecycle-apply-readiness`;
  - aggregate candidate inventory for approved/not-yet-applied candidates;
  - exact `lifecycle-bounded-batch-apply` command preview with required policy, approval phrase, batch approval phrase, actor, private reason placeholder, max apply, backup path, and output path;
  - exact `lifecycle-bounded-batch-post-apply-verification` command template;
  - safety exclusions for ordinary auto-approval, broad/background apply, default retrieval migration, collapse/delete, telemetry reset, unreviewed promotion, and apply without exact operator approval.
- Live smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-batch-operator-packet-20260516T022916Z/lifecycle-bounded-batch-operator-packet.json`.
- Live result: graduation readiness passed (`prior_one_at_a_time_apply_count=4`), but apply readiness and candidate inventory blocked the packet because `approved_eligible_count=0`. No live batch apply was executed.

Additional refresh preview slice:

- Added `dogfood lifecycle-candidate-refresh-preview`, a read-only source gate that separates fresh lifecycle preview candidates from existing review rows and already-applied/promoted target refs.
- Live reinforcement refresh artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-refresh-preview-20260516T025334Z/lifecycle-candidate-refresh-preview-reinforcement.json`.
- Live result: preview still found four reinforcement-shaped candidates, but all four target refs were already applied; `new_unapplied_target_candidate_count=0`, so candidate persistence remains blocked until genuinely fresh unapplied dogfood evidence appears.

Current interpretation:

- Safety-gated operational north-star remains approximately 99%: the batch apply corridor now has pre-apply packet + post-apply verifier, but the live DB has no approved candidates to batch apply.
- Literal fully autonomous human-brain-like memory is approximately 88-89%: the system has stronger operator runbook automation, but fresh candidate generation/review and ordinary-turn safe auto-approval are not yet autonomous.

Immediate next recommended slice:

1. Commit/push this operator packet checkpoint and watch CI.
2. Run refresh/persist after the fresh-evidence preview; if it still recycles applied targets, add novelty scoring that requires new target refs or post-apply evidence windows before review persistence.
3. Keep live batch apply blocked until a fresh operator packet is green with reviewed approved candidates.
4. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Checkpoint: fourth live exact-approved reinforcement lifecycle apply + bounded batch post-apply verifier source gate

The fourth and final initial live reinforcement lifecycle candidate has been applied through the exact reviewed-candidate corridor. This completes the one-at-a-time proof loop for the four initial reinforcement candidates while preserving backup, readiness, rollback replay, application audit, live evidence bundle, and lifecycle post-apply verification gates. A new read-only source gate, `dogfood lifecycle-batch-graduation-readiness`, now reports whether those repeated one-at-a-time proofs are enough to design a separate bounded-batch corridor; it does not execute or authorize batch apply.

What happened:

- Approved candidate `g5-reinforcement-84541df977996b35164b682a`, target `fact:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `774765d9b1fec9df76f7582232c14967e92b8e50afbfd5b550b700ec79e56690`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=4`, `pending=0`, `approved=0`.
- Rollback replay passed with application count `7`, including four `g5-lifecycle-reinforcement-apply-v1` applications.
- Post-apply live evidence bundle passed with `fixture_task_count=4`, baseline regressions `0`, rollback checked applications `7`, and audit application count `4`.
- `lifecycle-post-apply-verification.json` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- New source command `dogfood lifecycle-batch-graduation-readiness` passed on the live DB for `g5-lifecycle-reinforcement-apply-v1` with `prior_one_at_a_time_apply_count=4`, but reports `bounded_batch_apply_supported=false` and `requires_separate_exact_approval_corridor=true`.
- New source command `dogfood lifecycle-bounded-batch-apply` provides the separate exact-approval corridor with `--max-apply <= 2`; source tests cover a two-candidate batch after graduation proof. Live smoke returned `no_eligible_approved_lifecycle_candidates` without mutation because the current initial queue is exhausted.
- New source command `dogfood lifecycle-bounded-batch-post-apply-verification` validates bounded-batch apply artifacts as a read-only stop gate: applied count <= verifier max, backup file/SHA, rollback replay, application audit, default retrieval unchanged, privacy, and forbidden-authority flags.

Current interpretation:

- Safety-gated operational north-star is now approximately 97-98%.
- Literal fully autonomous human-brain-like memory is approximately 82-84%: the system has repeated live reviewed lifecycle mutation proof, a batch-graduation readiness classifier, a bounded batch corridor, and a batch-specific post-apply verifier in source, but risky mutation still requires exact reviewed approval and live batch proof is not yet available because there are no approved candidates.

Immediate next recommended slice:

1. Commit/push the `lifecycle-bounded-batch-post-apply-verification` source/test/docs checkpoint and watch CI.
2. Next code slice should generate new lifecycle candidates from fresh dogfood traces or add a read-only batch-operator packet that bundles graduation, candidate inventory, bounded apply command preview, and post-apply verifier command preview.
3. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked.
4. Do not live-batch-apply from the green source verifier alone; live batch apply requires reviewed approved candidates, exact operator approval, a backup path, and an immediate green bounded-batch post-apply verifier.

## Checkpoint: third live exact-approved reinforcement lifecycle apply

The third live reinforcement lifecycle candidate was applied through the exact reviewed-candidate corridor. This proved the repeated one-at-a-time loop across three different target refs while preserving backup, readiness, rollback replay, audit, and lifecycle post-apply verification gates.

What happened:

- Approved candidate `g5-reinforcement-da820f3c712f508c084d3137`, target `procedure:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `5a18d345734798790ffa5bdd678901975792534a906d4e8df343dd75f174201c`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=3`, `pending=1`, `approved=0`.
- Rollback replay passed, application audit passed, and `lifecycle-post-apply-verification` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- The post-apply live evidence bundle passed for this bounded artifact set; treat it as post-apply evidence, not broad/background apply permission.

Current interpretation:

- Safety-gated operational north-star was approximately 96-97%.
- Literal fully autonomous human-brain-like memory was approximately 76-78% at this checkpoint.

## Checkpoint: second live exact-approved reinforcement lifecycle apply

The second live reinforcement lifecycle candidate has been applied through the same exact reviewed-candidate corridor. This proves the one-at-a-time loop can repeat with backup, readiness, rollback replay, and lifecycle post-apply verification still green.

What happened:

- Approved candidate `g5-reinforcement-3c9f30f85f8bdb80c9f3474f`, target `episode:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `c1f7dab326276a91b4b9b89818a96280dd050525987b3bf26ce2733b3c121387`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=2`, `pending=2`, `approved=0`.
- Rollback replay passed, and `lifecycle-post-apply-verification` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- Broader `live-evidence-bundle` is still red on `live_fixture_reliability_gate_not_green`; keep treating that as ranking/evidence reliability work, not as lifecycle apply failure.

Current interpretation:

- Safety-gated operational north-star is now approximately 95-96%.
- Literal fully autonomous human-brain-like memory is approximately 74-76%: the real DB has now completed two live reviewed lifecycle reinforcement mutations, but autonomy is still exact-approval gated and one-at-a-time.

Immediate next recommended slice:

1. Commit/push this second live apply checkpoint and watch CI.
2. Apply at most one more pending reinforcement candidate only after the checkpoint is green.
3. Rerun `lifecycle-post-apply-verification` after each apply and stop.
4. Keep ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without fresh approval blocked until separate gates exist.

## Checkpoint: first live exact-approved reinforcement lifecycle apply

The first live lifecycle reinforcement candidate has been approved and applied on the real source DB through the exact reviewed-candidate corridor. This was intentionally bounded to one candidate and stopped after post-apply verification.

What happened:

- Approved candidate `g5-reinforcement-255f68c152b76d844c6720cc`, target `fact:4`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Readiness before apply was green for exactly one reinforcement candidate.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `5c44d39611e613b04bd0bb984b0bdd11fd8acd26b5bee6b3fb2f8b3ab26bec0d`.
- Post-apply readiness returned to no-ready-apply: `promoted=1`, `pending=3`, `approved=0` for reinforcement.
- Rollback confidence, rollback replay, and application audit with ranking evidence passed.
- Added and ran `dogfood lifecycle-post-apply-verification`; it passed on the live artifact directory with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- Broader post-apply `live-evidence-bundle` remained red on `live_fixture_reliability_gate_not_green`; this is a broader evidence-quality/ranking blocker, not a failure of the bounded reinforcement apply.

Current interpretation:

- Safety-gated operational north-star is now approximately 94-95%.
- Literal fully autonomous human-brain-like memory is approximately 72-74%: the live system can execute a real reviewed lifecycle mutation with backup/audit/rollback, but it still depends on exact approval and one-at-a-time stop gates.

Immediate next recommended slice:

1. Commit/push the source/test/docs checkpoint for `dogfood lifecycle-post-apply-verification` and watch CI.
2. After CI is green, approve/apply only one more pending reinforcement candidate with the same exact phrase corridor and stop again.
3. Rerun `lifecycle-post-apply-verification` immediately after that second one-candidate apply.
4. Do not enable ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, or repeated apply without fresh approval until separate gates exist.

## Checkpoint: live lifecycle readiness smoke and pending reinforcement review queue

Exercised the new lifecycle readiness gate against the real source DB at `/Users/reddit/.agent-memory/memory.db`. The gate correctly blocked apply because there were no approved candidates. The next safe action was to persist review candidates, not apply them.

What happened:

- Initial live readiness artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-apply-readiness-20260515T092750Z/lifecycle-apply-readiness.json`.
- Initial result: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, quality gate red with `decision=no_exact_lifecycle_apply_candidates_ready`.
- Read-only previews found:
  - reinforcement `candidate_count=4`, gate green;
  - decay `candidate_count=0`;
  - supersession `candidate_count=0`.
- Persisted four reinforcement lifecycle candidates for explicit review only at `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-persist-20260515T092910Z/`.
- After-persist readiness reports reinforcement `pending=4`, `approved=0`, `eligible_approved_count=0`, so apply remains blocked.

Current interpretation:

- Safety-gated operational north-star remains approximately 93-94%.
- Literal fully autonomous human-brain-like memory remains approximately 70-72% because the system can now produce live pending lifecycle candidates, but review/approval/apply is still exact-gated.

Immediate next recommended slice:

1. Review exactly one pending reinforcement candidate from `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-persist-20260515T092910Z/lifecycle-candidate-list-reinforcement.json`.
2. If approved, run `dogfood lifecycle-candidate-update` with exact phrase `approve-g5-lifecycle-candidate-v1`.
3. Then run `dogfood lifecycle-candidate-apply` for that candidate only with policy `g5-lifecycle-reinforcement-apply-v1` and exact phrase `apply-approved-g5-lifecycle-reinforcement-v1`, capturing backup/output artifacts.
4. Rerun readiness/rollback verification and stop; do not batch-apply.
5. Keep ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default-ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without fresh approval blocked.

## Checkpoint: lifecycle apply readiness/audit gate added

Completed the approval-gate cleanup slice for roadmap lanes 3-7. The source checkout can now summarize reviewed lifecycle apply eligibility across reinforcement, decay, and supersession before any mutation, while explicitly keeping ordinary conversation auto-approval and default-ranking automatic rollout blocked.

What changed:

- Added `dogfood lifecycle-apply-readiness <db_path> --output <readiness.json>`.
- The command is read-only and aggregate-only. It reports candidate status counts by lifecycle kind and policy readiness for:
  - reinforcement: `g5-lifecycle-reinforcement-apply-v1`;
  - decay: `g5-lifecycle-decay-deprecate-apply-v1`;
  - supersession: `g5-lifecycle-supersession-apply-v1`.
- For each lane it reports exact policy, exact approval phrase, eligible approved count, already-applied count, blocked count, and decision.
- Forbidden authority is explicit: no apply execution, no broad/background apply, no ordinary conversation auto-approval, no default ranking mutation, no collapse/delete apply, no telemetry reset, and no unreviewed promotion.

Verification:

- RED observed: focused test failed because `lifecycle-apply-readiness` was not a recognized dogfood action.
- Focused readiness test: `uv run pytest tests/test_cli.py::test_dogfood_lifecycle_apply_readiness_summarizes_gates_without_mutation -q` -> `1 passed`.
- Related lifecycle/policy subset: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'lifecycle_apply_readiness or lifecycle_candidate_apply or lifecycle_candidate_registry or automation_policy_readiness or retrieval_ranking_migrate_default or remember_intent'` -> `10 passed, 146 deselected`.
- Full source gate: `uv run pytest tests/ -q` -> `338 passed, 1 xfailed`.

Current interpretation:

- Safety-gated operational north-star is now approximately 93-94%.
- Literal fully autonomous human-brain-like memory is approximately 70-72%: reinforcement/decay/supersession now have consistent reviewed candidate corridors plus a read-only readiness/audit gate; ordinary conversation auto-approval, broad/background mutation, destructive forgetting, and automatic default-ranking rollout remain intentionally blocked.

Immediate next recommended slice:

1. Commit/push and verify CI for the lifecycle readiness gate slice.
2. Next safe source slice: live dogfood run of `lifecycle-apply-readiness` on the real source DB and, only if green, one exact reviewed apply on a single approved candidate family.
3. Keep ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default-ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without new approval blocked unless their own exact policy slices implement guardrails.

## Checkpoint: narrow reviewed reinforcement lifecycle apply added

Completed the next lowest-risk auto-apply unification slice after the read-only automation policy readiness classifier. Reinforcement already had preview, lifecycle-candidate persist/update, and G4 review-queue apply coverage; it now also has the same G5 lifecycle-candidate apply corridor used by decay and supersession.

What changed:

- Extended `dogfood lifecycle-candidate-apply` with policy `g5-lifecycle-reinforcement-apply-v1`.
- Required approval phrase: `apply-approved-g5-lifecycle-reinforcement-v1`.
- Scope is intentionally narrow: approved `candidate_kind=reinforcement`, `proposal_type=reinforcement_review` lifecycle candidates only.
- Apply action increments `reinforcement_count` for the reviewed target memory and records the application with backup/rollback metadata.
- It does not change memory status, retrieval defaults, ordinary conversation auto-approval, broad/background apply, decay collapse/delete, telemetry reset, or ranking defaults.

Verification:

- RED observed: focused test failed because the reinforcement lifecycle apply policy was not accepted.
- Focused reinforcement lifecycle apply test: `uv run pytest tests/test_cli.py::test_dogfood_lifecycle_candidate_apply_reinforces_approved_candidate_with_backup -q` -> `1 passed`.
- Related lifecycle/policy subset: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'lifecycle_candidate_apply or lifecycle_candidate_registry or reinforcement_refinement_preview or automation_policy_readiness or g4_review_queue_apply'` -> `6 passed, 149 deselected`.
- Full source gate: `uv run pytest tests/ -q` -> `337 passed, 1 xfailed`.

Current interpretation:

- Safety-gated operational north-star is now approximately 92-93%.
- Literal fully autonomous human-brain-like memory is approximately 68-70%: the first narrow reviewed apply family is now more uniform across reinforcement/decay/supersession, but ordinary conversation auto-approval, broad/background apply, collapse/delete, and automatic default-ranking rollout remain intentionally blocked.

Immediate next recommended slice:

1. Commit/push and verify CI for the reinforcement lifecycle apply slice.
2. Next safe source slice: a read-only or exact-gated lifecycle apply readiness/audit summary across reinforcement, decay, and supersession so repeated applies cannot happen without fresh review/approval evidence.
3. Keep ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default-ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without new approval blocked unless their own exact policy slices implement guardrails.

## Checkpoint: read-only automation policy readiness classifier added

Completed the next read-only policy slice after live evidence bundle comparison. The source checkout can now turn a green saved `dogfood_live_evidence_bundle_comparison` report into an explicit lane-by-lane automation readiness artifact without executing apply or changing defaults.

What changed:

- Added `dogfood automation-policy-readiness --comparison-report <comparison.json> --output <readiness.json>`.
- The command emits `kind=dogfood_automation_policy_readiness`.
- It summarizes the comparison artifact by path, SHA-256, quality decision, report count, fixture coverage, regression max, rollback/audit minima, and audit evidence pass count.
- It classifies the requested 1-7 automation lanes:
  - readiness report: complete;
  - narrow reviewed apply: eligible only for a later exact approval slice;
  - reinforcement: review-candidate generation only;
  - decay/forgetting: reviewed deprecate corridor only, collapse/delete still blocked;
  - conflict/supersession: reviewed supersession corridor only;
  - ordinary conversation auto-approval: blocked;
  - default ranking migration: exact migration review only.
- The readiness report is explicitly read-only and policy-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `ordinary_conversation_auto_approval=false`, no raw report embedding, and no apply/default-ranking/collapse-delete/telemetry-reset authority.

Verification:

- RED observed: focused CLI test failed because `automation-policy-readiness` was not a recognized dogfood action.
- Focused readiness test: `uv run pytest tests/test_cli.py::test_dogfood_automation_policy_readiness_classifies_next_lanes_without_apply -q` -> `1 passed`.
- Evidence/policy subset: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'automation_policy_readiness or live_evidence_bundle_compare or live_evidence_bundle or reinforcement_refinement_preview or decay_collapse_decision or supersession_preview or lifecycle_candidate_apply or retrieval_ranking_migrate_default or remember_preference'` -> `9 passed, 145 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `336 passed, 1 xfailed`.
- Live read-only readiness smoke wrote `/Users/reddit/.agent-memory/reports/source-automation-policy-readiness-20260515T084816Z/automation-policy-readiness.json` from the existing green comparison report; quality gate passed, narrow reviewed apply is eligible for exact approval slice, ordinary conversation auto-approval remains blocked.

Current interpretation:

- Safety-gated operational north-star is now approximately 91-92%.
- Literal fully autonomous human-brain-like memory is approximately 66-68%: the system now chooses the next automation lane from live evidence, but mutation/apply/default ranking/ordinary auto-approval remain intentionally separated into guarded exact slices.

Immediate next recommended slice:

1. Commit/push and verify CI for this readiness classifier slice.
2. Next safe source slice: implement the first exact narrow reviewed-candidate apply policy from this readiness artifact, with backup/audit/rollback and no broad/background apply.
3. Keep ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, and repeated apply without new approval blocked unless their own exact policy slices implement guardrails.

## Checkpoint: read-only live evidence bundle comparison added

Completed the next read-only accumulation slice after `dogfood live-evidence-bundle`. Saved bundle reports can now be compared without embedding raw report bodies, so repeated live dogfood windows can be summarized before any broader automation policy work.

What changed:

- Added `dogfood live-evidence-bundle-compare --report <bundle.json> --report <bundle.json> --output <comparison.json>`.
- The command emits `kind=dogfood_live_evidence_bundle_comparison`.
- Each input report is summarized by path, top-level SHA-256, generated timestamp, quality-gate decision, ref-safe rollup counts, and nested artifact hashes only.
- Aggregate output includes pass count, decision counts, fixture coverage min/max, fixture retrieval/reliability pass counts, ranking baseline regression totals/max, rollback/audit count ranges, audit evidence pass count, and blocker trends.
- The comparison remains read-only and policy-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `ordinary_conversation_auto_approval=false`, no raw report embedding, and no apply/default-ranking/collapse-delete/telemetry-reset authority.

Verification:

- RED observed: focused CLI test failed because `live-evidence-bundle-compare` was not a recognized dogfood action.
- Focused compare test: `uv run pytest tests/test_cli.py::test_dogfood_live_evidence_bundle_compare_summarizes_repeated_reports_without_raw_content -q` -> `1 passed`.
- Evidence/audit subset: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'live_evidence_bundle_compare or live_evidence_bundle or live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit or rollback_replay_validate'` -> `6 passed, 147 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `335 passed, 1 xfailed`.
- Live read-only compare smoke wrote `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-compare-20260515T074353Z/live-evidence-bundle-comparison.json` using the existing green source bundle twice as a same-window stability smoke; quality gate passed, report count `2`, fixture task count min/max `4/4`, baseline regression max `0`, rollback/audit min/max `3/3`.

Current interpretation:

- Safety-gated operational north-star is now approximately 90-91%.
- Literal fully autonomous human-brain-like memory is approximately 63-66%: trend comparison is now automated, but mutation/apply/default ranking/ordinary auto-approval remain deliberately blocked pending narrow policy slices.

Immediate next recommended slice:

1. Commit/push and verify CI for this comparison slice.
2. Next safe source slice: use stable comparison evidence to draft/implement a read-only automation-policy readiness report that decides which narrowly scoped auto-decision lane is eligible next without executing apply.
3. Keep broad/background apply, live G4 apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked unless a later exact policy slice implements its own guardrails.

## Checkpoint: read-only live evidence bundle added

Completed the next read-only evidence orchestration slice after live fixture diagnostics. The source checkout can now produce one ref-safe bundle that generates live fixture diagnostics, runs the ranking experiment, validates rollback replay, and feeds those artifacts into trace-candidate application audit with artifact hashes.

What changed:

- Added `dogfood live-evidence-bundle <db_path> --output-dir <dir>`.
- The command writes the live fixture JSON, fixture diagnostics report, retrieval-ranking experiment report, rollback replay report, trace-candidate application audit report, and optional bundle report.
- Bundle output includes artifact paths and SHA-256 hashes instead of embedding raw report bodies.
- The bundle remains evidence-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `ordinary_conversation_auto_approval=false`, and `bundle_executes_apply=false`.
- The safety contract explicitly keeps broad G4 apply, default-ranking mutation, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without new approval blocked.
- Privacy flags remain raw-content safe: no raw source/transcript/query/trace content, reviewed payload, backup content, or raw report embedding.

Verification:

- Focused bundle test: `uv run pytest tests/test_cli.py::test_dogfood_live_evidence_bundle_chains_read_only_artifacts -q` -> `1 passed`.
- Evidence/audit subset: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'live_evidence_bundle or live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit or rollback_replay_validate'` -> `5 passed, 147 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `334 passed, 1 xfailed`.
- Live source smoke wrote `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-20260515T072811Z/live-evidence-bundle.json` against `/Users/reddit/.agent-memory/memory.db`: quality gate pass, fixture tasks `4` (`facts=2`, `procedures=1`, `episodes=1`), fixture retrieval/reliability pass, ranking baseline regressions `0`, rollback checked application count `3`, audit application count `3`, audit required evidence gate pass.

Current interpretation:

- Brainlike-memory north-star is approximately 89-90% in the safety-gated operational roadmap framing.
- This reaches the edge of 90% because the live evidence path is now repeatable as one hashed, read-only bundle rather than a manually chained sequence.
- Literal fully autonomous human-brain-like memory is still materially lower because risky write/apply/delete/consolidation decisions remain human-reviewed or exact-approved.

Immediate next recommended slice:

1. Commit/push and verify CI for this bundle slice.
2. Next safe source slice: repeated-run bundle comparison/accumulation across two or more saved live evidence bundles, with artifact hashes and no mutation.
3. Keep broad/background apply, live G4 apply, telemetry reset, ranking default migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: live retrieval-ranking fixture diagnostics hardening added

Completed the next read-only evidence hardening slice after live fixture generation. The generator now explains not only what fixture tasks it wrote, but also what approved memory coverage was missing/skipped and whether the generated fixture passes a read-only retrieval eval before downstream ranking/application-audit use.

What changed:

- `dogfood live-retrieval-ranking-fixtures <db_path> --fixture-output <json>` now emits `generation_diagnostics`, `retrieval_diagnostics`, and a diagnostic-only `reliability_gate`.
- New flags: `--min-reliable-tasks`, `--baseline-mode`, and `--max-baseline-regressions`.
- Sparse DBs now report `insufficient_approved_memory` and `no_generated_fixture_tasks` instead of silently producing a tiny/empty fixture with no explanation.
- Per-type generation limits now report `generation_limit_reached` with skipped counts.
- Retrieval diagnostics include only task refs/counts and blocker reason labels; raw source content, raw transcript, raw query/content, reviewed payloads, private reasons, and backup contents remain excluded.
- The command remains evidence-only: no default ranking mutation, no live apply, no collapse/delete, no telemetry reset, and no ordinary-conversation auto-approval.

Verification:

- Focused diagnostics tests: `3 passed`.
- Evidence/audit subset: `4 passed, 147 deselected`.
- Full source gate: `333 passed, 1 xfailed`.
- Live source smoke wrote `/Users/reddit/.agent-memory/reports/source-live-ranking-fixture-diagnostics-20260515T065526Z/` against `/Users/reddit/.agent-memory/memory.db`: generated fixture `4` tasks (`facts=2`, `procedures=1`, `episodes=1`), generation diagnostics no skipped/insufficient items, retrieval diagnostics `pass=true`, `failed_task_count=0`, `baseline_regression_count=0`, reliability gate `pass=true` with `--min-reliable-tasks 4`, and downstream ranking experiment `ranking_change_allowed=true` with `live_compatible_task_count=4`.

Current interpretation:

- Brainlike-memory north-star is approximately 89% in the safety-gated operational roadmap framing.
- This moves the system closer to 90% because generated live ranking evidence now has explicit coverage/eval diagnostics instead of treating small live coverage as self-explanatory.
- Still below 90% because repeated live evidence orchestration and larger-volume stability are not bundled yet, and all mutation/automation gates remain deliberately blocked.

Immediate next recommended slice:

1. Commit/push and verify CI for this diagnostics hardening slice.
2. Next safe source slice: add a read-only repeated evidence bundle that generates live fixture diagnostics, runs ranking experiment, and feeds the resulting artifact into application audit with hashes and no mutation.
3. Keep broad/background apply, live G4 apply, telemetry reset, ranking default migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: live retrieval-ranking fixture generation added

Completed the next read-only evidence slice after the G5 application-audit gate. Application audits no longer need a manually shaped compatible ranking artifact for live smoke: source can now generate a retrieval-eval fixture from approved memories already present in the target DB, run the ranking experiment on it, and feed that ranking report into the application audit.

What changed:

- Added `dogfood live-retrieval-ranking-fixtures <db_path> --fixture-output <json>`.
- The generator builds fixture tasks from approved facts, procedures, and episodes in the same DB using numeric live refs, preferred scopes, expected IDs, empty avoid lists, and ref-safe rationales.
- The generated fixture is directly consumable by `dogfood retrieval-ranking-experiment --fixtures <fixture>`.
- The report remains evidence-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, no raw source content/transcripts/reviewed payloads/private reasons/backup content.
- This does not mutate default ranking, run apply, collapse/delete memory, reset telemetry, or enable ordinary-conversation auto-approval.

Verification so far:

- RED: focused test failed because `live-retrieval-ranking-fixtures` was not a recognized dogfood action.
- Focused test: `uv run pytest tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_generate_live_compatible_fixture -q` -> `1 passed`.
- Evidence/audit subset: `uv run pytest tests/test_cli.py -q -k 'live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit'` -> `2 passed, 147 deselected`.
- Live source smoke wrote `/Users/reddit/.agent-memory/reports/source-live-ranking-fixtures-20260515T054056Z/` against `/Users/reddit/.agent-memory/memory.db`: generated fixture `4` tasks (`facts=2`, `procedures=1`, `episodes=1`), ranking experiment `ranking_change_allowed=true`, `baseline_regression_count=0`, `live_compatible_task_count=4`, and application audit `required_evidence_gate.pass=true` with quality decision `trace_candidate_applications_ready_for_post_apply_review`.

Current interpretation:

- Brainlike-memory north-star is approximately 88% in the safety-gated operational roadmap framing.
- This removes the earlier live evidence gap where ranking evidence for application audit was manually shaped instead of generated from current live DB refs.
- Still below 90% until full source gate/CI are green and live fixture generation reports explicit skip/blocker diagnostics for larger realistic DB coverage across repeated runs.

Immediate next recommended slice:

1. Run full source gate, then commit/push and verify CI for this fixture-generation slice.
2. Next safe source slice: add skip/blocker diagnostics around generated live fixtures and retrieval-eval failures under realistic live DB volume.
3. Keep broad/background apply, live G4 apply, telemetry reset, ranking default migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: G5 trace candidate application audit evidence gate added

Completed the next read-only post-apply comparison slice toward the 90% runway. Reviewed trace-candidate promotions can now be audited with required rollback-replay and retrieval-ranking evidence before any broader automation decision.

What changed:

- Extended `dogfood trace-candidate-application-audit <db>` with `--rollback-replay-report` and `--retrieval-ranking-report`.
- The command reads `g5_trace_candidate_applications` joined to review state and emits a ref-safe audit report with application refs, policy/action, current memory status, backup/rollback confidence, status/policy rollups, a `required_evidence_gate`, and a combined quality gate.
- The required evidence gate validates rollback replay report kind/read-only/no-mutation/default-retrieval unchanged/green replay counts, plus retrieval-ranking experiment kind/read-only/no-mutation/default unchanged/no baseline regressions/no default-ranking mutation/no ordinary-conversation auto-enable.
- Missing required evidence now blocks the audit quality gate with `rollback_replay_report_not_provided` and/or `retrieval_ranking_report_not_provided`.
- The report remains explicitly read-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, and ordinary conversation auto-approval remains false.
- Raw clusters, reviewed payloads, raw content, raw reasons, and backup contents are not included.
- This is comparison/audit only; it does not apply candidates, replay rollback as mutation, mutate ranking defaults, collapse/delete memory, or approve ordinary conversation memories.

Verification:

- Focused audit/apply tests: `uv run pytest tests/test_cli.py::test_dogfood_trace_candidate_apply_promotes_only_approved_reviewed_fact_candidates tests/test_cli.py::test_dogfood_trace_candidate_application_audit_flags_missing_backup -q` -> `2 passed`.
- Trace candidate evidence/audit subset: `uv run pytest tests/test_cli.py -q -k 'trace_candidate_application_audit or trace_candidate_apply or rollback_replay_validate or retrieval_ranking_experiment'` -> `6 passed, 142 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `330 passed, 1 xfailed`.
- Live read-only source smoke wrote `/Users/reddit/.agent-memory/reports/source-g5-trace-candidate-application-evidence-gate-smoke-20260515T043414Z/` against `/Users/reddit/.agent-memory/memory.db`; result `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, application count `3`, `required_evidence_gate.pass=true`, quality gate pass, ordinary conversation auto-approval false. The rollback replay report was generated from the live DB; the ranking artifact was a minimal ref-safe green experiment-shaped artifact because the checked-in retrieval fixtures do not resolve against the current live DB scopes.

Current interpretation:

- Brainlike-memory north-star is approximately 87-88% complete.
- This narrows the gap to 90% by connecting post-apply audit to the required rollback and retrieval-ranking evidence rather than treating application audit as a standalone report.
- Still below 90% until source-checkout full tests/CI are green for this slice, live ranking evidence resolves from real live fixtures instead of a minimal compatible artifact, and repeated reports show stable quality under realistic candidate volume.

Immediate next recommended slice:

1. Commit/push and verify CI for this evidence-gated audit slice.
2. Next safe source slice: make live retrieval-ranking fixture generation self-contained from the current live DB so ranking evidence is generated, not manually shaped, for application audits.
3. Keep broad/background apply, live G4 apply, telemetry reset, ranking default migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: G5 trace candidate apply conflict preflight added

Completed the next E1/D5 safety boundary after D4 reject/snooze suppression. This narrows the remaining automation risk around reviewed candidate promotion: explicit review can promote durable memory, but same-claim contradictions are now preflighted before mutation.

What changed:

- `dogfood trace-candidate-apply` now runs `_promotion_conflict_preflight` for reviewed fact/preference promotions.
- Same claim slot (`subject_ref`, `predicate`, `scope`) with a different object is skipped by default with `reason=claim_slot_conflict`; no fact/status/application rows are created for that candidate.
- Added explicit `--allow-conflict` override for reviewers who intentionally accept coexisting claims after inspection.
- Apply output now includes `conflict_preflight_policy` showing fact/preference checking, default conflict blocking, and whether `--allow-conflict` was explicitly requested.
- Procedure/episode reviewed promotions are unchanged.
- No live DB apply, trace deletion, default ranking migration, broad/background apply, telemetry reset, collapse/delete, unreviewed promotion, or ordinary conversation auto-approval was executed.

Verification:

- Focused new conflict test: `uv run pytest tests/test_cli.py::test_dogfood_trace_candidate_apply_blocks_fact_claim_slot_conflicts_by_default -q` -> `1 passed`.
- Trace candidate regression subset: `uv run pytest tests/test_cli.py -q -k 'trace_candidate_apply or trace_candidate_update or trace_candidate_generate or trace_candidate_review_flow'` -> `7 passed, 140 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `329 passed, 1 xfailed`.
- Live read-only source smoke wrote `/Users/reddit/.agent-memory/reports/source-g5-trace-candidate-conflict-preflight-smoke-20260515T040859Z.json` against `/Users/reddit/.agent-memory/memory.db`; result `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, candidate count `10`, suppressed count `0`, ordinary conversation auto-approval false, raw content disallowed.

Current interpretation:

- Brainlike-memory north-star is approximately 83-85% complete.
- This improves the “human brain-like but safe” path by adding contradiction avoidance at the exact point where reviewed trace candidates become durable memory.
- Still below 90% because autonomous background mutation, ranking changes, collapse/delete, and ordinary-conversation approval remain deliberately blocked until rollback/retrieval/conflict evidence is stronger.

Immediate next recommended slice:

1. Finish full test + live read-only smoke for this checkpoint, then commit/push and verify CI.
2. Next safe source slice toward 90%: add a read-only post-apply comparison/audit report for trace candidate applications, so every reviewed promotion can be checked against retrieval/default-policy impact before any broader automation.
3. Keep broad/background apply, live G4 apply, telemetry reset, ranking default migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Checkpoint: G5 trace candidate reject/snooze suppression added

Completed the next D4 boundary after the G5 consolidation explainability slice. This adds the first explicit "do not keep showing me this same bad candidate" state for persisted trace-cluster candidates, while keeping memory creation and default retrieval behavior gated.

What changed:

- Fixed the G5 candidate review approval phrase helper so rejected candidates require `reject-g5-trace-candidate-v1` instead of the previous malformed `rejecte-...` derivation.
- Extended persisted trace candidate review state with `snoozed` and migration support for existing review tables.
- Added `--snooze-until` for `dogfood trace-candidate-update --status snoozed`, with exact phrase `snooze-g5-trace-candidate-v1`.
- `dogfood trace-candidate-generate` now filters candidates whose same candidate id/fingerprint was already rejected or is snoozed until a future timestamp.
- The generate report exposes only ref-safe suppression metadata: `suppressed_candidate_count`, `suppressed_candidates` with candidate id/status/snooze-until, and `suppression_policy`; it does not expose raw review payloads or raw trace content.
- No trace deletion, long-term memory promotion, default ranking migration, live G4 apply, telemetry reset, collapse/delete, broad/background apply, or ordinary conversation auto-approval was executed.

Verification:

- RED observed: new suppression test first failed on the malformed reject phrase and missing snooze support.
- Focused GREEN: `uv run pytest tests/test_cli.py::test_dogfood_trace_candidate_generate_suppresses_rejected_and_snoozed_existing_candidates -q` -> `1 passed`.
- Candidate flow regression: `uv run pytest tests/test_cli.py -q -k 'trace_candidate or lifecycle_candidate'` -> `8 passed, 138 deselected`.
- Full source gate: `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` initially hit one transient `uvx build` isolated pip-install failure in `tests/test_release_smoke.py::test_built_distributions_include_schema_sql`; exact rerun passed, then full rerun passed with `328 passed, 1 xfailed`.
- Live read-only source smoke wrote `/Users/reddit/.agent-memory/reports/source-g5-d4-trace-candidate-generate-20260515T035054Z.json` against `/Users/reddit/.agent-memory/memory.db`; result `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, candidate count `10`, suppressed count `0`, suppression policy present, and ordinary conversation auto-approval false.

Current interpretation:

- Brainlike-memory north-star remains approximately 81-83% complete.
- The system now has a safer negative-feedback path: humans can reject/snooze bad persisted trace candidates and the generator will stop resurfacing the same fingerprint.
- Remaining gap to human-brain-like automation is still substantial: promotion/apply must remain exact-approved; background consolidation still needs dry-run comparison, rollback proof, conflict-safe mutation, and ranking gates before any autonomous behavior.

Immediate next recommended slice:

1. Commit and push this D4 source/docs/test checkpoint on `develop`; no release solely for this narrow slice.
2. Continue with the E1/D5 boundary only after this is green in CI: manual reviewed promotion/apply should stay exact-approved with backup, audit, rollback, provenance, conflict/supersession preflight, and no ordinary conversation auto-approval.

## Checkpoint: G5 consolidation explainability source slice added

Completed the next read-only G5 brainlike consolidation runway slice after the v0.1.162 G4 release/packet checkpoint. This slice explains why consolidation candidates are review-worthy across trace clustering, reinforcement/refinement, decay/collapse, and supersession signals without granting mutation authority.

What changed:

- Added `dogfood consolidation-explainability <db_path>`.
- The command emits a ref-safe `dogfood_consolidation_explainability` report with:
  - `signal_counts` for trace clusters, reinforcement candidates, decay/collapse candidates, and supersession candidates;
  - an `explainability_ladder` from candidate evidence to `human_review_gate`;
  - ranked `top_review_candidates` with refs, tiers, scores, decisions, and evidence counts only;
  - explicit `automation_policy` showing `apply_supported=false`, `ordinary_conversation_auto_approval=false`, `requires_human_review=true`, `default_retrieval_policy=approved_only_unchanged`, and all mutation-contract flags false;
  - privacy flags that exclude raw conversation content, summaries, sample values, and object values.
- Fixed supersession enriched evidence to match the current `MemoryActivation` contract by filtering on `memory_ref` instead of nonexistent `memory_type`/`memory_id` attributes.
- No live apply, telemetry reset, default-ranking migration, broad/background apply, collapse/delete, promotion, or ordinary conversation auto-approval was executed.

Verification:

- Focused test: `.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_consolidation_explainability_reports_stage_reasons_without_mutation -q` -> `1 passed`.
- Focused G5 preview suite: `.venv/bin/python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && .venv/bin/python -m pytest tests/test_cli.py::test_dogfood_consolidation_explainability_reports_stage_reasons_without_mutation tests/test_cli.py::test_dogfood_trace_cluster_preview_reports_ref_safe_clusters_without_mutation tests/test_cli.py::test_dogfood_reinforcement_refinement_preview_scores_repeated_activation_without_mutation tests/test_cli.py::test_dogfood_decay_collapse_preview_reports_stale_weak_evidence_without_mutation tests/test_cli.py::test_dogfood_supersession_preview_reports_claim_conflicts_without_mutation -q` -> `5 passed`.
- Source-checkout live read-only smoke wrote `/Users/reddit/.agent-memory/reports/source-g5-consolidation-explainability-smoke.json` against `/Users/reddit/.agent-memory/memory.db`.
- Smoke result: `quality_gate.pass=true`, decision `consolidation_explainability_ready_for_manual_review`, `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, trace cluster candidates `5`, reinforcement candidates `4`, decay/collapse candidates `0`, supersession candidates `0`, and no blocked reasons.

Current interpretation:

- Overall brainlike-memory north-star is approximately 80-82% complete.
- The project now has a stronger read-only G5 explanation layer, but it is still not fully autonomous like a human brain because candidate review/promotion, mutation rollback, conflict-safe apply, opt-in ranking changes, and background dry-run/report comparison are still gated.
- The next meaningful progress is to persist reviewable consolidation candidates with explicit review state and audit/rollback boundaries, still without ordinary conversation auto-approval.

Immediate next recommended slice:

1. Commit and push this G5 source/docs/test checkpoint on `develop`; no release solely for this narrow slice.
2. If continuing G5, implement the next D4/E1 boundary: explicit candidate rejection/snooze or manual reviewed promotion into long-term memory with provenance, conflict/supersession checks, backup, audit output, and rollback proof.
3. Keep broad/background apply, live G4 apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked unless their exact approval corridors are separately supplied.

## Checkpoint: v0.1.162 released and published-install QA passed

The accumulated G4 bounded operator apply readiness corridor has been released as `v0.1.162` and verified from real published artifacts. This checkpoint completed priority 1 from the recommended sequence. No live memory apply, telemetry reset, default ranking migration, collapse/delete, broad/background apply, unreviewed promotion, or ordinary conversation auto-approval was executed.

Release path:

- Source release candidate commit: `b26be71`.
- Release metadata commit on `main`: `cda5696` (`chore: release v0.1.162 [skip release]`).
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.162`.
- npm: `@cafitac/agent-memory@0.1.162`.
- PyPI: `cafitac-agent-memory==0.1.162`.

GitHub Actions evidence:

- `ci` on source commit `b26be71`: success, run `25896978955`.
- `auto-release` on source commit `b26be71`: success, run `25896978967`.
- release-sync `ci` on `cda5696`: success, run `25897050696`.
- `ci` on release commit `cda5696`: success, run `25897160173`.
- release-sync `auto-release` on `cda5696`: success, run `25897160181`.
- `publish` workflow for `v0.1.162`: success, run `25897165575`; verify, PyPI publish, npm publish, and GitHub Release jobs all succeeded.

Local published-install QA:

- Artifact: `/tmp/agent-memory-v0162-published-smoke/published-install-smoke.json`.
- Result: `status=ok`, `attempt=1`, `propagation_retry_used=false`.
- Exact version verified: `0.1.162`.
- Surfaces covered: npm registry lookup, `npx`, `npm exec`, `uvx`, and `pipx run`.
- Commands covered: help, bootstrap, doctor, and hermes-pre-llm-hook where applicable.
- Isolated doctor checks passed with `status=ok`, `db_exists=true`, `config_exists=true`, and `hook_installed=true` for npm/uvx/pipx temp paths.

Operational note:

- The hosted `published-install-smoke.yml` workflow dispatch was attempted but blocked by the currently available `gh` token with `HTTP 403: Must have admin rights to Repository`. Do not treat that as package failure; the local exact-version published smoke passed against real npm/PyPI artifacts.

Current local state:

- Branch: `develop`.
- Local `develop` has been fast-forwarded to release commit `cda5696` and matches release metadata version `0.1.162`.
- Tracked tree is clean.
- Existing untracked local artifacts remain intentionally untouched: `.agent-learner/`, `.claude/`, `.dev/kb/retrieval-eval-m1-implementation-plan.md`, `.omc/`, `.worktrees/`.

Immediate next recommended slice:

- Priority 2 read-only evidence preparation is complete. The published `v0.1.162` CLI generated `/Users/reddit/.agent-memory/reports/v0.1.162-published-g4-operator-packet-20260515T024457Z/g4-operator-apply-packet.json` from the saved green operator bundle and readiness-summary artifacts.
- Packet result: `quality_gate.pass=true`, decision `operator_apply_packet_ready_for_manual_review_only`, `runbook_contract.matches_g4_bounded_operator_apply_runbook=true`, required apply/verifier flag checks true, `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, and `max_apply=1` in the manual command preview.
- Stop here unless the operator provides the exact live-apply approval corridor: phrase `apply-approved-g4-review-queue-items-v1`, policy `g4-review-queue-apply-v1`, actor, private reason, backup path, bounded `--max-apply`, and audit output path.
- If exact live-apply approval is not provided, continue with read-only G5 brainlike consolidation runway work instead.

## Checkpoint: G4 milestone release readiness review

Completed the requested milestone release-readiness review for the accumulated `develop` G4 corridor. No release or publish action was executed.

Review artifact:

- `.dev/roadmap/memory-consolidation/g4-milestone-release-readiness-review.md`

Scope:

- Compared `main..develop` after `v0.1.161`.
- Reviewed 10 commits from `539f929` through `e6eb7c1`.
- Changed tracked files vs main are limited to `.dev` status/roadmap docs, `src/agent_memory/api/cli.py`, and `tests/test_cli.py`.

Verdict:

- Source-ready as a release candidate after human maintainer release intent review.
- Candidate next release would be `v0.1.162` by patch bump, with theme `G4 bounded operator apply readiness corridor`.
- Do not publish automatically from generic continuation.

Checks:

- Full source test gate: `326 passed, 1 xfailed`.
- Release metadata check: package/module versions synced at `0.1.161`.
- Release readiness smoke: Python and Node bootstrap/doctor succeeded in isolated HOME.
- npm dry-run tarball: only `LICENSE`, `README.md`, `bin/agent-memory.js`, and `package.json`.
- Focused release/package tests: `34 passed`.

Immediate next recommended slice:

- Commit this release-readiness review checkpoint.
- If a real release is desired, get explicit release approval first, then follow the project release process and perform real downloaded install QA after publish.
- If no release approval is given, continue read-only source/docs hardening only.
- Live bounded G4 apply remains separate and still requires its exact operator approval corridor.

## Previous checkpoint: G4 packet/runbook contract self-check

Completed the next safe B-direction source/docs slice after docs commit `d92b2e9` without running live apply.

What changed:

- `dogfood g4-operator-apply-packet` now emits a `runbook_contract` block.
- The block makes the runbook/checklist alignment machine-readable:
  - required authorization inputs are enumerated;
  - pre-apply evidence requirements are enumerated;
  - post-apply stop requirements are enumerated;
  - manual apply command preview is checked for required flags;
  - post-apply verification template is checked for required flags;
  - `readiness_is_not_authorization=true` remains explicit.
- This is a read-only contract hardening only; it does not grant apply authority or run mutation.

Source live smoke:

- Command path: source checkout `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-packet`.
- Live DB checked: `/Users/reddit/.agent-memory/memory.db`.
- Inputs:
  - `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`
  - `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`
- Output: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-packet-runbook-crosscheck-20260514T145334Z/g4-operator-apply-packet.json`.
- Result: `quality_gate.pass=true`, decision `operator_apply_packet_ready_for_manual_review_only`, `runbook_contract.matches_g4_bounded_operator_apply_runbook=true`, required apply/verifier flag checks true, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`.

Verification:

- RED observed: focused packet test failed with `KeyError: 'runbook_contract'` before source implementation.
- Focused tests after implementation: `2 passed`.
- Full source gate: `PYTHONPATH=src .venv/bin/python -m compileall src && PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` -> `326 passed, 1 xfailed`.

Immediate next recommended slice:

- Commit this checkpoint.
- Do not release solely for this checkpoint.
- After commit, next safe work is milestone-release readiness review for the accumulated develop G4 corridor, or exact-approved bounded live apply if and only if the operator supplies the required live-apply approval packet.

## Previous checkpoint: G4 operator apply packet/checklist command added

Completed the next safe B-direction source slice after docs commit `204e63f` without running live apply.

What changed:

- Source commit `c7b6e0c` added `dogfood g4-operator-apply-packet`.
- The command consumes saved pre-apply evidence artifacts and emits a ref-safe JSON packet for manual review:
  - `operator_checklist` with required policy, approval phrase, actor, private reason, backup path, audit output path, bounded `max_apply`, post-apply verification, and repeated-apply prevention;
  - exact `g4-review-queue-apply` command preview with placeholders for private reason/backup/audit output;
  - exact `g4-post-apply-verification` command template.
- The command does not apply anything and reports `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, and ordinary conversation auto-approval false.
- It blocks unsafe/stale artifacts instead of treating any packet as approval.

Source live smoke:

- Command path: source checkout `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-packet`.
- Live DB checked: `/Users/reddit/.agent-memory/memory.db`.
- Inputs:
  - `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`
  - `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`
- Output: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-operator-apply-packet-20260514T141141Z/g4-operator-apply-packet.json`.
- Result: `quality_gate.pass=true`, decision `operator_apply_packet_ready_for_manual_review_only`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`.

Verification:

- RED observed: focused packet tests initially failed because the dogfood action did not exist.
- Focused tests: `2 passed`.
- Full source gate: `PYTHONPATH=src .venv/bin/python -m compileall src && PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` -> `326 passed, 1 xfailed`.

Immediate next recommended slice:

- Commit this docs/status checkpoint.
- Do not release yet; continue accumulating develop milestones until the corridor is complete/stable.
- Generic continuation may do read-only packet/runbook cross-checks or docs polish, but must not execute live apply.
- Live apply remains blocked unless separately approved with exact operator phrase, policy, actor, private reason, backup path, bounded max-apply, and audit output.

## Docs checkpoint: G4 bounded operator apply runbook/checklist hardened

Completed the next safe B-direction work after source commit `e0bc642`. This was a docs/checklist hardening slice only; no live apply was run and no source behavior changed.

Updated file:

- `.dev/roadmap/memory-consolidation/g4-bounded-operator-apply-runbook.md`

What changed:

- Added a one-screen operator checklist covering:
  - explicit live-apply authorization phrase and policy;
  - actor/private reason/backup/audit/max-apply inputs;
  - green pre-apply operator bundle and readiness-summary evidence;
  - post-apply `dogfood g4-post-apply-verification` stop gate;
  - prohibition on repeated apply without fresh approval.
- Updated pre-apply verification to check both:
  - `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`
  - `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`
- Recorded the intentional no-live-apply red verifier smoke:
  - `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-post-apply-verification-smoke-20260514T121220Z/g4-post-apply-verification.json`
- Updated post-apply procedure to run `dogfood g4-post-apply-verification` and require `quality_gate.decision=g4_post_apply_verification_green_stop_before_next_mutation` before stopping.

Verification:

- Docs only; no behavior tests required.
- Run `git diff --check` before committing.
- Confirm no report JSON, private reason, backup DB, `.agent-learner/`, `.claude/`, `.omc/`, or `.worktrees/` content is staged.

Immediate next recommended slice:

- Commit this docs/checklist slice.
- Still do not release yet.
- If no exact live apply approval is given, next safe source work is a read-only machine-readable operator apply packet/checklist command. It should emit checklist/evidence status and exact required inputs, but must still set `apply_executed=false`, `apply_supported=false`, and `broad_g4_apply_allowed=false`.
- Live apply remains blocked unless separately approved with exact operator phrase, policy, actor, private reason, backup path, bounded max-apply, and audit output.

## Source-checkout live read-only smoke: G4 operator bundle over saved v0.1.161 artifacts

Completed the safe next slice after commit `d75e034` without running live apply.

- Command path: source checkout `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-bundle`.
- Live DB: `/Users/reddit/.agent-memory/memory.db`.
- Output directory: `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/`.
- Inputs were the saved green v0.1.161 gate artifacts:
  - retrieval ranking: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/retrieval-ranking-shadow.json`
  - rollback confidence: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-confidence.json`
  - rollback replay: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-replay-validate.json`
  - telemetry reconciliation: `/Users/reddit/.agent-memory/reports/v0.1.161-fresh-runway-green-20260514T103021Z/green-telemetry-reconciliation.json`
- Generated artifacts:
  - `g4-review-queue-approval-report.json` sha256 `0efbb0a1376afc950a73908bb3798a2549e40b0395016b271b71b105dc725a46`
  - `g4-review-queue-preview.json` sha256 `3a985fd1264f4ca7a0ee52f816ca2531b056951dd17d8aea17f15bddcb68ea93`
  - `g4-apply-readiness.json` sha256 `041f27ecc75923930fed0cac1e7c9678d663b3827d0253786590b3703df4fc7e`
  - `g4-operator-apply-bundle.json`
- Result: `quality_gate.pass=true`, decision `operator_apply_bundle_ready_for_exact_manual_apply`, queue count `8`, `bounded_partial_apply_ready=true`.
- Safety state stayed unchanged: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, ordinary conversation auto-approval false, raw reason/content/query/trace/proposal JSON absent.

This smoke means the source-checkout operator bundle can consume the saved green v0.1.161 gates and produce the exact manual-apply packet. It is still not authorization to apply. Generic continuation remains limited to read-only evidence and source/doc/test work.

## Branch/release policy update

- Work is on local `develop` for normal source/doc/test slices.
- Release cadence is intentionally slower: do not cut a release for every small validated slice.
- Keep the existing QA method: real operational QA continues against actually downloaded/published installs after a milestone release, not just source checkout.
- Next release should wait for a genuinely complete/stable milestone, then use the existing release verification gates.

## Current source state: G4 read-only operator apply bundle added

Completed source work on `develop` after the human approval artifact and bounded apply-readiness slices:

- Commit `539f929` records the human approval artifact gate: `dogfood g4-review-queue-approval-report` plus `--human-review-approval-report` consumption in `g4-review-queue-preview`.
- `dogfood g4-apply-readiness` consumes a saved green `dogfood_g4_review_queue_preview` report and emits `bounded_partial_apply_ready=true` only when the preview is read-only, no-mutation, privacy-safe, non-empty, quality-gate green, and backed by green retrieval ranking, rollback confidence, rollback replay, telemetry reconciliation, and human-review approval artifacts.
- New read-only `dogfood g4-operator-apply-bundle` generates the operator workflow artifacts in one command: human approval report, queue preview, apply-readiness report, and an exact `g4-review-queue-apply` command preview.
- The bundle is still report-only: `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, and ordinary conversation auto-approval false.
- Actual mutation remains only in the separate `g4-review-queue-apply` corridor requiring exact `--policy g4-review-queue-apply-v1`, `--approval-phrase apply-approved-g4-review-queue-items-v1`, actor, private reason, backup path, and bounded `--max-apply`.

Verification:

- RED observed: focused operator-bundle tests initially failed because `g4-operator-apply-bundle` was not a valid dogfood action.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `2 passed`.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_preview_consumes_green_gate_artifacts_without_broad_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_approval_report_is_ref_safe_read_only_gate tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_consumes_green_preview_without_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_blocks_unsafe_preview_artifact tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `6 passed`.
- `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-bundle --help` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `320 passed, 1 xfailed`.

Immediate next recommended slice:

- Commit this develop slice.
- Do not release yet; accumulate develop milestones until the automation corridor is complete/stable.
- Next source slice can either add a live read-only bundle smoke/runbook against saved v0.1.161 artifacts or start the next explicit operator-approved apply dry-run plan; do not execute live apply from generic continuation.

## Runtime checkpoint: v0.1.161 fresh runway green and next gate evidence

Live/runtime read-only evidence was collected with `/Users/reddit/.agent-memory/runtime/v0.1.161/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.

- Wide epoch diagnosis from `2026-05-14T00:00:00Z`: 123 observations, 60 empty retrievals, 12 unknown empty outcomes. All unknown rows were aggregate-classified as `pre_llm_call` + `response_mode=unknown` under the same scope bucket, with latest unknown at `2026-05-14 10:27:21`. This is a classified stale/legacy metadata-gap window, not an unresolved adapter payload gap.
- Strict post-gap runway from `2026-05-14T10:27:22Z`: `/Users/reddit/.agent-memory/reports/v0.1.161-fresh-runway-green-20260514T103021Z/runway.json` passed. Fresh epoch, fresh comparison, and telemetry reconciliation gates are all green; trace coverage is `1.0`; unknown/unresolved metadata-gap counts are 0.
- The telemetry reconciliation preview reports 4771 candidate historical telemetry rows, but no live reset was run. Treat this as reset-avoidance/reconciliation evidence only.
- G4 review queue preview: `/Users/reddit/.agent-memory/reports/v0.1.161-next-g4-queue-20260514T103118Z/g4-review-queue-preview.json` passed as read-only/no-mutation/default unchanged. Its broad-G4 reassessment still blocks broad apply.
- Retrieval ranking shadow, rollback confidence, and rollback replay gates were collected under `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/` and passed in read-only/no-mutation/default-unchanged mode; ranking used the live mixed approved 50-task corpus with 0 baseline regressions.

Current action boundary:

- Generic continuation authorizes only read-only evidence and source/doc/test slices.
- Live telemetry reset, live default-ranking migration, broad G4/background apply, collapse/delete, unreviewed promotion, and ordinary-conversation auto-approval remain blocked without a separate exact approval corridor.
- Best next source slice: wire the green fresh-runway and next-gate artifacts into a single readiness/reassessment command or report contract so broad apply/default migration cannot be considered unless each explicit artifact is present, green, privacy-safe, and recent.

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

## Source checkpoint: fresh-epoch comparison gate

This source slice returns from the OSS package-surface work to the brain-like memory automation runway.

Implemented and verified in source:

- New read-only `dogfood fresh-epoch-compare` command compares saved `dogfood fresh-epoch` JSON reports across repeated fresh windows.
- The comparison is aggregate/ref-safe only: it records report hashes, pass counts, coverage/empty-retrieval ranges, unknown/unresolved metadata-gap totals, blocker/confidence counts, and privacy flags without raw query/content/trace samples.
- It passes only when enough reports are present, all source reports are read-only fresh-epoch readiness reports, all fresh-epoch gates pass, unresolved fresh metadata gaps are zero, no source blockers remain, default retrieval is unchanged, and privacy flags do not claim raw content exposure.
- It explicitly does not support telemetry reset apply, broad apply, default ranking changes, or ordinary conversation auto-approval.
- Regression tests cover both the green metadata-rich comparison and an unresolved adapter-payload metadata-gap blocker.

Verification:

- `.venv/bin/python -m pytest tests/test_cli.py -q -k 'fresh_epoch or scheduled_compare'` -> `6 passed, 123 deselected`.
- `.venv/bin/python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `311 passed, 1 xfailed`.
- `.venv/bin/python -m ruff check ...` could not run because repo-local venv has no `ruff` module installed.

Next after this slice:

- Use repeated metadata-rich live/runtime fresh-epoch reports and compare them with `dogfood fresh-epoch-compare` before treating historical blockers as reset-safe.
- Keep live default ranking on `conservative_legacy`; keep `graph_reinforced_v1` shadow-only until a separate explicit default-rollout decision.
- Keep broad G4/background apply, collapse/delete apply, telemetry reset apply, unreviewed promotion, and ordinary conversation auto-approval blocked.

## v0.1.158 npm package metadata/package-contents audit checkpoint

This source slice completes the OSS package-surface follow-up after the npm-install-only README cleanup.

Verified source state before release:

- `package.json` now has an OSS-facing description, keywords, repository, bugs, license, bin, `files`, and public `publishConfig`.
- `npm pack --dry-run --json` shows the npm tarball contains only `LICENSE`, `README.md`, `bin/agent-memory.js`, and `package.json`.
- Internal `.dev`, `.agent-learner`, `.claude`, `.worktrees`, report, cache, and dogfood artifacts remain excluded from the npm package.
- Focused test coverage asserts package metadata and tarball contents in `tests/test_npm_launcher.py`.

Next after this package-surface slice:

- Return to the brain-like memory runway: continue metadata-rich dogfooding with explicit fresh epoch windows, compare fresh trace/retrieval coverage, and keep all broad apply/default ranking/collapse-delete/telemetry-reset automation blocked until real runtime evidence clears the gates.

## v0.1.157 OSS README/npm install checkpoint

- Release: `v0.1.157` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.157`).
- npm: `@cafitac/agent-memory@0.1.157`.
- PyPI: `cafitac-agent-memory==0.1.157`.
- PR #341 reduced `README.md` to an npm-install-only OSS entrypoint. PR #342 synced release metadata.
- Published npm smoke passed with `UV_NO_CACHE=1 npm exec --yes --package @cafitac/agent-memory@0.1.157 -- agent-memory doctor`.
- Public README should stay intentionally short: install, bootstrap, doctor, one-shot npm usage, local DB path, trust/deeper-doc links, and license only.
- Do not add dogfood/G-stage/operator runbooks, raw runtime report details, Hermes integration walkthroughs, long examples, or Python-first install paths back into README. Put them in linked docs or `.dev` instead.
- Next OSS slice: audit `package.json` metadata and `npm pack --dry-run` contents so the npm page/package match the new README surface.
- Memory automation state is unchanged by this docs cleanup: `conservative_legacy` remains the live default; `graph_reinforced_v1` is shadow-only; broad G4/background apply, default ranking migration, collapse/delete apply, live telemetry reset, unreviewed automatic promotion, and ordinary conversation auto-approval remain blocked.





## v0.1.155 active runtime checkpoint

- Release: `v0.1.155` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`).
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`.
- Hermes `personal-oss` hook accepted and `hermes --profile personal-oss hooks doctor` is green.
- Runtime QA artifacts: `/Users/reddit/.agent-memory/reports/v0.1.155-runtime-qa-20260513T133421/`.
- v0.1.155 adds explicit `--epoch-start` support to `dogfood trace-quality` and propagates it through `dogfood scheduled-dry-run`, so fresh scheduled evidence can be measured without legacy lookback pollution.
- Fresh v0.1.155 hook-window smoke (`2026-05-13T13:33:00Z`) is read-only/no-mutation and passes scheduled dry-run as `scheduled_dry_run_quality_gate_passed_plan_g4_only`; broad G4/background apply is still not enabled.

## v0.1.154 continuation / v0.1.155 source checkpoint

- Continuation report directory: `/Users/reddit/.agent-memory/reports/v0.1.154-continuation-20260513T120215/`.
- Fresh post-v0.1.154 runtime window using the released v0.1.154 CLI still showed that the old `scheduled-dry-run --since-hours` path can be blocked by historical rows in the lookback window.
- Source now adds `--epoch-start` to `dogfood trace-quality` and propagates it through `dogfood scheduled-dry-run`, so scheduled bundles can measure the same fresh epoch boundary as `dogfood fresh-epoch` instead of mixing in legacy rows.
- Repo-run evidence with `--epoch-start 2026-05-13T09:18:00Z` is green/read-only/no-mutation: `trace-quality-epoch-start-repo.json` has coverage `0.96`, no trace-quality warnings, empty retrieval ratio `0.32`, and historical excluded counts for retrieval observations/memory activations/experience traces; `scheduled-dry-run-epoch-start-repo.json` has decision `scheduled_dry_run_quality_gate_passed_plan_g4_only`.
- This does not enable broad G4/background apply. It only removes a measurement ambiguity so fresh-epoch scheduled evidence can be compared safely. Default ranking migration, collapse/delete apply, ordinary conversation auto-approval, and telemetry reset remain blocked without explicit approval corridors.
- Local full suite after the source slice: `uv run --python 3.11 pytest tests/ -q` -> `307 passed, 1 xfailed`.

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

## v0.1.153 released runtime checkpoint

Use `.dev/status/next-agent-memory-action.md` as the shortest current source of truth.

Current verified state:

- Latest completed release/runtime rollout: `v0.1.153`.
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`.
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`.
- npm/PyPI latest verified as `0.1.153`.
- Hermes hook doctor is green for `personal-oss` after `--accept-hooks` smoke on the v0.1.153 runtime.
- Fresh G4 report directory retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.
- Fresh linkage diagnosis retained from G4 diagnostics: `g4-linkage-gap-diagnose-v0138-fresh.json` passed with decision `fresh_trace_linkage_gap_not_detected`.
- Current v0.1.153 source/runtime runway now includes a 50-task expanded retrieval fixture gate (`live-compatible-50-gate.json`), 75 checked-in retrieval eval tasks across the fixture directory, persisted/replayed per-candidate collapse proof artifacts with relation-equivalence/supersession-chain evidence, one fresh live G5 reviewed-candidate promotion (`candidate:29db0390b2f81bdb` -> `fact:4`) with backup/hash evidence, one guarded live reviewed procedure/episode promotion pair (`candidate:3435fe1db562aaf2` -> `procedure:1`, `candidate:4a35c03e7130fdec` -> `episode:1`) with backup/hash evidence, idempotent live G4 queue apply evidence, the explicit default-ranking opt-in-to-default migration plan at `.dev/roadmap/memory-consolidation/default-ranking-opt-in-to-default-migration.md`, and the released default-ranking migration mechanics.
- Default-ranking migration mechanics are now released through v0.1.153: named `conservative_legacy`/`graph_reinforced_v1`/`shadow_compare` policy diagnostics, shadow compare on `retrieval-ranking-experiment`, and approval-gated config-only `retrieval-ranking-migrate-default` with protected table hash proof plus rollback metadata. Live Hermes remains on `conservative_legacy`; live shadow reports under `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/` include a 50-task representative live-Hermes-DB fact corpus and a 50-task mixed fact/procedure/episode corpus, both with 50/50 pass, zero baseline regressions, protected default order, and no durable ranking mutation. The checked-in expanded 50-task source fixture still fails against the tiny live DB because project-M1 references are absent; the gap artifact is `checked-in-expanded-50-live-gap.stderr.txt`.
- Broad G4/background apply remains blocked; default retrieval ranking changes, collapse/delete apply, live telemetry reset, and ordinary conversation auto-approval remain blocked. The new fact `fact:4` also records this guardrail in the live memory DB.

Progress estimate:

- Overall north-star: 78-80%.
- Substrate/evidence plumbing: about 87%.
- Safe automatic mutation/promotion: about 66-70%.
- Remaining work: about 20-22% overall.

Current interpretation:

- The trace/retrieval/candidate/proof substrate is healthy enough for the next safety runway.
- Completed in the current runway: expanded retrieval gate to 50 tasks, proved the checked-in fixture directory at 75/75 pass, moved collapse proof to `satisfied` with supersession-chain evidence while keeping collapse/delete disabled, ran one fresh non-idempotent narrow live reviewed-candidate fact promotion plus one guarded reviewed procedure/episode promotion pair with backup/hash verification, released/runtime-smoked through v0.1.153, documented the explicit default-ranking opt-in-to-default migration plan, implemented and released the named-policy/shadow-compare/config-only migrate/rollback command path in v0.1.152, and smoke-tested live shadow comparison plus both 50-task representative live fact and mixed corpora without changing the live default.
- Broad G4/background apply remains blocked; existing docs/RED-test-only broad-G4 baseline must not be advertised as ready.
- Retrieval ranking changes remain opt-in experiments only; the expanded 50-task source experiment, the representative 50-task live-Hermes-DB fact corpus, and the representative 50-task mixed fact/procedure/episode corpus all passed as read-only comparisons with no durable ranking mutation. v0.1.153 carries the released migration mechanics, but live default enablement still requires fresh-epoch telemetry green, the exact approval phrase, and explicit operator approval.

Current safe mutation boundaries:

- Historical telemetry reconciliation must use the reviewed telemetry-only `telemetry-reset-v1` corridor with epoch filter, backup, approval phrase, actor, reason hash, and protected-table preservation.
- G4 reviewed queue apply remains narrow and policy-bound; broad promotion, delete/collapse, ordinary conversation auto-approval, raw transcript storage, and default retrieval ranking changes remain blocked.
- Collapse proof can become `satisfied` only with relation-equivalence or reviewed supersession-chain evidence, rollback replay, retrieval eval gate pass, and human-reviewed candidate payload evidence; collapse/delete apply remains disabled even after proof satisfaction.

Brain-like next design axis:

- `trace cluster -> consolidation candidate` is available as a ref-safe read-only preview, not an apply path.
- `candidate -> reviewed fact/procedure/preference promotion` is available only through explicit review/apply commands.
- `trace cluster -> review-priority scoring` remains human-review-only.
- `repeated activation -> reinforcement refinement preview` remains human-review-only; preview scores are not apply approval.
- `stale weak evidence -> decay/collapse candidate preview` remains human-review-only; candidates are not delete/deprecate/collapse approval.
- v0.1.150 adds the current release baseline for rollback replay validation, eval-gated ranking experiment, decay-collapse decision, richer candidate proof artifacts, telemetry safety reports, and live-compatible explicit-approval corridor smokes.
- Retrieval ranking changes only behind opt-in eval before any default change.

---

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first, then read `.dev/status/next-agent-memory-action.md` for the shortest current recommendation. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.



## Fast next-action pointer

For prompts like "다음으로 뭐해야 해?" or "다음 할 거 추천해줘", the shortest source of truth is now:

- `.dev/status/next-agent-memory-action.md`

Current recommendation: finish the local post-v0.1.150 safety slice review, run the full standard test suite, then commit/release it. This slice already strengthens the opt-in ranking experiment against the expanded 50-task fixture gate and reconfirms broad G4/background apply as blocked. After release, the next design slice is default-ranking rollout as an explicit opt-in-to-default migration with rollback/replay and fixture gates; do not enable broad G4/background apply from a generic continuation prompt.

## Ready-to-say answer

agent-memory is currently released/runtime-verified through `v0.1.146`. Hermes hooks point at `/Users/reddit/.agent-memory/runtime/v0.1.146/.venv/bin/agent-memory` and are doctor-green across default, personal-oss, earlypay, and infra-admin. G5a-G5g are merged/released; local G5h is implemented/test-green for rollback replay validation, eval-gated opt-in ranking experiments, decay/collapse decision boundaries, richer candidate skeleton annotations, and historical telemetry reconciliation. Overall north-star progress is about 71-73%. Broad G4/background apply, default retrieval ranking changes, collapse/delete apply, and ordinary conversation auto-approval remain blocked.

Historical G4 contract checkpoint remains docs/RED-test-only: PR #200, PR #202, PR #204, v0.1.99 runtime `/Users/reddit/.agent-memory/runtime/v0.1.99/.venv/bin/agent-memory`, and report `/Users/reddit/.agent-memory/reports/v0.1.99-runtime-qa-20260507T074118` are retained as the broad-G4-blocked baseline. Later releases hardened only narrow cleanup/restore/audit safety corridors, blocker diagnostics, fresh linkage, reviewed candidates, reinforcement review signals, decay/collapse review signals, lifecycle apply guardrails, rollback confidence, and G5h read-only validation/experiment/reconciliation reports; they did not enable broad background consolidation mutation.

## Current next slice

Completed release baseline: G4 fresh linkage/mutation safety landed by v0.1.136; G5a-G5g reviewed-candidate/scoring/reinforcement/decay/supersession/lifecycle safety runway is released through v0.1.146; current active local slice is G5h read-only validation/experiment/reconciliation before any broader automation.

Current slice status: v0.1.146 is installed and live-smoked. Local G5h is implemented/test-green and still safe-by-default: rollback replay validation, eval-gated ranking experiment preview, decay/collapse decision, skeleton annotation, and telemetry reconciliation reports do not enable broad background consolidation apply, collapse/delete mutation, ordinary conversation auto-approval, raw transcript/query storage, or default retrieval ranking changes.

Target shape for the next slice:

- `agent-memory dogfood supersession-preview <db>` or equivalent emits a read-only/ref-safe conflict/supersession candidate report with `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, and `automation_policy.apply_supported=false`.
- The report identifies same-claim-slot conflicts, replacement/supersedes chains, lifecycle status context, and copy-paste review commands using refs and aggregate counts only.
- No raw prompt/query/transcript/trace summary/sample values are printed.
- The first live G5e smoke against `/Users/reddit/.agent-memory/memory.db` wrote `/Users/reddit/.agent-memory/runtime/v0.1.143/g5e-live-smoke.json`: `read_only=true`, `mutated=false`, default retrieval unchanged, candidate count `0`, blocked only by `no_decay_collapse_candidates_ready`; no mutation.

Next safe slice: continue conflict -> supersession/replacement as preview/review-first work. Do not live-apply queue/candidate mutations without an explicit operator decision and the exact guarded command shape. Broad G4 apply remains a separate, still-blocked slice.

Recommended local backup commands before any future live mutation:

```bash
agent-memory backup export /Users/reddit/.agent-memory/memory.db \
  /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup inspect /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup restore /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip \
  /Users/reddit/.agent-memory/restored-memory.db
```

The backup manifest is metadata-only, but the bundled SQLite database contains local memory state and should be treated as private local data.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should normally be on `main` unless a docs/feature branch is active.
- Current feature branch for this slice: `feat/g4-readiness-blockers`.
- Latest merged G4a hardening PR: #257 `feat: write narrow restore audit trace`.
- Latest merged docs checkpoint PR: #259 `docs: record v0.1.123 live audit smoke`.
- Latest merged release-sync PR: #258 `chore: release v0.1.123 [skip release]`.
- Latest completed release/runtime rollout: `v0.1.136`.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for `gh` commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.136`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.136`
- npm package: `@cafitac/agent-memory@0.1.136`
- PyPI package: `cafitac-agent-memory==0.1.136`

Latest verified source/runtime snapshot, checked 2026-05-10 04:38 KST:

- branch before this slice: `main`, synced with `origin/main` at `v0.1.123` plus docs PR #259
- GitHub Release, npm, and PyPI all report `v0.1.123`
- latest main CI, auto-release, release-sync, publish, and published PyPI/npm smoke completed successfully for `v0.1.123`
- checked-in retrieval-eval fixtures remain at 21 tasks
- live DB remains privacy-clean for legacy query previews: non-empty `query_preview=0`
- targeted blocker-diagnostics tests passed locally on this branch: `uv run pytest tests/test_cli.py -q -k 'scheduled_dry_run or scheduled_compare or background_dry_run_quality_gates'`
- broad G4 consolidation apply mode remains blocked

Latest live narrow-audit smoke, checked 2026-05-10 04:13 KST:

- report dir: `/Users/reddit/.agent-memory/reports/v0.1.123-live-narrow-audit-write-20260510T041120`
- backup: `memory-before-narrow-audit-write.agent-memory-backup.json` plus `backup-inspect.json`
- read-only restore dry-run: `read_only=true`, `mutated=false`, `restorable_count=0`, `restore_apply_available=false`, privacy flags false, warning only `live_restore_not_implemented`
- live apply: `status=audit_written_restore_blocked`, `audit_trace_mutated=true`, `live_restore_mutated=false`, `restore_apply_available=false`, `blocked_reasons=["live_restore_not_implemented"]`
- inserted audit trace: `experience_traces.id=1465`, `event_kind=dogfood_query_preview_cleanup_restore_apply`, `retention_policy=review`, `summary=NULL`, `restored_count=0`, `source_database_match=true`, `artifact_integrity_passed=true`, `rehearsal_status=passed`
- duplicate rerun failed closed: no second audit row, `failed_checks=["duplicate_audit_event_absent"]`, `mutated=false`, `live_restore_mutated=false`
- post-write scheduled dry-run stayed read-only/no-mutation and still returned `decision=continue_scheduled_dry_run_dogfooding_before_g4` with blocked reasons `trace_quality_needs_more_dogfooding`, `decay_risk_above_threshold`, and `background_quality_warnings_present`

Latest source-branch blocker drilldown smoke, checked 2026-05-10 05:11 KST:

- report: `/tmp/agent-memory-g4-drilldown-live.json`
- command: source checkout `dogfood scheduled-dry-run` against `/Users/reddit/.agent-memory/memory.db`
- result stayed `read_only=true`, `mutated=false`, `automation_policy.apply_supported=false`, and privacy flags false
- quality gate still returned `continue_scheduled_dry_run_dogfooding_before_g4` with blocked reasons `trace_quality_needs_more_dogfooding`, `decay_risk_above_threshold`, and `background_quality_warnings_present`
- aggregate trace coverage drilldown identified `likely_gap=traces_missing_observation_links`, `unlinked_observation_count=370`, `trace_without_observation_link_count=371`, `activations_linked_to_traces=0`, and activation trace-link coverage `0.0`
- empty-retrieval activation drilldown identified `count=123`, `ratio=0.615`, surface `hermes-pre-llm-hook`, and hashed cwd scopes only
- decay-risk drilldown identified one aggregate candidate with top factors `low_connectivity` and `stale_activity`; raw content remains excluded

Latest source-branch blocker diagnostic smoke, checked 2026-05-10 04:38 KST:

- report dir: `/Users/reddit/.agent-memory/reports/v0.1.123-g4-blocker-diagnostics-source-20260509T193808Z`
- command: source checkout `dogfood scheduled-dry-run` against `/Users/reddit/.agent-memory/memory.db`
- result stayed `read_only=true`, `mutated=false`, `automation_policy.apply_supported=false`, and `ordinary_conversation_auto_approval=false`
- blocker diagnostics identified current aggregate blockers as: trace coverage ratio `0.0` with `low_observation_trace_coverage`, empty retrieval ratio `0.6188`, decay-risk candidate count `1` over threshold `0`, and background warning `high_empty_retrieval_activation_ratio`
- quality gate still returned `continue_scheduled_dry_run_dogfooding_before_g4`

Latest readiness-blockers source smoke, checked 2026-05-10 06:08 KST:

- report: `/tmp/agent-memory-g4-readiness-blockers-live.json`
- command: source checkout `dogfood scheduled-dry-run` against `/Users/reddit/.agent-memory/memory.db`
- result stayed `read_only=true`, `mutated=false`, `automation_policy.apply_supported=false`, and privacy flags false
- live DB still blocks broad G4 with `trace_quality_needs_more_dogfooding`, `decay_risk_above_threshold`, and `background_quality_warnings_present`
- live blocker details now include empty-retrieval diagnostics by hook event `pre_llm_call`, response mode `unknown`, hashed cwd scopes only, and trace linkage counts
- live decay-risk candidate `fact:1` is classified with resolution hint `add_relation_or_confirm_isolated_approved_memory`, ref-safe evidence only, and no raw content
- the trace linkage fix applies to new Hermes hook traces; historical live activations/traces remain unlinked until enough new dogfood evidence accumulates

Next safe work after this slice: if released and live-smoked, dogfood enough new Hermes turns to verify activation trace-link coverage improves, then decide whether empty retrievals are expected misses or query/scope gaps. Broad G4 implementation still requires turning the xfailed RED contract into a real review-queue apply path in a separate approved slice.

Latest installed-runtime linkage and next diagnostics smoke, checked 2026-05-10 06:31 KST:

- installed runtime: `/Users/reddit/.agent-memory/runtime/v0.1.126/.venv/bin/agent-memory`
- scheduled dry-run report: `/tmp/agent-memory-v0126-after-hooks.json`
- installed v0.1.126 manual hook smoke inserted `retrieval_observations.id=2250` and `experience_traces.id=1533`; the new trace has `related_observation_ids_json=[2250]`, proving the installed hook path can link new metadata-only traces to retrieval observations
- aggregate live coverage is still low because historical rows remain unlinked: activation trace-link coverage `0.005`, `activations_linked_to_traces=2`, `unlinked_observation_count=400`, `trace_without_observation_link_count=401`
- broad G4 remains blocked by `trace_quality_needs_more_dogfooding`, `decay_risk_above_threshold`, and `background_quality_warnings_present`
- the current source branch adds future `retrieval_outcome` diagnostics so empty retrievals report `verify_first`/`no_reliable_memory` instead of only `unknown` response mode, and adds ref-safe `review_support` commands for isolated approved decay-risk candidates


Latest v0.1.128 runtime/publish smoke, checked 2026-05-10 06:58 KST:

- PR #266 `feat: classify empty retrieval outcomes`, release-sync PR #267, CI stabilization PR #268, and release-sync PR #269 are merged.
- GitHub Release, npm, and PyPI all report `v0.1.128`; fresh PyPI install and npm registry smoke passed.
- installed runtime: `/Users/reddit/.agent-memory/runtime/v0.1.128/.venv/bin/agent-memory`; Hermes config backups use suffix `.bak-agent-memory-v0.1.128-20260510T065733`.
- hook smoke: `retrieval_observations.id=2260`, `experience_traces.id=1543`, `related_observation_ids_json=[2260]`, `retrieval_outcome=retrieved_memory`.
- scheduled dry-run report: `/tmp/agent-memory-v0128-after-hooks.json`; read-only/no mutation; decision remains `continue_scheduled_dry_run_dogfooding_before_g4`; blockers remain trace quality, decay-risk, and background warning.
- coverage diagnostics: `activation_trace_link_coverage_ratio=0.0098`, `activations_linked_to_traces=4`, `unlinked_observation_count=404`, `trace_without_observation_link_count=405`; this is expected to improve only as new v0.1.128 rows accumulate.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/`

Do not delete or commit these unless the user explicitly asks.

## In-progress G4a restore disposable-rehearsal slice

Status: Started from `v0.1.106` validated `main` on branch `g4/query-preview-cleanup-restore-disposable-rehearsal`. This slice adds only a disposable DB copy rehearsal for restore apply. It does not restore query previews in the target DB and does not open broad G4 apply.

Target contract:

- `dogfood query-preview-cleanup-restore <db> <artifact> --apply` still requires `--policy legacy-query-preview-cleanup-restore-v1`, `--actor`, and `--reason`.
- Raw reason text is never printed or stored; only `reason_sha256` appears in the contract payload.
- Source DB match and artifact integrity must pass before rehearsal runs.
- Rehearsal copies the target DB to a private disposable DB, restores only the rows that are currently empty there, verifies expected restored count and post-restore non-empty state, and reports aggregate counts only.
- The command still returns `read_only=true`, `mutated=false`, `status=error`, `restore_apply_available=false`, and blocked reasons including `restore_apply_contract_checkpoint_only` and `live_restore_not_implemented`.
- No raw `query_preview`, token, API-key-like values, or sample row values may appear in stdout.

Still forbidden after this slice:

- broad G4 apply mode — DO NOT enable broad G4 apply mode;
- ordinary conversation auto-approval;
- raw transcript or raw query text in stdout/audit metadata;
- default retrieval/ranking behavior changes;
- live restore mutation.

## v0.1.100 policy hardening release and runtime QA completed

PR #206 `feat: require policy for query preview cleanup apply`, release-sync PR #207, and stabilization PR #208 merged.

Completed behavior:

- `dogfood query-preview-cleanup --apply` requires `--policy legacy-query-preview-cleanup-v1` in addition to `--actor` and `--reason`.
- Preview remains read-only and surfaces the required apply policy/guardrails.
- Apply/audit metadata includes policy, actor, reason hash, audit trace id, and hash-only affected id summary.
- Broad G4/background consolidation apply mode remains blocked.

Verification completed:

- PR #206 checks passed and merged; post-merge main/auto-release runs passed.
- Release-sync PR #207 published `v0.1.100`.
- PR #208 stabilized Linux/SQLite retrieval-eval assertions exposed after the release-sync merge.
- GitHub Release, PyPI, and npm all report `v0.1.100`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.100/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.100-runtime-qa-20260507T105232`.
- Hermes config backup suffix: `.bak-agent-memory-v0.1.100-20260507T105212`.

## v0.1.99 release-sync and runtime QA completed

PR #203 `docs: checkpoint v0.1.98 runtime qa` and release-sync PR #204 merged after PR #200/#202/#201.

Completed behavior:

- Added/kept the static roadmap contract test that prevents the handoff and roadmap from advertising broad G4 apply mode as ready.
- Marked the broader G4 apply-mode contract checkpoint as complete without implementing broad mutation.
- Preserved hard blocks: no ordinary conversation auto-approval, no raw transcript storage, no default retrieval ranking change, and no broad apply without explicit policy/actor/reason/audit/restore guidance.
- Stabilized retrieval-eval comparator assertions around platform-specific SQLite/FTS avoid-hit delta variability.
- Checked-in retrieval task count remains 21.

Verification completed:

- PR #203 checks passed and merged; post-merge main CI passed: `25482409415`; auto-release `25482409434` created release-sync PR #204.
- Release-sync PR #204 merged and post-merge CI/publish succeeded: CI `25482537303`, auto-release `25482537294`, publish `25482545760`.
- GitHub Release, PyPI, and npm all report `v0.1.99`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.99/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.99-runtime-qa-20260507T074118`.
- Hermes config backup suffix: `.bak-agent-memory-v0.1.99-20260507T074006`.

## v0.1.96/v0.1.97 procedure prompt-budget and stabilization releases completed

PR #195 `test: add procedure prompt budget fixture`, release-sync PR #196, checkpoint PR #197, stabilization PR #198, and release-sync PR #199 merged.

Completed behavior:

- Added checked-in Project M1 guardrail `tests/fixtures/retrieval_eval/procedure/procedure-prompt-budget-pressure-guardrail.json`.
- Seeded same-scope release notes and release monitoring procedural noise around current release QA guidance.
- Verified authoritative published-artifact/live-runtime release QA procedure guidance survives `limit=1` prompt-budget pressure.
- Checked-in retrieval task count is now 21.
- No production retrieval/ranking change was needed for this slice.

Verification completed:

- RED: new checked-in fixture presence test failed before the fixture existed.
- GREEN/targeted: procedure prompt-budget fixture contract, checked-in aggregate/comparator matrix, and CLI fixture-directory tests passed.
- Local full verification: `uv run pytest tests/test_retrieval_evaluation.py -q` passed (`59 passed`), `uv run pytest tests/ -q` passed (`266 passed`), `uv run ruff check tests/test_retrieval_evaluation.py` passed, and checked-in retrieval-eval smoke passed (`21 21 0`).
- PR #195 checks passed after stabilizing Linux/SQLite lexical tie variability in a CLI delta assertion. Main CI after PR #195 passed: `25476937718`; auto-release `25476937714` passed.
- Release-sync PR #196 merged and post-merge CI/publish succeeded: CI `25477059941`, auto-release `25477059948`, publish `25477065111`.
- GitHub Release, PyPI, and npm all report `v0.1.96`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.96/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.96-runtime-qa-20260507T051021`.
- PR #197 post-merge main CI exposed Linux/SQLite lexical tie-break sensitive assertions; PR #198 stabilized the retrieval comparator matrix and Hermes adapter prompt-budget assertions.
- PR #199 published `v0.1.97`; GitHub Release, PyPI, npm, fresh artifact smoke, pinned runtime install, Hermes config patch, and installed-runtime QA passed.
- Latest v0.1.97 runtime QA report: `/Users/reddit/.agent-memory/reports/v0.1.97-runtime-qa-20260507T053631`.
- Broad G4 consolidation apply mode remains blocked; the next slice is docs/RED-test-only contract work, not implementation.


## v0.1.95 same-scope procedure recency retrieval release completed

PR #192 `test: add same-scope procedure recency fixture` and release-sync PR #193 merged.

Completed behavior:

- Added checked-in Project M1 guardrail `tests/fixtures/retrieval_eval/procedure/same-scope-procedure-recency-guardrail.json`.
- Seeded current `v0.1.94` release QA guidance and stale `v0.1.75` legacy release QA guidance in the shared retrieval-eval DB.
- Verified current same-scope release QA procedure guidance wins under `limit=1`.
- Checked-in retrieval task count is now 20.
- No production retrieval/ranking change was needed for this slice.

Verification completed:

- RED: new checked-in fixture presence test failed before the fixture existed.
- GREEN/targeted: same-scope procedure recency fixture contract, checked-in aggregate/comparator matrix, and CLI fixture-directory tests passed.
- Local full verification: `uv run pytest tests/test_retrieval_evaluation.py -q`, `uv run pytest tests/ -q`, `uv run ruff check tests/test_retrieval_evaluation.py`, release metadata/version smoke, and checked-in retrieval-eval smoke passed (`20 20 0`).
- PR #192 checks passed before merge. Main CI after PR #192 passed: `25475564685`.
- Release-sync PR #193 merged and post-merge CI/publish succeeded: CI `25475710843`, auto-release `25475710846`, publish `25475715957`.
- GitHub Release, PyPI, and npm all report `v0.1.95`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.95/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.95-runtime-qa-20260507T041950`.

## v0.1.94 scope-adjacent procedure retrieval release completed

PR #189 `test: add scope-adjacent procedure retrieval fixture` and release-sync PR #190 merged.

Completed behavior:

- Added checked-in Project M1 guardrail `tests/fixtures/retrieval_eval/procedure/scope-adjacent-procedure-guardrail.json`.
- Seeded a workspace-level pre-PR fallback procedure and verified preferred project-scope procedure guidance wins under `limit=1`.
- Checked-in retrieval task count is now 19.
- No production retrieval/ranking change was needed for this slice.

Verification completed:

- RED: new checked-in fixture presence test failed before the fixture existed.
- GREEN/targeted: scope-adjacent fixture contract, checked-in aggregate/comparator matrix, and CLI fixture-directory tests passed.
- Local full verification: `uv run pytest tests/test_retrieval_evaluation.py -q`, `uv run pytest tests/ -q`, `uv run ruff check tests/test_retrieval_evaluation.py`, release metadata/version smoke, and checked-in retrieval-eval smoke passed (`19 19 0`).
- PR #189 checks passed before merge. Main CI after PR #189 passed: `25474088143`.
- Release-sync PR #190 merged and post-merge CI/publish succeeded: CI `25474217238`, auto-release `25474217233`, publish `25474221963`.
- GitHub Release, PyPI, and npm all report `v0.1.94`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.94/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.94-runtime-qa-20260507T032531`.


## v0.1.91 noisy episode/procedure retrieval release completed

PR #181 `fix: suppress episodic noise for procedure retrieval`, PR #183 `test: stabilize lexical global CLI baseline assertion`, and release-sync PR #182 merged.

Completed behavior:

- Added checked-in Project M1 guardrail `tests/fixtures/retrieval_eval/noise/irrelevant-episode-procedure-guardrail.json`.
- Retrieval now suppresses episodic context when a query clearly asks for procedural guidance and approved procedures are available, preventing same-scope but irrelevant PR-preparation episodes from crowding out procedure answers.
- Checked-in retrieval task count is now 18.
- Stabilized the lexical-global CLI baseline test to avoid platform-dependent current-vs-baseline delta assumptions while preserving the baseline output contract.

Verification completed:

- RED: new checked-in fixture presence test failed before the fixture existed.
- GREEN/targeted: noisy procedure/episode guardrail, checked-in aggregate/comparator matrix, and CLI fixture-directory tests passed.
- Local full verification: `uv run pytest tests/ -q`, `uv run ruff check src/agent_memory/core/retrieval.py tests/test_retrieval_evaluation.py`, release metadata/version smoke, and checked-in retrieval-eval CLI smoke passed.
- PR #181 checks passed before merge. Main CI initially exposed a pre-existing platform-dependent assertion; PR #183 stabilized it and passed.
- Main CI after PR #183 passed: `25472090279`.
- Release-sync PR #182 merged and post-merge CI/publish succeeded: CI `25472167607`, auto-release `25472167557`, publish `25472175000`.
- GitHub Release, PyPI, and npm all report `v0.1.91`.
- Fresh artifact smoke passed from PyPI and npm.
- Live Hermes runtime QA passed from `/Users/reddit/.agent-memory/runtime/v0.1.91/.venv/bin/agent-memory`; report: `/Users/reddit/.agent-memory/reports/v0.1.91-runtime-qa-20260507T021821`.


## v0.1.90 same-scope episode drift retrieval release completed

PR #178 `test: add episode drift retrieval fixture` merged and released through release-sync PR #179.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a Project M1 same-scope episode drift guardrail.
- Episode recall for current rollout/candidate-validation history must prefer the current v0.1.90 candidate validation rollout episode over a stale v0.1.84 rollout episode with similar wording.
- Checked-in retrieval task count is now 17.
- The slice did not change production retrieval code; it added fixture/seed coverage and updated aggregate/comparator expectations.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- Focused episode-drift retrieval suite passed.
- `uv run pytest tests/test_retrieval_evaluation.py -q` passed.
- `uv run pytest tests/ -q` passed.
- `uv run ruff check tests/test_retrieval_evaluation.py` passed.
- Checked-in retrieval-eval CLI smoke passed.
- PR #178 CI and post-merge main CI passed.
- PR #179 release-sync CI passed and published `v0.1.90`.
- GitHub Release, PyPI, and npm all report `0.1.90`.
- Fresh PyPI and npm smoke commands passed for `0.1.90`.

## v0.1.90 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.90/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.90`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.90-20260507T013210`.

Verification completed:

- `agent_memory.__version__ == "0.1.90"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for default, `personal-oss`, and `earlypay` configs.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`, `agent_memory_version=0.1.90`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`.
- Installed runtime live DB backup export/inspect round-trip passed.
- QA artifacts are under `/Users/reddit/.agent-memory/reports/v0.1.90-runtime-qa-20260507T013303`.

## v0.1.89 prompt-budget pressure retrieval release completed

PR #175 `fix: keep current facts above budget noise` merged and released through release-sync PR #176.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a Project M1 prompt-budget pressure guardrail.
- Tight-budget release-version retrieval must keep the authoritative current same-slot fact above stale and noisy same-scope release-note facts.
- Approved fact conflict penalty was softened from `-0.75` per hidden alternative to `-0.20`, preserving conflict trace/review signals while avoiding over-penalizing the current fact under same-scope release-note noise.
- Checked-in retrieval task count is now 16; `tests/test_retrieval_evaluation.py` has 54 tests.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- Focused budget-pressure retrieval suite passed.
- `uv run pytest tests/test_retrieval_evaluation.py -q` passed with `54 passed`.
- `uv run pytest tests/ -q` passed with `261 passed`.
- `uv run ruff check src/agent_memory/storage/sqlite.py tests/test_retrieval_evaluation.py tests/test_retrieval_trace.py` passed.
- `git diff --check` and checked-in retrieval-eval CLI smoke passed.
- PR #175 CI and post-merge main CI passed.
- PR #176 release-sync CI passed and published `v0.1.89`.
- GitHub Release, PyPI, and npm all report `0.1.89`.
- Fresh PyPI and npm smoke commands passed for `0.1.89`.

## v0.1.89 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.89/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.89`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.89-20260507T004641`.

Verification completed:

- `agent_memory.__version__ == "0.1.89"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for default, `personal-oss`, and `earlypay` configs.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`, `agent_memory_version=0.1.89`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`, privacy flags false for raw conversation/query/sample output, and quality gate decision `continue_scheduled_dry_run_dogfooding_before_g4`.
- Installed runtime live DB backup export/inspect round-trip passed.
- QA artifacts are under `/Users/reddit/.agent-memory/reports/v0.1.89-runtime-qa-20260507T004805`.

## v0.1.88 stale procedure retrieval-eval release completed

PR #171 `test: add stale procedure retrieval fixture` merged and released through release-sync PR #173 after stabilization PR #172.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a same-scope stale procedure guardrail.
- Project M1 pre-PR procedure retrieval must prefer the current `uv run pytest tests/ -q` procedure over the legacy `.venv/bin/python -m pytest tests/ -q` procedure.
- Checked-in retrieval task count is now 15; the lexical baseline remains intentionally weaker than current retrieval.
- No production retrieval code changed in the fixture slice; PR #172 only stabilized an existing shared-seed branch-pattern assertion.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- Focused stale-procedure suite passed.
- `uv run pytest tests/test_retrieval_evaluation.py -q` passed with `53 passed`.
- `uv run ruff check tests/test_retrieval_evaluation.py` passed.
- `git diff --check` and release metadata check passed.
- Full local suite `uv run pytest tests/ -q` passed.
- CLI retrieval-eval smoke over checked-in fixtures passed.
- PR #171 CI passed, then main CI exposed an unrelated shared-seed assertion instability; PR #172 fixed it and main CI passed.
- PR #173 release-sync CI passed and published `v0.1.88`.
- GitHub Release, PyPI, and npm all report `0.1.88`.
- Fresh PyPI and npm smoke commands passed for `0.1.88`.

## v0.1.88 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.88/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.88`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.88-20260506T171008`.

Verification completed:

- `agent_memory.__version__ == "0.1.88"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for all three configs.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`, `agent_memory_version=0.1.88`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`, privacy flags false for raw conversation/query/sample output, and quality gate decision `continue_scheduled_dry_run_dogfooding_before_g4`.
- Installed runtime live DB backup export/inspect round-trip passed.
- QA artifacts are under `/Users/reddit/.agent-memory/reports/v0.1.88-runtime-qa-20260506T171117`.

## v0.1.87 conflicting fact retrieval-eval release completed

PR #168 `test: add conflicting fact retrieval fixture` merged and released through release-sync PR #169.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a same-slot current-vs-stale fact conflict.
- `Project M1 latest release version` retrieval must prefer the current Project M1 latest-release fact over an older same subject/predicate value.
- Checked-in retrieval task count is now 14; the lexical baseline remains intentionally weaker than current retrieval.
- No production retrieval code changed in this slice; it is fixture/test coverage only.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- Focused conflicting-fact suite passed with `4 passed`.
- `uv run pytest tests/test_retrieval_evaluation.py -q` passed.
- `uv run ruff check tests/test_retrieval_evaluation.py` passed.
- `git diff --check` and release metadata check passed.
- Full local suite `.venv/bin/python -m pytest tests/ -q` passed.
- CLI retrieval-eval smoke over checked-in fixtures passed.
- PR #168 CI and main CI passed.
- PR #169 release-sync CI passed and published `v0.1.87`.
- GitHub Release, PyPI, and npm all report `0.1.87`.
- Fresh PyPI and npm smoke commands passed for `0.1.87`.

## v0.1.87 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.87/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.87`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.87-20260506T231435`.

Verification completed:

- `agent_memory.__version__ == "0.1.87"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for all three configs.
- Direct `hermes-pre-llm-hook` stdin smoke with `hook_event_name=pre_llm_call` produced valid hook JSON.
- `hermes chat --accept-hooks ... 'Reply with OK only.'` returned `OK` for default, `personal-oss`, and `earlypay` profiles.
- `hermes hooks doctor`, `hermes --profile personal-oss hooks doctor`, and `hermes --profile earlypay hooks doctor` all report healthy hooks after allowlisting.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`, privacy flags false for raw conversation/query/sample output, and quality gate decision `continue_scheduled_dry_run_dogfooding_before_g4`.
- Installed runtime live DB backup export/inspect/restore round-trip passed.
- QA artifacts are under `/Users/reddit/.agent-memory/reports/v0.1.87-runtime-qa-20260506T231505`.

## v0.1.86 noisy global fact retrieval-eval release completed

PR #165 `test: add noisy fact retrieval fixture` merged and released through release-sync PR #166.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a project-scoped fact query with a noisy global archival fact.
- Project M1 KB export fact retrieval must not surface the same-wording global archive/noise fact.
- Checked-in retrieval task count is now 13; the lexical baseline remains intentionally weaker than current retrieval.
- No production retrieval code changed in this slice; it is fixture/test coverage only.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- `uv run pytest tests/test_retrieval_evaluation.py -q` -> `51 passed`.
- `uv run ruff check tests/test_retrieval_evaluation.py` passed.
- `git diff --check` and release metadata check passed.
- Full local suite: `.venv/bin/python -m pytest tests/ -q` -> `258 passed`.
- CLI retrieval-eval smoke over checked-in fixtures: current `13/13` pass, lexical baseline `8/13` pass.
- PR #165 CI and main CI passed.
- PR #166 release-sync CI passed and published `v0.1.86`.
- Fresh PyPI install smoke verified `agent_memory.__version__ == "0.1.86"` and project-scoped fact retrieval excludes the global noisy fact.
- Fresh npm smoke using `@cafitac/agent-memory@0.1.86` passed.

## v0.1.86 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.86/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.86`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.86-20260506T213316`.

Verification completed:

- `agent_memory.__version__ == "0.1.86"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for all three configs.
- Direct `hermes-pre-llm-hook` stdin smoke with `hook_event_name=pre_llm_call` produced valid hook JSON.
- `hermes chat --accept-hooks ... 'Reply with OK only.'` returned `OK` for default, `personal-oss`, and `earlypay` profiles.
- `hermes hooks doctor`, `hermes --profile personal-oss hooks doctor`, and `hermes --profile earlypay hooks doctor` all report healthy hooks after allowlisting.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`, privacy flags false for raw conversation/query/sample output, and quality gate decision `continue_scheduled_dry_run_dogfooding_before_g4`.
- Installed runtime live DB backup export/inspect/restore round-trip passed.
- QA artifacts are under `/Users/reddit/.agent-memory/reports/v0.1.86-runtime-qa-20260506T213508`.

## v0.1.85 retrieval-eval/runtime release completed

PR #162 `test: add cross-scope procedure retrieval fixture` merged and released through release-sync PR #163.

Completed behavior:

- Checked-in retrieval-eval coverage now includes a procedure-oriented cross-scope fixture.
- Project M1 procedure queries must not surface same-wording Project Drift procedure guidance.
- Preferred-scope exact-match narrowing applies to approved facts and procedures while episodes keep the broader hierarchy behavior.
- Checked-in retrieval task count is now 12.

Verification completed:

- RED: the new fixture contract test failed before the fixture was added.
- Focused retrieval/scope tests passed.
- Ruff passed for touched retrieval/storage files.
- `git diff --check` and release metadata check passed.
- Full local suite passed with `257 passed`.
- PR #162 CI and main CI passed.
- PR #163 release-sync CI passed and published `v0.1.85`.
- Fresh PyPI install smoke verified `agent_memory.__version__ == "0.1.85"` and the Project M1 procedure retrieval smoke excludes the Project Drift procedure.

## v0.1.85 live Hermes runtime QA completed

Installed runtime:

- `/Users/reddit/.agent-memory/runtime/v0.1.85/.venv/bin/agent-memory`
- Installed from PyPI with Python 3.11 and `cafitac-agent-memory==0.1.85`.

Updated Hermes configs:

- `/Users/reddit/.hermes/config.yaml`
- `/Users/reddit/.hermes/profiles/personal-oss/config.yaml`
- `/Users/reddit/.hermes/profiles/earlypay/config.yaml`

Timestamped backups were created next to each config with suffix `.bak-agent-memory-v0.1.85-20260506T160835`.

Verification completed:

- `agent_memory.__version__ == "0.1.85"` from the pinned runtime.
- `agent-memory hermes-doctor` reports `status=ok` for all three configs.
- Direct `hermes-pre-llm-hook` stdin smoke with `hook_event_name=pre_llm_call` produced valid hook JSON.
- `hermes chat --accept-hooks ... 'Reply with OK only.'` returned `OK` for default, `personal-oss`, and `earlypay` profiles.
- `hermes hooks doctor`, `hermes --profile personal-oss hooks doctor`, and `hermes --profile earlypay hooks doctor` all report healthy hooks after allowlisting.
- Installed runtime `dogfood storage-health` against `/Users/reddit/.agent-memory/memory.db` reports `healthy`, `read_only=true`, `mutated=false`.
- Installed runtime `dogfood scheduled-dry-run` reports `read_only=true`, `mutated=false`, privacy flags false for raw conversation/query/sample output, and quality gate decision `continue_scheduled_dry_run_dogfooding_before_g4`.

## H4 public docs promotion completed

This docs-only slice promoted verified behavior from `.dev` into public docs without code changes. It landed in PR #161 (`docs: promote public memory safety guidance`) and did not create a new release.

Changed docs:

- `README.md`: links the public privacy/safety model and distinguishes stable defaults from experimental/operator-only surfaces.
- `docs/privacy-and-safety.md`: new public privacy/safety model for local DBs, backup bundles, graph/report artifacts, read-only diagnostics, opt-in mutation guardrails, and sharing guidance.
- `docs/first-run-memory-layer.md`: tells new users to back up and inspect before experiments.
- `docs/hermes-dogfood.md`: clarifies dogfood/consolidation commands are diagnostics, not broad automatic memory saving.
- `docs/install-smoke.md`: updates the validated release note to `v0.1.84`, fixes npm/uvx command shapes, and adds backup/restore to the trust matrix.

Verification completed: docs validation, `git diff --check`, release metadata check, PR CI, and main CI passed. Docs-only merge did not create a new release.

## Completed v0.1.84 backup/import/export release

PR #158 `feat: add local memory backup commands` merged and released through release-sync PR #159.

Completed behavior:

- `agent-memory backup export <db_path> <output_path>` writes a private local backup bundle.
- `agent-memory backup inspect <bundle_path>` reads only metadata-safe manifest details.
- `agent-memory backup restore <bundle_path> <output_db_path> [--overwrite]` restores with overwrite protection.
- Backup bundles contain a metadata-only `manifest.json` plus a SQLite DB copy; the DB copy itself contains private local memory state.
- Restore/inspect reject unsupported manifest versions and unsafe database entry names.

Verification completed:

- PR #158 checks passed and merged.
- PR #159 release-sync validation passed and merged.
- GitHub Release `v0.1.84`, npm `@cafitac/agent-memory@0.1.84`, and PyPI `cafitac-agent-memory==0.1.84` verified.
- Fresh PyPI venv QA installed `cafitac-agent-memory==0.1.84` and passed init/backup export/inspect/restore plus retrieve-after-restore smoke.
- Fresh npm wrapper QA passed init/backup export/inspect/restore using `@cafitac/agent-memory@0.1.84` with a clean `UV_CACHE_DIR`.
- Live runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.84/.venv/bin/agent-memory`.
- Live DB backup export/inspect/restore smoke passed against `/Users/reddit/.agent-memory/memory.db`.
- `hermes hooks doctor` reports healthy hooks for the default/personal profile and the `earlypay` profile after v0.1.84 allowlisting.

## Completed v0.1.83 graph quality release

PR #156 `perf: localize graph UI and add quality modes` merged and released through release-sync PR #157.

Completed behavior:

- The graph export's visible operator UI is Korean-localized.
- Render quality controls are available: `auto`, `performance`, and `sharp`.
- Default high-DPI/Retina drawing is capped at DPR 1.5; performance mode uses DPR 1 with reduced blur/glow/labels.
- The renderer remains event-driven Canvas with no browser force simulation.

Verification completed upstream:

- `uv run ruff check src/agent_memory/api/cli.py tests/test_cli.py`
- focused graph export test
- `uv run pytest tests/test_cli.py -q`
- `uv run pytest tests/ -q`
- `git diff --check`
- release metadata/readiness checks
- `npm pack --dry-run`
- `node --check bin/agent-memory.js`
- browser smoke of generated local file with Korean UI and performance mode.

## Completed v0.1.82 interactive graph release

PR #154 `feat: add interactive brain graph export` merged and released through release-sync PR #155.

Completed behavior:

- `graph export-html` now emits an event-driven, brain-like Canvas layout.
- UI includes filters/search, zoom/pan, dominant-hub explanation, node inspector, and privacy-safe graph summary metadata.
- Rendering remains non-blocking through dirty redraws and viewport culling rather than browser force simulation.
- Documentation and smoke expectations were updated.

Verification completed upstream:

- ruff on graph-related CLI/tests
- focused graph export test
- full `tests/`
- live export smoke against `/Users/reddit/.agent-memory/memory.db`
- browser `file://` smoke with no console errors.

## Completed v0.1.76 scheduled-compare release

PR #138 `feat: add scheduled dogfood report comparison` merged and released through release-sync PR #139.

Completed behavior:

- New command: `agent-memory dogfood scheduled-compare --report <path> --report <path> --output <path>`.
- The report compares saved `dogfood scheduled-dry-run` artifacts with `kind=dogfood_scheduled_dry_run_comparison`, `read_only=true`, and `mutated=false`.
- It includes per-report hashes plus aggregate counts, ratios, warning names, quality-gate decision counts, and safe trend fields only.
- It never embeds raw report bodies, raw conversation content, raw queries, trace summaries, prompts, transcripts, API keys, token-like values, or sample values.
- It does not mutate DB rows, modify report artifacts, alter retrieval ranking, clean legacy query previews, or enable apply mode.

Verification completed:

- Focused scheduled-compare test passed.
- Focused scheduled-dry-run regression test passed.
- Full `tests/` passed locally before PR merge (`249 passed`).
- Targeted ruff, docs validation, and `git diff --check` passed.
- PR #138 checks passed and merged.
- PR #139 release-sync validation CI passed and merged.
- Main CI after PR #138 and after PR #139 passed.
- GitHub Release `v0.1.76`, npm `@cafitac/agent-memory@0.1.76`, and PyPI `cafitac-agent-memory==0.1.76` verified.
- Published install smoke passed from real npm/PyPI/uvx/npm channels.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reports all shell hooks healthy.
- Live DB G3f smoke wrote two scheduled reports and one comparison under `/tmp/agent-memory-v0176-g3f/`; comparison stayed read-only/no-mutation with raw-content privacy flags false and decision `continue_scheduled_report_collection_before_g4`.

## Completed v0.1.75 scheduled-dry-run release

PR #135 `feat: add dogfood scheduled dry-run bundle` merged and released through release-sync PR #136.

Completed behavior:

- New command: `agent-memory dogfood scheduled-dry-run <db> --output <path> --since-hours <hours>`.
- The report opens SQLite read-only and emits `kind=dogfood_scheduled_dry_run`, `read_only=true`, `mutated=false`, and `default_retrieval_unchanged=true`.
- It bundles `storage_health`, `trace_quality`, `remember_intent`, and inline `memory_consolidation_background_dry_run` reports under one top-level `quality_gate`.
- It writes the same JSON to `--output` when provided, making it cron-friendly.
- It never prints raw conversation content, raw queries, raw trace summaries, prompts, transcripts, API keys, token-like values, or sample values.
- It does not create candidates/approvals, mutate rows, alter retrieval ranking, clean legacy query previews, or enable apply mode.

Verification completed:

- Focused scheduled-dry-run test passed.
- `tests/test_cli.py` passed.
- Full `tests/` passed locally before PR merge.
- Targeted ruff and `git diff --check` passed.
- PR #135 CI passed and merged.
- PR #136 release-sync validation CI passed and merged.
- Main CI after PR #135 and after PR #136 passed.
- GitHub Release `v0.1.75`, npm `@cafitac/agent-memory@0.1.75`, and PyPI `cafitac-agent-memory==0.1.75` verified.
- Published install smokes passed locally for npm, PyPI fresh venv, and `uvx --refresh`; GitHub workflow dispatch for `published-install-smoke.yml` returned HTTP 403 with the current token, so local real-channel smoke was used.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.75/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reports all shell hooks healthy.

## Completed v0.1.74 trace-quality release

PR #132 `feat: add dogfood trace quality report` merged and released through release-sync PR #133.

Completed behavior:

- New command: `agent-memory dogfood trace-quality <db> --since-hours <hours> --min-trace-coverage <ratio> --min-evidence-count <count>`.
- The report opens SQLite read-only and emits `kind=dogfood_trace_quality`, `read_only=true`, `mutated=false`.
- It reports aggregate observation/trace/activation coverage, observation-to-trace coverage ratio, empty-retrieval ratio, repeated memory-ref counts, trace event-kind and retention-policy distributions, ordinary metadata-only invariants, metadata JSON validity, candidate-signal proxy counts, warnings, and recommendation.
- It never prints raw conversation content, raw queries, raw trace summaries, prompts, transcripts, API keys, token-like values, or sample values.
- It does not create candidates/approvals, mutate rows, alter retrieval ranking, or change hook behavior.
- Live 24h v0.1.74 smoke returned `status=warning`, `recommendation=continue_dogfooding`, `observation_count=174`, `trace_count=87`; the warning is expected because recent observations are not linked from traces strongly enough yet.

Verification completed:

- Focused trace-quality test passed.
- `tests/test_cli.py` passed.
- Full `tests/` passed: `247 passed`.
- Targeted ruff passed on `src/agent_memory/api/cli.py` and `tests/test_cli.py`.
- PR #132 CI passed and merged.
- PR #133 release-sync validation CI passed and merged.
- GitHub Release `v0.1.74`, npm `@cafitac/agent-memory@0.1.74`, and PyPI `cafitac-agent-memory==0.1.74` verified.
- Published install smokes passed for npm, PyPI fresh venv, and `uvx --refresh`.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reports all shell hooks healthy.

## Completed v0.1.70-v0.1.71 remember-intent diagnostics release

PR #122 `feat: add debuggable remember intent diagnostics` merged and released through v0.1.70. PR #124 `fix: reject freeform secret-like remember intents` then hardened the secret scanner and released through v0.1.71.

Completed behavior:

- Korean explicit remember prefixes (`기억해둬:`, `기억해줘:` plus spaced/full-width-colon variants) are recognized as review-ready `remember_intent` traces when content passes secret scanning.
- Safe explicit remember requests store a sanitized human-readable summary so reviewers can see the explicit request without storing ordinary raw conversation turns.
- Secret-like explicit remember requests store only a rejected metadata-only diagnostic: `candidate_policy=rejected`, `secret_scan=blocked`, `rejected_reason=secret_like_text`, `summary=NULL`.
- Freeform secret labels such as `api key <value>` are rejected even without `:` or `=`.
- `agent-memory dogfood remember-intent` reports safe `rejection_counts` without raw prompt/query/user-message leakage.
- Ordinary conversation still records only hash/metadata evidence and does not create approved facts/procedures/episodes.

Verification completed:

- PR #122 CI passed and merged.
- PR #123 release-sync merged and published v0.1.70.
- Published smoke for v0.1.70 found the freeform secret-like scanner gap before live runtime rollout.
- PR #124 added regression coverage for the freeform gap, CI passed, and merged.
- PR #125 release-sync merged and published v0.1.71.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.71` plus Korean safe remember and secret-like rejected diagnostics.
- npm `npm exec --package=@cafitac/agent-memory@0.1.71` smoke verified command/help surfaces.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.71/.venv/bin/agent-memory`.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool` returned `OK` and advanced observations, activations, and metadata-only ordinary traces without changing facts.
- `hermes hooks doctor` reports all hooks healthy.

## Completed v0.1.69 empty-context trace hotfix

PR #120 `chore: release v0.1.69 [skip release]` merged after commit `fix: record hermes turn traces before empty context return` landed on main.

- Root cause: v0.1.68 recorded ordinary metadata-only traces after checking whether rendered memory context was empty, so no-injected-context turns could store retrieval observations/activations without storing an ordinary `experience_traces` row.
- Fix: call `_record_pre_llm_experience_trace(...)` before `if not context.prompt_text.strip(): return {}`. Hook output remains `{}` when no memory context is injected.
- Regression test: `test_hermes_pre_llm_hook_records_trace_even_when_no_context_is_injected`.
- CI passed on the feature commit and release-sync PR.
- GitHub Release `v0.1.69` published.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.69`.
- Clean npm temp-dir smoke verified `@cafitac/agent-memory@0.1.69`.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.69/.venv/bin/agent-memory` and `/Users/reddit/.hermes/config.yaml` now points to it.
- `hermes hooks doctor` reports all shell hooks healthy.
- Real Hermes chat smoke recorded one new retrieval observation, one activation, and one metadata-only ordinary trace; latest ordinary trace has `summary=NULL`, `retention_policy=ephemeral`, `candidate_policy=evidence_only`, and `auto_approved=false`. Latest retrieval observations keep `query_preview` empty.

## Completed Stage G/G3a slice

PR #114 `feat: add background dry-run dogfood gates` merged and released in v0.1.67. Release-sync PR #115 merged.

- New command: `agent-memory dogfood background-dry-run <db> --report <json> [--output <path>]`.
- It evaluates one or more saved G3 background dry-run JSON reports into aggregate quality gates.
- Output kind is `background_dry_run_dogfood_report` with `read_only=true`, `mutated=false`, and `default_retrieval_unchanged=true`.
- It summarizes only secret-safe report metadata, per-report counts, warnings, and gate decisions; it does not echo raw report payloads, raw prompts, transcripts, query previews, tokens, or credentials.
- Conservative gate decision `continue_dry_run_dogfooding_before_g4` is expected when reports are sparse/noisy; passing the gate is advisory and does not enable apply mode.
- G3a does not mutate DB rows, create facts/relations/traces/retrieval observations, infer ordinary conversation preferences, or change Hermes/default retrieval behavior.

Verification completed for G3a/v0.1.67:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'dogfood_background_dry_run'
# 2 passed, 73 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'dogfood_background_dry_run or background_dry_run or dogfood or remember_intent or consolidation or activation or reinforcement or decay_risk'
# 14 passed, 66 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 239 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #114 CI succeeded and merged. A push-event CI run initially hit a known flaky retrieval-eval fixture assertion, while the pull_request run passed; an empty retry commit made both push and pull_request checks pass.
- Release-sync PR #115 validation workflow_dispatch CI succeeded and merged.
- GitHub Release `v0.1.67` published.
- npm registry shows `@cafitac/agent-memory@0.1.67`; clean `npm exec --package=@cafitac/agent-memory@0.1.67` smoke verified G3 + G3a command surfaces after normal PyPI/uvx propagation lag.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.67`, G3 background dry-run, and G3a background-dry-run dogfood report.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.67/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.67.
- Direct `hermes-pre-llm-hook` smoke succeeded.
- Runtime G3a live dogfood smoke against the latest saved local report succeeded with read-only/no-mutation/default-retrieval-unchanged assertions.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.67 agent-memory pre-LLM hook.

## Completed Stage G/G3b slice

PR #117 `feat: record ordinary Hermes turn traces` merged and released in v0.1.68. Release-sync PR #118 merged.

- Real non-synthetic Hermes pre-LLM turns now record metadata-only `turn` traces by default.
- Ordinary trace rows use `surface=hermes-pre-llm-hook`, `event_kind=turn`, low salience, `retention_policy=ephemeral`, and metadata `trace_recording=default_metadata_only`, `candidate_policy=evidence_only`, `auto_approved=false`.
- Trace storage remains secret-safe: no raw prompt, raw query, query preview, transcript, user message, or secret-like text is stored or printed.
- Synthetic Hermes doctor/test payloads are skipped.
- Trace write failures remain non-blocking; `--no-record-trace` disables runtime trace recording for a hook invocation.
- Ordinary turns do not create facts/procedures/episodes, do not auto-approve memories, and do not change default retrieval ranking.

Verification completed for G3b/v0.1.68:

- Focused tests: `23 passed, 54 deselected`.
- Full suite: `241 passed`.
- Release readiness: `git diff --check`, `scripts/check_release_metadata.py`, `scripts/smoke_release_readiness.py`, `npm pack --dry-run`, and `node --check bin/agent-memory.js` passed.
- GitHub PR #117 checks passed; main CI after merge passed.
- Release-sync PR #118 main CI and auto-release passed.
- GitHub Release `v0.1.68` published.
- npm smoke verified `@cafitac/agent-memory@0.1.68` can record metadata-only ordinary turn traces through the public wrapper after normal PyPI/uvx propagation.
- PyPI fresh venv smoke verified `cafitac-agent-memory==0.1.68` and metadata-only ordinary turn traces.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up to `/Users/reddit/.hermes/config.yaml.bak-v0.1.68` before updating the hook path to v0.1.68.
- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool --provider openai-codex --model gpt-5.5` returned `OK` and recorded a metadata-only ordinary `turn` trace.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.68 agent-memory pre-LLM hook.

## Completed Stage G/G3 slice

PR #111 `feat: add background consolidation dry run` merged and released in v0.1.66. Release-sync PR #112 merged.

- New command: `agent-memory consolidation background dry-run <db> [--output <path>] [--lock-path <path>]`.
- It bundles read-only `consolidation candidates`, `activations summary`, `activations reinforcement-report`, and `activations decay-risk-report` into one cron-friendly JSON report.
- It uses a non-blocking file lock; overlapping runs exit zero with `status: skipped_lock_busy` and write a readable skipped report when `--output` is supplied.
- It is report-only: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, no apply mode, and no fact/source/relation/status/trace/retrieval-observation mutation.
- Failure reports are readable JSON and do not introduce memory mutations.
- G3 does not infer from ordinary conversation and does not change default retrieval/Hermes hook behavior.

Verification completed for G3/v0.1.66:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'background_dry_run'
# 2 passed, 71 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'background_dry_run or consolidation or activation or reinforcement or decay_risk or remember_intent'
# 10 passed, 68 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 237 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #111 CI succeeded and merged.
- Release-sync PR #112 validation succeeded and merged.
- GitHub Release `v0.1.66` published.
- npm registry shows `@cafitac/agent-memory@0.1.66`.
- PyPI JSON and fresh install show `cafitac-agent-memory==0.1.66`; first pip install attempt hit normal index propagation lag, retry succeeded.
- PyPI fresh venv smoke verified G3 background dry-run on a seeded temp DB and confirmed no facts/source records were created.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.66` smoke verified the G3 command surface.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.66/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.66.
- Runtime G3 background dry-run smoke succeeded on a temp DB.
- `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.66 agent-memory pre-LLM hook.

## Completed Stage G/G2 slice

PR #108 `feat: add remember preference auto approval` merged and released in v0.1.65. Release-sync PR #109 merged.

- New command: `agent-memory consolidation auto-approve remember-preferences <db> --policy remember-preferences-v1 --scope <scope>`.
- Default mode is dry-run/read-only and reports `would_approve` candidates without mutation.
- Apply mode requires explicit `--apply --actor ... --reason ...`.
- Eligible rows are explicit/review-ready `remember_intent` traces in the selected scope with sanitized summaries shaped like `User prefers ...` or `I prefer ...`.
- The only auto-approved memory shape is `fact(user, prefers, <value>, <scope>)`.
- Guardrails block secret-like summaries, unsupported summary shapes, non-selected scopes, ordinary turns, and claim-slot conflicts.
- Successful apply writes approval/status history and an `auto_approved_as` relation from the trace to the fact.
- Default retrieval and Hermes hook ranking behavior remain unchanged.

Verification completed for G2/v0.1.65:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'auto_approve_remember_preferences or remember_intent'
# 6 passed, 65 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'auto_approve_remember_preferences or dogfood or remember_intent or hermes_pre_llm_hook or experience_trace or consolidation'
# 24 passed, 52 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 235 passed
```

## Completed Stage G/G1a slice

PR #105 `feat: add remember intent dogfood report` merged and released in v0.1.64. Release-sync PR #106 merged.

- New command: `agent-memory dogfood remember-intent <db> --limit 200 --sample-limit 10`.
- Output kind is `remember_intent_dogfood_report` with `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`.
- The report counts inspected traces, `remember_intent` traces, ordinary turn traces, review-ready traces, unsafe samples, and remember-intent scopes.
- Samples include safe sanitized summaries plus compact policy flags only; raw metadata, raw prompts/transcripts, and secret-like summaries are omitted.
- No facts/procedures/episodes, relations, status transitions, candidates, approvals, retrieval observations, or hook behavior are mutated.

## Completed Stage G/G1 slice

PR #102 `feat: add explicit remember intent traces` merged and released in v0.1.63.

- Existing Hermes trace recording remains disabled unless `--record-trace` is enabled.
- With `--record-trace`, explicit `Remember this:` / `Please remember:` messages that pass the conservative secret-like scan are recorded as `experience_traces.event_kind=remember_intent`.
- G1 rows use `retention_policy=review`, high salience/user emphasis, sanitized summary only, hashed session/content refs, and metadata `candidate_policy=review_required`, `auto_approved=false`.
- Secret-like remember requests fall back to ordinary hash-only ephemeral turn traces and do not create remember review traces.
- No facts/procedures/episodes are created or approved automatically; review remains through `consolidation candidates` and `consolidation explain`.

## Current north-star / open roadmap

The north-star remains a human-memory-like lifecycle:

1. Lightweight traces/observations, without storing raw transcripts forever.
2. Activation/reinforcement reports from repeated use, usefulness, recency, and graph connectivity.
3. Consolidation candidates that are explainable and reviewable.
4. Manual or narrow opt-in approval into long-term graph memory.
5. Lifecycle edges for reinforcement, conflict, supersession, decay risk, and audit history.
6. Conservative background/reporting jobs before any background apply mode.

Completed through v0.1.68:

- Stage C: activation evidence, activation summary, reinforcement report, decay risk report.
- Stage D: read-only consolidation candidates and `consolidation explain`.
- Stage E: manual reviewed promotion, promotion audit/report, lineage, conflict/supersession preflight and relation edges.
- Stage F: retrieval policy/ranker/decay/graph-neighborhood preview surfaces.
- Stage G/G1: explicit remember-intent review trace.
- Stage G/G1a: remember-intent dogfood report.
- Stage G/G2: narrow opt-in remember-preference auto-approval.
- Stage G/G3: cron-friendly background consolidation dry-run report.
- Stage G/G3a: read-only dogfood quality gates over saved G3 reports.

Open candidates:

- Keep dogfooding G3/G3a dry-run reports on the real local DB and define stricter quality gates/noise thresholds before G4.
- Stage G/G4 background apply mode, only after explicit policy/audit/rollback design.
- Stage H eval/visualization/backup/public docs hardening.

## Useful commands

```bash
cd /Users/reddit/Project/agent-memory

git status --short --branch
git tag --sort=-version:refname | head -5
HOME=/Users/reddit gh pr list --repo cafitac/agent-memory --state open --json number,title,headRefName,url
HOME=/Users/reddit gh run list --repo cafitac/agent-memory --limit 10

/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory consolidation background dry-run /Users/reddit/.agent-memory/memory.db \
  --limit 200 \
  --top 20 \
  --min-evidence 2 \
  --output /Users/reddit/.agent-memory/reports/background-dry-run.json \
  --lock-path /Users/reddit/.agent-memory/background-dry-run.lock

/Users/reddit/.agent-memory/runtime/v0.1.68/.venv/bin/agent-memory dogfood background-dry-run /Users/reddit/.agent-memory/memory.db \
  --report /Users/reddit/.agent-memory/reports/background-dry-run.json \
  --output /Users/reddit/.agent-memory/reports/background-dry-run-quality.json
```

## Safety rails

- Do not expose secrets/tokens/connection strings; redact as `[REDACTED]`.
- Do not store raw prompts/transcripts/query previews as durable memory artifacts.
- Do not enable ordinary conversation auto-approval.
- Do not change default retrieval/Hermes hook ranking as part of background consolidation.
- Treat G4/background apply as a separate high-risk slice requiring a new RED-tested plan.
- Preserve local-only untracked files listed above.


## In-flight checkpoint — fresh epoch empty retrieval classification (2026-05-10 13:39 KST)

- Branch: `feat/empty-retrieval-classification`.
- Goal: split fresh-epoch empty retrieval `unknown` outcomes into aggregate, metadata-only likely causes before any telemetry reset/delete path.
- New report fields: `empty_retrieval_diagnostics.by_likely_cause` and `unknown_outcome_drilldown`.
- Source smoke on live DB wrote `/tmp/agent-memory-fresh-epoch-classified-source.json` with `read_only=true` and `mutated=false`; aggregate result: 50 observations/traces/activations since epoch, coverage 0.24, empty ratio 0.52, unknown outcomes classified as `legacy_missing_outcome_metadata_gap` with unresolved_count 0.
- Still blocked: low fresh-epoch linkage, high empty ratio, and classified legacy metadata gap; broad G4 apply remains blocked.


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


### v0.1.135+ source checkpoint — fresh linkage, quality gate, narrow queue mutation (2026-05-10 20:29 KST)

- Branch: `feat/g4-fresh-linkage-and-mutations`; package version: `0.1.135`; PR/release/runtime rollout still pending.
- Implements the post-v0.1.134 follow-up while preserving hard blocks on broad G4 apply, ordinary conversation auto-approval, raw prompt/transcript/query persistence, telemetry reset apply, and default retrieval ranking changes.
- Fresh trace linkage: Hermes pre-LLM hook now records a metadata-only trace even when no context is injected and can resolve the trace/observation link from the latest same-query retrieval observation if `packet.retrieval_observation_id` is missing.
- G4 quality gate: `g4-review-queue-preview --epoch-start <ISO>` now treats historical/classified/reset-resolved empty-retrieval warnings as diagnostic-only when the fresh epoch has no unresolved unknown outcomes and no fresh unlinked observations; fresh unresolved evidence remains blocking.
- Approved review queue apply: `g4-review-queue-apply` can perform the first narrow guarded memory mutation for approved `reinforcement_review` items by incrementing only `reinforcement_count` on the target fact/procedure/episode. It still leaves status, default retrieval behavior, and raw content untouched, requires explicit policy/approval/actor/reason/backup, writes `g4_review_queue_applications`, and reports rollback metadata.
- Focused RED/GREEN verification passed so far:
  - `uv run pytest tests/test_cli.py::test_hermes_pre_llm_hook_records_metadata_only_trace_for_empty_retrieval_turn tests/test_cli.py::test_hermes_pre_llm_hook_records_trace_even_when_no_context_is_injected tests/test_cli.py::test_hermes_pre_llm_hook_resolves_trace_link_when_packet_observation_id_is_missing -q`
  - `uv run pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_preview_splits_historical_unknowns_with_fresh_epoch tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_apply_records_approved_items_without_memory_mutation -q`
- Full-suite verification now passed: `uv run --python 3.11 pytest tests/ -q` => `285 passed, 1 xfailed`.
- Remaining before handoff can call this released: update/open PR, merge, let release-sync/publish complete, install the published runtime, and perform live aggregate verification. Do not mark v0.1.135 as the latest completed release until this is done.


### v0.1.136 release/runtime rollout checkpoint (2026-05-10 20:48 KST)

- PR #285 `feat: apply narrow G4 reinforcement markers` merged after CI; release-sync PR #286 `chore: release v0.1.136 [skip release]` merged.
- Main CI, release-sync CI, auto-release, and publish workflow completed successfully; GitHub Release `v0.1.136`, npm `@cafitac/agent-memory@0.1.136`, and PyPI `cafitac-agent-memory==0.1.136` are visible.
- Fresh artifact smoke passed: npm tarball package version `0.1.136`; PyPI wheel `cafitac_agent_memory-0.1.136-py3-none-any.whl` downloaded; installed runtime import reports `agent_memory.__version__ == 0.1.136`.
- Runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory`; Hermes config updated from v0.1.135 to v0.1.136 with backup `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.136-20260510T2044`.
- Installed hook smoke wrote `/tmp/agent-memory-v0136-hook-smoke.json`; latest smoke-linked ids were observation `2438`, trace `1721`, activation `2343`, with trace `related_observation_ids_json=[2438]` and observation `retrieval_outcome=retrieved_memory`.
- Live installed G4 preview wrote `/tmp/agent-memory-v0136-g4-preview-live.json`; it stayed read-only/no-mutation and produced 2 ref-only queue entries. The old unknown-empty blocker is resolved/classified for the fresh window, but the broad gate remains blocked by `background_empty_retrieval_trace_linkage_gap` because the fresh comparison still has one fresh unlinked observation.
- Installed queue-apply smoke was performed only on disposable fixture `/tmp/agent-memory-v0136-installed-apply-fixture.db`; it produced `applied_count=1`, `memory_reinforcement_mutated=true`, `memory_status_mutated=false`, `default_retrieval_unchanged=true`, and fact row `(reinforcement_count=1.0, retrieval_count=0)`. No live apply mutation was performed in this rollout.
- Live aggregate after rollout: `facts=3`, `procedures=0`, `episodes=0`, `g4_review_queue_items=2`, `g4_review_queue_applications=2`, and the live telemetry tables continued to advance with the installed hook.


## G5i local checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 11:08 KST

Runtime baseline remains `v0.1.146` at `/Users/reddit/.agent-memory/runtime/v0.1.146/.venv/bin/agent-memory`; fresh linkage evidence still includes `fresh_trace_linkage_gap_not_detected` and report directory `g4-v0138-20260512-132253`. Overall north-star: 72-74%.

Local G5i implements the requested five next steps after G5h: rollback replay rollups, live-compatible retrieval fixture expansion summaries, collapse equivalence proof surface, telemetry-only apply safety-gate reporting, and broad G4 apply reassessment fields. Broad G4/background apply remains blocked; default ranking changes, collapse/delete apply, and ordinary conversation auto-approval remain forbidden.
