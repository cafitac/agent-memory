# First-run memory layer setup

This guide is the safe first-run path for users who want to try agent-memory without learning the whole data model first.

## What bootstrap creates

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

`agent-memory bootstrap` is local-first. It creates or reuses:

- `~/.agent-memory/memory.db` — the local SQLite database for curated memory.
- `~/.hermes/config.yaml` — the Hermes config file where the pre-LLM shell hook is merged.

Existing Hermes hooks are preserved. If bootstrap modifies an existing config it writes a `*.agent-memory.bak` backup next to the config file.

## Safe default behavior

Bootstrap installs the Hermes hook with the `conservative` preset. The generated hook is intentionally small and auditable:

- one top memory by default
- small prompt line, character, and token budgets
- no alternative-memory detail in normal prompt context
- no reason-code noise by default
- fail closed when the database or retrieval path is unavailable

The hook only reads approved memory and returns bounded context for the current prompt. It does not upload the database, sync it, or write back to Hermes session storage.

## First memory

```bash
DB=~/.agent-memory/memory.db
agent-memory create-fact "$DB" "agent-memory" "primary-install-path" "npm install -g @cafitac/agent-memory" "user:default"
agent-memory approve-fact "$DB" 1
agent-memory retrieve "$DB" "How should I install agent-memory?" --preferred-scope user:default
```

Normal retrieval is approved-only. Candidate, disputed, and deprecated memories stay out of prompt context unless you intentionally run a forensic command such as `agent-memory retrieve ... --status all`.

## Verify the layer

```bash
agent-memory doctor
hermes hooks doctor
```

Expected result:

- the DB exists
- the config exists
- the hook is installed
- Hermes hook diagnostics are healthy or show a clear local policy action such as accepting hooks

## Disable or delete

To disable the hook without deleting memory, edit `~/.hermes/config.yaml` and remove the `agent-memory hermes-pre-llm-hook ...` entry from `hooks.pre_llm_call`.

To delete local memory data, remove the SQLite database after confirming you no longer need it:

```bash
rm ~/.agent-memory/memory.db
```

To fully revert bootstrap, remove the hook entry from `~/.hermes/config.yaml` and delete `~/.agent-memory/memory.db`. Restore the `*.agent-memory.bak` file if you want the exact pre-bootstrap Hermes config.
