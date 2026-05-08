# G4 Readiness and First Mutation Plan

Status: Superseded as a first-mutation plan; retained as historical guardrails for broader G4 planning.
Last updated: 2026-05-07 21:35 KST

## Purpose

This document turns the post-v0.1.76 decision into an ordered execution plan:

1. continue scheduled report collection;
2. compare report trends;
3. write the G4 apply-mode plan before implementation;
4. implement only the first narrow mutation slice after the plan is accepted.

The plan exists to prevent a direct jump from read-only dogfood reports to broad automatic memory approval.

## Current verified starting point

Current release/runtime:

- Latest release: `v0.1.102`.
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.102/.venv/bin/agent-memory`.
- Live DB: `/Users/reddit/.agent-memory/memory.db`.
- Repo branch at plan start: `main`, then docs branch `docs/g4-readiness-apply-plan`.

Raw-content-safe live checks at plan start:

- `retrieval_observations`: 809, latest `2026-05-05 12:03:21` UTC.
- `memory_activations`: 714, latest `2026-05-05 12:03:21` UTC.
- `experience_traces`: 120, latest `2026-05-05 10:32:18` UTC.
- `facts`: 3.
- `procedures`: 0.
- `episodes`: 0.
- Legacy non-empty `retrieval_observations.query_preview`: 70, latest `2026-05-01 12:57:54` UTC.

Report artifacts created at plan start:

- `/tmp/agent-memory-g4-readiness/scheduled-dry-run-20260505T120412Z-a.json`.
- `/tmp/agent-memory-g4-readiness/scheduled-dry-run-20260505T120412Z-b.json`.
- `/tmp/agent-memory-g4-readiness/scheduled-compare-20260505T120412Z.json`.
- `/Users/reddit/.agent-memory/reports/g4-readiness/scheduled-dry-run-20260505T120519Z.json`.

Safe aggregate interpretation:

- `dogfood scheduled-dry-run`: `read_only=true`, `mutated=false`, privacy flags false, decision `continue_scheduled_dry_run_dogfooding_before_g4`, pass `false`.
- `dogfood scheduled-compare`: `read_only=true`, `mutated=false`, compared 2 reports, privacy flags false, decision `continue_scheduled_report_collection_before_g4`, pass `false`.
- Current blocked reasons include `scheduled_quality_gate_not_stable`, `blocked_reasons_present`, `decay_risk_above_threshold`, and `background_quality_warnings_present`.

A local Hermes cron job was scheduled to collect 4 more read-only artifacts every 6 hours:

- Job id: `6894df1bfd4c`.
- Name: `agent-memory G3f scheduled report collection`.
- Output directory: `/Users/reddit/.agent-memory/reports/g4-readiness`.
- The job must not mutate the DB or repo and must report only safe aggregate fields.

## Ordered execution plan

### Step 1: collect scheduled reports

Goal:

Collect enough repeated `dogfood scheduled-dry-run` artifacts to make the G4 decision data-backed rather than anecdotal.

Scope:

- Use the installed v0.1.76 runtime, not the source checkout.
- Save artifacts under `/Users/reddit/.agent-memory/reports/g4-readiness/`.
- Keep artifacts local-only; do not commit them.
- Do not print raw report bodies in PRs, docs, or chat.

Command shape:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory \
  dogfood scheduled-dry-run /Users/reddit/.agent-memory/memory.db \
  --since-hours 24 \
  --output /Users/reddit/.agent-memory/reports/g4-readiness/scheduled-dry-run-YYYYMMDDTHHMMSSZ.json
```

Acceptance:

- At least 3 saved artifacts from different timestamps, preferably 5 or more.
- Every artifact has `kind=dogfood_scheduled_dry_run`, `read_only=true`, `mutated=false`, and raw-content privacy flags false.
- Any failed run is recorded as an operator signal, not retried by loosening privacy or mutation guardrails.

### Step 2: compare trends

Goal:

