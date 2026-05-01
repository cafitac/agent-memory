# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 12:36 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.41까지 배포/Hermes QA가 완료됐고, 현재는 최종 목표인 graph-based memory consolidation runtime을 향해 PR 단위 도장깨기 로드맵을 고정하는 단계야. `.dev/roadmap/roadmap-v0.md`에 PR A1~H4 순서의 implementation ladder가 들어가 있고, 상세 실행 문서는 `.dev/roadmap/memory-consolidation/` 아래 stage별로 나뉘어 있다. 다음 자연스러운 작업은 PR A1로 이 planning checkpoint를 PR로 올리고 merge하는 것이다. 그 다음은 PR A2 dogfood baseline snapshot, 이후 B1 lightweight `experience_traces` schema부터 순서대로 진행한다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Latest completed release:

- `v0.1.41`
- v0.1.41 added read-only `observations empty-diagnostics`, completed published smoke, installed runtime QA, `hermes hooks doctor`, and real Hermes E2E with `DIRECT_CMD_MEMORY_LAYER_OK`.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.41/.venv/bin/agent-memory`.

Current local docs-only modifications:

- `.dev/roadmap/roadmap-v0.md`
  - Added north-star memory model.
  - Added PR-by-PR implementation ladder from PR A1 through PR H4.
  - Links to detailed stage docs under `.dev/roadmap/memory-consolidation/`.
- `.dev/roadmap/memory-consolidation/`
  - Added a README and stage A-H execution docs so compacted/fresh sessions can resume without changing direction.
- `.dev/architecture/architecture-v0.md`
  - Added graph-based memory consolidation north-star in Goal.
  - Added graph edge semantics for reinforcement/decay/consolidation/supersession/temporal context.
  - Added layered-memory note that long-term memory should emerge through consolidation.
- `.dev/product/thesis-and-scope.md`
  - Added memory consolidation thesis.
  - Updated principle to “Memory is curated through consolidation, not pre-filtered at birth”.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if any scoped worktrees are active

Do not delete or commit these unless the user explicitly asks.

## Canonical roadmap position

The durable north-star is now:

- not a curated facts DB that only stores important-looking items at ingestion time
- a graph-based memory consolidation runtime inspired by human memory
- experiences leave lightweight traces
- traces strengthen through repetition, recency, salience, user emphasis, graph connectivity, and retrieval usefulness
- weak traces decay/expire/collapse into summaries
- strong trace clusters consolidate into semantic, episodic, procedural, and preference memories
- prompt-time retrieval remains explainable through provenance, status history, supersession, and graph relations

The PR ladder in `.dev/roadmap/roadmap-v0.md` is the canonical sequence unless explicitly revised:

1. Stage A: lock plan and dogfood baseline
   - PR A1: planning checkpoint
   - PR A2: dogfood baseline snapshot/report
2. Stage B: trace layer without automatic memory creation
   - PR B1: `experience_traces` schema
   - PR B2: `traces record/list` CLI
   - PR B3: Hermes trace recording opt-in
   - PR B4: trace retention/safety guardrails
3. Stage C: activation and reinforcement signals
   - PR C1: activation events
   - PR C2: activation summary CLI
   - PR C3: reinforcement score report
   - PR C4: decay risk score report
4. Stage D: consolidation candidates before mutation
   - PR D1: trace clustering
   - PR D2: `consolidation candidates` read-only CLI
   - PR D3: candidate explanation details
   - PR D4: candidate rejection/snooze state
5. Stage E: reviewed promotion into long-term memory
   - PR E1: manual semantic fact promotion
   - PR E2: manual procedure/preference promotion
   - PR E3: consolidation relation edges
   - PR E4: conflict/supersession checks during promotion
6. Stage F: retrieval uses consolidation signals conservatively
   - PR F1: activation/reinforcement metadata in retrieval explanations
   - PR F2: reinforcement as opt-in ranking feature
   - PR F3: decay risk as opt-in noise penalty
   - PR F4: bounded graph neighborhood reinforcement
7. Stage G: cautious automation
   - PR G1: explicit `remember this` auto-candidate path
   - PR G2: opt-in auto-approval for narrow low-risk memories
   - PR G3: background consolidation dry-run job
   - PR G4: background consolidation apply mode behind explicit flag
8. Stage H: product hardening and public readiness
   - PR H1: consolidation eval fixtures/metrics
   - PR H2: graph/trace visualization export
   - PR H3: backup/import/export for trace/consolidation state
   - PR H4: promote reviewed docs into public docs

## Sequence guardrails

Do not skip directly to automatic memory saving until read-only reports and manual review loops are proven in local dogfood.

Hard guardrails:

1. No raw transcript archive as a default storage layer.
2. No automatic long-term approval before secret/redaction checks, provenance, conflict/supersession checks, and audit logs exist.
3. No default retrieval ranking change before opt-in eval and live Hermes E2E pass.
4. No mutating cleanup/decay before read-only decay reports are understandable and trusted.
5. Every release that touches Hermes runtime behavior must be installed from the published artifact and verified with a real Hermes E2E turn.

## Next best slice

PR A1: Persist the consolidation roadmap as the canonical planning checkpoint.

Before acting, read:

1. `.dev/status/current-handoff.md`
2. `.dev/roadmap/roadmap-v0.md`
3. `.dev/roadmap/memory-consolidation/README.md`
4. `.dev/roadmap/memory-consolidation/stage-a-plan-and-baseline.md`

Suggested first commands next session:

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git diff --check
git diff -- .dev/roadmap/roadmap-v0.md .dev/roadmap/memory-consolidation .dev/architecture/architecture-v0.md .dev/product/thesis-and-scope.md .dev/status/current-handoff.md | sed -n '1,420p'
python - <<'PY'
from pathlib import Path
for path in [
    Path('.dev/roadmap/roadmap-v0.md'),
    Path('.dev/architecture/architecture-v0.md'),
    Path('.dev/product/thesis-and-scope.md'),
    Path('.dev/status/current-handoff.md'),
    *Path('.dev/roadmap/memory-consolidation').glob('*.md'),
]:
    text = path.read_text()
    if '\n7|' in text or '\n8|' in text:
        raise SystemExit(f'accidental line-number artifact in {path}')
print('docs ok')
PY
```

If the user asks to proceed after that, create a docs-only PR from a clean branch/worktree or by selective staging only these docs files. Do not include local-only untracked directories. After PR A1 merges, the next implementation slice is PR A2 in `.dev/roadmap/memory-consolidation/stage-a-plan-and-baseline.md`.
