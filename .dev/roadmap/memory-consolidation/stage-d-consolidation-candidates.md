# Stage D: Consolidation Candidates Before Mutation

Status: AI-authored draft. Not yet human-approved.

## Goal

Suggest possible long-term memories from traces and activation signals without creating or approving them automatically.

This is where the product starts to feel like memory consolidation, but it must remain read-only until the candidate quality is trusted.

## Stage exit criteria

- Repeated/similar traces can be grouped into candidate clusters.
- Users can inspect why a candidate exists.
- Bad candidates can be rejected or snoozed without deleting evidence.
- No candidate is auto-approved.

## PR D1: Add trace clustering for consolidation candidates

### Status

- In progress on branch `feat/consolidation-candidates`.
- PR C4 completed in v0.1.51 with read-only `activations decay-risk-report`.

### Objective

Group related traces into candidate clusters using deterministic lexical/metadata logic first.

### Constraints

- Do not require embeddings.
- Do not output raw trace text.
- Preserve evidence refs and windows.
- Keep cluster fingerprints stable enough for rejection/snooze later.

### Acceptance

- Cluster report shows evidence count, time window, surfaces, scopes, and safe summaries.
- Empty or weak clusters are not promoted.

## PR D2: Add `consolidation candidates` read-only CLI

### Objective

Expose candidate clusters as reviewable suggestions.

### Candidate CLI

```bash
agent-memory consolidation candidates <db> --limit 50 --output-json
```

### Candidate fields

- candidate id/fingerprint
- guessed memory type: semantic, episodic, procedural, preference, unknown
- evidence refs
- reinforcement factors
- risk flags
- suggested review commands
- read_only: true

### Acceptance

- No mutation.
- No raw queries/prompts.
- Candidate JSON is stable for later explanation/promotion commands.

## PR D3: Add candidate explanation details

### Objective

Make candidates auditable before users trust promotion.

### Candidate CLI

```bash
agent-memory consolidation explain <db> <candidate-id>
```

### Explanation should answer

- Why was this candidate grouped?
- Which traces/activations support it?
- What memory type is guessed and why?
- What existing facts/procedures might overlap?
- What risks or conflicts are known?

### Acceptance

- Explanation includes provenance/status/supersession context.
- Explanation prints safe summaries and refs, not raw secrets.

## PR D4: Add candidate rejection/snooze state

### Objective

Avoid repeatedly annoying users with bad candidates.

### Candidate commands

```bash
agent-memory consolidation reject <db> <candidate-id> --reason "not useful"
agent-memory consolidation snooze <db> <candidate-id> --until <date-or-duration>
```

Exact command shape can change.

### Acceptance

- Rejection/snooze does not delete traces.
- Rejected fingerprints are filtered from candidate output.
- Candidate can reappear only if meaningful new evidence changes the fingerprint/window.
