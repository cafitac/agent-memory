# KB-ready M1 implementation plan

> For Hermes: use subagent-driven-development or equivalent task-by-task execution discipline when implementing this plan.

Status: AI-authored draft. M1 export slice implemented locally with tests on 2026-04-29; not yet human-approved or released.

Goal: extend agent-memory from a Hermes-usable memory runtime into a KB-ready memory plane that can ingest raw sources, extract candidate memory, promote approved memory, and render a first KB draft output without making the KB page the storage truth.

Architecture: keep agent-memory as the machine-memory substrate. Add the smallest vertical slice that goes from raw source -> candidate memory -> approved memory -> projected KB draft. Keep Hermes integration thin and avoid adding embeddings or heavy retrieval changes in this milestone.

Tech stack: Python 3.11+, SQLite, Pydantic models, existing `agent-memory` CLI, pytest.

---

## Milestone scope

In scope:
- explicit raw-source ingestion path
- candidate memory model for facts/procedures/entities at minimum
- approval/promotion path
- first KB draft projection output
- tests and docs for the vertical slice

Out of scope for M1:
- embeddings
- graph visualization
- full wiki CMS
- rich web UI
- multi-harness live ingestion beyond existing Hermes-first path
- forgetting/decay automation

## Task 1: Freeze the M1 vertical slice contract

Objective: turn the planning docs into one executable scope statement before changing code.

Files:
- Create: `.dev/kb/kb-m1-scope-freeze.md`
- Reference: `.dev/status/current-handoff.md`
- Reference: `.dev/kb/*.md`

Steps:
1. Summarize the exact M1 input/output path.
2. Name the minimum supported source types for M1.
3. Name the minimum candidate object types for M1.
4. Name the approval surface to support in M1.
5. Name the exact KB draft export shape to support in M1.

Verification:
- a reader can answer "what will be implemented now vs later?" without reading all other docs.

## Task 2: Audit current schema and CLI against the desired M1 flow

Objective: identify the smallest schema and CLI changes required for the vertical slice.

Files:
- Modify: `.dev/kb/kb-m1-scope-freeze.md`
- Reference: `src/agent_memory/storage/schema.sql`
- Reference: `src/agent_memory/storage/sqlite.py`
- Reference: `src/agent_memory/api/cli.py`
- Reference: `tests/test_cli.py`

Steps:
1. List current tables/models/commands that already support source ingestion, candidate creation, approval, and retrieval.
2. List the exact missing pieces.
3. Decide whether to extend existing objects or add new candidate-specific objects.
4. Record the minimum migration needed.

Verification:
- the scope-freeze doc contains an explicit "existing vs missing" section.

## Task 3: Add failing tests for raw source -> candidate extraction

Objective: define the first code slice with tests before implementation.

Files:
- Modify: `tests/test_cli.py`
- Create or modify: `tests/test_kb_pipeline.py`

Test targets:
- ingest a markdown/manual-note source into the DB
- extract at least one candidate fact from that source
- list/retrieve the candidate before approval
- preserve provenance to the source record

Verification command:
- `uv run pytest tests/test_kb_pipeline.py -q`
Expected before implementation:
- failing tests that clearly describe the missing behavior

## Task 4: Implement minimal source ingestion normalization path

Objective: make non-Hermes raw source ingestion explicit and testable.

Files:
- Modify: `src/agent_memory/core/models.py` or the current canonical models module
- Modify: `src/agent_memory/storage/schema.sql`
- Modify: `src/agent_memory/storage/sqlite.py`
- Modify: `src/agent_memory/api/cli.py`

Implementation targets:
- add or formalize a `SourceRecord` create/list path for markdown/manual-note input
- preserve checksum, source_type, created_at, metadata, and scope
- support idempotent-ish ingest behavior where practical

Verification:
- targeted tests for source ingest pass
- existing CLI/regression tests still pass

## Task 5: Add candidate memory objects and extraction interface

Objective: support candidate facts/procedures/entities as reviewable intermediate objects.

