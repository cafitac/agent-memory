from __future__ import annotations

from pathlib import Path
from typing import Iterable

from agent_memory.core.models import (
    Episode,
    Fact,
    KbExportCounts,
    KbExportedFile,
    KbExportResult,
    Procedure,
    SourceRecord,
)
from agent_memory.storage.sqlite import (
    get_source_records_by_ids,
    list_approved_episodes,
    list_approved_facts,
    list_approved_procedures,
)

EXCERPT_MAX_CHARS = 240


def export_kb_markdown(
    db_path: Path | str,
    output_dir: Path | str,
    *,
    scope: str | None = None,
) -> KbExportResult:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    facts = list_approved_facts(db_path, scope=scope)
    procedures = list_approved_procedures(db_path, scope=scope)
    episodes = list_approved_episodes(db_path, scope=scope)
    source_ids = _collect_source_ids(facts, procedures, episodes)
    sources_by_id = {source.id: source for source in get_source_records_by_ids(db_path, source_ids)}

    written_files = [
        _write_file(output_path / "index.md", "index", _render_index(scope, facts, procedures, episodes, source_ids), 0),
        _write_file(output_path / "facts.md", "fact", _render_facts(facts, sources_by_id), len(facts)),
        _write_file(
            output_path / "procedures.md",
            "procedure",
            _render_procedures(procedures, sources_by_id),
            len(procedures),
        ),
        _write_file(output_path / "episodes.md", "episode", _render_episodes(episodes, sources_by_id), len(episodes)),
    ]
    counts = KbExportCounts(
        facts=len(facts),
        procedures=len(procedures),
        episodes=len(episodes),
        total_items=len(facts) + len(procedures) + len(episodes),
    )
    return KbExportResult(output_dir=str(output_path), scope=scope, files=written_files, counts=counts, source_ids=source_ids)


def _write_file(path: Path, memory_type: str, content: str, item_count: int) -> KbExportedFile:
    path.write_text(content, encoding="utf-8")
    return KbExportedFile(path=str(path), memory_type=memory_type, item_count=item_count)


def _render_index(
    scope: str | None,
    facts: list[Fact],
    procedures: list[Procedure],
    episodes: list[Episode],
    source_ids: list[int],
) -> str:
    title = "# Agent Memory KB Export"
    scope_line = f"Scope: {scope}" if scope is not None else "Scope: all"
    return "\n".join(
        [
            title,
            "",
            scope_line,
            f"Source records referenced: {len(source_ids)}",
            "",
            "## Files",
            "",
            f"- [Facts](facts.md): {len(facts)}",
            f"- [Procedures](procedures.md): {len(procedures)}",
            f"- [Episodes](episodes.md): {len(episodes)}",
            "",
        ]
    )


def _render_facts(facts: list[Fact], sources_by_id: dict[int, SourceRecord]) -> str:
    lines = ["# Facts", ""]
    if not facts:
        lines.extend(["No approved facts exported.", ""])
        return "\n".join(lines)
    for fact in facts:
        lines.extend(
            [
                f"## {fact.subject_ref}",
                "",
                f"- Predicate: {fact.predicate}",
                f"- Value: {fact.object_ref_or_value}",
                f"- Scope: {fact.scope}",
                f"- Confidence: {fact.confidence:g}",
                f"- Evidence source ids: {_format_ids(fact.evidence_ids)}",
                "",
            ]
        )
        lines.extend(_render_sources(fact.evidence_ids, sources_by_id))
    return "\n".join(lines)


def _render_procedures(procedures: list[Procedure], sources_by_id: dict[int, SourceRecord]) -> str:
    lines = ["# Procedures", ""]
    if not procedures:
        lines.extend(["No approved procedures exported.", ""])
        return "\n".join(lines)
    for procedure in procedures:
        lines.extend(
            [
                f"## {procedure.name}",
                "",
                f"- Trigger: {procedure.trigger_context}",
                f"- Scope: {procedure.scope}",
                f"- Success rate: {procedure.success_rate:g}",
                f"- Evidence source ids: {_format_ids(procedure.evidence_ids)}",
                "",
            ]
        )
        if procedure.preconditions:
            lines.extend(["### Preconditions", ""])
            lines.extend(f"- {precondition}" for precondition in procedure.preconditions)
            lines.append("")
        if procedure.steps:
            lines.extend(["### Steps", ""])
            lines.extend(f"{index}. {step}" for index, step in enumerate(procedure.steps, start=1))
            lines.append("")
        lines.extend(_render_sources(procedure.evidence_ids, sources_by_id))
    return "\n".join(lines)


def _render_episodes(episodes: list[Episode], sources_by_id: dict[int, SourceRecord]) -> str:
    lines = ["# Episodes", ""]
    if not episodes:
        lines.extend(["No approved episodes exported.", ""])
        return "\n".join(lines)
    for episode in episodes:
        lines.extend(
            [
                f"## {episode.title}",
                "",
                episode.summary,
                "",
                f"- Scope: {episode.scope}",
                f"- Importance: {episode.importance_score:g}",
                f"- Tags: {_format_strings(episode.tags)}",
                f"- Source ids: {_format_ids(episode.source_ids)}",
                "",
            ]
        )
        lines.extend(_render_sources(episode.source_ids, sources_by_id))
    return "\n".join(lines)


def _render_sources(source_ids: list[int], sources_by_id: dict[int, SourceRecord]) -> list[str]:
    if not source_ids:
        return []
    lines = ["### Sources", ""]
    for source_id in _unique_sorted(source_ids):
        source = sources_by_id.get(source_id)
        if source is None:
            lines.extend([f"- Source {source_id}: missing", ""])
            continue
        lines.extend(
            [
                f"#### Source {source.id}",
                "",
                f"- Type: {source.source_type}",
                f"- Created at: {source.created_at}",
            ]
        )
        if source.adapter is not None:
            lines.append(f"- Adapter: {source.adapter}")
        if source.external_ref is not None:
            lines.append(f"- External ref: {source.external_ref}")
        lines.append(f"- Metadata: {_format_metadata(source.metadata)}")
        lines.extend([f"- Excerpt: {_excerpt(source.content)}", ""])
    return lines


def _collect_source_ids(facts: list[Fact], procedures: list[Procedure], episodes: list[Episode]) -> list[int]:
    ids: list[int] = []
    for fact in facts:
        ids.extend(fact.evidence_ids)
    for procedure in procedures:
        ids.extend(procedure.evidence_ids)
    for episode in episodes:
        ids.extend(episode.source_ids)
    return _unique_sorted(ids)


def _unique_sorted(values: Iterable[int]) -> list[int]:
    return sorted({value for value in values})


def _excerpt(content: str) -> str:
    collapsed = " ".join(content.split())
    if len(collapsed) <= EXCERPT_MAX_CHARS:
        return collapsed
    return f"{collapsed[: EXCERPT_MAX_CHARS - 1].rstrip()}…"


def _format_metadata(metadata: dict[str, object]) -> str:
    if not metadata:
        return "none"
    return ", ".join(f"{key}={metadata[key]}" for key in sorted(metadata))


def _format_ids(values: list[int]) -> str:
    if not values:
        return "none"
    return ", ".join(str(value) for value in values)


def _format_strings(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)
