# G4 bounded operator apply runbook

Status: AI-authored draft. Not yet human-approved. Do not execute live apply without explicit operator approval.
Last updated: 2026-05-14 23:12 KST

## Purpose

This runbook documents the exact live-apply corridor that follows the green source-checkout G4 operator bundle smoke. It deliberately separates readiness from authorization.

The current verified readiness artifacts are:

- operator bundle: `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`
- readiness summary: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`
- no-live-apply post-apply verifier smoke: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-post-apply-verification-smoke-20260514T121220Z/g4-post-apply-verification.json`

The first two artifacts are green and show bounded readiness. The third is intentionally red because no real apply artifact exists. None of them authorizes live apply by itself.

Additional source-checkout packet artifact:

- operator packet: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-operator-apply-packet-20260514T141141Z/g4-operator-apply-packet.json`

The operator packet is also read-only and exists to make the checklist machine-readable. It is not authorization and does not execute apply.

## One-screen operator checklist

Do not proceed to live apply unless every checkbox is true.

Pre-authorization checks:

- [ ] User/operator explicitly says this is a live bounded G4 review-queue apply, not generic continuation.
- [ ] Exact approval phrase is present: `apply-approved-g4-review-queue-items-v1`.
- [ ] Exact policy is present: `g4-review-queue-apply-v1`.
- [ ] Actor string is present.
- [ ] Private reason is present and will not be committed or printed in public/ref-safe artifacts.
- [ ] Backup path is under a private local report directory.
- [ ] Audit output path is under the same private local report directory.
- [ ] Bounded `--max-apply` is present and small. Default recommendation is `3`; never infer a larger value from queue count.

Pre-apply evidence checks:

- [ ] Optional machine-readable packet `g4-operator-apply-packet.json` has `kind=dogfood_g4_operator_apply_packet`, `quality_gate.pass=true`, and `apply_executed=false`.
- [ ] `g4-operator-apply-bundle.json` has `quality_gate.pass=true`.
- [ ] `g4-readiness-gate-summary.json` has `quality_gate.pass=true`.
- [ ] All pre-apply artifacts say `read_only=true`, `mutated=false`, and `default_retrieval_unchanged=true`.
- [ ] Pre-apply bundle says `apply_executed=false`, `apply_supported=false`, and `broad_g4_apply_allowed=false`.
- [ ] Privacy flags confirm no raw proposal JSON, raw content, raw query text, raw trace summary, raw reason, or sample values.

Post-apply stop checks:

- [ ] After any approved apply, run a new post-apply operator bundle.
- [ ] Run `dogfood g4-post-apply-verification` against the saved apply artifact, post-apply operator bundle, and rollback replay artifact.
- [ ] Stop after the first approved bounded apply. Do not run a second apply without a fresh explicit approval packet.

If any checkbox is false, stop after read-only verification.

## Current readiness evidence

Source-checkout smoke:

- Command family: `agent-memory dogfood g4-operator-apply-bundle`.
- Live DB checked: `/Users/reddit/.agent-memory/memory.db`.
- Report directory: `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/`.
- Queue count: `8`.
- Bundle decision: `operator_apply_bundle_ready_for_exact_manual_apply`.
- Bundle safety: `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`, ordinary conversation auto-approval false.
- Privacy: no raw proposal JSON, raw content, raw query text, raw trace summary, raw reason, or sample values in the public/ref-safe artifacts.

Child artifacts:

- `g4-review-queue-approval-report.json` sha256 `0efbb0a1376afc950a73908bb3798a2549e40b0395016b271b71b105dc725a46`.
- `g4-review-queue-preview.json` sha256 `3a985fd1264f4ca7a0ee52f816ca2531b056951dd17d8aea17f15bddcb68ea93`.
- `g4-apply-readiness.json` sha256 `041f27ecc75923930fed0cac1e7c9678d663b3827d0253786590b3703df4fc7e`.

Readiness-summary smoke:

- Artifact: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json`.
- Expected state: `kind=dogfood_g4_readiness_gate_summary`, `quality_gate.pass=true`, `read_only=true`, `mutated=false`, `default_retrieval_unchanged=true`.
- This is stronger preflight evidence, not authorization.

Post-apply verifier smoke:

