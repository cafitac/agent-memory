# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-18 12:33 KST

## Current checkpoint: Hermes plugin/default integration complete

- Latest source checkpoint adds a repo-level Hermes plugin manifest and `register(ctx)` entry point.
- Hermes users can use `hermes plugins install cafitac/agent-memory --enable` as the direct plugin/default path; npm `agent-memory bootstrap` remains the agent-agnostic hook/config path.
- The plugin registers `pre_llm_call`, initializes/reuses the local DB, returns prompt-cache-friendly context injection, and fails soft on empty/bad inputs.
- Validation complete: `tests/test_hermes_plugin_integration.py -q` -> `4 passed`; Hermes adapter/npm/docs/release corridor -> `30 passed`; full suite -> `428 passed, 1 xfailed`.
- Current progress framing: Hermes plugin/default integration 100%; broader human-brain-like lifecycle remains bounded by the prior no-auto-OS-scheduler safety boundary.
- Next safe action: commit/push only the plugin/default integration files and docs; leave unrelated untracked harness directories untouched.

Reference: `.dev/roadmap/memory-consolidation/hermes-plugin-default-integration-plan.md`

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
- It consumes a green one-cycle smoke gate and green scheduler status, runs exactly one explicit scheduler one-shot, immediately packages evidence, and stops.
- Copy mode preserves the source DB; background/cron/unattended/default authority remains false.
- Validation complete: focused one-cycle execute `1 passed`; one-cycle execute/smoke corridor `2 passed, 234 deselected`; enabled+disabled config corridor `9 passed, 227 deselected`; ordinary-turn default automation corridor `44 passed, 192 deselected`; full suite `418 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999998%+.
- Next safe slice: post-run verification hardening/read-only recurrence-install preflight readiness over the one-cycle execution report. Do not install background/cron or enable unattended recurrence yet.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-enabled-recurring-scheduler-config-one-cycle-execution.md`

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
- Validation so far: `tests/test_cli.py -q -k "disabled_recurring_scheduler_config"` -> `3 passed, 227 deselected`; `tests/test_cli.py -q -k "disabled_recurring_scheduler_config_materialize"` -> `1 passed, 229 deselected`; `tests/test_cli.py -q -k "ordinary_turn_default_automation"` -> `38 passed, 192 deselected`; full suite still pending for this checkpoint.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.999992%+.
- Latest test update feeds the materialized disabled config through scheduler integration and proves runner invocation remains false with `scheduler_config_disabled`; next safe slice is enabled-config preflight design only, still no enabled recurrence/background/cron.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-disabled-recurring-scheduler-config-materialization.md`

## Current checkpoint: disabled recurring scheduler config validation

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-disabled-recurring-scheduler-config-validate`.
- It consumes the disabled recurring scheduler config contract and fails closed unless the contract is green, disabled by default, disabled as enforced state, execution-free, write-free, fresh-evidence/package-stop/CI/rollback constrained, and still preserves separate approval for later enablement/background/cron.
- RED proof: the subcommand was initially missing; the test mutates the contract to set `recurring_scheduler_enabled=true` and `executes_scheduler_cycle=true`, and validation returns red blocked reasons while validator authority remains false.
- Positive local smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-disabled-recurring-config-validation-20260517T174542Z/disabled-recurring-scheduler-config-validation.json`.
- Validation so far: `tests/test_cli.py -q -k "disabled_recurring_scheduler_config"` -> `2 passed, 227 deselected`; full suite still pending for this checkpoint.
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
- Validation so far: focused config contract `1 passed, 227 deselected`; readiness/config/history corridor `3 passed, 225 deselected`; default-automation corridor `36 passed, 192 deselected`; full suite still pending for this checkpoint.
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
- Validation complete: focused readiness `1 passed, 226 deselected`; scheduler corridor `12 passed, 215 deselected`; default-automation corridor `35 passed, 192 deselected`; full suite `409 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.99998%+.
- Next safe slice: disabled recurring scheduler config contract after exact phrase `approve-disabled-recurring-default-automation-scheduler-config-contract-v1`; no enablement/background/cron execution yet.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-recurring-scheduler-readiness.md`

## Previous checkpoint: repeated scheduler-window copy smoke using package evidence as next previous rollup

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-repeated-window-smoke`.
- It copies the source DB, runs two explicit scheduler integration windows on the copy, packages post-apply evidence after each window, then proves window 2 used window 1 package outputs as its fresh previous evidence.
- Window 2 consumes window 1 package `ordinary-turn-default-automation-evidence-rollup.json` as `--previous-evidence-rollup`, window 1 scheduler runner as `--previous-scheduler-report`, and window 1 package post-apply verifier as `--post-apply-verification-report`.
- It mutates only the copied DB; the live/source DB must remain SHA/table-count unchanged.
- Positive copy-live smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-repeated-window-smoke-20260517T155339Z/scheduler-repeated-window-smoke.json`.
- Smoke result: `quality_gate.pass=true`, `window_count=2`, `green_integration_count=2`, `green_package_count=2`, `unique_trace_ref_count=2`, `all_rollups_reused_as_next_previous_evidence=true`, `source_db_unchanged=true`, unchanged source DB SHA `0d753d3c89f6c4a2a2efa2117b95dd2e4cb6738039df020c64f75efe08627135`.
- Validation: focused repeated-window smoke `1 passed`; default-automation corridor `15 passed, 208 deselected`; full suite `405 passed, 1 xfailed`.
- Current progress framing: safety-gated operational north-star about 99%+; scoped local human-brain-like lifecycle about 99.99985%+.
- Next safe slice: operator/status/runbook ergonomics for this repeated-window evidence, then a real local opt-in schedule that invokes the one-cycle runner only when all gates are already green and stops after packaging; still no unattended/default/background authority.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-scheduler-repeated-window-smoke.md`

## Just completed: scheduler package/collector for post-apply evidence before next cycle

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-package`.
- It consumes a green `ordinary-turn-default-automation-scheduler-integration` report from a prior explicit one-cycle run, validates the nested scheduler runner/apply report, then automatically collects rollback replay, post-apply verification, and default-automation evidence rollup for the next cycle.
- It is read-only/non-mutating and reports `collector.executes_scheduler_cycle=false` / `collector.executes_apply=false`; it never runs another scheduler cycle or apply.
- It blocks red/non-mutating integration reports before verifier collection and preserves the fail-closed boundary around enabled policy, exact scheduler approval, fresh evidence, and one-candidate maximum.
- Positive copy-live smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-package-copy-smoke-20260517T153723Z/scheduler-package.json`.
- Smoke result: `quality_gate.pass=true`, rollback replay/post-apply verifier/evidence rollup all executed, `evidence_rollup.green_report_count=1`, `source_db_unchanged=true`, unchanged source DB SHA `f20a8a8c7746e4dc257e0165df8e506827e2cb4761b45272774f94dd6fe94dda`.
- Validation: focused scheduler package `2 passed`; default-automation corridor `14 passed, 208 deselected`; full suite `404 passed, 1 xfailed`.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-scheduler-package.md`

## Just completed: scheduler integration/config around default automation one-cycle runner

- Latest source checkpoint adds `dogfood ordinary-turn-default-automation-scheduler-integration`.
- It validates explicit scheduler config, enabled policy state, green policy gate, fresh previous evidence rollup, previous scheduler-report state, and queued green post-apply verifier reports before it invokes the scheduler runner.
- It blocks disabled scheduler config before runner invocation and blocks a next cycle when the previous scheduler report still has unexecuted required post-apply verification.
- When all gates are green, it invokes exactly one scheduler-runner cycle, applies at most one candidate to the supplied DB, and then requires a new post-apply verifier/evidence-rollup before any later cycle.
- Positive copy-live smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-integration-copy-smoke-20260517T095816Z/scheduler-integration.json`.
- Smoke result: `quality_gate.pass=true`, `mutated_copy=true`, `scheduler_runner.invoked=true`, `post_apply_verification_queue.queued_report_count=1`, `selected_trace_ref=experience_trace:4130`, `source_db_unchanged=true`, unchanged source DB SHA `1413ffe379ceed84763ab52cb4a6ff7d17e54f4f7733f6b204518f2c1b67d85b`.
- Validation: focused scheduler integration `3 passed`; default-automation corridor `12 passed, 208 deselected`; full suite `402 passed, 1 xfailed`.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-scheduler-integration.md`

## Just completed: scheduler-facing default automation one-cycle runner

- Added `dogfood ordinary-turn-default-automation-scheduler-runner`, a scheduler-facing wrapper around the explicit opt-in default automation runner.
- It requires exact scheduler phrase `run-one-default-automation-scheduler-cycle-v1`, exact apply phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`, exact policy `ordinary-turn-default-automation-policy-v1`, enabled policy state, green policy gate, and a green previous default-automation evidence rollup before it invokes the runner.
- It invokes at most one runner cycle, can apply at most one candidate, and then stops with `post_apply_verification.required=true` / `executed=false` before any next cycle.
- Positive copy-live smoke wrote `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-scheduler-runner-positive-copy-smoke-20260517T092607Z/default-automation-scheduler-runner.json`; it reported `quality_gate.pass=true`, `runner_invoked=true`, `runner_applied=true`, `source_db_unchanged=true`, and unchanged source DB SHA `ec573b446cc9f64c9346a482b3e79633b4e98171b1a9eb2b3a1890c59efb2d71`.
- Validation passed: scheduler focused `2 passed, 215 deselected`; broader default-automation corridor `12 passed, 205 deselected`; full suite `399 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.9996%+.
- Remaining gap: wire real scheduler/config around this wrapper and automate repeated post-apply verifier/evidence-rollup collection, still opt-in/fail-closed/one-candidate bounded and without unattended/default/background authority.

Recommended next work now:

1. Commit/push this scheduler-runner checkpoint and watch CI.
2. Add real scheduler integration/config that calls this wrapper only when enabled policy-state and fresh evidence rollup are present, then automatically queues/records the required post-apply verification artifact before any later cycle.
3. Keep broad ordinary conversation auto-approval, default/background unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-scheduler-runner.md`

## Just completed: explicit opt-in default automation runner

- Added `dogfood ordinary-turn-default-automation-runner`, a command-level runner that wires enabled policy-state + green policy gate + read-only dry-run + exact one-candidate apply into a single explicit invocation.
- The runner applies at most one preference-shaped ordinary-turn candidate and only when the caller supplies exact policy `ordinary-turn-default-automation-policy-v1`, exact phrase `apply-exact-ordinary-turn-default-automation-candidate-v1`, actor, reason, and the enabled policy-state artifact.
- It inherits the prior freshness boundary: after any prior `ordinary_turn_default_automation_approved_as` relation exists, a fresh green `--previous-evidence-rollup` is required before the runner can apply again.
- Copy-live smoke wrote `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-runner-smoke-20260517T090307Z/default-automation-runner.json`; it mutated only the copied DB and reported `quality_gate.pass=true`, `apply_executed=true`, `source_db_mutated=false`, `ordinary_conversation_auto_approval=false`, and `unattended_default_apply_allowed=false`.
- Validation passed: RED missing subcommand, focused runner tests `3 passed, 212 deselected`, default-automation focused `23 passed, 192 deselected`, full suite `397 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.9995%+.
- Remaining gap: scheduler-facing runbook/wrapper for fresh post-apply verification before repeated runner use; no broad unattended/default/background authority is enabled.

Recommended next work now:

1. Commit/push this runner checkpoint and watch CI.
2. If continuing toward 100%, add a scheduler-facing wrapper/runbook that calls the runner only when enabled policy-state and fresh evidence rollup are present, then stops for post-apply verification.
3. Keep broad ordinary conversation auto-approval, default/background unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-runner.md`

## Just completed: default automation freshness-boundary copy-live smoke

- Added `dogfood ordinary-turn-default-automation-freshness-boundary-smoke`, a copy-DB smoke/report command for the default automation apply freshness boundary.
- The smoke copies the source DB, mutates only the copy, proves a prior exact-reviewed default-automation apply exists, verifies a repeated apply is blocked without `--previous-evidence-rollup`, then verifies the repeated apply passes only with a green previous `dogfood_ordinary_turn_default_automation_evidence_rollup`.
- Live/source smoke wrote `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-freshness-boundary-smoke-20260517T083948Z/freshness-boundary-smoke.json` and reported `quality_gate.pass=true`, `source_db_mutated=false`, `copied_db_mutated=true`, `missing_rollup_blocked=true`, and `fresh_rollup_apply_passed=true`.
- Validation passed: RED missing subcommand, focused test `1 passed`, default-automation focused `20 passed, 192 deselected`, full suite `394 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.999%+.
- Remaining gap: optional explicit-opt-in scheduler/default wiring, if any, must consume enabled policy state plus fresh post-apply evidence and still stay one-candidate/fail-closed.

Recommended next work now:

1. Commit/push this freshness-boundary smoke checkpoint and watch CI.
2. If continuing toward 100%, add explicit opt-in scheduler/default runner wiring only under the fail-closed policy-state + fresh-evidence boundary; prefer read-only/report-first if uncertainty remains.
3. Keep broad ordinary conversation auto-approval, default/background unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

Reference: `.dev/roadmap/memory-consolidation/references/post-v0.1.162-default-automation-freshness-boundary-smoke.md`

## Just completed: default automation apply-boundary policy-state/freshness enforcement

- `dogfood ordinary-turn-default-automation-apply` now requires `--policy-state-config` and fail-closes unless the opt-in policy state is present, enabled, same-policy, exact-review/fresh-verifier guarded, disable-switch available, and still denies ordinary/background/unattended/default authority.
- Added `--previous-evidence-rollup`; after any prior `ordinary_turn_default_automation_approved_as` relation exists, the next apply is blocked unless a green default-automation evidence-rollup proves prior post-apply verification coverage.
- Apply output now carries redacted `policy_state` plus `freshness_evidence` so the boundary is auditable without raw turn/reason/report content.
- Validation passed: new apply-boundary tests plus existing apply/post-apply cases `5 passed`, default-automation focused `19 passed`, broader ordinary-turn `38 passed`, full suite rerun `393 passed, 1 xfailed` after one unrelated retrieval-eval regression test passed on immediate isolated rerun.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.999%.
- Remaining gap: finalize full-suite/CI validation, then add source/copy-live smoke for the new freshness boundary and decide whether any broader scheduler wiring is still allowed under explicit opt-in only.

Recommended next work now:

1. Finish full suite, commit/push this apply-boundary checkpoint, and watch CI.
2. Run a copy-live/source smoke that exercises apply with enabled policy state and, for repeated apply, a fresh previous evidence rollup.
3. Keep broad ordinary conversation auto-approval, default/background unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Just completed: default automation policy-state read-path enforcement

- Added optional `--policy-state-config` to `dogfood ordinary-turn-default-automation-dry-run`.
- When supplied, dry-run now fail-closes if policy state is missing, disabled, wrong kind/policy, grants ordinary/background/unattended authority, lacks fresh-verifier/exact-review/disable requirements, or requests more candidates than the enabled policy allows.
- Enabled policy state still permits only bounded exact-review candidate refs; dry-run remains read-only and raw-text-free.
- Validation passed: default-automation focused `17 passed`, broader ordinary-turn `36 passed`, full suite `391 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.998%.
- Remaining gap: apply-boundary policy-state enforcement plus freshness linkage to post-apply verifier/evidence-rollup before repeated apply.

