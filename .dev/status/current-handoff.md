# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-04 12:02 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.60까지 PR/CI/merge/release/npm/PyPI/Hermes QA가 완료됐다. 현재 Stage F/F3 decay-risk prompt-time noise penalty preview가 `feat/decay-risk-ranker-preview` worktree에서 구현/검증 중이다. F3는 default retrieval을 바꾸지 않는 opt-in/read-only `retrieval decay-preview` 실험으로 유지해야 한다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main` after docs/handoff cleanup PR is merged.
- `origin/main` includes v0.1.60 release-sync PR #94.
- Active F3 feature worktree: `/Users/reddit/Project/agent-memory/.worktrees/decay-risk-ranker-preview` on `feat/decay-risk-ranker-preview` until PR/release cleanup completes.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.60`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.60`
- npm package: `@cafitac/agent-memory@0.1.60`
- PyPI package: `cafitac-agent-memory==0.1.60`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.60/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.60.

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

## Completed Stage E slices

### E1 — semantic fact promotion

PR #76 `feat: add consolidation fact promotion` merged and released in v0.1.54.

- `agent-memory consolidation promote fact <db> <candidate-id> ...` creates semantic facts from explicitly reviewed candidates.
- Reviewer supplies final fact fields; candidate contributes safe provenance only.
- Default output is `candidate` status and hidden from default retrieval.
- `--approve --actor ... --reason ...` explicitly approves and logs status history.
- Unknown candidate ids fail without creating facts or provenance sources.
- No automatic promotion, approval queue, procedure/preference promotion, or retrieval ranking change.

### E2 — promotion audit report

PR #78 `feat: add consolidation promotions report` merged and released in v0.1.55.

- `agent-memory consolidation promotions report <db> --limit 50` lists manual semantic fact promotions created by E1.
- Report includes promoted fact id/status/claim fields, candidate fingerprint, generated provenance source id, safe summaries, trace ids, related observation ids, status counts, and approval history.
- Output is visibly `read_only: true`.
- The command is read-only and omits raw prompts, transcripts, raw trace metadata, query previews, and secrets.
- Default retrieval remains approved-only.

### E3 — consolidation graph lineage relation edges

PR #81 `feat: add consolidation promotion lineage` merged and released in v0.1.56.

- `agent-memory consolidation promote fact ...` records graph lineage relations when a manual semantic fact promotion succeeds.
- Relation path:
  - `<candidate-id> --promoted_to--> fact:<id>`
  - `fact:<id> --has_promotion_provenance--> source_record:<id>`
- `consolidation promote fact` output includes a `lineage` payload with candidate, promoted memory, provenance source, and relation refs.
- `consolidation promotions report` includes the same safe lineage refs while remaining read-only.
- `graph inspect <db> <candidate-id> --depth 2` can explain candidate -> durable fact -> provenance source lineage.
- Unknown candidate ids remain safe failures with no facts, sources, or lineage relations created.
- No procedure/preference promotion, automatic promotion, cleanup/decay mutation, or retrieval ranking change.

### E4 — promotion conflict preflight

PR #84 `feat: add consolidation promotion conflict preflight` merged and released in v0.1.57.

- `agent-memory consolidation promote fact ...` runs read-only conflict preflight before any promotion mutation.
- Claim slot is `subject_ref` + `predicate` + `scope`.
- Existing approved/candidate/disputed/deprecated same-slot facts with a different `object_ref_or_value` block promotion.
- Blocked output returns non-zero with `promoted: false`, `read_only: true`, `error: conflict_preflight_required`, status counts, safe conflicting fact summaries, and suggested `review explain`, `review replacements`, and `graph inspect` commands.
- `--allow-conflict` is required to intentionally keep coexisting conflicting claims.
- Successful promotions preserve E1/E3 behavior.
- No automatic deprecation, supersession, cleanup/decay mutation, approval queue, or retrieval ranking change.

### E5 — explicit reviewed conflict relation edges

PR #87 `feat: add reviewed conflict relations` merged and released in v0.1.58.

- Relation model/storage supports optional `review_actor`, `review_reason`, and `reviewed_at` fields.
- Existing relation tables are migrated with those review metadata columns on `initialize_database`.
- `insert_relation` and `create_relation` accept review metadata.
- Existing `review supersede fact ...` replacement edges remain compatible and now store relation-level review metadata.
- New `review relate-conflict fact <db> <left-fact-id> <right-fact-id> --actor ... --reason ... [--evidence-ids-json ...]` command records a `conflicts_with` relation.
- The conflict relation command requires same claim slot (`subject_ref`, `predicate`, `scope`) and different object values; it rejects missing metadata/cross-slot/same-object attempts without mutation.
- `review conflicts fact ...` includes `conflict_relations` in its read-only output.
- No approval, deprecation, supersession, status mutation, or retrieval ranking/default policy change.

Verification completed for E5/v0.1.58:

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 218 passed

git diff --check
npm pack --dry-run
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
PYTHONPATH=src /Users/reddit/Project/agent-memory/.venv/bin/python -m agent_memory.api.cli review relate-conflict --help
PYTHONPATH=src /Users/reddit/Project/agent-memory/.venv/bin/python -m agent_memory.api.cli review conflicts --help
```

External release QA completed:

```bash
npm view @cafitac/agent-memory version
# 0.1.58
python3 - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen('https://pypi.org/pypi/cafitac-agent-memory/json'))['info']['version'])
PY
# 0.1.58
```

Published install smoke completed:

- PyPI fresh venv install: `cafitac-agent-memory==0.1.58`, `review relate-conflict --help`, `review conflicts --help`, and `graph inspect --help` succeeded.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.58` smoke succeeded for `review relate-conflict --help`, `review conflicts --help`, and `graph inspect --help`.

