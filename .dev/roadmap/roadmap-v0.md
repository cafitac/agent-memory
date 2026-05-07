# agent-memory roadmap v0

Status: AI-authored draft. Not yet human-approved.

## North-star memory model

The long-term goal is not a curated facts database that only stores items judged important at ingestion time.
The project should become a graph-based memory consolidation runtime inspired by human memory:

- experiences leave lightweight traces first, even when they are not obviously important yet
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and demonstrated retrieval usefulness
- weak traces decay, expire, or collapse into summaries instead of polluting long-term recall
- strong trace clusters consolidate into long-term semantic, episodic, procedural, and preference memories
- old memories can remain retrievable when they are highly salient or strongly connected, even if they are no longer recent
- long-term memories stay explainable through provenance, status history, supersession, and graph relations

In this framing, `agent-memory` should behave less like "save important notes" and more like a safe, inspectable memory system:
conversation and runtime events create short-lived evidence; repeated or meaningful evidence reinforces graph nodes and edges; consolidation promotes only the durable patterns; decay and review keep prompt-time recall from becoming noisy.

This is intentionally heavier than a simple memory MVP, so implementation should still proceed in thin, reversible slices:
trace logging, activation observation, read-only consolidation candidates, review/approval, then conservative automation.

## PR-by-PR implementation ladder

This section is the "stamp rally" plan for reaching the north-star without losing direction.
Each item should normally be one PR, even if the implementation is small.
If a PR grows too large, split it, but preserve the sequence and update this checklist before changing direction.
Every code PR should follow RED -> implementation -> verification, keep runtime defaults conservative, avoid raw prompt/transcript persistence by default, and include docs plus at least one local dogfood command when the change affects Hermes behavior.

Legend:
- Status: `[ ]` planned, `[~]` in progress, `[x]` completed
- Default posture: read-only/reporting before mutation, opt-in before default-on, approved memory before automatic injection

Detailed execution docs live under `.dev/roadmap/memory-consolidation/`:

- `.dev/roadmap/memory-consolidation/README.md`
- `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md` — historical checkpoint after `v0.1.76`; use `.dev/status/current-handoff.md` for the latest verified v0.1.97 state and next recommended slice.
- `.dev/roadmap/memory-consolidation/g4-readiness-and-first-mutation-plan.md` — historical first-mutation plan and current guardrails for the next broader G4 contract.
- `.dev/roadmap/memory-consolidation/stage-a-plan-and-baseline.md`
- `.dev/roadmap/memory-consolidation/stage-b-trace-layer.md`
- `.dev/roadmap/memory-consolidation/stage-c-activation-reinforcement-decay.md`
- `.dev/roadmap/memory-consolidation/stage-d-consolidation-candidates.md`
- `.dev/roadmap/memory-consolidation/stage-e-reviewed-promotion.md`
- `.dev/roadmap/memory-consolidation/stage-f-retrieval-signals.md`
- `.dev/roadmap/memory-consolidation/stage-g-cautious-automation.md`
- `.dev/roadmap/memory-consolidation/stage-h-product-hardening.md`

Use the stage docs as execution guidance. Use this file as the canonical index/checklist.
If a later session changes direction, update both this checklist and the relevant stage doc before implementing.

### Stage A: lock the plan and current dogfood baseline

- [ ] PR A1: Persist this consolidation roadmap and release it as the canonical planning checkpoint
  - Goal: commit the north-star plus PR ladder so future work has a durable sequence.
  - Scope: `.dev/roadmap/roadmap-v0.md`, `.dev/architecture/architecture-v0.md`, `.dev/product/thesis-and-scope.md`, and optionally `.dev/status/current-handoff.md`.
  - Acceptance: docs diff is clean, no accidental line-number artifacts, no code behavior change, PR title clearly says this is a planning checkpoint.

