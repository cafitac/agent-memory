# Memory Consolidation Roadmap

Status: AI-authored draft. Not yet human-approved.

This directory is the detailed execution guide for the agent-memory north-star:
agent-memory should become a graph-based memory consolidation runtime, not merely a curated facts database or transcript archive.

The short version in `../roadmap-v0.md` is the canonical index. This directory explains how to execute that index without drifting when a session is compacted or a new agent resumes the work.

## North-star

Experiences should leave lightweight traces first. Repetition, recency, salience, user emphasis, graph connectivity, and demonstrated retrieval usefulness should strengthen some traces. Weak traces should decay, expire, or collapse into summaries. Strong trace clusters should consolidate into explainable long-term semantic, episodic, procedural, and preference memories.

The full product can be heavy, but the implementation must move in thin, reversible PR-sized slices.

## Non-negotiable guardrails

1. Do not build a default raw transcript archive.
2. Do not store raw user prompts or tool outputs in trace/observation reports unless a future, explicitly reviewed storage policy allows it.
3. Do not auto-approve long-term memory before redaction, provenance, conflict/supersession checks, and audit logs exist.
4. Do not change default retrieval ranking until opt-in eval and live Hermes E2E pass.
5. Do not add mutating cleanup/decay before read-only decay reports are trusted in dogfood.
6. Every release that changes Hermes runtime behavior must be installed from the published artifact and verified with a real Hermes E2E turn.
7. Preserve local-only untracked directories unless explicitly told otherwise: `.agent-learner/`, `.claude/`, `.omc/`, and local `.dev/kb/*` notes.

## How to use this directory

When a new session starts with a vague prompt such as "이어서 진행해줘":

1. Read `.dev/status/current-handoff.md`.
2. Read this README.
3. Check the next unchecked PR in `../roadmap-v0.md`.
4. Open the matching stage file below.
5. Execute exactly one PR-sized slice unless the user explicitly asks for broader planning.
6. If the plan changes, update both `../roadmap-v0.md` and the relevant stage file before implementing.

## Current checkpoint

- `current-progress-and-next-steps.md` — latest verified progress, live dogfood state, final target, and next recommended slices after `v0.1.71`.

Use this current checkpoint together with `.dev/status/current-handoff.md` before choosing the next PR-sized task.

## Stage documents

- `stage-a-plan-and-baseline.md` — lock the plan, add dogfood baseline snapshot.
- `stage-b-trace-layer.md` — add lightweight traces without automatic memory creation.
- `stage-c-activation-reinforcement-decay.md` — add activation events and read-only reinforcement/decay scoring.
- `stage-d-consolidation-candidates.md` — surface reviewable consolidation candidates before mutation.
- `stage-e-reviewed-promotion.md` — manually promote candidates into long-term memory with provenance and graph edges.
- `stage-f-retrieval-signals.md` — use consolidation signals in retrieval conservatively and opt-in first.
- `stage-g-cautious-automation.md` — introduce explicit remember-intent and opt-in automation.
- `stage-h-product-hardening.md` — evaluation, visualization, backup/export, public docs.

## PR sequence

| PR | Stage | Purpose | Default behavior |
| --- | --- | --- | --- |
| A1 | Plan | Commit the roadmap and detailed plan docs | docs only |
| A2 | Baseline | Add dogfood baseline snapshot/report | read-only |
| B1 | Trace | Add `experience_traces` schema/API | no retrieval change |
| B2 | Trace | Add `traces record/list` CLI | explicit CLI only |
| B3 | Trace | Add Hermes trace recording opt-in | disabled by default |
| B4 | Trace | Add retention/safety guardrails | conservative defaults |
| C1 | Activation | Add activation events | no ranking change |
| C2 | Activation | Add activation summary CLI | read-only |
| C3 | Scoring | Add reinforcement score report | read-only |
| C4 | Scoring | Add decay risk score report | read-only |
| D1 | Candidates | Add trace clustering | read-only |
| D2 | Candidates | Add consolidation candidates CLI | read-only |
| D3 | Candidates | Add candidate explanations | read-only |
| D4 | Candidates | Add candidate rejection/snooze | explicit review state |
| E1 | Promotion | Manual semantic fact promotion | explicit human action |
| E2 | Promotion | Manual procedure/preference promotion | explicit human action |
| E3 | Graph | Add consolidation relation edges | graph lineage only |
| E4 | Safety | Add conflict/supersession promotion checks | blocks unsafe promotion |
| F1 | Retrieval | Show signal metadata in retrieval explanations | no ranking change |
| F2 | Retrieval | Opt-in reinforcement ranking | default unchanged |
| F3 | Retrieval | Opt-in decay noise penalty | default unchanged |
| F4 | Retrieval | Bounded graph neighborhood reinforcement | measured/controlled |
| G1 | Automation | Explicit `remember this` auto-candidate | still reviewed by default |
| G2 | Automation | Narrow opt-in auto-approval | off by default |
| G3 | Automation | Background consolidation dry-run | dry-run default |
| G4 | Automation | Background consolidation apply mode | explicit flag only |
| H1 | Hardening | Consolidation eval fixtures/metrics | advisory CI |
| H2 | Hardening | Graph/trace visualization export | local/redacted |
| H3 | Hardening | Backup/import/export | safe round-trip |
| H4 | Hardening | Promote reviewed docs public | stable behavior only |

## Verification baseline for planning PRs

For docs-only roadmap PRs:

```bash
git diff --check
python - <<'PY'
from pathlib import Path
for path in [
    Path('.dev/roadmap/roadmap-v0.md'),
    Path('.dev/architecture/architecture-v0.md'),
    Path('.dev/product/thesis-and-scope.md'),
    Path('.dev/status/current-handoff.md'),
]:
    text = path.read_text()
    if '\n7|' in text or '\n8|' in text:
        raise SystemExit(f'accidental line-number artifact in {path}')
print('docs ok')
PY
```

For code PRs, add the relevant focused tests, full tests, release readiness checks, npm dry-run, diff check, static secret scan, and Hermes/published runtime QA when applicable.
