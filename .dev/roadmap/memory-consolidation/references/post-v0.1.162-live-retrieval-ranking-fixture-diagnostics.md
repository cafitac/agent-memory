# Post-v0.1.162 live retrieval-ranking fixture diagnostics checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-15 15:56 KST

## Purpose

Harden the read-only live retrieval-ranking fixture generator so small or sparse live DB coverage does not look silently sufficient. The command now reports generation coverage, skipped/blocker reasons, and immediate retrieval-eval diagnostics before generated fixtures are used as ranking/application-audit evidence.

## Source changes

Command: `dogfood live-retrieval-ranking-fixtures <db_path> --fixture-output <json>`

New/extended output:

- `generation_diagnostics`
  - approved memory counts by type;
  - generated task counts by type;
  - skipped counts by type;
  - skip reasons by type: `insufficient_approved_memory`, `generation_limit_reached`, or `none`;
  - `limit_per_type` and per-task retrieval limit.
- `retrieval_diagnostics`
  - immediate read-only evaluation of the generated fixture;
  - eval pass/fail, failed task count, baseline regression count;
  - blocker reasons: `retrieval_eval_failures_present`, `baseline_regression_threshold_exceeded`, or `no_generated_fixture_tasks`;
  - failure diagnostics limited to task ids, preferred-scope presence, missing/avoid/retrieved counts, and reason labels.
- `reliability_gate`
  - diagnostic-only pass/blocker summary;
  - configurable via `--min-reliable-tasks`;
  - does not authorize mutation.

New flags:

- `--min-reliable-tasks`
- `--baseline-mode lexical|lexical-global|source-lexical|source-global`
- `--max-baseline-regressions`

## Safety contract

Unchanged from the prior fixture-generation checkpoint:

- read-only report/fixture generation only;
- `read_only=true`;
- `mutated=false`;
- `default_retrieval_unchanged=true`;
- no default ranking mutation;
- no live G4/G5 apply;
- no telemetry reset;
- no collapse/delete;
- no unreviewed promotion;
- no ordinary conversation auto-approval;
- no raw source content, raw transcript, raw query/content in failure diagnostics, reviewed payloads, private reasons, or backup contents.

## Verification

Focused diagnostics tests:

```bash
uv run pytest tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_generate_live_compatible_fixture tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_reports_generation_blockers_for_sparse_db tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_reports_limit_skips_without_raw_content -q
# 3 passed
```

Evidence/audit subset:

```bash
uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/test_cli.py -q -k 'live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit'
# 4 passed, 147 deselected
```

Full source gate:

```bash
uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py && uv run pytest tests/ -q
# 333 passed, 1 xfailed
```

Live read-only source smoke:

- Report directory: `/Users/reddit/.agent-memory/reports/source-live-ranking-fixture-diagnostics-20260515T065526Z/`
- Live DB: `/Users/reddit/.agent-memory/memory.db`
- Generated fixture: `live-retrieval-ranking-fixtures.json`
- Generator report: `live-retrieval-ranking-fixtures-report.json`
- Ranking report: `retrieval-ranking-experiment.json`

Smoke result:

- fixture task count: `4`
- memory type task counts: facts `2`, procedures `1`, episodes `1`
- generation diagnostics: no skipped tasks, all skip reasons `none`
- retrieval diagnostics: pass, failed task count `0`, baseline regression count `0`
- reliability gate: pass with `--min-reliable-tasks 4`
- downstream ranking experiment: `ranking_change_allowed=true`, `baseline_regression_count=0`, `live_compatible_task_count=4`

## Progress interpretation

Safety-gated north-star progress: approximately 89%.

This is not full human-brain-like autonomy yet. It improves the evidence runway by making live fixture coverage and retrieval failures explicit. Remaining blockers are repeated/bundled evidence runs, larger-volume stability, default-off automation, and exact-approved mutation corridors.

## Recommended next slice

Add a read-only repeated evidence bundle that:

1. generates live retrieval-ranking fixtures with diagnostics;
2. runs retrieval-ranking experiment over the generated fixture;
3. feeds the ranking report into trace-candidate application audit with rollback replay evidence;
4. records artifact hashes and blocker reasons;
5. remains strictly read-only/no-mutation.
