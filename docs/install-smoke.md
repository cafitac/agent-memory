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
hermes hooks list
```

Expected outcomes:
- `agent-memory bootstrap` initializes `~/.agent-memory/memory.db` if missing
- Hermes config is created or merged at `~/.hermes/config.yaml`
- `agent-memory doctor` reports healthy setup status
- `hermes hooks list` shows the installed hook entry

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
hermes hooks list
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
hermes hooks list
```

Optional cleanup:

```bash
uv tool uninstall cafitac-agent-memory
```

## What to capture if smoke fails

Record:
- install command used
- platform / shell
- full stdout/stderr
- whether `~/.agent-memory/memory.db` was created
- whether `~/.hermes/config.yaml` was created or merged
- output of `agent-memory doctor`
- output of `hermes hooks list`

## Release note

As of the latest validated public install smoke, the validated tag is `v0.1.6`.
