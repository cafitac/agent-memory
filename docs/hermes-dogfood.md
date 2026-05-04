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
agent-memory activations summary ~/.agent-memory/memory.db --limit 200 --top 20 --frequent-threshold 3
agent-memory activations reinforcement-report ~/.agent-memory/memory.db --limit 200 --top 20 --frequent-threshold 3
agent-memory activations decay-risk-report ~/.agent-memory/memory.db --limit 200 --top 20 --frequent-threshold 3
agent-memory consolidation candidates ~/.agent-memory/memory.db --limit 200 --top 20 --min-evidence 2
agent-memory consolidation explain ~/.agent-memory/memory.db <candidate-id> --limit 200 --min-evidence 2
agent-memory consolidation promote fact ~/.agent-memory/memory.db <candidate-id> \
  --subject-ref "agent-memory" \
  --predicate "prefers" \
  --object-ref-or-value "explicit human-reviewed promotion" \
  --scope project:agent-memory
agent-memory consolidation promotions report ~/.agent-memory/memory.db --limit 50
agent-memory dogfood baseline ~/.agent-memory/memory.db --output-json
agent-memory dogfood remember-intent ~/.agent-memory/memory.db --limit 200 --sample-limit 10
agent-memory traces record ~/.agent-memory/memory.db --surface cli --event-kind user_correction --summary "sanitized trace summary" --scope project:agent-memory
agent-memory traces list ~/.agent-memory/memory.db --surface cli --limit 20
agent-memory traces retention-report ~/.agent-memory/memory.db --max-trace-count 10000
```

Use this before tuning ranking or adding broader graph traversal: first confirm which memories are frequently injected, which scopes are active, whether retrieval is often empty, and whether any frequently injected refs are now deprecated/disputed/missing. The audit command is read-only and summarizes local observation rows without emitting raw query text or query previews. Keep this data local unless you intentionally export it.

`dogfood baseline` is the preferred one-command snapshot before trace/consolidation work. It is read-only JSON that includes the package version, DB path/schema metadata, memory status counts, observation audit, empty diagnostics, signal-bearing review candidates, sanitized Hermes doctor metadata, and a local E2E marker set to `not_executed`. It intentionally does not include raw queries, query previews, prompt text, full Hermes config, environment secrets, or the bootstrap command.

Stage B trace work includes a manual CLI for explicit local dogfood plus a Hermes hook opt-in for real turns. `experience_traces` is a local substrate for bounded event fingerprints and sanitized summaries/signals; `traces record` writes only when invoked explicitly, and `traces list` emits read-only filtered JSON. Hermes does not write traces by default. To enable real-turn trace rows, add `--record-trace` to `agent-memory hermes-pre-llm-hook ...` or render/install the hook with `--record-trace`. Hook traces store a content hash, hashed session ref, safe metadata such as platform/model, and related retrieved memory refs; they do not store raw prompts/user messages/query previews, skip synthetic doctor/test payloads, and are non-blocking if trace persistence fails. Traces are not queried by default retrieval and are not injected into prompts. Use `traces retention-report` to audit trace volume, expired refs, and expirable rows missing `expires_at`; it is read-only and intentionally omits trace metadata and summary text.

For Stage G/G1 dogfood, explicit `Remember this:` / `Please remember:` turns become `remember_intent` review traces only when hook trace recording is already opt-in enabled and the message passes the conservative secret-like scan. These rows carry sanitized summaries, `retention_policy=review`, high salience/user emphasis, and metadata showing review is required and auto-approval is false. They are reviewable through the existing read-only consolidation candidate/explain commands; they do not create approved long-term memories.

`dogfood remember-intent` is the read-only G1 quality gate before any G2 auto-approval policy. It counts inspected `remember_intent` and ordinary turn traces, reports review-ready counts, scope distribution, safe samples, and unsafe sample counts. It intentionally omits raw trace metadata, raw prompts, and secret-like summaries; it does not mutate traces, memory records, relations, counters, retrieval ranking, or Hermes hook behavior.

Stage C starts with an internal `memory_activations` substrate. Retrieval observations now bridge into activation events without changing ranking: selected memory refs create `retrieved` events and empty retrievals create `empty_retrieval` negative evidence. Activation rows are local-only and secret-safe: memory refs, observation ids, scope, strength, and sanitized metadata only; no raw queries, prompts, query previews, transcripts, automatic long-term promotion, or prompt injection changes.

`activations summary` is the first read-only Stage C dogfood report for this substrate. It summarizes activation counts, activation windows, surfaces/scopes, status counts for top refs, empty-retrieval evidence, and top refs with advisory signals such as `frequently_activated`, `likely_reinforcement_candidate`, `current_status_not_approved`, or `deprecated_activation`. Use it before reinforcement/decay scoring; it does not mutate memory status and does not affect ranking.

`activations reinforcement-report` is the next read-only Stage C report. It scores memory refs with an explicit factor breakdown for repetition, strength, status trust, surface/scope diversity, and graph connectivity, then applies visible penalties for deprecated/disputed/missing refs and supersession/replacement relations. The score is bounded, deterministic, and advisory only; it does not mutate memory status, promote memories, or change ranking.

`activations decay-risk-report` is the paired advisory view for weak activation evidence. It scores low repetition, weak strength, stale activity, low connectivity, and lifecycle status risk, but caps risk for approved/frequently activated/connected refs so "old" is not treated as automatically useless. It suggests review/explanation follow-up only; it does not delete traces, deprecate memories, mutate status, or change ranking.

`consolidation candidates` starts Stage D as a read-only dogfood report over sanitized traces. It groups `experience_traces` with deterministic cluster keys, reports candidate fingerprints, evidence windows, surfaces/scopes, safe summaries, related memory/observation refs, activation/status reinforcement context, guessed memory type, and risk flags. It is an advisory review queue only: no raw prompts/queries/transcripts, no automatic long-term memory creation, no approval, no reject/snooze state yet, and no ranking change.

`consolidation explain` expands a single candidate id into a read-only explanation packet for local review. It answers why the candidate was grouped, which safe traces/activations/status signals support it, why the memory type was guessed, and which risk flags or review guardrails apply. Unknown candidate ids produce JSON with `found: false` plus a non-zero exit. The command remains local-only and advisory: it does not promote, approve, reject, snooze, mutate status, delete traces, change ranking, or print raw prompts/queries/transcripts/query previews.

`consolidation promote fact` is the first mutating Stage E command and should be used only after a human reviews `consolidation explain`. The reviewer supplies the final semantic fact fields; the candidate contributes only safe provenance. Before it creates provenance sources, facts, status transitions, or lineage edges, the command runs a read-only conflict preflight against existing facts with the same `subject_ref` + `predicate` + `scope`. Different object values in approved/candidate/disputed/deprecated facts block promotion with `error: conflict_preflight_required`, `read_only: true`, status counts, safe conflicting fact summaries, and copy-paste `review explain`, `review replacements`, and `graph inspect` commands. Add `--allow-conflict` only after a human accepts that both claims should coexist. Default successful output is a `candidate` fact hidden from default retrieval. Add `--approve --actor ... --reason ...` only when approval is explicit; that path logs the candidate-to-approved transition with the generated provenance source id. Successful promotion also writes graph lineage relations: `candidate-id --promoted_to--> fact:<id>` and `fact:<id> --has_promotion_provenance--> source_record:<id>`, letting `graph inspect ~/.agent-memory/memory.db <candidate-id> --depth 2` explain the candidate/provenance path. Unknown candidate ids are safe failures that do not create facts, sources, or lineage edges. Procedure/preference promotion remains out of scope for this slice.

`consolidation promotions report` is the paired read-only audit surface for Stage E manual promotions. It lists promoted fact ids/statuses, candidate fingerprints, safe provenance summaries, trace/observation ids, approval history, and lineage refs so local dogfood can review what was promoted without touching retrieval ranking or mutating facts, sources, relations, transitions, traces, approval queues, or reject/snooze state. It does not print raw prompts, transcripts, query previews, or raw trace metadata.

`review relate-conflict fact` is the explicit human-reviewed follow-up for accepted E4 conflicts. It records a `conflicts_with` graph relation only for same-claim-slot facts with different object values, requires `--actor` and `--reason`, stores review metadata on the relation, and does not mutate either fact's status or default retrieval ranking. Use it after `consolidation promote fact --allow-conflict` only when a reviewer intentionally keeps both claims during migration or split-environment rollout. `review conflicts fact` now includes these relation refs in its otherwise read-only same-slot report. `review supersede fact` replacement edges use the same relation review metadata columns.


`retrieval policy-preview` is the first Stage F read-only lifecycle policy surface. It runs the existing approved-only retrieval path with `record_retrievals=false`, then explains what a conservative lifecycle-aware policy would do with each returned memory. The report includes score components, retrieval/reinforcement counts, same-claim-slot conflict counts, reviewed `conflicts_with` relations, supersession/replacement chains, and copy-paste review/graph inspection commands. It emits `read_only: true`, `mutated: false`, and `default_retrieval_unchanged: true`; it never stores the raw query or a query preview, and it does not alter Hermes hook behavior.

```bash
agent-memory retrieval policy-preview "$DB" "What memory would Hermes use here?" --preferred-scope user:default --limit 5
```

Use this before any opt-in ranker or prompt-time hiding experiment. A `flag_for_review` decision is an advisory signal, not an automatic cleanup instruction.

`retrieval ranker-preview` is the opt-in reinforcement-aware follow-up. It runs the same approved-only retrieval path with `record_retrievals=false`, then computes a preview-only reinforcement delta so operators can compare baseline rank and preview rank before changing any runtime behavior.

```bash
agent-memory retrieval ranker-preview "$DB" "What memory would Hermes use here?" --preferred-scope user:default --limit 5 --reinforcement-weight 0.15
```

`retrieval decay-preview` is the opt-in decay-risk follow-up. It runs the same approved-only retrieval path with `record_retrievals=false`, then computes a preview-only prompt-time noise penalty from activation decay risk. It reports baseline rank, preview rank, decay penalty, lifecycle exclusion reasons, and decay-risk factors while keeping default retrieval and Hermes hooks unchanged.

```bash
agent-memory retrieval decay-preview "$DB" "What memory would Hermes use here?" --preferred-scope user:default --limit 5 --decay-weight 0.2 --frequent-threshold 3
```

`retrieval graph-neighborhood-preview` is the bounded graph reinforcement follow-up. It walks relation edges from each retrieved memory only up to `--depth`, reports relation ids and neighbor refs used for the preview score, and keeps the graph delta capped so graph connectivity cannot become graph-only search. It is read-only and keeps default retrieval/Hermes hooks unchanged.

```bash
agent-memory retrieval graph-neighborhood-preview "$DB" "What memory would Hermes use here?" --preferred-scope user:default --limit 5 --depth 1 --graph-weight 0.15
```

Use this after `activations decay-risk-report` and before any runtime prompt-filtering change. A high decay penalty is an evaluation signal, not an automatic deprecation/delete instruction.

The output emits `kind: retrieval_ranker_preview`, `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, sanitized candidates, and `rank_changes`. It does not store the query, print `query_preview`, record retrieval observations, increment memory counters, or change Hermes prompt injection.

When `empty_retrieval_ratio` is high, run `observations empty-diagnostics` before changing rankers. It is a read-only, secret-safe segment report for empty observations. It groups empty-heavy rows by surface, preferred scope, and status filter; includes each segment's total count, empty count, empty ratio, sample observation ids, and observation window; and suggests operator checks such as scope mismatch review or adding/approving durable memories only after confirming the misses are real user needs.

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
agent-memory dogfood baseline ~/.agent-memory/memory.db --output-json
agent-memory dogfood remember-intent ~/.agent-memory/memory.db --limit 200 --sample-limit 10
hermes hooks doctor
```

Then run one real Hermes prompt with the conservative hook and record latency/fallback notes in the PR or release checklist.
