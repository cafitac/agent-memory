# Post-v0.1.162 live evidence bundle

Status: AI-authored draft. Not yet human-approved.
Date: 2026-05-15

## Summary

Added a read-only `dogfood live-evidence-bundle` command that chains the current live evidence path into one repeatable operator/reporting workflow:

1. generate live retrieval-ranking fixtures from approved memories in the target DB;
2. emit live fixture generation/retrieval/reliability diagnostics;
3. run `retrieval-ranking-experiment` over the generated fixture;
4. run `rollback-replay-validate`;
5. run `trace-candidate-application-audit` using the generated rollback and ranking artifacts;
6. emit a top-level bundle report with artifact paths and SHA-256 hashes.

This is evidence orchestration only. It does not authorize or execute apply.

## Command

```bash
uv run python -m agent_memory.api.cli dogfood live-evidence-bundle /Users/reddit/.agent-memory/memory.db \
  --output-dir /Users/reddit/.agent-memory/reports/source-live-evidence-bundle-<timestamp> \
  --limit-per-type 20 \
  --min-reliable-tasks 4 \
  --application-limit 50 \
  --output /Users/reddit/.agent-memory/reports/source-live-evidence-bundle-<timestamp>/live-evidence-bundle.json
```

Output kind: `dogfood_live_evidence_bundle`.

Generated artifacts:

- `live-retrieval-ranking-fixtures.json`
- `live-retrieval-ranking-fixtures-report.json`
- `retrieval-ranking-experiment.json`
- `rollback-replay-validate.json`
- `trace-candidate-application-audit.json`
- `live-evidence-bundle.json` when `--output` is provided

## Safety contract

The bundle must remain:

- `read_only=true`
- `mutated=false`
- `default_retrieval_unchanged=true`
- `ordinary_conversation_auto_approval=false`
- `bundle_executes_apply=false`

It must not enable or imply permission for:

- broad/background G4 apply;
- live G4 apply without the exact operator corridor;
- default ranking migration;
- collapse/delete;
- telemetry reset;
- unreviewed promotion;
- repeated apply without new approval;
- ordinary-conversation auto-approval.

Privacy contract:

- no raw source content;
- no raw transcript;
- no raw query text;
- no raw trace summary;
- no reviewed payload;
- no backup contents;
- no raw report embedding.

## Verification

Source verification on 2026-05-15:

```bash
uv run pytest tests/test_cli.py::test_dogfood_live_evidence_bundle_chains_read_only_artifacts -q
# 1 passed

uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py \
  && uv run pytest tests/test_cli.py -q -k 'live_evidence_bundle or live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit or rollback_replay_validate'
# 5 passed, 147 deselected

uv run python -m compileall -q src/agent_memory/api/cli.py tests/test_cli.py \
  && uv run pytest tests/ -q
# 334 passed, 1 xfailed
```

Live source smoke:

- Path: `/Users/reddit/.agent-memory/reports/source-live-evidence-bundle-20260515T072811Z/live-evidence-bundle.json`
- DB: `/Users/reddit/.agent-memory/memory.db`
- Result: `quality_gate.pass=true`, `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`.
- Rollup: fixture tasks `4` (`facts=2`, `procedures=1`, `episodes=1`), fixture retrieval/reliability pass, ranking baseline regressions `0`, rollback checked application count `3`, audit application count `3`, audit required evidence gate pass.

## Interpretation

This raises the safety-gated operational roadmap to about 89-90%. The system now has a repeatable hash-addressed read-only bundle for the live evidence path. It is not full human-brain-like autonomy: broad consolidation apply, default ranking migration, autonomous collapse/delete, live telemetry reset, unreviewed promotion, repeated apply without fresh approval, and ordinary-conversation auto-approval remain blocked.

## Next safe slice

Add a read-only repeated-run comparison/accumulation command over two or more saved `dogfood_live_evidence_bundle` reports. It should report pass counts, blocker trends, artifact hashes, and fixture/ranking/audit stability without reading raw report bodies into output and without mutating the DB or repo.