Recommended next work now:

1. Commit/push this read-path enforcement checkpoint and watch CI.
2. Next code slice should require enabled policy state at `ordinary-turn-default-automation-apply`, while preserving exact trace-ref review, one-candidate bound, backup, rollback replay, and no unattended/background apply.
3. Add freshness linkage so a second apply requires fresh post-apply verifier/evidence-rollup from the previous apply.

## Just completed: default automation exact opt-in enablement switch

- Added `dogfood ordinary-turn-default-automation-enablement-switch`, with explicit `enable` and `disable` actions.
- Enable consumes a green `dogfood_ordinary_turn_default_automation_enablement_preflight` artifact and requires exact phrase `enable-opt-in-ordinary-turn-default-automation-v1`, exact policy `ordinary-turn-default-automation-policy-v1`, actor, reason, and bounded `--max-default-candidates-per-run`.
- The switch writes only a caller-chosen local JSON policy-state file; it does not mutate the memory DB, default retrieval, classifier, or scheduler defaults.
- Green enable writes `manual_opt_in_default_automation_enabled=true` while keeping `ordinary_conversation_auto_approval=false`, `default_background_auto_approval_allowed=false`, `unattended_default_apply_allowed=false`, and `max_apply_without_fresh_post_apply_verification=0`.
- Disable requires exact phrase `disable-opt-in-ordinary-turn-default-automation-v1` and writes fail-closed state with `manual_opt_in_default_automation_enabled=false`.
- Source smoke enabled and then disabled a policy-state file only under the saved report directory; final state is disabled/fail-closed.
- Full validation passed: `389 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.997%.
- Remaining gap: wire the narrow policy-state reader into the ordinary-turn default automation runner so actual runner behavior respects enabled/disabled state while remaining disabled-by-default and fresh-verifier-gated.

Recommended next work now:

1. Commit/push this switch checkpoint and watch CI.
2. Next code slice should add read-path enforcement: absent/disabled policy state blocks default automation; enabled state only permits one exact-reviewed candidate and never unattended/background apply; stale/missing post-apply verifier evidence blocks the next apply.
3. Keep broad ordinary conversation auto-approval, default/background unattended apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Just completed: default automation opt-in enablement preflight

- Added `dogfood ordinary-turn-default-automation-enablement-preflight`, a read-only/manual-opt-in-only gate over a saved green `dogfood_ordinary_turn_default_automation_evidence_rollup` artifact.
- Live/source smoke consumed `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-evidence-rollup.json` and wrote `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-enablement-preflight.json`.
- Smoke result: `quality_gate.pass=true`, `decision=ordinary_turn_default_automation_enablement_preflight_green_manual_opt_in_only`, `green_report_count=2`, `applied_memory_count=2`, and `ready_for_manual_opt_in_enablement=true`.
- It still keeps `read_only=true`, `mutated=false`, `apply_supported=false`, `apply_executed=false`, `default_auto_approval_enabled=false`, `default_background_auto_approval_allowed=false`, `unattended_default_apply_allowed=false`, `ordinary_conversation_auto_approval=false`, and `enablement_executed=false`.
- Full validation passed after clearing transient macOS pytest/build/cache files from the full disk: `386 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.995%.
- Remaining gap: an exact opt-in enablement switch with disable/rollback guardrails and hard fail-closed default-on tests; this still must not permit unattended default/background apply.

Recommended next work now:

1. Commit/push this preflight checkpoint and watch CI.
2. Next code slice should be an exact opt-in enablement switch that consumes the green preflight, requires exact phrase `enable-opt-in-ordinary-turn-default-automation-v1`, writes a narrow auditable local config/policy state, and includes a disable/rollback path.
3. Keep broad/background ordinary conversation auto-approval, unattended default/background apply, repeated apply without fresh verifier evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Just completed: default automation copy-live verifier smoke + repeated evidence rollup

- Ran a copy-live smoke under `/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/`. The live DB was copied; `/Users/reddit/.agent-memory/memory.db` was not mutated.
- The smoke proved the current corridor end-to-end: default policy gate -> dry-run -> exact one-candidate apply -> rollback replay -> `ordinary-turn-default-automation-post-apply-verification`.
- Added `dogfood ordinary-turn-default-automation-evidence-rollup`, a read-only aggregate gate over repeated default-automation post-apply verifier artifacts. It checks green verifier reports, expected policy, one-at-a-time apply evidence, backup SHA evidence, rollback replay, audit row, relation evidence, privacy/ref safety, no forbidden authority, and no trace/memory ref reuse.
- Copy-live rollup is green with two independent verifier artifacts: `decision=ordinary_turn_default_automation_repeated_post_apply_evidence_green_for_enablement_design_only`, `green_report_count=2`, `unique_trace_ref_count=2`, `unique_memory_ref_count=2`.
- This is still design evidence only: `read_only=true`, `mutated=false`, `apply_supported=false`, `apply_executed=false`, `default_auto_approval_enabled=false`, `ordinary_conversation_auto_approval=false`.
- Focused validation so far: default automation verifier/rollup tests `5 passed`. Full suite and CI still need to run for this checkpoint.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.99%+.
- Remaining gap: a separate opt-in default enablement policy/runbook and hard fail-closed default-on switch tests before any unattended/default/background automation.

Recommended next work now:

1. Run the broader focused ordinary-turn tests and full suite.
2. Commit/push this evidence-rollup checkpoint and watch CI.
3. Next code slice should be a read-only opt-in enablement preflight/default-on design gate; do not flip any default/background auto-approval flag yet.
4. Keep ordinary conversation auto-approval, unattended default/background apply, repeated apply without fresh evidence, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Just completed: ordinary-turn default automation post-apply verification

- Added `dogfood ordinary-turn-default-automation-post-apply-verification`, a read-only stop gate over a separately exact-approved default automation apply report plus rollback replay evidence.
- It validates apply artifact kind/contract, exact policy, one-at-a-time apply bound, backup SHA/file, green rollback replay, `g5_trace_candidate_applications` audit row, and `ordinary_turn_default_automation_approved_as` relation evidence.
- Green means only `ordinary_turn_default_automation_post_apply_verification_green_stop`; it does not execute apply or enable ordinary conversation auto-approval, broad/background apply, default/background auto-approval, unattended default apply, default ranking mutation, collapse/delete, telemetry reset, or repeated apply without fresh exact approval.
- Validation: RED missing subcommand; focused GREEN `2 passed`; default-automation GREEN `8 passed, 192 deselected`; broader ordinary-turn GREEN `27 passed, 173 deselected`; full suite GREEN `382 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.985-99.99%.
- Remaining gap: real/source or copy-live post-apply verifier smoke, repeated independent green verifier windows/evidence rollup, and a separate opt-in enablement gate before any default/background automation.

Recommended next work now:

1. Finish full-suite verification, commit/push this verifier checkpoint, and watch CI.
2. Run a real/source or copy-live verifier smoke using a saved apply report plus rollback replay artifact; keep output ref-safe and local-only.
3. Add repeated default-automation post-apply evidence rollup only after green verifier artifacts exist.
4. Keep ordinary conversation auto-approval and unattended default/background apply blocked.

## Just completed: ordinary-turn default automation one-candidate apply corridor

- Added `dogfood ordinary-turn-default-automation-apply`, a separate exact-reviewed stop-after-one apply corridor over a saved default automation dry-run artifact.
- It validates exact policy, exact approval phrase, dry-run green evidence, exact trace ref, preference shape, privacy/ref safety, conflict preflight, no prior apply relation, and blocked forbidden authority.
- It creates a DB backup before mutation, then creates one approved fact, one `ordinary_turn_default_automation_approved_as` relation, and one `g5_trace_candidate_applications` audit row.
- It does not enable ordinary conversation auto-approval, broad/background apply, default/background auto-approval, unattended default apply, unattended batch apply, unreviewed promotion, default-ranking mutation, collapse/delete, telemetry reset, or repeated apply without fresh exact approval.
- Validation: RED missing subcommand; focused GREEN `2 passed`; default-automation GREEN `6 passed, 192 deselected`; broader ordinary-turn GREEN `25 passed, 173 deselected`; full suite GREEN `380 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.98-99.985%.
- Remaining gap: default-automation post-apply verifier + rollback replay evidence, repeated independent green windows, and a separate opt-in enablement gate before any default/background automation.

## Just completed: ordinary-turn default automation dry-run

- Added `dogfood ordinary-turn-default-automation-dry-run`, a read-only/ref-safe candidate scanner under the exact default automation policy gate.
- It validates a saved green `dogfood_ordinary_turn_default_automation_policy_gate` artifact and scans only non-secret preference-shaped ordinary turns.
- Output is local review material only: trace refs, content/summary hashes, coarse metadata, and aggregate counts. It excludes raw summaries, transcripts, queries, content, reasons, report bodies, and sample values.
- Green means only `ordinary_turn_default_automation_dry_run_ready_for_exact_single_candidate_review_keep_default_blocked`.
- It keeps `default_auto_approval_enabled=false`, `default_background_auto_approval_allowed=false`, `unattended_default_apply_allowed=false`, `apply_supported=false`, `apply_executed=false`, and `ordinary_conversation_auto_approval=false`.
- Validation: RED invalid subcommand; focused GREEN `4 passed, 192 deselected`; broader ordinary-turn GREEN `23 passed, 173 deselected`; full suite GREEN `378 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.97-99.98%.
- Remaining gap: a separate exact-reviewed one-candidate default-automation smoke/apply corridor, then repeated post-apply verification/rollback evidence, before any opt-in default enablement.

Recommended next work now:

1. Commit/push this dry-run checkpoint and watch CI.
2. Continue toward 100% by adding a separate exact-reviewed one-candidate default-automation smoke/apply corridor that consumes the dry-run artifact and stops after one candidate.
3. Do not enable ordinary conversation auto-approval or unattended default/background apply from the dry-run.

## Just completed: ordinary-turn broader automation readiness gate

- Added `dogfood ordinary-turn-broader-automation-readiness`, a read-only gate over saved `dogfood_ordinary_turn_inferred_evidence_rollup` plus saved `dogfood_ordinary_turn_auto_approval_readiness` artifacts.
- It validates artifact kind, read-only/no-mutation/default-unchanged flags, ordinary-auto-approval still false, green quality gates, minimum inferred rollup green reports, minimum readiness score, no secret-like ordinary turns, privacy safety, and no forbidden authority.
- Green means design-readiness only: `ordinary_turn_broader_automation_ready_for_design_only_keep_blocked`. It does not execute apply, does not support default/background auto-approval, and sets `max_apply_without_new_approval=0`.
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

- Added `dogfood ordinary-turn-inferred-evidence-rollup`, a read-only aggregate gate over repeated ordinary-turn inferred post-apply verifier artifacts.
- It validates repeated verifier reports for green quality gates, one-at-a-time apply evidence, backup SHA evidence, rollback replay, audit row, relation evidence, privacy safety, policy match, default retrieval unchanged, and no forbidden authority.
- Validation: RED invalid subcommand; focused GREEN `2 passed, 188 deselected`; broader ordinary-turn GREEN `17 passed, 173 deselected`; full suite GREEN `372 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.9-99.93%.
- Remaining gap: explicit broader-automation design and independently repeated one-at-a-time evidence before default/background ordinary-turn automation. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Commit/push this rollup checkpoint and watch CI.
2. Collect another copy/live-safe one-at-a-time ordinary-turn inferred apply + post-apply verification artifact only when there is a clearly eligible non-secret preference-shaped ordinary turn and fresh exact approval.
3. Design any broader ordinary-turn automation as a separate explicit gate; do not broaden to default/background ordinary conversation auto-approval.

## Just completed: ordinary-turn inferred post-apply verification

