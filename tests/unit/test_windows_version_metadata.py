from scripts.generate_windows_version_info import build_version_resource


def test_windows_executable_metadata_contains_version_company_and_product():
    resource = build_version_resource("1.5.69", "136")

    assert "filevers=(1, 5, 69, 136)" in resource
    assert "StringStruct('CompanyName', 'SSMaker')" in resource
    assert "StringStruct('ProductName', 'SSMaker')" in resource
    assert "StringStruct('ProductVersion', '1.5.69')" in resource
    assert "StringStruct('FileVersion', '1.5.69.136')" in resource
