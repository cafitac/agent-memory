from __future__ import annotations

import json
import math
import sqlite3
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from typing import Any, Callable, Literal, TypeVar

from agent_memory.core.models import Episode, Fact, MemoryStatus, Procedure, Relation, RetrievalTraceEntry, SourceRecord

T = TypeVar("T")
MemoryType = Literal["fact", "procedure", "episode"]

TABLE_NAME_BY_MEMORY_TYPE: dict[MemoryType, str] = {
    "fact": "facts",
    "procedure": "procedures",
    "episode": "episodes",
}

ROW_PARSER_BY_MEMORY_TYPE: dict[MemoryType, Callable[[sqlite3.Row], Any]] = {
    "fact": lambda row: fact_from_row(row),
    "procedure": lambda row: procedure_from_row(row),
    "episode": lambda row: episode_from_row(row),
}

RANK_COLUMN_BY_TABLE: dict[str, str] = {
    "facts": "confidence",
    "procedures": "success_rate",
    "episodes": "importance_score",
}

SCOPE_COLUMN_BY_TABLE: dict[str, str | None] = {
    "facts": "scope",
    "procedures": "scope",
    "episodes": "scope",
}


def _schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def _schema_sql() -> str:
    resource = files("agent_memory.storage").joinpath("schema.sql")
    return resource.read_text()


def connect(db_path: Path | str) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: Path | str) -> None:
    with connect(db_path) as connection:
        connection.executescript(_schema_sql())
        _ensure_memory_table_columns(
            connection,
            table_name="facts",
            required_columns={
                "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "approved_at": "TEXT",
                "last_accessed_at": "TEXT",
                "retrieval_count": "INTEGER NOT NULL DEFAULT 0",
                "reinforcement_count": "REAL NOT NULL DEFAULT 0.0",
            },
        )
        _ensure_memory_table_columns(
            connection,
            table_name="procedures",
            required_columns={
                "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "approved_at": "TEXT",
                "last_accessed_at": "TEXT",
                "retrieval_count": "INTEGER NOT NULL DEFAULT 0",
                "reinforcement_count": "REAL NOT NULL DEFAULT 0.0",
            },
        )
        _ensure_memory_table_columns(
            connection,
            table_name="episodes",
            required_columns={
                "scope": "TEXT NOT NULL DEFAULT 'global'",
                "created_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "updated_at": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
                "approved_at": "TEXT",
                "last_accessed_at": "TEXT",
                "retrieval_count": "INTEGER NOT NULL DEFAULT 0",
                "reinforcement_count": "REAL NOT NULL DEFAULT 0.0",
            },
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_episodes_status_scope_importance ON episodes(status, scope, importance_score)"
        )


def _ensure_memory_table_columns(
    connection: sqlite3.Connection,
    *,
    table_name: str,
    required_columns: dict[str, str],
) -> None:
    existing_columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()}
    for column_name, column_sql in required_columns.items():
        if column_name in existing_columns:
            continue
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_sql}")


