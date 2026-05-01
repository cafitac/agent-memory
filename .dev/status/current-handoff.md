# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 22:18 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.51까지 배포/Hermes QA가 완료됐고, 현재는 graph-based memory consolidation runtime 로드맵의 Stage D / PR D1 `consolidation candidates` read-only trace clustering CLI를 구현하는 단계야. Stage A baseline, Stage B trace substrate/CLI/Hermes opt-in/retention report, Stage C activation summary/reinforcement/decay-risk reports는 완료됐다. D1은 sanitized `experience_traces`를 deterministic scope/memory/summary key로 묶고 candidate fingerprint, evidence window, surfaces/scopes, safe summaries, related refs, activation/status reinforcement context, guessed memory type, risk flags를 보여주되 raw query/prompt/transcript 출력, retrieval ranking 변경, memory status mutation, reject/snooze mutation, long-term memory 자동 생성은 하지 않는다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`
- Commit author for this repo should remain `Minwoo Kang <31237832+cafitac@users.noreply.github.com>` unless the user says otherwise.

Latest completed release:

- `v0.1.51`
- v0.1.51 added read-only `agent-memory activations decay-risk-report`.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.51/.venv/bin/agent-memory`.

Current local PR D1 modifications:

- Branch/worktree: `/Users/reddit/Project/agent-memory/.worktrees/consolidation-candidates` on `feat/consolidation-candidates`
- `src/agent_memory/api/cli.py`
  - Adds `agent-memory consolidation candidates <db> --limit 200 --top 20 --min-evidence 2`.
  - Emits read-only JSON with `kind: memory_consolidation_candidates`.
  - Groups sanitized `experience_traces` by deterministic cluster keys:
    - `scope:<scope>|memory:<first-related-memory-ref>` when related refs exist
    - otherwise `scope:<scope>|summary:<safe-summary-token-key>`
  - Includes candidate id/fingerprint, evidence trace ids/window, surfaces/scopes, event kind counts, retention policy counts, safe summaries, related memory/observation refs, salience/user-emphasis totals, activation counts/current statuses, guessed memory type, risk flags, and suggested explanation command.
  - Does not mutate memory state, create long-term memories, reject/snooze candidates, or change retrieval ranking.
- `tests/test_memory_activations.py`
  - Adds CLI tests for consolidation candidate clustering, deterministic safe output, privacy, activation/status context, and lazy migration from DBs missing `experience_traces`/`memory_activations`.
- `README.md`, `docs/hermes-dogfood.md`, `.dev/roadmap/memory-consolidation/stage-d-consolidation-candidates.md`, `.dev/status/current-handoff.md`
  - Document D1 in progress and the read-only dogfood command.

Expected local untracked artifacts to preserve in the root checkout:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`
- `.worktrees/` if scoped worktrees are active

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
   - PR B1: `experience_traces` schema (done in v0.1.44)
   - PR B2: `traces record/list` CLI (done in v0.1.45)
   - PR B3: Hermes trace recording opt-in (done in v0.1.46)
   - PR B4: trace retention/safety guardrails (done in v0.1.47)
3. Stage C: activation and reinforcement signals
   - PR C1: activation events (done in v0.1.48)
   - PR C2: activation summary CLI (done in v0.1.49)
   - PR C3: reinforcement score report (done in v0.1.50)
   - PR C4: decay risk score report (done in v0.1.51)
4. Stage D: consolidation candidates before mutation
   - PR D1: trace clustering for consolidation candidates (current)
   - PR D2: candidate CLI surface may be folded into D1 if PR remains small; otherwise next slice should refine candidates/explain.
5. Stage E: reviewed promotion into long-term memory
6. Stage F: retrieval uses consolidation signals conservatively
7. Stage G: cautious automation
8. Stage H: product hardening and public readiness

## Sequence guardrails

Do not skip directly to automatic memory saving until read-only reports and manual review loops are proven in local dogfood.

Hard guardrails:

1. No raw transcript archive as a default storage layer.
2. No automatic long-term approval before secret/redaction checks, provenance, conflict/supersession checks, and audit logs exist.
3. No default retrieval ranking change before opt-in eval and live Hermes E2E pass.
4. No mutating cleanup/decay before read-only decay reports are understandable and trusted.
5. No promotion/reject/snooze mutation before read-only candidate grouping and explanation are trusted.
6. Every release that touches Hermes runtime behavior must be installed from the published artifact and verified with a real Hermes E2E turn.

## Next best slice

Finish PR D1: consolidation candidate trace clustering CLI.

D1 is intentionally read-only:

- summarize local sanitized `experience_traces` into candidate clusters
- preserve evidence trace ids and candidate fingerprints for future explanation/reject/snooze workflows
- include activation/status context but do not auto-promote or alter status
- avoid raw query/prompt/query_preview/transcript output
- avoid retrieval ranking changes, memory status mutation, trace cleanup/delete, reject/snooze writes, and long-term memory creation

## Suggested verification before PR

```bash
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest tests/test_memory_activations.py tests/test_cli.py tests/test_experience_traces.py -q
HOME=/Users/reddit /Users/reddit/Project/agent-memory/.venv/bin/python -m pytest -q
git diff --check
npm pack --dry-run
```

Also run a temp DB CLI smoke for `agent-memory consolidation candidates` and verify the output contains no raw query/secret strings.

If this becomes a release, install the published artifact under `/Users/reddit/.agent-memory/runtime/vNEXT` using `/usr/local/bin/python3.11 -m venv`, update `/Users/reddit/.hermes/config.yaml`, and run the standard dogfood baseline/activation summary/reinforcement report/decay risk/consolidation candidates/direct hook/Hermes E2E QA.
