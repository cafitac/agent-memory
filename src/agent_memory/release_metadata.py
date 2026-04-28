from __future__ import annotations

import json
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ReleaseMetadata:
    python_package_name: str
    python_package_version: str
    npm_package_name: str
    npm_package_version: str
    module_version: str
    npm_repository_url: str


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
PACKAGE_JSON_PATH = PROJECT_ROOT / "package.json"
MODULE_INIT_PATH = PROJECT_ROOT / "src" / "agent_memory" / "__init__.py"
EXPECTED_PYTHON_PACKAGE_NAME = "cafitac-agent-memory"
EXPECTED_NPM_PACKAGE_NAME = "@cafitac/agent-memory"
EXPECTED_REPOSITORY_URL = "https://github.com/cafitac/agent-memory"


def _read_pyproject(path: Path = PYPROJECT_PATH) -> tuple[str, str]:
    payload = tomllib.loads(path.read_text())
    project = payload["project"]
    return str(project["name"]), str(project["version"])


def _read_package_json(path: Path = PACKAGE_JSON_PATH) -> tuple[str, str, str]:
    payload = json.loads(path.read_text())
    repository = payload.get("repository")
    if not isinstance(repository, dict):
        raise ValueError(f"repository must be an object in {path}")
    repository_url = repository.get("url", "")
    return str(payload["name"]), str(payload["version"]), str(repository_url)


def _read_module_version(path: Path = MODULE_INIT_PATH) -> str:
    for line in path.read_text().splitlines():
        if line.startswith("__version__ = "):
            return line.split("=", 1)[1].strip().strip('"')
    raise ValueError(f"__version__ not found in {path}")


def load_release_metadata(project_root: Path = PROJECT_ROOT) -> ReleaseMetadata:
    pyproject_path = project_root / "pyproject.toml"
    package_json_path = project_root / "package.json"
    module_init_path = project_root / "src" / "agent_memory" / "__init__.py"

    python_name, python_version = _read_pyproject(pyproject_path)
    npm_name, npm_version, npm_repository_url = _read_package_json(package_json_path)
    module_version = _read_module_version(module_init_path)
    return ReleaseMetadata(
        python_package_name=python_name,
        python_package_version=python_version,
        npm_package_name=npm_name,
        npm_package_version=npm_version,
        module_version=module_version,
        npm_repository_url=npm_repository_url,
    )


def validate_release_metadata(project_root: Path = PROJECT_ROOT) -> ReleaseMetadata:
    metadata = load_release_metadata(project_root)

    if metadata.python_package_name != EXPECTED_PYTHON_PACKAGE_NAME:
        raise ValueError(
            "Unexpected Python package name: "
            f"{metadata.python_package_name!r} != {EXPECTED_PYTHON_PACKAGE_NAME!r}"
        )

    if metadata.npm_package_name != EXPECTED_NPM_PACKAGE_NAME:
        raise ValueError(
            "Unexpected npm package name: "
            f"{metadata.npm_package_name!r} != {EXPECTED_NPM_PACKAGE_NAME!r}"
        )

    if metadata.npm_repository_url != EXPECTED_REPOSITORY_URL:
        raise ValueError(
            "Unexpected npm repository URL: "
            f"{metadata.npm_repository_url!r} != {EXPECTED_REPOSITORY_URL!r}"
        )

    versions = {
        metadata.python_package_version,
        metadata.npm_package_version,
        metadata.module_version,
    }
    if len(versions) != 1:
        raise ValueError(
            "Release versions are out of sync across pyproject.toml, package.json, and src/agent_memory/__init__.py: "
            f"{metadata.python_package_version!r}, {metadata.npm_package_version!r}, {metadata.module_version!r}"
        )

    return metadata
