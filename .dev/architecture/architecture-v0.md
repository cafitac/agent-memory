# agent-memory architecture v0

Status: AI-authored draft. Not yet human-approved.

## 1. Goal

Build an open-source memory runtime that makes agents feel like they actually remember.
The north-star is a graph-based memory consolidation system, not a store of only pre-selected "important" notes:
experiences leave lightweight traces, repeated or salient traces strengthen, weak traces decay, and consolidated patterns become explainable long-term memory.
Not just by searching old text, but by:
- retaining important episodes
- extracting durable facts
- maintaining entity/concept relationships
- distinguishing knowledge from behavior
- retrieving the right memory for the current task
- preserving why a memory should be trusted

## 2. Design principles

1. SQLite-first, local-first
   - default install should be simple, cheap, and inspectable
   - users should be able to inspect tables and evidence without vendor lock-in

2. Graph-over-chunks, not chunks-only
   - chunk similarity is useful but insufficient
   - explicit memory objects and explicit relations should be first-class
   - graph edges should also represent reinforcement, decay, consolidation, supersession, and temporal context over time

3. Provenance-first
   - durable memory should point back to evidence
   - the system should preserve the path from claim to source

4. Layered memory
   - different memory types should have different retention and retrieval policies
   - working/short-term traces can be cheap and temporary; long-term memories should emerge through consolidation rather than immediate permanence

5. Harness-agnostic core
   - Hermes, Codex-like, Claude-style, and future runtimes should share the same core

6. Human-auditable
   - users should be able to review, approve, reject, revise, and deprecate memory

7. Hybrid retrieval, not ideology
   - graph should not become dogma
   - lexical, graph, metadata, recency, and optional embeddings should cooperate

## 3. RAG vs memory runtime

RAG usually means:
- store documents/chunks
- embed them
- retrieve semantically similar chunks at query time
- place top-k chunks into the prompt

That is useful, but it is only one retrieval primitive.
It does not automatically give:
- stable entities
- fact conflict resolution
- temporal episodes
- procedural memory
- explicit relations between memories
- forgetting policies
- curation lifecycle
- provenance-aware ranking

Recommended framing:
- RAG = one retrieval primitive
- memory runtime = ingestion + modeling + storage + retrieval + curation + decay + evaluation

## 4. Memory layers

### 4.1 Working memory
Short-lived, active-task context.

Examples:
- current objective
- recent tool outputs
- temporary assumptions
- active constraints

Properties:
- TTL-based
- prompt-adjacent
- easy to evict
- should usually not become durable by default

### 4.2 Episodic memory
Records of what happened in a task, turn, or session.

Examples:
- user requested a release workflow review
- test suite failed because of import mismatch
- deploy succeeded after switching provider config

Properties:
- timestamped
- source-linked to transcripts and tool outputs
- summarizable
- useful for recency-sensitive recall
- only some episodes should yield durable semantic/procedural memory

### 4.3 Semantic memory
Stable facts, concepts, entities, and relationships.

Examples:
- project X uses branch naming pattern EP-###
- Hermes stores sessions in SQLite with FTS5 search
- service A depends on service B for auth callbacks

Properties:
- canonicalized
- deduplicated
- confidence-scored
- relation-rich
- may need contradiction handling and validity intervals

### 4.4 Procedural memory
Reusable action patterns and task rules.

Examples:
- how to run a project's test suite correctly
- how to validate a Hermes hook integration safely
- how to open a PR in a team-specific workflow

Properties:
- action-oriented
- versioned
- reviewable
- can be exported into skills, rules, prompts, or task templates

## 5. Canonical objects

### 5.1 SourceRecord
Raw evidence.

Fields:
- id
- source_type: transcript | tool_output | document | codebase | web | manual_note
- adapter
- external_ref
- created_at
- content
- checksum
- metadata

### 5.2 Episode
A task or event summary grounded in one or more SourceRecords.

Fields:
- id
- title
- summary
- started_at
- ended_at
- participants
- source_ids[]
- tags[]
- importance_score
- status

### 5.3 Entity
People, repos, services, filesystems, projects, providers, environments, orgs.

Fields:
- id
- kind
- name
- aliases[]
- canonical_key
- attributes
- confidence

### 5.4 Concept
Abstract knowledge nodes.

Fields:
- id
- name
- definition
- tags[]
- confidence

### 5.5 Fact
Atomic claim with provenance.

Fields:
- id
- subject_ref
- predicate
- object_ref_or_value
- evidence_ids[]
- confidence
- valid_from
- valid_to
- scope
- status: candidate | approved | disputed | deprecated

### 5.6 Procedure
Reusable action pattern.

Fields:
- id
- name
- trigger_context
- preconditions
- steps
- evidence_ids[]
- success_rate
- scope
- status

### 5.7 Relation
Graph edge between canonical objects.

Fields:
- id
- from_ref
- relation_type
- to_ref
- weight
- evidence_ids[]
- confidence
- valid_from
- valid_to

## 6. Retrieval pipeline

Prompt-time retrieval should be hybrid.

