from datetime import datetime, timezone, timedelta
from src.utils.date_normalizer import DateNormalizer


def test_iso_parsing():
    dt = DateNormalizer.parse("2026-11-20T14:30:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 11
    assert dt.day == 20


def test_rfc2822_parsing():
    dt = DateNormalizer.parse("Fri, 20 Nov 2026 18:00:00 +0000")
    assert dt is not None
    assert dt.year == 2026
    assert dt.hour == 18


def test_relative_date_parsing():
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # 2 hours ago
    dt_2h = DateNormalizer.parse("2 hours ago", reference_time=now)
    assert dt_2h == now - timedelta(hours=2)

    # 45 minutes ago
    dt_45m = DateNormalizer.parse("45 mins ago", reference_time=now)
    assert dt_45m == now - timedelta(minutes=45)

    # yesterday
    dt_yd = DateNormalizer.parse("yesterday", reference_time=now)
    assert dt_yd == now - timedelta(days=1)


def test_24_hour_freshness_boundary():
    now = datetime(2026, 11, 20, 12, 0, 0, tzinfo=timezone.utc)

    # 3 hours ago -> FRESH
    fresh_dt = now - timedelta(hours=3)
    is_fresh, _ = DateNormalizer.is_within_24_hours(fresh_dt, reference_time=now)
    assert is_fresh is True

    # 23 hours ago -> FRESH
    is_fresh, _ = DateNormalizer.is_within_24_hours(now - timedelta(hours=23), reference_time=now)
    assert is_fresh is True

    # 25 hours ago -> STALE (must reject)
    stale_dt = now - timedelta(hours=25)
    is_fresh, _ = DateNormalizer.is_within_24_hours(stale_dt, reference_time=now)
    assert is_fresh is False

    # Future 30 mins clock drift -> ACCEPTED
    is_fresh, _ = DateNormalizer.is_within_24_hours(now + timedelta(minutes=30), reference_time=now)
    assert is_fresh is True
