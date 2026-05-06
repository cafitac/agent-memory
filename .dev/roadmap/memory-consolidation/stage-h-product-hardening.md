# Stage H: Product Hardening and Public Readiness

Status: AI-authored draft. Not yet human-approved.

## Goal

Turn the consolidation system into something external users can trust: measurable, inspectable, backed up, and documented without overstating experimental behavior.

## Stage exit criteria

- Consolidation quality has fixture-based metrics.
- Users can visualize trace/candidate/memory graph lineage.
- Richer state can be backed up and restored.
- Public docs describe only stable behavior as stable.

## PR H1: Add retrieval/consolidation evaluation fixtures and metrics

Status: complete for the first retrieval-eval hardening slice before `v0.1.83`, with follow-up cross-scope procedure coverage released in `v0.1.85`, noisy global fact coverage released in `v0.1.86`, and same-slot conflicting fact coverage released in `v0.1.87`.

### Objective

Measure retrieval quality before adding embeddings, reranking, broader graph expansion, or consolidation automation.

### Implemented format

- `agent-memory eval retrieval <db_path> <fixtures_path>` runs deterministic file-based fixtures against the real retrieval path.
- Baseline modes: `lexical`, `lexical-global`, `source-lexical`, and `source-global`.
- Output formats: stable JSON plus terminal-friendly text.
- Regression gates: `--fail-on-regression`, baseline regression flags, warning thresholds, and advisory reports.
- Evaluations suppress retrieval bookkeeping side effects while they run.

### Acceptance

- Covered by `tests/test_retrieval_evaluation.py` and CLI tests.
- Public README documents the command and current stable options.
- No external flaky services are required.
- Local verification on 2026-05-06: `.venv/bin/python -m pytest tests/ -q` passed after the v0.1.87 same-slot conflicting fact fixture; checked-in retrieval-eval coverage is now 14 tasks.

## PR H2: Add graph/trace visualization export

Status: complete through PR #149 / v0.1.80, PR #154 / v0.1.82, and PR #156 / v0.1.83.

### Objective

Let users inspect memory consolidation paths visually.

### Implemented format

- `agent-memory graph export-html <db> --output <html> --limit <n>` writes a standalone local HTML canvas visualization.
- Default labels are ref-only; `--include-memory-labels` is an explicit local-only opt-in for curated memory labels.
- The current UI is an event-driven brain-like Canvas graph with filters/search, zoom/pan, dominant-hub explanation, node inspector, Korean-localized operator labels, and quality modes (`auto`, `performance`, `sharp`).

### Acceptance

- Local-only, read-only, and redacted by default.
- Shows typed facts/procedures/episodes, traces, observations, activations, relations, and retrieval/activation edges.
- Example/live smoke contains no raw source content, raw query text, or trace summaries.
- Remaining polish is incremental UX tuning only; the first interactive/localized graph hardening path is complete.

## PR H3: Add backup/import/export for trace and consolidation state

Status: complete and released in `v0.1.84` via PR #158/#159.

### Objective

Make the richer DB operationally safe without changing retrieval ranking, default memory approval, or G4 apply-mode behavior.

### Acceptance

- Backup round-trip works in tests and published-install smokes through `agent-memory backup export`, `backup inspect`, and `backup restore`.
- Version compatibility is checked through the backup manifest `format_version`.
- Restore/import fails safely on incompatible manifest versions, unsafe database entry names, and existing output DBs unless `--overwrite` is explicit.
- Privacy docs explain that `manifest.json` is metadata-only while the bundled SQLite database contains the local memory state.
- v0.1.84 was verified from GitHub Release, npm, PyPI, fresh PyPI venv, fresh npm wrapper, and the live Hermes pinned runtime.

## PR H4: Promote reviewed docs from `.dev` into public docs

Status: complete in PR #161; live runtime follow-up verified in v0.1.85, v0.1.86, and v0.1.87.

### Objective

Expose the consolidation model to users only after implementation and dogfood are mature enough.

### Implemented format

- README links the public privacy/safety model and states stable defaults versus experimental/operator-only surfaces.
- `docs/privacy-and-safety.md` documents local-first storage, private artifacts, backup/restore privacy, read-only diagnostics, opt-in mutation guardrails, and sharing guidance.
- `docs/first-run-memory-layer.md` now tells new users to create and inspect a backup before experiments.
- `docs/hermes-dogfood.md` clarifies that dogfood/consolidation commands are diagnostics, not broad automatic memory saving.
- `docs/install-smoke.md` reflects the v0.1.84 validated release, current npm/uvx command shapes, and backup/restore smoke coverage; v0.1.85, v0.1.86, and v0.1.87 runtime QA were recorded in the handoff after PR #162/#163, PR #165/#166, and PR #168/#169.

### Acceptance

- README/docs clearly distinguish stable defaults from experimental opt-in features.
- Privacy/security docs match actual storage behavior.
- Hermes first-run/dogfood docs include current safe commands.
- No marketing claims exceed tested behavior.
