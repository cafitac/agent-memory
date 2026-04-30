from pathlib import Path

from agent_memory.core.curation import (
    approve_memory,
    create_candidate_fact,
    create_candidate_procedure,
    create_episode,
    deprecate_memory,
    dispute_memory,
    supersede_fact,
)
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import (
    get_fact,
    initialize_database,
    list_fact_replacement_relations,
    list_memory_status_history,
)


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

def test_status_transition_history_records_review_reason_actor_and_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X now uses PX branches instead of EP branches.",
        metadata={"project": "project-x"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="PX-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )

    approved_fact = approve_memory(
        db_path=db_path,
        memory_type="fact",
        memory_id=fact.id,
        reason="Verified from current project note.",
        actor="maintainer",
        evidence_ids=[source.id],
    )
    deprecated_fact = deprecate_memory(
        db_path=db_path,
        memory_type="fact",
        memory_id=fact.id,
        reason="Replaced by the next branch naming policy.",
        actor="maintainer",
        evidence_ids=[source.id],
    )

    assert approved_fact.status == "approved"
    assert deprecated_fact.status == "deprecated"
    history = list_memory_status_history(db_path=db_path, memory_type="fact", memory_id=fact.id)
    assert [entry.from_status for entry in history] == ["candidate", "approved"]
    assert [entry.to_status for entry in history] == ["approved", "deprecated"]
    assert history[0].reason == "Verified from current project note."
    assert history[0].actor == "maintainer"
    assert history[0].evidence_ids == [source.id]
    assert history[1].reason == "Replaced by the next branch naming policy."
    assert history[1].created_at

def test_supersede_fact_records_replacement_relation_and_status_history(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Project X moved from EP branches to PX branches.",
        metadata={"project": "project-x"},
    )
    old_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    replacement_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="PX-###",
        evidence_ids=[source.id],
        scope="project:project-x",
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=old_fact.id)

    relation = supersede_fact(
        db_path=db_path,
        superseded_fact_id=old_fact.id,
        replacement_fact_id=replacement_fact.id,
        reason="New project policy replaced the previous branch pattern.",
        actor="maintainer",
        evidence_ids=[source.id],
    )

    assert relation.from_ref == f"fact:{old_fact.id}"
    assert relation.relation_type == "superseded_by"
    assert relation.to_ref == f"fact:{replacement_fact.id}"
    assert relation.evidence_ids == [source.id]
    assert get_fact(db_path=db_path, fact_id=old_fact.id).status == "deprecated"
    assert get_fact(db_path=db_path, fact_id=replacement_fact.id).status == "approved"

    old_history = list_memory_status_history(db_path=db_path, memory_type="fact", memory_id=old_fact.id)
    replacement_history = list_memory_status_history(
        db_path=db_path,
        memory_type="fact",
        memory_id=replacement_fact.id,
    )
    assert old_history[-1].from_status == "approved"
    assert old_history[-1].to_status == "deprecated"
    assert old_history[-1].reason == "New project policy replaced the previous branch pattern."
    assert old_history[-1].actor == "maintainer"
    assert replacement_history[-1].from_status == "candidate"
    assert replacement_history[-1].to_status == "approved"

    old_relations = list_fact_replacement_relations(db_path=db_path, fact_id=old_fact.id)
    replacement_relations = list_fact_replacement_relations(db_path=db_path, fact_id=replacement_fact.id)
    assert [item.id for item in old_relations] == [relation.id]
    assert [item.id for item in replacement_relations] == [relation.id]

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What branch pattern does Project X use?",
        preferred_scope="project:project-x",
    )
    assert [fact.object_ref_or_value for fact in packet.semantic_facts] == ["PX-###"]


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
