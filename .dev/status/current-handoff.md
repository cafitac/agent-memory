# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-04-29 01:57 KST

## Trigger for the next session

If the user starts a fresh session and only says:

> 지금 해야하는거 알려줘

then read this file first and answer from the "Ready-to-say answer" section below. Do not ask the user to restate context. The immediate next work is already chosen here.

## Ready-to-say answer

지금 바로 해야 할 건 `agent-memory`에서 retrieval evaluation fixture/harness를 시작하는 거야.

KB M1/M1+와 v0.1.8 release/smoke까지 끝났고, 다음 단계는 embeddings/reranking 같은 복잡도를 넣기 전에 retrieval 품질을 측정하는 최소 평가 루프를 만드는 거야.

진행 순서는:
1. `~/Project/agent-memory` 상태 확인
2. `.dev/kb/retrieval-evaluation-v0.md`를 기준으로 `.dev/kb/retrieval-eval-m1-implementation-plan.md` 작성
3. TDD로 `tests/test_retrieval_evaluation.py`부터 추가
4. `agent-memory eval retrieval <db_path> <fixtures_dir>` 또는 최소 core API를 구현
5. fixture 기반으로 expected memory IDs / drift / counts를 검증
6. README는 검증 후 짧게만 업데이트

이 작업부터 진행하면 돼.

## Current repo state

Canonical repo path:

- `~/Project/agent-memory`

Current branch/release state at this handoff:

