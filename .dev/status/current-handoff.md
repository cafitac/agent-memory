# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 14:14 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.43까지 배포/Hermes QA가 완료됐고, 현재는 graph-based memory consolidation runtime 로드맵의 Stage B / PR B1 lightweight `experience_traces` schema를 구현하는 단계야. Stage A의 planning checkpoint와 `agent-memory dogfood baseline ~/.agent-memory/memory.db --output-json` read-only baseline은 완료됐다. 이번 B1은 trace storage/model/API만 추가하고, CLI/Hermes trace writes/default retrieval 변화는 다음 PR로 미룬다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Latest completed release:

- `v0.1.43`
- v0.1.43 added the read-only dogfood baseline report CLI.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.43/.venv/bin/agent-memory`.

Current local PR B1 modifications:

- `src/agent_memory/core/models.py`
  - Adds `ExperienceTrace` for sanitized, bounded event traces.
- `src/agent_memory/storage/schema.sql`
  - Adds `experience_traces` table and indexes.
- `src/agent_memory/storage/sqlite.py`
  - Adds lazy migration for `experience_traces`.
  - Adds explicit write/list APIs: `insert_experience_trace(...)` and `list_experience_traces(...)`.
  - Strips known raw metadata keys before writing trace metadata.
- `tests/test_experience_traces.py`
  - Covers new DB schema, lazy migration, sanitized insert/list behavior, and unchanged retrieval output.
- `README.md`, `docs/hermes-dogfood.md`, `.dev/roadmap/memory-consolidation/stage-b-trace-layer.md`, `.dev/status/current-handoff.md`
  - Document that B1 is storage-only: no CLI, no Hermes writes, no retrieval/ranking change.

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

PR B1: Add a lightweight `experience_traces` schema behind an explicit write path.

Before acting, read:

1. `.dev/status/current-handoff.md`
2. `.dev/roadmap/memory-consolidation/stage-b-trace-layer.md`
3. `src/agent_memory/core/models.py`
4. `src/agent_memory/storage/sqlite.py`
5. `tests/test_experience_traces.py`

Suggested first commands next session:

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git diff --check
HOME=/Users/reddit .venv/bin/python -m pytest tests/test_experience_traces.py -q
HOME=/Users/reddit .venv/bin/python -m pytest -q
```

If the user asks to proceed after that, finish B1 verification, create the PR, merge/release after CI, and run published-artifact smoke. Because B1 does not change Hermes hook behavior, Hermes QA should still verify the existing v0.1.43 hook path after installing the new release.