Use `dogfood scheduled-compare` to determine whether the quality signals are stable enough to write a G4 apply-mode implementation plan.

Command shape:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory \
  dogfood scheduled-compare \
  --report /Users/reddit/.agent-memory/reports/g4-readiness/scheduled-dry-run-1.json \
  --report /Users/reddit/.agent-memory/reports/g4-readiness/scheduled-dry-run-2.json \
  --report /Users/reddit/.agent-memory/reports/g4-readiness/scheduled-dry-run-3.json \
  --output /Users/reddit/.agent-memory/reports/g4-readiness/scheduled-compare-YYYYMMDDTHHMMSSZ.json
```

Acceptance:

- Comparison output has `kind=dogfood_scheduled_dry_run_comparison`, `read_only=true`, `mutated=false`, and raw-content privacy flags false.
- The comparison uses counts, ratios, timestamps, hashes, booleans, warning names, and decision names only.
- If warnings remain stable and explainable but still fail the gate, the next plan may target the narrowest warning first rather than G4 apply mode.
- If warnings improve enough to justify planning, proceed only to Step 3, not implementation.

### Step 3: G4 apply-mode plan PR

Goal:

Write the implementation contract for apply mode before any new mutating command exists.

Scope:

- Docs and tests plan only, unless the user explicitly asks to proceed to implementation after review.
- Define exact eligible action classes.
- Define exact blocked action classes.
- Define CLI contract and JSON output contract.
- Define rollback/audit/read-only preview behavior.

Minimum apply-mode contract:

- Dry-run remains the default.
- `--apply` is required for mutation.
- `--actor` is required.
- `--reason` is required.
- A named policy is required.
- Output must include `read_only=false` only when mutation really happened.
- Output must include `mutated=true` only when mutation really happened.
- Output must include operation ids or affected refs without raw content.
- Every mutation must have an audit/history row or an equivalent reviewable record, plus rollback/restore metadata when the mutation deletes or clears private local state.

Hard blocks:

- No ordinary conversation auto-approval.
- No raw transcript, raw prompt, raw query, query preview, or raw user message persistence.
- No default retrieval ranking change.
- No broad LLM extraction from ordinary turns.
- No apply mode that bypasses conflict/supersession preflight.
- No silent cleanup of live DB fields without explicit `--apply --actor --reason`.

Acceptance:

- The plan names the first implementation PR and its RED tests.
- The plan includes rollback or restore instructions for the first mutating slice.
- The plan states exactly which surfaces remain forbidden after the first mutation lands.

### Step 4: first narrow mutation slice

Recommended first mutation:

`dogfood query-preview-cleanup --apply --policy legacy-query-preview-cleanup-v1 --actor <actor> --reason <reason>` for legacy non-empty `retrieval_observations.query_preview` rows only.

Why this is the safest first mutation:

- It targets legacy privacy debt rather than creating new long-term memory.
- A read-only preview already exists.
- The live affected set is known as an aggregate: 70 rows, latest `2026-05-01 12:57:54` UTC.
- New v0.1.69+ privacy-safe rows already have empty `query_preview`.
- The expected mutation is to clear a deprecated unsafe field, not change retrieval, scoring, approval, or graph behavior.

Required RED tests before implementation:

1. Apply cannot run without `--apply`.
2. Apply cannot run without `--actor`.
3. Apply cannot run without `--reason`.
4. Apply clears only eligible legacy non-empty `query_preview` rows older than the cutoff.
5. Apply does not print raw query preview values.
6. Apply reports affected counts, timestamps, and hashed affected ids only.
7. Apply writes an audit marker or operation summary without raw content.
8. Apply emits a rollback manifest with private artifact path, artifact hash, row count, and hash-only affected ids.
9. The rollback artifact is local/private and may contain the exact pre-clear values needed for restore; stdout/audit remain raw-value-free.
10. Dry-run and apply output shapes are distinguishable.
11. New privacy-safe rows remain untouched.
12. Default retrieval/Hermes hook behavior remains unchanged.
13. Apply runs first against a disposable DB copy and proceeds only if count/hash/rollback checks pass.
14. A restore dry-run command validates rollback artifacts without mutating the DB or printing raw query previews; live restore remains blocked until a separate explicit policy slice.
15. Rollback artifacts are source-bound with a hashed DB fingerprint; restore dry-run fails closed on source/target DB mismatch.
16. Restore dry-run fails closed on artifact integrity problems such as wrong policy, invalid operation, declared row-count mismatch, duplicate row ids, or missing source fingerprint; the failure output remains aggregate/hash-only and read-only.
17. Restore apply remains unavailable, but `query-preview-cleanup-restore --apply` has a read-only contract checkpoint that requires a separate restore policy, actor, reason hash, source DB match, artifact integrity, disposable-restore rehearsal, and audit raw-query exclusion before any live restore implementation can be considered.
18. Restore audit remains unavailable as a DB write, but the apply contract exposes an aggregate audit preview shape limited to policy, actor, reason hash, artifact hash, source fingerprint, source/integrity booleans, rehearsal status, restored ids hash, and restored count. The write dry-run previews the future `experience_traces` audit row metadata/hash shape but must report `would_insert=false`.
19. Future restore audit writes remain unavailable, but the write dry-run now includes an audit-write apply contract: a separate required policy `legacy-query-preview-cleanup-restore-audit-write-v1`, actor/reason hash continuity, insert-preview field shape, source/integrity/rehearsal prerequisites, hash-only metadata, and raw query/reason/sample exclusion.

Required operator safety before live DB apply:

- Run read-only preview against the live DB.
- Export or back up the DB before mutation.
- Run apply only with explicit policy/actor/reason and disposable-copy preflight.
- Re-run storage-health and query-preview cleanup preview after mutation.
- Run restore dry-run against the private rollback artifact before considering any future live restore design; source/target DB fingerprint mismatches and artifact integrity failures must remain blocking read-only errors.
- Treat restore apply as contract-only: `--apply` must remain read-only/blocked with `legacy-query-preview-cleanup-restore-v1`, actor, reason hash, source/integrity requirements, a private disposable-restore rehearsal that verifies expected restored counts, an aggregate-only restore audit preview, a blocked audit write dry-run, a blocked audit-write apply contract requiring `legacy-query-preview-cleanup-restore-audit-write-v1`, and a read-only audit-write preflight gate before any live restore implementation is considered.
- Verify non-empty `query_preview` count becomes 0 or the remaining rows are explicitly explained.
- Keep backup and rollback artifact paths out of git; rollback artifacts may contain private local query-preview values.

## What not to do next

Do not implement these in the first mutation PR:

- automatic promotion from ordinary conversation;
- broad background consolidation apply mode — DO NOT enable broad G4 apply mode;
- default retrieval ranking changes;
- mutating decay/forgetting;
- LLM-based ordinary preference extraction;
- raw transcript or raw prompt archiving;
- cleanup of any field other than legacy `query_preview` without a separate preview and plan.

## Resume instructions

When a future session resumes this track:

1. Check cron collection status:

```bash
# Hermes cron state is external to the repo; list jobs before assuming collection is done.
# If using Hermes tools, inspect job id 6894df1bfd4c.
```

2. List safe artifact paths only:

```bash
find /Users/reddit/.agent-memory/reports/g4-readiness -maxdepth 1 -name 'scheduled-dry-run-*.json' -print | sort
```

3. Run scheduled compare over the collected artifacts.

4. If the comparison still says `continue_scheduled_report_collection_before_g4`, do not implement mutation yet unless the user explicitly chooses the legacy cleanup slice.

5. If the user asks to proceed with the first mutation, start with RED tests for `query-preview-cleanup --apply --actor --reason`.

## 2026-05-07 status update

This plan successfully served its original purpose: it prevented a direct jump from read-only dogfood reports to broad automatic memory approval.

Completed since the original draft:

- `query-preview cleanup` became the first narrow explicit mutation in G4a. It clears only legacy `retrieval_observations.query_preview` privacy debt under `--apply --policy legacy-query-preview-cleanup-v1 --actor --reason` and audit-safe output.
- `ordinary trace metadata default cleanup` became the second narrow explicit mutation in G4b. It normalized only already-metadata-only ordinary `turn` traces by filling conservative metadata defaults.
- H1-H4 hardening and retrieval-eval expansion continued through `v0.1.99`; latest runtime QA passed at `/Users/reddit/.agent-memory/reports/v0.1.99-runtime-qa-20260507T074118`.

The next G4 slice is not live broad mutation. The docs/RED-test-only broader background consolidation apply-mode contract landed in PR #200 and was runtime-verified through v0.1.99. The next safe move is one disposable-DB-backed explicit policy/action slice. That contract must keep the original hard blocks: no ordinary conversation auto-approval, no raw transcript/prompt/query/query-preview persistence, no default retrieval ranking change, no broad LLM extraction from ordinary turns, and no apply mode without explicit named policy, actor, reason, audit, and restore guidance. The first hardening step required the named query-preview cleanup policy on the existing G4a cleanup apply path and shipped in v0.1.100. The v0.1.104-v0.1.110 hardening line adds source DB binding, artifact-integrity checks, a blocked restore apply contract, disposable restore rehearsal, aggregate-only audit preview, an audit write dry-run, and a blocked audit-write apply contract. The next hardening step is a restore audit-write preflight gate: any future audit write must pass exact policy, actor/reason hash continuity, source/integrity/rehearsal checks, content/metadata hash matching, duplicate audit event absence, and raw query/reason/sample exclusion while still returning `write_allowed=false`.


## Current G4a safety hardening: disposable-copy apply check

`dogfood query-preview-cleanup --apply` remains the only narrow mutation being hardened. After the v0.1.101 named-policy and rollback-manifest release, the current slice requires the command to copy the target SQLite DB to a private local disposable artifact, run the same cleanup on that copy, and compare expected eligible/cleared/remaining counts plus rollback-manifest metadata before mutating the target DB. The disposable copy can contain private query-preview data; stdout/audit metadata must stay hash/count/path only and broad G4 apply mode remains blocked.


## Current G4a safety hardening: restore artifact-integrity check

`dogfood query-preview-cleanup --apply` remains the only narrow mutation being hardened. After the v0.1.104 named-policy, rollback-manifest, disposable-copy preflight, restore dry-run, and source-binding release, the current slice tightens `dogfood query-preview-cleanup-restore <db> <rollback-artifact> --dry-run` so malformed or tampered artifacts fail closed with structured JSON. The dry-run remains read-only and aggregate/hash-only, reports blocked reasons such as `artifact_policy_invalid`, `artifact_operation_invalid`, `artifact_row_count_mismatch`, `duplicate_artifact_row_ids`, and `source_database_fingerprint_missing`, and keeps live restore unavailable. Broad G4 apply mode remains blocked.


## Current G4a safety hardening: restore audit write fail-closed contract

`dogfood query-preview-cleanup-restore --apply` remains read-only and blocked. After v0.1.111 locked the deterministic audit-write preflight gate, the current slice adds only fail-closed negative-path contract fields for that future audit write path: failed check names, explicit `write_blocked_by_preflight`, duplicate audit event detection, and a conflict policy that marks duplicate audit events, content/metadata hash mismatch, source DB mismatch, artifact integrity failure, disposable rehearsal failure, and privacy leak risk as `fail_closed`. Duplicate/conflict failures must report `passed=false`, `status=failed_blocked`, `write_allowed=false`, `would_insert=false`, and no extra `experience_traces` insert beyond test-seeded duplicate fixtures. Live restore and audit row writes remain unavailable until a separate explicit policy slice, and broad mutation remains blocked — DO NOT enable broad G4 apply mode.
