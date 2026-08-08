"""Microsoft Store packaging contract tests."""

from pathlib import Path
import json
import re
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "packaging" / "msix" / "AppxManifest.xml.in"


def _render_manifest() -> ET.Element:
    text = MANIFEST.read_text(encoding="utf-8")
    values = {
        "@@IDENTITY_NAME@@": "Kimchanghee.SSMaker",
        "@@PUBLISHER@@": "CN=00000000-0000-0000-0000-000000000000",
        "@@VERSION@@": "1.5.46.0",
        "@@DISPLAY_NAME@@": "SSMaker",
        "@@PUBLISHER_DISPLAY_NAME@@": "SSMaker",
        "@@DESCRIPTION@@": "Shopping shorts automation",
    }
    for placeholder, value in values.items():
        text = text.replace(placeholder, value)
    assert "@@" not in text
    return ET.fromstring(text)


def test_manifest_declares_x64_full_trust_desktop_application():
    root = _render_manifest()
    ns = {"f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10"}
    identity = root.find("f:Identity", ns)
    application = root.find("f:Applications/f:Application", ns)

    assert identity is not None
    assert identity.attrib["ProcessorArchitecture"] == "x64"
    assert identity.attrib["Version"].endswith(".0")
    assert application is not None
    assert application.attrib["Executable"] == "ssmaker.exe"
    assert application.attrib["EntryPoint"] == "Windows.FullTrustApplication"


def test_manifest_delegates_startup_to_windows_and_requests_full_trust():
    root = _render_manifest()
    ns = {
        "f": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
        "desktop": "http://schemas.microsoft.com/appx/manifest/desktop/windows10",
        "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    }

    extension = root.find(
        "f:Applications/f:Application/f:Extensions/desktop:Extension", ns
    )
    startup_task = extension.find("desktop:StartupTask", ns) if extension is not None else None
    capability = root.find("f:Capabilities/rescap:Capability", ns)

    assert extension is not None
    assert extension.attrib["Category"] == "windows.startupTask"
    assert startup_task is not None
    assert startup_task.attrib["TaskId"] == "SSMakerStartup"
    assert capability is not None
    assert capability.attrib["Name"] == "runFullTrust"


def test_store_workflow_has_no_private_certificate_dependency():
    workflow = (ROOT / ".github" / "workflows" / "build-msix-store.yml").read_text(
        encoding="utf-8"
    )
    assert "SSMAKER_PACKAGE_TARGET: msix" in workflow
    assert "SIGN_CERT_PFX_BASE64" not in workflow
    assert "SIGN_CERT_PASSWORD" not in workflow
    assert "build_msix.ps1" in workflow


def test_msix_manifest_declares_internet_client_capability():
    manifest = MANIFEST.read_text(encoding="utf-8")

    assert '<Capability Name="internetClient" />' in manifest


def test_direct_installer_build_remains_default():
    script = (ROOT / "scripts" / "build_exe.ps1").read_text(encoding="utf-8-sig")
    assert '$PackageTarget = "installer"' in script
    assert '$StorePackageBuild = $PackageTarget -eq "msix"' in script
    assert "SIGN_CERT_THUMBPRINT is required for direct-download release builds" in script


def test_committed_version_matches_embedded_updater_fallback():
    version = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))["version"]
    updater = (ROOT / "utils" / "auto_updater.py").read_text(encoding="utf-8")
    match = re.search(r'^CURRENT_VERSION\s*=\s*["\']([^"\']+)["\']', updater, re.MULTILINE)

    assert match is not None
    assert match.group(1) == version
