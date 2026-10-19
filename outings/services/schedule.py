"""Date helpers shared by the Outings listings, cards, detail page and calendar export."""

from datetime import timedelta, timezone as dt_timezone

from django.utils import timezone


WEEKDAYS_JA = "月火水木金土日"

LONG_RUNNING_DAYS = 14


def is_upcoming(occurrence, now):
    """Still bookable: not cancelled and not over yet."""
    if occurrence.is_cancelled:
        return False
    if occurrence.end_at:
        return occurrence.end_at > now
    return occurrence.start_at >= now


def upcoming(occurrences, now):
    return sorted(
        (o for o in occurrences if is_upcoming(o, now)),
        key=lambda o: o.start_at,
    )


def is_ongoing(occurrence, now):
    return occurrence.start_at < now and bool(occurrence.end_at) and occurrence.end_at > now


def is_long_running(occurrences):
    """One run of two weeks or more, or dates spread across two weeks or more."""
    occurrences = [o for o in occurrences if not o.is_cancelled]
    if not occurrences:
        return False
    for o in occurrences:
        if o.end_at and o.end_at - o.start_at >= timedelta(days=LONG_RUNNING_DAYS):
            return True
    days = sorted({timezone.localtime(o.start_at).date() for o in occurrences})
    return len(days) > 1 and (days[-1] - days[0]).days >= LONG_RUNNING_DAYS


def is_recurring(occurrences):
    """Weekly or fortnightly repetitions."""
    days = sorted({timezone.localtime(o.start_at).date() for o in occurrences if not o.is_cancelled})
    return any((b - a).days in (7, 14) for a, b in zip(days, days[1:]))


def _has_time(value):
    local = timezone.localtime(value)
    return (local.hour, local.minute) != (0, 0)


def day_label(value):
    local = timezone.localtime(value)
    return f"{local.month}月{local.day}日（{WEEKDAYS_JA[local.weekday()]}）"


def short_day_label(value):
    local = timezone.localtime(value)
    return f"{local.month}/{local.day}（{WEEKDAYS_JA[local.weekday()]}）"


def time_label(value):
    local = timezone.localtime(value)
    return f"{local.hour}:{local.minute:02d}" if _has_time(value) else ""


def occurrence_label(occurrence, now=None):
    """'10/25（土）14:00', or '開催中・11/14（土）まで' for a run already open."""
    now = now or timezone.now()
    if is_ongoing(occurrence, now):
        return f"開催中・{short_day_label(occurrence.end_at)}まで"
    label = short_day_label(occurrence.start_at)
    start_time = time_label(occurrence.start_at)
    if start_time:
        label += f" {start_time}"
    if occurrence.end_at and timezone.localtime(occurrence.end_at).date() != timezone.localtime(occurrence.start_at).date():
        # A few hours past midnight still reads as the same evening.
        if occurrence.end_at - occurrence.start_at >= timedelta(hours=20):
            label += f"〜{short_day_label(occurrence.end_at)}"
    return label


def ics_escape(text):
    return (
        str(text or "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )


def _ics_time(value):
    return value.astimezone(dt_timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_ics(event, occurrences, *, url, now=None):
    """An iCalendar file with one VEVENT per occurrence."""
    now = now or timezone.now()
    location = ""
    if event.location:
        location = ", ".join(
            part for part in (event.location.name, event.location.address, event.location.city) if part
        )
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Yapp//Outings//JA",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
    ]
    for occurrence in occurrences:
        end = occurrence.end_at or occurrence.start_at + timedelta(hours=2)
        lines += [
            "BEGIN:VEVENT",
            f"UID:yapp-outings-{event.pk}-{occurrence.pk}@yapp",
            f"DTSTAMP:{_ics_time(now)}",
            f"DTSTART:{_ics_time(occurrence.start_at)}",
            f"DTEND:{_ics_time(end)}",
            f"SUMMARY:{ics_escape(event.title)}",
            f"DESCRIPTION:{ics_escape((event.summary_ja or '') + chr(10) + url)}",
            f"LOCATION:{ics_escape(location)}",
            f"URL:{url}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # RFC 5545 asks for CRLF line endings.
    return "\r\n".join(lines) + "\r\n"
