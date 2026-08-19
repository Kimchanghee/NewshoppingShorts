from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_store_workflow_can_build_candidates_and_publish_release_tags():
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    assert "store-v*" in workflow
    assert "publish_to_store:" in workflow
    assert "9P43TQHLP8WH" in workflow
    assert "YMcompany.SSMaker" in workflow
    assert "CN=447AAE61-8C19-4267-91D6-45419445A405" in workflow
    assert "Store tag/version mismatch" in workflow


def test_store_publication_uses_pinned_official_publisher_and_secret_preflight():
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    assert (
        "microsoft/microsoft-store-apppublisher@"
        "cc9910a8d59f2eb55cbb83df0a3800cf3b5300e0" in workflow
    )
    assert "version: v0.4.0" in workflow
    for secret in (
        "AZURE_AD_APPLICATION_CLIENT_ID",
        "AZURE_AD_APPLICATION_SECRET",
        "AZURE_AD_TENANT_ID",
        "SELLER_ID",
    ):
        assert secret in workflow
    assert "msstore reconfigure" in workflow
    assert "msstore publish $package.FullName --appId 9P43TQHLP8WH --verbose" in workflow


def test_store_artifact_is_retained_for_manual_partner_center_fallback():
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    assert "path: dist/store/*.msix" in workflow
    assert "retention-days: 30" in workflow
