import json
import sqlite3
import subprocess
from pathlib import Path

from agent_memory.core.curation import approve_memory, create_candidate_fact, create_episode, create_relation, deprecate_memory, dispute_memory
from agent_memory.core.ingestion import ingest_source_text
from agent_memory.core.retrieval import retrieve_memory_packet
from agent_memory.storage.sqlite import initialize_database


def _expected_review_risk_score(conflict_count: int, hidden_alternative_count: int) -> float:
    return min(1.0, (0.35 * conflict_count) + (0.15 * hidden_alternative_count))


def _expected_uncertainty_score(
    *,
    rank_value: float,
    review_risk_score: float,
    text_match_count: int,
    relation_match_count: int,
    reinforcement_score: float,
) -> float:
    support_penalty = 0.2 if text_match_count == 0 and relation_match_count == 0 else 0.0
    reinforcement_credit = min(0.25, reinforcement_score * 0.1)
    return min(
        1.0,
        max(
            0.0,
            ((1.0 - max(0.0, min(rank_value, 1.0))) * 0.6)
            + (review_risk_score * 0.3)
            + support_penalty
            - reinforcement_credit,
        ),
    )


def test_retrieval_trace_explains_scope_and_relation_reasoning(tmp_path: Path) -> None:
    db_path = tmp_path / "agent-memory.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Hermes persists sessions locally. SQLite is the backing store. Workspace notes explain scheduled job rollout.",
        metadata={"project": "hermes", "workspace": "example-workspace"},
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

    episode = create_episode(
        db_path=db_path,
        title="Scheduled job refactor",
        summary="Workspace-wide operational notes for scheduled job refactor.",
        source_ids=[source.id],
        tags=["daily-task", "workspace"],
        importance_score=0.9,
        scope="workspace:example-workspace",
        status="approved",
    )

    relation = create_relation(
        db_path=db_path,
        from_ref="Hermes",
        relation_type="uses_storage",
        to_ref="SQLite",
        evidence_ids=[source.id],
        confidence=0.9,
    )

    relation_packet = retrieve_memory_packet(
        db_path=db_path,
        query="Which system uses SQLite?",
        preferred_scope="project:hermes",
    )

    fact_trace = next(
        trace for trace in relation_packet.retrieval_trace if trace.memory_type == "fact" and trace.memory_id == fact.id
    )
    fact_trust = next(
        trust for trust in relation_packet.trust_summaries if trust.memory_type == "fact" and trust.memory_id == fact.id
    )
    assert fact_trace.label == "Hermes"
    assert fact_trace.scope == "project:hermes"
    assert fact_trace.scope_priority == 0
    assert fact_trace.text_match_count == 0
    assert fact_trace.relation_match_count == 1
    assert fact_trace.supporting_relation_ids == [relation.id]
    assert "sqlite" in fact_trace.matched_terms
    assert fact_trace.scope_score > 0
    assert fact_trace.relation_score > 0
    assert fact_trace.lexical_score == 0
    assert fact_trace.rank_signal_score == fact_trace.rank_value
    assert fact_trace.total_score == (
        fact_trace.scope_score
        + fact_trace.lexical_score
        + fact_trace.relation_score
        + fact_trace.recency_score
        + fact_trace.reinforcement_score
        + fact_trace.conflict_penalty
        + fact_trace.rank_signal_score
    )
    assert fact_trust.label == "Hermes"
    assert fact_trust.has_hidden_alternatives is False
    assert fact_trust.review_risk_score == _expected_review_risk_score(
        fact_trace.conflict_count,
        fact_trace.hidden_alternative_count,
    )
    assert fact_trust.uncertainty_score == _expected_uncertainty_score(
        rank_value=fact_trace.rank_value,
        review_risk_score=fact_trust.review_risk_score,
        text_match_count=fact_trace.text_match_count,
        relation_match_count=fact_trace.relation_match_count,
        reinforcement_score=fact_trace.reinforcement_score,
    )
    assert fact_trust.trust_band == "medium"
    assert relation_packet.decision_summary.model_dump() == {
        "recommended_answer_mode": "cautious",
        "target_memory_type": "fact",
        "target_memory_id": 1,
        "target_label": "Hermes",
        "trust_band": "medium",
        "has_hidden_alternatives": False,
        "should_mention_uncertainty": True,
        "requires_cross_check": False,
        "should_avoid_definitive": False,
        "reason_codes": [
            "top_ranked_memory",
            "no_hidden_alternatives_detected",
            "medium_uncertainty",
        ],
    }
    assert [hint.model_dump() for hint in relation_packet.policy_hints] == [
        {
            "action": "prefer",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "medium",
            "reason_code": "top_ranked_memory",
            "message": "Use fact #1 (Hermes) with medium trust.",
        },
        {
            "action": "no_hidden_alternatives",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "low",
            "reason_code": "no_hidden_alternatives_detected",
            "message": "No hidden alternatives detected for the top memory.",
        },
        {
            "action": "mention_uncertainty",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "medium",
            "reason_code": "medium_uncertainty",
            "message": "Mention uncertainty when presenting this memory.",
        },
    ]

    episode_packet = retrieve_memory_packet(
        db_path=db_path,
        query="What happened in the scheduled job refactor?",
        preferred_scope="project:example-backend",
    )

    episode_trace = next(
        trace for trace in episode_packet.retrieval_trace if trace.memory_type == "episode" and trace.memory_id == episode.id
    )
    assert episode_trace.scope == "workspace:example-workspace"
    assert episode_trace.scope_priority == 1
    assert episode_trace.text_match_count >= 3
    assert episode_trace.relation_match_count == 0
    assert episode_trace.lexical_score > 0
    assert episode_trace.scope_score > 0
    assert episode_trace.total_score > episode_trace.rank_signal_score