- [ ] PR A2: Add a dogfood baseline snapshot command/report
  - Goal: make the current local observation state easy to compare before/after later trace work.
  - Scope: read-only CLI/report or documented command that captures observation count, empty ratio, top refs, review candidates, runtime version, and Hermes E2E marker status.
  - Acceptance: baseline output contains no raw query/user prompt, is local-only, and can be attached to handoff notes without secrets.

### Stage B: trace layer without automatic memory creation

- [x] PR B1: Add a lightweight `experience_traces` schema behind an explicit write path
  - Goal: create the short-term trace substrate without changing retrieval or saving raw transcripts.
  - Scope: SQLite migration/model/storage APIs for trace id, surface, scope, event kind, timestamp, redaction/hash metadata, summary/signals, TTL/retention fields, and source/provenance refs.
  - Acceptance: tests prove raw prompt text is not required or emitted; existing DBs migrate lazily; normal retrieval is unchanged.

- [x] PR B2: Add `traces record` and `traces list` read-safe CLI
  - Status: completed in v0.1.45 via PR #57.
  - Goal: let developers create and inspect sanitized traces manually before adapters write them.
  - Scope: CLI commands for recording synthetic/sanitized events and listing grouped traces with JSON output.
  - Acceptance: list output redacts or omits raw content, supports scope/surface filters, and has stable JSON suitable for later reports.

- [x] PR B3: Connect Hermes hook to trace recording as conservative opt-in
  - Status: completed in v0.1.46 via PR #59.
  - Goal: record lightweight Hermes turn traces only when explicitly enabled.
  - Scope: `--record-trace` flag for hook/snippet/install/bootstrap, non-blocking write path, synthetic doctor/test skip behavior, docs.
  - Acceptance: hook failures never block Hermes; doctor/test payloads do not pollute traces; local E2E confirms enabled traces are recorded and disabled mode is unchanged.

- [x] PR B4: Add trace retention and local-only safety guardrails
  - Status: completed in v0.1.47 via PR #61.
  - Goal: prevent trace accumulation from becoming an unbounded transcript archive.
  - Scope: read-only retention report first: policy counts, expired trace refs, expirable traces missing `expires_at`, volume warning, privacy docs. Mutating cleanup is deferred.
  - Acceptance: expired traces can be identified read-only first; default behavior remains conservative; no raw transcript retention is introduced.

### Stage C: activation and reinforcement signals

- [ ] PR C1: Introduce activation events for retrieval use
  - Status: in progress on branch `feat/activation-events`.
  - Goal: distinguish "trace happened" from "memory was retrieved/used".
  - Scope: `memory_activations` model/table/storage APIs plus a retrieval-observation bridge that records selected refs and empty retrievals as local-only activation evidence.
  - Acceptance: existing observation commands keep their output contract; activation rows store no raw queries/prompts/query previews; retrieval ranking and long-term memory status remain unchanged.

- [ ] PR C2: Add read-only activation summary CLI
  - Goal: show which memories are repeatedly activated, stale, empty, or scope-mismatched.
  - Scope: `activations summary` or `observations activation-summary` report with counts, windows, surfaces, scopes, and status filters.
  - Acceptance: no raw queries; report identifies high-activation approved facts and noisy deprecated/superseded refs.

- [ ] PR C3: Add reinforcement score calculation as read-only report
  - Goal: compute a transparent score from repetition, recency, user emphasis, graph connectivity, and retrieval usefulness without mutating memory.
  - Scope: scoring module, tests for deterministic scoring, CLI report with factor breakdown.
  - Acceptance: scores are explainable, bounded, and do not change retrieval ranking yet.

- [ ] PR C4: Add decay risk score calculation as read-only report
  - Goal: identify weak, old, low-use, low-connectivity memories/traces that may decay later.
  - Scope: decay scoring module, CLI report, docs explaining that this is advisory only.
  - Acceptance: no mutation; protected approved/high-salience memories are not recommended for deletion solely because they are old.

### Stage D: consolidation candidates before mutation

