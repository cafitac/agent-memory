# Memory Consolidation Current Progress and Next Steps

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-05 11:46 KST

## Purpose

This document is the restartable checkpoint for the current `agent-memory` direction after the v0.1.71 remember-intent diagnostics and Hermes dogfood release.

Use it when the user asks:

- "지금까지 진행상황 정리해줘"
- "앞으로 뭐 해야 해?"
- "최종 목표까지 어떤 스텝으로 갈 거야?"
- "agent-memory 이어서 진행해줘"

The goal is to keep future sessions aligned with the north-star while avoiding an unsafe jump from lightweight trace capture to automatic memory approval.

## North-star

`agent-memory` should become a graph-based memory consolidation runtime inspired by human memory, not a raw transcript archive and not a manual-only note database.

Final target:

1. Ordinary experience creates lightweight local traces.
2. Retrieval and use create activation/observation evidence.
3. Repeated, recent, salient, connected, and useful traces strengthen over time.
4. Weak traces decay, expire, or collapse into safe summaries.
5. Strong trace clusters become consolidation candidates.
6. Candidates are explainable and reviewable before long-term promotion.
7. Approved long-term memories become graph nodes/edges with provenance, status history, supersession, and conflict handling.
8. Conservative retrieval uses only safe/approved memory by default.
9. Automation stays opt-in, audited, reversible or reviewable, and never stores raw prompts by default.

## Current verified release state

Latest completed release: `v0.1.71`

Released artifacts:

- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.71`
- npm: `@cafitac/agent-memory@0.1.71`
- PyPI: `cafitac-agent-memory==0.1.71`

Local Hermes runtime:

- Runtime path: `/Users/reddit/.agent-memory/runtime/v0.1.71/.venv/bin/agent-memory`
- Hermes config backup before v0.1.71 path update: `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.71-20260505111920`
- `hermes hooks doctor` reported the agent-memory hook healthy after approval.

v0.1.69 fixed the v0.1.68 live-path issue where ordinary metadata-only trace recording could be skipped when the rendered memory context was empty. The trace write now happens before the empty-context return, while hook output still returns `{}` when no memory context is injected.

## Current live dogfood health snapshot

Read-only live DB check at roughly 2026-05-05 11:46 KST:

- `retrieval_observations`: 725, latest 2026-05-05 02:46:27 UTC
- `memory_activations`: 630, latest 2026-05-05 02:46:27 UTC
- `experience_traces`: 50, latest 2026-05-05 02:43:42 UTC
- `facts`: 3, latest 2026-04-30 17:26:00 UTC
- `procedures`: 0
- `episodes`: 0
- `relations`: 0

Recent live Hermes v0.1.71 E2E smoke:

- `hermes chat --accept-hooks -Q -q 'Reply with OK only.' --source tool` returned `OK`.
- The live DB advanced by +1 retrieval observation, +1 activation, and +1 metadata-only ordinary trace.
- Approved `facts` stayed unchanged, which is expected under the conservative policy.

Privacy/integrity signals:

- Recent observations have `query_sha256`.
- Recent observations keep `query_preview` empty.
- Legacy non-empty `query_preview` rows exist from old versions: 70 rows, latest 2026-05-01 12:57:54 UTC.
- v0.1.69-and-later non-empty `query_preview`: 0.
- Latest ordinary traces are metadata-only: `event_kind=turn`, `summary=NULL`, `retention_policy=ephemeral`, `candidate_policy=evidence_only`, `auto_approved=false`.
- Latest safe explicit remember-intent traces keep sanitized summaries only.
- Latest secret-like explicit remember-intent traces are rejected diagnostics with `summary=NULL` and `rejected_reason=secret_like_text`.

Interpretation:

- The live write path is healthy enough to keep dogfooding.
- Observation/activation evidence is advancing.
- Ordinary metadata-only traces are advancing.
- Approved long-term facts are not changing during ordinary conversation, which is expected under the conservative policy.
- The system is not yet doing automatic long-term memory approval from ordinary conversation.

## What is intentionally not happening yet

Do not treat this as a gap to "fix" without a new plan.

Ordinary conversation currently does not:

- create approved facts/procedures/episodes automatically;
- infer preferences from normal chat;
- auto-approve long-term memory;
- change default retrieval ranking;
- store raw prompts, raw queries, transcripts, full user messages, or query previews;
- run background apply mode.

This is deliberate. The project is currently collecting safe weak evidence and measuring its quality before broader automation.

## Completed implementation arc

### Stage A/B: baseline and trace substrate

Completed:

- Lightweight `experience_traces` schema/API.
- `traces record/list` CLI for explicit sanitized local traces.
- Hermes trace recording path.
- Trace retention/safety reporting.

Current behavior:

- Traces are local and bounded.
- No raw transcript archive exists.
- Trace presence does not imply long-term memory approval.

### Stage C: activation/reinforcement/decay evidence

Completed:

- Retrieval observations bridge into `memory_activations`.
- Activation summary report.
- Reinforcement report.
- Decay-risk report.

Current behavior:

- Retrieved memory refs and empty retrievals create evidence rows.
- Reports are read-only and explanatory.
- Ranking/default retrieval is not changed by these reports.

### Stage D: consolidation candidate diagnostics

Completed:

- Read-only consolidation candidates.
- Candidate explanation CLI.

Current behavior:

- Candidate surfaces can explain possible memories from evidence.
- Candidate diagnostics do not mutate memory.

### Stage E: reviewed promotion and graph lifecycle

Completed:

- Manual reviewed promotion.
- Promotion audit/report.
- Lineage relation edges.
- Conflict/supersession preflight.
- Reviewed conflict relation edges.

Current behavior:

- Human/reviewed actions can promote durable memory with provenance.
- Graph edges record lineage and conflict context.
- Unsafe/conflicting promotion is guarded.

### Stage F: retrieval signal previews

Completed:

- Retrieval policy preview.
- Reinforcement ranker preview.
- Decay-risk prompt-time noise penalty preview.
- Bounded graph-neighborhood reinforcement preview.

Current behavior:

- Retrieval signal use is preview/advisory/opt-in.
- Default retrieval behavior remains conservative.

### Stage G: cautious automation and dogfood

Completed:

- G1: explicit `Remember this:` / `Please remember:` remember-intent review traces.
- G1a: read-only remember-intent dogfood quality report.
- G2: narrow opt-in auto-approval for explicit remember-preference traces only.
- G3: background consolidation dry-run report.
- G3a: saved background dry-run dogfood quality gates.
- G3b: ordinary Hermes turns create metadata-only traces by default.
- v0.1.69 hotfix: no-context ordinary turns still record metadata-only traces.
- v0.1.70/v0.1.71: debuggable explicit remember-intent diagnostics, Korean prefixes, and freeform secret-like rejection hardening.

Current behavior:

- Explicit remember-intent remains the only path toward narrow auto-approval, and only through guarded commands. Safe explicit requests can be reviewed through sanitized summaries; secret-like requests remain rejected diagnostics.
- Ordinary conversation is evidence-only.
- Background dry-runs are read-only.

## Current decision point

The next safe move is not G4 apply mode.

The next safe move is to measure live trace/evidence quality in a reusable, one-command, read-only way.

Why:

- We now have live ordinary traces, observations, and activations.
- The live data is still sparse.
- Observation/activation counts are higher than trace counts; that may be expected, but the system needs a first-class report explaining coverage instead of ad hoc SQL.
- The G3/G3a quality gate previously recommended continuing dry-run dogfooding before G4.
- Automatic approval from ordinary conversation would be premature without better quality and privacy evidence.

## Recommended next PR-sized slices

### G3c: Add read-only `dogfood storage-health`

Goal:

Create a one-command health report that answers whether live Hermes/agent-memory storage is functioning correctly without printing raw content.

Candidate command:

```bash
agent-memory dogfood storage-health ~/.agent-memory/memory.db \
  --hermes-config ~/.hermes/config.yaml
```

Current implementation status:

- Branch `feat/dogfood-storage-health` adds the read-only JSON command and docs.
- Focused and related tests passed locally; full suite passed locally.
- Live DB smoke reported `kind: dogfood_storage_health`, `read_only=true`, `mutated=false`, Hermes hook present, configured DB path present, and no raw-content marker leakage. The live DB status was `warning` because legacy non-empty stored query excerpts still exist and some old ordinary turn traces predate the final metadata-only shape.

Scope:

- table counts and latest timestamps for observations, activations, traces, facts/procedures/episodes/relations;
- active runtime path/version compatibility fields;
- Hermes hook path marker when available;
- recent non-empty `query_preview` count;
- missing hash counts;
- invalid JSON counts;
- orphan activation links;
- trace metadata shape counts;
- facts unchanged under ordinary turns as an expected conservative signal;
- clear `status` and `warnings` fields.

Acceptance:

- read-only, `mutated=false`;
- never prints raw prompts, query text, query previews, transcripts, full memory content, tokens, or secrets;
- works on the live DB and on temp DB fixtures;
- flags the v0.1.68-style pattern where observations/activations advance but traces do not;
- docs explain that sparse facts are normal unless explicit remember/apply commands ran.

### G3d: Add read-only `dogfood trace-quality`

Goal:

Measure whether ordinary conversation traces are useful enough to support later consolidation work.

Candidate command:

```bash
agent-memory dogfood trace-quality ~/.agent-memory/memory.db \
  --since-hours 24 \
  --min-trace-coverage 0.25 \
  --min-evidence-count 2
