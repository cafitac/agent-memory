from pathlib import Path

from agent_memory.adapters.hermes import (
    HermesVerificationResult,
    apply_hermes_verification_results,
    build_hermes_adapter_payload,
    prepare_hermes_memory_context,
    render_hermes_prompt_lines,
    render_hermes_prompt_text,
)
from agent_memory.core.curation import approve_memory, create_candidate_fact, dispute_memory
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.models import MemoryPacket
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def test_build_hermes_adapter_payload_direct_mode_for_high_trust_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "direct.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Direct uses branch pattern EP-###. Project Direct uses branch pattern EP-###.",
        metadata={"project": "project-direct"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Direct",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-direct",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Direct branch pattern EP-###",
        preferred_scope="project:project-direct",
    )
    adapter_payload = build_hermes_adapter_payload(packet)

    assert adapter_payload.response_mode == "direct"
    assert adapter_payload.top_memory.model_dump() == {
        "memory_type": "fact",
        "memory_id": 1,
        "label": "Project Direct",
        "trust_band": "high",
        "has_hidden_alternatives": False,
    }
    assert adapter_payload.pre_answer_checks == []
    assert adapter_payload.answer_guidelines == [
        "Use fact #1 (Project Direct) as the primary memory for the answer.",
        "Answer directly; no uncertainty qualifier is required.",
    ]
    assert adapter_payload.policy_reason_codes == [
        "top_ranked_memory",
        "no_hidden_alternatives_detected",
    ]
    assert adapter_payload.prompt_prefix == "Answer directly using the top-ranked memory."
    assert render_hermes_prompt_lines(adapter_payload) == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
        "Top memory: fact #1 (Project Direct), trust=high, hidden_alternatives=no",
        "Guideline: Use fact #1 (Project Direct) as the primary memory for the answer.",
        "Guideline: Answer directly; no uncertainty qualifier is required.",
        "Reason codes: top_ranked_memory, no_hidden_alternatives_detected",
    ]