- [ ] PR D1: Add trace clustering for consolidation candidates
  - Goal: group repeated/similar traces into candidate clusters without creating long-term memories.
  - Scope: deterministic lexical/metadata grouping first; optional graph refs if present; no embeddings required.
  - Acceptance: report shows cluster id, evidence count/window, scopes, surfaces, and safe summaries without raw event text.

- [ ] PR D2: Add `consolidation candidates` read-only CLI
  - Goal: surface possible semantic/episodic/procedural/preference memories for human review.
  - Scope: candidate report with type guess, evidence refs, score factors, suggested review commands, and risk flags.
  - Acceptance: candidates are not auto-approved; output is stable JSON; docs explain manual review flow.

- [ ] PR D3: Add candidate explanation details
  - Goal: make every consolidation candidate auditable.
  - Scope: `consolidation explain <candidate>` style report or expanded JSON explaining why the cluster exists, which signals contributed, and what would be promoted.
  - Acceptance: explanation contains provenance/status/supersession context and never prints raw secrets.

- [ ] PR D4: Add candidate rejection/snooze state
  - Goal: avoid repeatedly suggesting the same bad consolidation candidate.
  - Scope: storage for rejected/snoozed candidate fingerprints, CLI review commands, report filtering.
  - Acceptance: rejection does not delete evidence; snoozed candidates can reappear only after meaningful new evidence or time window changes.

### Stage E: reviewed promotion into long-term memory

- [ ] PR E1: Add manual consolidation promotion for semantic facts
  - Goal: turn an approved candidate into a reviewed long-term Fact with provenance.
  - Scope: CLI command that creates/updates a candidate fact from a candidate cluster only after explicit user action.
  - Acceptance: new fact starts candidate or approved only according to explicit flag; provenance links to traces/observations; default retrieval remains approved-only.

- [ ] PR E2: Add manual consolidation promotion for procedures/preferences
  - Goal: support the memory types that make agents feel personalized and capable.
  - Scope: reviewed promotion paths for Procedure and preference-like facts, with scope and trigger context.
  - Acceptance: generated procedures/preferences are reviewable, explainable, and not injected unless approved.

- [ ] PR E3: Add consolidation relation edges
  - Goal: make graph structure reflect evidence reinforcement and promotion history.
  - Scope: Relation types such as `reinforces`, `consolidated_into`, `derived_from_trace_cluster`, and maybe `decays_into_summary`.
  - Acceptance: `graph inspect` can show trace -> candidate -> durable memory lineage.

- [ ] PR E4: Add conflict/supersession checks during promotion
  - Goal: prevent candidate promotion from silently creating contradictory durable memory.
  - Scope: preflight report comparing candidate against existing approved/deprecated/superseded facts and replacement relations.
  - Acceptance: conflicting promotions require explicit action; suggested commands include explain/replacements/graph inspect.

### Stage F: retrieval uses consolidation signals conservatively

- [ ] PR F1: Add activation/reinforcement metadata to retrieval explanations
  - Goal: make prompt-time memory packets explain why a memory was selected beyond lexical match.
  - Scope: retrieval trace fields and JSON output only; no ranking change yet.
  - Acceptance: backwards-compatible output or versioned fields; tests cover approved-only retrieval and deprecated exclusion.

- [ ] PR F2: Use reinforcement as a small ranking feature behind opt-in
  - Goal: test whether repeated/useful memories rank better without overwhelming lexical/scope relevance.
  - Scope: opt-in retrieval config, deterministic scoring blend, eval comparison.
  - Acceptance: default ranking unchanged; opt-in eval shows no precision regression on fixtures.

- [ ] PR F3: Use decay risk as a prompt-time noise penalty behind opt-in
  - Goal: reduce injection of stale/noisy memories while preserving old salient memories.
  - Scope: opt-in penalty, safeguards for strong graph connectivity/high salience, explanation fields.
  - Acceptance: old but strongly connected E2E marker remains retrievable; deprecated/superseded facts remain excluded.

