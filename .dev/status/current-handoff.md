# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-04 12:18 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.61까지 PR/CI/merge/release/npm/PyPI/published smoke/Hermes QA가 완료됐다. v0.1.61에는 Stage F/F3 decay-risk prompt-time noise penalty preview가 포함됐다. 다음 제품 slice는 Stage F/F4 bounded graph neighborhood reinforcement 또는 all-DB `consolidation conflicts report` 같은 read-only diagnostics다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main` after docs/handoff cleanup PR is merged.
- `origin/main` includes v0.1.61 release-sync PR #97 after the F3 release path.
- No Stage F feature worktree is expected to remain active after F3 cleanup.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.61`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.61`
- npm package: `@cafitac/agent-memory@0.1.61`
- PyPI package: `cafitac-agent-memory==0.1.61`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.61/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.61.

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
   - F3 decay-risk prompt-time noise penalty preview done in v0.1.61
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness


## Latest completed PR-sized slice

Stage F / F3 decay-risk prompt-time noise penalty preview completed.

PR #96 `feat: add decay-risk retrieval preview` merged and released in v0.1.61. Release-sync PR #97 merged.

- New command: `agent-memory retrieval decay-preview <db> <query> [--preferred-scope ...] [--limit N] [--decay-weight N] [--frequent-threshold N]`.
- It reuses current approved-only retrieval trace with `record_retrievals=false`, then computes a preview-only decay-risk prompt-time noise penalty.
- Output kind is `retrieval_decay_preview`; it includes `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, baseline rank, preview rank, decay penalties, rank changes, relation policy, activation/retrieval counts, and decay-risk factor breakdowns.
- It omits raw query text, query previews, prompts, transcripts, and secrets.
- It does not create observations, increment retrieval counters, create activations, mutate facts/relations, or change default retrieval ranking/Hermes hook behavior.
- Reviewed supersession is preview-marked as `exclude`; frequently activated or connected approved memories receive protection signals so age alone does not downrank them.

Verification completed for F3/v0.1.61:

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

Release QA completed:

- GitHub Release: `v0.1.61`
- npm clean exec smoke: `npm-smoke-ok 0.1.61`
- PyPI fresh venv smoke: `pypi-smoke-ok 0.1.61`
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.61/.venv/bin/agent-memory`
- `agent-memory hermes-doctor`, `hermes hooks list`, `hermes hooks doctor`, `hermes hooks test pre_llm_call`, and `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` passed.


## Next recommended PR-sized slice

Primary recommendation: Stage F/F4 bounded graph-neighborhood reinforcement, or an all-DB `consolidation conflicts report` read-only diagnostic if we want a smaller lifecycle QA slice first.

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
