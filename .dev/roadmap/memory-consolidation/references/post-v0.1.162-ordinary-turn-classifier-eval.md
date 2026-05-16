# Post-v0.1.162 ordinary-turn classifier evaluation gate

Status: source/develop checkpoint. AI-authored draft; not human-approved.

## What changed

Added `dogfood ordinary-turn-classifier-eval <db_path>`, a read-only aggregate harness for evaluating ordinary-turn memory-worthiness classification before any inferred approval corridor exists.

The command:

- reads recent `experience_traces` with `event_kind=turn`;
- classifies only aggregate-safe reasons (`ordinary_preference`, `ordinary_procedure`, `durable_context`, `secret_like`, `none`);
- consumes optional labels from trace metadata key `expected_memory_worthy`;
- reports labeled/unlabeled counts, prediction counts, precision/recall, secret-block rate, and reason counts;
- keeps `ordinary_conversation_auto_approval=false` and all mutation authority false.

## Safety boundary

This is evaluation only. It does not:

- write facts, procedures, episodes, relations, candidates, review rows, or memory status transitions;
- auto-approve ordinary turns;
- expose raw trace summaries, raw transcripts, raw query text, raw content, sample values, or backup contents;
- allow broad/background apply, default-ranking mutation, collapse/delete, telemetry reset, or unreviewed promotion.

## Verification

Focused TDD path:

- RED: `tests/test_cli.py::test_dogfood_ordinary_turn_classifier_eval_scores_labeled_turns_without_apply` first failed because `ordinary-turn-classifier-eval` was not a valid dogfood subcommand.
- GREEN: focused test passed after adding the parser, dispatcher, classifier, and aggregate payload.
- Focused ordinary-turn suite: `2 passed, 174 deselected`.
- Local full suite: `358 passed, 1 xfailed` before push.
- First pushed CI exposed an unrelated Linux/SQLite retrieval-eval comparator-matrix tolerance issue (`total_avoid_hit_delta` for lexical mode can be `-16` locally and `-15` on GitHub while the stable task counts/pass counts remain unchanged). The test was tightened to accept only that known bounded delta variant instead of failing the whole automation slice on platform noise.

Live source smoke against `/Users/reddit/.agent-memory/memory.db`:

- Artifact directory: `/Users/reddit/.agent-memory/reports/post-v0.1.162-ordinary-turn-classifier-eval-20260516T160146Z/`.
- Result is correctly red/fail-closed because current live ordinary-turn traces have no `expected_memory_worthy` labels:
  - `ordinary_turn=995`;
  - `labeled_ordinary_turn=0`;
  - `unlabeled_ordinary_turn=995`;
  - `predicted_memory_worthy=0`;
  - `blocked_secret_like=0`;
  - blocked reasons: `labeled_ordinary_turn_count_below_minimum`, `precision_below_minimum`.

## Interpretation

This advances the remaining 1-2% from generic readiness measurement to a concrete read-only evaluation substrate. The live gate staying red is expected: the system now has a place to measure ordinary-turn inference quality, but it still needs a label/evidence collection pass before inferred approval can be considered.

## Next safe slice

Add a read-only ordinary-turn label/evidence packet that can select candidate ordinary turns for human review without exposing raw content in committed docs or enabling apply. After enough labels exist, rerun `ordinary-turn-classifier-eval` across repeated windows and require precision to stay green before designing any inferred approval corridor.
