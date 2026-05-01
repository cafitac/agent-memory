# Stage H: Product Hardening and Public Readiness

Status: AI-authored draft. Not yet human-approved.

## Goal

Turn the consolidation system into something external users can trust: measurable, inspectable, backed up, and documented without overstating experimental behavior.

## Stage exit criteria

- Consolidation quality has fixture-based metrics.
- Users can visualize trace/candidate/memory graph lineage.
- Richer state can be backed up and restored.
- Public docs describe only stable behavior as stable.

## PR H1: Add consolidation evaluation fixtures and metrics

### Objective

Measure whether trace/consolidation improves memory quality.

### Fixtures should cover

- repeated user corrections
- preference formation
- stale/superseded facts
- procedural reuse
- no-match/empty retrieval cases
- explicit remember-intent

### Acceptance

- CI produces advisory metrics.
- No external flaky services required.
- Metrics compare against a baseline.

## PR H2: Add graph/trace visualization export

### Objective

Let users inspect memory consolidation paths visually.

### Candidate formats

- JSON graph export
- Graphviz dot export
- small static HTML export

### Acceptance

- Local-only and redacted.
- Shows traces, candidates, durable memories, relations, activation counts, status history.
- Example data contains no secrets.

## PR H3: Add backup/import/export for trace and consolidation state

### Objective

Make the richer DB operationally safe.

### Acceptance

- Backup round-trip works in tests.
- Version compatibility is checked.
- Import fails safely on incompatible schemas.
- Privacy docs explain what is included.

## PR H4: Promote reviewed docs from `.dev` into public docs

### Objective

Expose the consolidation model to users only after implementation and dogfood are mature enough.

### Acceptance

- README/docs clearly distinguish stable defaults from experimental opt-in features.
- Privacy/security docs match actual storage behavior.
- Hermes first-run/dogfood docs include current safe commands.
- No marketing claims exceed tested behavior.
