# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 23:39 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.53까지 배포/Hermes QA가 완료됐고, Stage D / PR D3 `consolidation explain` read-only candidate explanation CLI까지 완료됐다. 다음 제품 slice는 Stage E / PR E1 manual reviewed promotion이지만, 현재 우선순위는 사용자가 지적한 GitHub Actions 비용/시간 문제 때문에 publish workflow 최적화 PR이다. 작업 branch는 `ci/optimize-publish-workflow`이며, 목표는 `publish.yml`을 빠른 publish path로 만들고 slow real-registry install smoke를 opt-in/manual gate로 분리하는 것이다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current worktree:

- `/Users/reddit/Project/agent-memory/.worktrees/publish-workflow-optimization`
- Branch: `ci/optimize-publish-workflow`
- Base: `origin/main`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author for this repo should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.53`
- v0.1.53 added read-only `agent-memory consolidation explain`.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.53/.venv/bin/agent-memory`.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Active workflow optimization slice

User concern:

- Recent `publish.yml` runs sometimes take 10+ minutes.
- Repeating full publish/smoke work for many small PRs risks burning GitHub Actions minutes.
- Desired direction: either optimize the workflow or use branch flow so publish only happens when dev is merged to main and external install checks are needed.

Chosen PR-sized fix:

- Keep PR/branch validation on `ci.yml`.
- Keep release publish on version tags/manual dispatch only.
- Add `auto-release.yml` `paths-ignore` for docs/workflow-only pushes so this optimization PR itself does not need to cut a package release.
- Remove full `uv run pytest tests/ -q` from `publish.yml` because main/release-sync CI already ran it.
- Keep lightweight publish safety in `publish.yml`: release metadata validation, release-readiness smoke, Python dist build, npm dry-run, npm/PyPI publish, GitHub Release creation.
- Make slow real-registry `published-install-smoke` opt-in via `run_published_install_smoke` input, default `false`.
- Auto-release dispatches `publish.yml` with `-f run_published_install_smoke=false`.
- Keep standalone `published-install-smoke.yml` as the manual high-confidence external-install gate.

Current modified files in the optimization worktree:

- `.github/workflows/publish.yml`
- `.github/workflows/auto-release.yml`
- `tests/test_published_install_smoke.py`
- `README.md`
- `docs/install-smoke.md`
- `.dev/status/current-handoff.md`

RED/GREEN state:

- Added tests for:
  - published install smoke is opt-in in `publish.yml`
  - `publish.yml` does not repeat the full pytest suite
  - `auto-release.yml` dispatches fast publish by default
- RED confirmed: all three tests failed before workflow changes.
- GREEN confirmed: those three tests passed after workflow changes.

Suggested remaining verification before PR:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_published_install_smoke.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
git diff --check
npm pack --dry-run
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
```

After merge, verify:

- PR CI is green.
- Main CI is green.
- Auto-release should be skipped for this docs/workflow-only PR because `auto-release.yml` now has `paths-ignore`; if an unexpected release run still appears, inspect before dispatching publish.
- Run manual registry install smoke only when needed:

```bash
gh workflow run published-install-smoke.yml --repo cafitac/agent-memory -f version=<version> -f attempts=6 -f propagation_attempts=12 -f propagation_delay_seconds=10
```

## Canonical roadmap position

The durable north-star is:

- not a curated facts DB that only stores important-looking items at ingestion time
- a graph-based memory consolidation runtime inspired by human memory
- experiences leave lightweight traces
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and retrieval usefulness
- weak traces decay/expire/collapse into summaries
- strong trace clusters consolidate into semantic, episodic, procedural, and preference memories
- prompt-time retrieval remains explainable through provenance, status history, supersession, and graph relations

The PR ladder in `.dev/roadmap/roadmap-v0.md` is the canonical product sequence unless explicitly revised:

1. Stage A: lock plan and dogfood baseline
2. Stage B: trace layer without automatic memory creation
3. Stage C: activation and reinforcement signals
4. Stage D: consolidation candidates before mutation
   - D1/D2 candidates report done in v0.1.52
   - D3 candidate explanation details done in v0.1.53
5. Stage E: reviewed promotion into long-term memory
6. Stage F: retrieval uses consolidation signals conservatively
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness

## Next product slice after workflow optimization

Stage E / PR E1: manual consolidation promotion for semantic facts.

E1 should remain explicit-human-action only:

- promote one reviewed candidate into a semantic Fact
- default status should be candidate unless the user explicitly approves
- preserve provenance to candidate/trace evidence
- default retrieval remains approved-only
- no automatic promotion, no background consolidation apply mode, no retrieval ranking changes
- conflict/supersession preflight can be a later PR E4 unless the minimum E1 implementation needs a conservative block
