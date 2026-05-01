# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-02 00:43 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.55까지 PR/CI/merge/release/npm/PyPI/Hermes QA가 완료됐다. v0.1.55에는 Stage E / PR E2 read-only `agent-memory consolidation promotions report` audit surface가 포함됐다. 현재 다음 제품 slice는 Stage E / PR E3 consolidation graph lineage relation edges다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main` or a short-lived docs/feature branch.
- `origin/main` includes v0.1.55 release commit `794ecb3`.
- No Stage E feature worktree is expected to remain active after E2; create a fresh scoped worktree for E3 if starting implementation.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.55`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.55`
- npm package: `@cafitac/agent-memory@0.1.55`
- PyPI package: `cafitac-agent-memory==0.1.55`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.55/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.55.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Completed workflow optimization slice

PR #75 `ci: shorten publish workflow` merged.

Result:

- `auto-release.yml` ignores docs/workflow-only pushes.
- `publish.yml` no longer repeats full pytest; main/release-sync CI remains the full test gate.
- Slow real-registry `published-install-smoke` is opt-in via `run_published_install_smoke`, default `false`.
- Standalone `published-install-smoke.yml` remains the manual external-install gate.

## Completed Stage E / PR E1 slice

PR #76 `feat: add consolidation fact promotion` merged and released in v0.1.54.

Behavior:

- `agent-memory consolidation promote fact <db> <candidate-id> ...` creates semantic facts from explicitly reviewed candidates.
- Reviewer supplies final fact fields; candidate contributes safe provenance only.
- Default output is `candidate` status and hidden from default retrieval.
- `--approve --actor ... --reason ...` explicitly approves and logs status history.
- Unknown candidate ids fail without creating facts or provenance sources.
- No automatic promotion, approval queue, graph relation edge, procedure/preference promotion, conflict preflight, or retrieval ranking change yet.

## Completed Stage E / PR E2 slice

PR #78 `feat: add consolidation promotions report` merged and released in v0.1.55.

Behavior:

- `agent-memory consolidation promotions report <db> --limit 50` lists manual semantic fact promotions created by E1.
- Report includes promoted fact id/status/claim fields, candidate fingerprint, generated provenance source id, safe summaries, trace ids, related observation ids, status counts, and approval history.
- Output is visibly `read_only: true`.
- The command is read-only: it does not mutate facts, sources, traces, status transitions, queues, ranking, or graph edges.
- Output omits raw prompts, transcripts, raw trace metadata, query previews, and secrets.
- Default retrieval remains approved-only.

Verification completed for E2/v0.1.55:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py tests/test_review_and_scope_ranking.py tests/test_experience_traces.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
git diff --check
npm pack --dry-run
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
```

External release QA completed:

```bash
npm view @cafitac/agent-memory version
# 0.1.55
python3 - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen('https://pypi.org/pypi/cafitac-agent-memory/json'))['info']['version'])
PY
# 0.1.55
```

Hermes QA completed:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.55/.venv/bin/agent-memory hermes-doctor \
  /Users/reddit/.agent-memory/memory.db \
  --config-path /Users/reddit/.hermes/config.yaml \
  --python-executable /Users/reddit/.agent-memory/runtime/v0.1.55/.venv/bin/python \
  --timeout 15
hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool
hermes hooks doctor
```

`hermes hooks doctor` reported all shell hooks healthy, including the v0.1.55 agent-memory pre-LLM hook.

## Canonical roadmap position

The durable north-star is a graph-based memory consolidation runtime:

- experiences leave lightweight traces
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and retrieval usefulness
- weak traces decay/expire/collapse into summaries
- strong trace clusters consolidate into semantic, episodic, procedural, and preference memories
- prompt-time retrieval remains explainable through provenance, status history, supersession, and graph relations

Roadmap sequence:

1. Stage A: lock plan and dogfood baseline
2. Stage B: trace layer without automatic memory creation
3. Stage C: activation and reinforcement signals
4. Stage D: consolidation candidates before mutation
   - D1/D2 candidates report done in v0.1.52
   - D3 candidate explanation details done in v0.1.53
5. Stage E: reviewed promotion into long-term memory
   - E1 semantic fact promotion done in v0.1.54
   - E2 promotion audit report done in v0.1.55
   - E3 consolidation graph lineage relation edges is next
6. Stage F: retrieval uses consolidation signals conservatively
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness

## Next recommended PR-sized slice: Stage E / PR E3

Goal:

- Represent consolidation as graph lineage so `graph inspect` can explain trace/candidate/durable-memory relationships.

Likely command/user surfaces:

- Existing `consolidation promote fact` should create relation metadata/edges from candidate evidence to promoted fact.
- Existing `consolidation promotions report` may include relation ids or graph lineage summaries after E3.
- Existing `graph inspect` should show consolidation lineage in a safe, explainable form.

Acceptance from roadmap:

- `graph inspect` shows trace/candidate/durable memory lineage.
- Relations include weights or metadata where useful.
- Existing supersession relations remain compatible.

Out of scope for E3 unless deliberately re-scoped:

- procedure/preference promotion
- conflict/supersession preflight
- automatic promotion
- retrieval ranking changes
- destructive cleanup/decay

## Recommended first commands for the next implementation session

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git fetch origin --prune --tags
git log --oneline -5
sed -n '1,220p' .dev/roadmap/memory-consolidation/stage-e-reviewed-promotion.md
```

Then create a fresh worktree, for example:

```bash
mkdir -p .worktrees
git worktree add .worktrees/consolidation-graph-lineage -b feat/consolidation-graph-lineage origin/main
```
