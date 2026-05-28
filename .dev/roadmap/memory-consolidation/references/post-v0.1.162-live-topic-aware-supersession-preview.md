# Post-v0.1.162 live topic-aware supersession preview

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-28 10:43 KST

## Scope

Continued from the fresh live read-only automation-policy checkpoint and inspected the concrete next-lane preview candidates against the real live DB `/Users/reddit/.agent-memory/memory.db`.

Primary run directory: `/tmp/agent-memory-next-candidate-review-20260528T103752Z`

No mock DB or smoke DB was used for the live decision. Focused tests were used only because the supersession preview code changed.

## Live evidence inspected

Re-ran the documented review-only next-lane previews:

- `/tmp/agent-memory-next-candidate-review-20260528T103752Z/reinforcement-refinement-preview.json`
  - `kind=dogfood_reinforcement_refinement_preview`
  - `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`
  - `candidate_count=7`
  - high-tier reinforcement review candidates: `procedure:1`, `fact:1`, `episode:1`, `fact:6`, `fact:4`, `fact:8`
  - `fact:5` remained low-tier with activation count `1`
- `/tmp/agent-memory-next-candidate-review-20260528T103752Z/decay-collapse-preview.json`
  - `kind=dogfood_decay_collapse_preview`
  - `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`
  - `candidate_count=1`
  - candidate `fact:5`, `resolution_hint=collect_more_activation_evidence_before_decay_action`
  - ref-safe evidence says the memory exists, is approved/default-visible elsewhere, has scope and one relation; no raw content included
- `/tmp/agent-memory-next-candidate-review-20260528T103752Z/supersession-preview.json`
  - pre-fix preview returned one high-tier `same_claim_slot_conflict`: `fact:5` vs `fact:9`
  - live review artifacts showed this was not a semantic supersession candidate; both facts are independent user preferences under the broad `(user, prefers, project:agent-memory)` slot:
    - `fact:5`: real downloaded-install QA for agent-memory milestone releases
    - `fact:9`: autonomous agent-memory progress when next steps are clear
  - both have independent auto-approval graph evidence and approval history

## Code change

The supersession preview now reuses the existing remember-preference topic key for `subject_ref=user` and `predicate=prefers` before treating preference memories as same-slot supersession candidates.

Effect:

- independent preference topics no longer appear as supersession/replacement candidates just because they share `(user, prefers, scope)`
- same-topic preference contradictions still appear for human review
- non-preference facts keep the previous subject/predicate/scope behavior
- preview remains read-only and does not write review rows, relations, status transitions, ranking data, or core memories
- ref-safe review command templates now use existing CLI verbs (`review explain`, `review history`, and `review replacements`) instead of the stale invalid `review fact` shape

Post-fix live artifact:

- `/tmp/agent-memory-next-candidate-review-20260528T103752Z/supersession-preview-topic-aware.json`
  - `read_only=true`
  - `mutated=false`
  - `default_retrieval_unchanged=true`
  - `candidate_count=0`
  - quality gate red only on `no_supersession_candidates_ready`

This resolves the only live supersession review candidate as a topic-grouping false positive. No supersession/replacement corridor should be opened from it.

## Verification

Focused code tests:

```text
uv run pytest tests/test_cli.py -q -k 'supersession_preview'
3 passed, 254 deselected
```

Live real-DB verification:

```text
uv run agent-memory dogfood supersession-preview /Users/reddit/.agent-memory/memory.db --limit 200 --top 20 --output /tmp/agent-memory-next-candidate-review-20260528T103752Z/supersession-preview-topic-aware.json
```

Result: zero supersession candidates after topic-aware grouping, with no mutation.

## Current stop gates

- Do not create a supersession/replacement relation for `fact:5` and `fact:9`; they are independent preference topics.
- Do not collapse/deprecate/delete `fact:5`; decay preview still recommends collecting more activation evidence, not mutation.
- Do not persist duplicate lifecycle reinforcement candidates; refresh preview previously had no new unapplied targets.
- Keep broad/background/default mutation, ordinary conversation auto-approval, default-ranking mutation, telemetry reset, core memory-status writes, retrieval-ranking writes, and unreviewed promotion blocked.

## Next safe action

Continue with real live read-only evidence. The remaining concrete review material is:

1. reinforcement refinement candidates, especially high-activation approved memories, but mutation still needs a separate guarded policy/corridor;
2. `fact:5` decay monitoring, where current evidence supports more activation collection rather than collapse/deprecation;
3. ordinary-turn auto-approval readiness, which remains blocked until explicit remember-intent evidence exists.