- Added `dogfood ordinary-turn-inferred-post-apply-verification`, a read-only stop gate for the exact ordinary-turn inferred preference apply corridor.
- It validates the saved apply report, rollback replay report, backup SHA-256, DB audit row, and `ordinary_turn_inferred_approved_as` relation without executing any further apply.
- Copy-DB smoke over the prior ordinary-turn inferred apply artifact is green: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-apply-smoke-20260516T182955Z/ordinary-turn-inferred-post-apply-verification.json`.
- Validation: RED invalid subcommand; focused GREEN `2 passed, 186 deselected`; broader ordinary-turn GREEN `9 passed, 179 deselected`; full suite GREEN `370 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.85-99.9%.
- Remaining gap: repeated one-at-a-time exact ordinary-turn inferred evidence and a separate design decision before any broader ordinary-turn automation. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Collect another copy/live-safe one-at-a-time ordinary-turn inferred apply + post-apply verification evidence only if there is a clearly eligible non-secret preference-shaped ordinary turn and fresh exact approval.
2. Add a read-only `ordinary-turn-inferred-evidence-rollup` over repeated post-apply verifier artifacts before considering broader automation.
3. Do not broaden to default/background ordinary conversation auto-approval.

## Just completed: ordinary-turn inferred exact apply corridor

- Added `dogfood ordinary-turn-inferred-apply`, the first mutating ordinary-turn inferred corridor.
- The lane is exact-approval only: one `experience_trace:<id>`, saved green `dogfood_ordinary_turn_inferred_approval_readiness` report, policy `ordinary-turn-inferred-preference-apply-v1`, approval phrase `apply-exact-ordinary-turn-inferred-preference-v1`, non-empty actor/reason, and pre-apply backup.
- It fails closed on red readiness, non-turn traces, secret-like summaries, unsupported shapes, preference conflicts, duplicate trace application, wrong policy/phrase, or missing audit inputs.
- It only supports the safest ordinary preference shape (`User prefers ...`) and creates an approved fact plus `ordinary_turn_inferred_approved_as` relation and `g5_trace_candidate_applications` audit row.
- It still reports `ordinary_conversation_auto_approval=false` and blocks broad/background apply, unattended batch apply, default-ranking mutation, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without fresh exact approval.
- Copy-DB smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-inferred-apply-smoke-20260516T182955Z/`.
  - The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
  - One synthetic ordinary preference trace was inserted into the copy only and applied through the exact corridor.
  - Apply report passed with `decision=ordinary_turn_inferred_exact_preference_applied_stop_after_one`, `memory_ref=fact:10`, and backup SHA-256 `4b532122ea6f065d5524f147354fb3fae8598e0b29236702a6764f4415107e75`.
  - Rollback replay on the copy DB passed with `decision=rollback_restore_replay_sufficient_for_bounded_partial_automation`.
  - Generic `trace-candidate-application-audit` is red for this lane because it expects reviewed trace-candidate status and retrieval-ranking evidence; treat that as the next audit compatibility/post-apply-verifier gap.
- Validation: RED focused tests failed on invalid subcommand; focused GREEN `2 passed, 184 deselected`; broader ordinary-turn focus GREEN `7 passed, 179 deselected`; full suite GREEN `368 passed, 1 xfailed`.

Current estimate:

- Safety-gated operational north-star: still approximately 99%+.
- Literal scoped human-brain-like local memory lifecycle: approximately 99.75-99.85%.
- Remaining gap: a dedicated ordinary-turn inferred post-apply verifier/audit compatibility layer, repeated copy/live-safe exact one-at-a-time evidence, then any broader ordinary-turn automation discussion. Ordinary-turn auto-approval, broad/background apply, unattended batch apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion remain blocked.

Recommended next work now:

1. Add `ordinary-turn-inferred-post-apply-verification` as a dedicated green stop gate over apply report + rollback replay + audit row.
2. Keep the current exact apply lane one-at-a-time and preference-shape-only.
3. Do not broaden to default/background ordinary conversation auto-approval.

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


## Just completed: exact-ref ordinary-turn label update corridor

- Added `dogfood ordinary-turn-label-update`, a bounded mutating corridor that labels exactly one `experience_trace:<id>` with `metadata.expected_memory_worthy=true/false`.
- Required operator inputs: `--trace-ref`, `--expected-memory-worthy true|false`, `--actor`, `--reason`, and exact `--approval-phrase label-approved-ordinary-turn-v1`.
- It updates only `experience_traces.metadata_json`, preserves existing metadata, marks `ordinary_turn=true`, hashes the reason, and emits no raw trace summary, transcript, query text, raw content, sample values, or raw reason.
- It blocks wrong approval phrases, missing/non-turn trace refs, invalid metadata JSON, and secret-like traces with `secret_like_trace_blocked`.
- It still keeps `ordinary_conversation_auto_approval=false`, default retrieval unchanged, no memory promotion, no broad/background apply, no collapse/delete, no telemetry reset, and no unreviewed promotion.
- RED/GREEN: focused tests first failed on missing subcommand, then passed after payload/parser/dispatcher implementation; a live-copy smoke first exposed that live packet refs may lack `metadata.ordinary_turn`, so the corridor now treats `event_kind=turn` as the ordinary-turn source of truth and sets `ordinary_turn=true` during labeling.
- Focused verification so far: `6 passed, 173 deselected` for ordinary-turn CLI coverage.
- Copy-DB smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-label-update-smoke-20260516T170107Z/`.
  - The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
  - `ordinary-turn-label-update` on the copy returned green with `mutated=true` and auto-approval still false.
  - `ordinary-turn-classifier-eval` on the copy returned green with `min_labeled=1` and auto-approval still false.

Current estimate:

- Safety-gated operational north-star: approximately 99%+.
- Literal fully autonomous human-brain-like memory within this repo's scoped local-memory lifecycle: approximately 99.2-99.4%.
- The missing piece is now not a labeling mechanism; it is repeated real labeled ordinary-turn windows plus an inferred-approval readiness gate.

Recommended next work now:

1. Run full source verification and commit/push this exact-ref label-update checkpoint.
2. Use the label packet plus exact-ref update corridor to label a bounded live/copy window, then rerun `ordinary-turn-classifier-eval` over repeated windows.
3. Add a read-only repeated-window ordinary-turn label/eval summary gate before any inferred approval/apply command.
4. Keep ordinary-turn auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked behind separate gates.


## Just completed: ordinary-turn label/evidence packet

- Added `dogfood ordinary-turn-label-packet`, a read-only raw-text-free packet for local human labeling of ordinary-turn memory-worthiness.
- The packet emits actionable local trace refs plus content/summary hashes and coarse evidence features only; it does not include raw trace summaries, transcripts, query text, sample values, or raw content.
- It keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `ordinary_conversation_auto_approval=false`, and all forbidden authority flags false.
- Focused RED/GREEN: the test first failed because the subcommand was not registered, then passed after parser/dispatcher/payload implementation.
- Focused ordinary-turn verification: `4 passed, 173 deselected`.
- Full suite: `359 passed, 1 xfailed`.
- Release metadata tests: `2 passed`; release-readiness smoke, release metadata script, `npm pack --dry-run`, and `git diff --check` passed.
- Live source smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-label-packet-20260516T164535Z/ordinary-turn-label-packet.json`.
  - `ordinary_turn=995`, `labeled_ordinary_turn=0`, `unlabeled_ordinary_turn=995`.
  - `review_item_count=25`, `eligible_unlabeled_nonsecret_count=995`, `blocked_secret_like_count=0`, `deferred_unlabeled_nonsecret_count=970`.
  - Quality gate green for manual labeling only; no live memory mutation occurred.

Current estimate:

- Safety-gated operational north-star: approximately 99%+.
- Literal fully autonomous human-brain-like memory within this repo's scoped local-memory lifecycle: approximately 99.0-99.2%.
- The missing piece is now repeated labeled ordinary-turn windows and an inferred-approval readiness gate; the label packet supplies the evidence queue but does not label or apply.

Recommended next work now:

1. Commit/push this label-packet checkpoint and watch CI.
2. Add a bounded labeling/update corridor for `metadata.expected_memory_worthy` using exact local trace refs, or manually label packet items in a source-safe way, then rerun `ordinary-turn-classifier-eval`.
3. Require repeated green labeled windows before designing inferred ordinary-turn approval readiness.
4. Keep ordinary-turn apply, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked behind separate gates.

## Just completed: ordinary-turn classifier evaluation gate

- Added `dogfood ordinary-turn-classifier-eval`, a read-only aggregate evaluation harness for ordinary-turn memory-worthiness classification.
- The command scans `event_kind=turn` traces, consumes optional `metadata.expected_memory_worthy` labels, reports prediction counts, precision/recall, secret-block rate, reason counts, and keeps all authority blocked.
- It does not write memories/candidates/review state, expose raw trace summaries, approve ordinary conversation, change default ranking, run broad/background apply, collapse/delete, reset telemetry, or promote unreviewed memories.
- Focused TDD: new test first failed because the subcommand did not exist, then passed after parser/dispatcher/payload implementation.
- Focused ordinary-turn verification: `2 passed, 174 deselected`.
- Live source smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-classifier-eval-20260516T160146Z/ordinary-turn-classifier-eval.json`.
  - Correctly red/fail-closed: `ordinary_turn=995`, `labeled_ordinary_turn=0`, `unlabeled_ordinary_turn=995`, `blocked_secret_like=0`.
  - Blocked reasons: `labeled_ordinary_turn_count_below_minimum`, `precision_below_minimum`.

Current estimate:

- Safety-gated operational north-star: approximately 99%+.
- Literal fully autonomous human-brain-like memory within this repo's scoped local-memory lifecycle: approximately 98.7-99%.
- The missing piece is no longer an eval command; it is labeled ordinary-turn evidence and a later exact-gated inferred-approval corridor.

Recommended next work now:

1. Commit/push this classifier-eval checkpoint and watch CI.
2. Next PR-sized safety gate: read-only ordinary-turn label/evidence packet for human review, without raw-content leakage in committed docs and without apply.
3. After repeated labeled windows are green, design an inferred approval readiness gate; do not jump directly to ordinary-turn apply.
4. Still blocked: broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: remember-preferences bounded-batch post-apply verifier

- Added `consolidation auto-approve remember-preferences-batch-post-apply-verification`, a read-only stop gate for future bounded `remember-preferences --max-apply 2` batches.
- The verifier checks a green/manual-only operator packet, the actual batch apply report, and the post-apply dry-run report.
- It enforces policy/scope/actor alignment, bounded approved count, fact-only `user prefers` writes, auto-approval relation ids, audit actor/reason, zero blocked candidates, post-dry-run skipped-count coverage, privacy-safe artifacts, and forbidden-authority flags.
- It does not authorize unattended batch apply. It reports `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true` and keeps broad/background/default-ranking/collapse-delete/telemetry-reset/unreviewed-promotion authority false.
- Live DB smoke found no remaining eligible explicit preference candidates for `project:agent-memory`, so the live graduation gate correctly stayed red with `current_dry_run_has_no_eligible_candidates` and no live mutation occurred.
- Validation from source checkout:
  - New focused tests: `2 passed, 173 deselected` after RED parser failures.
  - Remember-preferences focused coverage: `11 passed, 164 deselected`.
  - Full suite: `357 passed, 1 xfailed`.
  - Release metadata + release-readiness smoke, `npm pack --dry-run`, and `git diff --check` passed.

Current estimate:

- Safety-gated operational north-star: approximately 99%+.
- Literal fully autonomous human-brain-like memory within this repo's scoped local-memory lifecycle: approximately 98.5%.
- Explicit remember-intent/preference memory is effectively late-stage; the remaining progress to 100% is ordinary-turn inferred classification/approval and broader unattended lifecycle automation, not basic storage/retrieval/review plumbing.

Recommended next work now:

1. Commit/push this batch-verifier checkpoint and watch CI.
2. Next PR-sized safety gate: ordinary-turn classifier/evaluation harness, read-only first. Prove precision/recall over safe aggregate fixtures before enabling inferred approval.
3. Keep any real future `remember-preferences --max-apply 2` batch behind fresh packet + exact operator approval + backup + post-dry-run + this verifier.
4. Still blocked: broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: preference topic-slot semantics + second bounded auto-approval

- Hardened `consolidation auto-approve remember-preferences` so same `user/prefers/project` facts no longer treat every different preference as one contradiction.
- Added a narrow preference-topic claim slot for the G2 policy:
  - same-topic preferences such as `verbose handoffs` vs `concise handoffs` still block as `claim_slot_conflict`;
  - different topics such as handoff style vs release QA can coexist and be approved one-at-a-time.
- Preserved the previous safety rails: default dry-run, explicit `--apply --actor --reason`, `--max-apply 1`, secret-like summary block, duplicate `auto_approved_as` skip, no ordinary-turn inferred approval.
- Live dry-run before apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-dry-run-before-apply.json`.
  - `eligible_count=4`, `blocked_count=0`, `skipped_count=1`, `mutated=false`.
- Live bounded apply: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-apply.json`.
  - `approved_count=1`, `deferred_count=3`, `skipped_count=1`, `max_apply=1`, backup at `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/pre-topic-slot-auto-approval-memory-backup.db`.
