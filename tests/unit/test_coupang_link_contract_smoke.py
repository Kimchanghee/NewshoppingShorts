from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ENTRYPOINT = ROOT / "ssmaker.py"


def test_coupang_link_contract_smoke_writes_report_and_returns_ok(
    tmp_path,
    monkeypatch,
):
    import ssmaker
    from utils.url_security import (
        COUPANG_PARTNER_LINK_CONTRACT_ID,
        build_coupang_partner_link_contract_report,
    )

    report_path = tmp_path / "coupang-link-contract.json"
    monkeypatch.setenv(
        "SSMAKER_COUPANG_LINK_CONTRACT_REPORT",
        str(report_path),
    )

    expected = build_coupang_partner_link_contract_report()
    assert ssmaker.run_coupang_link_contract_smoke() == 0

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report == expected
    assert report["schema_version"] == 1
    assert report["contract_id"] == COUPANG_PARTNER_LINK_CONTRACT_ID
    assert report["ok"] is True
    assert [case["id"] for case in report["cases"]]
    reported_link = next(
        case for case in report["cases"] if case["id"] == "reported_partner_link"
    )
    assert reported_link == {
        "id": "reported_partner_link",
        "accepted": True,
        "links": ["https://link.coupang.com/a/f8i3PuVSqi"],
        "reason_code": "ok",
    }


def test_coupang_link_contract_smoke_exit_code_follows_report_ok(
    tmp_path,
    monkeypatch,
):
    import ssmaker
    from utils import url_security

    report_path = tmp_path / "failed-contract.json"
    failed_report = {
        "schema_version": 1,
        "contract_id": "test-contract",
        "ok": False,
        "cases": [],
    }
    monkeypatch.setenv(
        "SSMAKER_COUPANG_LINK_CONTRACT_REPORT",
        str(report_path),
    )
    monkeypatch.setattr(
        url_security,
        "build_coupang_partner_link_contract_report",
        lambda: failed_report,
    )

    assert ssmaker.run_coupang_link_contract_smoke() == 1
    assert json.loads(report_path.read_text(encoding="utf-8")) == failed_report


def test_coupang_link_contract_cli_dispatch_precedes_all_ui_startup():
    source = ENTRYPOINT.read_text(encoding="utf-8")
    dispatch = (
        'if __name__ == "__main__" and '
        '"--coupang-link-contract-smoke" in sys.argv:'
    )

    assert source.index(dispatch) < source.index("from PyQt6")
    assert source.index(dispatch) < source.index("load_dotenv")
    assert source.index(dispatch) < source.index("app = QApplication(sys.argv)")
