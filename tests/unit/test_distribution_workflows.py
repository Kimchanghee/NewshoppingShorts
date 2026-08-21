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


def test_production_credentials_are_scoped_to_protected_release_environments():
    direct = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch:" not in direct
    assert "environment: production-release-signing" in direct
    assert "environment: production-release-publication" in direct
    assert "Direct installer builds require an immutable vMAJOR.MINOR.PATCH tag push" in direct
    assert "validate_store_access:" not in workflow
    assert "microsoft-store-production" in workflow
    assert "microsoft-store-candidate" in workflow
    assert "candidate environment" in workflow


def test_both_windows_builds_receive_all_external_manifest_trust_values():
    direct = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    store = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    for workflow in (direct, store):
        assert "SSMAKER_EXPECTED_COMMIT_SHA: ${{ github.sha }}" in workflow
        assert "SSMAKER_EXPECTED_REF: ${{ github.ref }}" in workflow
        assert "SSMAKER_EXPECTED_RUN_ID: ${{ github.run_id }}" in workflow
        assert "SSMAKER_PACKAGE_TARGET:" in workflow


def test_store_dispatch_cannot_publish_and_tag_build_is_independently_verified():
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )

    assert "workflow_dispatch is candidate-only" in workflow
    assert '$publish = $env:EVENT_NAME -eq "push"' in workflow
    assert "publication_allowed must be true only for an immutable store-v tag push" in workflow
    assert "Verify Store manifest, PE identity, and frozen link smoke gate" in workflow
    assert workflow.index("Build Store application payload") < workflow.index(
        "Build unsigned Store MSIX"
    )
    validation = workflow.index("Store identity inputs must not contain CR or LF characters")
    version_validation = workflow.index(
        "Committed Store version must use exact MAJOR.MINOR.PATCH format without line breaks"
    )
    publish_output = workflow.index('"publish=$($publish.ToString().ToLowerInvariant())"')
    assert version_validation < publish_output
    assert validation < publish_output
    assert "[regex]::IsMatch($committedVersion, '\\A[0-9]+\\.[0-9]+\\.[0-9]+\\z')" in workflow
    assert "Store identity_name contains unsupported characters" in workflow
    assert "Store publisher must use the approved CN=<GUID> shape" in workflow
    assert "Store publisher_display_name contains unsupported characters" in workflow


def test_direct_distribution_has_installed_smoke_manifest_pe_and_homepage_gates():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )

    signing_gate = workflow.index("Verify app, installer, and installed uninstaller signing gates")
    installed_smoke = workflow.index("coupang_link_contract_installed.json", signing_gate)
    asset_hash = workflow.index("Compute installer SHA256", installed_smoke)
    assert signing_gate < installed_smoke < asset_hash
    assert "Source, frozen and installed link contract reports differ" in workflow
    assert "Build manifests differ across staging/frozen/installed" in workflow
    assert "PE PrivateBuild mismatch" in workflow
    assert "PE SpecialBuild mismatch" in workflow
    assert "PE version identity mismatch" in workflow
    assert "Direct homepage gate failed" in workflow
    assert "DIRECT_INSTALLER_VERSION" in workflow
    assert "DIRECT_DOWNLOAD_URL" in workflow


def test_build_script_freezes_manifest_and_compares_source_to_frozen_contract():
    build = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8-sig")

    source_smoke = build.index("Running source Coupang link contract smoke test")
    manifest = build.index("Generating build provenance manifest", source_smoke)
    freeze = build.index("Building ssmaker (onedir)", manifest)
    frozen_smoke = build.index("Running frozen Coupang link contract smoke test", freeze)
    assert source_smoke < manifest < freeze < frozen_smoke
    assert "SSMAKER_COUPANG_LINK_CONTRACT_REPORT" in build
    assert "Get-CoupangLinkContractProjection" in build
    assert "Source and frozen Coupang link contract reports are not structurally identical" in build
    assert '"build_manifest.json"' in build
    assert "datas.append((build_manifest, '.'))" in spec
    assert "[spec] ERROR: build manifest is missing" in spec
    assert "Build manifest does not contain verified immutable Whisper assets" in build
    assert "Frozen Whisper asset hash mismatch" in build
    assert "Frozen Tesseract asset hash mismatch" in build


def test_windows_release_inputs_pin_tesseract_and_whisper_content():
    direct = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    store = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )
    downloader = (ROOT / "scripts" / "download_whisper_models.py").read_text(
        encoding="utf-8"
    )
    tesseract_installer = (ROOT / "scripts" / "install_pinned_tesseract.ps1").read_text(
        encoding="utf-8-sig"
    )
    identities = (ROOT / "utils" / "release_assets.py").read_text(encoding="utf-8")

    for workflow in (direct, store):
        assert "./scripts/install_pinned_tesseract.ps1" in workflow
    assert 'packageVersion = "5.5.0.20241111"' in tesseract_installer
    assert "56659a4c01e6ea75a0b710ba7e8bb16e9cc6675978d2861323751812aeea6183" in tesseract_installer
    assert "Pinned Tesseract package hash mismatch" in tesseract_installer
    assert "continue-on-error: true" not in direct[direct.index("Download Whisper models") :]
    assert "snapshot_download(" in downloader
    assert "revision=str(identity[\"revision\"])" in downloader
    assert "verify_whisper_model_assets" in downloader
    assert "d90ca5fe260221311c53c58e660288d3deb8d356" in identities
    assert "ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66" in identities