- branch: `main`
- remote: `origin` -> `git@github.com-cafitac:cafitac/agent-memory.git`
- git status at last check: clean, `main...origin/main`
- latest commit: `750ef36 chore: release v0.1.8`
- latest validated release: `v0.1.8`
- npm: `@cafitac/agent-memory@0.1.8`
- PyPI: `cafitac-agent-memory==0.1.8`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.8`

Important run IDs:

- `25065915434` — CI success for `b468166 feat: enrich KB export provenance`
- `25066123570` — main CI success for `750ef36 chore: release v0.1.8`
- `25066195998` — publish workflow success for `v0.1.8`
- `25066196035` — tag CI success for `v0.1.8`

Published install smoke for `v0.1.8` was completed after registry propagation:

- npm global install path passed
- npm wrapper `agent-memory kb export --help` passed
- npm wrapper `agent-memory bootstrap` passed
- npm wrapper `agent-memory doctor` returned `status: ok`
- pipx install path passed
- pipx `kb export --help`, `bootstrap`, `doctor` passed
- uv tool install path passed
- uv tool `kb export --help`, `bootstrap`, `doctor` passed
- final smoke output: `published install smoke ok`

Note: the first npm smoke attempt for `v0.1.8` failed because the npm launcher correctly pinned `cafitac-agent-memory==0.1.8` before uv/PyPI simple-index resolution had caught up. A retry after propagation succeeded. This is the same known registry-propagation behavior seen in v0.1.7 and is not currently a code blocker.

## What is complete

### Runtime and distribution

- SQLite-first local memory runtime exists.
- Package is published to npm and PyPI.
- npm is the shortest onboarding surface; PyPI is the canonical Python runtime.
- npm thin launcher pins the delegated Python package to the npm package version.
- GitHub Actions CI/publish flow is validated.
- Actual published install smoke is validated through `v0.1.8`.

### Hermes integration

- `agent-memory bootstrap` works as the short onboarding command.
- `agent-memory doctor` works as the read-only health check.
- Hermes hook installer performs conservative config merge for normal YAML config.
- Hermes adapter remains thin: prompt-time memory injection only.
- The adapter does not execute tools or verification itself.

### KB M1

Implemented and released:

- source -> candidate -> approved memory -> KB draft export vertical slice
- command: `agent-memory kb export <db_path> <output_dir> [--scope <scope>]`
- exports markdown files:
  - `index.md`
  - `facts.md`
  - `procedures.md`
  - `episodes.md`
- approved facts/procedures/episodes only
- candidate/disputed/deprecated memories are excluded
- scope filtering works

### KB M1+

Implemented and released in `v0.1.8`:

- source-aware provenance in KB markdown export
- exported memory sections render source details when source records exist:
  - source id
  - source type
  - created timestamp
  - adapter
  - external reference
  - sorted metadata
  - short source excerpt
- missing source IDs render as missing instead of crashing export
- CLI JSON output includes:
  - generated file list
  - `counts.facts`
  - `counts.procedures`
  - `counts.episodes`
  - `counts.total_items`
  - `source_ids`

Key commits:

- `a01f762 feat: add KB markdown export`
- `b468166 feat: enrich KB export provenance`
- `750ef36 chore: release v0.1.8`

## Current planning docs

The active planning surface is under `.dev/kb/`:

- `.dev/kb/kb-architecture-v0.md`
  - memory vs KB boundary, truth source, export/sync direction
- `.dev/kb/source-ingestion-v0.md`
  - source classes, normalization, candidate extraction direction
- `.dev/kb/curation-and-promotion-v0.md`
  - candidate -> approved -> deprecated workflow
- `.dev/kb/retrieval-evaluation-v0.md`
  - the next active workstream; evaluation before embeddings/reranking
- `.dev/kb/harness-boundary-v0.md`
  - Hermes vs agent-memory vs future harness responsibilities
- `.dev/kb/kb-m1-implementation-plan.md`
  - historical M1 plan, now implemented
- `.dev/kb/kb-m1-plus-implementation-plan.md`
  - historical M1+ source-aware export plan, now implemented
- `.dev/kb/kb-m1-current-audit.md`
  - audit plus post-M1/M1+ status updates
- `.dev/kb/kb-m1-scope-freeze.md`
  - M1 scope/non-goals

## Immediate next work: retrieval evaluation M1

Do this next before adding embeddings, reranking, graph visualization, or memory-palace style lifecycle complexity.

Goal:

- Add a small reproducible evaluation loop that proves whether retrieval is getting better or worse.
- Establish fixtures and metrics before changing retrieval algorithms.

Why this is next:

- KB export/provenance is now good enough for reviewable artifacts.
- The long-term ambition is memory OS / memory palace, but that needs measurable retrieval quality.
- Embeddings/reranking should only be added after a baseline shows where lexical/current retrieval fails.

Recommended branch:

```bash
cd ~/Project/agent-memory
git status -sb
git checkout -b feat/retrieval-eval-fixtures
```

If `main` is already dirty, stop and inspect before branching. Preserve unrelated dirty work.

### Retrieval evaluation M1 scope

In scope:

- fixture file format for retrieval tasks
- core evaluator function using existing `retrieve_memory_packet`
- CLI surface to run evaluation
- JSON result output
- tests with a small seeded SQLite database
- docs update after tests pass

Out of scope:

- embeddings
- reranking
- graph expansion changes
- web UI
- changes to Hermes hook behavior
- automatic LLM judging

### Suggested fixture format

Prefer a simple JSON file or directory of JSON files. Start with one file:

`tests/fixtures/retrieval_eval/basic.json`

Suggested shape:

```json
{
  "tasks": [
    {
      "id": "project-scope-fact",
      "query": "What does Project M1 use for KB export?",
      "preferred_scope": "project:m1",
      "expected": {
        "facts": [1],
        "procedures": [],
        "episodes": []
      },
      "avoid": {
        "facts": [2],
        "procedures": [],
        "episodes": []
      },
      "limit": 5
    }
  ]
}
```

Do not hardcode production DB IDs in user-facing docs. In tests, build the DB in `tmp_path` and use created IDs.

### Suggested models

Add Pydantic models in `src/agent_memory/core/models.py` or a small new module if cleaner:

- `RetrievalEvalExpected`
- `RetrievalEvalTask`
- `RetrievalEvalTaskResult`
- `RetrievalEvalSummary`

Minimum output should include:

- task id
- query
- preferred scope
- hit/miss per expected memory id
- avoided/drift memory ids that appeared
- counts
- pass/fail boolean

### Suggested implementation files

Likely create:

- `src/agent_memory/core/retrieval_eval.py`
- `tests/test_retrieval_evaluation.py`

Likely modify:

- `src/agent_memory/core/models.py`
- `src/agent_memory/api/cli.py`
- `README.md` after behavior is verified
- `.dev/kb/retrieval-evaluation-v0.md` or create `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.dev/status/current-handoff.md` after completing the slice

### Suggested CLI

Prefer:

```bash
agent-memory eval retrieval <db_path> <fixtures_path> [--limit 5]
```

Expected behavior:

- reads JSON fixtures
- runs current retrieval with `retrieve_memory_packet`
- compares returned fact/procedure/episode IDs against expected/avoid lists
- prints JSON summary
- exits nonzero only for malformed fixtures or runtime errors, not necessarily for failed eval tasks unless an explicit `--fail-on-regression` flag is added later

Keep the first version boring and deterministic.

### TDD checklist for the next session

1. Write failing model/fixture parsing test.
2. Run targeted test and confirm RED.
3. Implement minimal fixture parser.
4. Run targeted test and confirm GREEN.
5. Write failing evaluator test with tmp SQLite DB and seeded approved/candidate memories.
6. Confirm RED.
7. Implement evaluator using existing `retrieve_memory_packet`.
8. Confirm GREEN.
9. Add CLI test for `agent-memory eval retrieval`.
10. Confirm RED, then implement CLI parser/handler.
11. Run focused tests.
12. Run full tests.
13. Update README only after tests pass.
14. Commit and push.
15. Watch CI.

Suggested verification commands:

```bash
uv run pytest tests/test_retrieval_evaluation.py -q
uv run pytest -q
uv run agent-memory eval retrieval --help
git status -sb
gh run list --branch main --limit 3
```

## Commands to verify current release if needed

Use these if future context is uncertain:

```bash
cd ~/Project/agent-memory
git status -sb
git log --oneline -5
git tag --list 'v0.1.*' --sort=-version:refname | head -5
gh release view v0.1.8 --json tagName,isDraft,isPrerelease,url,assets
python - <<'PY'
import json, urllib.request
for name, url in [
    ('npm', 'https://registry.npmjs.org/@cafitac%2Fagent-memory/latest'),
    ('pypi', 'https://pypi.org/pypi/cafitac-agent-memory/json'),
]:
    data=json.load(urllib.request.urlopen(url, timeout=20))
    print(name, data.get('version') or data.get('info',{}).get('version'))
