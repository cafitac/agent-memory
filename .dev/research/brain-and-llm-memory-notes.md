# brain and LLM memory research notes

Status: AI-authored draft. Not yet human-approved.

This file captures external references gathered during the design spike and translates them into implications for agent-memory.

## 1. Human memory systems: useful inspirations

### 1.1 Episodic and semantic memory
Reference surfaced via OpenAlex:
- Memory Transformation and Systems Consolidation (2011)
  - Journal of the International Neuropsychological Society
  - cited_by_count at lookup time: 566
  - DOI: https://doi.org/10.1017/S1355617711000683
- Episodic and declarative memory: Role of the hippocampus (1998)
  - Hippocampus
  - cited_by_count at lookup time: 87
  - DOI: https://doi.org/10.1002/(SICI)1098-1063(1998)8:3<198::AID-HIPO2>3.3.CO;2-J

Relevant takeaway:
- episodic memory and semantic memory are related but not identical
- experiences can transform over time into more abstract, generalized knowledge

Design implication:
- agent-memory should not keep only raw episodes
- episodic traces should be able to consolidate into semantic facts and procedures

### 1.2 Working memory and persistent activity
Reference surfaced via OpenAlex:
- Role of Prefrontal Persistent Activity in Working Memory (2016)
  - Frontiers in Systems Neuroscience
  - cited_by_count at lookup time: 264
  - DOI: https://doi.org/10.3389/fnsys.2015.00181
- Revisiting the role of persistent neural activity during working memory (2014)
  - Trends in Cognitive Sciences
  - cited_by_count at lookup time: 477
  - DOI: https://doi.org/10.1016/j.tics.2013.12.001

Relevant takeaway:
- working memory is active, capacity-limited, and task-coupled
- it is not the same thing as long-term storage

Design implication:
- active-task memory should be a separate layer with stricter TTL and token budgets
- do not pollute durable memory with every transient working-state item

### 1.3 Procedural memory and basal ganglia / habit learning
Reference surfaced via OpenAlex:
- The role of the basal ganglia in learning and memory: Insight from Parkinson’s disease (2011)
  - Neurobiology of Learning and Memory
  - cited_by_count at lookup time: 202
  - DOI: https://doi.org/10.1016/j.nlm.2011.08.006
- Human and Rodent Homologies in Action Control: Corticostriatal Determinants of Goal-Directed and Habitual Action (2009)
  - Neuropsychopharmacology
  - cited_by_count at lookup time: 1787
  - DOI: https://doi.org/10.1038/npp.2009.131

Relevant takeaway:
- action knowledge and habit-like behavior differ from factual memory
- repeated successful actions can become more automatic

Design implication:
- procedural memory deserves its own object model and scoring signals
- successful reuse should strengthen ranking differently from factual confidence

## 2. LLM / agent memory systems

### 2.1 MemGPT
Reference surfaced via OpenAlex:
- MemGPT: Towards LLMs as Operating Systems (2023)
  - cited_by_count at lookup time: 38
  - DOI: https://doi.org/10.48550/arxiv.2310.08560

Relevant takeaway:
- hierarchical memory management matters when context windows are limited
- memory needs explicit movement between active context and external storage

Design implication:
- agent-memory should model memory tiers explicitly
- retrieval and eviction policies matter as much as storage

### 2.2 MemoryBank
Reference surfaced via OpenAlex:
- MemoryBank: Enhancing Large Language Models with Long-Term Memory (2024)
  - AAAI
  - cited_by_count at lookup time: 118
  - DOI: https://doi.org/10.1609/aaai.v38i17.29946

Relevant takeaway:
- long-term memory for agents benefits from accumulation plus forgetting mechanisms
- simple accumulation without selective retention is not enough

Design implication:
- decay, forgetting, and importance scoring should be part of the design early

### 2.3 LONGMEM
Reference surfaced via OpenAlex:
- Augmenting Language Models with Long-Term Memory (2023)
  - cited_by_count at lookup time: 33
  - DOI: https://doi.org/10.48550/arxiv.2306.07174

Relevant takeaway:
- long-context augmentation is helpful, but long-term memory still needs external structures

Design implication:
- context extension is not a substitute for a memory runtime