- [ ] PR F4: Add bounded graph neighborhood reinforcement
  - Goal: let graph connectivity strengthen retrieval without full graph-only search.
  - Scope: bounded relation expansion for approved refs, edge weights, max depth, drift controls.
  - Acceptance: graph+lexical beats lexical-only on target fixtures; explanations remain understandable.

### Stage G: cautious automation

- [x] PR G1: Add explicit `remember this` conservative auto-candidate path
  - Goal: support the safest automatic memory flow for user-directed memories.
  - Scope: detect or accept explicit remember-intent event from adapter/CLI, create candidate with high salience, still require review unless configured otherwise.
  - Acceptance: ordinary conversation does not auto-approve; explicit path is test-covered and secret-safe.

- [x] PR G2: Add opt-in auto-approval for narrow low-risk memories
  - Goal: allow advanced users to auto-approve safe preferences/procedures under strict rules.
  - Scope: config-gated policy with allowed scopes/types, confidence threshold, redaction checks, conflict preflight, audit log.
  - Acceptance: default off; every auto-approval is explainable and reversible.

- [x] PR G3: Add background consolidation job in dry-run mode
  - Goal: periodically compute candidates and scores without changing memory.
  - Scope: CLI job command, cron-friendly output, file lock/safety, docs.
  - Acceptance: dry-run is default; failures are non-blocking; output can be reviewed before enabling mutations.
  - Status: completed through v0.1.66-v0.1.69, then extended with remember-intent diagnostics and ordinary trace live-path hardening through v0.1.71.

- [x] PR G3c: Add read-only dogfood storage-health report
  - Goal: make live Hermes/agent-memory storage health inspectable without ad hoc SQL or raw content exposure.
  - Scope: one-command report for table counts, latest timestamps, runtime/config marker checks, query-preview/hash/privacy invariants, orphan/invalid-JSON checks, and trace metadata shape counts.
  - Acceptance: read-only with `mutated=false`, no raw prompt/query/transcript/user-message/secret output, works on temp fixtures and the live DB, and flags observation/activation-without-trace regressions before G4 planning.
  - Status: completed and released in v0.1.72 via PR #127/#128.

- [x] PR G3c-followup: Add read-only legacy query-preview cleanup preview
  - Goal: make the storage-health `stored_query_excerpt` warning actionable without ad hoc SQL or raw query-preview leakage.
  - Scope: `agent-memory dogfood query-preview-cleanup <db> --older-than <timestamp>` reports aggregate affected/eligible counts, timestamps, privacy markers, and a recommended operation marker; no apply mode yet.
  - Acceptance: read-only with `mutated=false`, no raw prompt/query/transcript/user-message/secret output, no sample values, focused tests prove no DB mutation, and live DB smoke verifies aggregate-only output.
  - Status: completed and released in v0.1.73 via PR #129/#130.

- [x] PR G3d: Add read-only dogfood trace-quality report
  - Goal: measure whether ordinary metadata-only traces are useful enough to support later consolidation work before any G4 apply-mode plan.
  - Scope: `agent-memory dogfood trace-quality <db> --since-hours <hours> --min-trace-coverage <ratio> --min-evidence-count <count>` reports aggregate observation-to-trace coverage, empty retrieval ratio, repeated memory-ref counts, trace distributions, metadata-only invariants, candidate-signal proxies, and a conservative recommendation.
  - Acceptance: read-only with `mutated=false`, no raw prompt/query/trace-summary/transcript/user-message/secret/sample output, no candidates or approvals created, default retrieval unchanged, focused tests prove no DB mutation, and live DB smoke verifies aggregate-only output.
  - Status: completed and released in v0.1.74 via PR #132/#133.

- [x] PR G3e: Add scheduled dry-run dogfood bundle
  - Goal: run storage-health, trace-quality, remember-intent, and background consolidation dry-run together so multiple scheduled reports can guide the G4 decision.
  - Scope: `agent-memory dogfood scheduled-dry-run <db> --output <path>` emits one `dogfood_scheduled_dry_run` JSON payload with nested read-only reports, top-level privacy/no-mutation/default-retrieval markers, thresholds, and one conservative quality gate.
  - Acceptance: read-only with `mutated=false`, no raw prompt/query/trace-summary/transcript/user-message/secret/sample output, no candidates or approvals created, default retrieval unchanged, focused tests prove no DB mutation, and live DB smoke writes a report artifact.
  - Status: completed and released in v0.1.75 via PR #135/#136; first live quality gate recommends continuing scheduled dogfood before G4.

