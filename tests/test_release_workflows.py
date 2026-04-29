from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_auto_release_workflow_bumps_versions_on_main_merges() -> None:
    workflow_path = PROJECT_ROOT / ".github" / "workflows" / "auto-release.yml"

    workflow = workflow_path.read_text()

    assert "branches:" in workflow
    assert "- main" in workflow
    assert "contents: write" in workflow
    assert "actions: write" in workflow
    assert "[skip release]" in workflow
    assert "scripts/bump_release_version.py --patch" in workflow
    assert "git push origin HEAD:main" in workflow
    assert "git push origin \"$TAG\"" in workflow
    assert "gh workflow run publish.yml" in workflow
    assert "--ref \"$TAG\"" in workflow


def test_publish_workflow_remains_tag_driven_only() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "publish.yml").read_text()

    assert "tags:" in workflow
    assert "- 'v*'" in workflow
    assert "branches:" not in workflow
    assert "npm publish --access public --provenance" in workflow
    assert "softprops/action-gh-release" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