def test_prepare_hermes_memory_context_includes_actual_retrieved_fact_content(tmp_path: Path) -> None:
    db_path = tmp_path / "prompt-content.db"
    initialize_database(db_path)
    source = ingest_source_text(
        db_path=db_path,
        source_type="manual_note",
        content="The Hermes memory smoke target phrase is DIRECT_CMD_MEMORY_LAYER_OK.",
        metadata={"project": "agent-memory"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes memory smoke",
        predicate="target_phrase",
        object_ref_or_value="DIRECT_CMD_MEMORY_LAYER_OK",
        evidence_ids=[source.id],
        scope="project:agent-memory",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What is the Hermes memory smoke target phrase?",
        preferred_scope="project:agent-memory",
    )
    context = prepare_hermes_memory_context(packet, top_k=1, max_prompt_lines=8)

    assert "Retrieved fact #1: Hermes memory smoke | target_phrase | DIRECT_CMD_MEMORY_LAYER_OK" in context.prompt_text
    assert "DIRECT_CMD_MEMORY_LAYER_OK" in context.prompt_text


def test_build_hermes_adapter_payload_cautious_mode_for_medium_trust_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "cautious.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes persists sessions locally. SQLite is the backing store.",
        metadata={"project": "hermes"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Hermes",
        predicate="persistence_mode",
        object_ref_or_value="local durable session store",
        evidence_ids=[source.id],
        scope="project:hermes",
        confidence=0.4,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Hermes persistence mode",
        preferred_scope="project:hermes",
    )
    adapter_payload = build_hermes_adapter_payload(packet)

    assert adapter_payload.response_mode == "cautious"
    assert adapter_payload.pre_answer_checks == []
    assert adapter_payload.answer_guidelines == [
        "Use fact #1 (Hermes) as the primary memory for the answer.",
        "Explicitly mention uncertainty when presenting this memory.",
    ]
    assert adapter_payload.policy_reason_codes == [
        "top_ranked_memory",
        "no_hidden_alternatives_detected",
        "medium_uncertainty",
    ]
    assert adapter_payload.prompt_prefix == "Answer using the top-ranked memory, but explicitly mention uncertainty."
    assert render_hermes_prompt_lines(adapter_payload) == [
        "Memory response mode: cautious",
        "Prompt prefix: Answer using the top-ranked memory, but explicitly mention uncertainty.",
        "Top memory: fact #1 (Hermes), trust=medium, hidden_alternatives=no",
        "Guideline: Use fact #1 (Hermes) as the primary memory for the answer.",
        "Guideline: Explicitly mention uncertainty when presenting this memory.",
        "Reason codes: top_ranked_memory, no_hidden_alternatives_detected, medium_uncertainty",
    ]


def test_build_hermes_adapter_payload_verify_first_mode_for_low_trust_hidden_alternatives(tmp_path: Path) -> None:
    db_path = tmp_path / "verify-first.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Z policy note says ALPHA. Project Z policy note says ALPHA.",
        metadata={"project": "project-z"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=low_confidence_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Z policy ALPHA",
        preferred_scope="project:project-z",
    )
    adapter_payload = build_hermes_adapter_payload(packet)

    assert adapter_payload.response_mode == "verify_first"
    assert adapter_payload.pre_answer_checks == [
        "cross_check_hidden_alternatives",
        "corroborate_before_answer",
    ]
    assert adapter_payload.verification_plan.model_dump() == {
        "required": True,
        "fallback_answer_mode": "verify_first",
        "steps": [
            {
                "action": "cross_check_hidden_alternatives",
                "severity": "high",
                "target_memory_type": "fact",
                "target_memory_id": 1,
                "target_label": "Project Z",
                "reason_code": "hidden_alternatives_present",
                "blocking": True,
                "compare_against_memory_ids": [],
                "instruction": "Cross-check fact #1 (Project Z) against hidden alternatives before asserting a final answer.",
            },
            {
                "action": "corroborate_before_answer",
                "severity": "high",
                "target_memory_type": "fact",
                "target_memory_id": 1,
                "target_label": "Project Z",
                "reason_code": "low_trust_requires_corroboration",
                "blocking": True,
                "compare_against_memory_ids": [],
                "instruction": "Corroborate fact #1 (Project Z) before making a definitive claim.",
            },
        ],
    }
    assert adapter_payload.answer_guidelines == [
        "Use fact #1 (Project Z) as the primary memory for the answer.",
        "Surface hidden alternatives before giving the final answer.",
        "Avoid definitive claims until corroborating evidence is found.",
    ]
    assert adapter_payload.policy_reason_codes == [
        "top_ranked_memory",
        "hidden_alternatives_present",
        "low_trust_requires_corroboration",
    ]
    assert adapter_payload.prompt_prefix == "Do not answer definitively yet; verify hidden alternatives or corroborating evidence first."
    assert render_hermes_prompt_lines(adapter_payload) == [
        "Memory response mode: verify_first",
        "Prompt prefix: Do not answer definitively yet; verify hidden alternatives or corroborating evidence first.",
        "Top memory: fact #1 (Project Z), trust=low, hidden_alternatives=yes",
        "Pre-answer check: cross_check_hidden_alternatives",
        "Pre-answer check: corroborate_before_answer",
        "Verification step: cross_check_hidden_alternatives, severity=high, blocking=yes, target=fact #1, compare_against=none, reason=hidden_alternatives_present",
        "Verification step: corroborate_before_answer, severity=high, blocking=yes, target=fact #1, compare_against=none, reason=low_trust_requires_corroboration",
        "Guideline: Use fact #1 (Project Z) as the primary memory for the answer.",
        "Guideline: Surface hidden alternatives before giving the final answer.",
        "Guideline: Avoid definitive claims until corroborating evidence is found.",
        "Reason codes: top_ranked_memory, hidden_alternatives_present, low_trust_requires_corroboration",
    ]


def test_build_hermes_adapter_payload_includes_alternative_memories_for_top_n_context(tmp_path: Path) -> None:
    db_path = tmp_path / "alternatives.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Project Multi uses branch pattern EP-101. "
            "Project Multi workflow owner is Team Mercury. "
            "Project Multi deploy environment is staging."
        ),
        metadata={"project": "project-multi"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Multi",
        predicate="branch_pattern",
        object_ref_or_value="EP-101",
        evidence_ids=[source.id],
        scope="project:project-multi",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Multi",
        predicate="workflow_owner",
        object_ref_or_value="Team Mercury",
        evidence_ids=[source.id],
        scope="project:project-multi",
        confidence=0.72,
    )
    deploy_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Multi",
        predicate="deploy_environment",
        object_ref_or_value="staging",
        evidence_ids=[source.id],
        scope="project:project-multi",
        confidence=0.66,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=branch_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=owner_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=deploy_fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Multi branch workflow deploy",
        preferred_scope="project:project-multi",
    )
    adapter_payload = build_hermes_adapter_payload(packet, top_k=3)

    expected_memory_ids = [trace.memory_id for trace in packet.retrieval_trace[:3]]
    assert len(expected_memory_ids) == 3
    assert set(expected_memory_ids) == {branch_fact.id, owner_fact.id, deploy_fact.id}

    assert adapter_payload.top_memory.model_dump() == {
        "memory_type": "fact",
        "memory_id": expected_memory_ids[0],
        "label": "Project Multi",
        "trust_band": "high",
        "has_hidden_alternatives": False,
    }
    assert [memory.model_dump() for memory in adapter_payload.alternative_memories] == [
        {
            "memory_type": "fact",
            "memory_id": expected_memory_ids[1],
            "label": "Project Multi",
            "trust_band": "high",
            "has_hidden_alternatives": False,
        },
        {
            "memory_type": "fact",
            "memory_id": expected_memory_ids[2],
            "label": "Project Multi",
            "trust_band": "high",
            "has_hidden_alternatives": False,
        },
    ]
    assert render_hermes_prompt_lines(adapter_payload) == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
        f"Top memory: fact #{expected_memory_ids[0]} (Project Multi), trust=high, hidden_alternatives=no",
        f"Alternative memory: fact #{expected_memory_ids[1]} (Project Multi), trust=high, hidden_alternatives=no",
        f"Alternative memory: fact #{expected_memory_ids[2]} (Project Multi), trust=high, hidden_alternatives=no",
        f"Guideline: Use fact #{expected_memory_ids[0]} (Project Multi) as the primary memory for the answer.",
        "Guideline: Answer directly; no uncertainty qualifier is required.",
        "Reason codes: top_ranked_memory, no_hidden_alternatives_detected",
    ]
    assert render_hermes_prompt_text(adapter_payload).splitlines()[3] == (
        f"Alternative memory: fact #{expected_memory_ids[1]} (Project Multi), trust=high, hidden_alternatives=no"
    )


