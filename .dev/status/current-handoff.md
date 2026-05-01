# agent-memory current handoff

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-01 16:00 KST

## Trigger for the next session

If the user starts a fresh session with a vague prompt such as:

> 지금 해야하는거 알려줘
> 다음으로 진행할거 해줘
> 다음 거 진행해줘
> agent-memory 이어서 해줘

read this file first. Do not ask the user to restate context. Verify repo state, then answer from the current roadmap position below.

## Ready-to-say answer

agent-memory는 v0.1.46까지 배포/Hermes QA가 완료됐고, 현재는 graph-based memory consolidation runtime 로드맵의 Stage B / PR B4 `traces retention-report` read-only trace retention guardrail을 구현하는 단계야. Stage A baseline, Stage B / PR B1 `experience_traces` storage substrate, B2 `traces record/list`, B3 Hermes `--record-trace` opt-in trace recording은 완료됐다. 이번 B4는 trace volume/expiry를 read-only로 점검하고, raw transcript 저장/default retrieval 변화/long-term memory 자동 생성/trace deletion은 하지 않는다.

## Current repo state

Canonical repo path:

- `/Users/reddit/Project/agent-memory`

Expected GitHub identity:

- GitHub account: `cafitac`
- Use `HOME=/Users/reddit` for gh commands.
- Remote: `origin` -> `https://github.com/cafitac/agent-memory.git`

Latest completed release:

- `v0.1.46`
- v0.1.46 added opt-in Hermes hook trace recording via `--record-trace`.
- Current Hermes runtime path should be `/Users/reddit/.agent-memory/runtime/v0.1.46/.venv/bin/agent-memory`.

Current local PR B4 modifications:

- Branch: `feat/trace-retention-report`
- `src/agent_memory/storage/sqlite.py`
  - Adds `build_trace_retention_report(...)` as a read-only trace retention report.
  - Report includes trace count, retention-policy counts, expired trace refs, expirable traces missing `expires_at`, volume warnings, and suggested next steps.
  - Report intentionally omits trace summary/metadata/raw content and does not delete traces.
- `src/agent_memory/api/cli.py`
  - Adds `agent-memory traces retention-report <db>`.
  - Options: `--now`, `--max-trace-count`, `--expired-limit`, `--missing-expiry-limit`.
- `tests/test_experience_traces.py`
  - Adds storage-level retention report coverage for expired traces, missing expiry, volume warnings, secret-safe output, and read-only behavior.
- `tests/test_cli.py`
  - Adds module CLI coverage for `traces retention-report` secret-safe/read-only behavior.
- `README.md`, `docs/hermes-dogfood.md`, `.dev/roadmap/roadmap-v0.md`, `.dev/roadmap/memory-consolidation/stage-b-trace-layer.md`, `.dev/status/current-handoff.md`
  - Document B3 complete and B4 in progress as read-only retention reporting first.

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
   - PR B4: trace retention/safety guardrails (current)
3. Stage C: activation and reinforcement signals
   - PR C1: activation events
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

PR B4: Add trace retention and local-only safety guardrails.

B4 is intentionally read-only first:

- identify expired traces deterministically
- flag expirable trace policies without `expires_at`
- warn when total trace count exceeds an operator budget
- avoid mutation/deletion until a later explicitly scoped PR
- avoid raw prompt/transcript/query_preview/metadata/summary output in the retention report

## Suggested verification before PR

```bash
HOME=/Users/reddit .venv/bin/python -m pytest tests/test_experience_traces.py::test_trace_retention_report_identifies_expired_missing_expiry_and_volume tests/test_cli.py::test_python_module_cli_traces_retention_report_is_read_only_and_secret_safe -q
HOME=/Users/reddit .venv/bin/python -m pytest tests/test_cli.py tests/test_experience_traces.py -q
HOME=/Users/reddit .venv/bin/python -m pytest -q
npm pack --dry-run
```

If this becomes a release, install the published artifact under `/Users/reddit/.agent-memory/runtime/vNEXT` using `/usr/local/bin/python3.11 -m venv`, update `/Users/reddit/.hermes/config.yaml`, and run the standard dogfood baseline/direct hook/Hermes E2E QA.
