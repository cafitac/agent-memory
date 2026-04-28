from pathlib import Path

from agent_memory.core.curation import approve_fact, create_candidate_fact
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import MemoryPacket
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_ingest_initialize_and_retrieve_fact(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"

    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes stores sessions in SQLite with FTS5 search.",
        metadata={"project": "hermes"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes",
        predicate="stores_sessions_in",
        object_ref_or_value="SQLite with FTS5 search",
        evidence_ids=[source.id],
        scope="project:hermes",
    )

    approve_fact(db_path=db_path, fact_id=fact.id)

    packet = retrieve_memory_packet(db_path=db_path, query="Where does Hermes store sessions?")

    assert isinstance(packet, MemoryPacket)
    assert [fact.subject_ref for fact in packet.semantic_facts] == ["Hermes"]
    assert packet.semantic_facts[0].status == "approved"
    assert packet.semantic_facts[0].evidence_ids == [source.id]


def test_only_approved_facts_are_returned(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"

    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X uses branch naming pattern EP-###.",
        metadata={"project": "project-x"},
    )

    create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )

    packet = retrieve_memory_packet(db_path=db_path, query="What branch pattern does Project X use?")

    assert packet.semantic_facts == []
