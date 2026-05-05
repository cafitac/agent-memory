# agent-memory

[![CI](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml/badge.svg)](https://github.com/cafitac/agent-memory/actions/workflows/ci.yml)
[![npm](https://img.shields.io/npm/v/@cafitac/agent-memory.svg)](https://www.npmjs.com/package/@cafitac/agent-memory)
[![PyPI](https://img.shields.io/pypi/v/cafitac-agent-memory.svg)](https://pypi.org/project/cafitac-agent-memory/)
[![Python](https://img.shields.io/pypi/pyversions/cafitac-agent-memory.svg)](https://pypi.org/project/cafitac-agent-memory/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Local-first memory for AI agents.

agent-memory gives Hermes, Codex-style CLIs, Claude-style CLIs, and custom agent harnesses a shared SQLite memory runtime with curation, provenance, retrieval, prompt rendering, and regression evaluation.

It is intentionally small and local-first: your memory database lives on your machine unless you choose to sync or copy it elsewhere.

## Why use it?

Most agent memory systems end up as raw logs, ad-hoc notes, or one-shot RAG. agent-memory separates durable knowledge into semantic facts, procedures, episodes, source records, scopes, and lifecycle states so an agent can remember useful context without blindly stuffing every transcript into future prompts.

Use it when you want:

- one user-level memory store shared across multiple agent harnesses
- local SQLite storage instead of a hosted memory service
- approved-only prompt context by default
- candidate/disputed/deprecated memory review flows
- source/provenance metadata for every curated memory
- bounded prompt rendering for Hermes/Codex/Claude wrappers
- retrieval regression fixtures with lexical/source baselines and failure triage

Docs for first-run and operational validation:

- [First-run memory layer setup](docs/first-run-memory-layer.md)
- [Hermes dogfood and operations guide](docs/hermes-dogfood.md)
- [Install smoke recipes](docs/install-smoke.md)

## 30-second install

Recommended path for CLI agent users:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

What this does:

- installs the `agent-memory` command
- initializes `~/.agent-memory/memory.db` when missing
- creates or merges the Hermes hook config at `~/.hermes/config.yaml`
- preserves existing Hermes hooks and appends the agent-memory pre-LLM hook
- lets you verify setup with `agent-memory doctor`

Python-first alternatives:

```bash
pipx install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
```

```bash
uv tool install cafitac-agent-memory
agent-memory bootstrap
agent-memory doctor
```

## First memory in 60 seconds

```bash
DB=~/.agent-memory/memory.db

agent-memory init "$DB"
agent-memory create-fact "$DB" "agent-memory" "primary-install-path" "npm install -g @cafitac/agent-memory" "user:default"
agent-memory approve-fact "$DB" 1
agent-memory retrieve "$DB" "How should I install agent-memory?" --preferred-scope user:default
```

Normal retrieval is approved-only by default. Candidate, disputed, and deprecated memories stay out of prompt context unless you intentionally ask for a forensic view:

```bash
agent-memory retrieve "$DB" "What obsolete install notes exist?" --status all
agent-memory review conflicts fact "$DB" "agent-memory" "primary-install-path"
```

Review transitions can carry operator context and remain inspectable later. If one fact replaces another, record the replacement chain so stale facts can be explained without entering normal retrieval. If a reviewer intentionally accepts two contradictory same-claim facts as coexisting during migration, record a conflict relation without changing either fact's status:

```bash
agent-memory review approve fact "$DB" 1 --reason "Verified from current setup guide." --actor maintainer --evidence-ids-json '[1]'
agent-memory review history fact "$DB" 1
agent-memory review supersede fact "$DB" 1 2 --reason "Newer source replaces the old install path." --actor maintainer --evidence-ids-json '[2]'
agent-memory review replacements fact "$DB" 1
agent-memory review relate-conflict fact "$DB" 1 3 --reason "Human accepted temporary coexistence while rollout differs by environment." --actor maintainer --evidence-ids-json '[3]'
agent-memory review conflicts fact "$DB" "agent-memory" "primary-install-path"
agent-memory review explain fact "$DB" 1
```

`review explain` combines the current status, default retrieval visibility, transition history, same claim-slot alternatives, and replacement chain into one decision context so a reviewer can see why a stale or conflicting fact is hidden.

For read-only relation graph inspection, use `graph inspect`. This is an operator/debug view over stored `Relation` edges; it does not change retrieval behavior or mutate memory state:

```bash
agent-memory graph inspect "$DB" fact:1 --depth 1
agent-memory graph inspect "$DB" fact:1 --depth 2 --limit 50
```

The JSON output includes the start ref, visited node refs, relation edges, traversal depth per edge, and a `read_only: true` marker. It is intended as a safe graph-foundation slice before enabling any broader graph traversal in default retrieval.

For local dogfood and noise monitoring, retrievals can leave a secret-safe observation log. Normal `retrieve` only records an observation when explicitly asked; the Hermes pre-LLM hook records one automatically in the local SQLite DB for real turns. Observations store a query hash, selected memory refs, top memory ref, response mode, scope, and surface. They do not store the raw query text or a query preview. Deterministic `hermes hooks doctor/test` pre-LLM payloads exercise context injection but are skipped as dogfood observations so synthetic weather prompts do not pollute the audit.

```bash
agent-memory retrieve "$DB" "How should I install agent-memory?" --preferred-scope user:default --observe cli
agent-memory observations list "$DB" --limit 20
agent-memory observations audit "$DB" --limit 200 --top 10 --frequent-threshold 3
agent-memory observations empty-diagnostics "$DB" --limit 200 --top 10 --high-empty-threshold 0.5
agent-memory observations review-candidates "$DB" --limit 200 --top 10 --frequent-threshold 3
agent-memory activations summary "$DB" --limit 200 --top 20 --frequent-threshold 3
agent-memory activations reinforcement-report "$DB" --limit 200 --top 20 --frequent-threshold 3
agent-memory activations decay-risk-report "$DB" --limit 200 --top 20 --frequent-threshold 3
agent-memory consolidation candidates "$DB" --limit 200 --top 20 --min-evidence 2
agent-memory consolidation background dry-run "$DB" --limit 200 --top 20 --min-evidence 2 --output ~/.agent-memory/reports/background-consolidation.json
agent-memory dogfood background-dry-run "$DB" --report ~/.agent-memory/reports/background-consolidation.json --candidate-min 1 --max-decay-risk 0
agent-memory dogfood storage-health "$DB" --hermes-config ~/.hermes/config.yaml
agent-memory dogfood trace-quality "$DB" --since-hours 24 --min-trace-coverage 0.25 --min-evidence-count 2
agent-memory consolidation explain "$DB" <candidate-id> --limit 200 --min-evidence 2
agent-memory consolidation promote fact "$DB" <candidate-id> \
  --subject-ref "agent-memory" \
  --predicate "prefers" \
  --object-ref-or-value "explicit human-reviewed promotion" \
  --scope project:agent-memory
agent-memory consolidation promotions report "$DB" --limit 50
agent-memory dogfood baseline "$DB" --output-json
agent-memory traces record "$DB" --surface cli --event-kind user_correction --summary "sanitized trace summary" --scope project:agent-memory
agent-memory traces list "$DB" --surface cli --limit 20
agent-memory traces retention-report "$DB" --max-trace-count 10000
```


Before changing retrieval behavior, preview lifecycle policy effects with the Stage F read-only report:

```bash
agent-memory retrieval policy-preview "$DB" "How should I install agent-memory?" --preferred-scope user:default --limit 5
agent-memory retrieval ranker-preview "$DB" "How should I install agent-memory?" --preferred-scope user:default --limit 5 --reinforcement-weight 0.15
agent-memory retrieval decay-preview "$DB" "How should I install agent-memory?" --preferred-scope user:default --limit 5 --decay-weight 0.2 --frequent-threshold 3
agent-memory retrieval graph-neighborhood-preview "$DB" "How should I install agent-memory?" --preferred-scope user:default --limit 5 --depth 1 --graph-weight 0.15
```

`policy-preview` reuses the current approved-only retrieval packet but never records retrieval observations, increments retrieval counters, or mutates facts/relations. Its JSON output includes `read_only: true`, `mutated: false`, `default_retrieval_unchanged: true`, a non-stored query hash marker, per-memory score components, activation/retrieval counts, same-claim-slot conflict signals, reviewed `conflicts_with` relation coverage, and supersession/replacement policy signals. Use it to see whether a future conservative policy would include, flag, or exclude a returned memory before enabling any opt-in ranker or prompt-time hiding.

`ranker-preview` is the opt-in Stage F reinforcement experiment. It compares the current default retrieval trace against a reinforcement-aware preview score, reports baseline rank, preview rank, reinforcement delta, and rank changes, and remains read-only (`record_retrievals=false`, no observations, no counter increments, no relation/fact mutations). The command does not print or store the raw query or `query_preview`, and it does not change `agent-memory retrieve` or Hermes hook behavior.

`decay-preview` is the paired opt-in prompt-time noise penalty experiment. It reuses the current approved-only retrieval trace without recording retrievals, then subtracts a preview-only decay-risk penalty based on low activation evidence, stale activation windows, low connectivity, and lifecycle status while preserving protections for frequently activated or connected approved memories. Reviewed supersession relations are marked as `exclude` in the preview output, but the command does not mutate status, relations, observations, counters, default ranking, or Hermes hook behavior.

`graph-neighborhood-preview` is the bounded graph-neighborhood reinforcement experiment. It reuses the current approved-only retrieval trace with `record_retrievals=false`, walks relation edges only up to the requested `--depth`, reports the exact relation ids/neighbor refs used, and adds a preview-only capped graph delta plus optional activated-neighbor support. It remains read-only, omits raw query/query-preview/prompt content, and does not change `agent-memory retrieve` or Hermes hook behavior.

Use the observation log and audit report to spot frequently injected or surprising memories before changing retrieval behavior. The audit output is read-only JSON with surface/scope counts, empty-retrieval count and ratio, quality warnings such as `low_observation_count` or `high_empty_retrieval_ratio`, top injected memory refs, current status for known refs, per-ref observation windows, and simple signals such as `frequently_injected` and `current_status_not_approved`. `observations empty-diagnostics` is read-only and focuses specifically on empty retrievals: it groups empty-heavy observations by surface, preferred scope, and status filter with segment ratios, sample observation ids, observation windows, and next-step hints for checking scope mismatches or missing approved memory coverage before changing rankers. `observations review-candidates` is also read-only; it turns the top audit refs into forensic candidates with top-level `observation_count`/`candidate_count`, fact review explanations, status-history summaries, replacement-chain hints, graph-neighborhood summaries, and copy-paste follow-up commands such as `review explain`, `review replacements`, and `graph inspect`.

The next consolidation layer is an experimental trace and activation substrate, not automatic memory creation. `experience_traces` stores low-cost local event traces behind explicit write APIs, the manual `traces record` CLI, and the Hermes pre-LLM hook. For real non-synthetic Hermes turns, the hook now records a default metadata-only `turn` trace: content hash, hashed session ref, safe adapter metadata such as platform/model, related retrieved memory refs, low salience, and ephemeral retention. It intentionally does not store raw prompts, raw queries, query previews, transcripts, user messages, or secret-like content, and it does not change approved-memory retrieval or ranking. Use `--no-record-trace` on `hermes-pre-llm-hook` for a one-off/runtime opt-out. Synthetic `hermes hooks doctor/test` payloads are skipped, and trace write failures are non-blocking. `traces list` is read-only JSON and supports `--surface`, `--event-kind`, and `--scope` filters for local dogfood. `traces retention-report` is also read-only; it summarizes retention-policy counts, expired trace refs, expirable traces missing `expires_at`, and volume warnings without deleting traces, promoting memories, or printing trace metadata/summary text.

Stage G starts cautious automation with explicit remember intent only. User messages that start with `Remember this:`, `Please remember:`, `기억해둬:`, or `기억해줘:` create a high-salience `remember_intent` trace with `retention_policy=review`, a sanitized summary, and metadata marking `candidate_policy=review_required` and `auto_approved=false`. This intentionally keeps a safe, human-readable candidate summary so operators can debug which explicit requests did not become facts; ordinary turns remain hash-only metadata. Secret-like remember requests are recorded only as rejected metadata-only `remember_intent` diagnostics (`candidate_policy=rejected`, `secret_scan=blocked`, `rejected_reason=secret_like_text`) with no summary or raw prompt, so quality reports can count rejection reasons without leaking secrets. No fact/procedure/episode is created or approved automatically. Review still goes through `consolidation candidates`, `consolidation explain`, and explicit human promotion. Before expanding automation, run `agent-memory dogfood remember-intent "$DB" --limit 200 --sample-limit 10` to inspect read-only remember-intent counts, rejection counts, review-ready samples, scope distribution, and unsafe sample counts without printing raw metadata or secret-like summaries, mutating traces/memories, or changing default retrieval.

G2 adds one narrow default-off auto-approval policy for advanced/local operators: explicit review-ready remember traces whose sanitized summary starts with `User prefers ...` or `I prefer ...` can be converted into an approved `user prefers <value>` fact only when you call the policy command with `--apply`, an exact scope, and audit metadata. The default command is a dry-run and reports `would_approve` candidates without mutation:

```bash
agent-memory consolidation auto-approve remember-preferences "$DB" \
  --policy remember-preferences-v1 \
  --scope user:default
```

To actually approve eligible memories, make the opt-in explicit and leave an audit trail:

```bash
agent-memory consolidation auto-approve remember-preferences "$DB" \
  --policy remember-preferences-v1 \
  --scope user:default \
  --apply \
  --actor "reviewer:local" \
  --reason "explicit remember preference reviewed for auto-approval"
```

The policy is intentionally constrained to `fact` memories with predicate `prefers`, runs conflict preflight on the target claim slot before mutation, blocks secret-like summaries, writes normal review/status history through `approve_memory`, and records an `experience_trace:<id> --auto_approved_as--> fact:<id>` graph relation. It does not auto-approve ordinary conversation, procedures, broad inferred preferences, or conflicting claim slots.

G3 dry-run dogfood should stay measurable before any G4 apply-mode plan. After one or more `consolidation background dry-run` JSON files exist, summarize their quality gates with:

```bash
agent-memory dogfood background-dry-run "$DB" \
  --report ~/.agent-memory/reports/background-consolidation.json \
  --candidate-min 1 \
  --max-decay-risk 0
```

The dogfood report is read-only (`kind: background_dry_run_dogfood_report`) and emits only per-report summaries, status counts, aggregate candidate/reinforcement/decay-risk counts, thresholds, and `quality_gate.pass`. It does not include raw report payloads, raw prompts, `raw_prompt`, query text, or `query_preview`, and it does not mutate memory or enable apply mode. A passing gate means only "write a separate G4 plan with RED tests"; failures or warnings mean continue dry-run dogfooding.

G3c adds a read-only storage-health gate for the live dogfood DB:

```bash
agent-memory dogfood storage-health "$DB" --hermes-config ~/.hermes/config.yaml
```

The report emits `kind: dogfood_storage_health`, table counts, latest timestamps, memory status counts, Hermes hook markers, and aggregate invariant checks for non-empty stored query excerpts, query-hash presence, JSON metadata validity, orphan activation links, ordinary metadata-only turn traces, and remember-intent safety shape. It never prints raw queries, query preview values, prompts, transcripts, user messages, secret-like rejected text, or raw metadata payloads, and it opens the DB read-only without mutating facts, traces, activations, observations, ranking, or hook config. Treat warnings as blockers before any G4 apply-mode plan.

If storage-health reports legacy stored query excerpts, preview cleanup scope without mutation or raw-value output before any explicit cleanup apply path exists:

```bash
agent-memory dogfood query-preview-cleanup "$DB" --older-than 2030-01-01T00:00:00
```

The preview emits `kind: dogfood_query_preview_cleanup_preview`, aggregate affected/eligible counts and timestamps, `read_only: true`, `mutated: false`, and a recommended operation marker only. It never prints stored query excerpt samples, raw query values, prompts, transcripts, API keys, or token-like values.

G3d adds a read-only trace-quality gate before any G4 apply-mode plan:

```bash
agent-memory dogfood trace-quality "$DB" --since-hours 24 --min-trace-coverage 0.25 --min-evidence-count 2
```

The report emits `kind: dogfood_trace_quality`, aggregate observation/trace/activation coverage, empty-retrieval ratio, repeated memory-ref counts, trace event-kind and retention-policy distributions, ordinary metadata-only and metadata JSON invariants, candidate-signal proxy counts, and a conservative recommendation (`continue_dogfooding`, `ready_for_more_dry_runs`, or `consider_g4_plan`). It opens SQLite read-only, does not create candidates or approvals, does not change retrieval ranking, and never prints raw conversation text, trace summaries, query values, prompts, transcripts, API keys, or sample values.

Stage C starts with `memory_activations`, a local-only internal substrate that distinguishes "a trace happened" from "a memory was retrieved/activated." Retrieval observations now bridge into activation events: selected memory refs create `retrieved` activations, while empty retrievals create `empty_retrieval` negative evidence. Activation rows store refs, observation links, scope, strength, and sanitized metadata only; they do not store raw queries or prompt previews, and they do not change retrieval ranking or long-term memory status.

`agent-memory activations summary "$DB" --limit 200 --top 20 --frequent-threshold 3` is the first read-only Stage C reporting surface. It summarizes activation counts, activation windows, surfaces/scopes, status counts for top refs, empty-retrieval negative evidence, and top memory refs with advisory signals such as `frequently_activated`, `likely_reinforcement_candidate`, or `current_status_not_approved`. It remains local-only and read-only: no raw queries, no prompt previews, no ranker changes, no memory status mutation, and no automatic long-term promotion.

`agent-memory activations reinforcement-report "$DB" --limit 200 --top 20 --frequent-threshold 3` adds a deterministic read-only score over activation refs. The report explains every candidate score with factor breakdowns for repetition, strength, status trust, surface/scope diversity, and graph connectivity, plus penalties for deprecated/disputed/missing refs and supersession/replacement relations. It is advisory only: it does not change retrieval ranking, memory status, or long-term promotion state.

`agent-memory activations decay-risk-report "$DB" --limit 200 --top 20 --frequent-threshold 3` adds the paired read-only decay-risk view. It flags weak/low-use/low-connectivity/stale activation refs with factor breakdowns, but protects approved, frequently activated, connected refs from naive age-only recommendations. The output suggests review/explanation commands only; it does not delete traces, deprecate memories, alter status, or change retrieval ranking.

`agent-memory consolidation candidates "$DB" --limit 200 --top 20 --min-evidence 2` starts Stage D as a read-only trace clustering diagnostic. It groups sanitized `experience_traces` with deterministic scope/memory/summary keys, emits stable candidate fingerprints, evidence windows, surfaces/scopes, safe summaries, related memory/observation refs, current status and activation reinforcement context, guessed memory type, and risk flags. It does not create, approve, reject, snooze, or mutate memories, and it never prints raw prompts, queries, transcripts, or query previews.

`agent-memory consolidation explain "$DB" <candidate-id> --limit 200 --min-evidence 2` expands one candidate into an auditable read-only review packet. The explanation repeats the stable candidate payload, shows why the traces were grouped, exposes safe trace ids/windows/summaries, supporting activation/status signals, guessed memory type rationale, risk flags, and explicit review-state guardrails. Unknown candidate ids return JSON with `found: false` and a non-zero exit. The command is still advisory-only: it does not promote, approve, reject, snooze, or mutate memories, and it never prints raw trace payloads, prompts, transcripts, or `query_preview` values.

`agent-memory consolidation promote fact "$DB" <candidate-id> --subject-ref ... --predicate ... --object-ref-or-value ... --scope ...` starts Stage E with an explicit human-reviewed promotion action for semantic facts. The reviewer must supply the final fact fields; the command uses the candidate only as safe provenance, creating a local `consolidation_candidate` source from candidate id, trace ids, related observation ids, and safe summaries. Before any source/fact/lineage mutation, promotion now runs a read-only conflict preflight over the requested claim slot (`subject_ref`, `predicate`, `scope`). If an existing approved/candidate/disputed/deprecated fact in that slot has a different object value, the command returns `promoted: false`, `read_only: true`, `error: conflict_preflight_required`, status counts, safe conflicting fact summaries, and suggested `review explain`, `review replacements`, and `graph inspect` commands. Use `--allow-conflict` only after review if you intentionally want to keep both claims. By default successful promotion creates a `candidate` fact, so default retrieval remains approved-only; pass `--approve --actor ... --reason ...` only after explicit review to approve the new fact and log the status transition. Successful promotion also records graph lineage edges from the candidate fingerprint to the promoted fact (`promoted_to`) and from the fact to its generated provenance source (`has_promotion_provenance`) so `graph inspect "$DB" <candidate-id> --depth 2` can explain how a durable memory came from reviewed consolidation evidence. Unknown candidate ids return JSON with `promoted: false` and do not create sources, facts, or lineage relations. Procedure/preference promotion remains a future Stage E slice.

`agent-memory consolidation promotions report "$DB" --limit 50` adds the first read-only audit surface over those manual promotions. It lists promoted semantic facts, candidate fingerprints, generated provenance source ids, safe summaries/trace ids/observation ids, status counts, approval history, and the expected graph lineage relation refs without mutating facts, sources, relations, status transitions, retrieval ranking, or trace state. It is intended for review and release dogfood after promotion; it never prints raw prompts, transcripts, query previews, or raw trace metadata.

`agent-memory review relate-conflict fact "$DB" <left-fact-id> <right-fact-id> --actor ... --reason ...` records an explicit human-reviewed `conflicts_with` graph relation between two facts only when they share the same claim slot (`subject_ref`, `predicate`, `scope`) but have different object values. The command requires review metadata, stores it on the relation (`review_actor`, `review_reason`, `reviewed_at`), and intentionally does not approve, deprecate, supersede, or alter retrieval ranking. `review conflicts fact ...` includes these conflict relation refs alongside the read-only same-slot fact list so E4 `--allow-conflict` overrides remain auditable. Existing `review supersede fact ...` replacement relations also carry the same review metadata columns.

`agent-memory dogfood baseline "$DB" --output-json` composes the same read-only observation reports with package version, database path/schema metadata, memory status counts, sanitized Hermes hook doctor metadata, a non-executed local E2E marker, and suggested next steps. The baseline intentionally omits raw queries, query previews, prompt text, full Hermes config, and the bootstrap command so outputs can be pasted side by side during later trace/consolidation PRs. Treat all of these reports as local operator telemetry, not a synced analytics feature or an automatic cleanup workflow.

## Hermes quickstart

For most Hermes users:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
hermes hooks doctor
```

On first real Hermes use, Hermes may ask you to approve the shell hook or require `--accept-hooks` depending on your local Hermes policy.

The installed hook calls:

```bash
agent-memory hermes-pre-llm-hook ~/.agent-memory/memory.db --top-k 1 --max-prompt-lines 6 --max-prompt-chars 800 --max-prompt-tokens 200 --max-verification-steps 1 --max-alternatives 0 --max-guidelines 1 --no-reason-codes
```

The hook receives the Hermes event JSON on stdin, retrieves relevant approved memories, and returns bounded ephemeral context for the current prompt. It does not write back to Hermes session storage. `agent-memory bootstrap` uses the conservative Hermes preset by default: one top memory, small prompt budgets, no alternative-memory detail in the prompt, no reason-code noise, and fail-closed behavior if retrieval is unavailable.

If you only want to inspect the YAML snippet and not modify config:

```bash
agent-memory hermes-hook-config-snippet ~/.agent-memory/memory.db
```

If you want explicit paths and budgets:

```bash
agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --preset conservative --timeout 8
agent-memory hermes-install-hook ~/.agent-memory/memory.db --config-path ~/.hermes/config.yaml --preset balanced
```

Use `--preset balanced` if you intentionally want the older, more verbose hook shape (`--top-k 3`, larger budgets, and reason codes). Explicit flags such as `--top-k`, `--max-prompt-tokens`, or `--no-reason-codes` override the selected preset.

## Codex and Claude prompt wrappers

For harnesses that want a plain prompt prefix rather than a Hermes hook response:

```bash
agent-memory codex-prompt ~/.agent-memory/memory.db "What should I remember about this project?" --preferred-scope user:default
agent-memory claude-prompt ~/.agent-memory/memory.db "What should I remember about this project?" --preferred-scope user:default
```

The command prints prompt text only, so wrappers can prepend it to the live user request before invoking Codex, Claude Code, or another CLI.

This repository also includes source-checkout helper scripts for maintainers:

```bash
python scripts/run_codex_with_memory.py ~/.agent-memory/memory.db "What should I do next?" --dry-run
python scripts/run_claude_with_memory.py ~/.agent-memory/memory.db "What should I do next?" --dry-run
```

End users should prefer the installed `agent-memory` command unless they are developing this repository.

## Data and privacy model

- Default database: `~/.agent-memory/memory.db`
- Default Hermes config path: `~/.hermes/config.yaml`
- Storage: local SQLite
- Network behavior: the core CLI does not upload your memory database to an agent-memory cloud service
- Prompt policy: approved memories are retrieved by default; candidate/disputed/deprecated memories are excluded unless requested
- Scope policy: `user:default` is the recommended durable cross-project scope; Hermes can also derive privacy-preserving `cwd:<hash>` scopes without exposing raw local paths in prompt context

See `PRIVACY.md` and `SECURITY.md` for the external-user trust model, sensitive-data guidance, and vulnerability reporting instructions.

## Uninstall and rollback

Uninstall the CLI:

```bash
npm uninstall -g @cafitac/agent-memory
# or
pipx uninstall cafitac-agent-memory
# or
uv tool uninstall cafitac-agent-memory
```

Remove the Hermes hook by editing `~/.hermes/config.yaml` and deleting the `agent-memory hermes-pre-llm-hook ...` command from `hooks.pre_llm_call`.

Keep or remove local data explicitly:

```bash
# inspect first
ls -lh ~/.agent-memory/memory.db

# destructive: removes the local memory database
rm ~/.agent-memory/memory.db
```

`agent-memory bootstrap` backs up changed Hermes config files to `*.agent-memory.bak` when it modifies an existing config.

## Retrieval evaluation and regression gates

agent-memory includes a fixture-based retrieval evaluator so retrieval behavior can be tested like application code:

```bash
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --baseline-mode lexical
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --baseline-mode lexical --format text
agent-memory eval retrieval ~/.agent-memory/memory.db tests/fixtures/retrieval_eval --fail-on-regression
```

Supported baseline modes include:

- `lexical`: preferred-scope lexical comparator
- `lexical-global`: lexical comparator that ignores preferred scope
- `source-lexical`: lexical comparator over linked source content within preferred scope
- `source-global`: source-linked comparator that ignores preferred scope

Reports include per-task retrieved IDs, expected hits, missing IDs, avoid hits, pass/fail state, aggregate summaries, soft-threshold advisories, and failure triage details such as snippets, lifecycle status, scopes, and policy signals. Every JSON result also includes an `advisory_report` with severity, affected task IDs, and recommended next actions. Text reports render the same advisory report as terminal-friendly guidance for maintainers reviewing failed retrieval tasks; JSON is the stable machine-readable surface.

The evaluator calls the real retrieval path but suppresses retrieval bookkeeping side effects while it runs. Eval tasks do not increment `retrieval_count`, `reinforcement_count`, or `last_accessed_at`, so fixture order and repeated local/CI runs do not perturb later ranking results.

## Current maturity

agent-memory is alpha software, but the public install path is validated.

What is ready:

- npm and PyPI releases from the same versioned source
- GitHub Release artifacts
- CI and release metadata checks
- published-install smoke checks
- local SQLite storage
- Hermes bootstrap/doctor flow
- Codex/Claude prompt rendering commands
- approved-only retrieval policy by default
- retrieval regression fixtures and diagnostic reports

Known limitations:

- no hosted sync service
- no built-in encryption-at-rest wrapper around the SQLite file
- no automatic secret detection/redaction before users create memories
- no stable 1.0 API guarantee yet
- advanced graph/semantic retrieval behavior is still evolving
- multi-machine sharing is currently a user-managed file/sync concern

## Development

```bash
git clone https://github.com/cafitac/agent-memory.git
cd agent-memory
uv run pytest tests/ -q
uv run python scripts/check_release_metadata.py
uv run python scripts/smoke_release_readiness.py
uv run pytest tests/test_published_install_smoke.py -q
npm pack --dry-run
```

Release automation expects protected `main`: feature PRs and release-sync PRs run `ci.yml`, while `auto-release.yml` ignores docs/workflow-only pushes and `publish.yml` runs only from version tags or explicit manual dispatch. To keep GitHub Actions minutes bounded, `publish.yml` performs release metadata validation, package build, npm dry-run, npm/PyPI publish, and GitHub Release creation, but it no longer repeats the full pytest suite or runs the slow real-registry install matrix by default.

If a release needs extra external-install validation, run the opt-in `published-install-smoke` workflow manually with `gh workflow run published-install-smoke.yml -f version=<version>`, or dispatch `publish.yml` with `-f run_published_install_smoke=true`. The smoke verifies the exact npm/PyPI version through npm registry lookup, `npx`, `npm exec`, `uvx`, and `pipx`. The smoke script treats early resolver/package-index misses as propagation-like failures and applies exponential backoff before failing; failure artifacts include npm/PyPI registry probe diagnostics so maintainers can tell whether metadata is visible while installers are still stale.

If the auto-release workflow cannot push its bumped metadata commit directly, it opens a `release-sync/vX.Y.Z` PR instead. After that PR is merged, the same workflow tags the synced version and dispatches fast `publish.yml` with `run_published_install_smoke=false`, keeping the release path automated without requiring a permanent branch-protection bypass. The fallback is safe to rerun: if the `release-sync/vX.Y.Z` branch or PR already exists, the workflow reuses it instead of failing on a non-fast-forward push or opening a duplicate PR. When it creates a new release-sync PR, it also dispatches `ci.yml` on that bot-created branch and comments with the validation handoff because GitHub can suppress automatic PR checks for bot-created refs.

Useful source-checkout commands:

```bash
uv run python -m agent_memory.api.cli --help
uv run python -m agent_memory.api.cli hermes-bootstrap /tmp/agent-memory.db --config-path /tmp/hermes-config.yaml
uv run python -m agent_memory.api.cli hermes-doctor /tmp/agent-memory.db --config-path /tmp/hermes-config.yaml
```

## Repository docs

- `docs/install-smoke.md`: published install smoke recipes
- `SECURITY.md`: vulnerability reporting and local security model
- `PRIVACY.md`: local data, prompt, and hook privacy model
- `CONTRIBUTING.md`: contribution workflow
- `.dev/`: AI-authored drafts, design spikes, research notes, and unapproved plans
- `docs/`: human-reviewed promoted documentation

## License

MIT. See `LICENSE`.
