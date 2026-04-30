# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 00:20 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.34까지 배포/Hermes QA가 완료됐고, 지금은 Priority 5 dogfood/noise monitoring 첫 slice인 v0.1.35 후보 작업 중이야. 현재 브랜치는 `feat/retrieval-observation-log`이고, 목표는 Hermes/CLI retrieval이 어떤 memory를 주입했는지 secret-safe local observation log로 남겨 이후 noisy memory audit의 기반을 만드는 거야.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Verified base before this slice:

- latest completed release: `v0.1.34`
- v0.1.34 included published smoke propagation retry/backoff, release-sync PR CI dispatch, and read-only relation graph inspect CLI.
- local Hermes hook uses `/Users/reddit/.agent-memory/runtime/v0.1.34/.venv/bin/agent-memory` against `/Users/reddit/.agent-memory/memory.db`.

Active slice/worktree:

- branch: `feat/retrieval-observation-log`
- worktree: `/Users/reddit/Project/agent-memory/.worktrees/retrieval-observation-log`
- intended release after merge: likely `v0.1.35`

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` while scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## What is complete through v0.1.34

### Distribution and release automation

- npm package and PyPI package are published from the same versioned source.
- npm-first user install path is documented and verified.
- Publish workflow gates GitHub Release creation on `published-install-smoke` after npm/PyPI publish.
- Published smoke uploads JSON diagnostics artifacts.
- v0.1.34 distinguishes normal retry budget from propagation/transient resolver failure budget and adds registry probe diagnostics.
- Protected `main` fallback is automated and rerun-idempotent.
- release-sync fallback now dispatches `ci.yml` on the bot-created release-sync branch and comments/step-summarizes that handoff.

### Runtime adapter readiness

- Hermes bootstrap/doctor/install flow exists and defaults to the conservative preset.
- This local Hermes setup has agent-memory enabled via `/Users/reddit/.agent-memory/runtime/v0.1.34/.venv/bin/agent-memory`.
- Hermes hook fails closed: unavailable DB/schema returns `{}` and exit 0 instead of breaking prompt flow.
- Conservative preset remains default: small prompt budgets, one top memory, no alternative-memory detail, no reason-code noise.
- `--preset balanced` is explicit opt-in for more context/noise.

### Truth lifecycle, eval, and graph foundation

- Normal retrieval is approved-only by default.
- Candidate/disputed/deprecated facts remain available only behind explicit forensic/review surfaces.
- `memory_status_transitions` records status changes.
- `review history`, `review supersede`, `review replacements`, and `review explain` exist.
- Retrieval eval calls the real retrieval path but suppresses retrieval bookkeeping writes.
- `agent-memory graph inspect <db_path> <start_ref> --depth N --limit N` traverses stored `Relation` edges read-only and does not mutate memory state.

## Current slice: local retrieval observation log

Goal:

- Build a local-only, secret-safe observation log that records what retrieval injected during real dogfood use.
- This is the first Priority 5 dogfood/noise monitoring slice and should feed later noisy-memory audit commands.

Implemented so far:

- New SQLite table `retrieval_observations`.
- New model `RetrievalObservation`.
- New storage APIs:
  - `record_retrieval_observation(...)`
  - `list_retrieval_observations(...)`
- `retrieve_memory_packet(...)` accepts:
  - `observation_surface`
  - `observation_metadata`
- `agent-memory retrieve ... --observe <surface>` records an opt-in observation.
- Hermes pre-LLM hook records an observation automatically with surface `hermes-pre-llm-hook`.
- New CLI:
  - `agent-memory observations list <db_path> --limit 50`

Secret-safety contract:

- raw query text is not stored.
- stores `query_sha256` and a short redacted preview.
- redacts secret-like assignments such as password/token/api_key/secret/credential/connection_string.
- stores selected memory refs, top memory ref, response mode, statuses, preferred scope, and small metadata.

Files changed:

- `src/agent_memory/core/models.py`
- `src/agent_memory/storage/schema.sql`
- `src/agent_memory/storage/sqlite.py`
- `src/agent_memory/core/retrieval.py`
- `src/agent_memory/integrations/hermes_hooks.py`
- `src/agent_memory/api/cli.py`
- `tests/test_cli.py`
- `README.md`
- `docs/hermes-dogfood.md`
- `.dev/status/current-handoff.md`

Current focused verification already passed:

```bash
uv run pytest tests/test_cli.py::test_python_module_cli_retrieve_observe_records_secret_safe_local_observation tests/test_cli.py::test_python_module_cli_hermes_pre_llm_hook_outputs_context_for_hermes_shell_hook_payload -q
# 2 passed

uv run pytest tests/test_cli.py tests/test_retrieval_evaluation.py -q
# 83 passed
```

## Remaining work for this slice

1. Run real smoke for observation CLI and Hermes hook from the worktree.
2. Run full verification:
   ```bash
   uv run pytest tests/ -q
   uv run python scripts/check_release_metadata.py
   uv run python scripts/smoke_release_readiness.py
   npm pack --dry-run
   git diff --check
   node --check bin/agent-memory.js
   ```
3. Run static diff secret scan and confirm finding_count 0.
4. Commit branch and open PR.
5. Watch PR CI, merge when green.
6. Verify auto-release/release-sync/publish for likely v0.1.35.
7. Verify GitHub Release/npm/PyPI/published smoke artifact.
8. Install pinned Hermes runtime v0.1.35 and run Hermes QA.
9. Cleanup worktree/branch and update durable memory.

## Next likely slice after this

After observation logging is released and dogfooded, build a read-only noisy memory audit command over `retrieval_observations`, for example frequently injected memory refs, surprising scopes, high hidden-alternative counts, and stale/deprecated-nearby risks.
