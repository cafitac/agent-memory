# graph-first vs hybrid retrieval

Status: AI-authored draft. Not yet human-approved.

## Question

The project is leaning toward graph-based memory because human memory feels connected.
Is that the right direction, or could it become a bad abstraction?

## Short answer

Graph is a strong direction, but graph-only is a mistake.
The best architecture is likely graph-centered and hybrid.

## Why graph is attractive

1. Connected recall
   - human memory feels associative
   - graph edges support multi-hop recall and contextual expansion

2. Disambiguation
   - one token can map to multiple meanings
   - graph neighborhoods help distinguish company vs fruit vs code symbol

3. Explainability
   - retrieval can explain which nodes and edges were traversed

4. Provenance organization
   - evidence can be clustered around facts, entities, and procedures rather than remaining as loose chunks

5. Strong fit for semantic and procedural memory
   - facts and procedures are often more useful when connected to entities, tasks, and outcomes

## Why graph can go wrong

1. Edge quality bottleneck
   - bad extraction produces bad links
   - bad links can poison recall more subtly than bad chunks

2. Over-structuring too early
   - some observations are too uncertain or too ambiguous to force into a rigid graph

3. Retrieval drift through dense neighborhoods
   - graph expansion can pull in semantically related but task-irrelevant content

4. Maintenance cost
   - canonicalization, deduplication, and relation repair are real ongoing costs

5. Text still matters
   - some valuable knowledge remains best represented as text snippets, episodes, or evidence summaries

## Recommended stance

Use graph as the semantic spine, but preserve other retrieval channels.

### Best-effort architecture
- graph for canonical entities, concepts, facts, procedures, and relations
- lexical retrieval for precision and direct phrase matching
- metadata filters for scope and recency control
- optional embeddings for fuzzy semantic candidate generation
- reranking to combine all signals

### Retrieval order suggestion
1. parse the query and infer candidate entities/concepts/tasks
2. retrieve exact/lexical matches first
3. retrieve graph-neighbor candidates with bounded depth
4. retrieve optional embedding neighbors
5. rerank by task fit, confidence, recency, and scope
6. assemble a compact explanation-friendly retrieval packet

## Human-brain inspiration without overclaiming

The project can be inspired by the brain without pretending to be biologically faithful.

Good inspirations:
- multiple memory systems
- consolidation from episodes into more abstract knowledge
- salience and recency effects
- associative recall
- forgetting and compression

Bad inspirations:
- assuming every useful engineering component must map directly to a brain region
- assuming graph structure alone reproduces human memory quality

## Practical conclusion

Graph is not the wrong direction.
But the safest and strongest path is:
- graph-centered
- evidence-backed
- hybrid retrieval
- aggressively evaluated against non-graph baselines

The project should prove graph value empirically, not assume it.
