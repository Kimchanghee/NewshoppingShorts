"""Security contracts for Authenticode classification and release publication."""

from pathlib import Path

from utils import authenticode
from utils.authenticode import (
    AuthenticodeTrust,
    CODE_SIGNING_EKU_OID,
    LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS,
    classify_authenticode,
    validate_build_signing_configuration,
)


ROOT = Path(__file__).resolve().parents[2]
LEGACY_THUMBPRINT = next(iter(LEGACY_INTEGRITY_BRIDGE_THUMBPRINTS))
PUBLIC_THUMBPRINT = "A" * 40


def _evidence(
    *,
    status: str = "Valid",
    thumbprint: str = PUBLIC_THUMBPRINT,
    eku_oids: list[str] | None = None,
    timestamp_present: bool = True,
) -> dict[str, object]:
    return {
        "Status": status,
        "StatusMessage": "test status",
        "Thumbprint": thumbprint,
        "Subject": "CN=Expected Publisher",
        "Issuer": "CN=Public Code Signing CA",
        "EnhancedKeyUsageOids": eku_oids or [CODE_SIGNING_EKU_OID],
        "TimestampPresent": timestamp_present,
        "TimestampSubject": "CN=Timestamp Authority",
    }


def test_public_trust_requires_valid_status_expected_signer_eku_and_timestamp():
    verified = classify_authenticode(
        _evidence(),
        expected_thumbprints=[PUBLIC_THUMBPRINT],
    )

    assert verified.trust is AuthenticodeTrust.PUBLIC_TRUSTED
    assert verified.public_trusted is True
    assert verified.accepted_for_update is True


def test_public_trust_rejects_empty_expected_signer_allowlist():
    verified = classify_authenticode(_evidence(), expected_thumbprints=[])

    assert verified.trust is AuthenticodeTrust.INVALID
    assert "allowlist is empty" in verified.reason


def test_public_trust_rejects_unknownerror_even_for_expected_signer():
    verified = classify_authenticode(
        _evidence(status="UnknownError"),
        expected_thumbprints=[PUBLIC_THUMBPRINT],
    )

    assert verified.trust is AuthenticodeTrust.INVALID
    assert verified.public_trusted is False


def test_public_trust_rejects_missing_eku_or_timestamp():
    missing_eku = classify_authenticode(
        _evidence(eku_oids=["1.2.3.4"]),
        expected_thumbprints=[PUBLIC_THUMBPRINT],
    )
    missing_timestamp = classify_authenticode(
        _evidence(timestamp_present=False),
        expected_thumbprints=[PUBLIC_THUMBPRINT],
    )

    assert missing_eku.trust is AuthenticodeTrust.INVALID
    assert missing_timestamp.trust is AuthenticodeTrust.INVALID


def test_public_trust_rejects_manually_trusted_self_issued_signer():
    evidence = _evidence()
    evidence["Issuer"] = evidence["Subject"]

    verified = classify_authenticode(
        evidence,
        expected_thumbprints=[PUBLIC_THUMBPRINT],
    )

    assert verified.trust is AuthenticodeTrust.INVALID
    assert "self-issued" in verified.reason


def test_v1564_pin_is_compatibility_bridge_and_never_public_trust():
    verified = classify_authenticode(
        _evidence(status="UnknownError", thumbprint=LEGACY_THUMBPRINT),
        expected_thumbprints=[LEGACY_THUMBPRINT],
        artifact_version="1.5.64",
        allow_legacy_integrity_bridge=True,
    )

    assert verified.trust is AuthenticodeTrust.LEGACY_INTEGRITY_BRIDGE
    assert verified.accepted_for_update is True
    assert verified.public_trusted is False
    assert "not public trust" in verified.reason


def test_next_version_is_not_implicitly_authorized_as_transition_bridge():
    verified = classify_authenticode(
        _evidence(status="UnknownError", thumbprint=LEGACY_THUMBPRINT),
        artifact_version="1.5.65",
        allow_legacy_integrity_bridge=True,
    )

    assert verified.trust is AuthenticodeTrust.INVALID


