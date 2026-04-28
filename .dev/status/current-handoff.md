# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-29

## 1. Executive summary

agent-memory is no longer a raw idea. It is now a published, installable, Hermes-usable memory runtime with a working onboarding path:
- npm package: `@cafitac/agent-memory`
- PyPI package: `cafitac-agent-memory`
- latest validated release: `v0.1.5`
- one-line UX: `agent-memory bootstrap` + `agent-memory doctor`

What is complete today:
- SQLite-first local runtime
- global user-level DB default
- privacy-preserving `cwd:<hash>` scope derivation for Hermes hook use
- Hermes hook installer with structured merge behavior
- Hermes bootstrap and doctor commands
- npm thin launcher over Python runtime
- GitHub Actions CI/publish workflow
- published install smoke validated on npm / pipx / uv tool
- repo-local cafitac SSH/author setup for active OSS repos

What is not complete today:
- KB-grade ingestion and curation workflow
- hybrid retrieval with optional embeddings and measured reranking
- memory lifecycle features like decay / archival / consolidation
- benchmark harness proving retrieval quality improvements
- multi-harness adapters beyond the current Hermes-first practical path

Bottom line:
agent-memory has crossed from "concept" into "usable runtime v0", but it has not yet crossed into the stronger goal: a reusable memory OS / KB-capable memory plane for multiple harnesses.

## 2. Current product position

The right framing is:
- Hermes session storage is not the same thing as agent-memory
- session logs are raw evidence, not durable memory by themselves
- a KB is also not identical to raw memory storage

Recommended separation:
- host runtime (Hermes, Codex-like, Claude-style) owns sessions, orchestration, tools, UI
- agent-memory owns machine-usable memory objects, retrieval, provenance, scope, lifecycle, and review
- KB/wiki layer owns human-facing curated explanations and narrative documentation

So the target architecture is not:
- "put KB directly inside Hermes"

The target architecture is:
- "make agent-memory the reusable memory runtime"
- "let KB capabilities sit above or beside that runtime as a curation/export/sync layer"

## 3. What has already been proven

### 3.1 Runtime / packaging / distribution
- dual distribution works in practice
- npm is a thin onboarding surface, not the canonical runtime
- PyPI remains the canonical Python package/runtime
- release metadata sync and publish verification exist
- GitHub Releases and package publishes are real, not aspirational

### 3.2 Hermes integration
- `hermes-bootstrap` works as the shortest setup path
- `hermes-doctor` works as read-only verification
- existing Hermes `hooks:` and `pre_llm_call:` config can be merged safely in normal cases
- missing DB can be auto-initialized during bootstrap/install flow
- prompt-time memory injection works as a thin adapter layer

### 3.3 Storage / scope model
- one global user DB is the default posture
- `user:default` is the durable default scope
- `cwd:<hash>` gives project/folder-sensitive retrieval without leaking raw paths
- project/workspace scopes remain available as explicit narrowing tools

### 3.4 OSS posture
- README is npm-first for onboarding
- user-specific example paths and metadata were scrubbed from public docs/examples
- release workflows are in place and validated

## 4. What is still missing relative to the original ambition

The original ambition is stronger than "remember a little context in Hermes". The bigger target is something like:
- reusable memory runtime
- explainable retrieval
- layered memory systems
- long-term semantic + procedural accumulation
- optional KB sync/export surface
- reusable across multiple agent harnesses

The biggest missing capabilities are:

### 4.1 KB-grade ingestion
Today agent-memory can serve as a memory runtime, but it does not yet have a first-class KB pipeline for:
- source ingestion from notes/docs/transcripts/web/code
- extracting candidate facts/entities/procedures from those sources
- reviewing/promoting/deprecating them at scale
- generating durable, human-curated KB outputs from approved machine memory

### 4.2 Retrieval maturity
Current retrieval is useful, but the long-term target still needs:
- better lexical + graph + metadata composition
- optional embedding candidate generation
- contradiction-aware ranking
- richer retrieval explanation packets
- measured evaluation against transcript grep / lexical-only baselines

### 4.3 Memory lifecycle maturity
Still missing or immature:
- decay / forgetting
- archival tiers
- consolidation from episodic -> semantic/procedural memory
- validity windows and historical truth handling
- procedural success/failure learning loops

