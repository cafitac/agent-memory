# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 10:21 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.38까지 배포/Hermes QA가 완료됐고, 현재는 Priority 5 dogfood/noise monitoring의 다음 slice인 read-only observation review candidate report를 진행 중이야. 브랜치는 `feat/observation-review-candidates`, worktree는 `/Users/reddit/Project/agent-memory/.worktrees/observation-review-candidates`야. 목표는 `observations audit`의 top injected refs를 `review explain`, replacement/supersedes chain, `graph inspect` 요약과 copy-paste follow-up commands로 연결하는 거야. 자동 cleanup/mutation은 하지 않고 forensic review만 강화한다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- latest completed release: `v0.1.38`
- v0.1.38 removed observation query previews, skipped Hermes doctor/test synthetic observations, added audit quality warnings, and verified a real Hermes turn used an agent-memory fact.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.38/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.
- root checkout was clean on `main...origin/main` except local-only untracked state.
- open PRs were `[]`.

Active slice/worktree:

- branch: `feat/observation-review-candidates`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/observation-review-candidates`
- intended release after merge: likely `v0.1.39`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Current slice: observation review candidates

Goal:

- Keep dogfood/noise monitoring read-only.
- Turn `observations audit` top refs into actionable forensic review candidates.
- Help operators see lifecycle status, replacement chains, and relation graph hints without exposing raw user queries or mutating memory.

Implemented so far in the active worktree:

- New CLI:
  - `agent-memory observations review-candidates <db_path> --limit N --top N --frequent-threshold N`
- Output contract:
  - `kind: retrieval_observation_review_candidates`
  - `read_only: true`
  - nested `observation_audit` payload
  - `candidates[]` derived from `top_memory_refs`
  - fact refs include `review_explain` payload equivalent to `review explain fact`
  - graph summary includes depth-1 relation neighbor refs and edge count
  - signals include existing audit signals plus `has_replacement` and `has_graph_relations` when applicable
  - copy-paste commands for `review explain`, `review replacements`, and `graph inspect`
- Refactored CLI review explain to reuse `_fact_review_explanation_payload`.
- Docs updated:
  - `README.md`
  - `docs/hermes-dogfood.md`
- Test added in `tests/test_cli.py`:
  - `test_python_module_cli_observations_review_candidates_explains_top_refs_without_mutation_or_raw_queries`

Verification so far:

- RED confirmed:
  - `observations review-candidates` was not a valid subcommand.
- GREEN focused:
  - `uv run pytest tests/test_cli.py::test_python_module_cli_observations_review_candidates_explains_top_refs_without_mutation_or_raw_queries -q`
  - `1 passed`
- Broader focused:
  - audit, review-candidates, review explain, graph inspect CLI tests
  - `4 passed`
- Help smoke:
  - `PYTHONPATH=src uv run python -m agent_memory.api.cli observations review-candidates --help`
  - exit 0

Remaining before PR:

1. Run full local verification:
   - `uv run pytest tests/ -q`
   - `uv run python scripts/check_release_metadata.py`
   - `uv run python scripts/smoke_release_readiness.py`
   - `npm pack --dry-run`
   - `git diff --check`
   - `node --check bin/agent-memory.js`
2. Run real temp-DB smoke for `observations review-candidates` and confirm no raw secret-like query text appears.
3. Run static diff secret scan.
4. Create PR, watch CI, merge, follow release-sync/publish/published smoke/Hermes QA.
5. After v0.1.39 install, repeat Hermes hook doctor and run installed `observations review-candidates` against the existing local DB.

## Next natural slice after this one

After the read-only review candidate report is released and dogfooded, continue gathering real observation data. If enough non-synthetic observations accumulate, the next likely work is retrieval quality diagnostics for high empty-retrieval ratios or scope/ranking misses. Avoid automatic cleanup/deprecation until the review candidate workflow has been used on real local data.
