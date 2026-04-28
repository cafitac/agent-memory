# Harness boundary v0

Status: AI-authored draft. Not yet human-approved.

## Goal

Keep agent-memory reusable across harnesses by making adapter responsibilities explicit.

## Core boundary

### Host harness should own
- conversation loop
- session persistence
- tool execution
- orchestration
- permissions/consent model
- UI rendering
- final prompt assembly outside memory injection

### agent-memory should own
- source ingestion interfaces
- memory object schema
- provenance
- candidate extraction contracts
- review/promotion lifecycle
- retrieval ranking and packet assembly
- scope logic
- memory/KB projection logic

## Hermes boundary

Hermes should:
- provide hook payloads / session context
- optionally call bootstrap/install surfaces
- consume prompt-time retrieval packet text or JSON
- optionally send verification result objects back into agent-memory flows

agent-memory should:
- read Hermes payloads
- derive preferred scope when needed
- retrieve compact memory packet
- return prompt-time context only
- avoid taking over Hermes session storage or tool execution

Important rule:
- Hermes integration stays thin
- no hidden orchestration logic should move into the memory adapter layer

## Future Codex-like / Claude-style boundary

Future adapters should follow the same pattern:
- adapter transforms harness-native payload -> agent-memory retrieval request
- agent-memory returns retrieval packet / memory context
- harness decides how to inject/display/use it

Do not let each adapter redefine memory semantics.

## Ingestion boundary

There are two acceptable ingestion patterns:

1. synchronous lightweight ingestion
- harness emits selected session/tool events into agent-memory directly
- good for local-first simple setups

2. asynchronous export/import ingestion
- harness exports session/event artifacts
- agent-memory ingests them later via CLI/service path
- good for heavier or multi-runtime setups

Both are valid. The memory model should not depend on only one of them.

## Service boundary

Long-term delivery options may include:
- local CLI calls
- local HTTP service
- MCP retrieval service
- offline batch ingestion worker

The important thing is not transport choice.
The important thing is keeping the core contracts stable:
- ingest raw source
- extract candidates
- review/promote memory
- retrieve packet
- optionally project KB draft output

## Anti-patterns to avoid

- making Hermes-specific hook payloads part of the core domain model
- forcing every harness to use the same session storage format
- letting adapter code mutate durable memory semantics ad hoc
- mixing tool execution verification and memory retrieval in one opaque step
- hiding scope decisions inside one harness-specific integration path

## Recommended interface mindset

Adapters should be thin translators.
Core runtime should be the only place where memory semantics become truth.

That means future work should prefer:
- common request/response types
- harness-specific translators
- shared tests for adapter contract compliance

## Decision

The next milestone should preserve the current Hermes-thin stance and generalize the underlying contracts, not the other way around.