- Artifact: `/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-post-apply-verification-smoke-20260514T121220Z/g4-post-apply-verification.json`.
- Expected state before real apply: `kind=dogfood_g4_post_apply_verification`, `read_only=true`, `mutated=false`, `quality_gate.pass=false`.
- Expected blocker before real apply: `apply_report_mutation_not_confirmed`.
- This proves the verifier blocks placeholder/no-live-apply artifacts instead of becoming an apply trigger.

## Authorization boundary

Generic continuation does not authorize this runbook.

Before any live apply, the operator must explicitly approve live bounded G4 queue apply and provide/confirm:

1. live DB path: `/Users/reddit/.agent-memory/memory.db`;
2. backup path under a private local report directory;
3. audit output path under the same private local report directory;
4. actor string;
5. private reason string;
6. bounded `--max-apply` value;
7. exact policy: `g4-review-queue-apply-v1`;
8. exact approval phrase: `apply-approved-g4-review-queue-items-v1`.

Without all eight items, stop after read-only verification.

## Pre-apply read-only verification

Use this only to re-check saved readiness artifacts. It is safe because it is read-only and no-mutation.

Machine-readable packet command, also read-only/no-mutation:

```bash
PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli dogfood g4-operator-apply-packet \
  /Users/reddit/.agent-memory/memory.db \
  --operator-apply-bundle-report /Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json \
  --readiness-gate-summary-report /Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json \
  --actor <operator-or-agent-id> \
  --max-apply 1 \
  --output /Users/reddit/.agent-memory/reports/<private-run-dir>/g4-operator-apply-packet.json
```

Expected packet state: `kind=dogfood_g4_operator_apply_packet`, `quality_gate.pass=true`, `read_only=true`, `mutated=false`, `apply_executed=false`, `apply_supported=false`, `broad_g4_apply_allowed=false`.

```bash
RUN_DIR=/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z
SUMMARY=/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json
python - <<'PY'
import json
from pathlib import Path
bundle_path = Path('/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json')
summary_path = Path('/Users/reddit/.agent-memory/reports/v0.1.162-source-g4-readiness-summary-20260514T115854Z/g4-readiness-gate-summary.json')
bundle = json.loads(bundle_path.read_text())
summary = json.loads(summary_path.read_text())
assert bundle['kind'] == 'dogfood_g4_operator_apply_bundle'
assert bundle['quality_gate']['pass'] is True
assert bundle['bounded_partial_apply_ready'] is True
assert bundle['read_only'] is True
assert bundle['mutated'] is False
assert bundle['apply_executed'] is False
assert bundle['apply_supported'] is False
assert bundle['broad_g4_apply_allowed'] is False
assert bundle['default_retrieval_unchanged'] is True
assert bundle['ordinary_conversation_auto_approval'] is False
privacy = bundle['privacy']
for key in [
    'proposal_json_included',
    'raw_content_included',
    'raw_query_text_included',
    'raw_reason_included',
    'raw_trace_summary_included',
    'sample_values_included',
]:
    assert privacy[key] is False, key
assert summary['kind'] == 'dogfood_g4_readiness_gate_summary'
assert summary['quality_gate']['pass'] is True
assert summary['read_only'] is True
assert summary['mutated'] is False
assert summary['default_retrieval_unchanged'] is True
assert summary['operator_apply_bundle_gate']['pass'] is True
assert summary['retrieval_ranking_gate']['pass'] is True
print('g4 pre-apply read-only verification passed')
PY
```

If this fails, do not apply.

## Exact live apply command shape

Do not paste this command until the operator explicitly approves live apply and supplies a private reason and backup path.

```bash
APPLY_TS=$(date -u +%Y%m%dT%H%M%SZ)
APPLY_DIR=/Users/reddit/.agent-memory/reports/g4-bounded-apply-${APPLY_TS}
mkdir -p "$APPLY_DIR"

PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli \
  dogfood g4-review-queue-apply /Users/reddit/.agent-memory/memory.db \
  --policy g4-review-queue-apply-v1 \
  --approval-phrase apply-approved-g4-review-queue-items-v1 \
  --actor <OPERATOR_ACTOR> \
  --reason <PRIVATE_REASON_DO_NOT_COMMIT_OR_PRINT> \
  --backup-path "$APPLY_DIR/memory-before-g4-review-queue-apply.db" \
  --output "$APPLY_DIR/g4-review-queue-apply.json" \
  --max-apply <BOUNDED_MAX_APPLY>
```

