# Stage E: Reviewed Promotion Into Long-Term Memory

Status: AI-authored draft. Not yet human-approved.

## Goal

Turn trusted consolidation candidates into durable memory only through explicit review actions. This stage creates semantic facts, procedures, preferences, and graph lineage from candidate evidence.

## Stage exit criteria

- Users can manually promote candidates into long-term memory with provenance.
- Promotion creates graph relations that explain lineage.
- Conflict/supersession preflight prevents silent contradictions.
- Default retrieval remains approved-only.

## PR E1: Add manual consolidation promotion for semantic facts

### Objective

Promote a candidate into a Fact after explicit user action.

### Candidate CLI

```bash
agent-memory consolidation promote fact <db> <candidate-id> --status candidate
agent-memory consolidation promote fact <db> <candidate-id> --approve
```

Prefer candidate status by default unless the user explicitly chooses approval.

### Acceptance

- Fact has provenance back to trace/candidate evidence.
- Default retrieval only injects approved facts.
- Promotion is logged in status/history tables where appropriate.

## PR E2: Add manual consolidation promotion for procedures/preferences

### Objective

Support procedural and preference memory, not only facts.

### Acceptance

- Procedures include trigger context, preconditions, and steps.
- Preferences include scope and evidence.
- Neither is injected unless approved.
- Tests cover at least one procedure and one preference candidate.

## PR E3: Add consolidation relation edges

### Objective

Represent consolidation as graph lineage.

### Candidate relation types

- `reinforces`
- `consolidated_into`
- `derived_from_trace_cluster`
- `decays_into_summary`

Exact names can change, but graph inspection must explain lineage.

### Acceptance

- `graph inspect` shows trace/candidate/durable memory lineage.
- Relations include weights or metadata where useful.
- Existing supersession relations remain compatible.

## PR E4: Add conflict/supersession checks during promotion

### Objective

Prevent promotion from creating contradictory durable memory silently.

### Acceptance

- Promotion preflight compares candidate with existing approved/deprecated/superseded facts.
- Conflicts require explicit action.
- Suggested commands include review explain, replacements, and graph inspect.
- Tests cover at least one conflicting candidate.
