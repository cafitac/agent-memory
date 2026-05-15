# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-15 18:29 KST


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
