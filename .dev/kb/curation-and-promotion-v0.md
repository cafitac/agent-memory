# Curation and promotion v0

Status: AI-authored draft. Not yet human-approved.

## Goal

Define how extracted candidates become approved durable memory, and how approved memory later becomes deprecated or revised.

## Lifecycle states

Recommended minimum states:
- candidate
- approved
- disputed
- deprecated

Optional later states:
- archived
- superseded
- auto-approved
- blocked

## Core rule

Not every extracted observation should become durable memory.

That means:
- raw source != approved truth
- candidate != approved truth
- KB page text != approved truth

Approved memory should be deliberate and auditable.

## Review queue model

Suggested review queues:

1. fact review queue
- stable factual claims
- needs contradiction checks

2. procedure review queue
- reusable action patterns
- should prefer evidence from verified successful runs

3. entity/concept merge queue
- canonicalization and alias cleanup

4. dispute queue
- conflicts between old and new claims
- stale or scope-misaligned truth

## Promotion rules

### Candidate -> approved
Require at least:
- provenance exists
- scope is assigned
- canonical object references are valid enough
- confidence passes a threshold or a human approves
- no unresolved higher-priority contradiction blocks promotion

### Approved -> disputed
Trigger when:
- a newer candidate conflicts materially
- evidence quality is challenged
- scope mismatch is discovered
- historical validity is uncertain

### Approved/disputed -> deprecated
Trigger when:
- claim is no longer valid
- procedure is obsolete
- relation was based on superseded architecture or policy

## Contradiction handling

Need explicit handling for statements like:
- "project uses X" vs "project migrated to Y"
- "run tests with A" vs "A is deprecated, use B"
- "repo owner is C" vs "repo moved to D"

Recommended behavior:
- prefer validity windows over deleting history
- preserve old claims as historical unless they were simply wrong/noisy
- attach contradiction links or supersession links
- penalize disputed/deprecated memory at retrieval time

## Human approval policy

First milestone should stay conservative.

Recommended policy:
- facts: human review by default
- procedures: human review by default
- entities/concepts: allow merge suggestions but not silent irreversible merges
- episodes: can often be stored automatically if clearly labeled as episodic observations rather than durable semantic truth

## KB projection policy

Only approved or explicitly allowed disputed-with-warning memory should feed KB drafts.

Do not render candidate-only memory into official KB outputs by default.

Suggested page labeling:
- approved fact
- historical fact
- disputed fact
- recommended procedure
- deprecated procedure

## Review UX requirements

The system eventually needs at least a minimal review surface with:
- list pending candidates
- inspect evidence
- approve / reject / deprecate
- attach rationale
- merge into canonical entity when applicable
- mark validity windows

CLI-first is fine for now if it is explicit and testable.

## Suggested next CLI surfaces

Potential commands:
- `agent-memory review list <db> --type fact --status candidate`
- `agent-memory approve-fact <db> <candidate-or-id> ...`
- `agent-memory approve-procedure <db> <candidate-or-id> ...`
- `agent-memory deprecate-fact <db> <id> --reason ...`
- `agent-memory dispute-fact <db> <id> --reason ...`

## Metrics to track

For curation quality, track:
- candidate volume per source type
- approval rate
- rejection rate
- dispute rate
- duplicate/merge rate
- later deprecation rate
- retrieval hit rate of approved vs candidate memory

High later-deprecation rates usually mean extraction/promotion policy is too aggressive.

## Decision

The next milestone should bias toward conservative promotion with strong provenance and explicit review, because bad durable memory is more damaging than missing memory.
