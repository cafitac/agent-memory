import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "smoke_published_install.py"
SPEC = importlib.util.spec_from_file_location("smoke_published_install", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
smoke_published_install = importlib.util.module_from_spec(SPEC)
sys.modules["smoke_published_install"] = smoke_published_install
SPEC.loader.exec_module(smoke_published_install)
PublishedSmokeStep = smoke_published_install.PublishedSmokeStep
SmokeCommand = smoke_published_install.SmokeCommand


def test_published_install_command_matrix_pins_exact_package_versions() -> None:
    commands = smoke_published_install.build_command_matrix("1.2.3", python_executable="/usr/bin/python3.11")
    by_name = {command.name: command.command for command in commands}

    assert by_name["npm-registry-version"] == ["npm", "view", "@cafitac/agent-memory@1.2.3", "version"]
    assert by_name["npx-help"] == ["npx", "--yes", "@cafitac/agent-memory@1.2.3", "--help"]
    assert by_name["npm-exec-bootstrap"][:6] == [
        "npm",
        "exec",
        "--yes",
        "--package",
        "@cafitac/agent-memory@1.2.3",
        "agent-memory",
    ]
    assert by_name["npm-exec-hook"][:6] == [
        "npm",
        "exec",
        "--yes",
        "--package",
        "@cafitac/agent-memory@1.2.3",
        "agent-memory",
    ]
    assert by_name["uvx-bootstrap"][:3] == ["uvx", "--from", "cafitac-agent-memory==1.2.3"]
    assert by_name["uvx-hook"][:3] == ["uvx", "--from", "cafitac-agent-memory==1.2.3"]
    assert by_name["pipx-bootstrap"][:6] == ["pipx", "run", "--python", "/usr/bin/python3.11", "--spec", "cafitac-agent-memory==1.2.3"]
    assert by_name["pipx-hook"][:6] == ["pipx", "run", "--python", "/usr/bin/python3.11", "--spec", "cafitac-agent-memory==1.2.3"]


def test_published_install_command_matrix_can_skip_pipx() -> None:
    commands = smoke_published_install.build_command_matrix("1.2.3", include_pipx=False)

    assert {command.name for command in commands} == {
        "npm-registry-version",
        "npx-help",
        "npm-exec-help",
        "npm-exec-bootstrap",
        "npm-exec-doctor",
        "npm-exec-hook",
        "uvx-help",
        "uvx-bootstrap",
        "uvx-doctor",
        "uvx-hook",
    }


def test_published_install_script_uses_package_json_version_by_default() -> None:
    version = smoke_published_install._read_package_version(REPO_ROOT)
    package_json = json.loads((REPO_ROOT / "package.json").read_text())

    assert version == package_json["version"]


def test_published_install_workflows_install_pipx_into_uv_venv() -> None:
    workflow_paths = [
        REPO_ROOT / ".github" / "workflows" / "published-install-smoke.yml",
        REPO_ROOT / ".github" / "workflows" / "publish.yml",
    ]

    for workflow_path in workflow_paths:
        content = workflow_path.read_text()
        assert "uv venv" in content
        assert "uv pip install pipx" in content
        assert 'echo "$PWD/.venv/bin" >> "$GITHUB_PATH"' in content
        assert "pip install --user pipx" not in content
        assert "pipx.main" not in content


def test_published_install_script_appends_isolated_bootstrap_paths(tmp_path: Path) -> None:
    command = SmokeCommand("uvx-bootstrap", ["uvx", "--from", "cafitac-agent-memory==1.2.3", "agent-memory", "bootstrap"])

    argv = smoke_published_install._command_with_paths(
        command,
        db_path=tmp_path / "memory.db",
        config_path=tmp_path / "hermes.yaml",
    )

    assert argv[-3:] == [str(tmp_path / "memory.db"), "--config-path", str(tmp_path / "hermes.yaml")]


def test_stateful_smoke_commands_share_surface_directories() -> None:
    assert smoke_published_install._stateful_surface_name(SmokeCommand("npm-exec-bootstrap", [])) == "npm-exec"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("npm-exec-doctor", [])) == "npm-exec"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("npm-exec-hook", [])) == "npm-exec"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("uvx-bootstrap", [])) == "uvx"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("uvx-doctor", [])) == "uvx"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("uvx-hook", [])) == "uvx"
    assert smoke_published_install._stateful_surface_name(SmokeCommand("npm-registry-version", [])) == "npm-registry-version"


def test_published_install_script_appends_isolated_hook_paths(tmp_path: Path) -> None:
    command = SmokeCommand("npm-exec-hook", ["npm", "exec", "--yes", "--package", "@cafitac/agent-memory@1.2.3", "agent-memory", "--", "hermes-pre-llm-hook"])

    argv = smoke_published_install._command_with_paths(
        command,
        db_path=tmp_path / "memory.db",
        config_path=tmp_path / "hermes.yaml",
    )

    assert argv[-1:] == [str(tmp_path / "memory.db")]


def test_published_install_script_rejects_bad_doctor_payload() -> None:
    step = PublishedSmokeStep(
        name="doctor",
        command=["agent-memory", "doctor"],
        cwd="/tmp",
        returncode=0,
        stdout=json.dumps({"status": "needs_setup"}),
        stderr="",
    )

    with pytest.raises(RuntimeError, match="doctor status was not ok"):
        smoke_published_install._assert_doctor_ok(step)


