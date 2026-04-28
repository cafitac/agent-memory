# agent-memory roadmap v0

Status: AI-authored draft. Not yet human-approved.

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
