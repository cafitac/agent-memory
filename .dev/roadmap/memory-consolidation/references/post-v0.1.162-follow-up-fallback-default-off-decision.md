# post-v0.1.162 follow-up fallback default-off decision

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-27 15:57 KST

## Problem

The previous context-poor follow-up fallback fixed a real UX gap for short prompts such as `그럼 이후에 할 작업은 뭐지?`, but making that fallback implicit in normal Hermes runtime paths has a downside:

- It can mask baseline retrieval quality during performance/function tests.
- It can turn a genuine `Top memory: none` / `gather_more_evidence` signal into a fallback success, making retrieval regressions harder to detect.
- It is agent-memory repo-specific and uses handoff expansion terms, so it should not silently become a broad runtime behavior.

## Decision

Keep the fallback implementation as a diagnostic/operator escape hatch, but make it opt-in instead of default-on.

Desired contract:

1. `hermes-context` and `hermes-pre-llm-hook` default behavior should preserve raw retrieval results. A context-poor query with no reliable memory should remain `verify_first` / `Top memory: none`.
2. An explicit opt-in flag may enable the fallback for targeted operator/debug sessions.
3. The Hermes plugin may expose the same opt-in through an environment variable, defaulting to disabled.
4. When enabled, the fallback must remain read-only and visibly marked with `Follow-up fallback: expanded context-poor query with agent-memory handoff terms.`
5. This change must not alter default retrieval ranking, memory statuses, collapse/delete behavior, ordinary auto-approval, or background/default/unattended apply authority.

## Test plan

- Update the existing Korean follow-up tests so default `hermes-context` and `hermes-pre-llm-hook` stay blocked without opt-in.
- Add opt-in tests proving `--followup-fallback` enables the existing fallback behavior.
- Verify no fallback retrieval writes extra activation rows (`record_retrievals=False`) in the opt-in path.
- Run focused CLI tests and a live smoke against `/Users/reddit/.agent-memory/memory.db` for both default and opt-in behavior.

## Next safe work

After default-off fallback is verified and documented, return to the scheduled evidence chain state. The latest read-only live check showed monitor-only decay candidates only and a green `scheduled-blocker-resolution` for bounded partial automation evidence, but broad/default/background mutation authority remains blocked.