def test_retrieval_decision_summary_recommends_direct_for_high_trust_without_hidden_alternatives(tmp_path: Path) -> None:
    db_path = tmp_path / "direct-mode.db"
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

    assert packet.trust_summaries[0].trust_band == "high"
    assert packet.trust_summaries[0].has_hidden_alternatives is False
    assert packet.decision_summary.model_dump() == {
        "recommended_answer_mode": "direct",
        "target_memory_type": "fact",
        "target_memory_id": 1,
        "target_label": "Project Direct",
        "trust_band": "high",
        "has_hidden_alternatives": False,
        "should_mention_uncertainty": False,
        "requires_cross_check": False,
        "should_avoid_definitive": False,
        "reason_codes": [
            "top_ranked_memory",
            "no_hidden_alternatives_detected",
        ],
    }


def test_retrieval_trace_recency_prefers_newer_approved_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "recency.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="SQLite policy note. SQLite policy note.",
        metadata={"project": "memory"},
    )

    older_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="OldMemory",
        predicate="policy",
        object_ref_or_value="SQLite policy note",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.5,
    )
    newer_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="NewMemory",
        predicate="policy",
        object_ref_or_value="SQLite policy note",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.5,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=older_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=newer_fact.id)

    with sqlite3.connect(db_path) as connection:
        connection.execute("UPDATE facts SET approved_at = ? WHERE id = ?", ("2024-01-01 00:00:00", older_fact.id))
        connection.execute("UPDATE facts SET approved_at = ? WHERE id = ?", ("2024-01-10 00:00:00", newer_fact.id))

    packet = retrieve_memory_packet(db_path=db_path, query="SQLite policy")

    old_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == older_fact.id)
    new_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == newer_fact.id)
    assert new_trace.recency_score > old_trace.recency_score
    assert packet.semantic_facts[0].id == newer_fact.id


def test_retrieval_trace_reinforcement_prefers_reused_memory(tmp_path: Path) -> None:
    db_path = tmp_path / "reinforcement.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Runbook note. Runbook note.",
        metadata={"project": "memory"},
    )

    baseline_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="BaselineRunbook",
        predicate="guide",
        object_ref_or_value="Runbook note",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.5,
    )
    reused_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="ReusedRunbook",
        predicate="guide",
        object_ref_or_value="Runbook note",
        evidence_ids=[source.id],
        scope="global",
        confidence=0.5,
    )
    approve_memory(db_path=db_path, memory_type="fact", memory_id=baseline_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=reused_fact.id)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE facts SET approved_at = ?, retrieval_count = ?, reinforcement_count = ? WHERE id = ?",
            ("2024-01-01 00:00:00", 0, 0.0, baseline_fact.id),
        )
        connection.execute(
            "UPDATE facts SET approved_at = ?, retrieval_count = ?, reinforcement_count = ? WHERE id = ?",
            ("2024-01-01 00:00:00", 4, 4.0, reused_fact.id),
        )

    packet = retrieve_memory_packet(db_path=db_path, query="Runbook note")

    baseline_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == baseline_fact.id)
    reused_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == reused_fact.id)
    assert reused_trace.reinforcement_score > baseline_trace.reinforcement_score
    assert packet.semantic_facts[0].id == reused_fact.id


