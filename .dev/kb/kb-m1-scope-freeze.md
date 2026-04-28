# KB M1 scope freeze

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-29

## What M1 means

M1 means Milestone 1.

For this project, M1 is not the final knowledge-base product. It is the first complete, testable vertical slice that proves agent-memory can support a KB workflow without becoming Hermes-specific.

The M1 success path is:

1. ingest a raw source
2. create memory candidates from that source
3. approve or reject candidates through an explicit curation step
4. export approved memory into a human-readable KB draft
5. keep Hermes and other harnesses as thin consumers, not owners of the KB

M1 should feel boring and reliable. It should prefer a small end-to-end workflow over clever retrieval, embeddings, UI, or autonomous summarization.

## Product position

agent-memory is the memory runtime / memory plane.

The KB layer is a human-facing curation/export layer on top of that runtime.

This means:

- agent-memory stores source records, candidates, approved memories, provenance, scopes, and retrieval signals.
- KB workflows organize approved memories into readable documents.
- Hermes integration injects relevant memory at prompt time.
- Hermes does not own the KB, mutate the KB, or perform hidden curation.
- Other harnesses should be able to use the same DB and workflow through CLI/library APIs.

## M1 goal

Build the smallest trustworthy KB-ready workflow:

source -> candidate -> approved memory -> KB draft export

This should be usable from CLI first, then library APIs can stabilize around the same behavior.

## M1 non-goals

Do not include these in M1:

- embedding search
- reranking
- vector database dependency
- graph visualization
- web UI
- background daemons
- automatic LLM extraction as the only path
- Hermes-only behavior
- automatic modification of user files without explicit command
- bidirectional wiki sync
- conflict resolution UI
- multi-user server mode

These can come after the data model and workflow are stable.

## M1 accepted memory types

M1 should use the existing memory types first:

- SourceRecord
- Fact
- Procedure
- Episode
- Relation only if needed for provenance or linking, not required for the first vertical slice

Do not introduce a separate generic KBItem table in M1 unless implementation proves the existing model cannot represent the workflow.

Rationale:

- current schema already has source_records, facts, procedures, episodes, relations
- current models already have candidate/approved/disputed/deprecated status
- current retrieval already targets approved facts/procedures/episodes
- adding a new top-level KB entity too early would split the product model

## Source ingestion scope

M1 source ingestion should support:

- plain text content passed directly through CLI
- source_type
- optional adapter
- optional external_ref
- metadata_json
- content checksum deduplication behavior as currently implemented

M1 does not need:

- file crawling
- GitHub issue import
- Slack/Discord import
- PDF parsing
- web scraping
- automatic chunking

Those should be adapters after the core workflow is solid.

## Candidate creation scope

M1 should support explicit/manual candidate creation from an ingested source:

- create fact candidate with evidence_ids including the source id
- create procedure candidate with evidence_ids including the source id
- create episode candidate with source_ids including the source id

Optional convenience commands may be added, but explicit commands must remain available and testable.

M1 does not require automatic extraction from arbitrary source text.

Reason:

Automatic extraction introduces model quality, prompt, and verification problems before the lifecycle is proven.

## Approval/curation scope

M1 should use the existing review lifecycle:

- candidate
- approved
- disputed
- deprecated

M1 must make the curation step explicit.

Approved memory becomes eligible for:

- retrieval
- Hermes prompt-time injection
- KB draft export

Candidate/disputed/deprecated memory should not silently appear as canonical KB content.

## KB draft export scope

M1 should export approved memories to markdown.

Minimum CLI shape:

```bash
agent-memory kb export <db_path> <output_dir> --scope <scope>
```

Possible output:

```text
<output_dir>/index.md
<output_dir>/facts.md
<output_dir>/procedures.md
<output_dir>/episodes.md
```

Exported markdown must include provenance references, at least source ids.

M1 export is one-way only:

DB -> markdown draft

No markdown import/sync in M1.

## Retrieval scope

M1 keeps current retrieval behavior.

Do not block M1 on:

- embeddings
- semantic search
- reranking
- contradiction-aware ranking improvements

M1 only needs to verify that approved memories created by the source/candidate/approval path can be retrieved by existing retrieval APIs.

## Harness boundary

Harness adapters may:

- pass cwd/session metadata
- request memory context
- inject returned context into prompts
- show one-line bootstrap/doctor instructions

Harness adapters must not:

- approve memory automatically
- write KB markdown automatically
- run tool verification directly from memory suggestions
- own the canonical schema
- fork retrieval behavior per harness

## CLI-first M1 surface

Existing commands already covering part of M1:

- init
- ingest-source
- create-fact
- create-procedure
- create-episode
- review approve/dispute/deprecate
- retrieve
- hermes-context
- hermes-bootstrap
- hermes-doctor

Likely new M1 command:

- kb export

Potential convenience commands after the smallest slice:

- kb candidates
- kb approve
- kb draft

But M1 should not add aliases before the core flow is proven.

## M1 acceptance criteria

M1 is done when a test can prove this flow:

1. initialize a fresh SQLite DB
2. ingest a source record
3. create one candidate fact using the source id as evidence
4. approve the candidate fact
5. retrieve the approved fact through existing retrieval
6. export KB markdown
7. exported markdown contains the approved fact and source provenance
8. candidate/disputed/deprecated memories are excluded from canonical export

Additional acceptance criteria:

- no Hermes-specific dependency in the core KB export path
- no new remote service dependency
- no secrets or user-specific paths in docs/tests
- existing Hermes bootstrap/doctor tests still pass
- current npm/PyPI install assumptions remain valid

## Implementation order

1. current schema/CLI audit
2. tests for KB export with existing approved fact/procedure/episode rows
3. implement core markdown exporter as library code
4. add `agent-memory kb export` CLI
5. add vertical-slice test: source -> candidate -> approve -> export
6. update README or docs only after behavior is verified

## Deferred decisions

These are intentionally not decided in M1:

- whether the future KB has a dedicated document graph
- whether markdown becomes editable and syncable back into DB
- whether agent-memory should have a web UI
- whether source ingestion should use LLM extraction by default
- how to score contradictions across long time spans
- how to expose memory-palace-style short/mid/long-term tiers

## Default next action

Start with a current schema/CLI audit, then implement the KB export slice test-first.
