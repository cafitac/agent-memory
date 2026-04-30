from __future__ import annotations

from pathlib import Path
from typing import Literal

from agent_memory.core.models import Episode, Fact, MemoryStatus, Procedure, Relation
from agent_memory.storage.sqlite import (
    insert_episode,
    insert_fact,
    insert_procedure,
    insert_relation,
    update_memory_status,
)

MemoryType = Literal["fact", "procedure", "episode"]


def create_candidate_fact(
    db_path: Path | str,
    *,
    subject_ref: str,
    predicate: str,
    object_ref_or_value: str,
    evidence_ids: list[int],
    scope: str,
    confidence: float = 0.5,
) -> Fact:
    return insert_fact(
        db_path,
        subject_ref=subject_ref,
        predicate=predicate,
        object_ref_or_value=object_ref_or_value,
        evidence_ids=evidence_ids,
        scope=scope,
        status="candidate",
        confidence=confidence,
    )


def create_candidate_procedure(
    db_path: Path | str,
    *,
    name: str,
    trigger_context: str,
    preconditions: list[str],
    steps: list[str],
    evidence_ids: list[int],
    scope: str,
    success_rate: float = 0.0,
) -> Procedure:
    return insert_procedure(
        db_path,
        name=name,
        trigger_context=trigger_context,
        preconditions=preconditions,
        steps=steps,
        evidence_ids=evidence_ids,
        scope=scope,
        status="candidate",
        success_rate=success_rate,
    )


def create_episode(
    db_path: Path | str,
    *,
    title: str,
    summary: str,
    source_ids: list[int],
    tags: list[str],
    importance_score: float,
    scope: str = "global",
    status: MemoryStatus = "candidate",
    started_at: str | None = None,
    ended_at: str | None = None,
) -> Episode:
    return insert_episode(
        db_path,
        title=title,
        summary=summary,
        source_ids=source_ids,
        tags=tags,
        importance_score=importance_score,
        scope=scope,
        status=status,
        started_at=started_at,
        ended_at=ended_at,
    )


def create_relation(
    db_path: Path | str,
    *,
    from_ref: str,
    relation_type: str,
    to_ref: str,
    evidence_ids: list[int],
    weight: float = 1.0,
    confidence: float = 0.5,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> Relation:
    return insert_relation(
        db_path,
        from_ref=from_ref,
        relation_type=relation_type,
        to_ref=to_ref,
        evidence_ids=evidence_ids,
        weight=weight,
        confidence=confidence,
        valid_from=valid_from,
        valid_to=valid_to,
    )


def approve_fact(db_path: Path | str, *, fact_id: int) -> Fact:
    return approve_memory(db_path=db_path, memory_type="fact", memory_id=fact_id)


def approve_procedure(db_path: Path | str, *, procedure_id: int) -> Procedure:
    return approve_memory(db_path=db_path, memory_type="procedure", memory_id=procedure_id)


def approve_memory(
    db_path: Path | str,
    *,
    memory_type: MemoryType,
    memory_id: int,
    reason: str | None = None,
    actor: str | None = None,
    evidence_ids: list[int] | None = None,
) -> Fact | Procedure | Episode:
    return update_memory_status(
        db_path,
        memory_type=memory_type,
        memory_id=memory_id,
        status="approved",
        reason=reason,
        actor=actor,
        evidence_ids=evidence_ids,
    )


def dispute_memory(
    db_path: Path | str,
    *,
    memory_type: MemoryType,
    memory_id: int,
    reason: str | None = None,
    actor: str | None = None,
    evidence_ids: list[int] | None = None,
) -> Fact | Procedure | Episode:
    return update_memory_status(
        db_path,
        memory_type=memory_type,
        memory_id=memory_id,
        status="disputed",
        reason=reason,
        actor=actor,
        evidence_ids=evidence_ids,
    )


def deprecate_memory(
    db_path: Path | str,
    *,
    memory_type: MemoryType,
    memory_id: int,
    reason: str | None = None,
    actor: str | None = None,
    evidence_ids: list[int] | None = None,
) -> Fact | Procedure | Episode:
    return update_memory_status(
        db_path,
        memory_type=memory_type,
        memory_id=memory_id,
        status="deprecated",
        reason=reason,
        actor=actor,
        evidence_ids=evidence_ids,
    )
