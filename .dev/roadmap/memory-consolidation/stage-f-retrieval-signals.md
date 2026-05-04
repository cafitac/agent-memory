# Stage F: Retrieval Signals

Status: AI-authored draft. Not yet human-approved.

## Goal

Use consolidation signals to improve retrieval only after they are visible and trusted. This stage must be conservative: explanations first, opt-in ranking changes second, default changes only after measured success.

## Stage exit criteria

- Retrieval explanations show activation/reinforcement/decay metadata.
- Opt-in rankers can use reinforcement and decay risk.
- Graph neighborhood reinforcement is bounded and measured.
- Default retrieval remains safe until eval and Hermes E2E justify changes.

## PR F1: Read-only retrieval policy preview

### Objective

Expose lifecycle/retrieval policy decisions without changing default ranking, prompt injection, or memory state.

### Acceptance

- `agent-memory retrieval policy-preview <db> <query>` returns versioned/read-only JSON with `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`.
- The command uses current approved-only retrieval with `record_retrievals=false`; it does not create observations, increment retrieval counters, or mutate facts/relations.
- Output omits raw query text, query previews, prompts, transcripts, raw trace metadata, and secrets; it only exposes a non-stored query hash marker.
- Per-memory projections explain score components, activation/retrieval counts, same-claim-slot conflict counts, reviewed conflict relations, supersession/replacement chains, and advisory decisions (`include`, `flag_for_review`, or `exclude`).
- Existing `retrieve` behavior remains unchanged and covered by tests.

## PR F2: Use reinforcement as a small ranking feature behind opt-in

### Objective

Test whether repeated/useful memories rank better without overwhelming lexical/scope relevance.

### Acceptance

- Default ranking unchanged.
- Opt-in eval compares baseline vs reinforced ranking.
- No precision regression on target fixtures.

## PR F3: Use decay risk as a prompt-time noise penalty behind opt-in

### Objective

Reduce stale/noisy injections while protecting old but salient memories.

### Acceptance

- Default ranking unchanged.
- High-salience or strongly connected old memories can still rank.
- Deprecated/superseded facts remain excluded.
- Hermes local QA marker remains retrievable in E2E.

## PR F4: Add bounded graph neighborhood reinforcement

### Objective

Let graph connectivity help retrieval without becoming graph-only search.

### Acceptance

- Max depth and drift controls exist.
- Graph+lexical beats lexical-only on target fixtures.
- Explanations identify graph edges used.
- Optional embeddings remain optional.
