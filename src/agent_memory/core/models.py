from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

MemoryStatus = Literal["candidate", "approved", "disputed", "deprecated"]


class SourceRecord(BaseModel):
    id: int
    source_type: str
    adapter: str | None = None
    external_ref: str | None = None
    created_at: str
    content: str
    checksum: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class Fact(BaseModel):
    id: int
    subject_ref: str
    predicate: str
    object_ref_or_value: str
    evidence_ids: list[int] = Field(default_factory=list)
    confidence: float
    valid_from: str | None = None
    valid_to: str | None = None
    scope: str
    status: MemoryStatus
    searchable_text: str


class Procedure(BaseModel):
    id: int
    name: str
    trigger_context: str
    preconditions: list[str] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    evidence_ids: list[int] = Field(default_factory=list)
    success_rate: float = 0.0
    scope: str
    status: MemoryStatus
    searchable_text: str


class Episode(BaseModel):
    id: int
    title: str
    summary: str
    started_at: str | None = None
    ended_at: str | None = None
    source_ids: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    importance_score: float = 0.0
    scope: str = "global"
    status: MemoryStatus
    searchable_text: str


class Relation(BaseModel):
    id: int
    from_ref: str
    relation_type: str
    to_ref: str
    weight: float = 1.0
    evidence_ids: list[int] = Field(default_factory=list)
    confidence: float = 0.5
    valid_from: str | None = None
    valid_to: str | None = None


class ProvenanceSummary(BaseModel):
    source_id: int
    source_type: str
    created_at: str
    excerpt: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalTraceEntry(BaseModel):
    memory_type: Literal["fact", "procedure", "episode"]
    memory_id: int
    label: str
    scope: str | None = None
    scope_priority: int
    text_match_count: int = 0
    relation_match_count: int = 0
    matched_terms: list[str] = Field(default_factory=list)
    supporting_relation_ids: list[int] = Field(default_factory=list)
    rank_value: float = 0.0
    scope_score: float = 0.0
    lexical_score: float = 0.0
    relation_score: float = 0.0
    recency_score: float = 0.0
    reinforcement_score: float = 0.0
    conflict_count: int = 0
    conflict_penalty: float = 0.0
    hidden_disputed_alternatives_count: int = 0
    hidden_deprecated_alternatives_count: int = 0
    hidden_alternative_count: int = 0
    rank_signal_score: float = 0.0
    total_score: float = 0.0


class MemoryTrustSummary(BaseModel):
    memory_type: Literal["fact", "procedure", "episode"]
    memory_id: int
    label: str
    uncertainty_score: float = 0.0
    review_risk_score: float = 0.0
    has_hidden_alternatives: bool = False
    trust_band: Literal["high", "medium", "low"] = "medium"


PolicyHintReasonCode = Literal[
    "top_ranked_memory",
    "no_hidden_alternatives_detected",
    "hidden_alternatives_present",
    "medium_uncertainty",
    "low_trust_requires_corroboration",
]


class PolicyHint(BaseModel):
    action: Literal[
        "prefer",
        "no_hidden_alternatives",
        "surface_hidden_alternatives",
        "cross_check",
        "mention_uncertainty",
        "avoid_definitive",
    ]
    target_memory_type: Literal["fact", "procedure", "episode"]
    target_memory_id: int
    target_label: str
    severity: Literal["low", "medium", "high"]
    reason_code: PolicyHintReasonCode
    message: str


class DecisionSummary(BaseModel):
    recommended_answer_mode: Literal["direct", "cautious", "verify_first"]
    target_memory_type: Literal["fact", "procedure", "episode"]
    target_memory_id: int
    target_label: str
    trust_band: Literal["high", "medium", "low"]
    has_hidden_alternatives: bool = False
    should_mention_uncertainty: bool = False
    requires_cross_check: bool = False
    should_avoid_definitive: bool = False
    reason_codes: list[PolicyHintReasonCode] = Field(default_factory=list)


class VerificationStep(BaseModel):
    action: Literal[
        "gather_more_evidence",
        "cross_check_hidden_alternatives",
        "corroborate_before_answer",
    ]
    severity: Literal["low", "medium", "high"]
    target_memory_type: Literal["fact", "procedure", "episode"] | None = None
    target_memory_id: int | None = None
    target_label: str | None = None
    reason_code: PolicyHintReasonCode | None = None
    blocking: bool = False
    compare_against_memory_ids: list[int] = Field(default_factory=list)
    instruction: str


class VerificationPlan(BaseModel):
    required: bool = False
    fallback_answer_mode: Literal["direct", "cautious", "verify_first"] = "direct"
    steps: list[VerificationStep] = Field(default_factory=list)


class MemoryPacket(BaseModel):
    query: str
    working_hints: list[str] = Field(default_factory=list)
    policy_hints: list[PolicyHint] = Field(default_factory=list)
    decision_summary: DecisionSummary | None = None
    verification_plan: VerificationPlan = Field(default_factory=VerificationPlan)
    episodic_context: list[Episode] = Field(default_factory=list)
    semantic_facts: list[Fact] = Field(default_factory=list)
    procedural_guidance: list[Procedure] = Field(default_factory=list)
    related_relations: list[Relation] = Field(default_factory=list)
    provenance: list[ProvenanceSummary] = Field(default_factory=list)
    retrieval_trace: list[RetrievalTraceEntry] = Field(default_factory=list)
    trust_summaries: list[MemoryTrustSummary] = Field(default_factory=list)


class KbExportedFile(BaseModel):
    path: str
    memory_type: Literal["index", "fact", "procedure", "episode"]
    item_count: int


class KbExportCounts(BaseModel):
    facts: int = 0
    procedures: int = 0
    episodes: int = 0
    total_items: int = 0


class KbExportResult(BaseModel):
    output_dir: str
    scope: str | None = None
    files: list[KbExportedFile] = Field(default_factory=list)
    counts: KbExportCounts = Field(default_factory=KbExportCounts)
    source_ids: list[int] = Field(default_factory=list)