### 4.4 Harness-generalization
Hermes is the best validated integration path today, but the broader target still needs:
- cleaner runtime-neutral adapter interfaces
- non-Hermes ingestion/retrieval contracts
- testable adapter boundaries for Codex-like / Claude-style / generic MCP harnesses

## 5. Recommended next goal

## Goal: make agent-memory "KB-ready" without collapsing memory and KB into the same thing

This is the most important next milestone because it matches the original intent:
- not just session recall
- not just hook-time context injection
- not just transcript storage
- but a reusable runtime that can power a KB layer

The design stance should be:
- agent-memory core = machine memory plane
- KB layer = human-facing curation / sync / export / browse layer
- shared truth = approved structured memory objects + provenance

That lets Hermes and other harnesses consume the same memory runtime, while future KB tooling can read from the same approved memory substrate.

## 6. Concrete next milestone

## Milestone M1: KB-ready memory plane

Success criteria:
- define the boundary between raw source, candidate memory, approved memory, and KB export
- define the canonical ingestion flow for docs/transcripts/notes/code/web inputs
- define how approved memory can be rendered into human-facing KB pages without making KB the storage truth
- define the evaluation loop for memory extraction quality and retrieval usefulness
- keep Hermes adapter thin during all of this

Deliverables:
1. KB architecture/status doc
2. ingestion pipeline plan
3. curation/review workflow plan
4. retrieval evaluation plan
5. adapter boundary note for Hermes vs future harnesses

## 7. Proposed document set for the next phase

The next-phase KB planning set now exists under `.dev/kb/`:

1. `.dev/kb/kb-architecture-v0.md`
- memory vs KB boundary
- truth source
- export/sync directions
- scope/provenance rules

2. `.dev/kb/source-ingestion-v0.md`
- supported source classes
- normalization model
- source-to-candidate extraction stages
- idempotency/dedup strategy

3. `.dev/kb/curation-and-promotion-v0.md`
- candidate -> approved -> deprecated workflow
- review queues
- human approval points
- contradiction handling

4. `.dev/kb/retrieval-evaluation-v0.md`
- baseline tasks
- lexical vs graph vs hybrid comparisons
- prompt budget metrics
- explanation quality metrics

5. `.dev/kb/harness-boundary-v0.md`
- what Hermes should do
- what agent-memory should do
- what future Codex/Claude/MCP adapters should do

## 8. Recommended implementation order after the docs

### Phase A: planning/docs first
1. write the `.dev/kb/` design set
2. decide the machine-memory vs KB sync contract
3. freeze milestone M1 scope

### Phase B: smallest code slice for KB readiness
1. add explicit source ingestion model if current one is too transcript-centric
2. add candidate extraction interfaces for facts/entities/procedures
3. add review/promotion CLI surfaces if missing
4. add export shape for a human-facing KB page draft
5. add tests proving approved memory can generate stable KB-ready outputs

### Phase C: evaluation before overbuilding
1. define 5-10 retrieval tasks
2. compare transcript search vs current retrieval vs next retrieval
3. measure token budget and explanation usefulness
4. only then decide whether embeddings are worth adding immediately

## 9. Important decisions to keep

Keep these decisions unless a later document explicitly overturns them:
- SQLite-first, local-first remains the default
- one global user DB remains the default posture
- `user:default` remains the durable baseline scope
- `cwd:<hash>` remains the privacy-preserving project-sensitive retrieval fallback
- Hermes adapter remains thin and prompt-time only
- KB should not replace the memory runtime data plane
- npm remains the shortest onboarding path; PyPI remains canonical runtime distribution

## 10. Current repo reality check

Current known repo state at time of this handoff:
- release posture is validated through `v0.1.5`
- working tree may contain local doc edits outside this handoff document; check `git status --short --branch` before release or tagging work
- this document should become the single up-to-date planning handoff for the next phase instead of scattering status across chat memory

## 11. Immediate next action

Next recommended action in this repo:
- use `.dev/kb/kb-m1-implementation-plan.md` as the execution handoff
- start with the smallest vertical slice: source -> candidate -> approval -> KB draft export
- keep all behavior changes test-first and preserve the already-validated Hermes bootstrap/doctor path

That is the cleanest continuation because it turns the current design set into an execution-ready milestone without prematurely committing to unnecessary retrieval complexity.
