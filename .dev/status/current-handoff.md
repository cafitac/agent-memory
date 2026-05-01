# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 11:37 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.40까지 배포/Hermes QA가 완료됐고, 현재는 Priority 5 dogfood/noise monitoring에서 empty retrieval/high empty ratio 진단을 강화하는 read-only slice를 진행 중이야. 브랜치는 `feat/empty-retrieval-diagnostics`, worktree는 `/Users/reddit/Project/agent-memory/.worktrees/empty-retrieval-diagnostics`야. 목표는 `observations empty-diagnostics`를 추가해 empty-heavy observation을 surface/scope/status filter별로 묶고, scope mismatch나 승인된 memory coverage 부족을 사람이 안전하게 판단하게 하는 것이다. 자동 cleanup/mutation은 여전히 하지 않는다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified before this slice:

- latest completed release: `v0.1.40`
- v0.1.40 added observation windows/counts/status-history summaries to review-candidates and completed published smoke/Hermes runtime QA.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.40/.venv/bin/python -m agent_memory.api.cli hermes-pre-llm-hook ...` against `/Users/reddit/.agent-memory/memory.db`.
- root checkout was clean on `main...origin/main` except local-only untracked state.
- open PRs were `[]`.

Active slice/worktree:

- branch: `feat/empty-retrieval-diagnostics`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/empty-retrieval-diagnostics`
- intended release after merge: likely `v0.1.41`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Current slice: empty retrieval diagnostics

Goal:

- Keep dogfood/noise monitoring read-only.
- Make high empty retrieval ratio actionable without storing or emitting raw user queries.
- Diagnose empty-heavy segments by surface, preferred scope, and retrieval status filter before changing rankers or adding graph traversal.

Implemented so far in the active worktree:

- New CLI command:
  - `agent-memory observations empty-diagnostics <db_path> --limit 200 --top 10 --high-empty-threshold 0.5`
- Output contract:
  - `kind: retrieval_empty_diagnostics`
  - `read_only: true`
  - `observation_count`
  - `empty_retrieval_count`
  - `empty_retrieval_ratio`
  - `quality_warnings`
  - top-level `observation_window`
  - `empty_by_surface[]`
  - `empty_by_preferred_scope[]`
  - `empty_by_status_filter[]`
  - `suggested_next_steps`
- Segment entries include:
  - segment key (`surface`, `preferred_scope`, or `statuses`)
  - `total_count`
  - `empty_count`
  - `empty_ratio`
  - `signals`, currently `high_empty_segment` when above threshold
  - `sample_observation_ids`
  - `observation_window`
- Secret-safety preserved:
  - no raw query text
  - no query previews
  - no prompt content
- Docs updated:
  - `README.md`
  - `docs/hermes-dogfood.md`
- Tests updated in `tests/test_cli.py`:
  - new regression asserts empty diagnostics segment grouping, read-only shape, next-step hints, and no secret leakage from raw query strings.

Verification so far:

- RED confirmed:
  - focused test initially failed because `empty-diagnostics` parser choice was missing.
- GREEN focused:
  - `TMPDIR=$PWD/.tmp-test uv run pytest tests/test_cli.py::test_python_module_cli_observations_empty_diagnostics_groups_empty_segments_without_raw_queries -q`
  - `1 passed`

Remaining before PR:

1. Run broader focused CLI tests around observations audit/review-candidates/empty-diagnostics.
2. Run full local verification:
   - `uv run pytest tests/ -q`
   - `uv run python scripts/check_release_metadata.py`
   - `uv run python scripts/smoke_release_readiness.py`
   - `npm pack --dry-run`
   - `git diff --check`
   - `node --check bin/agent-memory.js`
3. Run real local DB smoke for `observations empty-diagnostics` and verify no raw query fields appear.
4. Run static diff secret scan.
5. Create PR, watch CI, merge, follow release-sync/publish/published smoke/Hermes QA.
6. After v0.1.41 install, repeat Hermes hook doctor and installed `observations empty-diagnostics` against the existing local DB.

## Next natural slice after this one

After empty retrieval diagnostics are released and dogfooded, continue Priority 5 by either:

1. adding an explicit human review cadence/checklist around audit/review-candidates/empty-diagnostics, or
2. improving candidate report UX further by bundling suggested follow-up commands into a richer read-only triage report.

Avoid automatic cleanup/deprecation until the review and diagnostics workflow has been used on real local data for a while.
