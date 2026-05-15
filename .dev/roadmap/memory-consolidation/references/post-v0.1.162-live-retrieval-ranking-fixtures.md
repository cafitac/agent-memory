# Post-v0.1.162 live retrieval-ranking fixture generation checkpoint

Context: after G5 trace-candidate application audit learned to require rollback replay and retrieval-ranking evidence, the remaining gap was that live audit smoke still used a manually shaped ranking report because checked-in fixtures did not resolve against the actual live DB.

What changed in source:

- Added `dogfood live-retrieval-ranking-fixtures <db_path>`.
- The command reads approved facts, procedures, and episodes that already exist in the target DB and writes a retrieval-eval fixture JSON to `--fixture-output`.
- Generated tasks use numeric live refs, preferred scopes, expected IDs, empty avoid lists, source `live-db-approved-memory`, and ref-safe rationales.
- Output report kind is `dogfood_live_retrieval_ranking_fixtures` and remains read-only/no-mutation/default-retrieval-unchanged.
- The command does not include raw source content, raw transcripts, raw reviewed payloads, private reasons, backup content, or secret-like fields.

Validation contract:

- The generated fixture must be directly consumable by `dogfood retrieval-ranking-experiment --fixtures <fixture>` against the same DB.
- The ranking experiment must remain read-only, non-mutating, default-ranking unchanged, with zero baseline regressions before it is accepted as application-audit evidence.
- Feeding the generated ranking report plus rollback replay report into `dogfood trace-candidate-application-audit` should satisfy `required_evidence_gate` without manually shaped compatible artifacts.

Verification from the source checkpoint:

- RED: focused test failed because `live-retrieval-ranking-fixtures` was not a recognized dogfood action.
- Focused test after implementation: `uv run pytest tests/test_cli.py::test_dogfood_live_retrieval_ranking_fixtures_generate_live_compatible_fixture -q` -> `1 passed`.
- Evidence/audit subset: `uv run pytest tests/test_cli.py -q -k 'live_retrieval_ranking_fixtures or retrieval_ranking_experiment or trace_candidate_application_audit'` -> `2 passed, 147 deselected`.
- Live source smoke against `/Users/reddit/.agent-memory/memory.db` wrote `/Users/reddit/.agent-memory/reports/source-live-ranking-fixtures-20260515T054056Z/`.
- Live generated fixture stats: `fixture_task_count=4`, facts `2`, procedures `1`, episodes `1`.
- Live ranking experiment stats: `fixture_task_count=4`, `live_compatible_task_count=4`, `ranking_change_allowed=true`, `baseline_regression_count=0`, read-only/no-mutation.
- Live application audit with generated ranking evidence and rollback replay evidence passed: `required_evidence_gate.pass=true`, quality decision `trace_candidate_applications_ready_for_post_apply_review`, read-only/no-mutation.

Safety boundary:

- This is evidence generation only.
- It does not apply trace candidates, execute G4 apply, change default ranking, reset telemetry, collapse/delete memory, repeat apply, approve unreviewed promotion, or enable ordinary-conversation auto-approval.
- Generated fixtures are live-DB-specific artifacts and should stay under local report directories; do not commit them.

Recommended next slice:

1. Harden the live fixture generator for realistic candidate volume and unstable lexical queries: add skip/blocker diagnostics for generated tasks that fail retrieval eval instead of silently treating small live DB coverage as enough.
2. Optionally add an application-audit convenience input that points to the generated fixture and runs the read-only ranking experiment internally, while preserving explicit artifact hashes.
3. Keep all broad/background apply and default ranking migration blocked until repeated generated live fixture reports are green.
