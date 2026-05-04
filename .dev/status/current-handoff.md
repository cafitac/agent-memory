# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-04 14:57 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.64까지 PR/CI/merge/release/npm/PyPI/published smoke/Hermes QA가 완료됐다. Stage G/G1 explicit `Remember this:` review trace path와 G1a `dogfood remember-intent` read-only quality gate가 완료됐다. 현재 진행 중인 다음 작업은 Stage G/G2 narrow opt-in auto-approval이며, `remember-preferences-v1` 정책을 default-off dry-run/apply CLI로 구현 중이다.

## Current in-progress slice

Stage G/G2 narrow opt-in auto-approval is in progress in worktree `.worktrees/remember-auto-approve` on branch `feat/remember-auto-approve`.

Current implementation slice:

- Adds `agent-memory consolidation auto-approve remember-preferences <db> --policy remember-preferences-v1 --scope <scope>`.
- Default mode is dry-run/read-only and reports `would_approve` candidates without mutation.
- Apply mode requires `--apply --actor ... --reason ...`.
- Eligible rows are explicit/review-ready `remember_intent` traces in the selected scope with sanitized summaries shaped like `User prefers ...` or `I prefer ...`.
- The only auto-approved memory shape is `fact(user, prefers, <value>, <scope>)`.
- Guardrails block secret-like summaries, unsupported summary shapes, non-selected scopes, ordinary turns, and claim-slot conflicts.
- Successful apply writes approval/status history and an `auto_approved_as` relation from the trace to the fact.

Recommended remaining steps before merging:

1. Re-run focused/related/full tests.
2. Run release readiness/package dry-run/manual CLI smoke.
3. Open PR and let CI validate.
4. Merge/release, then update runtime/Hermes QA if auto-release publishes a new version.

Do not broaden this slice into procedures, inferred preferences from ordinary conversation, background cron, or default retrieval ranking changes.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Current branch expectation:

