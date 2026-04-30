from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence


NPM_PACKAGE = "@cafitac/agent-memory"
PYTHON_PACKAGE = "cafitac-agent-memory"


@dataclass(frozen=True)
class PublishedSmokeStep:
    name: str
    command: list[str]
    cwd: str
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class SmokeCommand:
    name: str
    command: list[str]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_package_version(repo_root: Path) -> str:
    package_json = json.loads((repo_root / "package.json").read_text())
    version = package_json.get("version")
    if not isinstance(version, str) or not version:
        raise RuntimeError("package.json does not contain a non-empty version")
    return version


def _run(command: Sequence[str], *, cwd: Path, env: dict[str, str], timeout: int) -> PublishedSmokeStep:
    result = subprocess.run(
        list(command),
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return PublishedSmokeStep(
        name=" ".join(command),
        command=list(command),
        cwd=str(cwd),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _parse_json(step: PublishedSmokeStep) -> dict[str, object]:
    if step.returncode != 0:
        raise RuntimeError(f"step failed before JSON parse: {step.name}\n{step.stderr}")
    try:
        payload = json.loads(step.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"step did not emit JSON: {step.name}\nstdout={step.stdout!r}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"step emitted non-object JSON: {step.name}")
    return payload


def _assert_help(step: PublishedSmokeStep) -> None:
    if step.returncode != 0:
        raise RuntimeError(f"help command failed: {step.name}\n{step.stderr}")
    if "usage: agent-memory" not in step.stdout:
        raise RuntimeError(f"help output did not look like agent-memory CLI help: {step.name}")


def _assert_doctor_ok(step: PublishedSmokeStep) -> None:
    payload = _parse_json(step)
    if payload.get("status") != "ok":
        raise RuntimeError(f"doctor status was not ok for {step.name}: {step.stdout}")
    for key in ("db_exists", "config_exists", "hook_installed"):
        if payload.get(key) is not True:
            raise RuntimeError(f"doctor field {key} was not true for {step.name}: {step.stdout}")


def _assert_registry_version(step: PublishedSmokeStep, version: str) -> None:
    if step.returncode != 0:
        raise RuntimeError(f"registry version lookup failed: {step.name}\n{step.stderr}")
    if step.stdout.strip() != version:
        raise RuntimeError(f"registry returned {step.stdout.strip()!r}, expected {version!r}")


def build_command_matrix(version: str, *, include_pipx: bool = True, python_executable: str | None = None) -> list[SmokeCommand]:
    npm_spec = f"{NPM_PACKAGE}@{version}"
    python_spec = f"{PYTHON_PACKAGE}=={version}"
    pipx_python = python_executable or sys.executable
    commands = [
        SmokeCommand("npm-registry-version", ["npm", "view", npm_spec, "version"]),
        SmokeCommand("npx-help", ["npx", "--yes", npm_spec, "--help"]),
        SmokeCommand("npm-exec-help", ["npm", "exec", "--yes", "--package", npm_spec, "agent-memory", "--", "--help"]),
        SmokeCommand("npm-exec-bootstrap", ["npm", "exec", "--yes", "--package", npm_spec, "agent-memory", "--", "bootstrap"]),
        SmokeCommand("npm-exec-doctor", ["npm", "exec", "--yes", "--package", npm_spec, "agent-memory", "--", "doctor"]),
        SmokeCommand("uvx-help", ["uvx", "--from", python_spec, "agent-memory", "--help"]),
        SmokeCommand("uvx-bootstrap", ["uvx", "--from", python_spec, "agent-memory", "bootstrap"]),
        SmokeCommand("uvx-doctor", ["uvx", "--from", python_spec, "agent-memory", "doctor"]),
    ]
    if include_pipx:
        commands.extend(
            [
                SmokeCommand("pipx-help", ["pipx", "run", "--python", pipx_python, "--spec", python_spec, "agent-memory", "--help"]),
                SmokeCommand("pipx-bootstrap", ["pipx", "run", "--python", pipx_python, "--spec", python_spec, "agent-memory", "bootstrap"]),
                SmokeCommand("pipx-doctor", ["pipx", "run", "--python", pipx_python, "--spec", python_spec, "agent-memory", "doctor"]),
            ]
        )
    return commands


def _stateful_surface_name(command: SmokeCommand) -> str:
    if command.name.startswith("npm-exec-"):
        return "npm-exec"
    if command.name.startswith("uvx-"):
        return "uvx"
    if command.name.startswith("pipx-"):
        return "pipx"
    return command.name


def _command_with_paths(command: SmokeCommand, *, db_path: Path, config_path: Path) -> list[str]:
    if command.name.endswith("bootstrap") or command.name.endswith("doctor"):
        return [*command.command, str(db_path), "--config-path", str(config_path)]
    return command.command


def _tool_is_available(command: SmokeCommand) -> bool:
    return shutil.which(command.command[0]) is not None


def _run_once(version: str, *, timeout: int, include_pipx: bool) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="agent-memory-published-smoke-") as temp_dir:
        root = Path(temp_dir)
        home = root / "home"
        home.mkdir(parents=True, exist_ok=True)
        env = {
            **os.environ,
            "HOME": str(home),
            "XDG_CACHE_HOME": str(root / "cache"),
        }
        env.pop("AGENT_MEMORY_PYTHON_EXECUTABLE", None)
        env.pop("PYTHONPATH", None)

        steps: list[PublishedSmokeStep] = []
        command_results: dict[str, dict[str, object]] = {}
        for command in build_command_matrix(version, include_pipx=include_pipx):
            if not _tool_is_available(command):
                raise RuntimeError(f"required smoke tool is not available on PATH: {command.command[0]}")
            surface_name = _stateful_surface_name(command)
            surface_root = root / surface_name
            surface_root.mkdir(parents=True, exist_ok=True)
            db_path = surface_root / "memory.db"
            config_path = surface_root / "hermes.yaml"
            step = _run(
                _command_with_paths(command, db_path=db_path, config_path=config_path),
                cwd=root,
                env=env,
                timeout=timeout,
            )
            steps.append(step)

            if command.name == "npm-registry-version":
                _assert_registry_version(step, version)
            elif command.name.endswith("help"):
                _assert_help(step)
            elif command.name.endswith("bootstrap"):
                payload = _parse_json(step)
                if payload.get("db_initialized") is not True:
                    raise RuntimeError(f"bootstrap did not initialize db for {command.name}: {step.stdout}")
            elif command.name.endswith("doctor"):
                _assert_doctor_ok(step)

            command_results[command.name] = {
                "returncode": step.returncode,
                "stdout_excerpt": step.stdout[:500],
                "stderr_excerpt": step.stderr[:500],
            }

        return {
            "version": version,
            "temp_dir": temp_dir,
            "commands": command_results,
            "steps": [asdict(step) for step in steps],
        }


def run_with_retries(version: str, *, attempts: int, delay_seconds: int, timeout: int, include_pipx: bool) -> dict[str, object]:
    failures: list[str] = []
    for attempt in range(1, attempts + 1):
        try:
            summary = _run_once(version, timeout=timeout, include_pipx=include_pipx)
            summary["attempt"] = attempt
            summary["attempts"] = attempts
            return summary
        except Exception as exc:  # noqa: BLE001 - CLI should preserve the full smoke failure.
            failures.append(f"attempt {attempt}: {exc}")
            if attempt == attempts:
                break
            time.sleep(delay_seconds)
    raise RuntimeError("published install smoke failed\n" + "\n".join(failures))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Smoke-test exact published agent-memory packages outside the source checkout.")
    parser.add_argument("--version", default=None, help="Package version to verify. Defaults to package.json version.")
    parser.add_argument("--attempts", type=int, default=3, help="Retry attempts for registry propagation.")
    parser.add_argument("--delay-seconds", type=int, default=10, help="Delay between retry attempts.")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout per command in seconds.")
    parser.add_argument("--skip-pipx", action="store_true", help="Skip pipx smoke commands when the runner cannot provide pipx.")
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    version = args.version or _read_package_version(repo_root)
    summary = run_with_retries(
        version,
        attempts=args.attempts,
        delay_seconds=args.delay_seconds,
        timeout=args.timeout,
        include_pipx=not args.skip_pipx,
    )
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
