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

Status: In progress for the next release. This slice is dry-run/report-only; apply mode remains G4/later.

### Objective

Make periodic candidate/scoring reports cron-friendly without changing memory.

### Acceptance

- Dry-run default.
- File locking or concurrency protection exists.
- Failures are non-blocking and readable.
- Output is suitable for human review.

### Planned implementation shape

- Command: `agent-memory consolidation background dry-run <db> [--output <path>] [--lock-path <path>]`.
- Bundles existing read-only surfaces: `consolidation candidates`, `activations summary`, `activations reinforcement-report`, and `activations decay-risk-report`.
- Uses a non-blocking file lock so overlapping cron runs exit zero with `status: skipped_lock_busy`.
- Writes JSON to stdout and, when `--output` is supplied, the same JSON to disk for later review.
- Keeps `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`; no facts/sources/relations/status transitions/traces/retrieval observations are created.
- Does not infer from ordinary conversation, does not add apply mode, and does not change default retrieval/Hermes hook behavior.

## PR G4: Add background consolidation apply mode behind explicit flag

### Objective

Allow controlled application only after dry-run output is trusted.

### Acceptance

- Requires explicit `--apply` or equivalent.
- Requires policy file/config.
- Writes audit trail.
- Docs explain risk and rollback.
