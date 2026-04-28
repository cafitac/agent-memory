# KB M1 current schema and CLI audit

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-29

## Purpose

Audit the current agent-memory implementation against the M1 vertical slice:

source -> candidate -> approved memory -> KB draft export

This document identifies what already exists, what is missing, and the smallest implementation path.

## Current package state

- Python package: `cafitac-agent-memory`
- Current version: `0.1.6`
- CLI entrypoint: `agent-memory = agent_memory.api.cli:main`
- Runtime dependency baseline: Pydantic + SQLite stdlib
- Test runner: pytest through `uv run pytest`
- Published install path already validated in earlier release work

## Current schema coverage

Schema file:

- `src/agent_memory/storage/schema.sql`

Existing tables:

- `source_records`
- `facts`
- `procedures`
- `episodes`
- `relations`
- FTS virtual tables for facts/procedures/episodes

### source_records

Already supports M1 source ingestion:

- id
- source_type
- adapter
- external_ref
- created_at
- content
- checksum unique
- metadata_json

M1 fit: good.

Notes:

- checksum uniqueness already gives deduplication behavior.
- source_records are not currently full-text indexed, but M1 does not require source search.

### facts

Already supports M1 candidate/approved semantic memory:

- subject_ref
- predicate
- object_ref_or_value
- evidence_ids_json
- confidence
- valid_from / valid_to
- scope
- status
- searchable_text
- lifecycle/retrieval metadata

M1 fit: good.

Missing only for KB export:

- no direct markdown rendering function yet.

### procedures

Already supports M1 procedural memory:

- name
- trigger_context
- preconditions_json
- steps_json
- evidence_ids_json
- success_rate
- scope
- status
- searchable_text
- lifecycle/retrieval metadata

M1 fit: good.

Missing only for KB export:

- no direct markdown rendering function yet.

### episodes

Already supports M1 episodic memory:

- title
- summary
- source_ids_json
- tags_json
- importance_score
- scope
- status
- searchable_text
- lifecycle/retrieval metadata

M1 fit: good.

Missing only for KB export:

- no direct markdown rendering function yet.

### relations

Available but not necessary for the smallest M1 vertical slice.

M1 decision:

- do not require relation export in the first implementation.
- keep relation support as future enrichment.

## Current model coverage

Model file:

- `src/agent_memory/core/models.py`

Existing Pydantic models:

- SourceRecord
- Fact
- Procedure
- Episode
- Relation
- ProvenanceSummary
- RetrievalTraceEntry
- MemoryTrustSummary
- PolicyHint
- DecisionSummary
- VerificationPlan
- MemoryPacket

M1 fit: good.

Important observation:

- The project already follows the desired Pydantic-model style.
- No need to introduce ad-hoc dict/list based KB records for M1.

Potential M1 addition:

- `KbExportResult`
- `KbExportedFile`

These should be Pydantic models if export code returns structured results.

## Current ingestion coverage

File:

- `src/agent_memory/core/ingestion.py`

Current API:

- `ingest_source_text(...) -> SourceRecord`

Current CLI:

- `agent-memory ingest-source <db_path> <source_type> <content>`
- optional `--metadata-json`
- optional `--adapter`
- optional `--external-ref`

M1 fit: good.

No immediate schema change needed.

## Current curation coverage

File:

- `src/agent_memory/core/curation.py`

Current APIs:

- `create_candidate_fact`
- `create_candidate_procedure`
- `create_episode`
- `create_relation`
- `approve_fact`
- `approve_procedure`
- `approve_memory`
- `dispute_memory`
- `deprecate_memory`

Current CLI:

- `create-fact`
- `approve-fact`
- `list-candidate-facts`
- `create-procedure`
- `approve-procedure`
- `list-candidate-procedures`
- `create-episode`
- `list-candidate-episodes`
- `review approve|dispute|deprecate`

M1 fit: mostly good.

Minor issue:

- fact/procedure have dedicated approve commands.
- episode approval is available through generic `review approve episode`, not a dedicated `approve-episode` command.
- This is acceptable for M1; avoid adding aliases until the export path is proven.

## Current retrieval coverage

Files:

- `src/agent_memory/core/retrieval.py`
- `src/agent_memory/storage/sqlite.py`

Current behavior:

- retrieves approved facts/procedures/episodes
- ranks by lexical/scope/relation/reinforcement-ish signals
- records retrieval metadata
- returns MemoryPacket

