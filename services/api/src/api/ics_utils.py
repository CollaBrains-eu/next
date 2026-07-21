"""Shared iCalendar (RFC 5545) text building, used by both appointments.py
(timed VEVENTs) and tasks.py (all-day VEVENTs for a due_date). Kept as its
own module so neither router has to import from the other."""
from datetime import date, datetime, timezone


def escape_ics_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def format_ics_datetime(value: datetime) -> str:
    return value.strftime("%Y%m%dT%H%M%SZ")


def format_ics_date(value: date) -> str:
    return value.strftime("%Y%m%d")


def ics_slug(title: str) -> str:
    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "event"


def build_vevent_calendar(
    *,
    uid: str,
    summary: str,
    dtstart: str,
    all_day: bool = False,
    dtend: str | None = None,
    location: str | None = None,
    description: str | None = None,
    prodid: str = "-//CollaBrains//Calendar//EN",
) -> str:
    """Builds a single-event VCALENDAR. `dtstart`/`dtend` must already be
    formatted (via format_ics_datetime for timed events, format_ics_date for
    all_day ones)."""
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        f"PRODID:{prodid}",
        "BEGIN:VEVENT",
        f"UID:{uid}@collabrains.eu",
        f"DTSTAMP:{format_ics_datetime(datetime.now(timezone.utc))}",
    ]
    date_param = ";VALUE=DATE" if all_day else ""
    lines.append(f"DTSTART{date_param}:{dtstart}")
    if dtend:
        lines.append(f"DTEND{date_param}:{dtend}")
    lines.append(f"SUMMARY:{escape_ics_text(summary)}")
    if location:
        lines.append(f"LOCATION:{escape_ics_text(location)}")
    if description:
        lines.append(f"DESCRIPTION:{escape_ics_text(description)}")
    lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
