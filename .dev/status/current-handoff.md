# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 10:29 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘

> 다음으로 진행할거 해줘

> 다음 거 진행해줘

> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Answer from the "Ready-to-say answer" section, then begin the "Immediate next work" checklist after checking repo state.

## Ready-to-say answer

지금 다음으로 할 일은 agent-memory를 외부 사용자가 Hermes/Codex/Claude의 주 memory layer로 믿고 켤 수 있게 만드는 품질 강화의 다음 slice야.

현재 v0.1.15까지는 npm-first CLI, Hermes/Codex/Claude prompt memory injection, approved-only 기본 retrieval, disputed/deprecated forensic 조회, conflict review, Hermes hook fail-closed, published package smoke까지 완료됐어.

다음 1순위는 retrieval quality를 실제 사용 패턴으로 더 체계적으로 측정하는 거야. 구체적으로는 retrieval eval fixture corpus를 확장하고, noisy/irrelevant/stale/conflict 케이스를 더 많이 넣고, text report가 실패 원인을 바로 triage할 수 있게 만드는 PR을 만들면 돼.

진행 순서:
1. `~/Project/agent-memory`에서 main이 `v0.1.15`인지 확인한다.
2. 새 브랜치 `feat/retrieval-quality-corpus-and-triage`를 만든다.
3. retrieval eval fixture corpus를 실제 사용 패턴 중심으로 확장한다.
4. failure detail에 retrieved snippet / expected snippet / avoid snippet / policy signal을 더 명확히 보여준다.
5. focused/full tests를 통과시킨다.
6. PR/CI/merge 후 auto-release/publish를 확인한다.
7. 외부 temp cwd에서 published smoke를 다시 수행한다.

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
- HEAD: `47c6f2e chore: release v0.1.15 [skip release]`
- tag: `v0.1.15`
- PR #9 merged: `feat: add status-aware memory review surfaces`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.15`
- npm: `@cafitac/agent-memory@0.1.15`
- PyPI: `cafitac-agent-memory==0.1.15`

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
- Verified through `v0.1.15`:
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

## Immediate next work: retrieval quality corpus and triage surface

Goal:

Make retrieval quality measurable enough that external users can trust agent-memory as a default memory layer, not just a demo.

Recommended branch:

```bash
cd /Users/reddit/Project/agent-memory
HOME=/Users/reddit gh auth switch --hostname github.com --user cafitac || true
git checkout main
HOME=/Users/reddit GIT_TERMINAL_PROMPT=0 git pull --ff-only
git checkout -b feat/retrieval-quality-corpus-and-triage
```

Work items:

1. Expand retrieval eval fixtures around real OSS-agent memory risks:
   - noisy irrelevant memories
   - stale but semantically close memories
   - disputed/deprecated conflict alternatives
   - cross-scope leakage
   - procedure-vs-fact confusion
   - episode recency/scope tie-breakers
   - prompt-budget pressure where only top-k snippets fit

2. Improve text triage output:
   - done in this slice: failed-task text report now shows retrieved snippets, expected snippets, avoid-hit snippets, and top-memory policy signals
   - JSON per-task results now include `retrieved_details`, `expected_details`, and `avoid_hit_details`
   - next refinements can add richer conflict/lifecycle selector descriptions and more fixture families
   - make it obvious whether the failure is ranking, filtering, scope, lifecycle, or fixture-data quality

3. Add tests first:
   - RED tests in `tests/test_retrieval_evaluation.py`
   - fixture files under `tests/fixtures/retrieval_eval/`
   - tests should assert JSON contract and text report snippets

4. Keep machine contract stable:
   - do not break existing JSON fields
   - add fields only if needed
   - preserve `pass` external serialization
   - preserve JSON as default output

5. Verify:

```bash
unset AGENT_MEMORY_PYTHON_EXECUTABLE
TMPDIR=/Users/reddit/Project/agent-memory/.tmp-test uv run pytest tests/test_retrieval_evaluation.py -q
TMPDIR=/Users/reddit/Project/agent-memory/.tmp-test uv run pytest tests/test_cli.py tests/test_hermes_adapter.py tests/test_prompt_wrapper_scripts.py -q
TMPDIR=/Users/reddit/Project/agent-memory/.tmp-test uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
git diff --check
```

6. PR/release:

```bash
git add <changed files>
git commit -m "feat: expand retrieval quality fixtures and triage"
HOME=/Users/reddit GIT_TERMINAL_PROMPT=0 git push -u origin HEAD
HOME=/Users/reddit gh pr create --repo cafitac/agent-memory --title "feat: expand retrieval quality fixtures and triage" --body-file /tmp/agent-memory-retrieval-quality-pr.md
HOME=/Users/reddit gh pr checks <PR_NUMBER> --watch
HOME=/Users/reddit gh pr merge <PR_NUMBER> --repo cafitac/agent-memory --squash --delete-branch
HOME=/Users/reddit GIT_TERMINAL_PROMPT=0 git checkout main
HOME=/Users/reddit GIT_TERMINAL_PROMPT=0 git pull --ff-only
```

7. After merge, verify auto-release/publish and external published smoke.

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
