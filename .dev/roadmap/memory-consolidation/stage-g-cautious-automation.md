# Stage G: Cautious Automation

Status: AI-authored draft. Not yet human-approved.

## Goal

Add automation only after traces, activation reports, consolidation candidates, manual promotion, conflict checks, and opt-in retrieval signals are proven.

Automation starts with explicit user intent, then narrow opt-in policies, then dry-run jobs, then explicit apply mode.

## Stage exit criteria

- Explicit `remember this` creates high-salience candidates safely.
- Narrow auto-approval is opt-in and audited.
- Background consolidation can run in dry-run mode.
- Apply mode requires explicit flags/policy and is reversible or auditable.

## PR G1: Add explicit `remember this` conservative auto-candidate path

Status: Complete in `v0.1.63` via PR #102. G1 uses the Hermes opt-in trace path and remains review-gated.

### Objective

Capture user-directed remember intent as a candidate, not necessarily as approved memory.

### Acceptance

- Ordinary conversation does not auto-approve.
- Explicit remember-intent is test-covered.
- Secret/redaction checks run before candidate creation.
- Candidate is explainable and reviewable.
- G1 remains gated behind existing `--record-trace`; it records `remember_intent` review traces only, never approved facts/procedures/episodes.

## PR G1a: Dogfood/evaluate explicit remember-intent traces before G2

Status: Complete in `v0.1.64` via PR #105. This is a conservative quality gate before any auto-approval slice.

### Objective

Summarize real/local `remember_intent` trace quality without mutating memory so G2 policy work starts from measured noise and guardrail data.

### Acceptance

- Report is read-only and visibly says default retrieval is unchanged.
- Counts inspected `remember_intent` traces, ordinary turn traces, review-ready traces, scope distribution, and unsafe samples.
- Does not print raw metadata, raw prompts, transcripts, or secret-like summaries.
- Does not create facts/procedures/episodes, relations, status transitions, candidates, or approvals.
- Points next steps toward human review and G2 default-off policy design.

## PR G2: Add opt-in auto-approval for narrow low-risk memories

Status: Complete in `v0.1.65` via PR #108. This slice intentionally implements only `remember-preferences-v1` and leaves broader procedure/preference inference for later.

### Objective

Allow advanced users to auto-approve safe preferences/procedures under strict policy.

### Acceptance

- Default off.
- Policy is scope/type constrained.
- Conflict preflight runs.
- Every auto-approval has audit history and rollback/review path.

### Implemented policy shape

- Command: `agent-memory consolidation auto-approve remember-preferences <db> --policy remember-preferences-v1 --scope <scope> [--apply --actor ... --reason ...]`.
- Default is dry-run/read-only; apply requires `--apply`, `--actor`, and `--reason`.
- Eligible traces must be explicit/review-ready `remember_intent` rows in the selected scope with sanitized summaries shaped like `User prefers ...` or `I prefer ...`.
- Approved memory type is constrained to semantic `fact`, `subject_ref=user`, `predicate=prefers`.
- Secret-like summaries, ordinary turns, unsupported summary shapes, scope mismatches, and claim-slot conflicts are blocked.
- Successful apply writes normal status-transition audit history and an `experience_trace:<id> --auto_approved_as--> fact:<id>` graph relation.

## PR G3: Add background consolidation job in dry-run mode

Status: Complete in `v0.1.66` via PR #111. This slice is dry-run/report-only; apply mode remains G4/later.

### Objective

Make periodic candidate/scoring reports cron-friendly without changing memory.

### Acceptance

- Dry-run default.
- File locking or concurrency protection exists.
- Failures are non-blocking and readable.
- Output is suitable for human review.

### Implemented shape