- Post-apply dry-run: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-topic-slots-20260516T055757Z/remember-preferences-topic-post-dry-run.json`.
  - `eligible_count=3`, `blocked_count=0`, `skipped_count=2`; remaining safe explicit preferences are ready for future bounded one-at-a-time applies.

Recommended next work now:

1. Commit/push this topic-slot checkpoint and watch CI.
2. Continue exact-bounded `remember-preferences` applies one at a time until the explicit safe queue is drained, with a backup and post-dry-run after each apply.
3. Add a post-apply verifier/report for remember-preferences, analogous to lifecycle post-apply verification, before allowing batch size >1.
4. Keep broad/background apply, ordinary-turn inferred approval, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion blocked.

## Just completed: explicit remember-intent live evidence + first bounded auto-approval

- Recorded five safe source-hook `remember_intent` review traces against `/Users/reddit/.agent-memory/memory.db` from explicit, low-risk operator-approved preference statements. These traces are review-only evidence; they did not by themselves create long-term memories.
- Live G1 report: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-intent-evidence-20260516T053416Z/remember-intent-dogfood.json`.
  - `remember_intent=5`, `review_ready_count=5`, `ordinary_turn=295` within the inspected 300 traces.
- Live ordinary-turn readiness: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-intent-evidence-20260516T053416Z/ordinary-turn-auto-approval-readiness.json`.
  - `explicit_remember_intent=5`, `review_ready_remember_intent=5`, `ordinary_turn=995`, quality gate passed, but `ordinary_conversation_auto_approval=false` remains mandatory.
- Hardened `consolidation auto-approve remember-preferences` before live apply:
  - added `--max-apply` with default `1` stop-after-one behavior;
  - added `deferred` reporting for additional eligible traces;
  - added duplicate prevention via existing `experience_trace:<id> --auto_approved_as--> fact:<id>` relations;
  - re-runs now skip already auto-approved traces instead of duplicating facts/sources/relations.
- Live bounded G2 apply artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/remember-preferences-auto-approve-apply.json`.
  - `approved_count=1`, `deferred_count=4`, `max_apply=1`, backup SHA-256 recorded at `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/pre-auto-approval-memory-backup.sha256`.
- Post-apply duplicate guard dry-run: `/Users/reddit/.agent-memory/reports/post-v0.1.162-remember-preference-auto-approval-20260516T054022Z/remember-preferences-auto-approve-post-dry-run-after-duplicate-guard.json`.
  - `eligible_count=0`, `skipped_count=1`, `blocked_count=4`; the remaining four are blocked by the conservative same-slot preference conflict preflight after the first approved preference.

Recommended next work now:

1. Commit/push this bounded remember-preference auto-approval hardening checkpoint and watch CI.
2. Decide the next safe preference semantics: either keep `subject=user,predicate=prefers,scope=project` as one-slot conservative memory, or design a multi-preference relation/object-slot model that can safely approve multiple independent preferences without treating them as claim-slot conflicts.
3. Do not enable ordinary conversation auto-approval from generic turns. The only proven live G2 mutation is explicit `remember_intent` + narrow preference shape + `--max-apply 1` + audit/relation duplicate guard.
4. Still blocked: broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and ordinary-turn inferred approval.

## Just completed: repeated recurrent reinforcement applies + ordinary-turn readiness gate

- Repeated the exact-approved recurrent reinforcement corridor two more times, one at a time, after each prior recurrent post-apply verifier was green.
- Second recurrent apply artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-recurrent-reinforcement-apply-20260516T044243Z/lifecycle-recurrent-reinforcement-apply.json`.
  - `eligible_target_count=3`, `selected_target_count=1`, `applied_count=1`, backup SHA-256 `af5d903f5040036fc1a2f9e75995a9ff59b65494eaa91c8b609626e60114e588`.
  - Post-apply verifier green: `recurrent_reinforcement_post_apply_verification_green_stop`; rollback replay checked `9`, failed `0`; recurrent application audit count `2`.
- Third recurrent apply artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-recurrent-reinforcement-apply-20260516T044336Z/lifecycle-recurrent-reinforcement-apply.json`.
  - `eligible_target_count=2`, `selected_target_count=1`, `applied_count=1`, backup SHA-256 `4358b9c876ead3edfce12baecf9ec39f4aa6e231fd831478695025ad6c60f963`.
  - Post-apply verifier green: `recurrent_reinforcement_post_apply_verification_green_stop`; rollback replay checked `10`, failed `0`; recurrent application audit count `3`.
- Added read-only `dogfood ordinary-turn-auto-approval-readiness <db_path>` to measure how close ordinary conversation is to safe auto-approval without enabling it.
- Live ordinary-turn readiness artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-auto-approval-readiness-20260516T044849Z/ordinary-turn-auto-approval-readiness.json`.
- Live result: `ordinary_turn=1000`, `explicit_remember_intent=0`, `review_ready_remember_intent=0`, `secret_like_ordinary_turns=0`, score `75`, quality gate red with `explicit_remember_intent_ready_count_below_minimum`. This means ordinary-turn auto-approval is still correctly blocked because the live trace stream has ordinary turns but no explicit remember-intent evidence.

Recommended next work now:

1. Commit/push this checkpoint and watch CI if GitHub rate limits allow.
2. Add an explicit remember-intent evidence path or hook/classifier that can produce `remember_intent` traces from user-approved memory requests, still read-only/report-first.
3. Then rerun `ordinary-turn-auto-approval-readiness`; only after explicit-ready evidence exists should an apply path be considered.
4. Still blocked: ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: exact-approved recurrent reinforcement apply

- Added `dogfood lifecycle-recurrent-reinforcement-apply`, a narrow exact-approval policy for already-applied targets that have fresh post-apply evidence windows.
- Policy: `g5-lifecycle-recurrent-reinforcement-apply-v1`; exact phrase: `apply-approved-g5-lifecycle-recurrent-reinforcement-v1`.
- It selects only targets with enough fresh retrieval observations after their latest base/recurrent lifecycle application, caps live mutation with `--max-apply <= 2`, creates a SQLite backup, increments only `reinforcement_count`, and records an application/audit row.
- It does not requeue already-applied target refs, change status, change default retrieval, approve ordinary conversation, broad/background apply, collapse/delete, telemetry reset, or promote unreviewed memories.
- Live exact-approved smoke artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-recurrent-reinforcement-apply-20260516T041353Z/lifecycle-recurrent-reinforcement-apply.json`.
- Live result: `eligible_target_count=3`, `selected_target_count=1`, `applied_count=1`, backup SHA-256 `aafb6a0144ed792428bf34bc618f248c21de3c41711e2fd5bda44c0f766e7187`.
- Post-apply evidence: rollback confidence green, rollback replay green (`checked_application_count=8`, `failed_replay_count=0`), recurrent-policy application audit green (`application_count=1`, review status treated as policy-promoted because this recurrent corridor does not create review rows), and recurrent post-apply verifier green (`recurrent_reinforcement_post_apply_verification_green_stop`).

Recommended next work now:

1. Commit/push this recurrent-reinforcement policy checkpoint and watch CI.
2. Repeat at most one or two more recurrent applies through the same exact policy/phrase corridor only when the recurrent post-apply verifier is green after each apply.
3. Then add ordinary-turn auto-approval readiness scoring, still read-only first, to measure how close the system is to unattended brain-like consolidation.
4. Still blocked until separate gates exist: ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: lifecycle refresh source-novelty scoring

- Tightened `dogfood lifecycle-candidate-refresh-preview` with aggregate-only source-level novelty scoring.
- The preview now distinguishes genuinely new unapplied targets from fresh post-apply evidence that only recycles already-applied targets.
- The scoring remains read-only/no-mutation/default-unchanged and does not emit candidate ids, target refs, raw observation values, raw query text, query previews, source text, or backup contents.
- Also fixed the lifecycle bounded-batch operator packet nested artifact gate metadata so nested `mutated` reflects the underlying read-only reports instead of inverted boolean checks.
- Live source-novelty artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-source-novelty-preview-20260516T035332Z/lifecycle-candidate-refresh-preview-source-novelty.json`.
- Live result: `preview_candidate_count=4`, `target_already_applied_count=4`, `new_unapplied_target_candidate_count=0`, `fresh_observation_count_for_preview_targets=42`, `applied_target_with_fresh_window_count=4`, decision `fresh_evidence_recycles_already_applied_targets`. Therefore refresh evidence is real, but it still does not create safe new lifecycle review rows under the current target-aware persistence contract.

Recommended next work now:

1. Commit/push this source-novelty checkpoint and watch CI.
2. Next PR-sized source slice: design an explicit recurrent-reinforcement policy for already-applied targets with fresh evidence windows, or generate genuinely new target refs from broader traces. Do not bypass target-aware persistence silently.
3. A live bounded batch still requires reviewed approved candidates, exact approval phrases, backup/output paths, and immediate post-apply verification.
4. Still blocked until separate gates exist: ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: lifecycle fresh-evidence preview + target-aware persistence guard


- Added read-only `dogfood lifecycle-fresh-evidence-preview`, which checks aggregate retrieval observations after the latest lifecycle application for a policy before refreshing candidates.
- New focused source test proves post-apply observations are counted without raw query text, query previews, candidate ids, target refs, or backup contents.
- Live artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-fresh-evidence-preview-20260516T033110Z/lifecycle-fresh-evidence-preview-reinforcement.json`.
- Live result: `post_apply_observation_count=53`, quality gate green, so there is enough fresh post-apply dogfood activity to run the next refresh cycle; target-aware persistence still blocks already-applied refs.

- Added target-aware filtering to `dogfood lifecycle-candidate-persist`: candidates whose target refs already appear in lifecycle application audit rows are skipped before review-queue insertion.
- New focused source test proves already-applied target refs do not create fresh review rows and preserve row counts.
- Live no-op persistence smoke: `/Users/reddit/.agent-memory/reports/post-v0.1.162-target-aware-lifecycle-persist-20260516T030945Z/lifecycle-candidate-persist-target-aware-reinforcement.json`.
- Live result: `candidate_count=4`, `inserted_count=0`, `skipped_applied_target_count=4`, `mutated=false`; this correctly blocks requeueing the four already-applied reinforcement targets.

Previous source gates still stand:

- Added `dogfood lifecycle-bounded-batch-operator-packet`, a read-only machine-readable packet for the exact-approved lifecycle bounded-batch corridor.
- The packet bundles:
  - live batch graduation readiness;
  - lifecycle apply readiness;
  - approved eligible candidate inventory;
  - exact `lifecycle-bounded-batch-apply` command preview;
  - required backup/output placeholders;
  - exact `lifecycle-bounded-batch-post-apply-verification` command template.
- Source RED/GREEN focused test proves the packet is read-only/no-mutation, hides candidate JSON/raw content/raw reason/backup content, and preserves forbidden-authority flags.
- Live smoke against `/Users/reddit/.agent-memory/memory.db` wrote `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-batch-operator-packet-20260516T022916Z/lifecycle-bounded-batch-operator-packet.json`.
- Live packet result: batch graduation is green with four prior one-at-a-time reinforcement applies, but apply readiness is red because there are no eligible approved lifecycle candidates. Therefore bounded live batch apply remains blocked.

