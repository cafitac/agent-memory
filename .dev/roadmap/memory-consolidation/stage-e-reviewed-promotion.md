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

### Status

- Completed in v0.1.57 via PR #84.
- Scope was deliberately conservative: semantic fact promotion conflict preflight only. It blocks silent same claim-slot contradictions before any promotion mutation, but does not automatically deprecate, supersede, approve, or change retrieval ranking.

### Objective

Prevent promotion from creating contradictory durable memory silently.

### Implemented shape

`consolidation promote fact` computes a read-only `conflict_preflight` for the requested fact fields before creating provenance sources, facts, status transitions, or lineage edges. The preflight compares the requested claim slot:

- `subject_ref`
- `predicate`
- `scope`

against existing approved/candidate/disputed/deprecated facts. Existing same-slot facts with a different `object_ref_or_value` are reported as conflicts. Blocked output is a non-zero safe failure with:

- `promoted: false`
- `read_only: true`
- `error: conflict_preflight_required`
- status counts for the claim slot
- safe conflicting fact summaries
- suggested `review explain`, `review replacements`, and `graph inspect` commands

A reviewer can pass `--allow-conflict` only after accepting that both claims should coexist. Successful promotions still keep the previous E1/E3 behavior: default status is `candidate`, `--approve --actor --reason` is explicit, lineage edges are created only after successful promotion, and default retrieval remains approved-only.

### Acceptance

- Promotion preflight compares candidate with existing approved/deprecated/superseded facts.
- Conflicts require explicit action.
- Suggested commands include review explain, replacements, and graph inspect.
- Tests cover at least one conflicting candidate.

## PR E5: Add explicit reviewed conflict relation edges

### Status

- Completed in v0.1.58 via PR #87.

### Objective

Give reviewers an explicit graph-level action after E4 conflict preflight/`--allow-conflict`, without silently changing memory status or retrieval ranking.

### Planned/implemented shape

`review relate-conflict fact <db> <left-fact-id> <right-fact-id> --actor ... --reason ...` records a human-reviewed `conflicts_with` relation between two semantic facts when:

- both facts exist;
- they share the same claim slot (`subject_ref`, `predicate`, `scope`);
- their `object_ref_or_value` differs;
- review metadata is provided.

The relation stores `review_actor`, `review_reason`, and `reviewed_at`. `review conflicts fact ...` surfaces these relation refs in its read-only same-slot report. Existing `review supersede fact ...` replacement relations use the same relation review metadata columns.

### Guardrails

- Does not approve, deprecate, supersede, reject, snooze, delete, or re-rank memories.
- Does not create automatic retrieval policy changes.
- Refuses cross-slot or duplicate-object conflict relations.
- Keeps output secret-safe and avoids raw prompt/transcript/query preview fields.

### Acceptance

- Tests cover successful reviewed conflict relation creation.
- Tests cover missing review metadata and cross-slot rejection without mutation.
- Existing supersession/replacement behavior remains compatible.
- Migration adds review metadata columns to existing relation tables.
