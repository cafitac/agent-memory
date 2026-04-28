# KB architecture v0

Status: AI-authored draft. Not yet human-approved.

## Goal

Define how a human-facing KB should relate to agent-memory without collapsing KB and memory into one system.

## Short answer

The KB should be a layer above the memory runtime, not the runtime itself.

- agent-memory core owns machine-usable memory objects
- KB layer owns human-readable pages, curation views, exports, and browsing
- approved memory objects plus provenance are the shared truth substrate

## System boundary

### Host runtime responsibilities
Examples: Hermes, Codex-like harnesses, Claude-style harnesses, MCP clients.

Owns:
- sessions
- orchestration
- tool execution
- prompt assembly outside memory retrieval
- UI / CLI / gateway behavior

### agent-memory responsibilities
Owns:
- source ingestion
- source normalization
- candidate extraction interfaces
- durable memory objects
- provenance links
- scope and retrieval rules
- approval / deprecation lifecycle
- retrieval packet assembly

### KB layer responsibilities
Owns:
- human-facing page rendering
- topic pages and summaries
- curated wiki navigation
- export jobs / sync jobs
- browse/search UX for humans
- editorial notes beyond machine memory truth

## Truth model

Use a layered truth model:

1. raw source
- transcript
- tool output
- markdown/doc
- web page
- code snapshot
- manual note

2. candidate memory
- extracted but not yet approved
- may include entities, facts, procedures, episodes, relations

3. approved memory
- canonical machine-usable truth for retrieval
- provenance-backed
- status-aware

4. KB projection
- rendered human-facing output derived from approved memory + selected narrative text
- not the authoritative storage truth

The key rule is:
- never make the wiki page itself the only source of machine truth
- never make raw transcript text the only source of KB truth

## Recommended data flow

1. ingest source into `SourceRecord`
2. normalize metadata and assign scope/provenance
3. extract candidate entities/facts/procedures/episodes/relations
4. review or auto-promote according to policy
5. store approved memory objects in core runtime
6. project approved memory into one or more KB page drafts
7. optionally let a human edit the KB narrative layer
8. preserve links back to approved memory and source evidence

## Page model

A future KB page should be a projection, not a primitive.

Suggested page types:
- entity page
- project/repo page
- procedure page
- concept page
- issue/decision page
- topic aggregation page

Suggested page sections:
- summary
- key facts
- active procedures / runbooks
- related entities/concepts
- recent episodes
- evidence / provenance links
- open questions / disputed claims

## Sync direction

Primary sync direction should be:
- memory -> KB draft/export

Optional later direction:
- KB editorial feedback -> candidate memory update proposal

Avoid early bidirectional free-form sync because it will blur authority boundaries too soon.

## Scope/provenance rules

Every KB-renderable unit should preserve:
- source ids
- memory ids
- confidence / status
- scope
- validity window when relevant
- last-reviewed timestamp

Page rendering should be able to hide noisy internals while still keeping auditability available.

## Anti-goals

Do not do these in the first KB milestone:
- make markdown pages the primary memory DB
- build a full wiki CMS inside agent-memory
- require embeddings to ship the KB layer
- require a graph database before the KB layer works
- force human editors to understand raw internal schema details

## Decision

The next milestone should treat KB as a projection and curation layer over approved memory, not as a replacement for memory storage.