```

Scope:

- observation-to-trace coverage by time window;
- empty retrieval ratio;
- retrieved evidence repetition counts;
- trace event-kind and retention-policy distribution;
- metadata-only invariant checks;
- candidate-signal proxy counts;
- quality gate recommendation.

Acceptance:

- read-only, `mutated=false`, default retrieval unchanged;
- outputs `continue_dogfooding`, `ready_for_more_dry_runs`, or `consider_g4_plan` style recommendation;
- does not create candidates or approvals;
- does not print raw conversation content.

### G3e: Run scheduled dry-run dogfood over multiple reports

Goal:

Collect several G3/G3a reports over time so the decision to continue, tune, or plan G4 is data-backed.

Manual command shape:

```bash
agent-memory consolidation background dry-run ~/.agent-memory/memory.db \
  --limit 200 \
  --top 20 \
  --min-evidence 2 \
  --output ~/.agent-memory/reports/background-consolidation-YYYYMMDD-HHMMSS.json \
  --lock-path ~/.agent-memory/background-consolidation.lock

agent-memory dogfood background-dry-run ~/.agent-memory/memory.db \
  --report ~/.agent-memory/reports/background-consolidation-YYYYMMDD-HHMMSS.json \
  --output ~/.agent-memory/reports/background-quality-YYYYMMDD-HHMMSS.json
```

Acceptance:

- multiple reports complete without lock contention or mutation;
- quality warnings are explainable or decreasing;
- candidate signals become non-zero or the report explains why evidence remains sparse;
- privacy checks stay clean.

### G3f: Optional legacy privacy cleanup preview

Goal:

Handle old non-empty `query_preview` rows from earlier versions without touching new privacy-safe rows.

Scope:

- read-only preview first;
- count and timestamp windows only;
- optional backup path;
- no mutation unless a later explicit cleanup command is approved.

Acceptance:

- no raw previews printed;
- cleanup is not bundled with G4 or auto-approval work;
- user approval required before any mutation.

### G4-plan: Draft background apply-mode plan only after G3 quality is trusted

Goal:

Write, not implement, the apply-mode plan once dry-run and trace-quality reports justify it.

Required prerequisites:

- storage-health stable;
- trace-quality stable over multiple sessions;
- G3/G3a reports have enough candidate signal;
- candidate explanations are human-reviewable;
- conflict/supersession preflight works on representative candidates;
- rollback/audit path is documented.

Hard guardrails:

- no ordinary conversation auto-approval by default;
- no raw transcript storage;
- no retrieval ranking default change;
- `--apply` requires explicit actor, reason, policy, and audit;
- background apply may start only with explicit remember-intent or reviewed candidate classes, not broad LLM-extracted ordinary conversation.

## Longer-term path after G4

### Stage H1: consolidation eval fixtures and metrics

Build fixture suites that measure whether consolidation improves memory quality without privacy regression.

### Stage H2: graph/trace visualization export

Export local redacted graph/trace lineage for inspection.

### Stage H3: backup/import/export

Make richer memory DB state operationally safe.

### Stage H4: public docs hardening

Promote reviewed behavior into public docs only when defaults are stable and accurately described.

## What future sessions should do first

When resuming from here:

1. Check repo state:

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
git log --oneline -8
git tag --sort=-version:refname | head -5
```

2. Verify runtime state:

```bash
/Users/reddit/.agent-memory/runtime/v0.1.71/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
HOME=/Users/reddit hermes hooks doctor
```

3. Do a raw-content-safe live DB health check if the user asks whether data is still accumulating.

4. If implementing, start with G3c `dogfood storage-health` unless the user explicitly chooses another next slice.

5. Preserve local-only untracked artifacts:

- `.agent-learner/`
- `.claude/`
- `.dev/kb/retrieval-eval-m1-implementation-plan.md`
- `.omc/`

## Success criteria before broad automation

Do not broaden automation until all of these are true:

- storage-health passes repeatedly;
- trace-quality report shows stable coverage and no privacy regressions;
- background dry-run reports are not dominated by sparse/noisy warnings;
- candidate explanations are understandable without raw transcript access;
- conflict/supersession preflight catches representative conflicts;
- review/rollback/audit paths are exercised;
- default retrieval remains conservative and approved-memory-only unless explicitly opted in.

## Short answer for the current strategy

Yes: for now we keep talking and using Hermes so ordinary traces, retrieval observations, and activation evidence accumulate. Then we inspect the quality of that evidence with read-only reports. Only after the evidence is stable and reviewable do we consider narrow, guarded apply-mode automation.
