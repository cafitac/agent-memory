# KB M1+ Source-Aware Export Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Upgrade `agent-memory kb export` from approved-memory markdown dumping to source-aware KB draft export with stable automation-friendly JSON summary.

**Architecture:** Keep SQLite as the source of truth and markdown as a derived human-review artifact. Reuse existing `SourceRecord` storage and `get_source_records_by_ids` rather than adding schema. Add typed export provenance models, render source metadata/excerpts in markdown, and include counts/source IDs in the CLI JSON result.

**Tech Stack:** Python 3.10+, Pydantic models, SQLite storage helpers, argparse CLI, pytest, `uv run`.

---

## Scope

In scope:
- Export approved facts/procedures/episodes with readable source details.
- Render deterministic source sections containing source id, type, created_at, adapter/external_ref if present, selected metadata, and an excerpt.
- Add stable JSON fields for export automation: per-file counts, total item counts, and source IDs used by the export.
- Preserve existing approved-only and scope-filter behavior.
- Update README only with verified user-facing behavior.

Out of scope:
- LLM extraction from sources.
- Web UI or graph visualization.
- Embeddings/reranking.
- Markdown import/sync back into SQLite.
- Any Hermes hook behavior change.

## Acceptance Criteria

- `agent-memory kb export <db> <dir> --scope <scope>` writes `index.md`, `facts.md`, `procedures.md`, and `episodes.md`.
- Markdown includes source details for every referenced source record that exists.
- Missing source IDs are rendered as IDs but do not crash export.
- JSON output includes a stable `counts` object and `source_ids` list.
- Candidate/disputed/deprecated memories remain excluded.
- Existing tests plus new source-aware tests pass.
- README describes the source-aware export behavior.

---

### Task 1: Add failing tests for source-aware fact export

**Objective:** Prove that fact exports include source metadata and excerpts, not only numeric evidence IDs.

**Files:**
- Modify: `tests/test_kb_export.py`
- Exercise: `src/agent_memory/core/kb_export.py`

**Steps:**
1. Add a test that ingests a source with `source_type`, `adapter`, `external_ref`, and metadata.
2. Create and approve a fact with that source ID.
3. Export the scoped KB.
4. Assert `facts.md` contains:
   - `### Sources`
   - source id/type
   - adapter and external_ref
   - metadata key/value
   - a content excerpt
5. Run `uv run pytest tests/test_kb_export.py::test_export_kb_markdown_includes_source_details_for_facts -q`.
6. Expected RED: fail because only evidence source IDs are currently rendered.

### Task 2: Add failing tests for procedures, episodes, missing sources, and JSON schema

**Objective:** Lock down source rendering across all memory types and the CLI result shape.

**Files:**
- Modify: `tests/test_kb_export.py`
- Exercise: `src/agent_memory/core/models.py`, `src/agent_memory/core/kb_export.py`, `src/agent_memory/api/cli.py`

**Steps:**
1. Add procedure/episode export assertions for source sections.
2. Add a test with a referenced missing source ID and assert export succeeds and labels it missing.
3. Extend CLI vertical-slice test to assert JSON has:
   - `counts.facts`
   - `counts.procedures`
   - `counts.episodes`
   - `counts.total_items`
   - `source_ids`
4. Run targeted tests.
5. Expected RED: fail because `counts`, `source_ids`, and source sections are not implemented.

### Task 3: Add typed models for source-aware export summary

**Objective:** Keep output typed with Pydantic instead of ad-hoc dicts.

**Files:**
- Modify: `src/agent_memory/core/models.py`

**Steps:**
1. Add `KbExportCounts` with `facts`, `procedures`, `episodes`, and `total_items`.
2. Add `source_ids: list[int]` to `KbExportResult`.
3. Add `counts: KbExportCounts` to `KbExportResult` with default factory.
4. Run focused model/import tests through `uv run pytest tests/test_kb_export.py -q`.

### Task 4: Implement source collection and markdown rendering

**Objective:** Render readable provenance while preserving deterministic output.

**Files:**
- Modify: `src/agent_memory/core/kb_export.py`
- Use: `get_source_records_by_ids` from `src/agent_memory/storage/sqlite.py`

**Steps:**
1. Collect all evidence/source IDs from approved facts, procedures, and episodes after scope filtering.
2. Fetch source records once with `get_source_records_by_ids`.
3. Build a `dict[int, SourceRecord]` for rendering.
4. Render source blocks under each memory item:
   - existing numeric IDs remain visible
   - source details appear in `### Sources`
   - missing IDs appear as `Source <id>: missing`
5. Truncate excerpts to a small deterministic length, e.g. 240 chars.
6. Sort metadata keys for deterministic markdown.
7. Return `KbExportResult(counts=..., source_ids=...)`.
8. Run targeted tests and iterate until green.

### Task 5: Update CLI docs and README after behavior is verified

**Objective:** Promote only verified user-facing behavior into public docs.

**Files:**
- Modify: `README.md`
- Modify: `.dev/status/current-handoff.md`
- Maybe modify: `.dev/kb/kb-m1-current-audit.md`

**Steps:**
1. Update README KB export paragraph to mention source metadata/excerpts and JSON summary.
2. Update handoff/current audit with KB M1+ status and next candidates.
3. Avoid local usernames, real credentials, or private paths.

### Task 6: Final verification, commit, push, CI

**Objective:** Ship a clean commit with verified behavior.

**Commands:**
```bash
uv run pytest tests/test_kb_export.py -q
uv run pytest -q
uv run agent-memory kb export --help
git status -sb
git diff --stat
git add README.md .dev/kb .dev/status src/agent_memory/core/models.py src/agent_memory/core/kb_export.py tests/test_kb_export.py
git commit -m "feat: enrich KB export provenance"
git push origin main
gh run list --branch main --limit 3
gh run watch <run-id> --exit-status
```

Expected:
- focused and full tests pass
- CLI help works
- working tree clean after push
- main CI succeeds
