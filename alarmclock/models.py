"""Alarm data model and scheduling maths. Pure functions -- no I/O."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import List, Optional

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

_REPEAT_ALIASES = {
    "daily": list(WEEKDAYS),
    "everyday": list(WEEKDAYS),
    "weekdays": ["mon", "tue", "wed", "thu", "fri"],
    "weekends": ["sat", "sun"],
}


class RepeatError(ValueError):
    """Raised when a ``--repeat`` spec cannot be understood."""


def repeat_label(repeat):
    """Human label for a repeat list: an alias name if it matches one, else the days."""
    if not repeat:
        return "once"
    days = set(repeat)
    for name in ("daily", "weekdays", "weekends"):
        if days == set(_REPEAT_ALIASES[name]):
            return name
    return ",".join(day for day in WEEKDAYS if day in days)


def parse_repeat(spec):
    """``'weekdays'`` / ``'mon,wed,fri'`` -> canonical list of day codes.

    Returns ``[]`` for an empty spec (a one-shot alarm). Day order in the result
    always follows :data:`WEEKDAYS`, regardless of input order, and duplicates
    are collapsed.
    """
    spec = (spec or "").strip().lower()
    if not spec:
        return []
    if spec in _REPEAT_ALIASES:
        return list(_REPEAT_ALIASES[spec])
    chosen = set()
    for token in spec.replace(" ", "").split(","):
        if not token:
            continue
        code = token[:3]
        if code not in WEEKDAYS:
            raise RepeatError("unknown day %r (use mon..sun)" % token)
        chosen.add(code)
    return [day for day in WEEKDAYS if day in chosen]


def compute_next_trigger(hour, minute, repeat, now=None):
    """Next ``datetime`` at ``HH:MM`` satisfying ``repeat`` and after ``now``.

    * ``repeat`` empty  -> today at ``HH:MM``, or tomorrow if already past.
    * ``repeat`` given   -> the nearest future day whose weekday is in ``repeat``.
    """
    now = now or datetime.now()
    base = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if not repeat:
        if base <= now:
            base += timedelta(days=1)
        return base
    wanted = set(repeat)
    for offset in range(8):
        candidate = base + timedelta(days=offset)
        if WEEKDAYS[candidate.weekday()] in wanted and candidate > now:
            return candidate
    return base + timedelta(days=1)  # unreachable, kept as a guard


@dataclass
class Alarm:
    """One scheduled alarm. ``next_trigger`` (ISO string) is authoritative."""

    id: int
    label: str
    hour: int
    minute: int
    repeat: List[str]
    next_trigger: str
    sound: Optional[str] = None
    snooze_minutes: int = 9
    enabled: bool = True
    created: str = ""

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=int(data["id"]),
            label=data.get("label", ""),
            hour=int(data["hour"]),
            minute=int(data["minute"]),
            repeat=list(data.get("repeat") or []),
            next_trigger=data["next_trigger"],
            sound=data.get("sound"),
            snooze_minutes=int(data.get("snooze_minutes", 9)),
            enabled=bool(data.get("enabled", True)),
            created=data.get("created", ""),
        )
