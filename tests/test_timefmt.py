from datetime import datetime, timedelta

import pytest

from alarmclock.timefmt import humanize, parse_duration, parse_when, TimeSpecError

# A fixed "now" so clock-time tests are deterministic. 2026-09-10 is a Thursday.
NOW = datetime(2026, 9, 10, 14, 30, 0)


@pytest.mark.parametrize(
    "text,seconds",
    [
        ("30m", 1800),
        ("1h", 3600),
        ("1h30m", 5400),
        ("90m", 5400),
        ("45s", 45),
        ("2h15m30s", 8130),
        ("  1h 5m ", 3900),
    ],
)
def test_parse_duration(text, seconds):
    assert parse_duration(text).total_seconds() == seconds


@pytest.mark.parametrize("text", ["", "banana", "07:30", "5", "1x"])
def test_parse_duration_rejects_non_durations(text):
    assert parse_duration(text) is None


def test_parse_when_duration_with_prefix():
    target, kind = parse_when("in 10m", now=NOW)
    assert kind == "duration"
    assert target == NOW + timedelta(minutes=10)


def test_parse_when_plus_prefix():
    target, kind = parse_when("+2h", now=NOW)
    assert kind == "duration"
    assert target == NOW + timedelta(hours=2)


def test_parse_when_clock_future_today():
    target, kind = parse_when("15:00", now=NOW)
    assert kind == "clock"
    assert target == NOW.replace(hour=15, minute=0)


def test_parse_when_clock_past_rolls_to_tomorrow():
    target, _ = parse_when("14:00", now=NOW)
    assert target == NOW.replace(hour=14, minute=0) + timedelta(days=1)


def test_parse_when_ampm():
    assert parse_when("7:30pm", now=NOW)[0].hour == 19
    assert parse_when("7:30pm", now=NOW)[0].minute == 30
    assert parse_when("12:00am", now=NOW)[0].hour == 0
    assert parse_when("12:00pm", now=NOW)[0].hour == 12


def test_parse_when_bare_hour():
    target, kind = parse_when("9", now=NOW)
    assert kind == "clock"
    assert (target.hour, target.minute) == (9, 0)


def test_parse_when_at_prefix():
    target, _ = parse_when("at 16:45", now=NOW)
    assert (target.hour, target.minute) == (16, 45)


@pytest.mark.parametrize("text", ["banana", "25:00", "12:99", "0s"])
def test_parse_when_invalid(text):
    with pytest.raises(TimeSpecError):
        parse_when(text, now=NOW)


@pytest.mark.parametrize(
    "delta,expected",
    [
        (timedelta(seconds=0), "0s"),
        (timedelta(seconds=5), "5s"),
        (timedelta(minutes=1, seconds=5), "1m 5s"),
        (timedelta(hours=2, minutes=3), "2h 3m"),
        (timedelta(hours=1), "1h"),
        (timedelta(seconds=-10), "overdue"),
    ],
)
def test_humanize(delta, expected):
    assert humanize(delta) == expected
