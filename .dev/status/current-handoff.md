# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-08 12:55 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory is currently verified through `v0.1.110`: the first narrow G4a cleanup mutation has named-policy, rollback-manifest/private-artifact, disposable cleanup preflight, restore dry-run, source DB binding, artifact-integrity checks, a blocked restore apply contract checkpoint, disposable restore rehearsal, aggregate-only restore audit preview, a blocked audit write dry-run, and a blocked audit-write apply contract. GitHub Release, npm, and PyPI all report `v0.1.110`. The live Hermes `default`/`personal-oss` plus `earlypay` hook runtimes were upgraded to `/Users/reddit/.agent-memory/runtime/v0.1.110/.venv/bin/agent-memory`; installed-runtime QA passed with report `/Users/reddit/.agent-memory/reports/v0.1.110-runtime-qa-20260508T034840`.

Storage/privacy cleanup remains clean: legacy `retrieval_observations.query_preview` rows are expected to stay at 0, restore artifacts remain private/local because they contain raw query previews, and broad G4 consolidation apply mode remains blocked. The current branch adds only a restore audit-write preflight gate inside the already-blocked audit write apply contract; it still does not write audit rows or mutate the live DB.

Historical G4 contract checkpoint remains docs/RED-test-only: PR #200, PR #202, PR #204, v0.1.99 runtime `/Users/reddit/.agent-memory/runtime/v0.1.99/.venv/bin/agent-memory`, and report `/Users/reddit/.agent-memory/reports/v0.1.99-runtime-qa-20260507T074118` are retained as the broad-G4-blocked baseline.

## Current next slice

Current slice: start from `v0.1.110` validated `main` on branch `g4/query-preview-cleanup-restore-audit-write-preflight-gate`. Add a restore audit-write preflight gate under `dogfood query-preview-cleanup-restore --apply -> restore_apply_contract.audit_preview.write_dry_run.apply_contract` so any future `experience_traces` audit write must pass source/integrity/rehearsal/hash/duplicate/privacy checks while still returning `write_allowed=false`.

Why this is the best next move: v0.1.110 makes the audit-write apply contract explicit but still write-blocked. The remaining gap before any audit write or live restore is proving a deterministic preflight gate: exact policy, actor/reason hash continuity, source DB match, artifact integrity, disposable rehearsal, content/metadata hash match, duplicate audit event absence, and raw query/reason/sample exclusion. Broad consolidation apply mode remains blocked.

Recommended local backup commands:

```bash
agent-memory backup export /Users/reddit/.agent-memory/memory.db   /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup inspect /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup restore /Users/reddit/.agent-memory/backups/memory.agent-memory-backup.zip   /Users/reddit/.agent-memory/restored-memory.db
```

The backup manifest is metadata-only, but the bundled SQLite database contains local memory state and should be treated as private local data.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should normally be on `main` unless a docs/feature branch is active.
- Current feature branch for this slice: `g4/query-preview-cleanup-restore-audit-write-preflight-gate`.
- Latest merged G4a hardening PR: #229 `feat: add restore audit write apply contract`.
- Latest merged release-sync PR: #230 `chore: release v0.1.110 [skip release]`.
- Latest completed release: `v0.1.110`.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for `gh` commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.110`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.110`
- npm package: `@cafitac/agent-memory@0.1.110`
- PyPI package: `cafitac-agent-memory==0.1.110`

Latest verified source checkout snapshot, checked 2026-05-08 12:55 KST:

- branch before this slice: `main`, synced with `origin/main`
- open PRs: none observed before this branch
- GitHub Release, npm, and PyPI all report `v0.1.110`
- fresh artifact smoke passed from PyPI and npm; `agent_memory.__version__ == "0.1.110"`
- live Hermes `default`, `personal-oss`, and `earlypay` configs use the pinned v0.1.110 runtime
- checked-in retrieval-eval fixtures remain at 21 tasks
- installed runtime dogfood storage-health, scheduled dry-run, query-preview cleanup preview, restore dry-run, restore apply contract+rehearsal+audit write apply contract smoke, backup inspect, and hook smoke passed; broad G4 remains blocked

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
