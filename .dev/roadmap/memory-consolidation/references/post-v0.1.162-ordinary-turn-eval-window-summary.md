# Post-v0.1.162 ordinary-turn eval-window summary checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 02:20 KST

## Summary

Added `dogfood ordinary-turn-eval-window-summary`, a read-only aggregate/hash-only gate that summarizes repeated saved ordinary-turn classifier-eval artifacts before any inferred ordinary-turn approval design.

## Command contract

```bash
agent-memory dogfood ordinary-turn-eval-window-summary \
  --eval-report <ordinary-turn-classifier-eval-a.json> \
  --eval-report <ordinary-turn-classifier-eval-b.json> \
  --min-report-count 2 \
  --min-labeled-per-report 10 \
  --min-precision-percent 100 \
  --output <summary.json>
```

The command is read-only and validates each report:

- `kind == dogfood_ordinary_turn_classifier_eval`;
- `read_only=true`;
- `mutated=false`;
- `default_retrieval_unchanged=true`;
- `ordinary_conversation_auto_approval=false`;
- classifier eval quality gate green;
- labeled count and precision meet thresholds;
- false positives and false negatives are zero;
- privacy flags do not include raw trace summary, transcript, query text, raw content, or sample values.

Output is aggregate/ref-safe only:

- report path plus SHA-256;
- pass/read-only/auto-approval-blocked counts;
- labeled min/max/total;
- min precision;
- false-positive and false-negative totals;
- no raw report bodies and no raw trace text.

Forbidden authority remains blocked:

- no ordinary conversation auto-approval;
- no apply execution;
- no memory promotion;
- no broad/background apply;
- no default-ranking mutation;
- no collapse/delete;
- no telemetry reset;
- no unreviewed promotion.

## Verification

RED/GREEN:

- Initial focused tests failed because `ordinary-turn-eval-window-summary` was not a registered dogfood subcommand.
- After implementation, focused tests passed for green repeated windows and unsafe/insufficient windows.

Commands/results:

```text
.venv/bin/python -m pytest tests/test_cli.py::test_dogfood_ordinary_turn_eval_window_summary_requires_repeated_green_windows_without_apply tests/test_cli.py::test_dogfood_ordinary_turn_eval_window_summary_blocks_unsafe_or_insufficient_windows -q
2 passed

.venv/bin/python -m pytest tests/test_cli.py -q -k 'ordinary_turn'
8 passed, 173 deselected

.venv/bin/python -m pytest tests/ -q
363 passed, 1 xfailed
```

Copy-DB smoke:

- Directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-eval-window-summary-smoke-20260516T171603Z/`.
- Source DB was copied from `/Users/reddit/.agent-memory/memory.db`; live DB was not mutated.
- Two ordinary-turn labels were applied to the copy using exact-ref `ordinary-turn-label-update`.
- Strict `--min-precision-percent 100` stayed red because the sampled window was negative-only and precision was 0.
- `ordinary-turn-eval-window-summary-green-min0.json` passed as a mechanics smoke with `report_count=2`, `quality_gate_pass_count=2`, `labeled_ordinary_turn_total=4`, `read_only=true`, `mutated=false`, and `ordinary_conversation_auto_approval=false`.

## Progress interpretation

- Safety-gated operational north-star: approximately 99%+.
- Scoped local human-brain-like lifecycle: approximately 99.4-99.5%.
- Remaining gap: more real locally reviewed ordinary-turn labels, especially positive examples, strict repeated windows, and then a separate inferred-approval readiness gate.

## Next safe slice

Build stricter ordinary-turn label coverage and rerun repeated-window summaries at `--min-precision-percent 100`. Do not enable ordinary-turn auto-approval or apply from this checkpoint alone.
