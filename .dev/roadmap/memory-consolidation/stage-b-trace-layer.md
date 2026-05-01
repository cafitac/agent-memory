# Stage B: Trace Layer Without Automatic Memory Creation

Status: AI-authored draft. Not yet human-approved.

## Goal

Create the low-cost evidence layer for brain-like memory without making anything durable automatically. Stage B is about safe traces, not long-term memory.

A trace is a sanitized, bounded, local event record. It may later support activation, reinforcement, and consolidation, but by itself it must not be injected into prompts as approved memory.

## Stage exit criteria

- `experience_traces` or equivalent storage exists with lazy migration.
- Developers can record/list sanitized traces manually.
- Hermes can record traces only when explicitly enabled.
- Retention guardrails prevent the trace layer from becoming an unbounded transcript archive.

## Shared model constraints

A trace should support these concepts, but exact names can change during implementation:

- id
- created_at
- surface, e.g. `cli`, `hermes`, `hermes-pre-llm-hook`
- scope/project/session identifiers where safe
- event_kind, e.g. `turn`, `tool_result_summary`, `user_correction`, `remember_intent`
- query/content hash or fingerprint, not raw prompt
- sanitized summary or signal payload when explicitly supplied
- salience/user_emphasis signals
- related memory refs or observation ids
- retention/TTL fields
- metadata JSON for non-sensitive adapter data

## PR B1: Add a lightweight `experience_traces` schema behind an explicit write path

### Objective

Introduce the storage substrate while keeping retrieval and Hermes behavior unchanged.

### Likely files

- `src/agent_memory/core/models.py`
- `src/agent_memory/storage/sqlite.py`
- `tests/test_storage.py` or a new focused storage test file
- possibly `src/agent_memory/storage/schema.sql` if this repo uses static schema text for new tables

### Test ideas

- New DB creates the trace table lazily.
- Existing DB without the table migrates lazily.
- A trace can be written with only hashes/sanitized metadata.
- Listing traces never returns raw prompt fields.
- Retrieval output is unchanged after adding the schema.

### Acceptance

- No CLI command is required yet.
- No Hermes hook writes traces yet.
- No default memory retrieval/ranking change.
- The table design explicitly supports retention and provenance.

### Implementation status

- Completed in v0.1.44 via PR #55.
- Added `ExperienceTrace` model and `experience_traces` SQLite table with lazy migration.
- Added explicit storage APIs: `insert_experience_trace(...)` and `list_experience_traces(...)`.
- Stored fields are bounded/sanitized: content fingerprint, optional sanitized summary/signals, related memory refs, related observation ids, retention policy/expiry, and metadata.
- Raw prompt/transcript/content columns are intentionally absent; known raw metadata keys are stripped before persistence.
- Retrieval output/ranking remains unchanged by trace writes.
- Focused tests live in `tests/test_experience_traces.py`.

## PR B2: Add `traces record` and `traces list` read-safe CLI

### Objective

Expose trace creation/listing for synthetic and manually sanitized events so the storage shape can be dogfooded before adapters write into it.

### Candidate CLI

```bash
agent-memory traces record <db> --surface cli --event-kind user_correction --summary "sanitized summary" --scope project:agent-memory
agent-memory traces list <db> --limit 50 --surface cli --event-kind user_correction --scope project:agent-memory
```

Exact argument names may change, but the CLI must make it obvious that raw transcript input is not the default path.

### Test ideas

- CLI records a trace with sanitized summary.
- CLI list supports surface/scope/event filters.
- CLI list output contains trace ids, timestamps, signals, and metadata but not raw prompt text.
- CLI handles empty DBs.

### Acceptance

- Manual trace workflow works without Hermes.
- JSON output is stable enough for Stage C reports.
- Docs explain the command is experimental/local-only.

### Implementation status

- Completed in v0.1.45 via PR #57.
- Added `traces record` as an explicit manual write path only; if `--content-sha256` is omitted, the CLI hashes the sanitized `--summary` instead of accepting raw transcript input.
- Added `traces list` as read-only JSON with `--surface`, `--event-kind`, and `--scope` filters.
- The command does not create long-term facts/episodes/procedures and does not alter retrieval ranking.
- Hermes hook trace writes remain disabled by default and are handled as an explicit opt-in in PR B3.

## PR B3: Connect Hermes hook to trace recording as conservative opt-in

### Objective

Let real Hermes turns create lightweight traces only when explicitly enabled, while preserving the principle that hook failures must not block the user.

### Design choices to settle in the PR

- Config/env flag name for opt-in.
- Which Hermes payload fields are safe as metadata.
- How to identify synthetic doctor/test payloads and skip them.
- Whether the trace stores a sanitized adapter-generated summary or only hashes/signals at first.

### Test ideas

- Default Hermes hook path does not record traces.
- Opt-in path records a trace for a representative safe payload.
- Synthetic doctor/test payloads are skipped.
- Trace write failure is swallowed/logged and does not fail the hook.

### Implementation status

- Completed in v0.1.46 via PR #59.
- Added `--record-trace` to `hermes-pre-llm-hook` and to hook snippet/install/bootstrap commands.
- Default Hermes hook path still does not record traces.
- Opt-in hook traces store hash-only turn fingerprints, hashed session refs, safe metadata (`hook_event_name`, `platform`, `model`, `trace_recording`), and related retrieved memory refs.
- Synthetic Hermes doctor/test payloads are skipped even when `--record-trace` is present.
- Trace write failures are swallowed so pre-LLM hook context injection remains non-blocking.
- No default retrieval/ranking changes.

## PR B4: Add trace retention and local-only safety guardrails

### Objective

Add guardrails before trace volume grows.

### Candidate behavior

- Default TTL or retention class for traces.
- Max trace count or budget advisory.
- Read-only expiry report first.
- Optional explicit cleanup command only if scoped and safe; if uncertain, defer mutation to a later PR.

### Test ideas

- Expired traces are identified deterministically.
- Retention report is read-only by default.
- High-volume traces produce a warning without breaking retrieval.
- Approved long-term memories are not deleted by trace retention.

### Acceptance

- Trace layer cannot silently become an infinite local transcript archive.
- Docs explain what is retained, for how long, and how to inspect it.
- The next stage can build activation events on top of bounded trace data.

### Implementation status

- In progress on branch `feat/trace-retention-report`.
- Added `build_trace_retention_report(...)` as a read-only retention guardrail report.
- Added `agent-memory traces retention-report <db>` with `--max-trace-count`, `--expired-limit`, `--missing-expiry-limit`, and test-only/operator `--now` override.
- The report summarizes trace counts by retention policy, expired trace refs, expirable traces missing `expires_at`, volume warnings, and suggested next steps.
- The report intentionally omits trace metadata and summary text; it does not delete traces, promote long-term memories, or alter retrieval/ranking.
