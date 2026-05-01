# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 11:10 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.39까지 배포/Hermes QA가 완료됐고, 현재는 Priority 5 dogfood/noise monitoring에서 v0.1.39 dogfood 결과를 바탕으로 `observations review-candidates`의 JSON 계약을 더 운영 친화적으로 다듬는 slice를 진행 중이야. 브랜치는 `feat/observation-review-temporal`, worktree는 `/Users/reddit/Project/agent-memory/.worktrees/observation-review-temporal`야. 목표는 review-candidates 결과에 top-level count, per-ref observation window, fact status-history summary를 추가해 historical injections와 현재 lifecycle 상태를 더 쉽게 구분하는 것이다. 자동 cleanup/mutation은 여전히 하지 않는다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified before this slice:

- latest completed release: `v0.1.39`
- v0.1.39 added read-only `agent-memory observations review-candidates` and completed published smoke/Hermes runtime QA.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.39/.venv/bin/python -m agent_memory.api.cli hermes-pre-llm-hook ...` against `/Users/reddit/.agent-memory/memory.db`.
- root checkout was clean on `main...origin/main` except local-only untracked state.
- open PRs were `[]`.

Active slice/worktree:

- branch: `feat/observation-review-temporal`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/observation-review-temporal`
- intended release after merge: likely `v0.1.40`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Current slice: observation review temporal summaries

Goal:

- Keep dogfood/noise monitoring read-only.
- Make `observations review-candidates` easier to consume from local dogfood output.
- Add compact count/window/history summaries without exposing raw user queries and without mutating memory.

Implemented so far in the active worktree:

- `observations audit` top refs now include `observation_window`:
  - `first_observation_id`
  - `first_observed_at`
  - `latest_observation_id`
  - `latest_observed_at`
- `observations review-candidates` now includes top-level:
  - `observation_count`
  - `candidate_count`
- Each review candidate now includes:
  - the propagated `observation_window`
  - `status_history_summary.transition_count`
  - `status_history_summary.latest_transition`
- Docs updated:
  - `README.md`
  - `docs/hermes-dogfood.md`
- Tests updated in `tests/test_cli.py`:
  - audit regression asserts per-ref observation window.
  - review-candidates regression asserts top-level counts and status history summary.

Verification so far:

- RED confirmed:
  - focused tests failed on missing `observation_window` and top-level `observation_count`.
- GREEN focused:
  - `TMPDIR=$PWD/.tmp-test uv run pytest tests/test_cli.py::test_python_module_cli_observations_audit_reports_frequent_and_stale_refs_without_raw_queries tests/test_cli.py::test_python_module_cli_observations_review_candidates_explains_top_refs_without_mutation_or_raw_queries -q`
  - `2 passed`

Remaining before PR:

1. Run broader/full local verification:
   - focused CLI tests around audit/review-candidates
   - `uv run pytest tests/ -q`
   - `uv run python scripts/check_release_metadata.py`
   - `uv run python scripts/smoke_release_readiness.py`
   - `npm pack --dry-run`
   - `git diff --check`
   - `node --check bin/agent-memory.js`
2. Run real local DB smoke for `observations review-candidates` and verify the new fields exist.
3. Run static diff secret scan.
4. Create PR, watch CI, merge, follow release-sync/publish/published smoke/Hermes QA.
5. After v0.1.40 install, repeat Hermes hook doctor and installed `observations review-candidates` against the existing local DB.

## Next natural slice after this one

After the review-candidates contract is released and dogfooded, continue Priority 5 by either:

1. improving retrieval diagnostics for empty retrieval/high empty ratio, or
2. adding an explicit human review cadence/checklist around candidate reports.

Avoid automatic cleanup/deprecation until the review candidate workflow has been used on real local data for a while.
