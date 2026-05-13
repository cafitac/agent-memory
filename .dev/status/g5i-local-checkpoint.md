# G5i local checkpoint

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-13 11:08 KST

## Implemented local slice

The requested five G5i follow-ups are implemented behind existing safe dogfood surfaces:

1. `dogfood rollback-replay-validate` now includes a ref-safe `rollup` for accumulated live-style replay reports: checked count, passed/failed replay counts, policy counts, latest application timestamp, and live accumulation safety.
2. `dogfood retrieval-ranking-experiment` now reports `fixture_expansion`: task count, live-compatible task count, scoped task count, rationale coverage, fixture source counts, and live-runtime-safe status.
3. `dogfood decay-collapse-decision` now exposes `collapse_equivalence_proof`, keeping collapse/delete blocked until rollback replay, relation equivalence/supersession chain, retrieval eval, and human-reviewed candidate payload evidence are all green.
4. `dogfood telemetry-reconciliation` now documents the telemetry-only apply safety gate, and `dogfood telemetry-reset-apply` reports a post-apply quality gate after verifying backup, exact candidate deletion, zero remaining preview candidates, and unchanged protected memory tables.
5. `dogfood g4-review-queue-preview` now reports `broad_g4_apply_reassessment`, explicitly keeping broad G4 apply blocked until retrieval ranking, rollback confidence, rollback replay, live telemetry reconciliation, and human-reviewed queue approval gates are all green.

## Guardrails unchanged

- Default retrieval ranking is unchanged.
- Ordinary conversation auto-approval remains forbidden.
- Collapse/delete apply remains blocked.
- Broad G4/background apply remains blocked.
- Telemetry reset apply remains opt-in only: epoch filter, backup, policy, approval phrase, actor, and reason are required.

## Verification

Focused verification run locally:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_dogfood_g5h_next_brainlike_steps_are_read_only_or_guarded \
  tests/test_cli.py::test_python_module_cli_dogfood_telemetry_reset_apply_is_guarded_and_telemetry_only \
  tests/test_cli.py::test_dogfood_decay_collapse_preview_reports_stale_weak_evidence_without_mutation -q

.venv/bin/python -m pytest tests/test_retrieval_evaluation.py -q
```

Observed result: 3 CLI-focused tests passed; 59 retrieval-evaluation tests passed.

Full suite still needs to be run before release.
