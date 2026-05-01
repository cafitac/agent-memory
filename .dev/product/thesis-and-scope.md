# agent-memory thesis and scope

Status: AI-authored draft. Not yet human-approved.

## Product thesis

agent-memory should be a reusable memory runtime for AI agents, not just a transcript archive and not just a vector-search wrapper.

The strongest version of the project should not merely save important notes.
It should behave like a safe, inspectable approximation of memory consolidation:
conversation and runtime experiences leave lightweight traces; repetition, salience, recency, graph connectivity, and demonstrated usefulness strengthen some traces; weak traces decay; strong trace clusters consolidate into long-term semantic, episodic, procedural, and preference memory.

The strongest version of the project should make people say:
- it remembers the right thing
- it forgets the wrong thing
- it can explain why a memory was recalled
- it links related memories instead of dumping disconnected chunks
- it improves future behavior without exploding prompt size

## Problem statement

Today, many agent systems confuse these layers:
- session logs
- durable user/profile memory
- domain knowledge / KB
- procedural know-how
- temporary task context

When those are collapsed into one store, the system usually becomes one of:
- a noisy transcript search engine
- an opaque vector DB with weak provenance
- a prompt stuffing mechanism
- an uncurated notes pile

## Positioning

agent-memory should sit between the host runtime and durable knowledge.

Host runtime responsibilities:
- conversation loop
- tool execution
- sessions
- orchestration
- UI / gateway

agent-memory responsibilities:
- ingesting raw evidence from runtimes and external sources
- turning evidence into usable memory objects
- preserving provenance and confidence
- retrieving compact, task-fit memory packets
- managing memory lifecycles and decay
- supporting review, promotion, revision, and deprecation

## Core design commitments

1. Harness-agnostic
   - Hermes should not be the only target.
   - Codex-like, Claude-style, and generic MCP/HTTP harnesses should also work.

2. Memory is layered
   - working memory
   - episodic memory
   - semantic memory
   - procedural memory

3. Memory is evidence-backed
   - every durable claim should point to source records
   - every important retrieval should be explainable

4. Memory is curated through consolidation, not pre-filtered at birth
   - not every observation becomes durable memory
   - low-cost traces may be recorded before their long-term value is known
   - repetition, salience, usefulness, and graph connectivity should decide what strengthens or decays
   - the system needs candidate, approval, dispute, and deprecation states

5. Memory is connected
   - memories should form a graph of entities, concepts, facts, episodes, and procedures

6. Memory is inspectable
   - users should be able to audit the graph, evidence, and retrieval outputs

## Non-goals

- replacing host-agent session storage
- becoming a generic wiki/document CMS
- requiring embeddings or a heavyweight graph DB on day one
- treating all retrieved text as equally trustworthy
- pretending graph structure alone solves memory quality

## Success criteria

A strong MVP should be able to:
- ingest a session transcript or event stream
- extract candidate episodes, facts, entities, and procedures
- preserve provenance to source records
- approve selected memories into durable storage
- retrieve a compact memory packet for a new related task
- outperform transcript search alone on relevance and prompt efficiency

## Scope boundary with knowledge bases

A human-facing KB can exist beside agent-memory, but should not define the core data plane.

Preferred relationship:
- agent-memory owns structured, machine-usable memory
- external KB/wiki tools own narrative, human-facing documentation
- interoperability should happen via references, exports, or sync jobs, not by collapsing both systems into one lifecycle
