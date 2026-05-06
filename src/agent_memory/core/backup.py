from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from agent_memory import __version__
from agent_memory.storage.sqlite import connect, initialize_database

BACKUP_FORMAT_VERSION = 1
_DB_ENTRY_NAME = "memory.db"
_MANIFEST_ENTRY_NAME = "manifest.json"
_TABLES_TO_COUNT = [
    "source_records",
    "facts",
    "procedures",
    "episodes",
    "relations",
    "memory_status_transitions",
    "retrieval_observations",
    "experience_traces",
    "memory_activations",
]


class AgentMemoryBackupManifest(BaseModel):
    kind: Literal["agent_memory_backup_manifest"] = "agent_memory_backup_manifest"
    format_version: int = BACKUP_FORMAT_VERSION
    package_version: str = __version__
    created_at: str
    sqlite_user_version: int
    table_counts: dict[str, int] = Field(default_factory=dict)
    database_entry: str = _DB_ENTRY_NAME
    privacy_note: str = (
        "Manifest is metadata-only. The bundled SQLite database contains the user's local memory state and "
        "should be stored and shared according to the operator's local privacy policy."
    )


class AgentMemoryBackupExportResult(BaseModel):
    kind: Literal["agent_memory_backup_export"] = "agent_memory_backup_export"
    output_path: str
    manifest: AgentMemoryBackupManifest
    included_database: bool = True
    mutated_source_database: bool = False


class AgentMemoryBackupInspection(BaseModel):
    kind: Literal["agent_memory_backup_inspection"] = "agent_memory_backup_inspection"
    bundle_path: str
    manifest: AgentMemoryBackupManifest
    compatible: bool


class AgentMemoryBackupRestoreResult(BaseModel):
    kind: Literal["agent_memory_backup_restore"] = "agent_memory_backup_restore"
    bundle_path: str
    output_db_path: str
    manifest: AgentMemoryBackupManifest
    restored: bool = True


def _table_counts(db_path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with connect(db_path) as connection:
        for table in _TABLES_TO_COUNT:
            try:
                counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            except sqlite3.OperationalError:
                counts[table] = 0
    return counts


def _sqlite_user_version(db_path: Path) -> int:
    with connect(db_path) as connection:
        return int(connection.execute("PRAGMA user_version").fetchone()[0])


def _copy_sqlite_database(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    try:
        destination_connection = sqlite3.connect(destination)
        try:
            source_connection.backup(destination_connection)
        finally:
            destination_connection.close()
    finally:
        source_connection.close()


def _build_manifest(db_path: Path) -> AgentMemoryBackupManifest:
    return AgentMemoryBackupManifest(
        created_at=datetime.now(UTC).isoformat(),
        sqlite_user_version=_sqlite_user_version(db_path),
        table_counts=_table_counts(db_path),
    )


def _read_manifest(bundle_path: Path) -> AgentMemoryBackupManifest:
    with zipfile.ZipFile(bundle_path) as archive:
        if _MANIFEST_ENTRY_NAME not in archive.namelist():
            raise ValueError("backup bundle is missing manifest.json")
        manifest_payload = json.loads(archive.read(_MANIFEST_ENTRY_NAME))
    manifest = AgentMemoryBackupManifest.model_validate(manifest_payload)
    if manifest.format_version != BACKUP_FORMAT_VERSION:
        raise ValueError(f"unsupported backup format version: {manifest.format_version}")
    if manifest.database_entry != _DB_ENTRY_NAME:
        raise ValueError(f"unsupported backup database entry: {manifest.database_entry}")
    return manifest


def export_backup(*, db_path: Path | str, output_path: Path | str) -> AgentMemoryBackupExportResult:
    source = Path(db_path)
    output = Path(output_path)
    if not source.exists():
        raise FileNotFoundError(f"database not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    manifest = _build_manifest(source)
    with tempfile.TemporaryDirectory() as temp_dir:
        db_copy = Path(temp_dir) / _DB_ENTRY_NAME
        _copy_sqlite_database(source, db_copy)
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(_MANIFEST_ENTRY_NAME, manifest.model_dump_json(indent=2))
            archive.write(db_copy, _DB_ENTRY_NAME)
    return AgentMemoryBackupExportResult(output_path=str(output), manifest=manifest)


def inspect_backup(bundle_path: Path | str) -> AgentMemoryBackupInspection:
    bundle = Path(bundle_path)
    manifest = _read_manifest(bundle)
    with zipfile.ZipFile(bundle) as archive:
        if manifest.database_entry not in archive.namelist():
            raise ValueError(f"backup bundle is missing {manifest.database_entry}")
    return AgentMemoryBackupInspection(bundle_path=str(bundle), manifest=manifest, compatible=True)


def restore_backup(*, bundle_path: Path | str, output_db_path: Path | str, overwrite: bool = False) -> AgentMemoryBackupRestoreResult:
    bundle = Path(bundle_path)
    output = Path(output_db_path)
    if output.exists() and not overwrite:
        raise FileExistsError(f"output database already exists: {output}")
    manifest = _read_manifest(bundle)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temp_dir:
        extracted = Path(temp_dir) / _DB_ENTRY_NAME
        with zipfile.ZipFile(bundle) as archive:
            if manifest.database_entry not in archive.namelist():
                raise ValueError(f"backup bundle is missing {manifest.database_entry}")
            archive.extract(manifest.database_entry, temp_dir)
        if output.exists():
            output.unlink()
        _copy_sqlite_database(extracted, output)
    initialize_database(output)
    return AgentMemoryBackupRestoreResult(bundle_path=str(bundle), output_db_path=str(output), manifest=manifest)
