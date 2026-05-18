import importlib.util
import json
from pathlib import Path

from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.storage.sqlite import initialize_database


REPO_ROOT = Path(__file__).resolve().parents[1]


class RecordingHermesPluginContext:
    def __init__(self) -> None:
        self.hooks: dict[str, object] = {}
        self.skills: dict[str, Path] = {}

    def register_hook(self, name: str, handler: object) -> None:
        self.hooks[name] = handler

    def register_skill(self, name: str, skill_path: Path) -> None:
        self.skills[name] = Path(skill_path)


def _load_root_plugin_module():
    spec = importlib.util.spec_from_file_location("agent_memory_hermes_plugin", REPO_ROOT / "__init__.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_repo_root_is_installable_hermes_plugin_manifest() -> None:
    manifest_text = (REPO_ROOT / "plugin.yaml").read_text()

    assert "name: agent-memory" in manifest_text
    assert "manifest_version: 1" in manifest_text
    assert "pre_llm_call" in manifest_text
    assert "local-first" in manifest_text
    assert "requires_env" not in manifest_text


def test_hermes_plugin_registers_pre_llm_hook_and_skill() -> None:
    plugin = _load_root_plugin_module()
    ctx = RecordingHermesPluginContext()

    plugin.register(ctx)

    assert "pre_llm_call" in ctx.hooks
    assert callable(ctx.hooks["pre_llm_call"])
    assert ctx.skills["agent-memory"] == REPO_ROOT / "docs" / "first-run-memory-layer.md"


def test_hermes_plugin_pre_llm_hook_injects_existing_memory_context(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / "memory.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Hermes plugin default integration recalls marker HERMES_PLUGIN_OK.",
        metadata={"project": "hermes-plugin"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes plugin default integration",
        predicate="recalls",
        object_ref_or_value="HERMES_PLUGIN_OK",
        evidence_ids=[source.id],
        scope="project:hermes-plugin",
        confidence=0.97,
    )
    approve_fact(db_path=db_path, fact_id=fact.id)
    monkeypatch.setenv("AGENT_MEMORY_DB_PATH", str(db_path))
    monkeypatch.setenv("AGENT_MEMORY_HERMES_SCOPE", "project:hermes-plugin")

    plugin = _load_root_plugin_module()
    ctx = RecordingHermesPluginContext()
    plugin.register(ctx)
    handler = ctx.hooks["pre_llm_call"]

    result = handler(
        session_id="plugin-test-session",
        user_message="What marker does Hermes plugin default integration recall?",
        conversation_history=[],
        is_first_turn=True,
        model="test-model",
        platform="cli",
    )

    assert isinstance(result, dict)
    assert "<agent_memory_context>" in result["context"]
    assert "HERMES_PLUGIN_OK" in result["context"]
    assert json.dumps(result)


def test_hermes_plugin_pre_llm_hook_fails_soft_for_empty_or_bad_inputs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("AGENT_MEMORY_DB_PATH", str(tmp_path / "missing-parent" / "memory.db"))
    plugin = _load_root_plugin_module()
    ctx = RecordingHermesPluginContext()
    plugin.register(ctx)
    handler = ctx.hooks["pre_llm_call"]

    assert handler(session_id="s", user_message="", conversation_history=[], is_first_turn=False) is None
    assert handler(session_id="s", user_message=None, conversation_history=[], is_first_turn=False) is None
