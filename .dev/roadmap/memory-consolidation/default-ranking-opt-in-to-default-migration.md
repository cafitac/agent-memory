# Default Ranking Opt-in-to-default Migration Plan

Status: AI-authored implementation checkpoint. Not yet human-approved or released.
Last updated: 2026-05-13 14:55 KST

## Current local implementation checkpoint

Implemented locally after the v0.1.151 docs checkpoint:

- `dogfood retrieval-ranking-experiment` accepts `--ranking-policy {conservative_legacy,graph_reinforced_v1,shadow_compare}` and `--shadow-compare`.
- Experiment output now includes `active_ranking_policy`, `candidate_ranking_policy`, and `shadow_compare` diagnostics while preserving `default_retrieval_unchanged=true`.
- `dogfood retrieval-ranking-migrate-default` provides an explicit approval-gated config-only migration command.
- Migration command runs the fixture gate, runs shadow compare, hashes protected durable-memory tables before/after, writes an optional audit artifact, updates only the requested config path, and prints rollback command metadata.
- Rollback is the same command with `--policy conservative_legacy` and the approval phrase `migrate-retrieval-ranking-default-v1`.
- Focused regression: `tests/test_cli.py::test_retrieval_ranking_opt_in_default_migration_is_shadow_gated_and_rollbackable`.

The local implementation is not yet released, and the live Hermes profile has not been migrated to `graph_reinforced_v1`.

## Goal

Move retrieval ranking from read-only opt-in experiment toward a safe default only after it proves better than the current conservative behavior on fixture, replay, rollback, and live-runtime evidence.

This is not a broad automation enablement plan. It only covers retrieval ordering defaults. It must not enable:

- broad G4/background apply;
- ordinary conversation auto-approval;
- collapse/delete apply;
- raw prompt/query/transcript storage;
- unreviewed candidate promotion.

## Current baseline

Released runtime: `v0.1.151`.

Current verified evidence:

- Checked-in retrieval fixture directory evaluates at 75/75 pass.
- Expanded live-compatible fixture gate has 50 tasks.
- Ranking experiment payload includes `fixture_gate_comparison`.
- Opt-in ranking experiment can pass the expanded fixture gate.
- Default ranking remains unchanged.
- Broad G4/background apply remains blocked.
- Hermes `personal-oss` runtime hook is active at `/Users/reddit/.agent-memory/runtime/v0.1.151/.venv/bin/agent-memory` and `hermes hooks doctor` is green.

## Migration principles

1. Default behavior changes only through an explicit migration flag or config field.
2. Every migration step must have a one-command rollback path.
3. Fixture pass is necessary but not sufficient; replay and live runtime evidence are required.
4. Regression budget is zero for checked-in fixtures and zero for protected live smoke scenarios.
5. The first default-like run must be shadow/default-preview, not default mutation.
6. User-facing memory content must stay approved/provenance-backed; ranking may reorder retrieval but must not create, edit, approve, collapse, or delete memory.

## Proposed rollout phases

### Phase R0: Freeze and label current default

Purpose: make the current conservative default explicitly nameable so rollback is unambiguous.

Implementation shape:

- Add a named ranking policy enum/config surface, for example:
  - `conservative_legacy` — current default behavior;
  - `graph_reinforced_v1` — candidate future default;
  - `shadow_compare` — run both and report differences without changing returned order.
- Keep `conservative_legacy` as the default.
- Add CLI output that prints the active ranking policy in retrieval diagnostics.
- Add regression tests proving no config/default changes alter current behavior.

Exit criteria:

- Existing full suite passes.
- Retrieval CLI/report shows active policy.
- With no config/flag, output order matches current default.

### Phase R1: Shadow compare on fixtures

Purpose: compare candidate ranking against the named legacy default without affecting runtime retrieval.

Implementation shape:

- Add `agent-memory retrieval ranking-shadow-compare` or extend the existing experiment command with a first-class shadow mode.
- Persist a compact report with:
  - fixture count;
  - candidate pass/fail;
  - legacy pass/fail;
  - baseline regressions;
  - avoid-hit deltas;
  - per-primary-type matrix;
  - deterministic policy/version metadata.
- Fail the gate if candidate has any fixture regression against current 75-task checked-in fixtures or the 50-task expanded gate.

Exit criteria:

- 75 checked-in tasks: 75/75 candidate pass, zero regressions against legacy.
- 50 expanded gate: pass, zero baseline regressions.
- Report is checked into or referenced from `.dev/status/current-handoff.md`.

### Phase R2: Rollback/replay gate

Purpose: prove the policy can be toggled and reverted without durable-memory mutation or hidden state drift.

Implementation shape:

- Create a disposable copy of the live DB.
- Run representative retrieval traces under `conservative_legacy`, `shadow_compare`, and `graph_reinforced_v1`.
- Hash protected durable-memory tables before/after:
  - approved facts/procedures/episodes;
  - candidate/review state;
  - graph edges;
  - collapse/review artifacts if present.
- Record allowed write set, if any. Prefer read-only/no-write for this slice.
- Add rollback command or config reversal instructions and verify it restores legacy output.

Exit criteria:

- Protected durable tables unchanged.
- Rollback restores legacy policy and legacy retrieval order.
- Replay artifact proves exact commands and hashes.

### Phase R3: Live shadow runtime dogfood

Purpose: collect real runtime evidence while still returning legacy order to Hermes.

Implementation shape:

- Install/runtime config stays legacy for user-visible retrieval.
- Hook or diagnostic path records shadow comparison metadata only if it can do so without raw prompt/query storage.
- Shadow reports aggregate:
  - candidate would-have promoted/demoted refs;
  - avoid-hit risk;
  - empty retrieval impact;
  - latency budget;
  - failure/fallback rate.
- No raw query previews, prompts, or transcripts are stored.

Exit criteria:

- Fresh epoch has enough new-runtime observations to distinguish current behavior from historical rows.
- Candidate policy does not increase empty retrieval, avoid hits, or latency beyond agreed thresholds.
- Hermes hook doctor remains green after any runtime package update.

### Phase R4: Explicit opt-in-to-default migration

Purpose: make candidate ranking the default only for a deliberately migrated profile/runtime.

Implementation shape:

- Add an explicit command, for example:

  ```bash
  agent-memory dogfood retrieval-ranking-migrate-default \
    /Users/reddit/.agent-memory/memory.db \
    --fixtures tests/fixtures/retrieval_eval/expanded/live-compatible-50-gate.json \
    --policy graph_reinforced_v1 \
    --config-path /Users/reddit/.hermes/profiles/personal-oss/config.yaml \
    --actor <actor> \
    --reason <reason> \
    --approval-phrase migrate-retrieval-ranking-default-v1
  ```

- Command must:
  - run R1 fixture gate or require a fresh report path;
  - run R2 rollback/hash preflight or require a fresh report path;
  - write a migration audit artifact;
  - update only the explicit target config/runtime policy;
  - print exact rollback command.
- Rollback example:

  ```bash
  agent-memory dogfood retrieval-ranking-migrate-default \
    /Users/reddit/.agent-memory/memory.db \
    --fixtures tests/fixtures/retrieval_eval/expanded/live-compatible-50-gate.json \
    --policy conservative_legacy \
    --config-path /Users/reddit/.hermes/profiles/personal-oss/config.yaml \
    --actor <actor> \
    --reason rollback-to-legacy \
    --approval-phrase migrate-retrieval-ranking-default-v1
  ```

Exit criteria:

- One explicitly targeted profile migrated.
- One real Hermes turn succeeds with hook accepted and doctor green.
- Rollback has been tested on a disposable config or live config with explicit approval.
- No broad apply, auto-approval, collapse/delete apply, or raw storage was enabled.

### Phase R5: Default candidate becomes release default

Purpose: only after R4 proves stable, update the package default for new installs.

Implementation shape:

- Change code default from `conservative_legacy` to `graph_reinforced_v1` only after R4 evidence is documented.
- Existing installs should preserve explicit config unless the operator runs migration.
- Release notes must state:
  - new-install default;
  - existing-install behavior;
  - rollback command;
  - safety exclusions.

Exit criteria:

- Full suite green.
- CI release-readiness smoke green.
- Published install smoke green.
- Hermes hook doctor green after runtime update.

## Hard blockers before any default change

Do not proceed to R4/R5 unless all are true:

- Checked-in retrieval eval: 75/75 pass.
- Expanded fixture gate: 50-task gate pass.
- Baseline regression count: 0.
- Rollback/replay artifact exists and verifies protected durable tables unchanged.
- Live shadow runtime report is fresh enough to avoid historical-row false confidence.
- Fresh epoch diagnostics do not show unresolved high empty retrieval or metadata classification blockers.
- Human-reviewed queue approval path remains explicit and narrow.
- Ordinary conversation auto-approval remains false.
- Broad G4/background apply remains blocked.

## First implementation slice

Recommended next PR-sized slice:

1. Add named ranking policy enum/config plumbing while keeping `conservative_legacy` as the default.
2. Add retrieval diagnostic output that prints active policy.
3. Add shadow compare report mode that reuses the existing fixture comparison payload.
4. Add tests proving default/no-config behavior is byte-for-byte or order-for-order unchanged.
5. Update `.dev/status/current-handoff.md` with the R0/R1 result and next gate.

Do not implement the live config migration command in the first slice unless R0/R1 are already green and reviewed.
