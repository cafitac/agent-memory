from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_doc(relative_path: str) -> str:
    return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


def test_g4_broad_apply_contract_checkpoint_matches_latest_release_state() -> None:
    handoff = _read_doc(".dev/status/current-handoff.md")
    roadmap = _read_doc(".dev/roadmap/roadmap-v0.md")
    stage_g = _read_doc(".dev/roadmap/memory-consolidation/stage-g-cautious-automation.md")
    g4_plan = _read_doc(".dev/roadmap/memory-consolidation/g4-readiness-and-first-mutation-plan.md")

    assert "v0.1.99" in handoff
    assert "PR #200" in handoff
    assert "PR #204" in handoff
    assert "PR #202" in handoff
    assert "/Users/reddit/.agent-memory/runtime/v0.1.99/.venv/bin/agent-memory" in handoff
    assert "/Users/reddit/.agent-memory/reports/v0.1.99-runtime-qa-20260507T074118" in handoff

    assert "- [x] PR G3g" in roadmap
    assert "- [x] PR G4-plan" in roadmap
    assert "- [x] PR G4b" in roadmap
    assert "- [x] PR G4-broad-plan" in roadmap
    assert "docs/RED-test-only" in roadmap
    assert "ordinary conversation auto-approval remains forbidden" in roadmap

    assert "Status: Superseded as a first-mutation plan" in g4_plan
    assert "v0.1.99" in g4_plan
    assert "query-preview cleanup" in g4_plan
    assert "ordinary trace metadata default cleanup" in g4_plan
    assert "broader background consolidation apply-mode contract" in g4_plan

    assert "PR G4-broad-plan" in stage_g
    assert "Status: Complete" in stage_g
    assert "No ordinary conversation auto-approval" in stage_g
    assert "No raw transcript archive" in stage_g
    assert "No default retrieval ranking change" in stage_g


def test_current_handoff_does_not_advertise_broad_g4_apply_as_ready() -> None:
    handoff = _read_doc(".dev/status/current-handoff.md")

    blocked_phrases = [
        "broad G4 consolidation apply mode is ready",
        "ordinary conversation auto-approval is ready",
        "default retrieval ranking changes are ready",
        "raw transcript storage is enabled",
    ]
    for phrase in blocked_phrases:
        assert phrase not in handoff

    assert "broad G4 consolidation apply mode remains blocked" in handoff
    assert "docs/RED-test-only" in handoff


def test_v0138_status_docs_record_fresh_g4_sequence_and_next_brainlike_steps() -> None:
    next_action = _read_doc(".dev/status/next-agent-memory-action.md")
    handoff = _read_doc(".dev/status/current-handoff.md")
    current_progress = _read_doc(".dev/roadmap/memory-consolidation/current-progress-and-next-steps.md")
    roadmap = _read_doc(".dev/roadmap/roadmap-v0.md")
    stage_g = _read_doc(".dev/roadmap/memory-consolidation/stage-g-cautious-automation.md")

    for doc in (next_action, handoff, current_progress):
        assert "v0.1.138" in doc
        assert "/Users/reddit/.agent-memory/runtime/v0.1.138/.venv/bin/agent-memory" in doc
        assert "fresh_trace_linkage_gap_not_detected" in doc
        assert "g4-v0138-20260512-132253" in doc
        assert "Overall north-star: 52-56%" in doc
        assert "broad G4/background apply remains blocked" in doc

    assert "dogfood trace-cluster-preview" in next_action
    assert "G5b" in next_action
    assert "G4 broad apply contract" in next_action
    assert "historical telemetry reconciliation" in next_action
    assert "trace cluster -> consolidation candidate" in next_action
    assert "candidate -> reviewed fact/procedure/preference promotion" in next_action

    assert "PR G4-fresh-contract" in roadmap
    assert "PR G4-historical-reconcile" in roadmap
    assert "PR G4-reviewed-apply-1" in roadmap
    assert "PR G5-brainlike-consolidation-runway" in roadmap

    assert "telemetry-reset-v1" in stage_g
    assert "g4-review-queue-apply-v1" in stage_g
    assert "apply_reinforcement_marker" in stage_g
    assert "No ordinary conversation auto-approval" in stage_g
