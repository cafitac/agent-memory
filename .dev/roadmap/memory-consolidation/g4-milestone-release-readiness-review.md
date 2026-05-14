# G4 milestone release readiness review

Status: AI-authored draft. Not yet human-approved. No publish/release action executed.
Last updated: 2026-05-15 00:14 KST

## Scope reviewed

This review covers the accumulated `develop` G4 operator corridor after `v0.1.161` / `main`.

Compared range: `main..develop`.

Included commits:

- `539f929` feat: add g4 human approval artifact gate
- `9c4f303` feat: add g4 apply readiness report
- `d75e034` feat: add g4 operator apply bundle
- `189af4a` docs: record g4 operator bundle smoke
- `84af7a5` feat: add g4 readiness gate summary
- `e0bc642` feat: add g4 post-apply verification gate
- `204e63f` docs: harden g4 bounded apply runbook
- `c7b6e0c` feat: add g4 operator apply packet
- `d92b2e9` docs: record g4 operator apply packet status
- `e6eb7c1` feat: add g4 packet runbook contract

Changed tracked files vs `main`:

- `.dev/roadmap/memory-consolidation/current-progress-and-next-steps.md`
- `.dev/roadmap/memory-consolidation/g4-bounded-operator-apply-runbook.md`
- `.dev/status/current-handoff.md`
- `.dev/status/next-agent-memory-action.md`
- `src/agent_memory/api/cli.py`
- `tests/test_cli.py`

## Readiness verdict

Recommendation: release candidate is source-ready for a milestone release after a human maintainer reviews the release intent, but do not publish automatically from this generic continuation.

Reasoning:

- Source tests are green.
- Release metadata is internally synced at current version `0.1.161`.
- The auto-release workflow is expected to bump on main merge; current `develop` still intentionally reports `0.1.161` before release.
- npm package dry-run contents remain minimal and exclude internal `.dev`, dogfood, report, cache, worktree, and learner artifacts.
- The new G4 corridor remains read-only/report-only until exact approval is supplied.
- The release would expose safer operator tooling, not live broad automation.

Suggested release shape if approved later:

- Candidate next version: `v0.1.162` by patch bump from `0.1.161`.
- Release theme: G4 bounded operator apply readiness corridor.
- Do not include a default ranking migration, telemetry reset, broad/background G4 apply, collapse/delete apply, unreviewed promotion, or ordinary conversation auto-approval in the release action.

## Checks run

Source/full test gate:

```bash
PYTHONPATH=src .venv/bin/python -m compileall src
PYTHONPATH=src .venv/bin/python -m pytest tests/ -q
```

Result: `326 passed, 1 xfailed`.

Release metadata:

```bash
PYTHONPATH=src .venv/bin/python scripts/check_release_metadata.py
```

Result:

```json
{
  "python_package_name": "cafitac-agent-memory",
  "python_package_version": "0.1.161",
  "npm_package_name": "@cafitac/agent-memory",
  "npm_package_version": "0.1.161",
  "module_version": "0.1.161"
}
```

Release readiness smoke:

```bash
PYTHONPATH=src .venv/bin/python scripts/smoke_release_readiness.py
```

Result: Python bootstrap/doctor and Node wrapper bootstrap/doctor all returned success in an isolated temporary HOME.

npm package surface:

```bash
npm pack --dry-run --json
```

Resulting tarball files:

- `LICENSE`
- `README.md`
- `bin/agent-memory.js`
- `package.json`

Focused release/package tests:

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/test_release_metadata.py tests/test_release_workflows.py tests/test_npm_launcher.py tests/test_published_install_smoke.py -q
```

Result: `34 passed`.

Develop diff inventory:

```bash
git diff --stat main..develop
git diff --name-status main..develop
git log --oneline main..develop
```

Result: 10 commits after `main`, 6 tracked files changed, all in G4 corridor source/tests/docs/status.

npm dry-run package content guard:

```bash
python - <<'PY'
import json
from pathlib import Path
p=Path('/tmp/agent-memory-npm-pack-dry-run.json')
payload=json.loads(p.read_text())
files=[f['path'] for f in payload[0]['files']]
for forbidden in ['.dev/', '.agent-learner/', '.claude/', '.worktrees/', 'reports/', 'dogfood']:
    assert not any(forbidden in f for f in files), forbidden
print('npm package dry-run contents ref-safe')
PY
```

Result: passed.

## Safety boundary for this milestone

This release-readiness review does not authorize or execute live apply.

Still blocked without separate exact approval:

- live bounded G4 queue apply;
- repeated G4 apply;
- broad/background G4 apply;
- default-ranking migration;
- live telemetry reset;
- collapse/delete apply;
- unreviewed promotion;
- ordinary conversation auto-approval.

Live bounded G4 queue apply remains permitted only through the existing explicit corridor with all required inputs:

- exact approval phrase: `apply-approved-g4-review-queue-items-v1`;
- policy: `g4-review-queue-apply-v1`;
- actor;
- private reason;
- backup path;
- audit output path;
- bounded `--max-apply`.

## Open follow-up before actual publish

If a maintainer chooses to release this milestone later:

1. Ensure the release branch/PR path is intentional; current local branch is `develop` and `main` is still at `v0.1.161`.
2. Re-run the full source test gate immediately before merge/release.
3. Let the configured release workflow bump versions, or run the existing project release process if manual release is required.
4. After publish, run real downloaded install QA against the exact published `v0.1.162` artifacts, including npm and PyPI/uvx smoke.
5. Record published-runtime QA artifacts under `/Users/reddit/.agent-memory/reports/` before considering the milestone externally complete.

## Current next recommendation

Best next action after this review: ask for human approval to proceed with the release process, or continue read-only source/docs hardening. Do not infer release/publish approval from this review.