M1 fit: good.

M1 should not change retrieval unless a test exposes a real issue.

## Current Hermes boundary coverage

Current CLI:

- `hermes-context`
- `hermes-pre-llm-hook`
- `hermes-hook-config-snippet`
- `hermes-install-hook`
- `hermes-bootstrap`
- `hermes-doctor`

M1 fit: good.

Boundary decision:

- KB export must not depend on Hermes integration.
- Hermes continues to consume retrieval context only.

## Current test coverage relevant to M1

Existing test files include:

- `tests/test_memory_flow.py`
- `tests/test_procedure_and_relation_flow.py`
- `tests/test_episode_review_and_provenance.py`
- `tests/test_cli.py`
- `tests/test_cli_review_and_scope.py`
- `tests/test_retrieval_trace.py`
- `tests/test_hermes_adapter.py`

M1 test gap:

- no KB export tests
- no markdown rendering tests
- no CLI `kb export` tests
- no vertical-slice source -> candidate -> approve -> export test

## Current CLI gap

Current CLI has no `kb` command group.

Observed help output includes:

- init
- ingest-source
- create-fact
- approve-fact
- list-candidate-facts
- create-procedure
- approve-procedure
- list-candidate-procedures
- create-episode
- list-candidate-episodes
- review
- retrieve
- hermes-* commands

Missing for M1:

- `agent-memory kb export <db_path> <output_dir> [--scope <scope>]`

## Recommended M1 implementation shape

Add new module:

- `src/agent_memory/core/kb_export.py`

Suggested Pydantic models, likely in `core/models.py` or a KB-specific module:

- `KbExportedFile`
  - path: str
  - memory_type: str
  - item_count: int
- `KbExportResult`
  - output_dir: str
  - scope: str | None
  - files: list[KbExportedFile]

Suggested core function:

```python
def export_kb_markdown(
    db_path: Path | str,
    output_dir: Path | str,
    *,
    scope: str | None = None,
) -> KbExportResult:
    ...
```

Suggested CLI:

```bash
agent-memory kb export <db_path> <output_dir> --scope user:default
```

Output files:

- `index.md`
- `facts.md`
- `procedures.md`
- `episodes.md`

Export rules:

- include approved memories only
- filter by scope when provided
- include source/evidence ids
- deterministic ordering
- no hidden network calls
- create output directory if missing
- overwrite generated files deterministically

## Required storage helpers

Current storage layer has list-candidate helpers and ranked approved search. KB export should not need query-based retrieval.

Add simple list helpers for approved rows:

- `list_approved_facts(db_path, scope=None) -> list[Fact]`
- `list_approved_procedures(db_path, scope=None) -> list[Procedure]`
- `list_approved_episodes(db_path, scope=None) -> list[Episode]`

Alternative:

- generic `list_memories_by_status(...)`

Recommendation for M1:

- add explicit helpers first for clarity and low risk.

## Test-first implementation plan

1. Add failing unit test for `export_kb_markdown` with an approved fact.
2. Add implementation that writes `index.md` and `facts.md`.
3. Expand test for procedures and episodes.
4. Add test proving candidate/disputed/deprecated rows are excluded.
5. Add CLI test for `agent-memory kb export`.
6. Add vertical-slice test:
   - init DB
   - ingest source
   - create fact candidate with evidence source id
   - approve fact
   - export KB
   - assert markdown contains fact and source id
7. Run full pytest.
8. Update README/docs only after tests pass.

## Risk assessment

Low risk:

- add exporter module
- add CLI subcommand group
- add read-only storage list helpers
- write deterministic markdown files

Medium risk:

- changing existing retrieval code
- changing schema status semantics
- changing Hermes hook behavior

Avoid in M1:

- schema rewrite
- automatic extraction
- embeddings
- bidirectional sync

## Conclusion

The current agent-memory codebase is already close to KB-ready M1.

Most of the foundational pieces exist:

- source ingestion
- candidate memory creation
- explicit approval lifecycle
- approved-only retrieval
- Hermes thin consumption boundary

The main missing piece is a deterministic KB export path and its CLI/test coverage.

Recommended next implementation task:

- review the local KB export implementation and decide whether to commit it as the M1 export slice
- after commit, consider expanding M1 with source-aware export excerpts or richer provenance rendering
