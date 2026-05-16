# Post-v0.1.162 ordinary-turn label update checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 02:01 KST

## Summary

Added `dogfood ordinary-turn-label-update`, a bounded exact-ref corridor that writes one ordinary-turn memory-worthiness label into `experience_traces.metadata_json` while keeping ordinary conversation auto-approval blocked.

## Command contract

```bash
agent-memory dogfood ordinary-turn-label-update <db_path> \
  --trace-ref experience_trace:<id> \
  --expected-memory-worthy true|false \
  --actor <actor> \
  --reason <private reason> \
  --approval-phrase label-approved-ordinary-turn-v1 \
  --output <report.json>
```

Mutation scope:

- only the selected `experience_traces.metadata_json` row;
- preserves existing metadata;
- sets `ordinary_turn=true`;
- sets `expected_memory_worthy=true|false`;
- stores `ordinary_turn_label.policy`, `ordinary_turn_label.actor`, and `ordinary_turn_label.reason_sha256`.

Output/privacy:

- no raw trace summary;
- no raw transcript;
- no raw query text;
- no raw content;
- no sample values;
- no raw reason.

Safety blocks:

- exact phrase required: `label-approved-ordinary-turn-v1`;
- `trace_ref` must be `experience_trace:<positive-id>`;
- selected row must be `event_kind=turn`;
- invalid metadata JSON blocks;
- secret-like summaries block with `secret_like_trace_blocked`;
- no memory promotion, no broad/background apply, no default-ranking mutation, no collapse/delete, no telemetry reset, and no ordinary conversation auto-approval.

## Verification

RED/GREEN:

- Initial focused tests failed because `ordinary-turn-label-update` was not a registered dogfood subcommand.
- After implementation, focused label-update tests passed.
- Live-copy smoke initially failed because live packet refs can have `event_kind=turn` without `metadata.ordinary_turn=true`; the corridor now treats `event_kind=turn` as the source of truth and writes `ordinary_turn=true` during labeling.

Focused verification:

```text
2 passed
6 passed, 173 deselected
```

Copy-DB smoke:

- Directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-label-update-smoke-20260516T170107Z/`
- Source DB was copied from `/Users/reddit/.agent-memory/memory.db`; live DB was not mutated.
- `ordinary-turn-label-update.json`: green, `mutated=true`, `ordinary_conversation_auto_approval=false`.
- `ordinary-turn-classifier-eval.json`: green on the copy with `--min-labeled 1 --min-precision-percent 0`, read-only and auto-approval false.

## Progress interpretation

- Safety-gated operational north-star: approximately 99%+.
- Scoped local human-brain-like lifecycle: approximately 99.2-99.4%.
- Remaining gap: repeated labeled ordinary-turn windows and a read-only inferred-approval readiness summary before any ordinary-turn apply corridor.

## Next safe slice

Add a repeated-window ordinary-turn label/eval summary gate that consumes several saved `ordinary-turn-classifier-eval` artifacts and remains read-only. Do not enable ordinary-turn auto-approval or broad apply from this checkpoint alone.