Files:
- Modify: `src/agent_memory/core/models.py`
- Modify: `src/agent_memory/storage/schema.sql`
- Modify: `src/agent_memory/storage/sqlite.py`
- Modify: `src/agent_memory/api/cli.py`
- Modify: `tests/test_kb_pipeline.py`

Implementation targets:
- add candidate object schema/state where missing
- add extraction entrypoint for at least one source type
- create provenance links back to `SourceRecord`
- keep extraction interface provider-neutral

Verification:
- new tests prove candidate creation from a raw source
- candidates are queryable and clearly marked as non-approved

## Task 6: Add approval/promotion flow for one memory type first

Objective: prove the review boundary by promoting candidate fact(s) into approved memory.

Files:
- Modify: `src/agent_memory/storage/sqlite.py`
- Modify: `src/agent_memory/api/cli.py`
- Modify: `tests/test_kb_pipeline.py`

Implementation targets:
- support approve-fact for candidate -> approved promotion
- preserve provenance, scope, and status
- avoid silent promotion of everything in a source

Verification:
- targeted tests prove a candidate fact becomes approved memory
- retrieval behavior uses approved memory, not candidate-only memory by default

## Task 7: Add first KB draft export surface

Objective: prove that approved memory can project into a human-facing KB draft without becoming the storage truth.

Files:
- Modify: `src/agent_memory/api/cli.py`
- Create or modify: projection/export module under `src/agent_memory/`
- Modify: `tests/test_kb_pipeline.py`

Implementation targets:
- add a command such as `agent-memory export-kb-draft ...` or equivalent
- support at least one page type, likely a topic/entity/fact summary page
- render summary + key facts + provenance references
- keep export deterministic and testable

Verification:
- tests prove the output contains approved memory only
- tests prove provenance references are included

## Task 8: Add docs sync for the verified M1 behavior

Objective: reflect only implemented and tested behavior into user-visible docs.

Files:
- Modify: `README.md`
- Modify: `.dev/status/current-handoff.md`
- Modify: relevant `.dev/kb/*.md`
- Optionally create later: `docs/` content only after human review

Steps:
1. update the handoff doc with actual implemented status
2. update README only if the CLI surface is real and tested
3. keep speculative future design in `.dev/`

Verification:
- documented commands exactly match tested commands
- no README claim depends on unimplemented behavior

## Task 9: Add retrieval evaluation fixture set for post-M1 comparison

Objective: prepare the next milestone so retrieval complexity is measured, not guessed.

Files:
- Create: `.dev/kb/retrieval-task-set-v0.md`
- Create or modify: `tests/test_kb_retrieval_eval.py`

Implementation targets:
- define 5-10 evaluation prompts
- define expected essential facts/procedures per prompt
- create a harness-friendly artifact format for later comparisons

Verification:
- fixtures exist and can be reused in future retrieval experiments

## Task 10: Run full regression and release-readiness checks

Objective: make sure M1 vertical-slice work does not break the validated Hermes/package path.

Files:
- No new product files required beyond prior tasks

Verification commands:
- `uv run pytest tests/ -q`
- `uv run python scripts/check_release_metadata.py`
- `uv run python scripts/smoke_release_readiness.py`
- `npm pack --dry-run`

Expected:
- full regression passes
- release metadata remains consistent
- bootstrap/doctor/npm launcher still work

---

## Recommended implementation order summary

1. freeze M1 scope
2. audit current schema/CLI
3. write failing KB pipeline tests
4. implement source ingestion
5. implement candidate extraction surface
6. implement approval flow
7. implement KB draft export
8. sync docs to verified behavior
9. add retrieval evaluation fixture set
10. run full regression/release checks

## Commit guidance

Suggested commit grouping:
- `docs: freeze kb-ready m1 scope`
- `test: add failing kb pipeline coverage`
- `feat: add source ingestion path for kb pipeline`
- `feat: add candidate extraction and approval flow`
- `feat: add kb draft export`
- `docs: sync kb-ready handoff and readme`
- `test: add retrieval evaluation fixtures`

## Final note

M1 should prove the data plane, not finish the whole memory OS. If this milestone cleanly demonstrates source -> candidate -> approved memory -> KB draft export while preserving provenance and keeping Hermes thin, the project will be in the right shape for the next real build-out.
