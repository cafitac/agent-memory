# agent-memory

[![CI](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/@cafitac/agent-memory.svg)](https://www.npmjs.com/package/@cafitac/agent-memory)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local-first memory for AI agents.

`agent-memory` gives CLI agents a small SQLite-backed memory layer for storing approved facts, procedures, and other durable context locally. The default setup keeps your memory database on your machine at `~/.agent-memory/memory.db`.

## Install

Recommended npm install:

```bash
npm install -g @cafitac/agent-memory
```

Initialize the local database and check that the CLI works:

```bash
agent-memory bootstrap
agent-memory doctor
```

That is enough for the default local setup.

## One-shot usage without global install

If you do not want to install globally, run the CLI through npm:

```bash
npm exec --yes --package @cafitac/agent-memory -- agent-memory doctor
```

## Basic example

```bash
DB=~/.agent-memory/memory.db

agent-memory init "$DB"
agent-memory create-fact "$DB" "agent-memory" "install" "npm install -g @cafitac/agent-memory" "user:default"
agent-memory approve-fact "$DB" 1
agent-memory retrieve "$DB" "How do I install agent-memory?" --preferred-scope user:default
```

Normal retrieval uses approved memories by default. Candidate or disputed memories stay out of normal prompt context unless you explicitly review or request them.

## Hermes integration

For Hermes users, `bootstrap` creates or updates the local Hermes hook config so Hermes can retrieve bounded memory context before model calls:

```bash
agent-memory bootstrap
hermes hooks doctor
```

Existing Hermes hooks are preserved when possible.

## Local-first privacy model

By default, `agent-memory` stores data in your local SQLite database. It is not a hosted service and does not upload your memory database for you.

Be careful when sharing:

- `~/.agent-memory/memory.db`
- backup bundles
- exported graph/report files
- dogfood or debug artifacts

## More docs

- [First-run memory layer setup](docs/first-run-memory-layer.md)
- [Install smoke recipes](docs/install-smoke.md)
- [Hermes dogfood guide](docs/hermes-dogfood.md)
- [Privacy policy](PRIVACY.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
