# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-02 00:25 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.54까지 배포/npm/PyPI/Hermes QA가 완료됐고, Stage E / PR E1 `consolidation promote fact` manual reviewed semantic fact promotion까지 완료됐다. GitHub Actions publish 최적화도 완료되어 published install smoke는 opt-in/manual이고 docs/workflow-only auto-release는 skip된다. 현재 진행 중인 제품 slice는 Stage E / PR E2 read-only `consolidation promotions report` audit surface다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current worktree:

- `/Users/reddit/Project/agent-memory/.worktrees/consolidation-promotion-report`
- Branch: `feat/consolidation-promotion-report`
- Base: `origin/main`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.54`
- v0.1.54 added manual `agent-memory consolidation promote fact`.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.54/.venv/bin/agent-memory`.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Completed workflow optimization slice

PR #75 `ci: shorten publish workflow` merged.

Result:

- `auto-release.yml` ignores docs/workflow-only pushes.
- `publish.yml` no longer repeats full pytest; main/release-sync CI remains the full test gate.
- slow real-registry `published-install-smoke` is opt-in via `run_published_install_smoke`, default `false`.
- standalone `published-install-smoke.yml` remains the manual external-install gate.

## Completed Stage E / PR E1 slice

PR #76 `feat: add consolidation fact promotion` merged and released in v0.1.54.

Behavior:

- `agent-memory consolidation promote fact <db> <candidate-id> ...` creates semantic facts from explicitly reviewed candidates.
- Reviewer supplies final fact fields; candidate contributes safe provenance only.
- Default output is `candidate` status and hidden from default retrieval.
- `--approve --actor ... --reason ...` explicitly approves and logs status history.
- Unknown candidate ids fail without creating facts or provenance sources.
- No automatic promotion, approval queue, graph relation edge, procedure/preference promotion, conflict preflight, or retrieval ranking change yet.

## Active Stage E / PR E2 slice

Goal:

- Add a read-only audit/report surface for manual consolidation promotions created by E1.
- Command shape: `agent-memory consolidation promotions report <db> --limit 50`.
- Report promoted semantic facts, candidate fingerprints, provenance source ids, safe summaries, trace ids, related observation ids, status counts, and approval history.
- Keep the command read-only and secret-safe: no raw prompts, transcripts, query previews, raw trace metadata, queue mutation, graph edges, cleanup, or retrieval ranking changes.

Current modified files in the worktree:

- `src/agent_memory/api/cli.py`
- `tests/test_memory_activations.py`
- `README.md`
- `docs/hermes-dogfood.md`
- `.dev/roadmap/memory-consolidation/stage-e-reviewed-promotion.md`
- `.dev/status/current-handoff.md`

Focused tests already pass:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest \
  tests/test_memory_activations.py::test_cli_consolidation_promotions_report_lists_manual_promotions_without_mutation_or_raw_payload \
  tests/test_memory_activations.py::test_cli_consolidation_promotions_report_empty_database_is_read_only \
  -q
# 2 passed
```

Remaining verification before PR:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py tests/test_review_and_scope_ranking.py tests/test_experience_traces.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
git diff --check
npm pack --dry-run
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
```

After PR merge:

- Because this is a product feature, expect release-sync and publish to run for v0.1.55.
- Publish should stay fast because PR #75 removed duplicate full pytest and made published install smoke opt-in.
- Still run manual external install smoke for npm/PyPI before Hermes runtime update.
- Install `/Users/reddit/.agent-memory/runtime/v0.1.55/.venv/bin/agent-memory`, update Hermes config, and QA Hermes hook/runtime as in prior releases.

## Canonical roadmap position

The durable north-star is a graph-based memory consolidation runtime:

- experiences leave lightweight traces
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and retrieval usefulness
- weak traces decay/expire/collapse into summaries
- strong trace clusters consolidate into semantic, episodic, procedural, and preference memories
- prompt-time retrieval remains explainable through provenance, status history, supersession, and graph relations

Roadmap sequence:

1. Stage A: lock plan and dogfood baseline
2. Stage B: trace layer without automatic memory creation
3. Stage C: activation and reinforcement signals
4. Stage D: consolidation candidates before mutation
   - D1/D2 candidates report done in v0.1.52
   - D3 candidate explanation details done in v0.1.53
5. Stage E: reviewed promotion into long-term memory
   - E1 semantic fact promotion done in v0.1.54
   - E2 promotion audit report in progress
6. Stage F: retrieval uses consolidation signals conservatively
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness

## E2 boundaries

In scope:

- read-only report over E1 manual semantic fact promotions
- promoted fact id/status/claim fields
- candidate fingerprint and generated provenance source id
- safe provenance summaries, trace ids, related observation ids
- approval history using existing memory status transitions
- status counts and retrieval policy reminder

Out of scope:

- automatic promotion
- approval queue write/bulk apply
- procedure/preference promotion
- graph lineage relation edges
- conflict/supersession preflight
- retrieval ranking changes
- cleanup/delete/decay mutations
- raw prompt/user message/transcript/query_preview storage or output