def test_retrieval_trace_conflict_penalty_demotes_conflicting_fact_and_excludes_non_approved(tmp_path: Path) -> None:
    db_path = tmp_path / "conflict.db"
    initialize_database(db_path)

    source = ingest_source_text(
        db_path=db_path,
        source_type="transcript",
        content="Project X branch pattern notes include EP and YY variants.",
        metadata={"project": "project-x"},
    )

    canonical_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="EP-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.8,
    )
    conflicting_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="YY-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.8,
    )
    disputed_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="ZZ-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.95,
    )
    deprecated_fact = create_candidate_fact(
        db_path=db_path,
        subject_ref="Project X",
        predicate="branch_pattern",
        object_ref_or_value="AA-###",
        evidence_ids=[source.id],
        scope="project:project-x",
        confidence=0.95,
    )

    approve_memory(db_path=db_path, memory_type="fact", memory_id=canonical_fact.id)
    approve_memory(db_path=db_path, memory_type="fact", memory_id=conflicting_fact.id)
    dispute_memory(db_path=db_path, memory_type="fact", memory_id=disputed_fact.id)
    deprecate_memory(db_path=db_path, memory_type="fact", memory_id=deprecated_fact.id)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE facts SET retrieval_count = ?, reinforcement_count = ? WHERE id = ?",
            (3, 3.0, canonical_fact.id),
        )
        connection.execute(
            "UPDATE facts SET retrieval_count = ?, reinforcement_count = ? WHERE id = ?",
            (0, 0.0, conflicting_fact.id),
        )

    packet = retrieve_memory_packet(
        db_path=db_path,
        query="What branch pattern does Project X use?",
        preferred_scope="project:project-x",
    )

    returned_ids = [fact.id for fact in packet.semantic_facts]
    assert canonical_fact.id in returned_ids
    assert conflicting_fact.id in returned_ids
    assert disputed_fact.id not in returned_ids
    assert deprecated_fact.id not in returned_ids
    assert packet.semantic_facts[0].id == canonical_fact.id

    canonical_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == canonical_fact.id)
    conflicting_trace = next(trace for trace in packet.retrieval_trace if trace.memory_id == conflicting_fact.id)
    canonical_trust = next(trust for trust in packet.trust_summaries if trust.memory_id == canonical_fact.id)
    conflicting_trust = next(trust for trust in packet.trust_summaries if trust.memory_id == conflicting_fact.id)
    assert canonical_trace.conflict_count == 1
    assert conflicting_trace.conflict_count == 1
    assert canonical_trace.hidden_disputed_alternatives_count == 1
    assert canonical_trace.hidden_deprecated_alternatives_count == 1
    assert canonical_trace.hidden_alternative_count == 2
    assert conflicting_trace.hidden_disputed_alternatives_count == 1
    assert conflicting_trace.hidden_deprecated_alternatives_count == 1
    assert conflicting_trace.hidden_alternative_count == 2
    assert canonical_trace.conflict_penalty < 0
    assert conflicting_trace.conflict_penalty < 0
    assert canonical_trace.reinforcement_score > conflicting_trace.reinforcement_score
    assert canonical_trace.total_score > conflicting_trace.total_score
    assert canonical_trust.has_hidden_alternatives is True
    assert conflicting_trust.has_hidden_alternatives is True
    assert canonical_trust.review_risk_score == _expected_review_risk_score(
        canonical_trace.conflict_count,
        canonical_trace.hidden_alternative_count,
    )
    assert conflicting_trust.review_risk_score == _expected_review_risk_score(
        conflicting_trace.conflict_count,
        conflicting_trace.hidden_alternative_count,
    )
    assert canonical_trust.uncertainty_score == _expected_uncertainty_score(
        rank_value=canonical_trace.rank_value,
        review_risk_score=canonical_trust.review_risk_score,
        text_match_count=canonical_trace.text_match_count,
        relation_match_count=canonical_trace.relation_match_count,
        reinforcement_score=canonical_trace.reinforcement_score,
    )
    assert conflicting_trust.uncertainty_score == _expected_uncertainty_score(
        rank_value=conflicting_trace.rank_value,
        review_risk_score=conflicting_trust.review_risk_score,
        text_match_count=conflicting_trace.text_match_count,
        relation_match_count=conflicting_trace.relation_match_count,
        reinforcement_score=conflicting_trace.reinforcement_score,
    )
    assert canonical_trust.uncertainty_score < conflicting_trust.uncertainty_score
    assert canonical_trust.trust_band == "high"
    assert conflicting_trust.trust_band == "medium"
    assert packet.decision_summary.model_dump() == {
        "recommended_answer_mode": "verify_first",
        "target_memory_type": "fact",
        "target_memory_id": 1,
        "target_label": "Project X",
        "trust_band": "high",
        "has_hidden_alternatives": True,
        "should_mention_uncertainty": False,
        "requires_cross_check": True,
        "should_avoid_definitive": False,
        "reason_codes": [
            "top_ranked_memory",
            "hidden_alternatives_present",
        ],
    }
    assert packet.verification_plan.model_dump() == {
        "required": True,
        "fallback_answer_mode": "verify_first",
        "steps": [
            {
                "action": "cross_check_hidden_alternatives",
                "severity": "high",
                "target_memory_type": "fact",
                "target_memory_id": 1,
                "target_label": "Project X",
                "reason_code": "hidden_alternatives_present",
                "blocking": True,
                "compare_against_memory_ids": [2],
                "instruction": "Cross-check fact #1 (Project X) against ranked alternatives before asserting a final answer.",
            },
        ],
    }
    assert [hint.model_dump() for hint in packet.policy_hints] == [
        {
            "action": "prefer",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project X",
            "severity": "high",
            "reason_code": "top_ranked_memory",
            "message": "Use fact #1 (Project X) with high trust.",
        },
        {
            "action": "surface_hidden_alternatives",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project X",
            "severity": "medium",
            "reason_code": "hidden_alternatives_present",
            "message": "Mention that 2 hidden alternatives exist behind the top memory.",
        },
        {
            "action": "cross_check",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project X",
            "severity": "high",
            "reason_code": "hidden_alternatives_present",
            "message": "Cross-check this memory against hidden alternatives before asserting a final answer.",
        },
    ]