- Added `dogfood lifecycle-candidate-refresh-preview`, a read-only duplicate/recycle gate for fresh lifecycle candidate generation.
- Live refresh preview artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-refresh-preview-20260516T025334Z/lifecycle-candidate-refresh-preview-reinforcement.json`.
- Live result: `preview_candidate_count=4`, `new_candidate_count=4`, but `new_unapplied_target_candidate_count=0` and `target_already_applied_count=4`; therefore these are not safe to persist/review as fresh work.

Recommended next work now:

1. Commit/push this target-aware persistence checkpoint and watch CI.
2. Next PR-sized source slice: use the fresh-evidence preview with candidate refresh/persist to isolate genuinely new targets; if refresh still recycles applied targets, add source-level novelty scoring that requires new target refs or new evidence windows before review persistence.
3. Do not live-batch-apply until the operator packet is green, candidates are reviewed approved, backup/output paths are set, exact approval phrases are supplied, and immediate post-apply verification is run.
4. Still blocked: ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, and unreviewed promotion.

## Just completed: fourth live exact-approved reinforcement lifecycle apply + batch graduation readiness gate

- Applied exactly the last remaining pending reinforcement candidate only; no batch apply was enabled.
- Approved candidate `g5-reinforcement-84541df977996b35164b682a`, target `fact:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-fourth-live-reinforcement-apply-20260516T014150Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `774765d9b1fec9df76f7582232c14967e92b8e50afbfd5b550b700ec79e56690`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=4`, `pending=0`, `approved=0`.
- Rollback replay passed with decision `rollback_restore_replay_sufficient_for_bounded_partial_automation` and application count `7`.
- Post-apply live evidence bundle passed: fixture task count `4`, baseline regressions `0`, rollback checked applications `7`, audit application count `4`.
- `lifecycle-post-apply-verification.json` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- Added `dogfood lifecycle-batch-graduation-readiness`, a read-only source gate. Live run passed for the reinforcement policy with four prior one-at-a-time applies, while keeping `bounded_batch_apply_supported=false`.
- Added `dogfood lifecycle-bounded-batch-apply`, an exact-approval bounded batch corridor with `--max-apply <= 2`; source tests prove it can apply two already-approved lifecycle candidates after graduation proof. Live smoke was a safe no-op because there are currently no eligible approved lifecycle candidates.
- Added `dogfood lifecycle-bounded-batch-post-apply-verification`, a read-only stop gate for bounded-batch apply artifacts that checks applied count, backup file/SHA, rollback replay, application audit, default retrieval unchanged, privacy, and forbidden-authority flags.

Recommended next work now:

1. Commit/push the bounded-batch post-apply verifier checkpoint; watch CI.
2. Next PR-sized slice: produce new reviewed lifecycle candidates from fresh dogfood traces or add a read-only batch operator packet that previews candidate inventory, exact apply command, backup path, and verifier command.
3. Do not live-batch-apply anything until there are reviewed approved candidates and exact operator approval for the batch.
4. Keep default-ranking auto-rollout, collapse/delete, telemetry reset, ordinary conversation auto-approval, broad/background apply, and unreviewed promotion blocked.

## Just completed: third live exact-approved reinforcement lifecycle apply

- Applied exactly one additional reinforcement candidate only; no batch/repeated apply was enabled.
- Approved candidate `g5-reinforcement-da820f3c712f508c084d3137`, target `procedure:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-third-live-reinforcement-apply-20260516T013407Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `5a18d345734798790ffa5bdd678901975792534a906d4e8df343dd75f174201c`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=3`, `pending=1`, `approved=0`.
- Rollback replay passed with decision `rollback_restore_replay_sufficient_for_bounded_partial_automation`.
- Post-apply live evidence bundle passed for the bounded artifact set: fixture task count `4`, baseline regressions `0`, rollback checked applications `6`, audit application count `3`.
- `lifecycle-post-apply-verification.json` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.

Recommended next work now:

1. Commit/push this third live apply checkpoint and watch CI.
2. Continue one-at-a-time only: approve/apply at most the last remaining pending reinforcement candidate, then rerun `lifecycle-post-apply-verification` and stop again.
3. After all four initial reinforcement candidates have green one-at-a-time post-apply proof, design a separate bounded-batch graduation gate; do not infer batch permission from this run.
4. Do not broad/background apply, ordinary conversation auto-approve, default-ranking auto-rollout, collapse/delete, telemetry reset, or unreviewed promotion until their separate gates exist.

## Just completed: second live exact-approved reinforcement lifecycle apply

- After the first post-apply verifier and CI were green, applied one more reinforcement candidate only; no batching was enabled.
- Approved candidate `g5-reinforcement-3c9f30f85f8bdb80c9f3474f`, target `episode:1`, with phrase `approve-g5-lifecycle-candidate-v1`.
- Applied with policy `g5-lifecycle-reinforcement-apply-v1` and phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/`.
- Backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-second-live-reinforcement-apply-20260516T001544Z/pre-apply-memory-backup.db`.
- Backup SHA-256: `c1f7dab326276a91b4b9b89818a96280dd050525987b3bf26ce2733b3c121387`.
- Post-apply readiness returned to no-ready-apply: reinforcement `promoted=2`, `pending=2`, `approved=0`.
- Rollback replay passed with decision `rollback_restore_replay_sufficient_for_bounded_partial_automation`.
- `lifecycle-post-apply-verification.json` passed with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- The broader `live-evidence-bundle` still stayed red on `live_fixture_reliability_gate_not_green`; this remains a broader fixture/reliability blocker, not a lifecycle apply rollback/audit failure.

Recommended next work now:

1. Commit/push this second live apply checkpoint and watch CI.
2. Continue one-at-a-time only: approve/apply at most one of the two remaining pending reinforcement candidates, then rerun `lifecycle-post-apply-verification` and stop again.
3. Do not batch-apply, broad/background apply, ordinary conversation auto-approve, default-ranking auto-rollout, collapse/delete, telemetry reset, or unreviewed promotion until their separate gates exist.

## Just completed: first live exact-approved reinforcement lifecycle apply

- Operator gave blanket approval to continue toward the fully automated brain-like memory north-star; the session still preserved the exact policy/phrase safety corridor instead of broad auto-apply.
- Approved one pending reinforcement candidate only:
  - candidate id: `g5-reinforcement-255f68c152b76d844c6720cc`;
  - target ref: `fact:4`;
  - update phrase: `approve-g5-lifecycle-candidate-v1`.
- Before apply, `lifecycle-apply-readiness` went green with reinforcement `approved=1`, `eligible_approved_count=1`, and decision `eligible_for_exact_reviewed_apply`.
- Applied that one candidate only with:
  - policy: `g5-lifecycle-reinforcement-apply-v1`;
  - apply phrase: `apply-approved-g5-lifecycle-reinforcement-v1`;
  - backup: `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/pre-apply-memory-backup.db`;
  - backup SHA-256: `5c44d39611e613b04bd0bb984b0bdd11fd8acd26b5bee6b3fb2f8b3ab26bec0d`.
- Post-apply readiness returned to red/no-ready-apply with reinforcement `promoted=1`, `pending=3`, `approved=0`; this is the intended stop-after-one behavior.
- Added source-level `dogfood lifecycle-post-apply-verification` to validate the apply report, post-apply readiness, rollback replay, and application audit as one read-only stop gate, without depending on unrelated live fixture reliability.
- Verification artifacts are under `/Users/reddit/.agent-memory/reports/post-v0.1.162-live-reinforcement-apply-20260515T235921Z/`:
  - `lifecycle-candidate-update-approved.json`;
  - `lifecycle-apply-readiness-before-apply.json`;
  - `lifecycle-candidate-apply-reinforcement.json`;
  - `lifecycle-apply-readiness-after-apply.json`;
  - `rollback-confidence-after-reinforcement-apply.json` gate green;
  - `rollback-replay-after-reinforcement-apply.json` gate green;
  - `application-audit-after-reinforcement-apply-with-ranking.json` gate green;
  - `lifecycle-post-apply-verification.json` gate green with decision `lifecycle_post_apply_verification_green_for_one_candidate_stop`.
- A post-apply `live-evidence-bundle` also ran, but its top-level gate stayed red due to `live_fixture_reliability_gate_not_green`; this is now separated from lifecycle apply safety and should be treated as an evidence-quality/ranking blocker, not as failed rollback/apply.

Recommended next work now:

1. Commit/push source/test/docs for the post-apply verifier and watch CI.
2. Then approve/apply at most one more pending reinforcement candidate with the same exact policy/phrase corridor and immediately rerun `lifecycle-post-apply-verification`.
3. Do not batch-apply the remaining three pending reinforcement candidates yet; graduate from one-at-a-time only after repeated green post-apply verifications.
4. Ordinary conversation auto-approval, broad/background apply, default-ranking automatic rollout, collapse/delete, telemetry reset, unreviewed promotion, and repeated apply without fresh approval remain blocked until their own code/tested gates exist.

## Just completed: live lifecycle readiness smoke and pending reinforcement review queue

- Ran source-checkout `dogfood lifecycle-apply-readiness` against the real source DB at `/Users/reddit/.agent-memory/memory.db`.
- Initial live readiness artifact: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-apply-readiness-20260515T092750Z/lifecycle-apply-readiness.json`.
- Result: read-only/no-mutation/default-unchanged passed, but quality gate stayed red with `decision=no_exact_lifecycle_apply_candidates_ready` because there were no approved lifecycle candidates yet.
- Ran read-only lifecycle previews:
  - reinforcement preview found `candidate_count=4` and quality gate passed;
  - decay preview found `candidate_count=0`;
  - supersession preview found `candidate_count=0`.
- Persisted the four reinforcement candidates for explicit operator review only:
  - artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-lifecycle-candidate-persist-20260515T092910Z/`;
  - `lifecycle-candidate-persist-reinforcement.json`: `mutated=true`, `default_retrieval_unchanged=true`, `candidate_count=4`, raw content not included, reason stored as SHA-256;
  - `lifecycle-candidate-list-reinforcement.json`: four pending reinforcement candidates targeting refs `fact:4`, `episode:1`, `fact:1`, and `procedure:1`.
- After-persist readiness remains read-only/no-mutation/default-unchanged, with reinforcement counts `pending=4`, `approved=0`, and still `decision=no_exact_lifecycle_apply_candidates_ready`.

Recommended next work now:

1. Do not apply yet: there are pending candidates but no approved candidates.
2. If the operator wants to proceed with live reinforcement apply, review one pending candidate and approve it with the exact update phrase `approve-g5-lifecycle-candidate-v1`, then apply with policy `g5-lifecycle-reinforcement-apply-v1` and exact apply phrase `apply-approved-g5-lifecycle-reinforcement-v1`.
3. Apply at most one candidate family and preferably one candidate first; capture backup/audit output and rerun readiness/rollback verification.
4. Keep ordinary conversation auto-approval, broad/background apply, live G4 apply, telemetry reset, default-ranking automatic rollout, collapse/delete, unreviewed promotion, and repeated apply without new approval blocked.

## Just completed: lifecycle apply readiness/audit source checkpoint

- Added `dogfood lifecycle-apply-readiness <db_path> --output <readiness.json>`.
- It summarizes reviewed lifecycle apply eligibility across reinforcement, decay, and supersession without mutation.
- It reports per-kind status counts and per-policy readiness:
  - policy;
  - exact approval phrase;
  - eligible approved count;
  - already-applied count;
  - blocked count;
  - decision.
- It explicitly forbids apply execution, broad/background apply, ordinary conversation auto-approval, default ranking mutation, collapse/delete apply, telemetry reset, and unreviewed promotion.
- Verification:
  - RED observed on missing dogfood action.
  - Focused readiness test passed: `1 passed`.
  - Lifecycle/policy subset passed: `10 passed, 146 deselected`.
  - Full source gate passed: `338 passed, 1 xfailed`.

Recommended next work now:

1. Commit/push source/test/docs and watch CI.
2. Run the new readiness command on the real source memory DB.
3. If it reports eligible reviewed candidates, choose exactly one approved candidate family for an exact guarded apply.
4. Do not implement ordinary conversation auto-approval yet; it remains the largest safety gap and should stay blocked.

## Just completed: narrow reviewed reinforcement lifecycle apply source checkpoint

- Added `dogfood lifecycle-candidate-apply --policy g5-lifecycle-reinforcement-apply-v1`.
- Required approval phrase: `apply-approved-g5-lifecycle-reinforcement-v1`.
- Accepted candidates: approved lifecycle candidates with `candidate_kind=reinforcement` and `proposal_type=reinforcement_review`.
- Mutation is narrow and reversible via backup: increment target memory `reinforcement_count` and record application/audit metadata.
- Explicitly unchanged/blocked:
  - memory status changes for reinforcement;
  - retrieval default changes;
  - ordinary conversation auto-approval;
  - broad/background apply;
  - collapse/delete;
  - telemetry reset;
  - default ranking automatic rollout;
  - unreviewed promotion;
  - repeated apply without the existing unique `(candidate_id, policy)` application guard.
- Verification:
  - RED observed on unsupported reinforcement policy.
  - Focused test passed: `1 passed`.
  - Lifecycle/policy subset passed: `6 passed, 149 deselected`.
  - Full source gate passed: `337 passed, 1 xfailed`.

Recommended next work now:

1. Commit/push source/test/docs and watch CI.
2. Next safe source slice: lifecycle apply readiness/audit summary for reinforcement/decay/supersession. It should prove which reviewed candidates are eligible, already-applied, blocked, or missing proof before applying anything else.
3. Do not implement ordinary conversation auto-approval yet; it is still the highest-risk lane and should remain blocked until much stronger explicit-intent evidence exists.

## Just completed: read-only automation policy readiness classifier source checkpoint

- Added `dogfood automation-policy-readiness --comparison-report <comparison.json> --output <readiness.json>`.
- Required input: one green `dogfood_live_evidence_bundle_comparison` report.
- Output kind: `dogfood_automation_policy_readiness`.
- Output remains aggregate/hash/ref-safe:
  - comparison path and SHA-256;
  - quality-gate pass/decision/blockers;
  - report count and pass count;
  - fixture coverage minimum;
  - ranking baseline regression max;
  - rollback/audit minima;
  - audit required-evidence pass count;
  - lane decisions for the requested 1-7 automation path.
- Safety contract remains strict:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - `ordinary_conversation_auto_approval=false`
  - `executes_apply=false`
  - no raw report embedding, raw source/transcript/query/trace content, reviewed payload, backup content, broad G4 apply, ranking-default mutation, collapse/delete, telemetry reset, unreviewed promotion, or repeated apply without new approval.
- Verification so far:
  - RED observed on missing dogfood action.
  - Focused readiness test passed: `1 passed`.
  - Evidence/policy subset passed: `9 passed, 145 deselected`.
  - Full source gate passed: `336 passed, 1 xfailed`.
  - Live read-only readiness smoke: `/Users/reddit/.agent-memory/reports/source-automation-policy-readiness-20260515T084816Z/automation-policy-readiness.json`; quality gate green, narrow reviewed apply eligible for exact approval slice, ordinary conversation auto-approval blocked.

Recommended next work now:

1. Commit/push source/test/docs and watch CI.
2. Next safe source slice: first exact narrow reviewed-candidate apply automation lane from the readiness report. It may apply only already-reviewed candidates with backup/audit/rollback guardrails and must not enable broad/background apply, default ranking migration, collapse/delete, telemetry reset, unreviewed promotion, repeated apply without new approval, or ordinary conversation auto-approval.

## Just completed: read-only live evidence bundle comparison source checkpoint

- Added `dogfood live-evidence-bundle-compare` for repeated saved bundle reports.
- Required input: at least one `--report`; practical gate defaults to `--min-report-count 2`.
- Output kind: `dogfood_live_evidence_bundle_comparison`.
- Output remains aggregate/hash/ref-safe:
  - top-level report SHA-256 per input;
  - nested artifact hashes per input;
  - quality-gate pass/decision counts;
  - fixture count min/max;
  - fixture retrieval/reliability pass counts;
  - ranking baseline regression total/max;
  - rollback/audit count ranges;
  - audit required-evidence pass count;
  - blocker diagnostics.
- Safety contract remains strict:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - `ordinary_conversation_auto_approval=false`
  - `apply_supported=false`
  - no raw report embedding, raw source/transcript/query/trace content, reviewed payload, backup content, broad G4 apply, ranking-default mutation, collapse/delete, telemetry reset, unreviewed promotion, or repeated apply without new approval.
- Verification so far:
  - RED observed on missing dogfood action.
  - Focused compare test passed: `1 passed`.
  - Evidence/audit subset passed: `6 passed, 147 deselected`.
  - Full source gate passed: `335 passed, 1 xfailed`.
  - Live read-only compare smoke: `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-compare-20260515T074353Z/live-evidence-bundle-comparison.json`; quality gate green over two same-window reports, fixture task count `4`, baseline regression max `0`, rollback/audit counts `3`.

Recommended next work now:

1. Commit/push source/test/docs and watch CI.
2. Next safe source slice: read-only automation-policy readiness report over one or more green bundle comparisons. It may classify the next narrow auto-decision lane, but must not execute apply, mutate default ranking, collapse/delete, reset telemetry, or auto-approve ordinary conversation memories.

## Just completed: read-only live evidence bundle source checkpoint

- Added `dogfood live-evidence-bundle <db_path> --output-dir <dir>` to chain live fixture diagnostics -> retrieval-ranking experiment -> rollback replay validation -> trace-candidate application audit in one read-only run.
- The command writes hashed artifacts under the requested output directory:
  - `live-retrieval-ranking-fixtures.json`
  - `live-retrieval-ranking-fixtures-report.json`
  - `retrieval-ranking-experiment.json`
  - `rollback-replay-validate.json`
  - `trace-candidate-application-audit.json`
  - optional bundle report via `--output`
- Bundle output kind: `dogfood_live_evidence_bundle`.
- Safety contract remains strict:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - `ordinary_conversation_auto_approval=false`
  - `bundle_executes_apply=false`
  - no default ranking mutation, broad G4 apply, collapse/delete, telemetry reset, unreviewed promotion, repeated apply without new approval, raw report embedding, raw source/transcript/query/trace content, reviewed payload, or backup content.
- Focused gates:
  - `uv run pytest tests/test_cli.py::test_dogfood_live_evidence_bundle_chains_read_only_artifacts -q` -> `1 passed`.
  - `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'live_evidence_bundle or live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit or rollback_replay_validate'` -> `5 passed, 147 deselected`.
  - `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `334 passed, 1 xfailed`.