def test_transition_bridge_requires_separate_explicit_version():
    verified = classify_authenticode(
        _evidence(status="UnknownError", thumbprint=LEGACY_THUMBPRINT),
        artifact_version="1.6.0",
        allow_legacy_integrity_bridge=True,
        transition_bridge_version="1.6.0",
    )

    assert verified.trust is AuthenticodeTrust.LEGACY_INTEGRITY_BRIDGE
    assert "explicit transition version 1.6.0" in verified.reason
    assert verified.public_trusted is False


def test_build_policy_defaults_to_no_public_release_authority():
    ok, reason = validate_build_signing_configuration(
        "public",
        "1.5.65",
        PUBLIC_THUMBPRINT,
    )

    assert ok is False
    assert "baked public release signer allowlist is empty" in reason


def test_build_policy_allows_only_the_exact_baked_transition(monkeypatch):
    monkeypatch.setattr(authenticode, "TRANSITION_BRIDGE_VERSION", "1.6.0")
    monkeypatch.setattr(
        authenticode,
        "PUBLIC_RELEASE_SIGNER_THUMBPRINTS",
        frozenset({PUBLIC_THUMBPRINT}),
    )

    bridge_ok, bridge_reason = validate_build_signing_configuration(
        "integrity-bridge",
        "1.6.0",
        LEGACY_THUMBPRINT,
    )
    public_ok, public_reason = validate_build_signing_configuration(
        "public",
        "1.6.1",
        PUBLIC_THUMBPRINT,
    )

    assert bridge_ok is True
    assert "historical signer pin" in bridge_reason
    assert public_ok is True
    assert "baked public release signer" in public_reason


def test_v1584_is_the_only_baked_integrity_bridge_release():
    assert authenticode.TRANSITION_BRIDGE_VERSION == "1.5.84"

    approved, _ = validate_build_signing_configuration(
        "integrity-bridge",
        "1.5.84",
        LEGACY_THUMBPRINT,
    )
    next_version, reason = validate_build_signing_configuration(
        "integrity-bridge",
        "1.5.85",
        LEGACY_THUMBPRINT,
    )

    assert approved is True
    assert next_version is False
    assert "does not match" in reason


def test_build_uses_rfc3161_and_inno_named_sign_tool_contract():
    build = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")
    installer = (ROOT / "installer.iss").read_text(encoding="utf-8-sig")

    assert '"/tr", "http://timestamp.digicert.com"' in build
    assert '"/td", "SHA256"' in build
    assert "/fd SHA256 /tr http://timestamp.digicert.com /td SHA256" in build
    assert '"/DSignToolAvailable"' in build
    assert '"/Sssmaker=$innoSignCommand"' in build
    assert "SignTool=ssmaker" in installer
    assert "SignedUninstaller=yes" in installer
    assert '"/t", "http://timestamp' not in build.lower()
    assert " /t http://timestamp" not in build.lower()


def test_build_public_gate_is_fail_closed_and_checks_expected_identity():
    build = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")
    runtime_policy = (ROOT / "utils" / "authenticode.py").read_text(encoding="utf-8")

    assert "SIGN_CERT_THUMBPRINT is required for direct-download release builds" in build
    assert "signer mismatch" in build
    assert "Code Signing EKU" in build
    assert "ForEach-Object { [string]$_.ObjectId }" in build
    assert "ObjectId.Value" not in build
    assert "ForEach-Object { [string]$_.ObjectId })" in runtime_policy
    assert "ObjectId.Value" not in runtime_policy
    assert "Import-Module Microsoft.PowerShell.Security -ErrorAction Stop" in runtime_policy
    assert "TimeStamperCertificate" in build
    assert 'if ([string]$signature.Status -ne "Valid")' in build
    assert "UnknownError is not accepted in public mode" in build
    assert '"verify", "/pa", "/all", "/v"' in build