def test_apply_hermes_verification_results_allows_cautious_answer_when_blocking_steps_pass(tmp_path: Path) -> None:
    db_path = tmp_path / "verification-results-pass.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Verify Result policy note says ALPHA. Project Verify Result policy note says ALPHA.",
        metadata={"project": "project-verify-result"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Verify Result",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:project-verify-result",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Verify Result",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:project-verify-result",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=low_confidence_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Verify Result policy ALPHA",
        preferred_scope="project:project-verify-result",
    )
    context = prepare_hermes_memory_context(packet)
    outcome = apply_hermes_verification_results(
        context,
        [
            HermesVerificationResult(
                step_action="cross_check_hidden_alternatives",
                status="passed",
                evidence_summary="No active approved alternative contradicted the primary memory.",
                target_memory_type="fact",
                target_memory_id=1,
            ),
            HermesVerificationResult(
                step_action="corroborate_before_answer",
                status="passed",
                evidence_summary="Corroborating source text repeated the ALPHA policy note.",
                target_memory_type="fact",
                target_memory_id=1,
            ),
        ],
    )

    assert outcome.should_answer_now is True
    assert outcome.should_verify_first is False
    assert outcome.response_mode_after_verification == "cautious"
    assert outcome.unresolved_blocking_steps == []
    assert outcome.prompt_text.splitlines()[-2:] == [
        "Verification result: cross_check_hidden_alternatives, status=passed, target=fact #1, evidence=No active approved alternative contradicted the primary memory.",
        "Verification result: corroborate_before_answer, status=passed, target=fact #1, evidence=Corroborating source text repeated the ALPHA policy note.",
    ]