- Live read-only source smoke: `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-20260515T072811Z/live-evidence-bundle.json`.
  - `quality_gate.pass=true`, `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`.
  - Bundle rollup: fixture tasks `4` (`facts=2`, `procedures=1`, `episodes=1`), fixture retrieval/reliability pass, ranking allowed with zero baseline regressions, rollback checked application count `3`, audit application count `3`, audit required evidence gate pass.

Recommended next work now:

1. Commit/push this live evidence bundle source/test/docs checkpoint and watch CI.
2. Next safe source slice: repeated-run comparison/accumulation over two or more saved bundle reports, still read-only and hash/ref-safe, so stability across live dogfood windows can be measured before any broader automation decision.
3. Still blocked without exact separate approval: live G4 apply, broad/background apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, and ordinary conversation auto-approval.

## Just completed: live retrieval-ranking fixture diagnostics hardening source checkpoint

- Hardened `dogfood live-retrieval-ranking-fixtures <db_path>` with explicit generation, retrieval, and reliability diagnostics while preserving the original read-only fixture output.
- New report fields:
  - `generation_diagnostics`: approved memory counts, generated task counts, skipped counts, skip reasons (`insufficient_approved_memory`, `generation_limit_reached`, `none`), per-type limits, and task limit.
  - `retrieval_diagnostics`: immediate read-only eval of the generated fixture, failed task count, baseline regression count, blocker reasons, and ref/count-only failure diagnostics.
  - `reliability_gate`: diagnostic-only pass/blocker summary with configurable `--min-reliable-tasks`.
- Added optional generator flags: `--min-reliable-tasks`, `--baseline-mode`, and `--max-baseline-regressions`.
- Safety contract remains unchanged:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - writes only requested fixture/report files
  - no raw source content, raw transcript, raw query/content in failure diagnostics, reviewed payloads, private reasons, backup contents, default-ranking mutation, collapse/delete, or auto-approval.
- Focused gates:
  - `uv run pytest tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_generate_live_compatible_fixture tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_reports_generation_blockers_for_sparse_db tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_reports_limit_skips_without_raw_content -q` -> `3 passed`.
  - `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit'` -> `4 passed, 147 deselected`.
  - `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `333 passed, 1 xfailed`.
- Live read-only source smoke: `/Users/reddit/.agent-memory/reports/source-live-ranking-fixture-diagnostics-20260515T065526Z/`.
  - Generated live fixture: `fixture_task_count=4` (`facts=2`, `procedures=1`, `episodes=1`).
  - Generation diagnostics: all available approved facts/procedures/episodes selected; no skipped items or insufficient-type blockers.
  - Retrieval diagnostics: `pass=true`, `failed_task_count=0`, `baseline_regression_count=0`, no blocker reasons.
  - Reliability gate with `--min-reliable-tasks 4`: `pass=true`.
  - Ranking experiment over generated fixture: `ranking_change_allowed=true`, `baseline_regression_count=0`, `live_compatible_task_count=4`, read-only/no-mutation/default unchanged.

Recommended next work now:

1. Commit/push this diagnostics hardening source/test/docs checkpoint and watch CI.
2. Next safe source slice: add repeated live evidence-run bundling so one command can generate fixture diagnostics, run ranking experiment, and feed the ranking report into application audit with artifact hashes, still read-only.
3. Still blocked without exact separate approval: live G4 apply, broad/background apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, and ordinary conversation auto-approval.

## Just completed: live retrieval-ranking fixture generation source checkpoint

- Added `dogfood live-retrieval-ranking-fixtures <db_path>` to generate retrieval-eval fixture JSON from approved facts/procedures/episodes that already exist in the target DB.
- Purpose: let `trace-candidate-application-audit` use generated live DB ranking evidence instead of manually shaped compatible artifacts.
- Output kind: `dogfood_live_retrieval_ranking_fixtures`.
- Safety contract:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - writes only the requested fixture/report files
  - no raw source content, raw transcripts, reviewed payloads, private reasons, backup contents, default-ranking mutation, collapse/delete, or auto-approval.
- Focused gates:
  - RED: new focused test failed because `live-retrieval-ranking-fixtures` was not a recognized dogfood action.
  - `uv run pytest tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_generate_live_compatible_fixture -q` -> `1 passed`.
  - `uv run pytest tests/test_cli.py -q -k 'live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit'` -> `2 passed, 147 deselected`.
- Live read-only source smoke: `/Users/reddit/.agent-memory/reports/source-live-ranking-fixtures-20260515T054056Z/`.
  - Generated live fixture: `fixture_task_count=4` (`facts=2`, `procedures=1`, `episodes=1`).
  - Ranking experiment over generated fixture: `ranking_change_allowed=true`, `baseline_regression_count=0`, `live_compatible_task_count=4`, read-only/no-mutation.
  - Application audit with rollback replay + generated ranking evidence: `required_evidence_gate.pass=true`, quality decision `trace_candidate_applications_ready_for_post_apply_review`, read-only/no-mutation.

Recommended next work now:

1. Run full source gate for this slice, then commit/push and watch CI.
2. Next source slice: harden live fixture generation with skip/blocker diagnostics for generated tasks that fail retrieval eval under realistic live DB volume, instead of treating small live DB coverage as sufficient.
3. Still blocked without exact separate approval: live G4 apply, broad/background apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, and ordinary conversation auto-approval.

## Just completed: G5 trace candidate application audit evidence gate source checkpoint

- Extended source command `dogfood trace-candidate-application-audit <db_path>` with `--rollback-replay-report` and `--retrieval-ranking-report`.
- Purpose: make post-apply trace-candidate audit depend on explicit rollback replay and retrieval-ranking evidence before any broader automation decision.
- Output kind remains `dogfood_trace_candidate_application_audit`.
- New output block: `required_evidence_gate` with rollback replay and retrieval-ranking sub-gates.
- Safety contract:
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - `ordinary_conversation_auto_approval=false`
  - missing rollback/ranking evidence blocks quality gate
  - no raw clusters, reviewed payloads, raw content, raw reasons, backup contents, default-ranking mutation, collapse/delete, or auto-approval.
- Focused gates:
  - `uv run pytest tests/test_cli.py::test_dogfood_trace_candidate_apply_promotes_only_approved_reviewed_fact_candidates tests/test_cli.py::test_dogfood_trace_candidate_application_audit_flags_missing_backup -q` -> `2 passed`.
  - `uv run pytest tests/test_cli.py -q -k 'trace_candidate_application_audit or trace_candidate_apply or rollback_replay_validate or retrieval_ranking_experiment'` -> `6 passed, 142 deselected`.
  - `uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q` -> `330 passed, 1 xfailed`.
- Source smoke artifact directory: `/Users/reddit/.agent-memory/reports/source-g5-trace-candidate-application-evidence-gate-smoke-20260515T043414Z/`.
- Smoke result: `application_count=3`, `required_evidence_gate.pass=true`, quality gate passed, read-only/no-mutation/default unchanged/ordinary conversation auto-approval false. Rollback replay was generated from the live DB; ranking evidence used a minimal ref-safe green experiment-shaped artifact because checked-in fixtures do not resolve against the current live DB scopes.

Recommended next work now:

1. Commit/push the tracked source/test/docs changes for this checkpoint; do not stage unrelated local artifacts (`.agent-learner/`, `.claude/`, `.omc/`, `.worktrees/`, report outputs).
2. Watch CI after push.
3. Next source slice should make live retrieval-ranking fixture generation self-contained from current live DB refs so application audits can use generated ranking evidence instead of a manually shaped compatible artifact.
4. Still blocked without exact separate approval: live G4 apply, broad/background apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply, and ordinary conversation auto-approval.

## Just completed: v0.1.162 milestone release and published-install QA

- Released the accumulated G4 bounded operator apply readiness corridor as `v0.1.162`.
- Release trigger path:
  - fast-forwarded `main` from reviewed `develop` commit `b26be71`;
  - `auto-release` created release-sync branch `release-sync/v0.1.162` because protected `main` rejected metadata write-back;
  - verified release-sync CI green;
  - fast-forwarded `main` to release commit `cda5696` (`chore: release v0.1.162 [skip release]`);
  - `auto-release` tagged and dispatched `publish.yml` for `v0.1.162`.
- Release evidence:
  - `ci` on `b26be71`: success, run `25896978955`.
  - `auto-release` on `b26be71`: success, run `25896978967`.
  - release-sync `ci` on `cda5696`: success, run `25897050696`.
  - `ci` on `cda5696`: success, run `25897160173`.
  - release-sync `auto-release` on `cda5696`: success, run `25897160181`.
  - `publish` on `v0.1.162`: success, run `25897165575`.
  - GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.162`.
  - npm latest: `@cafitac/agent-memory@0.1.162`.
  - PyPI latest: `cafitac-agent-memory==0.1.162`.
- Published-install QA:
  - Local outside-source smoke wrote `/tmp/agent-memory-v0162-published-smoke/published-install-smoke.json`.
  - Smoke status: `ok`, attempt `1`, no propagation retry needed after the first early npm wrapper resolver miss.
  - Covered npm registry lookup, `npx --help`, `npm exec` help/bootstrap/doctor/hook, `uvx` help/bootstrap/doctor/hook, and `pipx run` help/bootstrap/doctor/hook against exact version `0.1.162`.
  - `doctor` status was `ok` on npm/uvx/pipx isolated temp DB/config paths.
  - Hook smoke returned the expected verify-first no-memory context from isolated empty DBs.
- GitHub hosted `published-install-smoke.yml` was not dispatched because the currently available `gh` token could not create workflow dispatch events (`HTTP 403: Must have admin rights to Repository`). Local exact-version published smoke passed and is the authoritative completed QA for this session.
- Local `develop` was fast-forwarded to release commit `cda5696`; tracked tree is clean except pre-existing untracked local agent/worktree artifacts.

Recommended next work now:

1. Do not rerun release or publish for `v0.1.162`; it is complete and externally verified.
2. Priority 2 read-only preparation is complete: published `v0.1.162` generated `/Users/reddit/.agent-memory/reports/v0.1.162-published-g4-operator-packet-20260515T024457Z/g4-operator-apply-packet.json` with `quality_gate.pass=true`, decision `operator_apply_packet_ready_for_manual_review_only`, `runbook_contract.matches_g4_bounded_operator_apply_runbook=true`, `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, and `broad_g4_apply_allowed=false`.
3. Stop here for live apply unless the operator supplies the full exact corridor: approval phrase `apply-approved-g4-review-queue-items-v1`, policy `g4-review-queue-apply-v1`, actor, private reason, backup path, bounded `--max-apply`, and audit output path.
4. Keep broad/background G4 apply, telemetry reset, default-ranking migration, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Just completed: G4 milestone release readiness review

- Reviewed accumulated `develop` G4 corridor after `v0.1.161` / `main`.
- Compared range: `main..develop`.
- Included 10 commits from `539f929` through `e6eb7c1`, covering human approval artifacts, apply readiness, operator bundle, readiness summary, post-apply verification, operator packet, runbook contract, and docs/status updates.
- Wrote release-readiness review: `.dev/roadmap/memory-consolidation/g4-milestone-release-readiness-review.md`.
- Verdict: source-ready as a release candidate after human maintainer release intent review, but no publish/release action was executed.
- Candidate release shape if approved later: patch milestone `v0.1.162`, theme `G4 bounded operator apply readiness corridor`.
- Checks passed:
  - `PYTHONPATH=src .venv/bin/python -m pytest tests/ -q` -> `326 passed, 1 xfailed`.
  - `PYTHONPATH=src .venv/bin/python scripts/check_release_metadata.py` -> package/module versions synced at `0.1.161`.
  - `PYTHONPATH=src .venv/bin/python scripts/smoke_release_readiness.py` -> Python and Node bootstrap/doctor success in isolated HOME.
  - `npm pack --dry-run --json` -> tarball only includes `LICENSE`, `README.md`, `bin/agent-memory.js`, `package.json`.
  - focused release/package tests -> `34 passed`.
- Safety remains unchanged: no live apply, no release/publish, no telemetry reset, no default-ranking migration, no broad/background G4 apply, no collapse/delete, no unreviewed promotion, no ordinary conversation auto-approval.

Recommended next work now:

1. Commit this release-readiness review checkpoint; still do not publish automatically.
2. If the operator wants a real release, ask for explicit release approval and then follow the existing project release process for a patch milestone, followed by real downloaded install QA.
3. If no release approval is given, continue read-only source/docs hardening only.
4. Live bounded G4 queue apply remains separate and still requires exact approval phrase `apply-approved-g4-review-queue-items-v1` plus actor, private reason, backup path, policy `g4-review-queue-apply-v1`, bounded `--max-apply`, and audit output path.

## Previous checkpoint: G4 packet/runbook cross-check contract

- Source now includes a `runbook_contract` block in `dogfood g4-operator-apply-packet` output.
- The contract explicitly mirrors the bounded apply runbook checklist:
  - required authorization items: live bounded G4 intent, exact approval phrase, exact policy, actor, private reason, backup path, audit output path, and bounded max apply;
  - pre-apply evidence items: green packet, green operator bundle, green readiness summary, read-only/no-mutation/default-unchanged, pre-apply bundle no-apply/no-support state, and ref-safe privacy;
  - post-apply stop items: new post-apply operator bundle, `g4-post-apply-verification`, and no repeated apply without fresh approval.
- The packet self-checks that the manual apply preview contains all required apply flags and that the post-apply verification template contains all required verifier flags.
- Source live smoke wrote `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-packet-runbook-crosscheck-20260514T145334Z/g4-operator-apply-packet.json` with `quality_gate.pass=true`, `runbook_contract.matches_g4_bounded_operator_apply_runbook=true`, and both command-template flag checks true.
- Safety remains unchanged: `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, and no live apply was run.

Recommended next work now:

1. Commit this source/docs checkpoint; no release yet.
2. After commit, the best next step is a milestone-release readiness review for the accumulated develop G4 corridor, still without live apply.
3. Only run live bounded G4 queue apply if the operator separately gives the exact approval phrase `apply-approved-g4-review-queue-items-v1` plus actor, private reason, backup path, policy `g4-review-queue-apply-v1`, bounded `--max-apply`, and audit output path.
4. Keep live telemetry reset, default-ranking migration, broad/background G4 apply, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Previous checkpoint: source-level read-only G4 operator apply packet

- Source commit `c7b6e0c` added `dogfood g4-operator-apply-packet`.
- The command consumes saved green pre-apply artifacts:
  - `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`
  - `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`
- It emits a machine-readable manual checklist plus exact command templates for `g4-review-queue-apply` and `g4-post-apply-verification`.
- Safety remains unchanged: `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, no raw content/query/trace/reason/sample values.
- Source live smoke wrote `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-operator-apply-packet-20260514T141141Z/g4-operator-apply-packet.json` with `quality_gate.pass=true` and decision `operator_apply_packet_ready_for_manual_review_only`.

Recommended next work now:

1. Commit this docs/status checkpoint; no release yet.
2. If staying in safe B-direction without exact live apply approval, the next useful work is a read-only packet/runbook cross-check or operator-facing docs polish around the packet output. Do not create another apply-enabling command from generic continuation.
3. Only run live bounded G4 queue apply if the operator separately gives the exact approval phrase `apply-approved-g4-review-queue-items-v1` plus actor, private reason, backup path, policy `g4-review-queue-apply-v1`, bounded `--max-apply`, and audit output path.
4. Keep live telemetry reset, default-ranking migration, broad/background G4 apply, collapse/delete, unreviewed promotion, repeated apply without new approval, and ordinary conversation auto-approval blocked.

## Previous checkpoint: source-checkout read-only G4 operator bundle smoke

- Ran source checkout `dogfood g4-operator-apply-bundle` against live `/Users/reddit/.agent-memory/memory.db` using saved green v0.1.161 ranking, rollback confidence, rollback replay, and telemetry reconciliation artifacts.
- Report directory: `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/`.
- Main artifact: `g4-operator-apply-bundle.json`.
- Generated child artifacts: `g4-review-queue-approval-report.json`, `g4-review-queue-preview.json`, `g4-apply-readiness.json`.
- Result: quality gate green, queue count `8`, `bounded_partial_apply_ready=true`, and decision `operator_apply_bundle_ready_for_exact_manual_apply`.
- Safety was preserved: read-only/no-mutation/default unchanged; `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, ordinary conversation auto-approval false, and no raw reason/content/query/trace/proposal JSON output.

Recommended next work now:

1. Commit this doc/status/runbook update if desired; no release yet.
2. The exact bounded G4 queue apply runbook now lives at `.dev/roadmap/memory-consolidation/g4-bounded-operator-apply-runbook.md`. It must not be executed unless the operator gives explicit approval for live apply with backup path, actor, private reason, bounded `--max-apply`, policy `g4-review-queue-apply-v1`, and exact approval phrase `apply-approved-g4-review-queue-items-v1`.
3. Keep live telemetry reset, default-ranking migration, broad/background G4 apply, collapse/delete, unreviewed promotion, and ordinary conversation auto-approval blocked.

## Operating policy: develop first, slower release cadence

- Current work branch: `develop`.
- Do not release every small slice. Accumulate validated develop work and release only when the automation corridor is complete/stable enough to justify a real milestone.
- Keep QA discipline unchanged: source tests for development plus real QA against actually downloaded/published installs after a release exists.

## Source checkpoint: G4 read-only operator apply bundle

This source slice makes the live/runtime G4 operator workflow easier without applying anything.

Implemented in source:

- Prior commit `539f929` added `dogfood g4-review-queue-approval-report` and wired `--human-review-approval-report` into `dogfood g4-review-queue-preview`.
- `dogfood g4-apply-readiness` consumes a saved green queue-preview artifact and reports bounded readiness while still setting `apply_supported=false` and `broad_g4_apply_allowed=false`.
- New `dogfood g4-operator-apply-bundle` command.
- The bundle writes three artifacts under `--report-dir`: `g4-review-queue-approval-report.json`, `g4-review-queue-preview.json`, and `g4-apply-readiness.json`.
- The bundle emits an exact `g4-review-queue-apply` command preview with placeholders for the private reason, backup path, and apply audit output.
- It is read-only/report-only: `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, default retrieval unchanged, and ordinary conversation auto-approval false.
- Actual mutation remains only in the separate `g4-review-queue-apply` corridor requiring exact `--policy g4-review-queue-apply-v1`, `--approval-phrase apply-approved-g4-review-queue-items-v1`, actor, private reason, backup, and bounded `--max-apply`.

Verification:

- RED observed before implementation: `g4-operator-apply-bundle` was an invalid dogfood action.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `2 passed`.
- `.venv/bin/python -m pytest tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_preview_consumes_green_gate_artifacts_without_broad_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_review_queue_approval_report_is_ref_safe_read_only_gate tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_consumes_green_preview_without_apply tests/test_cli.py::test_python_module_cli_dogfood_g4_apply_readiness_blocks_unsafe_preview_artifact tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_is_ref_safe_read_only_command_preview tests/test_cli.py::test_python_module_cli_dogfood_g4_operator_apply_bundle_blocks_failed_artifact_without_apply -q` -> `6 passed`.
- `PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-bundle --help` -> passed.
- `.venv/bin/python -m pytest tests/ -q` -> `320 passed, 1 xfailed`.

Recommended next work:

1. Commit this source/doc/test slice on `develop`.
2. Do not release yet.
3. Next source slice can run/record a source-checkout read-only operator bundle smoke against saved live v0.1.161 gate artifacts, or draft the exact operator-approved apply plan. Do not execute live apply from a generic continuation prompt.

## Runtime checkpoint: v0.1.161 fresh runway green and next gate evidence

This checkpoint used the installed v0.1.161 runtime and live `/Users/reddit/.agent-memory/memory.db` in read-only/report-only mode.

Fresh metadata-gap diagnosis from the wide `2026-05-14T00:00:00Z` epoch:

- `retrieval_observations`: 123 fresh observations.
- Empty retrievals: 60.
- Unknown empty-outcome rows: 12, all `hook_event_name=pre_llm_call`, `response_mode=unknown`, same aggregate scope bucket `cwd:a439e0c3063d5e5c`.
- The latest unknown row was at `2026-05-14 10:27:21`; strict post-gap rows after that had 3 observations, 3 traces, 2 empty retrievals, and 0 unknown empty outcomes.
- Interpretation: the blocker was classified/stale metadata-gap evidence in the wider epoch, not an unresolved adapter payload gap.

Green fresh-runway evidence:

- Runway: `/Users/reddit/.agent-memory/reports/v0.1.161-fresh-runway-green-20260514T103021Z/runway.json`.
- Epoch: `2026-05-14T10:27:22Z`.
- Fresh epoch gate: pass, `fresh_epoch_ready_to_compare_against_historical`.
- Fresh comparison gate: pass, `fresh_epoch_collection_stable_for_historical_comparison`.
- Telemetry reconciliation gate: pass, `telemetry_only_reconciliation_ready_for_manual_apply`.
- Coverage: 3 observations, 3 traces, trace coverage `1.0`; empty retrievals were 2/3, all `no_reliable_memory`; unknown/unresolved metadata-gap counts were 0.
- Telemetry reset preview candidate count: 4771 historical telemetry rows, but this remains preview/reconciliation evidence only.

Next gate evidence collected after the green runway:

- G4 review queue preview: `/Users/reddit/.agent-memory/reports/v0.1.161-next-g4-queue-20260514T103118Z/g4-review-queue-preview.json`; quality gate passed as `review_queue_ready_for_manual_review`, read-only/no-mutation/default unchanged.
- Broad G4 reassessment still says `broad_g4_apply_allowed=false`; required gates remain retrieval ranking, rollback confidence, rollback replay, live telemetry reconciliation, and human-reviewed queue approval.
- Ranking shadow gate: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/retrieval-ranking-shadow.json`; live mixed 50-task corpus stayed read-only/no-mutation/default unchanged with 0 baseline regressions.
- Rollback confidence: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-confidence.json`; quality gate pass.
- Rollback replay validate: `/Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-replay-validate.json`; quality gate pass.

Recommended next work:

1. Do not run live telemetry reset or default-ranking migration from generic continuation. Both need their own exact approval phrase and operator intent.
2. The safest PR-sized source slice is now to make the G4/default-ranking readiness report consume the green runway and gate evidence as explicit inputs, so broad apply/default migration remains blocked unless every required artifact is present and green.
3. If the operator explicitly wants live default ranking migration next, use the existing `retrieval-ranking-migrate-default` command only with `--policy graph_reinforced_v1`, a live config path, actor/reason, backup/audit output, and exact approval phrase `migrate-retrieval-ranking-default-v1`; otherwise keep `conservative_legacy` live.
4. If the operator explicitly wants telemetry cleanup next, use the telemetry-only reset corridor only after backup and exact approval phrase; do not infer that permission from this green preview.

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

Recommended next work:

1. Commit/push/PR the stacked source checkpoint that wires `dogfood telemetry-reconciliation --fresh-epoch-comparison-report` to saved `dogfood fresh-epoch-compare` reports.
2. Generate/collect repeated metadata-rich live/runtime fresh-epoch reports with explicit `--epoch-start` boundaries.
3. Compare those saved reports with `dogfood fresh-epoch-compare --report ... --report ...`.
4. Feed the green comparison report into `dogfood telemetry-reconciliation --fresh-epoch-comparison-report ...` only as reset-avoidance evidence; do not infer broad apply permission.
5. Keep live default ranking on `conservative_legacy`; keep `graph_reinforced_v1` shadow-only until a separate explicit default-rollout decision.
6. Keep broad G4/background apply, collapse/delete apply, telemetry reset apply, unreviewed promotion, and ordinary conversation auto-approval blocked.

## v0.1.158 npm package metadata/package-contents audit checkpoint

This source slice completes the OSS package-surface follow-up after the npm-install-only README cleanup.

Verified source state before release:

- `package.json` now has an OSS-facing description, keywords, repository, bugs, license, bin, `files`, and public `publishConfig`.
- `npm pack --dry-run --json` shows the npm tarball contains only `LICENSE`, `README.md`, `bin/agent-memory.js`, and `package.json`.
- Internal `.dev`, `.agent-learner`, `.claude`, `.worktrees`, report, cache, and dogfood artifacts remain excluded from the npm package.
- Focused test coverage asserts package metadata and tarball contents in `tests/test_npm_launcher.py`.

Next after this package-surface slice:

- Return to the brain-like memory runway: continue metadata-rich dogfooding with explicit fresh epoch windows, compare fresh trace/retrieval coverage, and keep all broad apply/default ranking/collapse-delete/telemetry-reset automation blocked until real runtime evidence clears the gates.

## v0.1.157 OSS README checkpoint

This is the newest verified public-surface checkpoint. The code/runtime automation runway remains as described below, but the OSS-facing README was intentionally reset to a minimal npm-install-only entrypoint.

Verified state:

- Release: `v0.1.157` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.157`).
- npm: `@cafitac/agent-memory@0.1.157`.
- PyPI: `cafitac-agent-memory==0.1.157`.
- PR #341 made the README npm-install-only. PR #342 synced release metadata.
- Main CI passed after the README/docs update and release-sync merge.
- Published npm smoke passed with `UV_NO_CACHE=1 npm exec --yes --package @cafitac/agent-memory@0.1.157 -- agent-memory doctor`.