def test_retrieval_trace_low_trust_emits_avoid_definitive_hint(tmp_path: Path) -> None:
    db_path = tmp_path / "low-trust.db"
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

    top_trust = packet.trust_summaries[0]
    assert top_trust.memory_id == low_confidence_fact.id
    assert top_trust.trust_band == "low"
    assert top_trust.has_hidden_alternatives is True
    assert packet.decision_summary.model_dump() == {
        "recommended_answer_mode": "verify_first",
        "target_memory_type": "fact",
        "target_memory_id": 1,
        "target_label": "Project Z",
        "trust_band": "low",
        "has_hidden_alternatives": True,
        "should_mention_uncertainty": False,
        "requires_cross_check": True,
        "should_avoid_definitive": True,
        "reason_codes": [
            "top_ranked_memory",
            "hidden_alternatives_present",
            "low_trust_requires_corroboration",
        ],
    }
    assert packet.verification_plan.model_dump() == {
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
    assert [hint.model_dump() for hint in packet.policy_hints] == [
        {
            "action": "prefer",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project Z",
            "severity": "low",
            "reason_code": "top_ranked_memory",
            "message": "Use fact #1 (Project Z) with low trust.",
        },
        {
            "action": "surface_hidden_alternatives",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project Z",
            "severity": "medium",
            "reason_code": "hidden_alternatives_present",
            "message": "Mention that 1 hidden alternative exists behind the top memory.",
        },
        {
            "action": "cross_check",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project Z",
            "severity": "high",
            "reason_code": "hidden_alternatives_present",
            "message": "Cross-check this memory against hidden alternatives before asserting a final answer.",
        },
        {
            "action": "avoid_definitive",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Project Z",
            "severity": "high",
            "reason_code": "low_trust_requires_corroboration",
            "message": "Avoid definitive claims until corroborating evidence is found.",
        },
    ]


def test_cli_retrieve_includes_retrieval_trace_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "cli-trace.db"
    cwd = Path(__file__).resolve().parents[1]

    subprocess.run(["uv", "run", "agent-memory", "init", str(db_path)], cwd=cwd, check=True, capture_output=True, text=True)
    subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "ingest-source",
            str(db_path),
            "transcript",
            "Hermes persists sessions locally. SQLite is the backing store.",
            "--metadata-json",
            '{"project":"hermes"}',
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "create-fact",
            str(db_path),
            "Hermes",
            "persistence_mode",
            "local durable session store",
            "project:hermes",
            "--evidence-ids-json",
            "[1]",
            "--confidence",
            "0.4",
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["uv", "run", "agent-memory", "review", "approve", "fact", str(db_path), "1"],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        [
            "uv",
            "run",
            "python",
            "-c",
            (
                "from pathlib import Path; "
                "from agent_memory.core.curation import create_relation; "
                f"create_relation(Path({str(db_path)!r}), from_ref='Hermes', relation_type='uses_storage', to_ref='SQLite', evidence_ids=[1], confidence=0.9)"
            ),
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )

    retrieved = subprocess.run(
        [
            "uv",
            "run",
            "agent-memory",
            "retrieve",
            str(db_path),
            "Which system uses SQLite?",
            "--preferred-scope",
            "project:hermes",
        ],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
    )
    packet = json.loads(retrieved.stdout)

    assert packet["retrieval_trace"][0]["memory_type"] == "fact"
    assert packet["retrieval_trace"][0]["scope_priority"] == 0
    assert packet["retrieval_trace"][0]["supporting_relation_ids"] == [1]
    assert packet["retrieval_trace"][0]["total_score"] > packet["retrieval_trace"][0]["rank_signal_score"]
    assert packet["retrieval_trace"][0]["scope_score"] > 0
    assert packet["retrieval_trace"][0]["relation_score"] > 0
    assert "recency_score" in packet["retrieval_trace"][0]
    assert "reinforcement_score" in packet["retrieval_trace"][0]
    assert "conflict_count" in packet["retrieval_trace"][0]
    assert "conflict_penalty" in packet["retrieval_trace"][0]
    assert "hidden_disputed_alternatives_count" in packet["retrieval_trace"][0]
    assert "hidden_deprecated_alternatives_count" in packet["retrieval_trace"][0]
    assert "hidden_alternative_count" in packet["retrieval_trace"][0]
    assert packet["trust_summaries"][0]["memory_type"] == "fact"
    assert packet["trust_summaries"][0]["label"] == "Hermes"
    assert packet["trust_summaries"][0]["has_hidden_alternatives"] is False
    assert packet["trust_summaries"][0]["trust_band"] == "medium"
    assert "uncertainty_score" in packet["trust_summaries"][0]
    assert "review_risk_score" in packet["trust_summaries"][0]
    assert packet["decision_summary"] == {
        "recommended_answer_mode": "cautious",
        "target_memory_type": "fact",
        "target_memory_id": 1,
        "target_label": "Hermes",
        "trust_band": "medium",
        "has_hidden_alternatives": False,
        "should_mention_uncertainty": True,
        "requires_cross_check": False,
        "should_avoid_definitive": False,
        "reason_codes": [
            "top_ranked_memory",
            "no_hidden_alternatives_detected",
            "medium_uncertainty",
        ],
    }
    assert packet["working_hints"] == [
        "Use fact #1 (Hermes) with medium trust.",
        "No hidden alternatives detected for the top memory.",
        "Mention uncertainty when presenting this memory.",
    ]
    assert packet["policy_hints"] == [
        {
            "action": "prefer",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "medium",
            "reason_code": "top_ranked_memory",
            "message": "Use fact #1 (Hermes) with medium trust.",
        },
        {
            "action": "no_hidden_alternatives",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "low",
            "reason_code": "no_hidden_alternatives_detected",
            "message": "No hidden alternatives detected for the top memory.",
        },
        {
            "action": "mention_uncertainty",
            "target_memory_type": "fact",
            "target_memory_id": 1,
            "target_label": "Hermes",
            "severity": "medium",
            "reason_code": "medium_uncertainty",
            "message": "Mention uncertainty when presenting this memory.",
        },
    ]