PY
```

Expected current versions:

- npm: `0.1.8`
- PyPI: `0.1.8`

## Things not to redo

Do not redo these unless evidence shows they regressed:

- do not redesign Hermes hook integration before retrieval evaluation exists
- do not add embeddings before evaluation fixtures exist
- do not split `agent-brain` / `agent-memory-palace` into a new repo yet
- do not rerun old v0.1.7 release work
- do not change unrelated `.claude/`, `.hermes/`, or local user config files unless explicitly requested
- do not commit temp smoke directories or generated local DBs

## Secrets and privacy

Never preserve or print real token values.

Token names that may appear in docs are okay:

- `NPM_TOKEN`
- `PYPI_API_TOKEN`

Actual token values must remain redacted. Do not include private keys, passwords, or real credential helper output in handoff docs.

## Durable decisions to keep

- SQLite-first, local-first remains the default.
- One global user DB remains the default posture.
- `user:default` remains the durable baseline scope.
- `cwd:<hash>` remains the privacy-preserving project-sensitive Hermes fallback.
- Hermes adapter remains thin and prompt-time only.
- KB markdown export is a derived artifact; SQLite remains the source of truth.
- npm remains the shortest onboarding path; PyPI remains the canonical Python runtime distribution.
- Use TDD for behavior changes.
- For published CLI/package changes, validate actual published artifacts, not just green CI.
