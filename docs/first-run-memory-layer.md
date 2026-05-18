# First-run setup

The default setup is local-first. For Hermes, the plugin path avoids manual config edits:

```bash
hermes plugins install cafitac/agent-memory --enable
```

The plugin uses `~/.agent-memory/memory.db` by default and injects recalled context through Hermes' `pre_llm_call` plugin hook. Set `AGENT_MEMORY_DB_PATH` if you want a different database.

For an agent-agnostic CLI setup, use npm:

```bash
npm install -g @cafitac/agent-memory
agent-memory bootstrap
agent-memory doctor
```

`bootstrap` creates or reuses the local SQLite database at:

```text
~/.agent-memory/memory.db
```

It also adds the agent-memory pre-LLM hook to the local Hermes config when Hermes is present. Existing hook config is preserved where possible, and a backup is written before config changes. The default hook uses the conservative preset.

## Check the setup

```bash
agent-memory doctor
```

If you use Hermes, also run:

```bash
hermes hooks doctor
```

Hermes may ask you to approve the new hook command the first time it runs.

## Use without global install

```bash
npm exec --yes --package @cafitac/agent-memory -- agent-memory doctor
```

## Privacy note

`agent-memory` is not a hosted service. By default, your memory database stays on your machine.

Treat these as private local data:

- `~/.agent-memory/memory.db`
- backup bundles
- exported graph or report files
- debug/dogfood artifacts

## Remove local data

To delete local memory data after confirming you no longer need it:

```bash
rm ~/.agent-memory/memory.db
```

To disable the Hermes hook, edit `~/.hermes/config.yaml` and remove the `agent-memory` hook entry from `hooks.pre_llm_call`.