def test_build_bundles_and_verifies_font_license_notices():
    build = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")
    spec = (ROOT / "ssmaker.spec").read_text(encoding="utf-8-sig")

    assert "for _font_choice in FONT_CHOICES" in spec
    assert "DEFAULT_FONTS_DIR / _font_choice.asset.filename" in spec
    assert "for _license_notice in LICENSE_NOTICES.values()" in spec
    assert "DEFAULT_LICENSES_DIR / _license_notice.filename" in spec
    assert "datas.append((str(_font_path), 'fonts'))" in spec
    assert "datas.append((str(_license_path), 'licenses'))" in spec
    assert "datas.append((_fonts_dir, 'fonts'))" not in spec
    assert '"scripts\\download_all_fonts_final.py"' in build
    assert '"scripts\\verify_font_assets.py"' in build
    assert '"--fonts-dir", (Join-Path $Root "fonts")' in build
    assert '"--licenses-dir", (Join-Path $Root "resources\\licenses")' in build
    assert '"--fonts-dir", (Join-Path $distDir "fonts")' in build
    assert '"--licenses-dir", (Join-Path $distDir "licenses")' in build
    for stale_item in (
        "Pretendard-Bold.ttf",
        "Pretendard-SemiBold.ttf",
        "IBMPlexSansKR-Bold.ttf",
        "LICENSE-NotoSansKR.txt",
        "LICENSE-SUIT.txt",
        "$requiredFontItems",
    ):
        assert stale_item not in build


def test_workflow_forces_tag_publication_and_scopes_bridge_to_baked_version():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )

    assert "version:" in workflow
    assert "publish:" in workflow
    assert "signing_mode:" in workflow
    assert '$publish = "true"' in workflow
    assert '$signingMode = "public"' in workflow
    assert "workflow_dispatch:" not in workflow
    assert "Direct installer builds require an immutable vMAJOR.MINOR.PATCH tag push" in workflow
    assert "environment: production-release-signing" in workflow
    assert "Public signing mode rejects self-issued certificates" in workflow
    assert "ForEach-Object { [string]$_.ObjectId }" in workflow
    assert "ObjectId.Value" not in workflow
    assert "Release gate requires a nonempty expected signer thumbprint" in workflow
    assert "validate_build_signing_configuration" in workflow
    assert "if: needs.build.outputs.publish == 'true'" in workflow
    assert "steps.version" not in workflow


def test_workflow_installs_package_and_directly_verifies_signed_uninstaller():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    installer = (ROOT / "installer.iss").read_text(encoding="utf-8-sig")

    assert '"/VERYSILENT"' in workflow
    assert '"/VERIFYPACKAGE"' in workflow
    assert "$installProcess = Start-Process" in workflow
    assert "-Wait" in workflow
    assert "-PassThru" in workflow
    assert "$installProcess.ExitCode" in workflow
    assert "$LASTEXITCODE" not in workflow[
        workflow.index("$installProcess = Start-Process") : workflow.index(
            '$installedApp = Join-Path $installRoot "ssmaker.exe"'
        )
    ]
    assert 'Filter "unins*.exe"' in workflow
    assert 'Assert-SigningGate $uninstaller "installed Inno uninstaller"' in workflow
    assert "& $signtool verify /pa /all /v $Path" in workflow
    assert "ShouldLaunchInstalledApp" in installer
    assert "ParamStr(I)" in installer


def test_installed_link_contract_gate_runs_after_signing_and_before_assets():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )

    signing = workflow.index('Assert-SigningGate $installedApp "installed application"')
    smoke = workflow.index("coupang_link_contract_installed.json", signing)
    hash_asset = workflow.index("Compute installer SHA256", smoke)
    assert signing < smoke < hash_asset
    assert '"--coupang-link-contract-smoke"' in workflow
    assert "WaitForExit(30000)" in workflow
    assert "publication_allowed=true and clean_tree=true" in workflow


def test_release_and_api_follow_signature_and_asset_hash_gates():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )

    signing_gate = workflow.index("Verify app, installer, and installed uninstaller signing gates")
    prepublish_hash = workflow.index("Verify candidate asset hash before any publication")
    create_draft = workflow.index("Create draft Release with verified local assets")
    draft_hash = workflow.index("Verify draft GitHub release asset hash")
    publish_release = workflow.index("Publish verified GitHub release")
    update_api = workflow.index("Update server version API")

    assert signing_gate < prepublish_hash < create_draft < draft_hash < publish_release < update_api
    assert "draft: true" in workflow
    assert "--draft=false --latest --verify-tag" in workflow
    assert "publish:\n    needs: build" in workflow
    assert "Recompute candidate hash across trust boundary" in workflow


