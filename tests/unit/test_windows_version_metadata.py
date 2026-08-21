from pathlib import Path

from scripts.generate_windows_version_info import build_version_resource


def test_windows_executable_metadata_contains_version_company_and_product():
    resource = build_version_resource(
        "1.5.69",
        "136",
        commit_sha="0123456789abcdef0123456789abcdef01234567",
        url_contract_id="coupang-partner-link-v1",
    )

    assert "filevers=(1, 5, 69, 136)" in resource
    assert "StringStruct('CompanyName', 'SSMaker')" in resource
    assert "StringStruct('ProductName', 'SSMaker')" in resource
    assert "StringStruct('ProductVersion', '1.5.69')" in resource
    assert "StringStruct('FileVersion', '1.5.69.136')" in resource
    assert "flags=0x28" in resource
    assert "StringStruct('PrivateBuild', '0123456789ab')" in resource
    assert "StringStruct('SpecialBuild', 'coupang-partner-link-v1')" in resource


def test_windows_version_generator_consumes_external_build_manifest():
    script = Path("scripts/generate_windows_version_info.py").read_text(encoding="utf-8")

    assert 'parser.add_argument("--build-manifest"' in script
    assert 'manifest.get("commit_sha", "local")' in script
    assert 'manifest.get("url_contract_id", "unknown")' in script
