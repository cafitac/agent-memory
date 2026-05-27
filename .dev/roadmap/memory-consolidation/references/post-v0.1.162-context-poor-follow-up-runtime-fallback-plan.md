# post-v0.1.162 context-poor follow-up runtime fallback plan

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-27 13:45 KST

## Triggering observation

A live Hermes turn asked a context-dependent Korean follow-up: `그럼 이후에 할 작업은 뭐지? 개선이 필요한거 아니야?`.

The live `agent-memory` storage path was healthy and actively recording:

- `dogfood storage-health` over `/Users/reddit/.agent-memory/memory.db` reported `status=healthy`, `warnings=[]`, `plugin_enabled=true`, `doctor_status=ok`, `duplicate_context_injection_risk=false`.
- Live totals at the time of inspection: `retrieval_observations=4627`, `memory_activations=10554`, `experience_traces=4627`, `facts=9`, `procedures=1`, `episodes=1`.
- Latest observations/traces/activations were fresh to the current minute, and 24h trace quality had `observation_trace_coverage_ratio=1.0`, `warnings=[]`, and privacy flags proving no raw conversation/query/trace samples were included.

However, a direct `hermes-context` smoke with only the short follow-up query reproduced the UX failure:

```text
Memory response mode: verify_first
Prompt prefix: No reliable memory is available yet; gather more evidence before answering.
Top memory: none
Verification step: gather_more_evidence, severity=high, blocking=yes
```

Adding explicit terms such as `agent_memory_context`, `gather_more_evidence`, or the project/domain made retrieval succeed. This means storage is not the blocker; context-poor follow-up query routing is.

## Diagnosis

The current Hermes hook retrieves mostly from the current user message. Short follow-up phrasing in Korean/English can be too lexical-light to hit the approved agent-memory roadmap/procedure facts, even when the current working directory is the `agent-memory` repo and `.dev/status/current-handoff.md` / `.dev/status/next-agent-memory-action.md` contain the exact next work.

Separate active-learning noise was also observed in the same live turn: session-end learned rules for Claude/Hermes adapter internals were injected into a normal user request. That is a related retrieval/filtering problem, but this slice focuses on the safe runtime fallback for `agent-memory` follow-up work.

## Safe slice scope

Add a read-only runtime fallback for context-poor follow-up questions in the `agent-memory` repo.

Desired behavior:

1. If normal approved-memory retrieval already returns a reliable decision, do nothing.
2. If normal retrieval returns `verify_first` / no top memory and the query looks like a follow-up/next-work/status question, retry retrieval with a safe expanded query containing stable agent-memory handoff terms, for example:
   - `agent-memory current handoff next action .dev status roadmap memory-consolidation`
   - preserve the user's original query as part of the retrieval query only through hashing/observation-safe paths; do not print/store raw query previews.
3. Only use this fallback for prompt/context rendering. It must not:
   - write memory status
   - approve/promote/collapse/delete memories
   - change default retrieval ranking
   - change storage policy
   - authorize G4/default/background/unattended apply
4. Prompt output must label the fallback so operators can tell the answer is grounded by a follow-up query expansion, not by a direct exact match.
5. If the expanded query still has no reliable memory, keep the existing `gather_more_evidence` behavior.
6. Keep privacy behavior unchanged: no raw query preview, no raw transcript, no raw `.dev` content dump from the hook.

## RED tests to add first

- `hermes-context` with Korean query `그럼 이후에 할 작업은 뭐지? 개선이 필요한거 아니야?` and an approved agent-memory next-action fact that is only discoverable via agent-memory handoff terms should not stay `Top memory: none`; it should include a fallback marker and retrieved approved memory content.
- A non-follow-up unrelated query against the same DB should keep the existing `verify_first` / `gather_more_evidence` behavior.
- The fallback must not mutate durable memory counts or enable any automation authority.

## Follow-up after this slice

After the runtime fallback is green, continue the documented product work:

1. Continue normal-turn dogfood for `fact:5` / `fact:6`.
2. Rerun the scheduled artifact chain: decay-risk, scheduled-dry-run, blocker-resolution, evidence-blocker packet, classification validation, and classification resolution.
3. Keep broad G4 apply, ordinary auto-approval, unattended/default/background apply, default-ranking mutation, collapse/delete, telemetry reset, and unreviewed promotion blocked until separate reviewed gates pass.
