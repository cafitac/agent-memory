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

### Status

- Completed in v0.1.54 via PR #76.
- Scope was deliberately narrow: semantic fact promotion only. Procedure/preference promotion, graph lineage edges, and conflict preflight remain future PRs.

### Objective

Promote a candidate into a Fact after explicit user action.

### Candidate CLI

```bash
agent-memory consolidation promote fact <db> <candidate-id> \
  --subject-ref "agent-memory" \
  --predicate "prefers" \
  --object-ref-or-value "explicit human-reviewed promotion" \
  --scope project:agent-memory
agent-memory consolidation promote fact <db> <candidate-id> \
  --subject-ref "agent-memory" \
  --predicate "prefers" \
  --object-ref-or-value "explicit human-reviewed promotion" \
  --scope project:agent-memory \
  --approve --actor maintainer --reason "reviewed candidate evidence"
```

Prefer candidate status by default unless the user explicitly chooses approval.

### Acceptance

- Fact has provenance back to trace/candidate evidence.
- Default retrieval only injects approved facts.
- Promotion is logged in status/history tables where appropriate.

## PR E2: Add read-only consolidation promotion audit report

### Status

- Completed in v0.1.55 via PR #78.
- Scope was deliberately read-only: audit/report the manual semantic fact promotions created by E1 before adding new promotion memory types or graph mutations.

### Objective

List manual reviewed promotions with safe provenance and approval history so local dogfood can review what changed.

### Candidate CLI

```bash
agent-memory consolidation promotions report <db> --limit 50
```

### Acceptance

- Report includes promoted fact id/status, candidate fingerprint, provenance source id, safe summaries, trace ids, related observation ids, and approval history.
- Report is visibly `read_only: true` and does not mutate facts, sources, traces, status transitions, queues, ranking, or graph edges.
- Output omits raw prompts, transcripts, raw trace metadata, query previews, and secrets.
- Default retrieval remains approved-only.

## PR E3: Add consolidation relation edges

### Status

- Completed in v0.1.56 via PR #81.
- Scope was deliberately limited to manual semantic fact promotion lineage: candidate fingerprint -> promoted fact -> generated provenance source. Procedure/preference promotion, conflict preflight, automatic promotion, and retrieval ranking changes remain future PRs.

### Objective

Represent consolidation as graph lineage.

### Candidate relation types

Implemented in this E3 slice:

- `promoted_to`: from the stable consolidation candidate fingerprint to the promoted durable memory ref.
- `has_promotion_provenance`: from the promoted durable memory ref to the generated `source_record:<id>` provenance source.

Future candidate relation types:

- `reinforces`
- `derived_from_trace_cluster`
- `decays_into_summary`

Exact future names can change, but graph inspection must explain lineage.

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
