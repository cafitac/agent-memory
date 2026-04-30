# Privacy

agent-memory is designed as a local-first memory runtime for AI agents.

## What is stored

Depending on the commands and integrations you use, the SQLite database may contain:

- approved semantic facts
- candidate facts awaiting review
- procedures and steps
- episodes / work history
- source records and excerpts
- scopes and provenance metadata
- lifecycle states such as candidate, approved, disputed, and deprecated

Default database path:

```text
~/.agent-memory/memory.db
```

## What is sent to models

agent-memory itself renders memory context. The host harness decides where that context goes.

For example, the Hermes pre-LLM hook returns bounded context to Hermes, and Hermes injects it into the current prompt. Codex/Claude prompt commands print prompt text that a wrapper can prepend to a model request.

By default, retrieval uses approved memories only. Candidate, disputed, and deprecated memories are excluded from normal prompt context unless you explicitly ask for them, for example with `--status all` during forensic review.

## What is not sent by default

The core CLI does not intentionally upload your SQLite database to an agent-memory cloud service. There is no default hosted sync service.

agent-memory does not control what a downstream agent/model provider stores after your harness sends prompt context. Review the privacy policy of Hermes, Codex, Claude, or any other host you connect to.

## Scope and path privacy

`user:default` is the recommended durable cross-project scope.

When the Hermes hook needs a project-local default and no explicit `--preferred-scope` is set, it can derive a `cwd:<hash>` scope from the runtime working directory. This avoids embedding raw local usernames or repository paths in prompt context.

## Sensitive data guidance

Do not store secrets as memories.

Avoid approving memories that contain:

- API keys
- access tokens
- passwords
- private keys
- customer data
- production connection strings
- confidential incident details that should never enter prompts

If sensitive data is accidentally stored, remove or rotate it like any other local secret exposure. If a secret may have been sent to a hosted model through prompt context, rotate it with the relevant upstream service.

## Inspecting and deleting local data

Inspect whether the default DB exists:

```bash
ls -lh ~/.agent-memory/memory.db
```

Delete the default DB:

```bash
rm ~/.agent-memory/memory.db
```

This is destructive. Back up the file first if you may need its contents later.

## Hermes config changes

`agent-memory bootstrap` may create or update:

```text
~/.hermes/config.yaml
```

When modifying an existing config, the installer backs up changed files to `*.agent-memory.bak`. To disable the integration, remove the `agent-memory hermes-pre-llm-hook ...` entry from `hooks.pre_llm_call`.
