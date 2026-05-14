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


def test_v0157_status_docs_record_oss_readme_checkpoint_and_blocked_broad_apply() -> None:
    next_action = _read_doc(".dev/status/next-agent-memory-action.md")
    handoff = _read_doc(".dev/status/current-handoff.md")
    current_progress = _read_doc(".dev/roadmap/memory-consolidation/current-progress-and-next-steps.md")
    roadmap = _read_doc(".dev/roadmap/roadmap-v0.md")
    stage_g = _read_doc(".dev/roadmap/memory-consolidation/stage-g-cautious-automation.md")

    for doc in (next_action, handoff, current_progress):
        assert "v0.1.157" in doc
        assert "@cafitac/agent-memory@0.1.157" in doc
        assert "npm-install-only" in doc
        assert "PR #341" in doc
        assert "package.json" in doc
        assert "npm pack --dry-run" in doc
        assert "conservative_legacy" in doc
        assert "graph_reinforced_v1" in doc
        assert "ordinary conversation auto-approval" in doc
        assert "broad g4/background apply" in doc.lower()
        assert "v0.1.155" in doc
        assert "/Users/reddit/.agent-memory/runtime/v0.1.155/.venv/bin/agent-memory" in doc
        assert "fresh_trace_linkage_gap_not_detected" in doc
        assert "g4-v0138-20260512-132253" in doc
        assert "Overall north-star: 78-80%" in doc
        assert "50-task expanded retrieval fixture gate" in doc or "50-task expanded retrieval fixture" in doc
        assert "75 checked-in" in doc or "75/75" in doc
        assert "mixed fact/procedure/episode" in doc or "approved facts/procedure/episode" in doc
        assert "collapse proof" in doc.lower()

    assert "dogfood trace-cluster-preview" in next_action
    assert "G5b" in next_action
    assert "G5c" in next_action
    assert "G5d" in next_action
    assert "G5e" in next_action
    assert "G5f" in next_action
    assert "G5g" in next_action
    assert "G5h" in next_action
    assert "G5i" in next_action
    assert "review_score" in next_action
    assert "dogfood reinforcement-refinement-preview" in next_action
    assert "dogfood decay-collapse-preview" in next_action
    assert "repeated activation -> reinforcement" in next_action
    assert "stale weak evidence -> decay/collapse candidate preview" in next_action
    assert "conflict -> supersession/replacement candidate preview" in next_action
    assert "reviewed decay deprecate" in next_action
    assert "retrieval-ranking" in next_action
    assert "rollback confidence" in next_action
    assert "rollback-replay-validate" in next_action
    assert "retrieval-ranking-experiment" in next_action
    assert "decay-collapse-decision" in next_action
    assert "telemetry-reconciliation" in next_action
    assert "G4 broad apply contract" in next_action
    assert "historical telemetry reconciliation" in next_action.lower()
    assert "trace cluster -> consolidation candidate" in stage_g
    assert "candidate -> reviewed fact/procedure/preference promotion" in stage_g
    assert "trace cluster -> review-priority scoring" in stage_g

    assert "PR G4-fresh-contract" in roadmap
    assert "PR G4-historical-reconcile" in roadmap
    assert "PR G4-reviewed-apply-1" in roadmap
    assert "PR G5-brainlike-consolidation-runway" in roadmap

    assert "telemetry-reset-v1" in stage_g
    assert "g4-review-queue-apply-v1" in stage_g
    assert "apply_reinforcement_marker" in stage_g
    assert "No ordinary conversation auto-approval" in stage_g
