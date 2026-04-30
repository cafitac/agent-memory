from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_external_trust_docs_exist_and_are_linked_from_readme() -> None:
    readme = (ROOT / "README.md").read_text()

    for relative_path in [
        "LICENSE",
        "SECURITY.md",
        "PRIVACY.md",
        "CONTRIBUTING.md",
        "docs/install-smoke.md",
        "docs/first-run-memory-layer.md",
        "docs/hermes-dogfood.md",
    ]:
        assert (ROOT / relative_path).exists()
        assert relative_path in readme

    assert "npm install -g @cafitac/agent-memory" in readme
    assert "agent-memory bootstrap" in readme
    assert "agent-memory doctor" in readme
    assert "https://www.npmjs.com/package/@cafitac/agent-memory" in readme
    assert "https://pypi.org/project/cafitac-agent-memory/" in readme


def test_first_run_memory_layer_guide_covers_safe_bootstrap_and_cleanup() -> None:
    guide = (ROOT / "docs" / "first-run-memory-layer.md").read_text()

    for expected in [
        "agent-memory bootstrap",
        "agent-memory doctor",
        "~/.agent-memory/memory.db",
        "~/.hermes/config.yaml",
        "conservative",
        "disable",
        "delete",
        "local-first",
    ]:
        assert expected in guide


def test_hermes_dogfood_guide_covers_ops_smoke_and_fallbacks() -> None:
    guide = (ROOT / "docs" / "hermes-dogfood.md").read_text()

    for expected in [
        "dogfood",
        "agent-memory bootstrap",
        "agent-memory doctor",
        "hermes hooks doctor",
        "--preset conservative",
        "--preset balanced",
        "latency",
        "fail closed",
        "rollback",
    ]:
        assert expected in guide


def test_issue_and_pr_templates_exist() -> None:
    expected_paths = [
        ".github/ISSUE_TEMPLATE/bug_report.yml",
        ".github/ISSUE_TEMPLATE/feature_request.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/pull_request_template.md",
    ]

    for relative_path in expected_paths:
        path = ROOT / relative_path
        assert path.exists()
        assert path.read_text().strip()