- [x] PR G3f: Collect scheduled dry-run trend reports
  - Goal: compare multiple G3e report artifacts over time before drafting apply-mode behavior.
  - Scope: `agent-memory dogfood scheduled-compare --report <path> --report <path> --output <path>` emits a read-only `dogfood_scheduled_dry_run_comparison` payload over saved scheduled reports, including per-report hashes and aggregate counts/ratios/warning names only.
  - Acceptance: no raw content, no embedded raw report bodies, no mutation, no default retrieval change; output explains whether signals are stable enough for a separate G4 plan or blocked by warnings/decay risk/legacy cleanup/noise.
  - Status: completed and released in v0.1.76 via PR #138/#139; first live comparison recommends continuing scheduled report collection before G4.

- [x] PR G3g: Continue scheduled report collection and lock the G4 readiness sequence
  - Goal: make the post-G3f plan explicit while scheduled artifacts accumulate over time.
  - Scope: collect local-only scheduled artifacts, schedule repeated collection, and document the sequence: collect reports -> compare trends -> draft apply-mode contract -> implement one narrow mutation.
  - Acceptance: docs name the artifact directory, cron/job boundary, G4 apply-mode prerequisites, and the first recommended mutation slice without adding any new DB mutation.
  - Status: complete via PR #141. Later PRs implemented the first two narrow cleanup mutations, but broad background consolidation apply mode remains blocked.

- [x] PR G4-plan: Draft first mutation apply-mode contract before implementation
  - Goal: define exact eligible actions, blocked actions, CLI flags, JSON output, audit records, and rollback rules before the first mutating cleanup command.
  - Scope: docs and RED-test plan only before implementation.
  - Acceptance: `--apply`, `--actor`, `--reason`, and named policy/audit intent are mandatory for future mutation; ordinary conversation auto-approval, raw transcript storage, and default retrieval ranking changes remain forbidden.
  - Status: complete as the contract path that enabled G4a/G4b narrow cleanup; it does not authorize broader consolidation apply mode.

- [x] PR G4a: Add first narrow mutation for legacy query-preview cleanup
  - Goal: remove legacy privacy debt by clearing old non-empty `retrieval_observations.query_preview` values under an explicit operator command.
  - Scope: extend `dogfood query-preview-cleanup` with `--apply --actor --reason`, backup/operator instructions, and audit-safe output.
  - Acceptance: RED tests prove dry-run remains default, apply cannot run without actor/reason, only eligible legacy rows are cleared, raw previews are never printed, and default retrieval/Hermes hook behavior is unchanged.
  - Status: implemented in PR #142, released in v0.1.77 via PR #143, and applied once to the live DB; 70 legacy rows cleared, 0 non-empty `query_preview` rows remain, backup/artifacts under `/Users/reddit/.agent-memory/reports/query-preview-cleanup-v0177-20260505T142043Z`.

- [x] PR G4b: Add second narrow mutation for ordinary trace metadata default cleanup
  - Goal: clear the remaining storage-health ordinary metadata-only warning when it is caused only by old ordinary `turn` traces missing conservative metadata defaults.
  - Scope: add `dogfood ordinary-trace-metadata-cleanup` preview/apply with `--apply --actor --reason`, aggregate/hash-only output, and docs/tests.
  - Acceptance: RED tests prove preview is read-only, apply cannot run without actor/reason, apply only fills `candidate_policy=evidence_only` and `auto_approved=false` for traces that already have `summary=NULL` and `retention_policy=ephemeral`, raw metadata/sample values are never printed, and default retrieval/Hermes hook behavior is unchanged.
  - Status: implemented in PR #145, released in v0.1.78 via PR #146, and applied once to the live DB; 1 legacy ordinary turn row normalized, ordinary metadata-only preview now reports 0 violations, and storage-health is healthy. Follow-up quality-gate stabilization landed before the v0.1.97 runtime QA line.

