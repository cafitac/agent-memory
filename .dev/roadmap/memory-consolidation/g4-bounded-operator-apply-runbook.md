# G4 bounded operator apply runbook

Status: AI-authored draft. Not yet human-approved. Do not execute without explicit operator approval.
Last updated: 2026-05-14 20:48 KST

## Purpose

This runbook documents the exact live-apply corridor that follows the green source-checkout G4 operator bundle smoke. It deliberately separates readiness from authorization.

The current verified readiness artifact is:

- `/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json`

That artifact is green and reports `bounded_partial_apply_ready=true`, but it did not apply anything and does not authorize apply by itself.

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

Use this only to re-check the latest readiness bundle. It is safe because it is read-only and no-mutation.

```bash
RUN_DIR=/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z
python - <<'PY'
import json
from pathlib import Path
p = Path('/Users/reddit/.agent-memory/reports/v0.1.161-source-g4-operator-bundle-smoke-20260514T114822Z/g4-operator-apply-bundle.json')
payload = json.loads(p.read_text())
assert payload['kind'] == 'dogfood_g4_operator_apply_bundle'
assert payload['quality_gate']['pass'] is True
assert payload['bounded_partial_apply_ready'] is True
assert payload['read_only'] is True
assert payload['mutated'] is False
assert payload['apply_executed'] is False
assert payload['apply_supported'] is False
assert payload['broad_g4_apply_allowed'] is False
assert payload['default_retrieval_unchanged'] is True
assert payload['ordinary_conversation_auto_approval'] is False
privacy = payload['privacy']
for key in [
    'proposal_json_included',
    'raw_content_included',
    'raw_query_text_included',
    'raw_reason_included',
    'raw_trace_summary_included',
    'sample_values_included',
]:
    assert privacy[key] is False, key
print('g4 operator bundle pre-apply verification passed')
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
import json, os
from pathlib import Path
p = Path(os.environ['APPLY_OUTPUT'])
payload = json.loads(p.read_text())
assert payload.get('read_only') is False
assert payload.get('mutated') is True
assert payload.get('policy') == 'g4-review-queue-apply-v1'
assert payload.get('approval_phrase_matched') is True
print('g4 bounded apply output basic checks passed')
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
```

The post-apply bundle must remain read-only/no-mutation and must not expose raw reason/content/query/trace/proposal JSON.

## Stop conditions

Stop immediately and do not retry by loosening guardrails if any of these happen:

- pre-apply bundle verification fails;
- backup path cannot be created;
- apply output is missing or malformed;
- apply output does not confirm exact policy and exact approval phrase;
- post-apply read-only verification fails;
- any command emits raw reason/content/query/trace/proposal JSON in public artifacts;
- `default_retrieval_unchanged` becomes false;
- command suggests broad/background apply, collapse/delete, telemetry reset, default-ranking migration, unreviewed promotion, or ordinary conversation auto-approval.

## Explicit non-goals

This runbook does not authorize:

- broad G4/background apply;
- live telemetry reset;
- default-ranking migration from `conservative_legacy`;
- collapse/delete apply;
- unreviewed memory promotion;
- ordinary conversation auto-approval;
- raw transcript/raw prompt/raw query persistence.
