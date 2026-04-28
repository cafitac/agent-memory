from __future__ import annotations

from pathlib import Path

from agent_memory.core.models import Episode, Fact, KbExportedFile, KbExportResult, Procedure
from agent_memory.storage.sqlite import list_approved_episodes, list_approved_facts, list_approved_procedures


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

    written_files = [
        _write_file(output_path / "index.md", "index", _render_index(scope, facts, procedures, episodes), 0),
        _write_file(output_path / "facts.md", "fact", _render_facts(facts), len(facts)),
        _write_file(output_path / "procedures.md", "procedure", _render_procedures(procedures), len(procedures)),
        _write_file(output_path / "episodes.md", "episode", _render_episodes(episodes), len(episodes)),
    ]
    return KbExportResult(output_dir=str(output_path), scope=scope, files=written_files)


def _write_file(path: Path, memory_type: str, content: str, item_count: int) -> KbExportedFile:
    path.write_text(content, encoding="utf-8")
    return KbExportedFile(path=str(path), memory_type=memory_type, item_count=item_count)


def _render_index(scope: str | None, facts: list[Fact], procedures: list[Procedure], episodes: list[Episode]) -> str:
    title = "# Agent Memory KB Export"
    scope_line = f"Scope: {scope}" if scope is not None else "Scope: all"
    return "\n".join(
        [
            title,
            "",
            scope_line,
            "",
            "## Files",
            "",
            f"- [Facts](facts.md): {len(facts)}",
            f"- [Procedures](procedures.md): {len(procedures)}",
            f"- [Episodes](episodes.md): {len(episodes)}",
            "",
        ]
    )


def _render_facts(facts: list[Fact]) -> str:
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
    return "\n".join(lines)


def _render_procedures(procedures: list[Procedure]) -> str:
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
    return "\n".join(lines)


def _render_episodes(episodes: list[Episode]) -> str:
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
    return "\n".join(lines)


def _format_ids(values: list[int]) -> str:
    if not values:
        return "none"
    return ", ".join(str(value) for value in values)


def _format_strings(values: list[str]) -> str:
    if not values:
        return "none"
    return ", ".join(values)
