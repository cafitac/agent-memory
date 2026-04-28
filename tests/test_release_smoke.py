import json
import os
import subprocess
import sys
import tarfile
import zipfile
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


def test_built_distributions_include_schema_sql(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()

    subprocess.run(
        ["uvx", "--from", "build", "python", "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)],
        cwd=PROJECT_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    wheels = list(dist_dir.glob("*.whl"))
    sdists = list(dist_dir.glob("*.tar.gz"))
    assert wheels, "wheel build missing"
    assert sdists, "sdist build missing"

    with zipfile.ZipFile(wheels[0]) as wheel:
        assert "agent_memory/storage/schema.sql" in wheel.namelist()

    with tarfile.open(sdists[0], "r:gz") as sdist:
        assert any(name.endswith("/src/agent_memory/storage/schema.sql") for name in sdist.getnames())
