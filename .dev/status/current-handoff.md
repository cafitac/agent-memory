# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 16:57 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.47까지 배포/Hermes QA가 완료됐고, 현재는 graph-based memory consolidation runtime 로드맵의 Stage C / PR C1 `memory_activations` activation-event substrate를 구현하는 단계야. Stage A baseline, Stage B / PR B1 `experience_traces`, B2 `traces record/list`, B3 Hermes `--record-trace`, B4 `traces retention-report`는 완료됐다. C1은 retrieval observation을 activation evidence로 bridge하되, raw query/prompt 저장, retrieval ranking 변경, long-term memory 자동 생성은 하지 않는다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Latest completed release:

- `v0.1.47`
- v0.1.47 added read-only trace retention-report guardrails.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.47/.venv/bin/agent-memory`.

Current local PR C1 modifications:

- Branch: `feat/activation-events`
- `src/agent_memory/core/models.py`
  - Adds `MemoryActivation` model.
- `src/agent_memory/storage/schema.sql`
  - Adds `memory_activations` table and indexes.
- `src/agent_memory/storage/sqlite.py`
  - Adds lazy `_ensure_memory_activations_schema(...)`.
  - Adds `list_memory_activations(...)` and `memory_activation_from_row(...)`.
  - `record_retrieval_observation(...)` now records activation evidence:
    - `retrieved` rows for selected memory refs.
    - `empty_retrieval` row when retrieval is empty.
  - Activation metadata is sanitized; raw prompt/query/query_preview/user_message/transcript keys are omitted.
- `tests/test_memory_activations.py`
  - Covers schema creation, secret-safe activation recording, empty retrieval negative evidence, and lazy migration.
- `README.md`, `docs/hermes-dogfood.md`, `.dev/roadmap/roadmap-v0.md`, `.dev/roadmap/memory-consolidation/stage-c-activation-reinforcement-decay.md`, `.dev/status/current-handoff.md`
  - Document C1 in progress.

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
   - PR B1: `experience_traces` schema (done in v0.1.44)
   - PR B2: `traces record/list` CLI (done in v0.1.45)
   - PR B3: Hermes trace recording opt-in (done in v0.1.46)
   - PR B4: trace retention/safety guardrails (done in v0.1.47)
3. Stage C: activation and reinforcement signals
   - PR C1: activation events (current)
   - PR C2: activation summary CLI
   - PR C3: reinforcement score report
   - PR C4: decay risk score report
4. Stage D: consolidation candidates before mutation
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
5. Every release that touches Hermes runtime behavior must be installed from the published artifact and verified with a real Hermes E2E turn.

## Next best slice

Finish PR C1: activation event substrate.

C1 is intentionally a substrate/bridge first:

- create local-only `memory_activations` rows from retrieval observations
- link activation rows to observation ids and memory refs
- represent empty retrievals as negative evidence
- keep existing observation command outputs compatible
- avoid raw query/prompt/query_preview/transcript storage in activation rows
- avoid retrieval ranking changes and long-term memory promotion

## Suggested verification before PR

```bash
HOME=/Users/reddit .venv/bin/python -m pytest tests/test_memory_activations.py -q
HOME=/Users/reddit .venv/bin/python -m pytest tests/test_memory_activations.py tests/test_cli.py tests/test_experience_traces.py -q
HOME=/Users/reddit .venv/bin/python -m pytest -q
git diff --check
npm pack --dry-run
```

If this becomes a release, install the published artifact under `/Users/reddit/.agent-memory/runtime/vNEXT` using `/usr/local/bin/python3.11 -m venv`, update `/Users/reddit/.hermes/config.yaml`, and run the standard dogfood baseline/direct hook/Hermes E2E QA.
