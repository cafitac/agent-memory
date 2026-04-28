# Source ingestion v0

Status: AI-authored draft. Not yet human-approved.

## Goal

Define the canonical ingestion path from raw external inputs into candidate memory objects.

## Supported source classes

Phase-1 source classes:
- transcript / session log
- tool output
- markdown / plain text note
- web page capture
- codebase snapshot or selected files
- manual note / operator annotation

Phase-later source classes:
- issue/PR metadata
- CI/build logs
- API/event streams
- external KB documents
- structured CSV/JSON imports

## Canonical ingestion pipeline

1. source registration
- assign `SourceRecord`
- compute checksum
- store adapter/source_type/external_ref/metadata

2. normalization
- normalize timestamps
- normalize source labels
- normalize project/user/scope metadata
- segment large sources into reviewable evidence spans when needed

3. extraction
- identify candidate episodes
- identify candidate entities/concepts
- identify candidate facts
- identify candidate procedures
- identify candidate relations

4. dedup / merge hints
- detect obvious duplicate entities/facts
- attach candidate-to-canonical merge suggestions
- avoid silent destructive merges in early versions

5. review queue creation
- emit candidate records into human/audit review flows
- allow future policy-based auto-promotion only for narrow trusted cases

## SourceRecord requirements

Each source should capture at least:
- source_type
- adapter
- external_ref
- content
- checksum
- created_at
- metadata
- preferred scope or inferred scope

Important metadata examples:
- harness name
- repo identifier
- file path or URL when safe
- session/task identifiers
- user or workspace hints
- capture timestamp

## Extraction policy by source type

### transcript / session log
Good at extracting:
- episodes
- user preferences
- stable facts when repeated or explicit
- procedures that were actually executed and verified

Risk:
- over-promoting temporary statements into durable truth

### tool output
Good at extracting:
- verified technical facts
- execution outcomes
- failure reasons
- version/command evidence

Risk:
- environment-specific facts that should remain scope-limited

### markdown / plain text note
Good at extracting:
- curated knowledge
- design intent
- decisions
- procedure drafts

Risk:
- stale statements with weak time validity

### web page
Good at extracting:
- external facts
- release notes
- package docs
- public KB inputs

Risk:
- provenance drift when pages change

### codebase snapshot
Good at extracting:
- config facts
- architecture relationships
- procedure hints from scripts/workflows
- file/repo entities

Risk:
- over-claiming runtime behavior from static code alone

## Idempotency rules

Ingestion should be idempotent at the source level when possible.

Minimum rules:
- same checksum + same source_type + same adapter should not create duplicate raw source rows without explicit override
- re-ingestion may create a new observation event if metadata materially changed
- candidate extraction should preserve source linkage and avoid duplicating the exact same candidate text blindly

## Early extraction contract

The extraction layer should not hardcode one model/provider.

Suggested contract:
- input: normalized source payload + extraction mode + scope metadata
- output: candidate objects with confidence, evidence spans, and extraction rationale

Output classes should include:
- `CandidateEpisode`
- `CandidateEntity`
- `CandidateConcept`
- `CandidateFact`
- `CandidateProcedure`
- `CandidateRelation`

## Safety rules

- extraction is suggestion, not truth
- confidence must not imply approval
- every durable claim must retain a path back to raw evidence
- code/web/document ingestion should preserve source location metadata where safe
- privacy-sensitive local paths should be hashed or scoped the same way current Hermes integration hashes cwd

## Minimum CLI surfaces for the next code slice

Potential commands:
- `agent-memory ingest-source <db> <path-or-ref> --source-type ...`
- `agent-memory list-sources <db>`
- `agent-memory extract-candidates <db> --source-id ...`
- `agent-memory list-candidates <db> --status pending`

The exact CLI names can change, but the workflow should exist explicitly.

## Decision

The ingestion pipeline should treat all inputs as raw evidence first, then produce candidate memory objects second. That keeps memory explainable and prevents KB ambitions from bypassing provenance.
