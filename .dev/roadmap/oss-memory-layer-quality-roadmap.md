# OSS Default Memory Layer Quality Roadmap

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-30 10:16 KST

## Final objective

Make `agent-memory` credible as an open-source default memory layer for Hermes, Codex, and Claude Code.

Credible means:

- easy to install through npm/npx and Python surfaces
- safe to leave enabled in an agent runtime
- conservative by default: approved memory only, no disputed/deprecated prompt injection unless explicitly requested
- measurable retrieval quality with regression visibility
- debuggable conflict/staleness lifecycle
- prompt-budget, latency, and failure-mode behavior that does not break the host agent
- published release smoke from outside the repo cwd

## Baseline already achieved through v0.1.15

### Packaging and release

- npm package: `@cafitac/agent-memory@0.1.15`
- PyPI package: `cafitac-agent-memory==0.1.15`
- GitHub Release: `v0.1.15`
- main merge auto-release is active and verified:
  - patch bump
  - `[skip release]` commit
  - tag
  - publish workflow dispatch
  - npm/PyPI/GitHub Release publish

### Runtime attach surfaces

- Direct CLI surface is the user-facing default:
  - `agent-memory [command]`
- npm wrapper uses the packaged version and avoids user-facing `uv run` onboarding.
- Hermes hook default command is direct CLI:
  - `agent-memory hermes-pre-llm-hook ...`
- Hermes/Codex/Claude prompt surfaces include actual retrieved snippets.
- Local and published smokes verified that prompt output includes approved memory content.

### Retrieval eval and triage

- `agent-memory eval retrieval` exists.
- JSON report is the default machine contract.
- Text report exists via `--format text`.
- Current/baseline/delta summaries exist.
- Baseline modes exist:
  - lexical
  - lexical-global
  - source-lexical
  - source-global
- Soft advisory thresholds and hard gate flags exist.

### Lifecycle and forensic retrieval

- Status model exists:
  - candidate
  - approved
  - disputed
  - deprecated
- Default retrieval is approved-only.
- Forensic retrieval exists:
  - `retrieve --status approved|candidate|disputed|deprecated|all`
- Conflict review exists for fact slots:
  - `review conflicts fact DB SUBJECT PREDICATE --scope SCOPE`
- Forensic/non-approved retrieval sets verification-required / verify-first signals.

### Always-on safety

- Hermes pre-LLM hook fails closed.
- Broken DB/schema returns `{}` and exit 0 instead of breaking host-agent prompting.

## Priority 1: Retrieval quality corpus and triage

### Goal

Make retrieval quality visible enough that maintainers and users can trust changes.

### Why this is first

A memory layer is dangerous if it silently injects stale or irrelevant memory. Before adding more intelligence, we need robust measurement of retrieval behavior.

### Next PR: `feat: expand retrieval quality fixtures and triage`

#### Scope

- Add fixture families for:
  - noisy irrelevant memory
  - stale but semantically similar memory
  - same subject/predicate conflict
  - disputed/deprecated alternatives
  - cross-scope leakage
  - procedure vs fact confusion
  - episode recency/scope ranking
  - prompt budget pressure
- Extend text report failure details to show:
  - retrieved snippets
  - expected selectors/snippets
  - avoid-hit snippets
  - memory status
  - scope
  - conflict/hidden-alternative signals
  - likely failure category: ranking/filtering/scope/lifecycle/fixture

#### Files likely touched

- `tests/test_retrieval_evaluation.py`
- `tests/fixtures/retrieval_eval/**`
- `src/agent_memory/core/retrieval_eval.py`
- `src/agent_memory/api/cli.py` only if CLI report options change
- `README.md` if user-facing eval examples change
- `.dev/status/current-handoff.md` after release

#### Verification

```bash
unset AGENT_MEMORY_PYTHON_EXECUTABLE
TMPDIR=/Users/reddit/Project/agent-memory/.tmp-test uv run pytest tests/test_retrieval_evaluation.py -q
TMPDIR=/Users/reddit/Project/agent-memory/.tmp-test uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
git diff --check
```

#### Acceptance

- Existing JSON report consumers remain compatible.
- Text report is more actionable for failures.
- New fixtures fail on obvious stale/noisy regressions.
- Default retrieval still remains approved-only.

## Priority 2: Conservative always-on runtime defaults

### Goal

A new user can leave agent-memory enabled without surprising prompt pollution, latency, or crashes.

### Next PR: `feat: add Hermes conservative memory preset`

#### Scope

- Define default prompt budget policy:
  - small top-k
  - max prompt lines/chars
  - concise snippets
  - no debug metadata unless verbose/debug mode
