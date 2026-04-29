from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from agent_memory.release_metadata import PROJECT_ROOT, load_release_metadata

SEMVER_RE = re.compile(r"^(?P<major>0|[1-9]\d*)\.(?P<minor>0|[1-9]\d*)\.(?P<patch>0|[1-9]\d*)$")


def bump_patch_version(version: str) -> str:
    match = SEMVER_RE.match(version)
    if match is None:
        raise ValueError(f"Expected a simple MAJOR.MINOR.PATCH version, got {version!r}")
    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))
    return f"{major}.{minor}.{patch + 1}"


def replace_once(text: str, old: str, new: str, path: Path) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected exactly one occurrence of {old!r} in {path}, found {count}")
    return text.replace(old, new, 1)


def update_pyproject_version(path: Path, version: str) -> None:
    text = path.read_text()
    updated = re.sub(
        r'(?m)^version = "[^"]+"$',
        f'version = "{version}"',
        text,
        count=1,
    )
    if updated == text:
        raise ValueError(f"Could not update project.version in {path}")
    path.write_text(updated)


def update_package_json_version(path: Path, version: str) -> None:
    payload = json.loads(path.read_text())
    payload["version"] = version
    path.write_text(json.dumps(payload, indent=2) + "\n")


def update_module_version(path: Path, version: str) -> None:
    text = path.read_text()
    updated = re.sub(
        r'(?m)^__version__ = "[^"]+"$',
        f'__version__ = "{version}"',
        text,
        count=1,
    )
    if updated == text:
        raise ValueError(f"Could not update __version__ in {path}")
    path.write_text(updated)


def update_uv_lock_version(path: Path, version: str) -> None:
    if not path.exists():
        return
    text = path.read_text()
    pattern = re.compile(
        r'(\[\[package\]\]\nname = "cafitac-agent-memory"\nversion = ")[^"]+("\n)',
        re.MULTILINE,
    )
    updated, count = pattern.subn(rf"\g<1>{version}\2", text, count=1)
    if count != 1:
        raise ValueError(f"Could not update cafitac-agent-memory package version in {path}")
    path.write_text(updated)


def update_release_version_files(project_root: Path, version: str) -> None:
    update_pyproject_version(project_root / "pyproject.toml", version)
    update_package_json_version(project_root / "package.json", version)
    update_module_version(project_root / "src" / "agent_memory" / "__init__.py", version)
    update_uv_lock_version(project_root / "uv.lock", version)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bump synchronized release metadata.")
    parser.add_argument(
        "--patch",
        action="store_true",
        help="Increment the current synchronized version's patch component.",
    )
    parser.add_argument(
        "--set-version",
        help="Set an explicit MAJOR.MINOR.PATCH version instead of incrementing patch.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=PROJECT_ROOT,
        help="Repository root containing pyproject.toml and package.json.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.patch == bool(args.set_version):
        raise SystemExit("Pass exactly one of --patch or --set-version")

    metadata = load_release_metadata(args.project_root)
    next_version = args.set_version or bump_patch_version(metadata.python_package_version)
    if SEMVER_RE.match(next_version) is None:
        raise SystemExit(f"Invalid release version: {next_version!r}")

    update_release_version_files(args.project_root, next_version)
    print(next_version)


if __name__ == "__main__":
    main()
