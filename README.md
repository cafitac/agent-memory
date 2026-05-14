# agent-memory

[![CI](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/@cafitac/agent-memory.svg)](https://www.npmjs.com/package/@cafitac/agent-memory)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local-first memory for AI agents.

## Install

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

Use without a global install:

```bash
npm exec --yes --package @cafitac/agent-memory -- agent-memory doctor
```

By default, the local SQLite database lives at `~/.agent-memory/memory.db`.

## More docs

- [First-run setup](docs/first-run-memory-layer.md)
- [Install smoke recipes](docs/install-smoke.md)
- [Privacy policy](PRIVACY.md)
- [Security policy](SECURITY.md)
- [Contributing](CONTRIBUTING.md)

## License

[MIT](LICENSE)
