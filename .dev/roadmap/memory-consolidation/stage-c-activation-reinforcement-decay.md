# Stage C: Activation, Reinforcement, and Decay Signals

Status: AI-authored draft. Not yet human-approved.

## Goal

Turn traces and retrieval observations into measurable signals. This stage still avoids mutation: it explains which memories are repeatedly used, which traces are gaining strength, and which memories/traces look weak or stale.

## Stage exit criteria

- Activation events exist or existing observations can be bridged into activation reports.
- Read-only reports show repeated use, windows, scopes, surfaces, and status history.
- Reinforcement and decay scores are explainable and deterministic.
- Retrieval ranking is not changed yet.

## Core distinction

- Trace: something happened.
- Observation: retrieval selected or did not select memory.
- Activation: a memory/trace was used, surfaced, reinforced, or found relevant in context.
- Reinforcement score: evidence that a memory/cluster should become stronger.
- Decay risk: evidence that a trace/memory may be weak, stale, noisy, or no longer useful.

## PR C1: Introduce activation events for retrieval use

### Objective

Add the concept of activation without changing prompt-time retrieval ranking.

### Likely files

- `src/agent_memory/core/models.py`
- `src/agent_memory/storage/sqlite.py`
- `src/agent_memory/core/retrieval.py`
- `tests/test_retrieval.py`, `tests/test_cli.py`, or new activation tests

### Design options

1. New `memory_activations` table.
2. A compatibility view/report that treats `retrieval_observations.selected_memory_refs` as activations.
3. Hybrid: new table for future events plus bridge from observations.

Prefer the simplest path that keeps v0.1.41 observation output compatible.

### Acceptance

- Existing observation commands keep their output contract.
- Activation events are local-only and secret-safe.
- No retrieval ranking change.
- Empty retrievals can still be represented as useful negative evidence.

## PR C2: Add read-only activation summary CLI

### Objective

Show which memory refs are repeatedly activated and where activation is sparse or noisy.

### Candidate CLI

```bash
agent-memory activations summary <db> --limit 200 --top 20 --output-json
```

or, if reusing observation namespace is cleaner:

```bash
agent-memory observations activation-summary <db> --limit 200 --top 20
```

### Output should include

- kind
- read_only: true
- activation_count
- observation/trace windows
- top refs
- status summary for refs
- surfaces/scopes
- empty or negative evidence summary
- suggested next read-only commands

### Acceptance

- No raw query text.
- Deprecated/superseded refs are flagged, not silently used.
- Approved high-activation refs are visible as likely reinforcement candidates.

## PR C3: Add reinforcement score calculation as read-only report

### Objective

Compute a transparent score that approximates "this memory or cluster is becoming stronger".

### Candidate factors

- repetition count
- recency window
- user emphasis/explicit remember intent when available
- graph connectivity
- retrieval usefulness or repeated selection
- status trust, e.g. approved vs candidate vs deprecated
- conflict/supersession penalty

### Output requirements

Every score must show factor breakdown. Avoid black-box scores that cannot be explained to a user.

### Acceptance

- Deterministic tests for factor weights.
- Score is bounded and explainable.
- Score does not mutate status and does not alter retrieval ranking.

## PR C4: Add decay risk score calculation as read-only report

### Objective

Identify traces/memories that look weak, stale, low-use, low-connectivity, or noisy.

### Important nuance

Old does not mean useless. A memory can be old and still strong if it is highly salient, explicitly approved, or strongly connected. Decay should be about weak activation/connectivity/usefulness, not time alone.

### Acceptance

- Decay report is advisory only.
- Approved/high-salience/strongly connected memories are protected from naive age-only recommendations.
- Report suggests review commands rather than deleting or deprecating anything.
