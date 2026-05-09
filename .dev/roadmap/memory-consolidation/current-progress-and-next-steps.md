# Memory Consolidation Current Progress and Next Steps

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-10 03:42 KST

## Purpose

This document is the restartable checkpoint for the current `agent-memory` direction after the v0.1.122 restore/audit approval-token validation safety release and the current narrow audit-row write slice. Older sections below preserve historical context from the v0.1.77-v0.1.99 transition; the current source of truth is the v0.1.122 snapshot and next-slice guidance in this file plus `.dev/status/current-handoff.md`.

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

Latest completed release: `v0.1.122`

Released artifacts:

- GitHub release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.122`
- npm: `@cafitac/agent-memory@0.1.122`
- PyPI: `cafitac-agent-memory==0.1.122`

Local Hermes/runtime signal:

- Published PyPI and npm smoke passed for `v0.1.122`.
- Source checkout is based on `v0.1.122` main.
- Main CI and auto-release succeeded for the v0.1.122 release.

Current implementation interpretation:

- G4a narrow query-preview cleanup is complete and has been live-applied once.
- Restore/audit safety hardening reached the approval-token positive validation checkpoint in `v0.1.122`.
- The current branch opens only the narrow metadata-only restore audit row write when approval/preflight gates pass.
- Live restore, broad consolidation apply mode, ordinary-conversation auto-approval, raw transcript storage, raw query-preview output, sample values, and default retrieval ranking changes remain disabled.

## Current live dogfood health snapshot

Read-only aggregate snapshot checked 2026-05-10 03:04 KST against `/Users/reddit/.agent-memory/memory.db`:

- `retrieval_observations`: 2153, latest 2026-05-09 18:04:14 UTC
- `memory_activations`: 2058, latest 2026-05-09 18:04:14 UTC
- `experience_traces`: 1435, latest 2026-05-09 18:04:14 UTC
- `facts`: 3, latest 2026-04-30 17:26:00 UTC
- `procedures`: 0
- `episodes`: 0
- non-empty legacy `retrieval_observations.query_preview`: 0

Privacy/integrity interpretation:

- Observation, activation, and metadata-only trace evidence has grown substantially since the v0.1.77 checkpoint.
- Approved facts remain intentionally sparse under conservative defaults.
- Legacy stored query previews remain cleared.
- Restore artifacts and backups remain private local files because rollback artifacts can contain raw query previews.
- Broad G4 consolidation apply mode remains blocked.

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
- v0.1.72/v0.1.73: read-only storage-health and legacy query-preview cleanup preview reports.
- v0.1.74: read-only trace-quality report.
- v0.1.75: cron-friendly `dogfood scheduled-dry-run` bundle.
- v0.1.76: read-only `dogfood scheduled-compare` over saved scheduled report artifacts.
- v0.1.77: explicit `dogfood query-preview-cleanup --apply --actor --reason`; live cleanup cleared 70 legacy query-preview rows and left 0 remaining.

Current behavior:

- Explicit remember-intent remains the only path toward narrow auto-approval, and only through guarded commands. Safe explicit requests can be reviewed through sanitized summaries; secret-like requests remain rejected diagnostics.
- Ordinary conversation is evidence-only.
- Background dry-runs are read-only.

## Current decision point

The project is past the first two narrow cleanup mutations and deep into G4a restore/audit safety hardening. The current branch implements the next narrow mutation: a single metadata-only restore audit row write after validated approval and passing preflight, while live restore and broad G4 apply remain blocked.

Sequence from here:

1. Land this narrow audit-row write slice with focused restore/audit tests and full suite verification.
2. Release and smoke the published artifacts.
3. Run a live dry-run/contract check against the Hermes DB before considering any live audit-row write.
4. If a live audit-row write is approved later, take a backup first and use only the named restore/audit corridor; do not restore query previews in the live DB.
5. Reassess broad G4 consolidation apply mode from live scheduled dogfood evidence after the narrow restore/audit corridor is safe.

Why:

- Matching hashes are now a validated approval signal, but only this narrow metadata-only audit trace write is allowed.
- The restore/audit path is a narrow safety corridor; it must prove approval, preflight, duplicate/conflict, audit, and rollback behavior before broader consolidation mutation.
- The human-brain-like goal still requires cautious automation, but the current blocker is safe mutation infrastructure, not more raw evidence capture.

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

- Completed and released in v0.1.72 via PR #127/#128.
- At release time, the Hermes runtime was updated to `/Users/reddit/.agent-memory/runtime/v0.1.72/.venv/bin/agent-memory`; the current runtime is recorded in the top-level verified state above.
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

### G3c-followup: Add read-only legacy query-preview cleanup preview

Status: completed and released in v0.1.73 via PR #129/#130. Published npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.73/.venv/bin/agent-memory`, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed.

Goal:

Make the storage-health legacy stored-query-excerpt warning actionable without printing raw stored excerpts or adding an apply mode.

Command shape:

```bash
agent-memory dogfood query-preview-cleanup ~/.agent-memory/memory.db \
  --older-than 2030-01-01T00:00:00
```

Scope:

- aggregate non-empty stored query excerpt counts;
- aggregate cleanup-eligible counts before the supplied cutoff;
- earliest/latest timestamps only;
- explicit privacy markers proving samples/raw values are omitted;
- recommended operation marker for future manual cleanup planning.

Acceptance:

- read-only, `mutated=false`;
- no raw prompts, query text, query previews, transcripts, full memory content, tokens, API keys, or secrets;
- no sample values;
- works on the live DB and on temp DB fixtures;
- no apply mode until explicitly planned and approved.