Hermes QA completed:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.58/.venv/bin/agent-memory hermes-doctor \
  /Users/reddit/.agent-memory/memory.db \
  --config-path /Users/reddit/.hermes/config.yaml \
  --python-executable /Users/reddit/.agent-memory/runtime/v0.1.58/.venv/bin/python \
  --timeout 15
hermes hooks list
hermes hooks doctor
hermes hooks test pre_llm_call
hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool
```

`hermes hooks doctor` reported all shell hooks healthy, including the v0.1.58 agent-memory pre-LLM hook.

## Canonical roadmap position

The durable north-star is a graph-based memory consolidation runtime:

- experiences leave lightweight traces
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and retrieval usefulness
- weak traces decay/expire/collapse into summaries
- strong trace clusters consolidate into semantic, episodic, procedural, and preference memories
- prompt-time retrieval remains explainable through provenance, status history, supersession, conflict relations, and graph relations

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
   - E5 explicit reviewed conflict relation edges done in v0.1.58
6. Stage F: retrieval uses consolidation signals conservatively
   - F1 read-only retrieval policy preview done in v0.1.59
   - F2 opt-in reinforcement ranker preview done in v0.1.60
   - F3 decay-risk prompt-time noise penalty preview in progress on `feat/decay-risk-ranker-preview`
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness


## Active in-progress PR-sized slice

Stage F / F3 decay-risk prompt-time noise penalty preview is implemented locally but not yet PR-merged/released.

Branch/worktree:

- Branch: `feat/decay-risk-ranker-preview`
- Worktree: `/Users/reddit/Project/agent-memory/.worktrees/decay-risk-ranker-preview`

Implemented local command:

```bash
agent-memory retrieval decay-preview <db> <query> [--preferred-scope ...] [--limit N] [--decay-weight N] [--frequent-threshold N]
```

Current local behavior:

- Output kind: `retrieval_decay_preview`.
- `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`.
- Uses current approved-only retrieval trace with `record_retrievals=false`.
- Reports baseline rank vs decay-risk-penalized preview rank, decay penalties, rank changes, relation policy, activation/retrieval counts, and decay-risk factor breakdowns.
- Omits raw query text, `query_preview`, prompts, transcripts, and secret-like metadata.
- Does not create retrieval observations, increment counters, create activations, mutate facts/relations, or change `agent-memory retrieve` / Hermes hook behavior.
- Reviewed supersession is preview-marked as `exclude`; frequently activated or connected approved memories receive protection signals so age alone does not downrank them.

Local verification completed before PR:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_decay_preview'
# 3 passed, 58 deselected
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_decay_preview or retrieval_ranker_preview or retrieval_policy_preview or retrieve'
# 12 passed, 49 deselected
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 225 passed
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
PYTHONPATH=src /Users/reddit/Project/agent-memory/.venv/bin/python -m agent_memory.api.cli retrieval decay-preview --help
```

Next steps are PR creation, CI watch, merge, release-sync/publish verification, published PyPI/npm smoke, Hermes runtime update, Hermes QA, and post-release docs cleanup.

## Latest completed PR-sized slice

Stage F / F2 opt-in reinforcement ranker preview completed.

PR #93 `feat: add reinforcement ranker preview` merged and released in v0.1.60. Release-sync PR #94 merged.

- New command: `agent-memory retrieval ranker-preview <db> <query> [--preferred-scope ...] [--limit N] [--reinforcement-weight N] [--reinforcement-cap N]`.
- It reuses current default retrieval trace with `record_retrievals=false`, then computes a preview-only reinforcement delta and rank comparison.
- Output kind is `retrieval_ranker_preview`; it includes `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, baseline rank, preview rank, rank deltas, score components, and activation/retrieval counts.
- It omits raw query text, query previews, prompts, transcripts, and secrets.
- It does not create observations, increment retrieval counters, mutate facts/relations, or change default retrieval ranking.

Verification completed for F2/v0.1.60:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_ranker_preview'
# 2 passed, 56 deselected
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_ranker_preview or retrieval_policy_preview or retrieve'
# 9 passed, 49 deselected
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 222 passed
git diff --check
npm pack --dry-run
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
node --check bin/agent-memory.js
```

Release QA completed:

- GitHub Release: `v0.1.60`
- npm clean exec smoke: `npm-smoke-ok 0.1.60`
- PyPI fresh venv smoke: `pypi-smoke-ok 0.1.60`
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.60/.venv/bin/agent-memory`
- `agent-memory hermes-doctor`, `hermes hooks list`, `hermes hooks doctor`, `hermes hooks test pre_llm_call`, and `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` passed.

## Next recommended PR-sized slice

Primary recommendation: finish the active Stage F/F3 PR/release path for `retrieval decay-preview`. After F3 is merged, released, and Hermes-QA'd, the next product slice can be Stage F/F4 bounded graph-neighborhood reinforcement or an all-DB `consolidation conflicts report` read-only diagnostic.

Out of scope unless deliberately re-scoped:

- procedure/preference promotion
- automatic promotion
- automatic deprecation/supersession
- destructive cleanup/decay
- default retrieval ranking changes

## Recommended first commands for the next implementation session

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git fetch origin --prune --tags
git log --oneline -5
python - <<'PY'
from pathlib import Path
print(Path('.dev/roadmap/memory-consolidation/stage-f-retrieval-signals.md').read_text())
PY
```
