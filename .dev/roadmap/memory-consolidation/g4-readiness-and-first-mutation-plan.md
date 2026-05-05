# G4 Readiness and First Mutation Plan

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-05 21:05 KST

## Purpose

This document turns the post-v0.1.76 decision into an ordered execution plan:

1. continue scheduled report collection;
2. compare report trends;
3. write the G4 apply-mode plan before implementation;
4. implement only the first narrow mutation slice after the plan is accepted.

The plan exists to prevent a direct jump from read-only dogfood reports to broad automatic memory approval.

## Current verified starting point

Current release/runtime:

- Latest release: `v0.1.76`.
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory`.
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
- Every mutation must have an audit/history row or an equivalent reviewable record.

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

`dogfood query-preview-cleanup --apply --actor <actor> --reason <reason>` for legacy non-empty `retrieval_observations.query_preview` rows only.

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
8. Dry-run and apply output shapes are distinguishable.
9. New privacy-safe rows remain untouched.
10. Default retrieval/Hermes hook behavior remains unchanged.

Required operator safety before live DB apply:

- Run read-only preview against the live DB.
- Export or back up the DB before mutation.
- Run apply only with explicit actor/reason.
- Re-run storage-health and query-preview cleanup preview after mutation.
- Verify non-empty `query_preview` count becomes 0 or the remaining rows are explicitly explained.
- Keep backup path out of git.

## What not to do next

Do not implement these in the first mutation PR:

- automatic promotion from ordinary conversation;
- broad background consolidation apply mode;
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