def test_api_update_verifies_all_three_public_metadata_contracts():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )

    assert '"version": f"{api_base_url}/app/version?verify={nonce}"' in workflow
    assert '"check": f"{api_base_url}/app/version/check?current_version=0.0.0&verify={nonce}"' in workflow
    assert '"legacy": f"{api_base_url}/free/lately/?item=1&verify={nonce}"' in workflow
    assert 'raw_contracts["check"].get("latest_version")' in workflow
    assert 'for key in ("download_url", "release_notes", "file_hash")' in workflow
    assert "all(contract == expected_contract for contract in verified_contracts.values())" in workflow
    assert 'PYTHONUTF8: "1"' in workflow


def test_release_workflows_never_publish_internal_commit_notes_to_customers():
    release_workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(
        encoding="utf-8"
    )
    metadata_workflow = (
        ROOT / ".github" / "workflows" / "update-app-version-api.yml"
    ).read_text(encoding="utf-8")

    assert "generate_release_notes: false" in release_workflow
    assert "Resolve release notes" not in release_workflow
    assert "RELEASE_NOTES_SUMMARY: 안정성과 사용성을 개선했습니다." in release_workflow
    assert "Customer-facing Korean release notes" in metadata_workflow
    assert "Ignoring non-Korean internal release notes" in metadata_workflow


def test_release_workflow_pins_actions_tools_and_never_interpolates_signing_secrets():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(encoding="utf-8")

    for mutable_ref in (
        "actions/checkout@v",
        "actions/setup-python@v",
        "actions/cache@v",
        "actions/upload-artifact@v",
        "softprops/action-gh-release@v",
    ):
        assert mutable_ref not in workflow
    assert "--disable-pip-version-check --require-hashes -r requirements-release.lock" in workflow
    assert "PyInstaller.__version__ == '6.19.0'" in workflow
    assert "python-version: '3.11.9'" in workflow
    assert "hashFiles('requirements-release.lock')" in workflow
    assert "choco install innosetup --version=" in workflow
    assert "./scripts/install_pinned_tesseract.ps1" in workflow
    assert workflow.count("--require-checksums --fail-on-unfound") == 1
    assert '"${{ secrets.SIGN_CERT_' not in workflow
    assert "$env:SIGN_CERT_PFX_BASE64" in workflow
    assert 'raise SystemExit("APP_VERSION_UPDATE_HMAC_KEY is required")' in workflow


def test_publish_credentials_are_isolated_from_untrusted_build_steps():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(encoding="utf-8")
    build_start = workflow.index("\n  build:\n")
    publish_start = workflow.index("\n  publish:\n", build_start)
    build_section = workflow[build_start:publish_start]
    publish_section = workflow[publish_start:]

    assert "permissions:\n      contents: read" in build_section
    assert "persist-credentials: false" in build_section
    assert "permissions:\n      contents: write" in publish_section
    assert "actions/download-artifact@d3f86a106a0bac45b974a628896c90dbdf5c8093" in publish_section
    assert "SIGN_CERT_PFX_BASE64" not in publish_section


def test_release_workflow_global_monotonic_gate_and_exact_baked_bridge_contract():
    workflow = (ROOT / ".github" / "workflows" / "build-and-deploy.yml").read_text(encoding="utf-8")

    assert "group: signed-release-publication" in workflow
    assert "Reject non-monotonic release publication" in workflow
    assert "Refusing to publish version" in workflow
    assert "TRANSITION_BRIDGE_VERSION" in workflow
    assert "$bakedBridge -and $version -eq $bakedBridge" in workflow
    assert "$hasPublicPins" not in workflow
    assert workflow.index("Reject non-monotonic release publication") < workflow.index(
        "Create draft Release with verified local assets"
    )


def test_build_pins_and_validates_tessdata_fast_assets():
    build = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")

    assert "tessdata_fast/raw/main" not in build
    assert "87416418657359cb625c412a48b6e1d6d41c29bd" in build
    for expected_size, expected_hash in (
        ("4113088", "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2"),
        ("1677415", "6b85e11d9bbf07863b97b3523b1b112844c43e713df8b66418a081fd1060b3b2"),
        ("2469156", "a5fcb6f0db1e1d6d8522f39db4e848f05984669172e584e8d76b6b3141e1f730"),
    ):
        assert expected_size in build
        assert expected_hash in build
    assert "$actualSize -ne $expected.Size -or $actualHash -ne $expected.Hash" in build