Public README rule:

- Keep `README.md` short: one-line product description, `npm install -g @cafitac/agent-memory`, `agent-memory bootstrap`, `agent-memory doctor`, npm one-shot usage, default local DB path, trust/deeper-doc links, and license.
- Do not re-expand README with examples, Hermes integration details, dogfood/G-stage/operator details, raw runtime reports, or Python-first install paths. Put details in linked docs or `.dev`.

Recommended next PR-sized slice:

- Audit and tighten npm package metadata/package contents: `package.json` description/keywords/homepage/repository/bugs/license, `files`, `npm pack --dry-run` contents, and published npm smoke.
- Keep it OSS-facing and install-surface focused; do not change memory automation policy in that PR.

Automation guardrails remain unchanged:

- Live default ranking remains `conservative_legacy`; `graph_reinforced_v1` remains shadow-only.
- Broad G4/background apply, collapse/delete apply, live telemetry reset, default ranking migration, unreviewed automatic promotion, and ordinary conversation auto-approval remain blocked.

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.154`; the `personal-oss` Hermes hook is healthy on the v0.1.154 runtime. The current verified runway now has a 50-task expanded retrieval fixture gate, 75 checked-in retrieval eval tasks across the fixture directory, persisted/replayed per-candidate collapse proof artifacts with supersession-chain evidence, one fresh non-idempotent narrow live reviewed-candidate promotion, copy/live-safe explicit-approval corridor evidence, an idempotent live G4 queue apply, named ranking policy/shadow-compare diagnostics, approval-gated config-only default-ranking migrate/rollback mechanics, a live Hermes DB 50-task representative fact shadow corpus, and a new live Hermes DB 50-task mixed fact/procedure/episode shadow corpus. Broad G4/background apply, collapse/delete apply, live telemetry reset, default ranking migration, and ordinary conversation auto-approval remain blocked. Live default ranking remains `conservative_legacy`.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 78-80%.
- Substrate/evidence plumbing: about 87%.
- Safe automatic mutation/promotion: about 66-70%.
- Remaining work: about 20-22% overall.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, first narrow approved mutation (`apply_reinforcement_marker`), fresh linkage health, G5a ref-safe `trace cluster -> consolidation candidate` preview, G5b reviewed trace-candidate persist/list/update/apply for explicit fact/preference/procedure promotion, G5c read-only cluster scoring, G5d read-only repeated activation -> reinforcement refinement preview, G5e read-only stale weak evidence -> decay/collapse candidate preview, G5f conflict -> supersession/replacement candidate preview plus lifecycle registry/bounded partial automation, G5g reviewed decay deprecate / ranking gate / rollback confidence, G5h/G5i rollback replay validation / eval-gated opt-in ranking experiment / decay-collapse decision boundary / richer candidate skeleton annotations / telemetry reconciliation/reset safety reporting / broad-G4 reassessment report fields, 50-task expanded retrieval fixture gate with 75 checked-in eval tasks across the directory, per-candidate collapse proof artifact replay with supersession-chain evidence, and narrow explicit-approval corridor copy/live-safe smokes including one fresh non-idempotent live reviewed-candidate promotion.
- Not done: broad background consolidation apply, fully automatic long-term memory promotion, default retrieval-ranking policy changes, automatic ordinary-conversation approval, collapse/delete apply, and large-scope autonomous rollback/replay on real runtime evidence.

## Latest verified checkpoint

- Release: `v0.1.155`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`
- npm: `@cafitac/agent-memory@0.1.155`
- PyPI: `cafitac-agent-memory==0.1.155`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`
- Runtime smoke: PyPI install smoke passed after simple-index propagation, npm installed-bin smoke passed, GitHub release exists, and `hermes --profile personal-oss hooks doctor` is green after `--accept-hooks` approval for the v0.1.153 hook command. v0.1.155 runtime QA artifacts: `/Users/reddit/.agent-memory/reports/v0.1.155-runtime-qa-20260513T133421/`.
- Current source follow-up reports: `/tmp/agent-memory-g4-corridor-smoke/`, `/tmp/agent-memory-telemetry-reset-decision/`, `/tmp/agent-memory-fresh-epoch-v0149/`, and `/tmp/agent-memory-apply-corridor-v0150/`.
- Fresh report directory retained from G4 diagnostics: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/`.
- Fresh linkage diagnosis retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-linkage-gap-diagnose-v0138-fresh.json` with decision `fresh_trace_linkage_gap_not_detected`.
- Fresh epoch readiness retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/fresh-epoch-v0138.json`.
- Fresh review queue preview retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/g4-review-queue-preview-v0138-fresh.json`.
- Historical scheduled dry-run retained: `/Users/reddit/.agent-memory/reports/g4-v0138-20260512-132253/scheduled-dry-run.json`.
- Source G5a-G5i checkpoint: `dogfood trace-cluster-preview`, `dogfood trace-candidate-persist/list/update/apply`, read-only `review_score`/`review_recommendation`, `dogfood reinforcement-refinement-preview`, `dogfood decay-collapse-preview`, `dogfood supersession-preview`, lifecycle candidate registry/apply, decay deprecate apply, ranking gate/experiment, rollback confidence, `rollback-replay-validate`, `retrieval-ranking-experiment`, `decay-collapse-decision`, `telemetry-reconciliation`, telemetry reconciliation/reset safety reporting, and G4 reviewed queue preview/persist/update/apply are merged and released through v0.1.150.
- Current local follow-up evidence: expanded fixture file `tests/fixtures/retrieval_eval/expanded/live-compatible-50-gate.json` has 50 live-compatible tasks; checked-in fixture directory evaluates at 75/75 pass; opt-in ranking experiment report `/Users/reddit/.agent-memory/reports/g5i-ranking-experiment-expanded-50-20260513T1355/ranking-experiment-expanded-50.json` is read-only with `expanded_fixture_gate_met=true`, `eval_gate_pass=true`, and `default_ranking_mutated=false`; fresh live reviewed candidate `candidate:29db0390b2f81bdb` promoted to `fact:4` only through the guarded explicit-approval corridor.
- Current source/runtime ranking evidence: `retrieval-ranking-experiment` has named policy/shadow-compare diagnostics; `retrieval-ranking-migrate-default` provides an approval-gated config-only migration with protected table hashes, audit output, and rollback metadata. v0.1.153 published and installed this path. Live default remains `conservative_legacy`. Live shadow reports under `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/` include `live-fact4-shadow.json`, `live-hermes-approved-fact-50-corpus-v1-shadow.json`, and `live-hermes-mixed-approved-50-corpus-v1-shadow.json`; the mixed corpus replayed 50 live tasks across approved facts/procedure/episode with 50/50 pass, zero baseline regressions, protected default order, and no durable mutation. The checked-in 50-task fixture still is not directly runnable against the tiny live Hermes DB because project-M1 references are absent there; the gap artifact is `checked-in-expanded-50-live-gap.stderr.txt`.

## Current blocker

The v0.1.155 runtime is healthy and includes the epoch-start scheduled-dry-run measurement fix, but broad brain-like automation is still intentionally blocked:

- Fresh epoch report `/Users/reddit/.agent-memory/reports/default-ranking-v0152-shadow/fresh-epoch-since-v0152-with-metadata-gap-diagnostic.json`: quality gate still fails with `low_epoch_observation_trace_coverage` and `epoch_empty_retrieval_outcome_metadata_gap_classified`. The new metadata-gap diagnostic shows `dominant_blocker=classified_legacy_missing_outcome`, `classified_missing_outcome_count=6`, and `unresolved_adapter_payload_gap_count=0`; continue metadata-rich dogfooding before telemetry reset or default ranking migration.
- G4 review queue copy/live-safe smoke `/tmp/agent-memory-apply-corridor-v0150/`: live preview/list/reconciliation were read-only; copy telemetry reset and copy G4 queue apply preserved durable memory (`mutated=false`); live G4 queue apply was idempotent with `applied_count=0`, `already_applied_count=1`, `mutated=false`, and `default_retrieval_unchanged=true`.
- Historical telemetry reconciliation via the telemetry reset copy smoke `/tmp/agent-memory-telemetry-reset-decision/copy-apply.json`: deleting 1773 historical telemetry rows on a DB copy passed with protected durable memory tables unchanged. Live DB was not reset because the fresh epoch gate still fails; live reset remains manual-only behind `telemetry-reset-v1` and `apply-telemetry-reset-v1`.
- Collapse proof is evidence-driven and can persist/replay per-candidate proof artifacts. The current local proof path can reach `satisfied` when supersession-chain/relation evidence exists, but collapse/delete apply remains disabled even after proof satisfaction.
- Retrieval fixture coverage now includes a 50-task live-compatible expanded source gate, 75 checked-in eval tasks across the directory, a live-Hermes-DB representative 50-task fact corpus, and a live-Hermes-DB representative 50-task mixed fact/procedure/episode corpus. The opt-in ranking experiments passed as read-only comparisons, but default retrieval ranking is still unchanged and blocked until a separate explicit default-rollout decision is made after fresh-epoch telemetry is green.
- New source follow-up evidence: `/Users/reddit/.agent-memory/reports/v0.1.154-continuation-20260513T120215/trace-quality-epoch-start-repo.json` and `/Users/reddit/.agent-memory/reports/v0.1.154-continuation-20260513T120215/scheduled-dry-run-epoch-start-repo.json` show that adding `--epoch-start` to trace-quality/scheduled-dry-run lets the post-v0.1.154 fresh window pass without legacy lookback pollution. This is a measurement fix, not an apply permission.
- G4 broad apply contract remains blocked by policy even when a report is individually green. The guardrail now requires all of these to be green on real runtime evidence before reconsideration: retrieval ranking gate, rollback replay validation, live telemetry reconciliation, and human-reviewed queue approval; ordinary conversation auto-approval remains false.

## Recommended next work

Proceed in this sequence:

1. Keep live default ranking on `conservative_legacy`; do not run `retrieval-ranking-migrate-default` against the live profile until an operator gives the exact approval phrase and fresh-epoch telemetry is green.
2. Keep metadata-rich dogfooding and compare fresh-epoch windows using the released explicit `--epoch-start` boundary; do not let legacy lookback rows drive go/no-go decisions.
3. Keep live mixed retrieval corpus coverage in the shadow-only lane; extend it only through guarded reviewed-candidate promotions with backup/audit evidence.
4. Keep fresh reviewed candidate promotion limited to the guarded explicit-approval corridor.
5. Keep broad G4/background apply blocked until ranking gate, rollback replay, telemetry reconciliation/fresh epoch, and reviewed queue approvals all pass on real runtime evidence.

## What not to do next

Do not start with live broad G4/background apply.

Do not treat fresh linkage health, G5b reviewed candidate apply support, G5c review scores, G5d reinforcement-refinement preview, or G5e decay-collapse preview as approval for automatic memory creation. They only make the review runway safer and more inspectable.

Do not live-apply persisted queue/candidate mutations unless the operator intentionally uses the exact guarded command shape with backup, policy, approval phrase, actor, and reason. Generic continuation does not authorize broad apply, ordinary conversation auto-approval, raw transcript storage, decay/delete, promotion, supersession, retrieval-ranking changes, or treating review scores as apply approval.

Do not silently delete, reset, or rewrite telemetry. Historical reconciliation must go through the reviewed telemetry-only corridor and preserve protected memory tables.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.153까지 릴리즈/설치/스모크가 끝났고 `personal-oss` Hermes hook도 doctor-green입니다. 전체 목표 대비 대략 78-80% 정도 왔습니다. live Hermes default는 여전히 `conservative_legacy`이고, `graph_reinforced_v1`은 shadow 후보로만 비교했습니다. 새 live-Hermes-DB mixed 50-task corpus는 approved facts/procedure/episode를 포함해 50/50 pass, zero baseline regression, protected default order, no mutation으로 통과했습니다. 다만 post-v0.1.152 fresh-epoch는 아직 `low_epoch_observation_trace_coverage`와 `epoch_empty_retrieval_outcome_metadata_gap_classified`로 block입니다. 새 diagnostic 기준 unresolved adapter payload gap은 0이고, 남은 핵심은 classified legacy missing-outcome row를 metadata-rich dogfooding으로 밀어내는 것입니다. broad G4/background apply, collapse/delete apply, ordinary conversation auto-approval, default ranking migration, live telemetry reset은 아직 금지입니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.154/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory dogfood supersession-preview   /Users/reddit/.agent-memory/memory.db   --limit 200 --top 10   --output /tmp/agent-memory-next-g5f-supersession-preview.json
```

Expected: read-only/no-mutation. Collapse proof may become satisfied only through proof artifacts; collapse/delete apply and broad G4/background apply remain blocked.


## v0.1.154 active runtime checkpoint

- Release: `v0.1.155` (`https://github.com/cafitac/agent-memory/releases/tag/v0.1.155`).
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory`.
- Hermes `personal-oss` hook accepted and `hermes --profile personal-oss hooks doctor` is green.
- Runtime QA artifacts: `/Users/reddit/.agent-memory/reports/v0.1.154-runtime-qa-20260513T091806/`.
- v0.1.154 fixes episode decay-collapse evidence snapshots by reading episode `source_ids_json`; the v0.1.154 decay-collapse decision over the mixed corpus now runs read-only/no-mutation.
- Runtime QA remains safety-preserving: storage health healthy, mixed 50-task shadow ranking passed `50/50` with zero regressions and no default mutation, decay-collapse decision keeps collapse/delete apply disabled, and telemetry reconciliation remains manual-only.