### G3d: Add read-only `dogfood trace-quality`

Status: completed and released in v0.1.74 via PR #132/#133. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.74/.venv/bin/agent-memory`, published npm/PyPI/uvx smokes, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed. Live 24h report currently returns `status=warning` / `recommendation=continue_dogfooding` because recent observations are still not linked from traces strongly enough; this is an expected conservative gate before G4 planning.

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

### G3e: Add cron-friendly `dogfood scheduled-dry-run` bundle

Status: completed and released in v0.1.75 via PR #135/#136. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.75/.venv/bin/agent-memory`, published npm/PyPI/uvx smokes, live DB smoke, Hermes E2E, and `hermes hooks doctor` passed. The first live quality gate returned `continue_scheduled_dry_run_dogfooding_before_g4`, so G4 apply-mode is still not the next implementation step.

Goal:

Collect several G3/G3a/G3d reports over time so the decision to continue, tune, or plan G4 is data-backed without requiring ad hoc command choreography.

Command shape:

```bash
agent-memory dogfood scheduled-dry-run ~/.agent-memory/memory.db \
  --output ~/.agent-memory/reports/scheduled-dry-run-YYYYMMDD-HHMMSS.json \
  --since-hours 24 \
  --min-trace-coverage 0.25 \
  --min-evidence-count 2 \
  --candidate-min 1 \
  --max-decay-risk 0
```

Scope:

- one cron-friendly read-only command;
- bundle `dogfood storage-health`, `dogfood trace-quality`, `dogfood remember-intent`, and inline `consolidation background dry-run`;
- write the same JSON to `--output` when provided;
- expose one conservative `quality_gate` whose pass only means "write a separate G4 plan with RED tests";
- keep privacy markers and no-mutation/default-retrieval-unchanged markers top-level.

Acceptance:

- multiple scheduled reports can complete without lock contention or mutation;
- quality warnings are explainable or decreasing;
- candidate signals become non-zero or the report explains why evidence remains sparse;
- privacy checks stay clean;
- no cleanup apply mode, G4 apply mode, ordinary-conversation auto-approval, raw transcript storage, broad preference inference, or default retrieval ranking change.

### G3f: Collect and compare scheduled dry-run reports

Status: completed and released in v0.1.76 via PR #138/#139. Published GitHub Release/npm/PyPI, installed runtime `/Users/reddit/.agent-memory/runtime/v0.1.76/.venv/bin/agent-memory`, published npm/PyPI/uvx/npm smokes, live DB scheduled-compare smoke, Hermes E2E, and `hermes hooks doctor` passed. The first comparison decision remains `continue_scheduled_report_collection_before_g4`, so G4 apply-mode is still not the next implementation step.

Goal:

Run the new G3e bundle repeatedly from the live Hermes DB and compare the aggregate quality gate, warning set, candidate counts, trace coverage, and decay-risk signals over time before any G4 apply-mode plan.

Scope:

- save timestamped `dogfood scheduled-dry-run` JSON artifacts;
- add `dogfood scheduled-compare` as a read-only comparison over repeated saved artifacts;
- compare only counts, timestamps, booleans, ratios, hashes, IDs, and warning names;
- no raw content samples or embedded raw report bodies;
- no cleanup/apply mutation;
- no default retrieval or hook config changes.

Command shape:

```bash
agent-memory dogfood scheduled-compare \
  --report ~/.agent-memory/reports/scheduled-dry-run-1.json \
  --report ~/.agent-memory/reports/scheduled-dry-run-2.json \
  --output ~/.agent-memory/reports/scheduled-compare.json \
  --min-report-count 2 \
  --max-decay-risk 0
```

Acceptance:

- multiple reports complete read-only with `mutated=false`;
- warning trends are explainable;
- decision remains conservative unless quality signals improve;
- any G4 plan is a separate RED-tested PR, not bundled into reporting.

### G3g: Optional legacy privacy cleanup apply plan

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

### G3g: Continue scheduled collection and lock the G4 readiness sequence

Status: in progress in this docs checkpoint. Baseline G4-readiness artifacts were created with the v0.1.76 runtime; the latest compare decision remains `continue_scheduled_report_collection_before_g4`. A local Hermes cron job `6894df1bfd4c` is scheduled to collect four more read-only reports every 6 hours under `/Users/reddit/.agent-memory/reports/g4-readiness`.

Goal:

Make the post-G3f path explicit while report artifacts accumulate: collect, compare, write the G4 apply-mode contract, then implement only the first narrow mutation slice.

Detailed plan:

- `.dev/roadmap/memory-consolidation/g4-readiness-and-first-mutation-plan.md`

Acceptance:

- local scheduled artifacts are not committed;
- docs record artifact paths and cron boundary without raw report bodies;
- the first recommended mutation is legacy `query_preview` cleanup apply, not ordinary conversation auto-approval;
- no DB mutation, retrieval change, or Hermes config change lands in this planning slice.

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

First MVP complete in PR #149 / v0.1.80. `graph export-html` exports a standalone local neural-style HTML graph over memory refs, relations, traces, observations, and activations. The default is read-only/redacted/ref-only; curated memory labels require explicit `--include-memory-labels`. Visual QA confirms it renders and is useful as an MVP, but richer filtering/search/clustering remains future polish.

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
/Users/reddit/.agent-memory/runtime/v0.1.80/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
HOME=/Users/reddit hermes hooks doctor
```

3. Do a raw-content-safe live DB health check if the user asks whether data is still accumulating.

4. If implementing, keep collecting/comparing G3f scheduled reports or draft a separate G4 plan only after the report trend justifies it; do not implement apply mode directly from this checkpoint.

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
