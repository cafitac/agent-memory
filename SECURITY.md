# Security Policy

## Supported versions

agent-memory is currently pre-1.0 alpha software. Security fixes are released on the latest published version only unless a maintainer explicitly announces otherwise.

Use the latest version from npm or PyPI:

```bash
npm view @cafitac/agent-memory version
python - <<'PY'
import json, urllib.request
print(json.load(urllib.request.urlopen('https://pypi.org/pypi/cafitac-agent-memory/json'))['info']['version'])
PY
```

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that exposes private data, credentials, local files, or command execution risk.

Report privately by using GitHub's private vulnerability reporting flow if it is enabled for the repository:

https://github.com/cafitac/agent-memory/security/advisories/new

If that flow is unavailable, open a minimal public issue that says you need a private security contact, but do not include exploit details, secrets, or sensitive logs.

A useful report includes:

- affected version
- install surface used: npm, pipx, uv tool, source checkout, or other
- operating system and shell
- exact command or hook path involved
- whether the issue requires a malicious local user, malicious memory content, malicious repository, or remote input
- redacted logs
- safe reproduction steps

## Local security model

agent-memory is local-first. The default memory database is a SQLite file at:

```text
~/.agent-memory/memory.db
```

The default Hermes config path touched by bootstrap is:

```text
~/.hermes/config.yaml
```

Security-relevant behavior:

- `agent-memory bootstrap` may create or modify the Hermes config file to install a shell hook.
- Existing Hermes hooks are preserved and the agent-memory hook is appended.
- Changed existing config files are backed up to `*.agent-memory.bak`.
- The hook command retrieves approved local memories and emits bounded prompt context.
- The hook does not intentionally upload the SQLite database to an agent-memory-hosted service.
- The core CLI does not execute memory text as code.

## User responsibilities

Treat the SQLite database as sensitive. It may contain project names, personal notes, internal procedures, and source excerpts that you or your agents chose to store.

Recommended practices:

- keep `~/.agent-memory/` out of git repositories
- do not paste secrets into memories
- review generated/candidate memories before approval
- use filesystem permissions appropriate for your machine
- inspect `~/.hermes/config.yaml` after bootstrap if you have custom hooks
- remove or rotate sensitive memories if a secret is accidentally stored

## Known limitations

- agent-memory does not currently provide built-in encryption-at-rest for the SQLite file.
- agent-memory does not currently provide automatic secret scanning/redaction before memory creation.
- Syncing the database across machines is user-managed and outside the default trust boundary.
- Prompt context is visible to the host agent/model that receives it; do not approve memories that should never enter prompts.

## Maintainer release checks

Before treating a release as externally ready, maintainers should verify:

```bash
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
```

After publishing, run at least one clean install smoke from the real registry. See `docs/install-smoke.md`.
