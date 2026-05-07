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
