import importlib.util
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "bump_release_version.py"


def load_bump_release_version_module() -> ModuleType:
    assert SCRIPT_PATH.exists(), "scripts/bump_release_version.py must exist"
    spec = importlib.util.spec_from_file_location("bump_release_version", SCRIPT_PATH)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_bump_patch_version_increments_patch_component() -> None:
    module = load_bump_release_version_module()

    assert module.bump_patch_version("0.1.9") == "0.1.10"


def test_update_release_version_files_syncs_all_release_metadata(tmp_path: Path) -> None:
    module = load_bump_release_version_module()
    project_root = tmp_path
    (project_root / "src" / "agent_memory").mkdir(parents=True)
    (project_root / "tests").mkdir()
    (project_root / "pyproject.toml").write_text(
        '[project]\nname = "cafitac-agent-memory"\nversion = "0.1.9"\n',
    )
    (project_root / "package.json").write_text(
        '{\n  "name": "@cafitac/agent-memory",\n  "version": "0.1.9"\n}\n',
    )
    (project_root / "src" / "agent_memory" / "__init__.py").write_text(
        '__version__ = "0.1.9"\n',
    )
    (project_root / "uv.lock").write_text(
        '[[package]]\nname = "cafitac-agent-memory"\nversion = "0.1.9"\n',
    )

    module.update_release_version_files(project_root, "0.1.10")

    assert 'version = "0.1.10"' in (project_root / "pyproject.toml").read_text()
    assert '"version": "0.1.10"' in (project_root / "package.json").read_text()
    assert '__version__ = "0.1.10"' in (
        project_root / "src" / "agent_memory" / "__init__.py"
    ).read_text()
    assert 'version = "0.1.10"' in (project_root / "uv.lock").read_text()
