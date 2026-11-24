"""India Standard Time helpers. Storage is always UTC; display is IST."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def now_ist() -> datetime:
    return datetime.now(IST)


def today_ist() -> date:
    return now_ist().date()


def to_ist(value: datetime | None) -> datetime | None:
    return value.astimezone(IST) if value else None


def format_datetime(value: datetime | None) -> str:
    v = to_ist(value)
    return v.strftime("%d %b %Y, %I:%M %p") if v else ""


def format_date(value: date | None) -> str:
    return value.strftime("%a, %d %b %Y") if value else ""


def format_time(value: str | None) -> str:
    if not value:
        return ""
    hours, minutes = (int(x) for x in value.split(":"))
    suffix = "AM" if hours < 12 else "PM"
    return f"{(hours % 12) or 12}:{minutes:02d} {suffix}"