def test_apply_hermes_verification_results_keeps_verify_first_when_blocking_step_is_unavailable(tmp_path: Path) -> None:
    db_path = tmp_path / "verification-results-unavailable.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Verify Block policy note says ALPHA. Project Verify Block policy note says ALPHA.",
        metadata={"project": "project-verify-block"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Verify Block",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:project-verify-block",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Verify Block",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:project-verify-block",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=low_confidence_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Verify Block policy ALPHA",
        preferred_scope="project:project-verify-block",
    )
    context = prepare_hermes_memory_context(packet)
    outcome = apply_hermes_verification_results(
        context,
        [
            HermesVerificationResult(
                step_action="cross_check_hidden_alternatives",
                status="passed",
                evidence_summary="No active approved alternative contradicted the primary memory.",
                target_memory_type="fact",
                target_memory_id=1,
            ),
            HermesVerificationResult(
                step_action="corroborate_before_answer",
                status="unavailable",
                evidence_summary="The harness did not have a corroborating source lookup tool available.",
                target_memory_type="fact",
                target_memory_id=1,
            ),
        ],
    )

    assert outcome.should_answer_now is False
    assert outcome.should_verify_first is True
    assert outcome.response_mode_after_verification == "verify_first"
    assert [step.action for step in outcome.unresolved_blocking_steps] == ["corroborate_before_answer"]
    assert "Verification result: corroborate_before_answer, status=unavailable" in outcome.prompt_text


def test_prepare_hermes_memory_context_trims_prompt_lines_without_mutating_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-budget.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Project Budget branch pattern is EP-201. "
            "Project Budget owner is Team Atlas. "
            "Project Budget deploy target is production."
        ),
        metadata={"project": "project-budget"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Budget",
        predicate="branch_pattern",
        object_ref_or_value="EP-201",
        evidence_ids=[source.id],
        scope="project:project-budget",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Budget",
        predicate="owner",
        object_ref_or_value="Team Atlas",
        evidence_ids=[source.id],
        scope="project:project-budget",
        confidence=0.9,
    )
    deploy_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Budget",
        predicate="deploy_target",
        object_ref_or_value="production",
        evidence_ids=[source.id],
        scope="project:project-budget",
        confidence=0.9,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=branch_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=owner_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=deploy_fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Budget branch owner deploy",
        preferred_scope="project:project-budget",
    )
    context = prepare_hermes_memory_context(
        packet,
        top_k=3,
        max_prompt_lines=5,
        max_alternatives=1,
        include_reason_codes=False,
    )

    assert len(context.prompt_text.splitlines()) == 5
    assert context.prompt_text.splitlines() == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
        "Top memory: fact #1 (Project Budget), trust=high, hidden_alternatives=no",
        "Alternative memory: fact #2 (Project Budget), trust=high, hidden_alternatives=no",
        "Guideline: Use fact #1 (Project Budget) as the primary memory for the answer.",
    ]
    assert len(context.payload.alternative_memories) == 2
    assert context.payload.policy_reason_codes == [
        "top_ranked_memory",
        "no_hidden_alternatives_detected",
    ]


