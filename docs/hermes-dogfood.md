# Hermes dogfood and operations guide

Use this dogfood checklist before claiming the Hermes integration is safe for always-on use.

## Baseline dogfood smoke

Run from a normal user shell, not the source checkout:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

Then start a real Hermes session and ask one prompt that should retrieve a small approved memory. If your local Hermes policy requires hook confirmation, approve the shell hook or run Hermes with your normal hook-acceptance flow.

## Conservative preset expectation

The default hook is `--preset conservative`. The generated command should include small explicit budgets such as:

```bash
agent-memory hermes-pre-llm-hook ~/.agent-memory/memory.db --top-k 1 --max-prompt-lines 6 --max-prompt-chars 800 --max-prompt-tokens 200 --max-verification-steps 1 --max-alternatives 0 --max-guidelines 1 --no-reason-codes
```

Use `--preset balanced` only when deliberately dogfooding richer context. Balanced is useful for debugging retrieval quality, but it can add more prompt text, reason codes, and alternative memory detail.

## What to observe

Capture these observations for each dogfood run:

- `agent-memory doctor` JSON status
- `hermes hooks doctor` output
- whether the first real prompt required hook approval
- prompt latency before and after the hook is installed
- whether returned context includes only approved memory
- whether unrelated scopes stay out of the prompt
- whether failure paths fail closed with no broken prompt text
- whether `agent-memory observations list ~/.agent-memory/memory.db --limit 20` shows the expected memory refs without raw query text, query previews, or secrets
- whether `agent-memory observations audit ~/.agent-memory/memory.db --limit 200 --top 10` highlights frequently injected or no-longer-approved refs, low observation counts, and high empty-retrieval ratios before any retrieval tuning

A good conservative smoke has low latency, at most one surfaced memory, no noisy reason codes, no workflow-blocking error if the memory DB is missing, and a local observation entry that explains what memory was injected.

## Local observation log

Hermes pre-LLM hook retrievals write a secret-safe local observation row to the SQLite DB for real turns. The row is intended for dogfood/noise review and stores the surface, query hash, selected memory refs, top memory ref, response mode, scope, and small metadata. It does not store the raw query text or a query preview. `hermes hooks doctor` / `hermes hooks test pre_llm_call` still exercise hook context injection, but their deterministic synthetic weather payload is skipped as dogfood observation data.

```bash
agent-memory observations list ~/.agent-memory/memory.db --limit 20
agent-memory observations audit ~/.agent-memory/memory.db --limit 200 --top 10 --frequent-threshold 3
agent-memory observations empty-diagnostics ~/.agent-memory/memory.db --limit 200 --top 10 --high-empty-threshold 0.5
agent-memory observations review-candidates ~/.agent-memory/memory.db --limit 200 --top 10 --frequent-threshold 3
```

Use this before tuning ranking or adding broader graph traversal: first confirm which memories are frequently injected, which scopes are active, whether retrieval is often empty, and whether any frequently injected refs are now deprecated/disputed/missing. The audit command is read-only and summarizes local observation rows without emitting raw query text or query previews. Keep this data local unless you intentionally export it.

When `empty_retrieval_ratio` is high, run `observations empty-diagnostics` before changing rankers. It is a read-only, secret-safe segment report for empty observations. It groups empty-heavy rows by surface, preferred scope, and status filter; includes each segment's total count, empty count, empty ratio, sample observation ids, and observation window; and suggests operator checks such as scope mismatch review or adding/approving durable memories only after confirming the misses are real user needs. It does not emit raw query text, query previews, or prompt content.

`observations review-candidates` is the next read-only step after audit. It keeps the same secret-safe observation summary, then expands each top ref into a forensic candidate:

- fact refs include the same lifecycle explanation as `agent-memory review explain fact ...`.
- replacement/supersedes chains are surfaced as candidate signals instead of mutating anything.
- relation graph neighbors are summarized so you know when `agent-memory graph inspect ...` is worth running.
- the JSON includes `observation_count`/`candidate_count`, each ref's observation window, and copy-paste follow-up commands for `review explain`, `review replacements`, and `graph inspect`.
- fact refs include a `status_history_summary` so historical injections that were later deprecated/superseded are easier to distinguish from currently approved frequent memories.

Do not treat review candidates as automatic cleanup recommendations. They are a short list for human review; approve/deprecate/supersede decisions should still be explicit curation actions.

When the audit reports `quality_warnings`, treat them as QA signals rather than cleanup instructions:

- `no_observations`: Hermes has not produced dogfood observation data yet; check hook install/allowlist and run a real prompt.
- `low_observation_count`: keep dogfooding before drawing ranking conclusions.
- `high_empty_retrieval_ratio`: memory retrieval is often returning no approved refs; check scopes, approved memory coverage, and query wording before changing rankers.

## Fallback and rollback

The hook should fail closed. If retrieval fails, Hermes should continue without memory context rather than blocking the user workflow.

Rollback options:

1. Edit `~/.hermes/config.yaml` and remove the `agent-memory hermes-pre-llm-hook ...` command from `hooks.pre_llm_call`.
2. Restore the `*.agent-memory.bak` file created by bootstrap if you want the exact pre-bootstrap config.
3. Keep `~/.agent-memory/memory.db` if you only want to disable the hook; delete it only if you want to remove local memory data.

## Release dogfood gate

Before a release that changes Hermes behavior, run:

```bash
agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db --preset conservative
agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db --preset balanced
agent-memory doctor
hermes hooks doctor
```

Then run one real Hermes prompt with the conservative hook and record latency/fallback notes in the PR or release checklist.
