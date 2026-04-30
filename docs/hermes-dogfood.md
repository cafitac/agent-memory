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

A good conservative smoke has low latency, at most one surfaced memory, no noisy reason codes, and no workflow-blocking error if the memory DB is missing.

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
