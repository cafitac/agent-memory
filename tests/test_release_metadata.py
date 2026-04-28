from pathlib import Path

from agent_memory.release_metadata import load_release_metadata, validate_release_metadata


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_release_metadata_versions_and_names_are_synced() -> None:
    metadata = validate_release_metadata(PROJECT_ROOT)

    assert metadata.python_package_name == "cafitac-agent-memory"
    assert metadata.npm_package_name == "@cafitac/agent-memory"
    assert metadata.python_package_version == "0.1.2"
    assert metadata.npm_package_version == metadata.python_package_version
    assert metadata.module_version == metadata.python_package_version
    assert metadata.npm_repository_url == "https://github.com/cafitac/agent-memory"



def test_release_metadata_loader_reads_expected_fields() -> None:
    metadata = load_release_metadata(PROJECT_ROOT)

    assert metadata.python_package_name
    assert metadata.npm_package_name
    assert metadata.python_package_version
    assert metadata.npm_package_version
    assert metadata.module_version
    assert metadata.npm_repository_url
