# Install smoke recipes

Use these checks after publishing or when changing install/launcher behavior. Run them from a temporary directory, not from the source checkout.

## Hermes plugin install

```bash
hermes plugins install cafitac/agent-memory --enable
hermes plugins list
```

Expected:

- `agent-memory` appears as an enabled plugin
- Hermes can call the `pre_llm_call` plugin hook without editing `~/.hermes/config.yaml`
- the local memory database defaults to `~/.agent-memory/memory.db`

## npm global install

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

Expected:

- `agent-memory` is available on `PATH`
- `agent-memory bootstrap` creates or reuses `~/.agent-memory/memory.db`
- `agent-memory doctor` exits successfully and reports the local setup status

Optional cleanup:

```bash
npm uninstall -g @cafitac/agent-memory
```

## npm one-shot install

Use this when you do not want a global install:

```bash
npm exec --yes --package @cafitac/agent-memory -- agent-memory doctor
```

For an exact published version:

```bash
npm exec --yes --package @cafitac/agent-memory@<version> -- agent-memory doctor
```

Immediately after a release, the npm wrapper can briefly see stale Python package index data. If npm shows that the version exists but the delegated Python package cannot be resolved yet, retry once with a cache-busting environment:

```bash
UV_NO_CACHE=1 npm exec --yes --package @cafitac/agent-memory@<version> -- agent-memory doctor
```

## Maintainer release smoke

For release validation, check the exact published version from a clean temporary directory:

```bash
cd /tmp
npm view @cafitac/agent-memory version
npm exec --yes --package @cafitac/agent-memory@<version> -- agent-memory doctor
```

If install behavior changed, also run the published install smoke workflow:

```bash
gh workflow run published-install-smoke.yml \
  --repo cafitac/agent-memory \
  -f version=<version> \
  -f attempts=6 \
  -f propagation_attempts=12 \
  -f propagation_delay_seconds=10
```

## What to capture if smoke fails

Record:

- install command used
- platform and shell
- stdout/stderr
- output of `agent-memory doctor`
- whether `~/.agent-memory/memory.db` was created

Keep private data private. Do not paste or commit local databases, backup bundles, exported graph files, or debug reports.
