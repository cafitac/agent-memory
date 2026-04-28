from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from agent_memory.core.models import SourceRecord
from agent_memory.storage.sqlite import insert_source_record


def ingest_source_text(
    db_path: Path | str,
    *,
    source_type: str,
    content: str,
    metadata: dict[str, Any] | None = None,
    adapter: str | None = None,
    external_ref: str | None = None,
) -> SourceRecord:
    payload = metadata or {}
    checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return insert_source_record(
        db_path,
        source_type=source_type,
        content=content,
        checksum=checksum,
        metadata=payload,
        adapter=adapter,
        external_ref=external_ref,
    )