- [x] PR G4-broad-plan: Draft broader consolidation apply-mode contract before implementation
  - Goal: define the contract for controlled promotion/snooze/decay actions without adding broad mutation yet.
  - Scope: docs/RED-test-only checkpoint over CLI flags, policy naming, eligible action classes, blocked action classes, preview/apply JSON, audit records, restore/rollback, and live-runtime QA prerequisites.
  - Acceptance: broad apply remains unimplemented; `--apply --actor --reason` plus a named policy are required; ordinary conversation auto-approval remains forbidden; raw transcript storage remains forbidden; default retrieval ranking changes remain forbidden.
  - Status: complete in PR #200, stabilized by PR #202, and released/runtime-verified in v0.1.98 via PR #201. This checkpoint authorizes only the next disposable-DB-backed explicit policy/action slice, not live broad apply.

- [ ] PR G4: Add broader background consolidation apply mode behind explicit policy
  - Goal: allow controlled promotion/snooze/decay actions after the dry-run path is trusted.
  - Scope: explicit `--apply` with policy file, audit trail, rollback instructions.
  - Acceptance: no apply without explicit flag; actions are reversible or at least reviewable; docs warn this is advanced.

### Stage H: product hardening and public readiness

- [x] PR H1: Add retrieval/consolidation evaluation fixtures and metrics
  - Done across the retrieval-eval M1/M1+ line before v0.1.83: `agent-memory eval retrieval <db> <fixtures>` now exercises the real retrieval path, supports baseline modes (`lexical`, `lexical-global`, `source-lexical`, `source-global`), text/JSON output, advisory reports, and regression flags.
  - Acceptance: covered by `tests/test_retrieval_evaluation.py`, `tests/test_cli.py`, README docs, and the full local suite; follow-up PR #162 / v0.1.85 raised checked-in retrieval tasks to 12, PR #165 / v0.1.86 raised them to 13 with noisy global fact coverage, and PR #168 / v0.1.87 raised them to 14 with same-slot conflicting fact coverage.

- [x] PR H2: Add graph/trace visualization export
  - First completed in PR #149 / v0.1.80 with `graph export-html`: local standalone HTML, typed memory/trace/observation/activation graph, ref-only labels by default, explicit `--include-memory-labels` opt-in.
  - Continued through PR #154 / v0.1.82 and PR #156 / v0.1.83: event-driven brain-like Canvas UI, filters/search, zoom/pan, dominant-hub explanation, node inspector, Korean-localized visible UI, and quality modes (`auto`, `performance`, `sharp`).
  - Acceptance: export is local-only/read-only/redacted by default and examples do not include raw source content, raw query text, trace summaries, or secrets.

- [x] PR H3: Add backup/import/export for trace and consolidation state
  - Goal: make the richer memory DB operationally safe.
  - Scope: `agent-memory backup export|inspect|restore`, metadata-only manifest, SQLite backup API copy, restore overwrite guard, version and database-entry validation, README privacy docs.
  - Acceptance: backup round-trip works in tests; incompatible versions and unsafe database entries fail safely; existing output DBs are protected unless `--overwrite` is explicit.
  - Status: complete and released in v0.1.84 via PR #158/#159; published PyPI/npm install smokes and live Hermes pinned-runtime QA passed.

- [x] PR H4: Promote reviewed docs from `.dev` into public docs
  - Goal: explain the memory consolidation model to external users only after enough behavior exists.
  - Scope: README/docs stable-vs-experimental framing, first-run backup guidance, Hermes dogfood guardrails, install-smoke command refresh, and a public privacy/safety model.
  - Acceptance: docs accurately distinguish stable/default behavior from experimental opt-in features; private local artifacts and backup bundles are called out; H4 landed in PR #161 and was followed by v0.1.85 runtime QA.

