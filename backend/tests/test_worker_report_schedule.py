from datetime import datetime
from zoneinfo import ZoneInfo

from app.worker import _operational_report_key


def test_daily_operational_report_runs_after_18_once_per_date():
    timezone = ZoneInfo("Europe/Istanbul")
    assert _operational_report_key(datetime(2026, 7, 17, 17, 59, tzinfo=timezone), "daily") is None
    assert _operational_report_key(datetime(2026, 7, 17, 18, 0, tzinfo=timezone), "daily") == "2026-07-17"


def test_weekly_operational_report_runs_monday_after_09():
    timezone = ZoneInfo("Europe/Istanbul")
    assert _operational_report_key(datetime(2026, 7, 20, 8, 59, tzinfo=timezone), "weekly") is None
    assert _operational_report_key(datetime(2026, 7, 20, 9, 0, tzinfo=timezone), "weekly") == "2026-W30"
    assert _operational_report_key(datetime(2026, 7, 21, 9, 0, tzinfo=timezone), "weekly") is None
