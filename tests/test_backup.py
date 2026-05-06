import json
import zipfile
from pathlib import Path

import pytest

from agent_memory.core.backup import export_backup, inspect_backup, restore_backup
from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_backup_export_inspect_restore_round_trips_memory_db(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    bundle_path = tmp_path / "memory-backup.agent-memory-backup.zip"
    restored_path = tmp_path / "restored.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="Backup round trip should preserve approved memories.",
        metadata={"project": "backup"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Backup",
        predicate="preserves",
        object_ref_or_value="approved memories",
        evidence_ids=[source.id],
        scope="project:backup",
    )
    approve_fact(db_path=db_path, fact_id=fact.id)

    exported = export_backup(db_path=db_path, output_path=bundle_path)
    inspected = inspect_backup(bundle_path)
    restored = restore_backup(bundle_path=bundle_path, output_db_path=restored_path)

    assert exported.kind == "agent_memory_backup_export"
    assert exported.output_path == str(bundle_path)
    assert exported.included_database is True
    assert exported.manifest.table_counts["facts"] == 1
    assert inspected.kind == "agent_memory_backup_inspection"
    assert inspected.manifest.table_counts["source_records"] == 1
    assert restored.kind == "agent_memory_backup_restore"
    assert restored.output_db_path == str(restored_path)
    packet = retrieve_memory_packet(restored_path, query="What does backup preserve?", preferred_scope="project:backup")
    assert [item.id for item in packet.semantic_facts] == [fact.id]


def test_backup_manifest_is_metadata_only_and_version_checked(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    bundle_path = tmp_path / "memory-backup.zip"
    initialize_database(db_path)
    ingest_source_text(
        db_path=db_path,
        source_type="note",
        content="SECRET_SHOULD_STAY_ONLY_IN_DATABASE_PAYLOAD",
    )

    export_backup(db_path=db_path, output_path=bundle_path)

    with zipfile.ZipFile(bundle_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert "SECRET_SHOULD_STAY_ONLY_IN_DATABASE_PAYLOAD" not in json.dumps(manifest)
        manifest["format_version"] = 999
        incompatible = tmp_path / "incompatible.zip"
        with zipfile.ZipFile(incompatible, "w") as edited:
            edited.writestr("manifest.json", json.dumps(manifest))
            edited.writestr("memory.db", archive.read("memory.db"))

    with pytest.raises(ValueError, match="unsupported backup format version"):
        restore_backup(bundle_path=incompatible, output_db_path=tmp_path / "out.db")
    assert not (tmp_path / "out.db").exists()


def test_backup_rejects_unsafe_database_entry_before_restore(tmp_path: Path) -> None:
    db_path = tmp_path / "memory.db"
    bundle_path = tmp_path / "memory-backup.zip"
    initialize_database(db_path)
    export_backup(db_path=db_path, output_path=bundle_path)

    unsafe_bundle = tmp_path / "unsafe-entry.zip"
    with zipfile.ZipFile(bundle_path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        manifest["database_entry"] = "../memory.db"
        with zipfile.ZipFile(unsafe_bundle, "w") as edited:
            edited.writestr("manifest.json", json.dumps(manifest))
            edited.writestr("../memory.db", archive.read("memory.db"))

    with pytest.raises(ValueError, match="unsupported backup database entry"):
        inspect_backup(unsafe_bundle)
    with pytest.raises(ValueError, match="unsupported backup database entry"):
        restore_backup(bundle_path=unsafe_bundle, output_db_path=tmp_path / "restored.db")
    assert not (tmp_path / "restored.db").exists()