def test_prepare_hermes_memory_context_trims_prompt_chars_without_mutating_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-char-budget.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Project Char Budget branch pattern is EP-301. "
            "Project Char Budget owner is Team Longform. "
            "Project Char Budget deploy target is production."
        ),
        metadata={"project": "project-char-budget"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Char Budget",
        predicate="branch_pattern",
        object_ref_or_value="EP-301",
        evidence_ids=[source.id],
        scope="project:project-char-budget",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Char Budget",
        predicate="owner",
        object_ref_or_value="Team Longform",
        evidence_ids=[source.id],
        scope="project:project-char-budget",
        confidence=0.9,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=branch_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=owner_fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Char Budget branch owner",
        preferred_scope="project:project-char-budget",
    )
    full_context = prepare_hermes_memory_context(packet, top_k=2, include_reason_codes=False)
    trimmed_context = prepare_hermes_memory_context(
        packet,
        top_k=2,
        max_prompt_chars=150,
        include_reason_codes=False,
    )

    assert len(trimmed_context.prompt_text) <= 150
    assert trimmed_context.prompt_text.splitlines() == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
    ]
    assert len(full_context.prompt_text) > len(trimmed_context.prompt_text)
    assert len(trimmed_context.payload.alternative_memories) == 1
    assert trimmed_context.payload.answer_guidelines == full_context.payload.answer_guidelines



def test_prepare_hermes_memory_context_trims_prompt_tokens_without_mutating_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-token-budget.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content=(
            "Project Token Budget branch pattern is EP-401. "
            "Project Token Budget owner is Team Token. "
            "Project Token Budget deploy target is production."
        ),
        metadata={"project": "project-token-budget"},
    )
    branch_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Token Budget",
        predicate="branch_pattern",
        object_ref_or_value="EP-401",
        evidence_ids=[source.id],
        scope="project:project-token-budget",
        confidence=0.95,
    )
    owner_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Token Budget",
        predicate="owner",
        object_ref_or_value="Team Token",
        evidence_ids=[source.id],
        scope="project:project-token-budget",
        confidence=0.9,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=branch_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=owner_fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Token Budget branch owner",
        preferred_scope="project:project-token-budget",
    )
    full_context = prepare_hermes_memory_context(packet, top_k=2, include_reason_codes=False)
    trimmed_context = prepare_hermes_memory_context(
        packet,
        top_k=2,
        max_prompt_tokens=24,
        include_reason_codes=False,
    )

    assert len(trimmed_context.prompt_text) <= 96
    assert trimmed_context.prompt_text.splitlines() == [
        "Memory response mode: direct",
        "Prompt prefix: Answer directly using the top-ranked memory.",
    ]
    assert len(full_context.prompt_text) > len(trimmed_context.prompt_text)
    assert len(trimmed_context.payload.alternative_memories) == 1
    assert trimmed_context.payload.answer_guidelines == full_context.payload.answer_guidelines



def test_prepare_hermes_memory_context_keeps_blocking_verification_steps_when_trimming_prompt(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-budget-verify.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Budget Verify policy says ALPHA. Project Budget Verify policy says ALPHA.",
        metadata={"project": "project-budget-verify"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Budget Verify",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:project-budget-verify",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Budget Verify",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:project-budget-verify",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=low_confidence_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Budget Verify policy ALPHA",
        preferred_scope="project:project-budget-verify",
    )
    context = prepare_hermes_memory_context(
        packet,
        max_prompt_lines=5,
        max_verification_steps=1,
        max_guidelines=1,
    )

    assert context.should_verify_first is True
    assert [step.action for step in context.blocking_steps] == [
        "cross_check_hidden_alternatives",
        "corroborate_before_answer",
    ]
    assert context.prompt_text.count("Verification step:") == 1
    assert "Verification step: cross_check_hidden_alternatives" in context.prompt_text
    assert "Verification step: corroborate_before_answer" not in context.prompt_text
    assert len(context.prompt_text.splitlines()) == 5


def test_prepare_hermes_memory_context_allows_immediate_answer_for_direct_mode(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-direct.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Direct uses branch pattern EP-###. Project Direct uses branch pattern EP-###.",
        metadata={"project": "project-direct"},
    )
    fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Direct",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-direct",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=fact.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Direct branch pattern EP-###",
        preferred_scope="project:project-direct",
    )
    context = prepare_hermes_memory_context(packet, top_k=1)

    assert context.should_answer_now is True
    assert context.should_verify_first is False
    assert context.blocking_steps == []
    assert context.payload.response_mode == "direct"
    assert context.prompt_text.splitlines()[0] == "Memory response mode: direct"
    assert context.model_dump()["payload"]["top_memory"] == {
        "memory_type": "fact",
        "memory_id": 1,
        "label": "Project Direct",
        "trust_band": "high",
        "has_hidden_alternatives": False,
    }