def insert_source_record(
    db_path: Path | str,
    *,
    source_type: str,
    content: str,
    checksum: str,
    metadata: dict[str, Any],
    adapter: str | None = None,
    external_ref: str | None = None,
) -> SourceRecord:
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO source_records (
                source_type,
                adapter,
                external_ref,
                content,
                checksum,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (source_type, adapter, external_ref, content, checksum, json.dumps(metadata, sort_keys=True)),
        )
        row = connection.execute(
            "SELECT * FROM source_records WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    return source_record_from_row(row)


def insert_fact(
    db_path: Path | str,
    *,
    subject_ref: str,
    predicate: str,
    object_ref_or_value: str,
    evidence_ids: list[int],
    scope: str,
    status: MemoryStatus = "candidate",
    confidence: float = 0.5,
    valid_from: str | None = None,
    valid_to: str | None = None,
) -> Fact:
    searchable_text = " ".join([subject_ref, predicate.replace("_", " "), object_ref_or_value])
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO facts (
                subject_ref,
                predicate,
                object_ref_or_value,
                evidence_ids_json,
                confidence,
                valid_from,
                valid_to,
                scope,
                status,
                searchable_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                subject_ref,
                predicate,
                object_ref_or_value,
                json.dumps(evidence_ids),
                confidence,
                valid_from,
                valid_to,
                scope,
                status,
                searchable_text,
            ),
        )
        row = connection.execute("SELECT * FROM facts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return fact_from_row(row)


def insert_procedure(
    db_path: Path | str,
    *,
    name: str,
    trigger_context: str,
    preconditions: list[str],
    steps: list[str],
    evidence_ids: list[int],
    scope: str,
    status: MemoryStatus = "candidate",
    success_rate: float = 0.0,
) -> Procedure:
    searchable_text = " ".join([name, trigger_context, *preconditions, *steps])
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO procedures (
                name,
                trigger_context,
                preconditions_json,
                steps_json,
                evidence_ids_json,
                success_rate,
                scope,
                status,
                searchable_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                trigger_context,
                json.dumps(preconditions),
                json.dumps(steps),
                json.dumps(evidence_ids),
                success_rate,
                scope,
                status,
                searchable_text,
            ),
        )
        row = connection.execute("SELECT * FROM procedures WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return procedure_from_row(row)


def insert_episode(
    db_path: Path | str,
    *,
    title: str,
    summary: str,
    source_ids: list[int],
    tags: list[str],
    importance_score: float,
    scope: str,
    status: MemoryStatus = "candidate",
    started_at: str | None = None,
    ended_at: str | None = None,
) -> Episode:
    searchable_text = " ".join([title, summary, *tags])
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO episodes (
                title,
                summary,
                started_at,
                ended_at,
                source_ids_json,
                tags_json,
                importance_score,
                scope,
                status,
                searchable_text
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                title,
                summary,
                started_at,
                ended_at,
                json.dumps(source_ids),
                json.dumps(tags),
                importance_score,
                scope,
                status,
                searchable_text,
            ),
        )
        row = connection.execute("SELECT * FROM episodes WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return episode_from_row(row)


def insert_relation(
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
    with connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO relations (
                from_ref,
                relation_type,
                to_ref,
                weight,
                evidence_ids_json,
                confidence,
                valid_from,
                valid_to
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                from_ref,
                relation_type,
                to_ref,
                weight,
                json.dumps(evidence_ids),
                confidence,
                valid_from,
                valid_to,
            ),
        )
        row = connection.execute("SELECT * FROM relations WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return relation_from_row(row)


def update_memory_status(
    db_path: Path | str,
    *,
    memory_type: MemoryType,
    memory_id: int,
    status: MemoryStatus,
) -> Fact | Procedure | Episode:
    table_name = TABLE_NAME_BY_MEMORY_TYPE[memory_type]
    row_parser = ROW_PARSER_BY_MEMORY_TYPE[memory_type]
    return _update_status(db_path, table_name=table_name, object_id=memory_id, status=status, row_parser=row_parser)


def search_approved_facts(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[Fact]:
    return [
        model
        for model, _trace in search_ranked_approved_facts(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
    ]


def search_ranked_approved_facts(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[tuple[Fact, RetrievalTraceEntry]]:
    return _search_model_rows_with_trace(
        db_path=db_path,
        table_name="facts",
        memory_type="fact",
        query=query,
        limit=limit,
        row_parser=fact_from_row,
        preferred_scope=preferred_scope,
    )


def search_approved_procedures(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[Procedure]:
    return [
        model
        for model, _trace in search_ranked_approved_procedures(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
    ]


def search_ranked_approved_procedures(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[tuple[Procedure, RetrievalTraceEntry]]:
    return _search_model_rows_with_trace(
        db_path=db_path,
        table_name="procedures",
        memory_type="procedure",
        query=query,
        limit=limit,
        row_parser=procedure_from_row,
        preferred_scope=preferred_scope,
    )


def search_approved_episodes(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[Episode]:
    return [
        model
        for model, _trace in search_ranked_approved_episodes(
            db_path,
            query=query,
            limit=limit,
            preferred_scope=preferred_scope,
        )
    ]


def search_ranked_approved_episodes(
    db_path: Path | str,
    *,
    query: str,
    limit: int = 5,
    preferred_scope: str | None = None,
) -> list[tuple[Episode, RetrievalTraceEntry]]:
    return _search_model_rows_with_trace(
        db_path=db_path,
        table_name="episodes",
        memory_type="episode",
        query=query,
        limit=limit,
        row_parser=episode_from_row,
        preferred_scope=preferred_scope,
    )


def search_relations_for_refs(db_path: Path | str, *, refs: list[str], limit: int = 10) -> list[Relation]:
    unique_refs = sorted({ref for ref in refs if ref})
    if not unique_refs:
        return []

    placeholders = ", ".join("?" for _ in unique_refs)
    params = [*unique_refs, *unique_refs, limit]
    sql = f"""
        SELECT *
        FROM relations
        WHERE from_ref IN ({placeholders}) OR to_ref IN ({placeholders})
        ORDER BY confidence DESC, weight DESC, id ASC
        LIMIT ?
    """
    with connect(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [relation_from_row(row) for row in rows]


def search_relations_matching_query(db_path: Path | str, *, query: str, limit: int = 20) -> list[Relation]:
    tokens = _tokenize_query(query)
    if not tokens:
        return []

    sql = "SELECT * FROM relations WHERE "
    clauses: list[str] = []
    params: list[Any] = []
    for token in tokens:
        clauses.append("(LOWER(from_ref) LIKE ? OR LOWER(to_ref) LIKE ? OR LOWER(relation_type) LIKE ?)")
        params.extend([f"%{token}%", f"%{token}%", f"%{token}%"])
    sql += " OR ".join(clauses)
    sql += " ORDER BY confidence DESC, weight DESC, id ASC LIMIT ?"
    params.append(limit)

    with connect(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [relation_from_row(row) for row in rows]


def list_candidate_facts(db_path: Path | str, limit: int = 50) -> list[Fact]:
    return _list_by_status(db_path, table_name="facts", status="candidate", limit=limit, row_parser=fact_from_row)


def list_candidate_procedures(db_path: Path | str, limit: int = 50) -> list[Procedure]:
    return _list_by_status(
        db_path,
        table_name="procedures",
        status="candidate",
        limit=limit,
        row_parser=procedure_from_row,
    )


def list_candidate_episodes(db_path: Path | str, limit: int = 50) -> list[Episode]:
    return _list_by_status(db_path, table_name="episodes", status="candidate", limit=limit, row_parser=episode_from_row)


def list_approved_facts(db_path: Path | str, scope: str | None = None) -> list[Fact]:
    return _list_approved_by_scope(db_path, table_name="facts", scope=scope, row_parser=fact_from_row)


def list_approved_procedures(db_path: Path | str, scope: str | None = None) -> list[Procedure]:
    return _list_approved_by_scope(db_path, table_name="procedures", scope=scope, row_parser=procedure_from_row)


def list_approved_episodes(db_path: Path | str, scope: str | None = None) -> list[Episode]:
    return _list_approved_by_scope(db_path, table_name="episodes", scope=scope, row_parser=episode_from_row)


def get_source_records_by_ids(db_path: Path | str, source_ids: list[int]) -> list[SourceRecord]:
    unique_ids = sorted({source_id for source_id in source_ids})
    if not unique_ids:
        return []
    placeholders = ", ".join("?" for _ in unique_ids)
    sql = f"SELECT * FROM source_records WHERE id IN ({placeholders}) ORDER BY id ASC"
    with connect(db_path) as connection:
        rows = connection.execute(sql, unique_ids).fetchall()
    return [source_record_from_row(row) for row in rows]


def _update_status(
    db_path: Path | str,
    *,
    table_name: str,
    object_id: int,
    status: MemoryStatus,
    row_parser: Callable[[sqlite3.Row], T],
) -> T:
    with connect(db_path) as connection:
        if status == "approved":
            connection.execute(
                f"""
                UPDATE {table_name}
                SET status = ?,
                    updated_at = CURRENT_TIMESTAMP,
                    approved_at = COALESCE(approved_at, CURRENT_TIMESTAMP)
                WHERE id = ?
                """,
                (status, object_id),
            )
        else:
            connection.execute(
                f"UPDATE {table_name} SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (status, object_id),
            )
        row = connection.execute(f"SELECT * FROM {table_name} WHERE id = ?", (object_id,)).fetchone()
    return row_parser(row)


def record_memory_retrieval(
    db_path: Path | str,
    *,
    memory_type: MemoryType,
    memory_id: int,
) -> None:
    table_name = TABLE_NAME_BY_MEMORY_TYPE[memory_type]
    with connect(db_path) as connection:
        connection.execute(
            f"""
            UPDATE {table_name}
            SET retrieval_count = COALESCE(retrieval_count, 0) + 1,
                reinforcement_count = COALESCE(reinforcement_count, 0.0) + 1.0,
                last_accessed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (memory_id,),
        )


def _search_model_rows_with_trace(
    db_path: Path | str,
    *,
    table_name: str,
    memory_type: Literal["fact", "procedure", "episode"],
    query: str,
    limit: int,
    row_parser: Callable[[sqlite3.Row], T],
    preferred_scope: str | None,
) -> list[tuple[T, RetrievalTraceEntry]]:
    tokens = _tokenize_query(query)
    query_relations = search_relations_matching_query(db_path, query=query, limit=max(limit * 3, 10))

    with connect(db_path) as connection:
        rows = connection.execute(f"SELECT * FROM {table_name} WHERE status = 'approved'").fetchall()
        non_approved_rows = (
            connection.execute(f"SELECT * FROM {table_name} WHERE status IN ('disputed', 'deprecated')").fetchall()
            if table_name == "facts"
            else []
        )

    recency_values = [_row_recency_value(row) for row in rows]
    recency_min = min(recency_values) if recency_values else None
    recency_max = max(recency_values) if recency_values else None
    approved_conflicts = _approved_fact_conflict_map(rows) if table_name == "facts" else {}
    hidden_alternatives = _hidden_fact_alternative_map(rows, non_approved_rows) if table_name == "facts" else {}

    scored_rows: list[tuple[tuple[Any, ...], T, RetrievalTraceEntry]] = []
    for row in rows:
        model = row_parser(row)
        text_matches = _count_text_matches(row["searchable_text"], tokens)
        relation_match_count, matched_terms, supporting_relation_ids = _relation_support_for_model(
            table_name,
            model,
            query_relations,
            tokens,
        )
        if tokens and text_matches == 0 and relation_match_count == 0:
            continue

        scope_priority = _scope_priority(preferred_scope=preferred_scope, candidate_scope=_model_scope(model))
        rank_value = float(getattr(model, RANK_COLUMN_BY_TABLE[table_name]))
        scope_score = _scope_score(scope_priority)
        lexical_score = float(text_matches)
        relation_score = float(relation_match_count)
        recency_score = _recency_score(_row_recency_value(row), minimum=recency_min, maximum=recency_max)
        reinforcement_score = _reinforcement_score(row)
        conflict_count = approved_conflicts.get(model.id, 0)
        conflict_penalty = _conflict_penalty(conflict_count)
        hidden_disputed_alternatives_count, hidden_deprecated_alternatives_count = hidden_alternatives.get(
            model.id,
            (0, 0),
        )
        hidden_alternative_count = hidden_disputed_alternatives_count + hidden_deprecated_alternatives_count
        rank_signal_score = rank_value
        total_score = (
            scope_score
            + lexical_score
            + relation_score
            + recency_score
            + reinforcement_score
            + conflict_penalty
            + rank_signal_score
        )
        score_tuple = (
            -total_score,
            scope_priority,
            -max(text_matches, relation_match_count),
            -relation_match_count,
            -recency_score,
            -reinforcement_score,
            -rank_value,
            model.id,
        )
        trace = RetrievalTraceEntry(
            memory_type=memory_type,
            memory_id=model.id,
            label=_model_label(table_name, model),
            scope=_model_scope(model),
            scope_priority=scope_priority,
            text_match_count=text_matches,
            relation_match_count=relation_match_count,
            matched_terms=matched_terms,
            supporting_relation_ids=supporting_relation_ids,
            rank_value=rank_value,
            scope_score=scope_score,
            lexical_score=lexical_score,
            relation_score=relation_score,
            recency_score=recency_score,
            reinforcement_score=reinforcement_score,
            conflict_count=conflict_count,
            conflict_penalty=conflict_penalty,
            hidden_disputed_alternatives_count=hidden_disputed_alternatives_count,
            hidden_deprecated_alternatives_count=hidden_deprecated_alternatives_count,
            hidden_alternative_count=hidden_alternative_count,
            rank_signal_score=rank_signal_score,
            total_score=total_score,
        )
        scored_rows.append((score_tuple, model, trace))

    scored_rows.sort(key=lambda item: item[0])
    return [(model, trace) for _, model, trace in scored_rows[:limit]]


def _tokenize_query(query: str) -> list[str]:
    return [token.lower() for token in query.replace("?", " ").replace(".", " ").split() if token.strip()]


def _count_text_matches(searchable_text: str, tokens: list[str]) -> int:
    lowered = searchable_text.lower()
    return sum(1 for token in tokens if token in lowered)


def _row_recency_value(row: sqlite3.Row) -> float:
    for column_name in ("approved_at", "updated_at", "ended_at", "started_at", "created_at", "last_accessed_at"):
        parsed = _parse_timestamp(row[column_name]) if column_name in row.keys() else None
        if parsed is not None:
            return parsed.timestamp()
    return 0.0


def _recency_score(value: float, *, minimum: float | None, maximum: float | None) -> float:
    if minimum is None or maximum is None:
        return 0.0
    if maximum <= minimum:
        return 1.0
    return max(0.0, min(1.0, (value - minimum) / (maximum - minimum)))


def _reinforcement_score(row: sqlite3.Row) -> float:
    reinforcement_count = float(row["reinforcement_count"]) if "reinforcement_count" in row.keys() else 0.0
    retrieval_count = float(row["retrieval_count"]) if "retrieval_count" in row.keys() else 0.0
    return math.log1p(max(reinforcement_count, retrieval_count))


def _approved_fact_conflict_map(rows: list[sqlite3.Row]) -> dict[int, int]:
    grouped_values: dict[tuple[str, str, str], set[str]] = {}
    row_keys: dict[int, tuple[str, str, str]] = {}
    for row in rows:
        key = (row["subject_ref"], row["predicate"], row["scope"])
        row_keys[row["id"]] = key
        grouped_values.setdefault(key, set()).add(row["object_ref_or_value"])
    return {
        row_id: max(0, len(grouped_values[key]) - 1)
        for row_id, key in row_keys.items()
    }


def _hidden_fact_alternative_map(
    approved_rows: list[sqlite3.Row],
    non_approved_rows: list[sqlite3.Row],
) -> dict[int, tuple[int, int]]:
    grouped_hidden_counts: dict[tuple[str, str, str], dict[str, int]] = {}
    for row in non_approved_rows:
        key = (row["subject_ref"], row["predicate"], row["scope"])
        status_counts = grouped_hidden_counts.setdefault(key, {"disputed": 0, "deprecated": 0})
        if row["status"] in status_counts:
            status_counts[row["status"]] += 1

    result: dict[int, tuple[int, int]] = {}
    for row in approved_rows:
        key = (row["subject_ref"], row["predicate"], row["scope"])
        status_counts = grouped_hidden_counts.get(key, {"disputed": 0, "deprecated": 0})
        result[row["id"]] = (status_counts["disputed"], status_counts["deprecated"])
    return result


def _conflict_penalty(conflict_count: int) -> float:
    if conflict_count <= 0:
        return 0.0
    return -0.75 * float(conflict_count)


def _parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _relation_support_for_model(
    table_name: str,
    model: Fact | Procedure | Episode,
    relations: list[Relation],
    tokens: list[str],
) -> tuple[int, list[str], list[int]]:
    refs = _model_refs(table_name, model)
    matched_terms: set[str] = set()
    supporting_relation_ids: list[int] = []
    for relation in relations:
        relation_text = f"{relation.from_ref} {relation.relation_type} {relation.to_ref}".lower()
        relation_terms = sorted({token for token in tokens if token in relation_text})
        if not relation_terms:
            continue
        if relation.from_ref in refs or relation.to_ref in refs:
            matched_terms.update(relation_terms)
            supporting_relation_ids.append(relation.id)
    supporting_relation_ids = sorted(set(supporting_relation_ids))
    return len(supporting_relation_ids), sorted(matched_terms), supporting_relation_ids


def _model_label(table_name: str, model: Fact | Procedure | Episode) -> str:
    if table_name == "facts":
        return model.subject_ref
    if table_name == "procedures":
        return model.name
    return model.title


def _model_refs(table_name: str, model: Fact | Procedure | Episode) -> set[str]:
    if table_name == "facts":
        return {model.subject_ref}
    if table_name == "procedures":
        return {model.name}
    return {model.title, *model.tags}


def _model_scope(model: Fact | Procedure | Episode) -> str | None:
    return getattr(model, "scope", None)


def _scope_priority(*, preferred_scope: str | None, candidate_scope: str | None) -> int:
    if not preferred_scope or not candidate_scope:
        return 50
    if candidate_scope == preferred_scope:
        return 0

    preferred_kind = _scope_kind(preferred_scope)
    candidate_kind = _scope_kind(candidate_scope)
    fallback_order: dict[str, list[str]] = {
        "project": ["workspace", "user", "global", "cwd", "project", "other"],
        "workspace": ["user", "global", "project", "cwd", "workspace", "other"],
        "user": ["cwd", "global", "workspace", "project", "user", "other"],
        "cwd": ["user", "global", "workspace", "project", "cwd", "other"],
        "global": ["user", "workspace", "project", "cwd", "global", "other"],
    }
    ordered_kinds = fallback_order.get(preferred_kind, ["user", "global", "workspace", "project", "cwd", "other"])
    try:
        return 1 + ordered_kinds.index(candidate_kind)
    except ValueError:
        return 99


def _scope_score(scope_priority: int) -> float:
    if scope_priority <= 0:
        return 10.0
    return max(0.0, 10.0 - float(scope_priority))


def _scope_kind(scope: str) -> str:
    if scope == "global":
        return "global"
    if ":" not in scope:
        return "other"
    kind = scope.split(":", 1)[0]
    if kind in {"project", "workspace", "user", "cwd"}:
        return kind
    return "other"


def _list_by_status(
    db_path: Path | str,
    *,
    table_name: str,
    status: MemoryStatus,
    limit: int,
    row_parser: Callable[[sqlite3.Row], T],
) -> list[T]:
    with connect(db_path) as connection:
        rows = connection.execute(
            f"SELECT * FROM {table_name} WHERE status = ? ORDER BY id ASC LIMIT ?",
            (status, limit),
        ).fetchall()
    return [row_parser(row) for row in rows]


def _list_approved_by_scope(
    db_path: Path | str,
    *,
    table_name: str,
    scope: str | None,
    row_parser: Callable[[sqlite3.Row], T],
) -> list[T]:
    sql = f"SELECT * FROM {table_name} WHERE status = ?"
    params: list[Any] = ["approved"]
    if scope is not None:
        sql += " AND scope = ?"
        params.append(scope)
    sql += " ORDER BY id ASC"
    with connect(db_path) as connection:
        rows = connection.execute(sql, params).fetchall()
    return [row_parser(row) for row in rows]


def source_record_from_row(row: sqlite3.Row) -> SourceRecord:
    return SourceRecord(
        id=row["id"],
        source_type=row["source_type"],
        adapter=row["adapter"],
        external_ref=row["external_ref"],
        created_at=row["created_at"],
        content=row["content"],
        checksum=row["checksum"],
        metadata=json.loads(row["metadata_json"]),
    )


def fact_from_row(row: sqlite3.Row) -> Fact:
    return Fact(
        id=row["id"],
        subject_ref=row["subject_ref"],
        predicate=row["predicate"],
        object_ref_or_value=row["object_ref_or_value"],
        evidence_ids=json.loads(row["evidence_ids_json"]),
        confidence=row["confidence"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
        scope=row["scope"],
        status=row["status"],
        searchable_text=row["searchable_text"],
    )


def procedure_from_row(row: sqlite3.Row) -> Procedure:
    return Procedure(
        id=row["id"],
        name=row["name"],
        trigger_context=row["trigger_context"],
        preconditions=json.loads(row["preconditions_json"]),
        steps=json.loads(row["steps_json"]),
        evidence_ids=json.loads(row["evidence_ids_json"]),
        success_rate=row["success_rate"],
        scope=row["scope"],
        status=row["status"],
        searchable_text=row["searchable_text"],
    )


def episode_from_row(row: sqlite3.Row) -> Episode:
    return Episode(
        id=row["id"],
        title=row["title"],
        summary=row["summary"],
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        source_ids=json.loads(row["source_ids_json"]),
        tags=json.loads(row["tags_json"]),
        importance_score=row["importance_score"],
        scope=row["scope"],
        status=row["status"],
        searchable_text=row["searchable_text"],
    )


def relation_from_row(row: sqlite3.Row) -> Relation:
    return Relation(
        id=row["id"],
        from_ref=row["from_ref"],
        relation_type=row["relation_type"],
        to_ref=row["to_ref"],
        weight=row["weight"],
        evidence_ids=json.loads(row["evidence_ids_json"]),
        confidence=row["confidence"],
        valid_from=row["valid_from"],
        valid_to=row["valid_to"],
    )
