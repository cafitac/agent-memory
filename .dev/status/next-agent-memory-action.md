# agent-memory next action

Status: AI-authored draft. Not yet human-approved.
Last updated: 2026-05-10 21:14 KST

## Use this first when the user asks

Read this file before answering prompts such as:

- "다음으로 뭐하지?"
- "다음 할 거 추천해줘"
- "agent-memory 이어서 해줘"
- "지금 상황에서 제일 좋은 다음 작업 뭐야?"

Then verify the repo/runtime state briefly and answer from the recommendation below. Do not ask the user to restate context.

## One-sentence current state

`agent-memory` is released and live-runtime-smoked through `v0.1.136`; the installed Hermes hook is using `/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory`, and broad G4/background consolidation apply remains intentionally blocked by the remaining fresh trace-linkage quality gap.

## Current progress estimate toward the north-star

The north-star is a human-memory-like, mostly automatic, graph-based memory consolidation runtime: experience traces, retrieval activations, reinforcement/decay, reviewable candidates, approved graph memories, conflict/supersession, safe retrieval, and audited/reversible automation.

Approximate progress:

- Overall north-star: 45-50%.
- Substrate/evidence plumbing: about 65%.
- Safe automatic mutation/promotion: about 25-30%.

Reasoning:

- Done: trace substrate, retrieval observations, activation/reinforcement/decay evidence, graph/review primitives, background dry-runs, fresh-epoch comparison, persisted review queue, and the first narrow approved mutation (`apply_reinforcement_marker`).
- Not done: broad background consolidation apply, automatic long-term memory promotion, conflict-aware automatic supersession, weak-trace decay/collapse apply, graph-cluster-to-fact/procedure/episode generation, and large-scope rollback confidence.

## Latest verified checkpoint

- Release: `v0.1.136`
- GitHub Release: `https://github.com/cafitac/agent-memory/releases/tag/v0.1.136`
- npm: `@cafitac/agent-memory@0.1.136`
- PyPI: `cafitac-agent-memory==0.1.136`
- Runtime: `/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory`
- Hermes config backup from rollout: `/Users/reddit/.hermes/config.yaml.bak-agent-memory-v0.1.136-20260510T2044`
- Installed hook smoke artifact: `/tmp/agent-memory-v0136-hook-smoke.json`
- Live G4 preview artifact: `/tmp/agent-memory-v0136-g4-preview-live.json`
- Disposable installed apply smoke artifact: `/tmp/agent-memory-v0136-installed-apply.json`
- Docs checkpoint PR: `https://github.com/cafitac/agent-memory/pull/287`

## Current blocker

The live installed G4 preview stayed read-only/no-mutation and produced queue entries, but the quality gate still blocked on:

- `background_empty_retrieval_trace_linkage_gap`

Fresh comparison has already separated old historical unknowns from new evidence, but there is still fresh unlinked observation evidence. That means broad G4/background apply must stay blocked.

## Current implementation slice

Branch `feat/g4-linkage-gap-diagnose` adds a read-only command:

```bash
agent-memory dogfood g4-linkage-gap-diagnose /Users/reddit/.agent-memory/memory.db \
  --epoch-start 2026-05-10T11:40:00Z \
  --surface hermes-pre-llm-hook \
  --output /tmp/agent-memory-g4-linkage-gap-diagnose-source-live.json
```

The source-checkout live smoke kept `retrieval_observations`, `memory_activations`, and `experience_traces` counts unchanged and classified the selected fresh epoch as `hook_runtime_linkage_bug` because many trace rows still have empty `related_observation_ids_json` while matching observations/activations exist. Broad G4/background apply is still blocked.

## Recommended next work

Best next PR-sized slice:

1. Add or strengthen an installed-runtime read-only diagnostic that explains the remaining fresh trace-linkage gap in ref-safe terms.
2. It should identify whether the latest fresh unlinked observation is:
   - a real hook/runtime linkage bug,
   - an expected race/window artifact,
   - a metadata classification gap,
   - or historical/rollout telemetry that should be handled by a reviewed backfill/reset corridor.
3. Keep the command read-only, aggregate/ref-only, and no raw prompt/query/transcript/sample values.
4. Add RED tests before implementation.
5. Run installed-runtime smoke against `/Users/reddit/.agent-memory/memory.db` after release, not only source tests.

Suggested command shape:

```bash
agent-memory dogfood g4-linkage-gap-diagnose /Users/reddit/.agent-memory/memory.db \
  --epoch-start 2026-05-10T11:40:00Z \
  --surface hermes-pre-llm-hook \
  --output /tmp/agent-memory-v0136-linkage-gap-diagnose.json
```

If that command is too narrow, the alternative is to extend `dogfood g4-review-queue-preview --epoch-start ...` with a `trace_linkage_gap_drilldown` section.

## What not to do next

Do not start with broad G4/background apply.

Do not live-apply persisted queue mutations unless the user explicitly approves it. If approved later, first back up the live DB and start only with the persisted `fact:1` reinforcement-review item. That path is a narrow reinforcement marker, not general memory consolidation.

Do not silently delete, reset, or rewrite telemetry. If the fresh trace-linkage gap persists, design a reviewed telemetry backfill/reset preview/apply corridor with backup, policy, actor, reason hash, audit row, and rollback guidance.

## Fast answer template for next session

If asked "다음으로 뭐해야 해?", answer:

> 지금은 v0.1.136까지 릴리즈/설치/스모크가 끝났고, broad G4 자동 consolidation apply는 아직 `background_empty_retrieval_trace_linkage_gap` 때문에 막혀 있어요. 다음으로 제일 좋은 작업은 live DB를 건드리지 않는 read-only linkage-gap 진단 slice입니다. fresh epoch 이후 남은 unlinked observation이 실제 버그인지, 정상 race/window인지, 분류 gap인지, 아니면 reviewed reset/backfill corridor가 필요한 과거성 telemetry인지 ref-safe하게 설명하는 명령/리포트를 만들고 테스트하는 게 맞습니다.

## Quick verification commands

```bash
cd /Users/reddit/Project/agent-memory
git status --short --branch
/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/python - <<'PY'
import agent_memory
print(agent_memory.__version__)
PY
/Users/reddit/.agent-memory/runtime/v0.1.136/.venv/bin/agent-memory dogfood g4-review-queue-preview \
  /Users/reddit/.agent-memory/memory.db \
  --limit 30 --top 5 --queue-limit 5 --frequent-threshold 3 \
  --epoch-start 2026-05-10T11:40:00Z \
  --output /tmp/agent-memory-next-g4-preview.json
```

Expected: read-only/no-mutation. If `background_empty_retrieval_trace_linkage_gap` is gone, reassess the next slice. If it remains, implement the linkage-gap diagnostic slice above.
