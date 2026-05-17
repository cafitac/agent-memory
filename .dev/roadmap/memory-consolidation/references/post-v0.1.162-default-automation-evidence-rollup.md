# Post-v0.1.162 default automation verifier smoke and evidence rollup

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-17 16:11 KST

## Scope

This checkpoint adds and validates the read-only repeated-evidence gate after the ordinary-turn default automation one-candidate corridor:

- `dogfood ordinary-turn-default-automation-evidence-rollup`
- copy-live smoke of default automation policy gate -> dry-run -> exact one-candidate apply -> rollback replay -> post-apply verifier -> repeated evidence rollup

It does not enable ordinary conversation auto-approval, unattended default/background apply, default retrieval changes, collapse/delete, telemetry reset, unreviewed promotion, or repeated apply without fresh exact evidence.

## Command contract

```bash
agent-memory dogfood ordinary-turn-default-automation-evidence-rollup \
  --post-apply-verification-report <default-post-apply-verification-1.json> \
  --post-apply-verification-report <default-post-apply-verification-2.json> \
  --expected-policy ordinary-turn-default-automation-policy-v1 \
  --min-green-reports 2 \
  --output <default-automation-evidence-rollup.json>
```

The command is read-only and aggregate/ref-safe. It validates:

- expected verifier kind: `dogfood_ordinary_turn_default_automation_post_apply_verification`;
- verifier reports are read-only, non-mutating, default-retrieval-safe, and ordinary-auto-approval false;
- exact policy match;
- verifier quality gates green;
- one-at-a-time apply evidence;
- valid trace/memory refs and no ref reuse across the rollup window;
- backup SHA/file evidence;
- rollback replay green status;
- application audit row;
- `ordinary_turn_default_automation_approved_as` relation evidence;
- privacy/ref safety and no forbidden authority.

Green decision:

```text
ordinary_turn_default_automation_repeated_post_apply_evidence_green_for_enablement_design_only
```

Red decision:

```text
collect_more_ordinary_turn_default_automation_evidence_before_enablement_design
```

## Copy-live smoke

Artifact directory:

```text
/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/
```

Safety boundary:

- The smoke copied `/Users/reddit/.agent-memory/memory.db`; it did not mutate the live DB.
- Synthetic non-secret preference-shaped ordinary turns were inserted only into copied DBs.
- Apply steps were run only against copied DBs.

Final green rollup:

```text
/Users/reddit/.agent-memory/reports/post-v0.1.162-default-automation-verifier-smoke-20260517T070356Z/default-automation-evidence-rollup.json
```

Observed aggregate result:

```text
quality_gate.pass=true
decision=ordinary_turn_default_automation_repeated_post_apply_evidence_green_for_enablement_design_only
green_report_count=2
applied_memory_count=2
unique_trace_ref_count=2
unique_memory_ref_count=2
default_auto_approval_enabled=false
apply_supported=false
apply_executed=false
ordinary_conversation_auto_approval=false
```

## Verification

Focused tests:

```bash
.venv/bin/python -m pytest \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_dry_run_blocks_red_policy_gate \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_post_apply_verification_green_stop \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_post_apply_verification_blocks_unsafe_artifacts \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_evidence_rollup_summarizes_repeated_green_verifiers \
  tests/test_cli.py::test_dogfood_ordinary_turn_default_automation_evidence_rollup_blocks_reused_or_red_verifiers \
  -q
```

Result:

```text
5 passed
```

Broader/full suite validation is pending at the time of this reference note.

## Safety interpretation

This checkpoint is very close to the scoped local human-brain-like lifecycle target, but it is intentionally still not autonomous default enablement. The new rollup proves repeated post-apply verifier evidence exists and is ref-safe; it does not flip a default, schedule unattended applies, or authorize ordinary conversation auto-approval.

Next safe slice: a read-only opt-in default enablement preflight/default-on design gate with hard fail-closed tests and explicit policy fields.
