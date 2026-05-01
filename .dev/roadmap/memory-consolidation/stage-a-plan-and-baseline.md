# Stage A: Plan Lock and Dogfood Baseline

Status: AI-authored draft. Not yet human-approved.

## Goal

Make the long-term memory consolidation direction durable before implementing new storage or automation. Stage A prevents future sessions from drifting toward a simplistic "save important memories" product or jumping directly to unsafe automatic memory creation.

## Stage exit criteria

- The north-star and PR ladder are committed in a docs-only PR.
- Future sessions can read `.dev/status/current-handoff.md` plus this directory and know the next PR.
- A repeatable local dogfood baseline report exists for comparing trace/consolidation changes.
- No code path stores raw prompts as a side effect of this stage.

## PR A1: Persist this consolidation roadmap and release it as the canonical planning checkpoint

### Objective

Commit the roadmap, architecture/product clarifications, handoff, and detailed stage documents as a planning checkpoint.

### Files

- Modify: `.dev/roadmap/roadmap-v0.md`
- Modify: `.dev/architecture/architecture-v0.md`
- Modify: `.dev/product/thesis-and-scope.md`
- Modify: `.dev/status/current-handoff.md`
- Create: `.dev/roadmap/memory-consolidation/README.md`
- Create: `.dev/roadmap/memory-consolidation/stage-a-plan-and-baseline.md`
- Create: `.dev/roadmap/memory-consolidation/stage-b-trace-layer.md`
- Create: `.dev/roadmap/memory-consolidation/stage-c-activation-reinforcement-decay.md`
- Create: `.dev/roadmap/memory-consolidation/stage-d-consolidation-candidates.md`
- Create: `.dev/roadmap/memory-consolidation/stage-e-reviewed-promotion.md`
- Create: `.dev/roadmap/memory-consolidation/stage-f-retrieval-signals.md`
- Create: `.dev/roadmap/memory-consolidation/stage-g-cautious-automation.md`
- Create: `.dev/roadmap/memory-consolidation/stage-h-product-hardening.md`

### Implementation steps

1. Verify the root checkout and preserve local-only untracked files.
2. Review the roadmap diff and make sure it says final goal, not MVP goal.
3. Confirm every stage document has purpose, acceptance criteria, guardrails, and next-step boundaries.
4. Run docs-only verification.
5. Create a branch such as `docs/memory-consolidation-roadmap`.
6. Stage only the roadmap/status/product/architecture docs and this directory.
7. Open a docs-only PR titled `docs: add memory consolidation roadmap`.

### Verification

```bash
git diff --check
python - <<'PY'
from pathlib import Path
paths = [
    Path('.dev/roadmap/roadmap-v0.md'),
    Path('.dev/architecture/architecture-v0.md'),
    Path('.dev/product/thesis-and-scope.md'),
    Path('.dev/status/current-handoff.md'),
]
for path in paths:
    text = path.read_text()
    if '\n7|' in text or '\n8|' in text:
        raise SystemExit(f'accidental line-number artifact in {path}')
print('docs ok')
PY
```

### Acceptance

- No application code changes.
- No release behavior changes.
- PR clearly states this is a planning checkpoint.
- `roadmap-v0.md` points to this directory.
- `current-handoff.md` says the next executable slice after A1 is A2.

### Do not do in A1

- Do not add trace schemas.
- Do not change Hermes config.
- Do not create auto-save behavior.
- Do not commit local-only untracked directories.

## PR A2: Add a dogfood baseline snapshot command/report

### Objective

Capture the current memory/observation/Hermes QA state in a stable read-only report so later PRs can compare whether trace and consolidation work improves or worsens the system.

### Candidate shape

Prefer a read-only CLI command such as:

```bash
agent-memory dogfood baseline ~/.agent-memory/memory.db --output-json
```

If a dedicated command feels premature, create a documented script under `scripts/` that composes existing read-only commands. The dedicated command is preferable if the report will be reused in release QA.

### Data to include

- agent-memory version
- DB path and schema version if available
- retrieval observation count
- empty retrieval ratio
- top retrieved memory refs with status summary
- review candidate count
- empty diagnostics summary
- current Hermes runtime command/path as metadata only when safe
- E2E marker check result for the harmless local QA fact, if executed separately

### Safety rules

- Do not include raw user queries.
- Do not include prompt text.
- Do not include full Hermes config.
- Do not include environment secrets or credential paths.
- Treat the report as local-only dogfood output.

### Tests

- Regression test that the JSON has stable top-level keys.
- Regression test that no query preview/raw prompt field is emitted.
- Regression test with an empty DB or no observations.
- Regression test that failures in optional Hermes metadata collection degrade gracefully.

### Implementation status

Implemented in PR A2:

- Added `agent-memory dogfood baseline <db> --output-json` as a dedicated read-only CLI report.
- Reused existing observation audit, empty diagnostics, and review-candidate logic instead of adding a new telemetry store.
- Added memory status counts, DB path/schema metadata, sanitized Hermes doctor metadata, and a non-executed local E2E marker.
- Kept secret-safety constraints: no raw queries, query previews, prompt text, full Hermes config, environment secrets, or bootstrap command in the baseline output.
- Added CLI regression tests for a populated observation DB and an empty/no-observation DB.

### Verification

Focused tests plus full test suite. If the command lands in the package CLI, include release readiness and npm dry-run checks. If Hermes behavior is untouched, real Hermes E2E is optional but a local run of the baseline command against `/Users/reddit/.agent-memory/memory.db` is required.

### Exit criteria

- A future PR can paste two baseline outputs side by side and compare observation quality.
- The report is read-only and secret-safe.
- The next stage can start from trace schema design with a known baseline.