- Add hook timeout/fallback tests where feasible.
- Ensure hook failures never modify the user prompt on error.
- Document default vs debug behavior.

#### Files likely touched

- `src/agent_memory/adapters/hermes.py`
- `src/agent_memory/integrations/hermes_hooks.py`
- `src/agent_memory/api/cli.py`
- `tests/test_hermes_adapter.py`
- `tests/test_cli.py`
- `README.md`
- `docs/install-smoke.md`

#### Acceptance

- Default hook output is small and stable.
- Debug information is opt-in.
- Failure modes are covered by tests.
- `hermes hooks doctor` remains part of recommended verification.

## Priority 3: Fresh-user onboarding matrix automation

### Goal

Every release should prove that a fresh external user can install and use the package without repo-local leakage.

### Next PR: `test: automate published install smoke matrix`

#### Scope

- Add a documented or scriptable smoke matrix for:
  - npm exec
  - npx
  - uvx
  - direct installed `agent-memory`
  - Hermes bootstrap/doctor/context
  - Codex prompt dry-run
  - Claude prompt dry-run
- Ensure smoke runs from `/tmp/...`, not repo cwd.
- Ensure `AGENT_MEMORY_PYTHON_EXECUTABLE` is unset.
- Avoid requiring secrets or authenticated hosted services for default smoke.

#### Files likely touched

- `docs/install-smoke.md`
- `scripts/smoke_release_readiness.py`
- maybe new script: `scripts/smoke_published_package.py`
- `tests/test_npm_launcher.py`
- `.github/workflows/publish.yml` only if making it automated post-publish

#### Acceptance

- Maintainers can run one command after publish to verify external install behavior.
- The smoke catches npm/PyPI propagation and command-shape issues.
- The smoke verifies approved-only prompt injection and forensic retrieval.

## Priority 4: Conflict and obsolete memory lifecycle depth

### Goal

Users can understand why a memory is trusted, disputed, deprecated, or replaced.

### Next PRs

1. `feat: add memory transition history`
2. `feat: add supersedes relation for facts`
3. `feat: explain conflict review decisions`

### Scope

- Persist status transition history:
  - actor/source if available
  - timestamp
  - previous status
  - new status
  - reason
  - evidence IDs
- Add replacement/supersedes relation for stale facts.
- Make review output explain preferred vs hidden alternatives.

### Acceptance

- Deprecated/disputed memories remain inspectable.
- Default prompts never include non-approved memory.
- Operators can understand why one claim is active and another is hidden.

## Priority 5: Long-run dogfood and noise monitoring

### Goal

Measure whether real memory injection helps or hurts day-to-day agent work.

### Next PRs

1. `feat: add local retrieval observation log`
2. `feat: add noisy memory audit command`
3. `docs: add dogfood review cadence`

### Scope

- Locally record non-secret retrieval observations:
  - query hash or redacted query summary
  - memory IDs injected
  - scopes
  - policy hints
  - prompt budget use
- Add audit command to find frequently injected but ignored/deprecated/noisy memories.
- Keep logs local and opt-in or clearly documented.

### Acceptance

- No secrets are printed or persisted by default.
- Users can inspect why memory entered prompts.
- Users can curate noisy memories out of default retrieval.

## Definition of done for the final objective

The project can claim OSS default-memory-layer readiness when all of these are true:

1. Install and first-run path
   - npm/npx install path works outside repo cwd.
   - PyPI/uvx path works outside repo cwd.
   - docs use direct `agent-memory [command]` as the primary surface.

2. Runtime safety
   - Hermes hook fail-closed behavior is tested.
   - Prompt budget defaults are conservative.
   - Debug mode is opt-in.
   - Latency/failure behavior is documented.

3. Retrieval quality
   - Fixture corpus covers realistic stale/noisy/conflict/scope failures.
   - Eval report makes failures actionable.
   - CI can run retrieval eval as advisory at minimum.

4. Lifecycle trust
   - Approved-only default retrieval is enforced.
   - Disputed/deprecated memory is inspectable through forensic commands.
   - Transition/replacement history exists for operator review.

5. Published release verification
   - Every release can be externally smoke-tested from `/tmp`.
   - Smoke confirms Hermes/Codex/Claude prompt surfaces include approved memory snippets and exclude disputed/deprecated snippets by default.

## Fresh-session first commands

```bash
cd /Users/reddit/Project/agent-memory
HOME=/Users/reddit gh auth status || true
git status --short --branch
git log -5 --oneline --decorate
git tag --sort=-version:refname | head -5
```

If clean on `main` at or after `v0.1.15`, start Priority 1.