### Stage A: candidate generation
- lexical search over facts, procedures, entities, concepts, and episodes
- metadata filters: adapter, project, user, workspace, scope, recency
- optional embedding similarity over semantic summaries
- graph neighborhood expansion from matched entities/concepts
- optional rule-based boosts for recent success-linked procedures

### Stage B: candidate ranking
- task relevance
- confidence
- recency decay
- successful reuse frequency
- provenance quality
- scope match: user | project | workspace | global
- contradiction penalties
- novelty penalty for redundant near-duplicates

### Stage C: memory assembly
- produce a compact retrieval packet
- separate sections by layer:
  - working hints
  - episodic context
  - semantic facts
  - procedural guidance
- enforce token budgets by section
- include provenance summaries, not just payload text

## 7. Why graph matters

If the user asks about "apple", the system should not only retrieve chunks mentioning the word.
It should reason over connected context, for example:
- apple -> entity(company)
- apple -> concept(fruit)
- apple(company) -> relation -> iphone
- apple(fruit) -> relation -> banana
- banana -> relation -> fruit
- fruit -> relation -> nutrition

Graph structure helps with:
- disambiguation
- relation-based expansion
- provenance clustering
- multi-hop recall
- explanation of why something was recalled

But graph alone is not enough:
- edge extraction can be noisy
- over-connected graphs can create retrieval drift
- some relevant memories are textual and weakly structured

Therefore graph should be central, but not alone.

## 8. Storage strategy

### Phase 1: SQLite only
- normalized relational tables for canonical objects
- FTS5 tables for lexical retrieval
- adjacency tables for graph traversal
- JSON columns for flexible metadata

Why:
- easy local OSS install
- inspectable and debuggable
- enough to validate the data model and retrieval loops

### Phase 2: optional vector sidecar
- sqlite-vec, pgvector, lance, qdrant, or compatible adapter
- embeddings used for candidate generation and reranking
- semantic layer still grounded in canonical objects, not raw chunks alone

### Phase 3: optional cold/archive tiers
- compressed historical episodes
- cheaper long-term retention
- export/import snapshots
- selective replay for offline reprocessing

## 9. Curation lifecycle

Not every observation should become durable memory.

Pipeline:
1. ingest raw source
2. extract candidate episodes, entities, facts, procedures, and relations
3. deduplicate against existing memory graph
4. score for confidence, usefulness, and scope
5. approve automatically or require review depending on policy
6. promote into durable memory
7. revise, dispute, or deprecate when contradicted or stale

Without curation, memory quality collapses into noise.

## 10. Temporal behavior and forgetting

A strong memory system needs both retention and forgetting.

Suggested signals per memory item:
- confidence
- importance
- recency
- reuse_count
- success_rate
- source_count
- contradiction_count

Suggested behaviors:
- repeated successful use strengthens ranking
- stale, low-value items decay
- conflicting facts stay visible but penalized until resolved
- episodic summaries can compress over time into semantic/procedural memory
- archival tier keeps history without polluting prompt-time retrieval

## 11. Harness integration model

### Hermes adapter
Possible integration surfaces:
- memory provider plugin
- shell-hook ingestion path
- local MCP/HTTP retrieval server
- session export/event listener

Hermes should remain the runtime.
agent-memory should remain the memory engine.

### Generic adapter contract
- ingest_event(payload)
- ingest_document(payload)
- retrieve_context(task_prompt, scope)
- write_memory(action)
- search_memory(query)
- review_candidates()
- explain_retrieval(retrieval_id)

## 12. Initial repo layout

```text
agent-memory/
  README.md
  .dev/
    product/
    architecture/
    roadmap/
    research/
  src/agent_memory/
    core/
      models.py
      retrieval.py
      ranking.py
      curation.py
      graph.py
      decay.py
    storage/
      sqlite.py
      schema.sql
    adapters/
      base.py
      hermes.py
    api/
      cli.py
      http.py
  tests/
```

## 13. Recommended first milestone

M1: local semantic/procedural memory engine

Deliverables:
- SQLite schema
- canonical objects: SourceRecord, Episode, Entity, Fact, Procedure, Relation
- FTS retrieval
- basic graph traversal
- simple reranking
- CLI for ingest/search/retrieve
- Hermes adapter stub

Success criteria:
- ingest a session transcript
- extract candidate facts/procedures/entities/episodes
- approve selected items
- retrieve compact, useful memory for a new related task
- demonstrate better recall than transcript search alone

## 14. Evaluation philosophy

Do not evaluate only with retrieval hit rate.
Measure:
- task success uplift
- fewer repeated user corrections
- lower prompt bloat
- precision of recalled facts
- useful procedure reuse rate
- contradiction detection quality
- time-to-useful-context
- quality of retrieval explanations

## 15. Open questions

- how much extraction should happen online vs asynchronously?
- when should graph expansion stop to avoid retrieval drift?
- which memories require explicit human review?
- what should be the default forgetting policy?
- how should procedural memory export into harness-native skills/rules?
- can the system learn relation weights from downstream task success?
