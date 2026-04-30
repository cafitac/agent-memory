# Contributing

Thanks for helping improve agent-memory.

## Development setup

```bash
git clone https://github.com/cafitac/agent-memory.git
cd agent-memory
uv run agent-memory --help
uv run pytest tests/ -q
```

The project uses:

- Python 3.11+
- `uv` for local development commands
- npm only for the thin launcher package and package smoke checks
- SQLite for local storage
- pytest for tests

## Before opening a PR

Run:

```bash
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
npm pack --dry-run
```

If your change affects install, release, or launcher behavior, also run a clean install smoke from outside the source checkout. See `docs/install-smoke.md`.

## Change expectations

- Keep user-facing behavior documented in `README.md`.
- Keep security/privacy-impacting changes reflected in `SECURITY.md` or `PRIVACY.md`.
- Add or update tests for behavior changes.
- Keep retrieval evaluator changes covered in `tests/test_retrieval_evaluation.py`.
- Prefer small PRs with one clear purpose.
- Do not commit local memory databases, virtualenvs, agent state directories, or secrets.

## Retrieval evaluation changes

When changing retrieval behavior or retrieval-eval report fields:

```bash
uv run pytest tests/test_retrieval_evaluation.py -q
uv run pytest tests/test_retrieval_trace.py -q
uv run pytest tests/ -q
```

The evaluator should continue to exercise the real retrieval path, preserve JSON as the machine-readable contract, and keep text reports human-actionable.

## Reporting issues

For ordinary bugs, use the bug report issue template.

For vulnerabilities or private data exposure, follow `SECURITY.md` instead of posting exploit details publicly.