- Root checkout should be on `main`.
- `origin/main` includes v0.1.64 release-sync PR #106.
- No Stage F feature worktree is required after F4 cleanup; if `.worktrees/graph-neighborhood-ranker-preview` remains locally, it is safe to remove after verifying no uncommitted changes.

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.64`
- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.64`
- npm package: `@cafitac/agent-memory@0.1.64`
- PyPI package: `cafitac-agent-memory==0.1.64`
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.64/.venv/bin/agent-memory`.
- Hermes config hook command is allowlisted and points to v0.1.64.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Completed Stage G/G1 slice

PR #102 `feat: add explicit remember intent traces` merged and released in v0.1.63.

- Existing Hermes trace recording remains disabled unless `--record-trace` is enabled.
- With `--record-trace`, explicit `Remember this:` / `Please remember:` messages that pass the conservative secret-like scan are recorded as `experience_traces.event_kind=remember_intent`.
- G1 rows use `retention_policy=review`, high salience/user emphasis, sanitized summary only, hashed session/content refs, and metadata `candidate_policy=review_required`, `auto_approved=false`.
- Secret-like remember requests fall back to ordinary hash-only ephemeral turn traces and do not create remember review traces.
- No facts/procedures/episodes are created or approved automatically; review remains through `consolidation candidates` and `consolidation explain`.

Verification completed for G1/v0.1.63:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'remember_intent or remember_candidate or secret_like_remember'
# 3 passed, 64 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'hermes_pre_llm_hook or experience_trace or consolidation_candidates or remember'
# 18 passed, 54 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 231 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #102 CI succeeded and merged.
- Release-sync PR #103 CI succeeded and merged.
- GitHub Release `v0.1.63` published.
- npm registry shows `@cafitac/agent-memory@0.1.63`.
- PyPI JSON and fresh install show `cafitac-agent-memory==0.1.63`.
- PyPI fresh venv smoke verified `remember_intent` trace creation.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.63` smoke succeeded for CLI/help.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.63/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.63.
- Direct v0.1.63 hook smoke verified review-only remember traces.
- `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.63 agent-memory pre-LLM hook.

## Completed Stage G/G1a slice

PR #105 `feat: add remember intent dogfood report` merged and released in v0.1.64. Release-sync PR #106 merged.

- New command: `agent-memory dogfood remember-intent <db> --limit 200 --sample-limit 10`.
- Output kind is `remember_intent_dogfood_report` with `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`.
- The report counts inspected traces, `remember_intent` traces, ordinary turn traces, review-ready traces, unsafe samples, and remember-intent scopes.
- Samples include safe sanitized summaries plus compact policy flags only; raw metadata, raw prompts/transcripts, and secret-like summaries are omitted.
- No facts/procedures/episodes, relations, status transitions, candidates, approvals, retrieval observations, or hook behavior are mutated.
- Real dogfood DB read-only report completed with zero current `remember_intent` traces.

Verification completed for G1a/v0.1.64:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'remember_intent_report or dogfood_remember'
# 1 passed, 67 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q -k 'dogfood or remember_intent or hermes_pre_llm_hook or experience_trace'
# 21 passed, 52 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 232 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #105 CI succeeded and merged.
- Release-sync PR #106 validation succeeded and merged.
- GitHub Release `v0.1.64` published.
- npm registry shows `@cafitac/agent-memory@0.1.64`.
- PyPI JSON and fresh install show `cafitac-agent-memory==0.1.64`.
- PyPI fresh venv smoke verified `dogfood remember-intent` on a seeded temp DB.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.64` smoke verified `dogfood remember-intent` on a temp DB.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.64/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.64.
- Direct v0.1.64 hook smoke verified review-only remember traces.
- `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.64 agent-memory pre-LLM hook.

## Completed Stage F/F4 slice

PR #99 `feat: add graph-neighborhood retrieval preview` merged and released in v0.1.62.

- `agent-memory retrieval graph-neighborhood-preview <db> <query>` is an opt-in/read-only preview command.
- Output kind is `retrieval_graph_neighborhood_preview` with `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`.
- The preview reports baseline rank vs graph-neighborhood preview rank without changing `retrieve`, Hermes hook behavior, or default ranking.
- Traversal is bounded by explicit depth/neighbor controls and capped scoring; explanations include relation ids/types, neighbor refs, activated neighbor refs, graph boost, and rank deltas.
- Output omits raw query/query_preview/prompt/transcript content and uses existing relation edges only.
- Focused CLI coverage proves no retrieval counters, observations, activations, facts, or relations mutate.

Verification completed for F4/v0.1.62:

```bash
/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_graph_neighborhood_preview'
# 3 passed, 61 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_cli.py -q -k 'retrieval_graph_neighborhood_preview or retrieval_decay_preview or retrieval_ranker_preview or retrieval_policy_preview or graph_inspect'
# 11 passed, 53 deselected

/Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/ -q
# 228 passed

/Users/reddit/Project/agent-memory/.venv/bin/python scripts/check_release_metadata.py
/Users/reddit/Project/agent-memory/.venv/bin/python scripts/smoke_release_readiness.py
npm pack --dry-run
node --check bin/agent-memory.js
git diff --check
```

Release QA completed:

- PR #99 CI succeeded and merged.
- Release-sync PR #100 merged.
- GitHub Release `v0.1.62` published.
- npm registry shows `@cafitac/agent-memory@0.1.62`.
- PyPI JSON and files show `cafitac-agent-memory==0.1.62`.
- PyPI fresh venv smoke: import version `0.1.62`, CLI `--help`, and `retrieval graph-neighborhood-preview --help` succeeded.
- npm clean `npm exec --package=@cafitac/agent-memory@0.1.62` smoke succeeded for CLI `--help` and `retrieval graph-neighborhood-preview --help`.
- Hermes runtime installed at `/Users/reddit/.agent-memory/runtime/v0.1.62/.venv/bin/agent-memory`.
- `/Users/reddit/.hermes/config.yaml` was backed up before updating the hook path to v0.1.62.
- Direct pre-LLM hook smoke succeeded and did not echo the synthetic prompt.
- `hermes chat --accept-hooks -Q -q 'Say exactly: OK' --source tool` returned `OK`.
- `hermes hooks doctor` reported all shell hooks healthy, including the v0.1.62 agent-memory pre-LLM hook.

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
   - F4 bounded graph-neighborhood reinforcement preview done in v0.1.62
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
