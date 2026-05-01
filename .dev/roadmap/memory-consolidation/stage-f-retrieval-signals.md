# Stage F: Retrieval Signals

Status: AI-authored draft. Not yet human-approved.

## Goal

Use consolidation signals to improve retrieval only after they are visible and trusted. This stage must be conservative: explanations first, opt-in ranking changes second, default changes only after measured success.

## Stage exit criteria

- Retrieval explanations show activation/reinforcement/decay metadata.
- Opt-in rankers can use reinforcement and decay risk.
- Graph neighborhood reinforcement is bounded and measured.
- Default retrieval remains safe until eval and Hermes E2E justify changes.

## PR F1: Add activation/reinforcement metadata to retrieval explanations

### Objective

Expose signal metadata without changing ranking.

### Acceptance

- Retrieval output remains backwards-compatible or clearly versioned.
- Approved-only behavior and deprecated exclusion remain covered by tests.
- Users can see why a memory was selected.

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
