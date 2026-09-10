"""Parse human time specs and format durations. Standard library only.

Two kinds of input are understood by :func:`parse_when`:

* a **duration** -- ``30m``, ``1h30m``, ``90m``, ``45s``, ``2h15m30s``
  (optionally prefixed with ``in ``/``after ``/``+``)
* a **wall-clock time** -- ``7``, ``07:30``, ``7:30pm``, ``23:15``, ``12:00am``
  (optionally prefixed with ``at ``); if the time is already past today it
  rolls to the same time tomorrow.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

_DURATION_RE = re.compile(
    r"^\s*(?:(?P<hours>\d+)\s*h)?"
    r"\s*(?:(?P<minutes>\d+)\s*m)?"
    r"\s*(?:(?P<seconds>\d+)\s*s)?\s*$",
    re.IGNORECASE,
)

_CLOCK_RE = re.compile(
    r"^\s*(?P<hour>\d{1,2})"
    r"(?::(?P<minute>\d{2}))?"
    r"(?::(?P<second>\d{2}))?"
    r"\s*(?P<ampm>am|pm)?\s*$",
    re.IGNORECASE,
)

_PREFIXES = ("in ", "after ", "at ", "+")


class TimeSpecError(ValueError):
    """Raised when a time spec cannot be parsed."""


def parse_duration(text):
    """``'1h30m'`` -> :class:`~datetime.timedelta`; ``None`` if not a duration."""
    match = _DURATION_RE.match(text)
    if not match or not any(match.groupdict().values()):
        return None
    parts = {key: int(value) for key, value in match.groupdict().items() if value}
    return timedelta(
        hours=parts.get("hours", 0),
        minutes=parts.get("minutes", 0),
        seconds=parts.get("seconds", 0),
    )


def parse_clock(text, now):
    """``'7:30pm'`` -> next :class:`~datetime.datetime` at that wall-clock time."""
    match = _CLOCK_RE.match(text)
    if not match:
        return None
    hour = int(match["hour"])
    minute = int(match["minute"] or 0)
    second = int(match["second"] or 0)
    meridiem = (match["ampm"] or "").lower()
    if meridiem:
        if not 1 <= hour <= 12:
            raise TimeSpecError("hour %d is not valid with am/pm" % hour)
        if meridiem == "am":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        raise TimeSpecError("%r is not a valid clock time" % text.strip())
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def parse_when(text, now=None):
    """Return ``(datetime, kind)`` where ``kind`` is ``'duration'`` or ``'clock'``.

    ``now`` is injectable for testing; it defaults to :func:`datetime.now`.
    """
    now = now or datetime.now()
    cleaned = text.strip()
    lowered = cleaned.lower()
    for prefix in _PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
            break

    duration = parse_duration(cleaned)
    if duration is not None:
        if duration.total_seconds() <= 0:
            raise TimeSpecError("duration must be greater than zero")
        return now + duration, "duration"

    clock = parse_clock(cleaned, now)
    if clock is not None:
        return clock, "clock"

    raise TimeSpecError(
        "could not understand time %r "
        "(try 07:30, 7:30pm, 30m, 1h30m, 'in 45s')" % text
    )


def humanize(delta):
    """Format a :class:`~datetime.timedelta` as ``'2h 3m'`` / ``'45s'``."""
    total = int(round(delta.total_seconds()))
    if total < 0:
        return "overdue"
    hours, rest = divmod(total, 3600)
    minutes, seconds = divmod(rest, 60)
    chunks = []
    if hours:
        chunks.append("%dh" % hours)
    if minutes:
        chunks.append("%dm" % minutes)
    if seconds or not chunks:
        chunks.append("%ds" % seconds)
    return " ".join(chunks)
