# Retrieval evaluation v0

Status: AI-authored draft. Not yet human-approved.

## Goal

Define how to measure whether agent-memory retrieval is actually getting better instead of only becoming more complex.

## Principle

Graph-centered memory only matters if it beats simpler baselines on real tasks.

Do not assume:
- more structure means better retrieval
- embeddings automatically help
- bigger context packets are better

## Evaluation questions

1. Does agent-memory beat transcript/session search alone?
2. Does approved-memory retrieval beat raw-source retrieval alone?
3. Does graph expansion help or create drift?
4. Do embeddings add enough value to justify complexity?
5. Does retrieval remain explainable under prompt budgets?

## Baselines

Minimum baselines:
- baseline A: transcript/session grep or lexical-only source search
- baseline B: lexical retrieval over approved memory only
- baseline C: lexical + metadata filtering
- candidate next baseline: lexical + graph
- candidate next baseline: lexical + graph + embeddings

## Task set

Define 5-10 representative tasks before adding more retrieval complexity.

Suggested task families:
- recall a stable repo/project convention
- recall a proven procedure that worked previously
- distinguish current truth from stale historical truth
- retrieve relevant context for a new but related task
- explain why a retrieved memory was selected
- avoid retrieving project-irrelevant memory from another scope

Each task should include:
- query text
- expected useful answer ingredients
- expected irrelevant/drift items to avoid
- target scope
- prompt budget

## Metrics

### Relevance metrics
- top-k hit quality
- whether key fact/procedure was included
- rank of first truly useful item
- drift rate (irrelevant memory included)

### Efficiency metrics
- prompt chars / tokens used
- useful-signal-per-token ratio
- whether the system stayed under budget without losing critical context

### Trust/explainability metrics
- provenance present or absent
- confidence/status visibility
- explanation quality of why an item appeared
- contradiction warning visibility

### Outcome metrics
- task success uplift
- reduction in repeated user correction
- reduction in unnecessary follow-up search/tooling steps

## Suggested evaluation harness shape

For each task:
1. run baseline retrieval
2. run current retrieval
3. compare outputs side by side
4. score usefulness and drift
5. record explanation quality
6. only promote a more complex retrieval mode if it wins clearly

## Embedding adoption gate

Do not add embeddings just because they are common.

Add them only if:
- lexical + graph misses materially useful fuzzy recall cases
- explanation quality remains acceptable
- operational complexity stays manageable
- measured uplift beats simpler setups on the task set

## Minimum artifact format

The repo should eventually have a reproducible evaluation artifact containing:
- task id
- query
- retrieval mode
- retrieved packet
- score summary
- qualitative notes
- pass/fail against expected essentials

## Early warning signs

Bad retrieval systems often show one or more of:
- top-k gets bigger but not better
- graph expansion pulls in related but useless content
- disputed or deprecated memory outranks current approved truth
- prompt packet becomes too large to be practical
- provenance gets hidden or dropped

## Decision

The next retrieval milestone should be evaluation-led. Complexity only earns its place if it improves real recall quality under realistic prompt budgets.
