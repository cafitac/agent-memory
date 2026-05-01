# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-02 05:49 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.57까지 PR/CI/merge/release/npm/PyPI/Hermes QA가 완료됐다. v0.1.57에는 Stage E / PR E4 consolidation promotion conflict preflight가 포함됐다. 다음 제품 slice는 E5 explicit human-reviewed supersession/conflict relation command 또는 더 작은 read-only/preflight 후속 점검이다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main` after docs/handoff cleanup PR is merged.
- `origin/main` includes v0.1.57 release-sync PR #85.
- No Stage E feature worktree is expected to remain active after E4 cleanup.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.57`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.57`
- npm package: `@cafitac/agent-memory@0.1.57`
- PyPI package: `cafitac-agent-memory==0.1.57`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.57/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.57.

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
- No automatic promotion, approval queue, procedure/preference promotion, or retrieval ranking change.

## Completed Stage E / PR E2 slice

PR #78 `feat: add consolidation promotions report` merged and released in v0.1.55.

Behavior:

- `agent-memory consolidation promotions report <db> --limit 50` lists manual semantic fact promotions created by E1.
- Report includes promoted fact id/status/claim fields, candidate fingerprint, generated provenance source id, safe summaries, trace ids, related observation ids, status counts, and approval history.
- Output is visibly `read_only: true`.
- The command is read-only and omits raw prompts, transcripts, raw trace metadata, query previews, and secrets.
- Default retrieval remains approved-only.

## Completed Stage E / PR E3 slice

PR #81 `feat: add consolidation promotion lineage` merged and released in v0.1.56.

Behavior:

- `agent-memory consolidation promote fact ...` records graph lineage relations when a manual semantic fact promotion succeeds.
- Relation path:
  - `<candidate-id> --promoted_to--> fact:<id>`
  - `fact:<id> --has_promotion_provenance--> source_record:<id>`
- `consolidation promote fact` output includes a `lineage` payload with candidate, promoted memory, provenance source, and relation refs.
- `consolidation promotions report` includes the same safe lineage refs while remaining read-only.
- `graph inspect <db> <candidate-id> --depth 2` can explain candidate -> durable fact -> provenance source lineage.
- Unknown candidate ids remain safe failures with no facts, sources, or lineage relations created.
- No procedure/preference promotion, automatic promotion, cleanup/decay mutation, or retrieval ranking change.

## Completed Stage E / PR E4 slice

PR #84 `feat: add consolidation promotion conflict preflight` merged and released in v0.1.57.

Behavior:

- `agent-memory consolidation promote fact ...` now runs read-only conflict preflight before any promotion mutation.
- Claim slot is `subject_ref` + `predicate` + `scope`.
- Existing approved/candidate/disputed/deprecated same-slot facts with a different `object_ref_or_value` block promotion.
- Blocked output returns non-zero with:
  - `promoted: false`
  - `read_only: true`
  - `error: conflict_preflight_required`
  - status counts for the claim slot
  - safe conflicting fact summaries
  - suggested `review explain`, `review replacements`, and `graph inspect` commands
- `--allow-conflict` is required to intentionally keep coexisting conflicting claims.
- Successful promotions preserve E1/E3 behavior: default status is `candidate`, explicit `--approve --actor --reason` still logs approval, lineage edges are created only after successful promotion, and default retrieval remains approved-only.
- Unknown candidate ids remain safe failures with no facts, sources, or lineage relations created.
- No automatic deprecation, supersession, cleanup/decay mutation, approval queue, or retrieval ranking change.

Verification completed for E4/v0.1.57:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py tests/test_review_and_scope_ranking.py tests/test_experience_traces.py tests/test_cli.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
git diff --check
npm pack --dry-run
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
PYTHONPATH=src /Users/reddit/Project/agent-memory/.venv/bin/python -m agent_memory.api.cli consolidation promote fact --help
```

External release QA completed:

```bash
npm view @cafitac/agent-memory version
# 0.1.57
python3 - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen('https://pypi.org/pypi/cafitac-agent-memory/json'))['info']['version'])
PY
# 0.1.57
```

Published install smoke completed:

- PyPI fresh venv install: `cafitac-agent-memory==0.1.57`, `consolidation promote fact --help` including `--allow-conflict`, and `graph inspect --help` succeeded.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.57` smoke succeeded for `consolidation promote fact --help` including `--allow-conflict`, and `graph inspect --help`.

Hermes QA completed:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.57/.venv/bin/agent-memory hermes-doctor \
  /Users/reddit/.agent-memory/memory.db \
  --config-path /Users/reddit/.hermes/config.yaml \
  --python-executable /Users/reddit/.agent-memory/runtime/v0.1.57/.venv/bin/python \
  --timeout 15
hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool
hermes hooks doctor
hermes hooks test pre_llm_call
```

`hermes hooks doctor` reported all shell hooks healthy, including the v0.1.57 agent-memory pre-LLM hook.

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
   - E3 consolidation graph lineage relation edges done in v0.1.56
   - E4 conflict/supersession preflight done in v0.1.57
6. Stage F: retrieval uses consolidation signals conservatively
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness

## Next recommended PR-sized slice: Stage E / PR E5

Goal:

- Add an explicit human-reviewed supersession/conflict relation command after E4 has made contradictions visible.

Suggested first shape:

- Keep mutation explicit and review-gated.
- Add a command that records a supersession/conflict relation only when the operator provides source fact, target fact, actor, and reason.
- Do not auto-deprecate the old fact in the same slice unless the command name and flags make that lifecycle transition explicit.
- Do not change retrieval ranking/default behavior.

Alternative smaller slice:

- Add a read-only `consolidation conflicts report` or broaden E4 preflight diagnostics before introducing new mutation.

Out of scope unless deliberately re-scoped:

- procedure/preference promotion
- automatic promotion
- automatic deprecation/supersession
- destructive cleanup/decay
- retrieval ranking changes

## Recommended first commands for the next implementation session

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git fetch origin --prune --tags
git log --oneline -5
sed -n '1,260p' .dev/roadmap/memory-consolidation/stage-e-reviewed-promotion.md
```
