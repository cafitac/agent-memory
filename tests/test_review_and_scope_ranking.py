from pathlib import Path

from agent_memory.core.curation import (
    approve_memory,
    create_candidate_fact,
    create_candidate_procedure,
    create_episode,
    deprecate_memory,
    dispute_memory,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_common_review_transitions_work_for_fact_procedure_and_episode(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X uses EP branches. Run tests before PR.",
        metadata={"project": "project-x"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    procedure = create_candidate_procedure(
        db_path=db_path,
        name="Run local tests",
        trigger_context="Before PR",
        preconditions=["Dependencies installed"],
        steps=["uv run pytest tests/ -q"],
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    episode = create_episode(
        db_path=db_path,
        title="Validated Project X PR workflow",
        summary="Confirmed EP branch pattern and test expectations.",
        source_ids=[source.id],
        tags=["project-x", "review"],
        importance_score=0.6,
    )

    approved_fact = approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)
    disputed_procedure = dispute_memory(db_path=db_path, memory_type="procedure", memory_id=procedure.id)
    deprecated_episode = deprecate_memory(db_path=db_path, memory_type="episode", memory_id=episode.id)

    assert approved_fact.status == "approved"
    assert disputed_procedure.status == "disputed"
    assert deprecated_episode.status == "deprecated"


def test_scope_aware_ranking_prefers_matching_scope(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Both projects use different branch names.",
        metadata={"workspace": "agent-memory"},
    )

    project_y = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Y",
        predicate="branch_pattern",
        object_ref_or_value="YY-###",
        evidence_ids=[source.id],
        scope="project:project-y",
        confidence=0.95,
    )
    project_x = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.50,
    )

    approve_memory(db_path=db_path, memory_type="fact", memory_id=project_y.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=project_x.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What branch pattern does Project X use?",
        preferred_scope="project:project-x",
    )

    assert packet.semantic_facts[0].scope == "project:project-x"
    assert packet.semantic_facts[0].object_ref_or_value == "EP-###"
