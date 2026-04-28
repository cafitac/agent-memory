# Release checklist v0

This checklist is for the first dual-distribution releases of agent-memory.

## Goal

Ship both of these safely:
- PyPI package `cafitac-agent-memory`: canonical Python runtime and library distribution
- npm package `@cafitac/agent-memory`: thin launcher surface for agent-tooling users

## Preconditions

1. Version sync
- `pyproject.toml` `project.version`
- `package.json` `version`
- `src/agent_memory/__init__.py` `__version__`
- Verify with:
  - `uv run python scripts/check_release_metadata.py`
- Expected package names:
  - PyPI: `cafitac-agent-memory`
  - npm: `@cafitac/agent-memory`

2. Test suite
- Run:
  - `uv run pytest tests/ -q`

3. Release-readiness smoke
- Run:
  - `uv run python scripts/smoke_release_readiness.py`
- Expected:
  - Python CLI `hermes-bootstrap` succeeds
  - Python CLI `hermes-doctor` returns `status=ok`
  - npm launcher `bootstrap` succeeds
  - npm launcher `doctor` returns `status=ok`

4. Packaging checks
- Python:
  - `uvx --from build python -m build`
- npm:
  - `npm pack --dry-run`

5. Credentials / registry setup
- PyPI trusted publishing configured for this GitHub repository, or `PYPI_API_TOKEN` present in GitHub Actions secrets as the fallback path
- `NPM_TOKEN` present in GitHub Actions secrets
- npm package name availability confirmed
- npm provenance publish supported by the repository/workflow permissions (`id-token: write`)

## Publish flow

### Tag-driven release
1. Bump synced version in all three places
2. Commit
3. Push tag `vX.Y.Z`
4. `publish.yml` runs:
   - metadata validation
   - pytest
   - smoke script
   - Python build
   - npm dry-run
   - PyPI publish
   - npm publish
   - GitHub Release creation with generated notes and Python dist artifacts

### Manual release
Use `workflow_dispatch` on `publish.yml` when you need to publish only one surface or re-run publish after infra fixes.

## First-release runbook

1. Confirm registry names are the intended ones:
   - PyPI: `cafitac-agent-memory`
   - npm: `@cafitac/agent-memory`
2. Confirm GitHub repository settings are ready:
   - PyPI trusted publishing is configured, or `PYPI_API_TOKEN` exists in Actions secrets
   - `NPM_TOKEN` exists in Actions secrets
3. Run local verification in this order:
   - `uv run python scripts/check_release_metadata.py`
   - `uv run pytest tests/ -q`
   - `uv run python scripts/smoke_release_readiness.py`
   - `uvx --from build python -m build`
   - `npm pack --dry-run`
4. Publish by either:
   - pushing `vX.Y.Z`, or
   - using `workflow_dispatch` on `.github/workflows/publish.yml`
5. After publish, verify from a clean machine or shell session:
   - `npm install -g @cafitac/agent-memory`
   - `agent-memory bootstrap`
   - `agent-memory doctor`
6. Only after that smoke passes, promote the README top quickstart to the npm-first form.

## Criteria for switching README to npm-first

Promote the README quickstart from “target npm UX after publish” to real npm-first instructions only after all of these are true:

1. npm package has been published successfully at least once
2. `npm install -g @cafitac/agent-memory && agent-memory bootstrap` works on a clean machine/session
3. `agent-memory doctor` works on a clean machine/session
4. npm package resolution is stable enough that the fallback story is clear
5. at least one PyPI direct-install path remains documented for CI/power users

## Recommended README state after first successful publish

Top quickstart:
- `npm install -g @cafitac/agent-memory`
- `agent-memory bootstrap`
- `agent-memory doctor`

Alternative installs section:
- `pipx install cafitac-agent-memory`
- `uv tool install cafitac-agent-memory`

## Notes

- The npm package is intentionally a launcher, not the canonical runtime implementation.
- The Python package remains the source of truth for runtime behavior and library embedding.
- Keep the launcher thin; avoid duplicating memory logic in Node.
