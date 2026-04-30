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


def test_auto_release_workflow_falls_back_to_release_sync_pr_when_main_is_protected() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "auto-release.yml").read_text()

    assert "pull-requests: write" in workflow
    assert "Create release sync pull request after protected main rejection" in workflow
    assert "release-sync/${{ steps.bump.outputs.tag }}" in workflow
    assert "git push origin \"HEAD:${RELEASE_SYNC_BRANCH}\"" in workflow
    assert "gh pr create" in workflow
    assert "chore: release ${{ steps.bump.outputs.tag }} [skip release]" in workflow
    assert "steps.push_release.outputs.release_sync_required == 'true'" in workflow
    assert "Publish workflow will run after the release sync PR is merged and the tag is pushed." in workflow


def test_auto_release_fallback_is_idempotent_when_release_sync_branch_or_pr_exists() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "auto-release.yml").read_text()

    assert "git ls-remote --exit-code --heads origin \"${RELEASE_SYNC_BRANCH}\"" in workflow
    assert "Release sync branch ${RELEASE_SYNC_BRANCH} already exists" in workflow
    assert "git push origin \"HEAD:${RELEASE_SYNC_BRANCH}\"" in workflow
    assert "gh pr list" in workflow
    assert "existing_pr_url" in workflow
    assert "Release sync PR already exists" in workflow
    assert "gh pr create" in workflow


def test_publish_workflow_remains_tag_driven_only() -> None:
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "publish.yml").read_text()

    assert "tags:" in workflow
    assert "- 'v*'" in workflow
    assert "branches:" not in workflow
    assert "npm publish --access public --provenance" in workflow
    assert "softprops/action-gh-release" in workflow
    assert "github.event_name == 'workflow_dispatch'" in workflow
    assert "startsWith(github.ref, 'refs/tags/v')" in workflow
