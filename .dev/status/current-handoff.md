# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 11:17 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘

> 다음으로 진행할거 해줘

> 다음 거 진행해줘

> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Answer from the "Ready-to-say answer" section, then begin the "Immediate next work" checklist after checking repo state.

## Ready-to-say answer

지금 다음으로 할 일은 agent-memory의 외부 사용자 신뢰를 실제 사용자 피드백/품질 관측으로 이어가는 다음 slice야.

현재 v0.1.17까지는 npm-first CLI, Hermes/Codex/Claude prompt memory injection, approved-only 기본 retrieval, disputed/deprecated forensic 조회, conflict review, Hermes hook fail-closed, retrieval-eval failure triage, OSS trust README/SECURITY/PRIVACY/CONTRIBUTING/community templates, published package smoke까지 완료됐어.

다음 1순위는 공개 이후 사용자가 바로 겪을 수 있는 friction을 줄이는 거야. 추천 slice는 `ci: automate published install smoke matrix` 또는 `feat: add conservative Hermes memory preset` 중 하나야.

진행 순서:
1. `/Users/reddit/Project/agent-memory`에서 main이 `v0.1.17`인지 확인한다.
2. 열린 PR/실패한 Actions가 없는지 확인한다.
3. 다음 slice를 하나 고른다: published install smoke 자동화 또는 Hermes 보수적 preset.
4. 작은 PR로 구현하고 focused/full tests를 통과시킨다.
5. PR/CI/merge 후 auto-release/publish와 published smoke를 확인한다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- If gh auth looks logged out, first ensure HOME is correct:
  - `HOME=/Users/reddit gh auth status`
  - `HOME=/Users/reddit gh auth switch --hostname github.com --user cafitac`
- Remote:
  - `origin` -> `https://github.com/cafitac/agent-memory.git`

Current verified base:

- branch: `main`
- HEAD: `39477b8 chore: release v0.1.17 [skip release]`
- tag: `v0.1.17`
- PR #11 merged: `docs: improve OSS trust and onboarding`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.17`
- npm: `@cafitac/agent-memory@0.1.17`
- PyPI: `cafitac-agent-memory==0.1.17`