### Sequence guardrails

Do not skip directly to automatic memory saving until the earlier read-only reports and manual review loops are proven in local dogfood.
Specifically:

1. No raw transcript archive as a default storage layer.
2. No automatic long-term approval before secret/redaction checks, provenance, conflict/supersession checks, and audit logs exist.
3. No default retrieval ranking change before opt-in eval and live Hermes E2E pass.
4. No mutating cleanup/decay before read-only decay reports are understandable and trusted.
5. Every release that touches Hermes runtime behavior must be installed from the published artifact and verified with a real Hermes E2E turn.

## Phase 0: design spike

Objectives:
- define canonical memory objects
- define scope boundaries with host runtimes and external KBs
- choose SQLite-first persistence strategy
- define evaluation metrics and baselines
- decide the first adapter target

Exit criteria:
- architecture draft exists
- research notes exist
- graph-vs-hybrid position is explicit
- first milestone is small enough to implement safely

## Phase 1: local memory MVP

Objectives:
- ingest raw sources into SourceRecord
- extract candidate entities, episodes, facts, procedures, and relations
- store canonical objects in SQLite
- support FTS5 retrieval and basic graph traversal
- support approval / rejection / deprecation lifecycle
- expose a CLI for ingest, search, retrieve, review

Suggested deliverables:
- `src/agent_memory/core/models.py`
- `src/agent_memory/storage/schema.sql`
- `src/agent_memory/storage/sqlite.py`
- `src/agent_memory/core/retrieval.py`
- `src/agent_memory/core/curation.py`
- `src/agent_memory/api/cli.py`
- tests for ingestion, deduplication, retrieval, and review

Exit criteria:
- can ingest a transcript or note
- can extract and review candidates
- can approve durable facts/procedures
- can retrieve a compact memory packet that beats transcript grep alone

## Phase 2: Hermes integration

Objectives:
- add a thin Hermes adapter
- support prompt-time retrieval packets
- support session/event ingestion
- support memory review workflow from real Hermes traces

Candidate integration surfaces:
- local CLI called from hooks
- HTTP/MCP retrieval service
- Hermes memory-provider integration
- background ingestion worker fed by exported sessions/events

Exit criteria:
- real Hermes session data can be ingested
- prompt-time retrieval works for at least one end-to-end workflow
- the adapter stays thin and the core remains harness-agnostic

## Phase 3: hybrid retrieval

Objectives:
- add optional embedding support
- improve reranking with recency, importance, confidence, and scope
- bound graph expansion depth and drift
- add contradiction-aware ranking penalties

Exit criteria:
- graph+lexical beats lexical-only on target tasks
- graph+lexical+embedding beats simpler setups only when measured, not assumed
- retrieval explanations remain understandable

## Phase 4: memory lifecycle maturity

Objectives:
- forgetting and decay policies
- archival tiers
- reflection / consolidation jobs
- temporal validity windows
- richer procedural success tracking

Exit criteria:
- stale memory can decay safely
- episodic traces can consolidate into semantic/procedural memory
- historical evidence remains available without polluting prompt-time recall

## Phase 5: product hardening

Objectives:
- multi-user / multi-project scopes
- memory graph visualization
- benchmark suite
- import/export and backup
- operational docs for approved `docs/` promotion

Exit criteria:
- reproducible benchmark harness exists
- users can inspect memory quality and provenance visually
- approved public docs can be promoted from `.dev/`

## Cross-phase evaluation track

Across all phases, measure:
- task success uplift
- repeated-user-correction reduction
- prompt token savings
- precision/recall of memory retrieval
- contradiction rate
- retrieval explanation quality
- procedure reuse success rate

## Recommended implementation order

1. schema and object model
2. ingestion pipeline
3. review / curation pipeline
4. lexical retrieval baseline
5. graph traversal
6. Hermes adapter stub
7. embedding sidecar
8. forgetting / reflection / evaluation suite
