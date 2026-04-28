import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_smoke_script_reports_python_and_node_paths(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": "src",
    }

    result = subprocess.run(
        [sys.executable, "scripts/smoke_release_readiness.py"],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["python_doctor"]["status"] == "ok"
    assert payload["python_doctor"]["hook_installed"] is True
    assert payload["node_doctor"]["status"] == "ok"
    assert payload["node_doctor"]["hook_installed"] is True
    assert len(payload["steps"]) == 4
