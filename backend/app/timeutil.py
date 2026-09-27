from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from .config import get_settings


def tz() -> ZoneInfo:
    return ZoneInfo(get_settings().timezone)


def today_local() -> date:
    return datetime.now(tz()).date()


def parse_date(s: str) -> date:
    return date.fromisoformat(s[:10])


def days_ago(n: int) -> str:
    return (today_local() - timedelta(days=n)).isoformat()
