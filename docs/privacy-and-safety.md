# Privacy and safety model

agent-memory is local-first, but local memory can still be sensitive. This page describes the stable default behavior, what is experimental or opt-in, and what operators should back up or avoid sharing.

## Stable defaults

The current stable public surfaces are conservative:

- The memory database is a local SQLite file, normally `~/.agent-memory/memory.db`.
- Normal retrieval and prompt context use approved memories only.
- Candidate, disputed, and deprecated memories are excluded from normal prompt context unless an operator intentionally asks for a forensic view such as `retrieve --status all`.
- Hermes prompt injection is bounded by small prompt budgets and fails closed: if the DB or retrieval path is unavailable, the hook should return no memory context instead of blocking the host agent.
- Retrieval observations, activation rows, and ordinary Hermes traces are designed to be secret-safe metadata. They use hashes, refs, scopes, counts, and sanitized metadata rather than raw prompts or transcript text.
- Graph and dogfood reports are local diagnostic artifacts. They should be treated as private unless you intentionally publish or share them.

## Data that can contain private information

Treat these as private local data:

- `~/.agent-memory/memory.db`
- backup bundles created by `agent-memory backup export`
- restored or copied SQLite databases
- local graph exports when `--include-memory-labels` is used
- local reports under paths such as `~/.agent-memory/reports/`

A backup bundle contains a metadata-only `manifest.json` plus a SQLite database copy. `backup inspect` prints manifest and table-count metadata without raw content, but the bundled database itself still contains local memory state.

## Backup and restore

Use backup commands before risky local operations or when moving memory between machines:

```bash
DB=~/.agent-memory/memory.db
agent-memory backup export "$DB" ~/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup inspect ~/.agent-memory/backups/memory.agent-memory-backup.zip
agent-memory backup restore ~/.agent-memory/backups/memory.agent-memory-backup.zip ~/.agent-memory/restored-memory.db
```

Restore refuses unsupported backup format versions, unsafe database entry names, and existing output databases unless `--overwrite` is explicit.

## Stable read-only diagnostics

These diagnostics are intended to be safe to run on a local DB because they do not mutate memory state or change default retrieval behavior:

```bash
agent-memory observations audit "$DB" --limit 200 --top 10
agent-memory activations summary "$DB" --limit 200 --top 20
agent-memory traces retention-report "$DB" --max-trace-count 10000
agent-memory retrieval policy-preview "$DB" "example query" --limit 5
agent-memory graph export-html "$DB" --output ~/.agent-memory/reports/memory-graph.html --limit 200
agent-memory dogfood scheduled-dry-run "$DB" --output ~/.agent-memory/reports/scheduled-dry-run.json --since-hours 24
```

Read-only diagnostics should report fields such as `read_only: true`, `mutated: false`, or `default_retrieval_unchanged: true` when those fields apply.

## Experimental or opt-in surfaces

The consolidation and dogfood layers are for local operators and maintainers. They should not be described as broad automatic memory saving.

Current guardrails:

- No raw transcript archive is enabled as a default storage layer.
- Ordinary conversation is not automatically approved as durable long-term memory.
- Default retrieval ranking is not changed by the preview, graph, dogfood, or scheduled-dry-run reports.
- Mutating cleanup commands require explicit flags such as `--apply`, plus audit metadata such as `--actor` and `--reason`.
- The narrow `remember-preferences-v1` auto-approval policy is default-off, scope-bound, conflict-checked, and limited to explicit low-risk preference summaries.
- Broader G4 background apply mode is not stable public behavior yet.

## Sharing guidance

Before sharing an artifact publicly:

1. Prefer command output from `backup inspect`, `dogfood ...` summaries, or release smoke JSON over raw DB files.
2. Do not share backup bundles, copied SQLite DBs, or graph exports with labels unless you have reviewed the contents.
3. Check for raw prompts, transcript text, query previews, API keys, tokens, passwords, connection strings, and secret-like values.
4. When in doubt, share aggregate counts, hashes, refs, command versions, and status fields rather than artifact bodies.
