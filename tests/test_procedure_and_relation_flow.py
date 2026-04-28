from pathlib import Path

from agent_memory.core.curation import (
    approve_fact,
    approve_procedure,
    create_candidate_fact,
    create_candidate_procedure,
    create_relation,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import MemoryPacket
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_retrieve_memory_packet_returns_pydantic_model(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    packet = retrieve_memory_packet(db_path=db_path, query="anything")

    assert isinstance(packet, MemoryPacket)
    assert packet.semantic_facts == []
    assert packet.procedural_guidance == []


def test_approved_procedure_is_returned_in_procedural_guidance(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Run pytest tests/ -q before opening a PR.",
        metadata={"project": "agent-memory"},
    )

    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local test suite",
        trigger_context="Before opening a PR for agent-memory",
        preconditions=["Project dependencies installed"],
        steps=["Run PYTHONPATH=src pytest tests/ -q"],
        evidence_ids=[source.id],
        scope="project:agent-memory",
    )
    approve_procedure(db_path=db_path, procedure_id=procedure.id)

    packet = retrieve_memory_packet(db_path=db_path, query="How should I validate agent-memory before opening a PR?")

    assert [item.name for item in packet.procedural_guidance] == ["Run local test suite"]
    assert packet.procedural_guidance[0].status == "approved"
    assert packet.procedural_guidance[0].steps == ["Run PYTHONPATH=src pytest tests/ -q"]


def test_related_relations_are_returned_with_matching_facts(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes stores sessions in SQLite with FTS5 search. SQLite powers lexical retrieval.",
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

    relation = create_relation(
        db_path=db_path,
        from_ref="Hermes",
        relation_type="uses_storage",
        to_ref="SQLite",
        evidence_ids=[source.id],
    )

    packet = retrieve_memory_packet(db_path=db_path, query="Where does Hermes store sessions?")

    assert len(packet.related_relations) == 1
    assert packet.related_relations[0].id == relation.id
    assert packet.related_relations[0].from_ref == "Hermes"
    assert packet.related_relations[0].to_ref == "SQLite"