def test_prepare_hermes_memory_context_exposes_blocking_verification_steps(tmp_path: Path) -> None:
    db_path = tmp_path / "integration-verify.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project Z policy note says ALPHA. Project Z policy note says ALPHA.",
        metadata={"project": "project-z"},
    )
    low_confidence_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="policy",
        object_ref_or_value="ALPHA",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.05,
    )
    hidden_alternative = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project Z",
        predicate="policy",
        object_ref_or_value="BETA",
        evidence_ids=[source.id],
        scope="project:project-z",
        confidence=0.95,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=low_confidence_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=hidden_alternative.id)

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="Project Z policy ALPHA",
        preferred_scope="project:project-z",
    )
    context = prepare_hermes_memory_context(packet, top_k=2)

    assert context.should_answer_now is False
    assert context.should_verify_first is True
    assert [step.action for step in context.blocking_steps] == [
        "cross_check_hidden_alternatives",
        "corroborate_before_answer",
    ]
    assert context.payload.response_mode == "verify_first"
    assert context.payload.verification_plan.required is True
    assert context.prompt_text.count("Verification step:") == 2
    assert "Verification step: cross_check_hidden_alternatives" in context.prompt_text


def test_build_hermes_adapter_payload_falls_back_safely_when_no_memory_is_available() -> None:
    packet = MemoryPacket(query="unknown topic")

    adapter_payload = build_hermes_adapter_payload(packet)

    assert adapter_payload.response_mode == "verify_first"
    assert adapter_payload.top_memory is None
    assert adapter_payload.pre_answer_checks == ["gather_more_evidence"]
    assert adapter_payload.answer_guidelines == [
        "No reliable memory was retrieved.",
        "Ask for clarification or gather more evidence before answering.",
    ]
    assert adapter_payload.policy_reason_codes == []
    assert adapter_payload.verification_plan.model_dump() == {
        "required": True,
        "fallback_answer_mode": "verify_first",
        "steps": [
            {
                "action": "gather_more_evidence",
                "severity": "high",
                "target_memory_type": None,
                "target_memory_id": None,
                "target_label": None,
                "reason_code": None,
                "blocking": True,
                "compare_against_memory_ids": [],
                "instruction": "Gather more evidence before answering because no reliable memory was retrieved.",
            },
        ],
    }
    assert adapter_payload.prompt_prefix == "No reliable memory is available yet; gather more evidence before answering."
    assert render_hermes_prompt_lines(adapter_payload) == [
        "Memory response mode: verify_first",
        "Prompt prefix: No reliable memory is available yet; gather more evidence before answering.",
        "Top memory: none",
        "Pre-answer check: gather_more_evidence",
        "Verification step: gather_more_evidence, severity=high, blocking=yes, target=none, compare_against=none, reason=none",
        "Guideline: No reliable memory was retrieved.",
        "Guideline: Ask for clarification or gather more evidence before answering.",
        "Reason codes: none",
    ]
