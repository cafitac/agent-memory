# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 01:10 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.36까지 배포/Hermes QA가 완료됐고, 지금은 Priority 5 dogfood/noise monitoring의 다음 slice인 read-only observation audit 작업 중이야. 현재 브랜치는 `feat/observations-audit`, worktree는 `/Users/reddit/Project/agent-memory/.worktrees/observations-audit`이고, 목표는 기존 retrieval observation log를 바탕으로 자주 주입되는 memory ref, surface/scope 분포, 빈 retrieval, deprecated/disputed/missing ref 신호를 raw query 없이 요약하는 `agent-memory observations audit` CLI를 추가하는 거야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- latest completed release: `v0.1.36`
- v0.1.36 included secret-safe local retrieval observation logging and lazy migration for existing DBs without `retrieval_observations`.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.36/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.

Active slice/worktree:

- branch: `feat/observations-audit`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/observations-audit`
- intended release after merge: likely `v0.1.37`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Current slice: read-only retrieval observation audit

Goal:

- Add a local-only, secret-safe, read-only audit report over `retrieval_observations`.
- Summarize dogfood/noise signals before changing ranking, graph traversal, or mutating memory cleanup.

Implemented so far in the active worktree:

- New CLI:
  - `agent-memory observations audit <db_path> --limit 200 --top 10 --frequent-threshold 3`
- JSON output includes:
  - `kind: retrieval_observation_audit`
  - `read_only: true`
  - `observation_count`
  - `surface_counts`
  - `preferred_scope_counts`
  - `empty_retrieval_count`
  - `top_memory_refs[]` with `memory_ref`, `injection_count`, `current_status`, `signals`, and sample observation ids
- Current signals:
  - `frequently_injected`
  - `current_status_not_approved`
- Storage helper added:
  - `get_memory_status(db_path, memory_type=..., memory_id=...)`
- Docs updated:
  - `README.md`
  - `docs/hermes-dogfood.md`

Secret-safety contract:

- audit uses existing observation rows and does not read or emit raw query text.
- output contains counts, memory refs, statuses, and observation ids only.
- keep this data local unless intentionally exported.

Verification so far:

- RED confirmed before implementation:
  - `agent-memory observations audit` failed with argparse invalid choice.
- GREEN focused:
  - `uv run pytest tests/test_cli.py::test_python_module_cli_observations_audit_reports_frequent_and_stale_refs_without_raw_queries -q`
  - `1 passed`
- Focused regression group:
  - `uv run pytest tests/test_cli.py::test_python_module_cli_observations_audit_reports_frequent_and_stale_refs_without_raw_queries tests/test_cli.py::test_python_module_cli_retrieve_observe_records_secret_safe_local_observation tests/test_cli.py::test_python_module_cli_observations_list_migrates_existing_database_without_observation_table -q`
  - `3 passed`
- CLI help smoke:
  - `uv run python -m agent_memory.api.cli observations audit --help`
  - `uv run python -m agent_memory.api.cli observations list --help`
  - both exit 0.

Remaining before PR:

1. Run full local verification:
   - `uv run pytest tests/ -q`
   - `uv run python scripts/check_release_metadata.py`
   - `uv run python scripts/smoke_release_readiness.py`
   - `npm pack --dry-run`
   - `git diff --check`
   - `node --check bin/agent-memory.js`
2. Run real smoke for `observations audit` on a temp DB and confirm no raw secret-like query text appears.
3. Run static diff secret scan.
4. Create PR, watch CI, merge, follow release-sync/publish/published smoke/Hermes QA.

## Next natural slice after this one

After this audit slice is released and Hermes QA passes, the next likely Priority 5 step is dogfood cadence refinement: use the audit report over real Hermes observations to decide whether ranking/scope filters need adjustment. Avoid mutating cleanup or broad graph retrieval until the read-only signals have been observed in real use.