### 2.4 Generative Agents
Reference surfaced via OpenAlex:
- Generative Agents: Interactive Simulacra of Human Behavior (2023)
  - cited_by_count at lookup time: 1308
  - DOI: https://doi.org/10.1145/3586183.3606763

Relevant takeaway:
- memory scoring by recency, relevance, and importance is useful
- higher-level reflections over many memories can guide future behavior

Design implication:
- ranking should combine recency, relevance, and importance
- the system should support reflective summarization over multiple episodes

### 2.5 HippoRAG
Reference surfaced via OpenAlex:
- HippoRAG: Neurobiologically Inspired Long-Term Memory for Large Language Models (2024)
  - cited_by_count at lookup time: 20
  - DOI: https://doi.org/10.48550/arxiv.2405.14831

Relevant takeaway:
- graph-like or memory-network structures can improve non-parametric recall for LLMs
- the hippocampal inspiration is specifically about indexing and associative recall, not literal biological reproduction

Design implication:
- graph-based retrieval is promising, especially for associative recall
- but it should be validated against simpler baselines

### 2.6 GraphRAG / HybridRAG family
References surfaced via OpenAlex:
- HybridRAG: Integrating Knowledge Graphs and Vector Retrieval Augmented Generation for Efficient Information Extraction (2024)
  - cited_by_count at lookup time: 88
  - DOI: https://doi.org/10.1145/3677052.3698671
- Equipping Large Language Models with Memories: A GraphRAG Based Approach (2024)
  - cited_by_count at lookup time: 1
  - DOI: https://doi.org/10.1109/SMC54092.2024.10831551

Relevant takeaway:
- graph augmentation can improve structured reasoning and explainability
- hybrid retrieval often beats single-paradigm retrieval in practical systems

Design implication:
- graph should likely be the semantic spine, not the only retrieval mechanism

### 2.7 Zep temporal knowledge graph
Reference surfaced via OpenAlex:
- Zep: A Temporal Knowledge Graph Architecture for Agent Memory (2025)
  - cited_by_count at lookup time: 4
  - DOI: https://doi.org/10.48550/arxiv.2501.13956

Relevant takeaway:
- time-aware knowledge graphs are a natural fit for agent memory
- agent memory is not just entities and facts; it also needs temporal sequencing

Design implication:
- valid_from / valid_to / event ordering should be first-class fields

### 2.8 A-MEM
Reference surfaced via OpenAlex:
- A-MEM: Agentic Memory for LLM Agents (2025)
  - cited_by_count at lookup time: 6
  - DOI: https://doi.org/10.48550/arxiv.2502.12110

Relevant takeaway:
- agent memory is evolving toward more active and policy-driven memory management
- memory should not be passive storage only

Design implication:
- retrieval, curation, and promotion policies should be explicit and tunable

## 3. Design conclusions from the research pass

### 3.1 Good ideas to keep
- layered memory: working / episodic / semantic / procedural
- consolidation from episodes into abstractions
- recency + importance + relevance scoring
- forgetting / decay / archival
- graph-based associative recall
- temporal modeling
- reflective summarization over multiple memories

### 3.2 Cautions
- graph-only retrieval may be brittle if edge extraction quality is poor
- biological inspiration should guide architecture, not justify untested complexity
- long context is useful but does not replace memory curation
- embeddings help, but chunk similarity alone is not enough

### 3.3 Strong recommendation
Build agent-memory as a hybrid memory runtime:
- graph-centered semantic layer
- lexical retrieval baseline
- optional embedding candidate generation
- temporal signals
- explicit curation lifecycle
- strong provenance and explanation support

## 4. What to test empirically

Before fully committing to graph-heavy design, benchmark these variants:
1. transcript search only
2. lexical + metadata retrieval over canonical memory objects
3. lexical + graph expansion
4. lexical + graph + embeddings
5. lexical + graph + embeddings + rerank + decay

Measure:
- precision of recalled memories
- task success uplift
- prompt token cost
- contradiction rate
- explanation quality
- user correction rate over repeated tasks

## 5. Bottom line

The human-brain inspiration is directionally useful.
But the best engineering interpretation is probably not "simulate the brain directly."
It is:
- separate memory systems
- allow consolidation
- allow associative recall
- allow forgetting
- track salience and recency
- validate every layer with task outcomes
