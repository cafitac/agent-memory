from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SmokeStepResult:
    name: str
    returncode: int
    stdout: str
    stderr: str


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> SmokeStepResult:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )
    return SmokeStepResult(
        name=" ".join(command),
        returncode=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )


def _parse_json_output(step: SmokeStepResult) -> Any:
    if step.returncode != 0:
        raise RuntimeError(f"step failed: {step.name}\n{step.stderr}")
    return json.loads(step.stdout)


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]

    with tempfile.TemporaryDirectory(prefix="agent-memory-smoke-") as temp_dir:
        home = Path(temp_dir) / "home"
        home.mkdir(parents=True, exist_ok=True)
        common_env = {
            **os.environ,
            "HOME": str(home),
            "PYTHONPATH": "src",
            "AGENT_MEMORY_PYTHON_EXECUTABLE": sys.executable,
        }

        python_bootstrap = _run(
            [sys.executable, "-m", "agent_memory.api.cli", "hermes-bootstrap"],
            cwd=repo_root,
            env=common_env,
        )
        python_doctor = _run(
            [sys.executable, "-m", "agent_memory.api.cli", "hermes-doctor"],
            cwd=repo_root,
            env=common_env,
        )
        node_bootstrap = _run(
            ["node", "bin/agent-memory.js", "bootstrap"],
            cwd=repo_root,
            env=common_env,
        )
        node_doctor = _run(
            ["node", "bin/agent-memory.js", "doctor"],
            cwd=repo_root,
            env=common_env,
        )

        python_bootstrap_payload = _parse_json_output(python_bootstrap)
        python_doctor_payload = _parse_json_output(python_doctor)
        node_bootstrap_payload = _parse_json_output(node_bootstrap)
        node_doctor_payload = _parse_json_output(node_doctor)

        summary = {
            "python_bootstrap": {
                "db_initialized": python_bootstrap_payload.get("db_initialized"),
                "config_path": python_bootstrap_payload.get("config_path"),
            },
            "python_doctor": {
                "status": python_doctor_payload.get("status"),
                "hook_installed": python_doctor_payload.get("hook_installed"),
            },
            "node_bootstrap": {
                "db_initialized": node_bootstrap_payload.get("db_initialized"),
                "config_path": node_bootstrap_payload.get("config_path"),
            },
            "node_doctor": {
                "status": node_doctor_payload.get("status"),
                "hook_installed": node_doctor_payload.get("hook_installed"),
            },
            "steps": [
                asdict(python_bootstrap),
                asdict(python_doctor),
                asdict(node_bootstrap),
                asdict(node_doctor),
            ],
        }

        if python_doctor_payload.get("status") != "ok":
            raise RuntimeError(f"python smoke failed: {python_doctor.stdout}")
        if node_doctor_payload.get("status") != "ok":
            raise RuntimeError(f"node smoke failed: {node_doctor.stdout}")

        print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
