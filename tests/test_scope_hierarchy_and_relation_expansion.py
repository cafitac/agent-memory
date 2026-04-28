from pathlib import Path

from agent_memory.core.curation import approve_memory, create_candidate_fact, create_episode, create_relation
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_episode_scope_hierarchy_prefers_exact_then_workspace_then_global(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Scheduled job refactor notes exist at project, workspace, and global scopes.",
        metadata={"workspace": "example-backend"},
    )

    project_episode = create_episode(
        db_path=db_path,
        title="Scheduled job refactor",
        summary="Project-specific rollout notes for example-backend scheduled job refactor.",
        source_ids=[source.id],
        tags=["daily-task", "project"],
        importance_score=0.4,
        scope="project:example-backend",
        status="approved",
    )
    workspace_episode = create_episode(
        db_path=db_path,
        title="Scheduled job refactor",
        summary="Workspace-wide operational notes for scheduled job refactor.",
        source_ids=[source.id],
        tags=["daily-task", "workspace"],
        importance_score=0.9,
        scope="workspace:example-workspace",
        status="approved",
    )
    global_episode = create_episode(
        db_path=db_path,
        title="Scheduled job refactor",
        summary="Global fallback note for scheduled job refactor.",
        source_ids=[source.id],
        tags=["daily-task", "global"],
        importance_score=1.0,
        scope="global",
        status="approved",
    )

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What happened in the scheduled job refactor?",
        preferred_scope="project:example-backend",
        limit=3,
    )

    assert [episode.id for episode in packet.episodic_context] == [
        project_episode.id,
        workspace_episode.id,
        global_episode.id,
    ]


def test_scope_hierarchy_prefers_workspace_and_global_before_other_projects(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="Branch naming differs by scope.",
        metadata={"workspace": "example-workspace"},
    )

    other_project_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="branch_pattern",
        object_ref_or_value="ZZ-###",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.99,
    )
    workspace_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Workspace policy",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="workspace:example-workspace",
        confidence=0.30,
    )
    global_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Global policy",
        predicate="branch_pattern",
        object_ref_or_value="GEN-###",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.20,
    )

    approve_memory(db_path=db_path, memory_type="fact", memory_id=other_project_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=workspace_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=global_fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What branch pattern should I use?",
        preferred_scope="project:project-x",
        limit=3,
    )

    assert [fact.id for fact in packet.semantic_facts] == [
        workspace_fact.id,
        global_fact.id,
        other_project_fact.id,
    ]


def test_relation_aware_retrieval_expands_semantic_facts_from_query_ref(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes persists sessions locally. SQLite is the backing store.",
        metadata={"project": "hermes"},
    )

    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes",
        predicate="persistence_mode",
        object_ref_or_value="local durable session store",
        evidence_ids=[source.id],
        scope="project:hermes",
        confidence=0.4,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)

    relation = create_relation(
        db_path=db_path,
        from_ref="Hermes",
        relation_type="uses_storage",
        to_ref="SQLite",
        evidence_ids=[source.id],
        weight=1.0,
        confidence=0.9,
    )

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Which system uses SQLite?",
        preferred_scope="project:hermes",
    )

    assert packet.semantic_facts[0].id == fact.id
    assert packet.related_relations[0].id == relation.id
    assert packet.related_relations[0].to_ref == "SQLite"
