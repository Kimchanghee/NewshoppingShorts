from pathlib import Path

from ui.panels.subscription_panel import PLANS


ROOT = Path(__file__).resolve().parents[2]


def test_program_exposes_one_fixed_monthly_subscription():
    assert set(PLANS) == {"trial", "pro", "pro_1month"}
    assert PLANS["pro_1month"]["price"] == 149000
    assert PLANS["pro_1month"]["period"] == "월"


def test_mock_checkout_shows_only_the_fixed_monthly_price():
    html = (ROOT / "backend" / "static" / "mock_payment.html").read_text(
        encoding="utf-8"
    )

    assert "149,000원 / 월" in html
    for old_price in (
        "price: '49,000원'",
        "price: '759,900원'",
        "price: '1,251,600원'",
    ):
        assert old_price not in html
