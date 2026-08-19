import os
from datetime import datetime, timedelta, timezone

os.environ.setdefault("JWT_SECRET_KEY", "a" * 64)
os.environ.setdefault("DATABASE_URL", "sqlite:///./backend_test.db")

from app.utils.subscription_utils import build_expiry_notice


def test_expiry_notice_uses_seven_three_and_one_day_bands():
    now = datetime.now(timezone.utc)

    seven = build_expiry_notice(now + timedelta(days=6, hours=12), now)
    three = build_expiry_notice(now + timedelta(days=2, hours=12), now)
    one = build_expiry_notice(now + timedelta(hours=12), now)

    assert seven and seven["key"].endswith(":7") and seven["days_remaining"] == 7
    assert three and three["key"].endswith(":3") and three["days_remaining"] == 3
    assert one and one["key"].endswith(":1") and one["days_remaining"] == 1


def test_expiry_notice_is_absent_outside_notice_window():
    now = datetime.now(timezone.utc)
    assert build_expiry_notice(now + timedelta(days=8), now) is None