- Command: `agent-memory consolidation background dry-run <db> [--output <path>] [--lock-path <path>]`.
- Bundles existing read-only surfaces: `consolidation candidates`, `activations summary`, `activations reinforcement-report`, and `activations decay-risk-report`.
- Uses a non-blocking file lock so overlapping cron runs exit zero with `status: skipped_lock_busy`.
- Writes JSON to stdout and, when `--output` is supplied, the same JSON to disk for later review.
- Keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`; no facts/sources/relations/status transitions/traces/retrieval observations are created.
- Does not infer from ordinary conversation, does not add apply mode, and does not change default retrieval/Hermes hook behavior.

## PR G3a: Dogfood background dry-run quality gates before G4

Status: Complete in `v0.1.67` via PR #114. This slice evaluates saved G3 dry-run reports without mutation so G4 does not start from anecdotal evidence.

### Objective

Summarize repeated G3 background dry-run outputs into a conservative quality gate for deciding whether a separate G4 plan is even worth drafting.

### Acceptance

- Evaluator is read-only and reports `mutated=false`, `default_retrieval_unchanged=true`.
- Input is one or more saved `consolidation background dry-run` JSON reports.
- Output summarizes status counts, candidate/reinforcement/decay-risk maxima, quality warnings, thresholds, and blocked reasons.
- Raw report payloads, raw prompts, query text, query previews, `raw_prompt`, secrets, and transcripts are not embedded in the dogfood report.
- Passing quality gates do not enable apply mode; they only recommend a separate G4 plan with RED tests, audit, and rollback.

## PR G3b: Record ordinary Hermes turns as metadata-only lightweight traces

Status: Complete in `v0.1.68` via PR #117, with the empty-context trace recording hotfix released in `v0.1.69` via PR #120. This reordered the roadmap after v0.1.67 so ordinary conversation produces safe metadata-only trace evidence before any G4 apply mode.

### Why this comes before G4

The north-star is not a manual "Remember this" notebook. Ordinary Hermes usage should leave weak, bounded traces that can later strengthen through repetition, recency, salience, retrieval usefulness, and graph connectivity. G1/G2 were deliberately explicit and conservative; they are not the final memory model. Before any background apply mode, the runtime needs a safer evidence layer for ordinary turns.

### Objective

Let normal Hermes turns create local, metadata-only `turn` traces by default while preserving privacy and keeping long-term memory creation review-gated.

### Acceptance

- Default Hermes pre-LLM hook records a bounded `experience_traces` row for real non-synthetic turns.
- The trace is metadata-only: no raw prompt, raw query, query preview, transcript, user message, or secret-like content is stored or printed.
- Trace content is represented by a hash/fingerprint plus safe metadata, related retrieval observation ids/refs when available, scope, salience signals, and short/ephemeral retention.
- Synthetic Hermes doctor/test payloads are still skipped.
- Hook failures remain non-blocking.
- Ordinary `turn` traces do not create facts/procedures/episodes, do not auto-approve candidates, and do not change retrieval ranking.
- Explicit `Remember this:` remains higher-salience `remember_intent` with review policy; ordinary turns are lower-salience evidence only.
- Docs and dogfood reports clearly distinguish weak traces from approved long-term memories.

### Non-goals

- No G4 apply mode.
- No automatic approval from ordinary conversation.
- No raw transcript archive.
- No LLM-based extraction of preferences/procedures in this slice.
- No default retrieval ranking change.

## PR G3g: Continue scheduled collection and lock G4 readiness sequence

Status: Complete via PR #141. Scheduled collection remains active while post-cleanup reports accumulate.

### Objective

Keep collecting scheduled dry-run artifacts while making the next four-step sequence explicit: collect reports, compare trends, write the G4 apply-mode contract, then implement only the first narrow mutation slice.

### Acceptance

- Scheduled artifacts are local-only and not committed.
- Repeated collection uses the installed runtime and live DB read-only.
- The plan names the artifact directory and cron/job boundary.
- The first recommended mutation is legacy `query_preview` cleanup, not memory auto-approval.
- No new DB mutation, retrieval change, or Hermes config change lands in this docs slice.

### Implemented planning shape

- Current artifact directory: `/Users/reddit/.agent-memory/reports/g4-readiness`.
- Current scheduled collector job id: `6894df1bfd4c`.
- Detailed plan: `.dev/roadmap/memory-consolidation/g4-readiness-and-first-mutation-plan.md`.

## PR G4-plan: Draft background apply-mode contract before implementation

Status: Complete for first narrow cleanup mutations. The query-preview cleanup path now has a named policy gate, rollback-manifest hardening, disposable-copy preflight hardening, restore dry-run validation, and source-database fingerprint hardening complete and artifact-integrity hardening in progress; broader consolidation apply mode still requires a separate contract before mutating code.

### Objective

Define exactly what future apply mode may mutate, what it must audit, and what remains forbidden.

### Acceptance

- Dry-run remains default.
- `--apply`, `--actor`, `--reason`, and a named policy are mandatory for future mutation.
- JSON output distinguishes no-op/dry-run from real mutation.
- Every mutation path has audit or reviewable operation records plus restore/rollback guidance.
- Ordinary conversation auto-approval, raw transcript storage, broad LLM extraction, and default retrieval ranking changes remain forbidden.

## PR G4a: Add first narrow mutation for legacy query-preview cleanup

Status: Implemented in PR #142, released in `v0.1.77` via PR #143, applied once to the live DB, and hardened through `v0.1.109` with a named policy gate, rollback manifest, disposable-copy preflight before target DB mutation, read-only restore dry-run validation, source DB binding, artifact integrity, blocked restore apply contract, disposable restore rehearsal, aggregate audit preview, and audit write dry-run. Current follow-up adds only a blocked audit-write apply contract; live restore, audit row writes, and broader G4 consolidation apply mode remain blocked by explicit policy/readiness work.

### Objective

Clear legacy `retrieval_observations.query_preview` values from old versions with explicit operator approval.

### Acceptance

- RED tests prove apply cannot run without `--apply --policy legacy-query-preview-cleanup-v1 --actor --reason`.
- Dry-run remains read-only.
- Apply clears only eligible legacy rows older than the cutoff.
- Raw query preview values are never printed.
- The command writes audit-safe operation metadata, including rollback manifest path/hash/count without raw values in stdout/audit.
- The command preflights apply on a private disposable DB copy before target DB mutation.
- A restore dry-run validates rollback artifacts and target-row compatibility without mutating or printing raw query previews; source/target DB fingerprint mismatch and artifact integrity failures are blocking; live restore remains unavailable.
- Restore apply intent is contract-only: it requires `legacy-query-preview-cleanup-restore-v1`, actor, reason hash, source/integrity gates, a private disposable-restore rehearsal, an aggregate restore audit preview, a blocked audit write dry-run, a dry-run audit row materialization contract, a blocked audit-write apply contract requiring `legacy-query-preview-cleanup-restore-audit-write-v1`, a read-only audit-write preflight gate, a single-row apply policy packet, an approval-token-missing negative gate, and duplicate/conflict fail-closed reporting while returning `mutated=false`, `restore_apply_available=false`, `would_insert=false`, and `write_allowed=false`. The row materialization freezes the future `experience_traces` insert columns/canonical JSON values/duplicate key without enabling writes; the policy packet freezes the exact operator approval payload, expected insert count, row materialization hash, rollback/manual-review limits, and privacy flags while still requiring explicit operator approval; the approval-token negative gate freezes `approval_token_required=true`, `approval_token_present=false`, `approval_token_sha256=null`, and `write_blocked_by_missing_approval=true` without adding any token flag. Duplicate audit events, missing approval token, content/metadata hash mismatch, source DB mismatch, artifact integrity failure, disposable rehearsal failure, and privacy leak risk must fail closed; broad mutation remains blocked — DO NOT enable broad G4 apply mode.
- Storage-health and cleanup preview can verify the result afterward.
- Retrieval/Hermes behavior is unchanged.

### Live dogfood result

- Backup and artifacts: `/Users/reddit/.agent-memory/reports/query-preview-cleanup-v0177-20260505T142043Z`.
- Before preview: 70 affected/eligible legacy rows.
- Apply: cleared 70 rows, remaining affected count 0, audit trace id 143, reason and eligible row ids recorded as hashes.
- After preview/direct SQL: 0 non-empty `query_preview` rows.
- After scheduled-dry-run: read-only/no-mutation with raw-content privacy flags false.

## PR G4b: Add second narrow mutation for ordinary trace metadata default cleanup

Status: Implemented in PR #145, released in `v0.1.78` via PR #146, and applied once to the live DB. Follow-up quality-gate stabilization landed before the v0.1.97 runtime QA line. Broader G4 consolidation apply mode remains planned and blocked by explicit policy/readiness work.

### Objective

Normalize legacy ordinary `turn` traces that are already metadata-only but are missing the conservative defaults required by the storage-health invariant.

### Acceptance

- RED tests prove apply cannot run without `--apply --actor --reason`.
- Preview remains read-only and aggregate/hash-only.
- Apply only fills `candidate_policy=evidence_only` and `auto_approved=false`.
- Apply is limited to ordinary `turn` traces that already have `summary=NULL` and `retention_policy=ephemeral`.
- Raw trace metadata, prompts, transcripts, queries, sample values, and raw reason text are never printed or written to the audit trace.
- The command writes audit-safe operation metadata.
- Storage-health and scheduled-dry-run can verify the result afterward.
- Retrieval/Hermes behavior is unchanged.

### Current live preview

- Source-checkout read-only preview against `/Users/reddit/.agent-memory/memory.db` found 2 aggregate violations on 1 fixable legacy ordinary `turn` row.
- Live v0.1.78 apply normalized 1 fixable row with audit trace id 150.
- After preview reports 0 ordinary metadata-only violations and storage-health reports `status=healthy` with no warnings.
- The follow-up quality-gate fix removes stale `storage_health_not_clean` blocked reasons when storage-health reports `healthy`.

## PR G4-broad-plan: Draft broader consolidation apply-mode contract before implementation

Status: Complete in PR #200, stabilized by PR #202, and released/runtime-verified in v0.1.99 via PR #204. This remains a docs/RED-test-only contract checkpoint; broad mutation is still blocked — DO NOT enable broad G4 apply mode.

### Objective

Define the future contract for controlled background consolidation mutations before implementation. The contract must decide which promotion, snooze, rejection, or decay actions are eligible; which actions remain blocked; what preview/apply JSON looks like; and how audit/restore works.

### Acceptance

- No broad mutation is implemented in this planning slice.
- No ordinary conversation auto-approval.
- No raw transcript archive.
- No default retrieval ranking change.
- Requires explicit `--apply`, `--actor`, `--reason`, and a named policy before any future mutation.
- Preview remains read-only and is the default.
- Apply output is aggregate/ref/hash-only and distinguishes real mutation from no-op.
- Every future mutation path has audit or reviewable operation records plus restore/rollback guidance.
- Live Hermes runtime QA from the published artifact is required before any future broad apply slice is marked complete.

## PR G4: Add broader background consolidation apply mode behind explicit policy

Status: Blocked until a first disposable-DB-backed explicit policy/action slice proves the apply/audit/restore contract. PR G4-broad-plan has landed, but it did not authorize live broad apply.

### Objective

Allow controlled application only after dry-run output is trusted and the broader apply-mode contract is RED-tested.

### Acceptance

- Requires explicit `--apply` or equivalent.
- Requires an explicit named policy; the first narrow cleanup path uses `--policy legacy-query-preview-cleanup-v1`.
- Writes audit trail.
- Docs explain risk and rollback; narrow cleanup apply emits a rollback manifest before mutation.
- Ordinary conversation auto-approval remains forbidden.
- Raw transcript storage remains forbidden.
- Default retrieval ranking changes remain forbidden.


## Current G4a safety hardening: restore dry-run check

`dogfood query-preview-cleanup --apply` remains the only narrow mutation being hardened. After the v0.1.104 named-policy, rollback-manifest, disposable-copy preflight, restore dry-run, and source-binding release, the current slice hardens read-only `dogfood query-preview-cleanup-restore <db> <rollback-artifact> --dry-run` against malformed or tampered artifacts. It rejects wrong-policy, invalid-operation, declared row-count mismatch, duplicate row id, and missing/mismatched source fingerprint cases as structured read-only errors before reporting any restorable rows. Live restore remains unavailable and broad G4 apply mode remains blocked.
