# post-v0.1.162 ordinary-turn metadata memory hints

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 02:38 KST

## Purpose

Close the evidence-quality gap exposed by the repeated ordinary-turn eval-window gate: live `turn` traces intentionally store no raw summary by default, so the ordinary-turn classifier could not produce positive predictions from metadata-only traces.

This slice keeps raw transcript storage blocked while allowing the hook to attach a small raw-text-free metadata hint when the transient user message contains an obvious durable marker such as `next time`, `from now on`, `remember that`, `my setup`, `my workflow`, `우리`, or `앞으로`.

## Source behavior

- `hermes-pre-llm-hook` still records ordinary turns as metadata-only:
  - `summary=None`
  - no raw user message
  - no raw transcript/query/content
  - `trace_recording=default_metadata_only`
  - `candidate_policy=evidence_only`
  - `auto_approved=false`
- For safe durable ordinary turns, metadata may now include:
  - `ordinary_turn_memory_hint.classifier_policy=ordinary-turn-memory-worthiness-heuristic-v1`
  - `ordinary_turn_memory_hint.predicted_memory_worthy=true`
  - `ordinary_turn_memory_hint.classified_reason=durable_context` or `ordinary_procedure`
  - `ordinary_turn_memory_hint.raw_text_stored=false`
- `dogfood ordinary-turn-label-packet` and `dogfood ordinary-turn-classifier-eval` consume the metadata hint only when the policy matches and `raw_text_stored=false`.
- Summary-based secret blocking and preference/procedure classification still take precedence when a summary exists.

## Copy-DB smoke

Artifact directory:

`/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-memory-hint-smoke-20260516T173512Z/`

The smoke copied `/Users/reddit/.agent-memory/memory.db` and did not mutate the live DB.

Smoke flow:

1. Inserted two metadata-only ordinary turns through the real `hermes-pre-llm-hook` command against the copy DB.
2. Labeled each copied trace with `dogfood ordinary-turn-label-update` and exact phrase `label-approved-ordinary-turn-v1`.
3. Ran two strict `dogfood ordinary-turn-classifier-eval` reports.
4. Ran `dogfood ordinary-turn-eval-window-summary` with `--min-report-count 2`, `--min-labeled-per-report 1`, and `--min-precision-percent 100`.

Smoke result:

- `quality_gate.pass=true`
- `precision_percent_min=100`
- `false_positive_total=0`
- `false_negative_total=0`
- `labeled_ordinary_turn_total=3`
- `ordinary_conversation_auto_approval=false`
- `mutated=false` in the final repeated-window summary

## Validation

- RED observed:
  - hook metadata-hint test failed with missing `ordinary_turn_memory_hint`
  - classifier eval test failed because metadata-only hinted traces were counted as `none`
- Focused GREEN:
  - `2 passed` for the new hook + classifier tests
- Broader ordinary-turn / hook focus:
  - `11 passed, 171 deselected`
- Full suite:
  - `364 passed, 1 xfailed`
- Release/package checks:
  - `tests/test_release_workflows.py tests/test_release_metadata.py`: `7 passed`
  - `scripts/check_release_metadata.py`: passed
  - `npm pack --dry-run`: passed

## Current interpretation

- Safety-gated operational north-star remains approximately 99%+.
- Scoped local human-brain-like lifecycle is approximately 99.55-99.65%.
- The system can now produce positive ordinary-turn eval evidence without storing raw ordinary-turn text.
- Ordinary-turn apply and ordinary conversation auto-approval are still blocked.

## Next safe work

1. Let future real turns accumulate metadata hints, or create copy-DB windows from approved hook smokes.
2. Label only locally reviewed refs with `ordinary-turn-label-update`.
3. Rerun strict repeated-window summaries on larger windows.
4. Design a separate read-only inferred ordinary-turn approval readiness gate; do not implement apply yet.