def test_published_install_workflow_runs_script_after_publish() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "publish.yml").read_text()

    assert "published-install-smoke" in workflow
    assert "scripts/smoke_published_install.py" in workflow
    assert "--output-json .artifacts/published-install-smoke.json" in workflow
    assert "--propagation-attempts" in workflow
    assert "--propagation-delay-seconds" in workflow
    assert "actions/upload-artifact" in workflow
    assert "published-install-smoke-result" in workflow
    assert "needs:" in workflow
    assert "publish-pypi" in workflow
    assert "publish-npm" in workflow
    assert "--attempts 12" in workflow
    assert "--propagation-attempts 36" in workflow
    assert "--propagation-delay-seconds 20" in workflow


def test_standalone_published_install_workflow_is_manual() -> None:
    workflow_path = REPO_ROOT / ".github" / "workflows" / "published-install-smoke.yml"
    workflow = workflow_path.read_text()

    assert "workflow_dispatch:" in workflow
    assert "version:" in workflow
    assert "scripts/smoke_published_install.py" in workflow
    assert "default: '18'" in workflow
    assert "uv pip install pipx" in workflow
    assert "--output-json .artifacts/published-install-smoke.json" in workflow
    assert "--propagation-attempts" in workflow
    assert "--propagation-delay-seconds" in workflow
    assert "actions/upload-artifact" in workflow


def test_published_install_script_does_not_mask_missing_required_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _command: None)

    with pytest.raises(RuntimeError, match="required smoke tool is not available"):
        smoke_published_install._run_once("1.2.3", timeout=1, include_pipx=False)


def test_run_with_retries_reports_all_failed_attempts(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_once(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("registry not ready")

    monkeypatch.setattr(smoke_published_install, "_run_once", fail_once)
    monkeypatch.setattr(smoke_published_install.time, "sleep", lambda _seconds: None)

    with pytest.raises(RuntimeError) as error:
        smoke_published_install.run_with_retries(
            "1.2.3",
            attempts=2,
            delay_seconds=0,
            timeout=1,
            include_pipx=False,
        )

    assert "attempt 1: registry not ready" in str(error.value)
    assert "attempt 2: registry not ready" in str(error.value)


def test_run_with_retries_waits_longer_for_propagation_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0
    sleeps: list[int] = []

    def flaky_propagation(*_args: object, **_kwargs: object) -> dict[str, object]:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise RuntimeError("No solution found when resolving dependencies: cafitac-agent-memory==1.2.3")
        return {"version": "1.2.3"}

    monkeypatch.setattr(smoke_published_install, "_run_once", flaky_propagation)
    monkeypatch.setattr(smoke_published_install.time, "sleep", lambda seconds: sleeps.append(seconds))

    summary = smoke_published_install.run_with_retries(
        "1.2.3",
        attempts=2,
        delay_seconds=10,
        timeout=1,
        include_pipx=False,
        propagation_attempts=4,
        propagation_delay_seconds=30,
    )

    assert summary["attempt"] == 3
    assert summary["attempts"] == 4
    assert summary["propagation_retry_used"] is True
    assert sleeps == [30, 60]


def test_published_install_failure_artifact_includes_registry_probe_diagnostics(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail_once(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("No matching distribution found for cafitac-agent-memory==1.2.3")

    def fake_probe(version: str, *, timeout: int) -> dict[str, object]:
        return {
            "version": version,
            "timeout": timeout,
            "npm_version": "1.2.3",
            "pypi_json_version_present": True,
            "pypi_simple_mentions_version": False,
        }

    output_path = tmp_path / "published-install-smoke.json"
    monkeypatch.setattr(smoke_published_install, "_run_once", fail_once)
    monkeypatch.setattr(smoke_published_install, "probe_registry_propagation", fake_probe)
    monkeypatch.setattr(smoke_published_install.time, "sleep", lambda _seconds: None)

    exit_code = smoke_published_install.main(
        [
            "--version",
            "1.2.3",
            "--attempts",
            "1",
            "--propagation-attempts",
            "1",
            "--delay-seconds",
            "0",
            "--output-json",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text())
    assert exit_code == 1
    assert "published install smoke failed" in captured.err
    assert payload["registry_probe"]["npm_version"] == "1.2.3"
    assert payload["registry_probe"]["pypi_json_version_present"] is True
    assert payload["registry_probe"]["pypi_simple_mentions_version"] is False



def test_published_install_cli_writes_failure_artifact(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    def fail_once(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise RuntimeError("deterministic import failure")

    output_path = tmp_path / "published-install-smoke.json"
    monkeypatch.setattr(smoke_published_install, "_run_once", fail_once)
    monkeypatch.setattr(smoke_published_install.time, "sleep", lambda _seconds: None)

    exit_code = smoke_published_install.main(
        [
            "--version",
            "1.2.3",
            "--attempts",
            "2",
            "--delay-seconds",
            "0",
            "--output-json",
            str(output_path),
        ]
    )

    captured = capsys.readouterr()
    payload = json.loads(output_path.read_text())
    assert exit_code == 1
    assert "published install smoke failed" in captured.err
    assert payload["status"] == "failed"
    assert payload["version"] == "1.2.3"
    assert payload["failures"] == [
        "attempt 1: deterministic import failure",
        "attempt 2: deterministic import failure",
    ]
