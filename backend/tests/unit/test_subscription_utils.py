# -*- coding: utf-8 -*-
from datetime import datetime, timezone

from app.utils.subscription_utils import get_trial_cycle_start, is_new_trial_cycle


def test_get_trial_cycle_start_uses_kst_month_boundary():
    # 2026-02-10 12:34 UTC == 2026-02-10 21:34 KST
    ref = datetime(2026, 2, 10, 12, 34, 0, tzinfo=timezone.utc)
    cycle_start = get_trial_cycle_start(ref)

    # KST month start for Feb 2026 is 2026-02-01 00:00 KST
    # which is 2026-01-31 15:00 UTC.
    assert cycle_start == datetime(2026, 1, 31, 15, 0, 0, tzinfo=timezone.utc)


def test_is_new_trial_cycle_true_when_crossing_month():
    stored = datetime(2026, 1, 31, 15, 0, 0, tzinfo=timezone.utc)  # Feb cycle start (KST)
    now = datetime(2026, 2, 28, 16, 0, 0, tzinfo=timezone.utc)  # Mar 1 KST 01:00
    assert is_new_trial_cycle(stored, now=now) is True


def test_is_new_trial_cycle_false_within_same_month():
    stored = datetime(2026, 1, 31, 15, 0, 0, tzinfo=timezone.utc)  # Feb cycle start (KST)
    now = datetime(2026, 2, 10, 0, 0, 0, tzinfo=timezone.utc)
    assert is_new_trial_cycle(stored, now=now) is False