Expected local untracked artifacts to preserve:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.tmp-test/`

Do not delete or commit these unless the user explicitly asks.

## What is complete so far

### Distribution and release automation

- npm package and PyPI package are published.
- User-facing install/usage is npm-first:
  - `agent-memory [command]`
  - `npx @cafitac/agent-memory ...`
  - `uvx --from cafitac-agent-memory agent-memory ...`
- main merge auto-release is active:
  - patch bump
  - `[skip release]` release commit
  - annotated tag
  - explicit publish workflow dispatch
- Verified through `v0.1.17`:
  - GitHub Release
  - npm package
  - PyPI package
  - external temp cwd smoke

### Runtime adapter readiness

- Hermes runtime smoke passed historically.
- Codex runtime smoke passed historically.
- Claude Code runtime smoke passed historically.
- Hermes/Codex/Claude prompt surfaces include actual retrieved memory snippets, not only IDs/metadata.
- npm-installed `agent-memory` is the default Hermes hook command path.
- Legacy `python -m agent_memory.api.cli hermes-pre-llm-hook ...` hooks can be migrated to the direct CLI hook.

### Retrieval eval and quality visibility

- `agent-memory eval retrieval` exists.
- JSON output remains the machine-readable default.
- `--format text` exists for human triage.
- Baseline comparators exist:
  - lexical
  - lexical-global
  - source-lexical
  - source-global
- Pass/fail semantics:
  - `missing_expected == 0`
  - `avoid_hits == 0`
- Gating options exist:
  - `--fail-on-regression`
  - `--fail-on-baseline-regression`
  - `--fail-on-baseline-regression-memory-type ...`
- Advisory threshold options exist and do not change exit codes by themselves.

### Memory lifecycle and conflict handling

- Memory statuses exist:
  - `candidate`
  - `approved`
  - `disputed`
  - `deprecated`
- Default retrieval remains approved-only.
- `retrieve --status approved|candidate|disputed|deprecated|all` supports intentional forensic retrieval.
- `review conflicts fact ...` shows same-slot fact lifecycle across statuses.
- Forensic/non-approved retrieval sets verify-first / verification-required signals.
- Hidden alternatives/conflicts can influence risk policy without surfacing stale content by default.

### Always-on hook safety

- Hermes pre-LLM hook fails closed for broken/unavailable DB/schema.
- Hook failure returns `{}` and exit 0 instead of breaking the user prompt flow.
- This matters for always-on memory use.

## Immediate next work: choose the next external-confidence slice

Goal:

After v0.1.17, the repo has a credible external trust surface. The next work should convert that trust into repeated evidence from real install paths or safer always-on defaults.

Recommended next options:

1. `test: automate published install smoke matrix`
   - automate npm/npx/uvx/pipx smoke checks in a script or workflow
   - verify exact published package versions outside the source checkout
   - fail clearly on launcher/runtime resolver regressions

2. `feat: add Hermes conservative memory preset`
   - provide a named low-risk preset for always-on memory injection
   - keep prompt budgets small
   - approved-only retrieval by default
   - document how users can opt into wider context

3. `ci: run retrieval eval advisory report on main`
   - run checked-in retrieval fixtures on main as an advisory signal
   - publish/report failures without prematurely blocking docs-only releases
   - keep JSON/text reports available for triage

Suggested first pick:

```bash
cd /Users/reddit/Project/agent-memory
HOME=/Users/reddit gh auth switch --hostname github.com --user cafitac || true
git checkout main
HOME=/Users/reddit GIT_TERMINAL_PROMPT=0 git pull --ff-only
git checkout -b test/published-install-smoke-matrix
```

Acceptance for the next slice:
- local focused tests pass
- full tests pass
- CI passes on PR
- release workflow still avoids recursive publish loops
- published-install smoke remains verified after merge if a release is cut

## Sequential roadmap to final goal

Final goal:

agent-memory should be credible as an OSS default memory layer for Hermes, Codex, and Claude Code: safe to install, safe to leave on, measurable, debuggable, and conservative by default.

### Priority 1 — Retrieval quality measurement and triage

Outcome:

- Users can see whether retrieval is good, where it fails, and whether changes regress quality.

Next PR candidates:

1. `feat: expand retrieval quality fixtures and triage`
2. `feat: add retrieval eval grouped corpus reports`
3. `ci: run retrieval eval advisory report on main`

Acceptance:

- Fixture corpus covers realistic memory failures.
- Text report makes failures actionable without reading raw JSON.
- CI can run eval advisories without blocking releases prematurely.

### Priority 2 — Always-on hook safety and conservative defaults

Outcome:

- A new user can leave agent-memory enabled in Hermes without prompt breakage, latency surprises, or excessive context pollution.

Next PR candidates:

1. `feat: add Hermes conservative memory preset`
2. `test: cover hook timeout and prompt budget fallbacks`
3. `docs: document always-on memory safety policy`

Acceptance:

- Prompt budget defaults are conservative.
- Hook failure modes are documented and tested.
- Debug/verbose modes are opt-in, not default.
- Latency-sensitive surfaces have clear fallback behavior.

### Priority 3 — Fresh-user onboarding matrix automation

Outcome:

- Published package releases prove that a fresh external user can install and use memory with Hermes/Codex/Claude surfaces.

Next PR candidates:

1. `test: automate published install smoke matrix`
2. `docs: add first-run memory layer setup guide`
3. `ci: add optional post-publish smoke workflow`

Acceptance:

- npm / npx / uvx surfaces are tested outside the repo cwd.
- Hermes bootstrap/doctor/hook flow is tested.
- Codex/Claude prompt wrappers are tested in dry-run or authenticated smoke mode.
- Published package smoke avoids repo-local import leakage.

### Priority 4 — Conflict, obsolete, and truth lifecycle

Outcome:

- Users can see why a memory is trusted, replaced, disputed, or deprecated.

Next PR candidates:

1. `feat: add memory transition history`
2. `feat: add supersedes/replaces relation for facts`
3. `feat: add conflict review explanations`

Acceptance:

- Status transitions record reason/evidence.
- Deprecated/disputed memories remain inspectable but do not enter default prompts.
- Replacement chains are visible.
- Review UX supports safe operator decisions.

### Priority 5 — Long-run dogfood and noise monitoring

Outcome:

- The project accumulates evidence that agent-memory improves real agent sessions instead of adding noise.

Next PR candidates:

1. `feat: add local dogfood retrieval observation log`
2. `feat: add noisy memory audit command`
3. `docs: add dogfood review cadence`

Acceptance:

- No secrets are logged.
- Observations are local by default.
- Users can inspect which memory snippets were injected and why.
- Irrelevant injected memories can be reviewed and deprecated.

## Known caveats and commands to avoid

- Do not commit or delete pre-existing local artifacts unless explicitly asked.
- For published package smoke, do not run inside repo cwd; use `/tmp/...` external cwd.
- Unset package-path overrides before published smoke:
  - `unset AGENT_MEMORY_PYTHON_EXECUTABLE`
- If HOME was changed by a smoke script, use `HOME=/Users/reddit` for gh/git operations.
- Do not print or save GitHub tokens or credentials.
- Historical denied one-liners should not be blindly retried:
  - `.venv/bin/python -c 'import agent_memory...'`
  - `uv run python -c 'import agent_memory; print(agent_memory.__file__)'`

## Useful verification snippets

Published package smoke shape:

```bash
unset AGENT_MEMORY_PYTHON_EXECUTABLE
SMOKE_DIR=$(mktemp -d /tmp/agent-memory-published-smoke.XXXXXX)
cd "$SMOKE_DIR"
npm exec --yes --package '@cafitac/agent-memory@0.1.15' agent-memory -- --help
npx --yes '@cafitac/agent-memory@0.1.15' --help
uvx --refresh --from 'cafitac-agent-memory==0.1.15' agent-memory retrieve --help
```

Hermes local check shape:

```bash
agent-memory bootstrap ~/.agent-memory/memory.db
agent-memory doctor ~/.agent-memory/memory.db
hermes hooks doctor
agent-memory hermes-context ~/.agent-memory/memory.db "What should I remember?" --preferred-scope user:default --top-k 3
```
