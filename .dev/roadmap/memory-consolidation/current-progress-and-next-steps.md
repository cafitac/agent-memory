# Memory Consolidation Current Progress and Next Steps

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-14 12:45 KST

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
