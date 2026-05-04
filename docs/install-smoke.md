# Install smoke recipes

This document records the approved post-publish smoke paths for agent-memory.

## Goal

Verify that published install surfaces work in a clean shell or clean machine without relying on the source checkout.

When validating multiple install surfaces on the same machine, run each path in a fresh shell or sanitize `PATH` so an earlier `agent-memory` binary does not shadow the surface under test.

Maintainer note: if you also isolate `HOME` during smoke runs, restore your normal maintainer shell context before using `gh` or `git push` against the repo again. For example, run GitHub operations from a fresh maintainer shell or temporarily set `HOME=/path/to/maintainer/home` for that command. Repositories maintained with SSH remotes and host aliases are less sensitive to `gh` HTTPS credential lookup, but the principle still applies to any tooling that reads credentials from `HOME`.

## npm path

Use this as the primary end-user onboarding path for Hermes-oriented CLI users.

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Expected outcomes:
- `agent-memory bootstrap` initializes `~/.agent-memory/memory.db` if missing
- Hermes config is created or merged at `~/.hermes/config.yaml`
- `agent-memory doctor` reports healthy setup status
- `hermes hooks doctor` reports that shell hooks are healthy

Optional cleanup:

```bash
npm uninstall -g @cafitac/agent-memory
```

## pipx path

Use this when the operator prefers Python-native installation while still avoiding a source checkout.

```bash
pipx install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Optional cleanup:

```bash
pipx uninstall cafitac-agent-memory
```

## uv tool path

Use this for users already standardizing on uv-managed CLI tools.

```bash
uv tool install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Optional cleanup:

```bash
uv tool uninstall cafitac-agent-memory
```


## Automated published smoke

The fast release path does not run the slow published install matrix by default. Feature PRs and release-sync PRs already run `ci.yml`; docs/workflow-only pushes are ignored by `auto-release.yml`; `publish.yml` is reserved for tag/manual publish, package build, registry publish, and GitHub Release creation. This keeps GitHub Actions minutes bounded while still leaving an explicit external-install gate when needed.

Run the published install matrix manually before a high-confidence external-user checkpoint, after a suspicious publish, or when changing launcher/install behavior:

```bash
gh workflow run published-install-smoke.yml \
  --repo cafitac/agent-memory \
  -f version=<version> \
  -f attempts=6 \
  -f propagation_attempts=12 \
  -f propagation_delay_seconds=10
```

For an inline smoke during a manual publish dispatch, opt in explicitly:

```bash
gh workflow run publish.yml \
  --repo cafitac/agent-memory \
  --ref v<version> \
  -f publish_pypi=true \
  -f publish_npm=true \
  -f run_published_install_smoke=true
```

The workflows execute `scripts/smoke_published_install.py`, which validates the exact published version through npm registry lookup, `npx`, `npm exec`, `uvx`, and `pipx` from isolated temporary homes. Smoke artifacts are uploaded as `published-install-smoke-result` and include failure summaries plus registry propagation diagnostics.

Local maintainer smoke for the current `package.json` version:

```bash
uv run python scripts/smoke_published_install.py --attempts 3 --delay-seconds 10
```

## Fresh-user trust matrix

Before treating a release as ready for external users, validate these surfaces from an external temp directory, not from the source checkout:

| Surface | Required checks | Expected safety property |
| --- | --- | --- |
| npm | `npm exec --yes --package @cafitac/agent-memory@<version> agent-memory -- --help`; seed one approved memory; run `hermes-context` | direct `agent-memory [command]` UX works and prompt text includes only approved memory content |
| npx | `npx --yes @cafitac/agent-memory@<version> --help` | no source checkout or local PATH dependency |
| uvx | `uvx --refresh cafitac-agent-memory==<version> agent-memory --help` | PyPI package resolves independently of npm wrapper |
| Hermes | `agent-memory bootstrap`; `agent-memory doctor`; `hermes hooks doctor`; one QA prompt with hooks accepted | hook install is merge-safe, bounded by conservative prompt budgets, and fails closed if memory DB is unavailable |
| Codex/Claude prompts | `agent-memory codex-prompt ...`; `agent-memory claude-prompt ...` after seeding approved memory | prompt wrappers include actual approved snippets and exclude disputed/deprecated content by default |
| Forensic review | `agent-memory retrieve ... --status all`; `agent-memory review conflicts fact ...`; `agent-memory review history fact ...`; `agent-memory review replacements fact ...`; `agent-memory review relate-conflict fact ... --actor ... --reason ...`; `agent-memory review explain fact ...` | obsolete/conflicting memory can be inspected intentionally with status-transition reason/evidence history, same-claim alternatives, default-retrieval visibility, reviewed supersedes/replaces chains, and explicit reviewed conflict relation refs without entering normal prompts |

## What to capture if smoke fails

Record:
- install command used
- platform / shell
- full stdout/stderr
- whether `~/.agent-memory/memory.db` was created
- whether `~/.hermes/config.yaml` was created or merged
- output of `agent-memory doctor`
- output of `hermes hooks doctor`

## Release note

As of the latest validated public install smoke, the validated tag is `v0.1.18`. The primary npm path is expected to leave users with a direct shell command: `agent-memory [command]`; docs should not require users to type `uv`, `uvx`, or `python -m` after npm installation.
