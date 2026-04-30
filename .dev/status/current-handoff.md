# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 01:55 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.37까지 배포/Hermes QA가 완료됐고, 현재는 실제 dogfood QA에서 발견된 observation 데이터 품질 이슈를 고치는 slice를 진행 중이야. 브랜치는 `fix/observation-dogfood-quality`, worktree는 `/Users/reddit/Project/agent-memory/.worktrees/observation-dogfood-quality`야. 목표는 query preview 제거, `hermes hooks doctor/test` synthetic pre-LLM payload가 dogfood observation을 오염시키지 않게 하기, audit에 데이터 부족/empty retrieval 품질 경고를 추가하기, 그리고 기존 DB에서 `memory_status_transitions` table이 없을 때 approve/review가 lazy migration 되도록 하는 거야. 실제 Hermes가 agent-memory에서 가져온 정보를 답변에 사용하는 E2E도 확인했어.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- latest completed release: `v0.1.37`
- v0.1.37 added read-only `agent-memory observations audit` and was published to GitHub/npm/PyPI.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.37/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.

Active slice/worktree:

- branch: `fix/observation-dogfood-quality`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/observation-dogfood-quality`
- intended release after merge: likely `v0.1.38`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Current slice: observation dogfood data quality

Goal:

- Keep observation telemetry useful for real dogfood QA.
- Avoid storing prompt-like query previews.
- Avoid synthetic hook doctor/test payloads polluting observation audits.
- Make audit explicitly report low-signal data states.
- Ensure existing DBs lazily migrate missing lifecycle tables encountered during real local QA.

Implemented so far in the active worktree:

- `record_retrieval_observation` now writes `query_preview = None` for new observations.
- Hermes pre-LLM hook detects the deterministic `hermes hooks doctor/test` payload:
  - session_id `test-session`
  - user_message `What is the weather?`
  - empty conversation_history
  - is_first_turn true
  - model `gpt-4`
  - platform `cli`
- Synthetic doctor/test payloads still exercise hook context injection but do not write dogfood observation rows.
- `observations audit` now returns:
  - `empty_retrieval_ratio`
  - `quality_warnings`
    - `no_observations`
    - `low_observation_count`
    - `high_empty_retrieval_ratio`
- `memory_status_transitions` now has lazy/idempotent schema ensure used by initialize, status update, and status history paths.
- Docs updated:
  - `README.md`
  - `docs/hermes-dogfood.md`
- Tests added/updated in `tests/test_cli.py`:
  - query preview is absent from observation list output
  - audit reports low-signal empty retrievals
  - approve-fact migrates existing DBs missing `memory_status_transitions`
  - Hermes hook synthetic doctor payload skips observation write
  - Hermes hook context includes retrieved memory content when line budget allows

Verification so far:

- RED confirmed:
  - query_preview still present
  - synthetic doctor payload wrote observation rows
  - audit lacked `empty_retrieval_ratio`/`quality_warnings`
  - existing DB without `memory_status_transitions` failed approve with sqlite OperationalError
- GREEN focused:
  - `uv run pytest tests/test_cli.py::test_python_module_cli_approve_fact_migrates_existing_database_without_status_transition_table tests/test_cli.py::test_python_module_cli_retrieve_observe_records_secret_safe_local_observation tests/test_cli.py::test_python_module_cli_observations_audit_reports_low_signal_empty_retrievals tests/test_cli.py::test_python_module_cli_hermes_pre_llm_hook_skips_synthetic_doctor_observation tests/test_cli.py::test_python_module_cli_hermes_pre_llm_hook_injects_retrieved_memory_context -q`
  - `5 passed`

Live local Hermes QA already confirmed on v0.1.37 runtime before this patch:

- Created a temporary approved fact in `/Users/reddit/.agent-memory/memory.db` with marker `AM_LIVE_E2E_1777567838` scoped to `/Users/reddit/Project/agent-memory`.
- Direct hook check confirmed:
  - `direct_hook_contains_marker=True`
  - `direct_hook_contains_agent_memory_context=True`
  - `direct_hook_contains_retrieved_fact=True`
- Actual Hermes command confirmed the model used injected memory:
  - `hermes --accept-hooks -z "What is the Hermes live E2E QA marker? Return only the marker and nothing else."`
  - output contained `AM_LIVE_E2E_1777567838`
- Cleanup done:
  - test fact id 2 deprecated with reason `live E2E QA cleanup`
  - `review explain` showed `visible_in_default_retrieval: false`
- During live QA, an existing DB migration gap was discovered:
  - approve failed until `agent-memory init ~/.agent-memory/memory.db` created `memory_status_transitions`
  - this is now covered by the new lazy migration test/fix.

Remaining before PR:

1. Run broader focused group and full local verification:
   - `uv run pytest tests/ -q`
   - `uv run python scripts/check_release_metadata.py`
   - `uv run python scripts/smoke_release_readiness.py`
   - `npm pack --dry-run`
   - `git diff --check`
   - `node --check bin/agent-memory.js`
2. Run real smoke for observation list/audit on a temp DB and confirm query_preview is null and no raw secret-like text appears.
3. Run static diff secret scan.
4. Create PR, watch CI, merge, follow release-sync/publish/published smoke/Hermes QA.
5. After v0.1.38 install, repeat Hermes hook doctor and one real E2E check with the new runtime.

## Next natural slice after this one

After this data-quality fix is released and Hermes QA passes, continue dogfood/noise monitoring using the cleaner audit data. Avoid mutating cleanup or broader graph retrieval until there are enough real, non-synthetic observations to justify ranking/scope changes.