Recommended first live bound if the operator does not specify otherwise: `--max-apply 3`, because the green readiness bundle was generated with max apply `3` even though the queue count was `8`.

## Post-apply verification

Immediately after any approved live apply, run these checks before considering further mutation.

```bash
APPLY_OUTPUT="$APPLY_DIR/g4-review-queue-apply.json"
export APPLY_OUTPUT
python - <<'PY'
import hashlib
import json
import os
from pathlib import Path
p = Path(os.environ['APPLY_OUTPUT'])
payload = json.loads(p.read_text())
assert payload.get('kind') == 'dogfood_g4_review_queue_apply'
assert payload.get('read_only') is False
assert payload.get('mutated') is True
assert payload.get('policy') == 'g4-review-queue-apply-v1'
assert payload.get('approval_phrase_matched') is True
assert payload.get('default_retrieval_unchanged') is True
assert payload.get('memory_status_mutated') is False
assert payload.get('ordinary_conversation_auto_approval') is False
assert payload.get('applied_count', 0) <= payload.get('max_apply', 0)
backup = payload.get('backup') or {}
backup_path = Path(backup['path'])
assert backup_path.exists()
assert hashlib.sha256(backup_path.read_bytes()).hexdigest() == backup['sha256']
print('g4 bounded apply output and backup checks passed')
PY

PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli \
  dogfood g4-operator-apply-bundle /Users/reddit/.agent-memory/memory.db \
  --report-dir "$APPLY_DIR/post-apply-readiness" \
  --retrieval-ranking-report /Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/retrieval-ranking-shadow.json \
  --rollback-confidence-report /Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-confidence.json \
  --rollback-replay-report /Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-replay-validate.json \
  --telemetry-reconciliation-report /Users/reddit/.agent-memory/reports/v0.1.161-fresh-runway-green-20260514T103021Z/green-telemetry-reconciliation.json \
  --actor <OPERATOR_ACTOR> \
  --reason post-apply-read-only-verification \
  --max-apply <BOUNDED_MAX_APPLY> \
  --output "$APPLY_DIR/post-apply-readiness/g4-operator-apply-bundle.json"

PYTHONPATH=src .venv/bin/python -m agent_memory.api.cli \
  dogfood g4-post-apply-verification /Users/reddit/.agent-memory/memory.db \
  --apply-report "$APPLY_DIR/g4-review-queue-apply.json" \
  --post-apply-bundle-report "$APPLY_DIR/post-apply-readiness/g4-operator-apply-bundle.json" \
  --rollback-replay-report /Users/reddit/.agent-memory/reports/v0.1.161-next-gates-20260514T103215Z/rollback-replay-validate.json \
  --output "$APPLY_DIR/g4-post-apply-verification.json"
```

The final `g4-post-apply-verification.json` must report:

- `kind=dogfood_g4_post_apply_verification`;
- `read_only=true`;
- `mutated=false`;
- `quality_gate.pass=true`;
- `quality_gate.decision=g4_post_apply_verification_green_stop_before_next_mutation`;
- `next_step=stop_or_collect_operator_review_before_any_further_mutation`.

After this green post-apply verifier, stop. A second apply requires a fresh explicit approval packet.

## Stop conditions

Stop immediately and do not retry by loosening guardrails if any of these happen:

- pre-apply bundle verification fails;
- pre-apply readiness summary fails;
- backup path cannot be created;
- backup SHA-256 does not match the apply artifact;
- apply output is missing or malformed;
- apply output does not confirm exact policy and exact approval phrase;
- apply output has `applied_count > max_apply`;
- apply output mutates memory status instead of only reinforcement/audit state;
- post-apply read-only bundle verification fails;
- `dogfood g4-post-apply-verification` is not green after a real apply;
- any command emits raw reason/content/query/trace/proposal JSON in public artifacts;
- `default_retrieval_unchanged` becomes false;
- command suggests broad/background apply, collapse/delete, telemetry reset, default-ranking migration, unreviewed promotion, repeated apply without new approval, or ordinary conversation auto-approval.

## Explicit non-goals

This runbook does not authorize:

- broad G4/background apply;
- live telemetry reset;
- default-ranking migration from `conservative_legacy`;
- collapse/delete apply;
- unreviewed memory promotion;
- repeated apply without a fresh explicit approval packet;
- ordinary conversation auto-approval;
- raw transcript/raw prompt/raw query persistence.
