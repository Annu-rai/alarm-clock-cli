from datetime import datetime, timedelta

import pytest

from alarmclock.models import (
    Alarm,
    compute_next_trigger,
    parse_repeat,
    repeat_label,
    RepeatError,
)

# 2026-09-10 14:30 is a Thursday (weekday() == 3).
THU = datetime(2026, 9, 10, 14, 30)


def test_parse_repeat_empty():
    assert parse_repeat("") == []
    assert parse_repeat(None) == []


def test_parse_repeat_aliases():
    assert parse_repeat("daily") == ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    assert parse_repeat("weekdays") == ["mon", "tue", "wed", "thu", "fri"]
    assert parse_repeat("weekends") == ["sat", "sun"]


def test_parse_repeat_list_is_canonicalised():
    assert parse_repeat("fri,mon,wed") == ["mon", "wed", "fri"]
    assert parse_repeat("Mon, monday, MON") == ["mon"]


def test_parse_repeat_invalid():
    with pytest.raises(RepeatError):
        parse_repeat("funday")


def test_repeat_label():
    assert repeat_label([]) == "once"
    assert repeat_label(["mon", "tue", "wed", "thu", "fri"]) == "weekdays"
    assert repeat_label(["sat", "sun"]) == "weekends"
    assert repeat_label(parse_repeat("daily")) == "daily"
    assert repeat_label(["mon", "fri"]) == "mon,fri"


def test_next_trigger_oneshot_future():
    assert compute_next_trigger(15, 0, [], THU) == THU.replace(
        hour=15, minute=0, second=0
    )


def test_next_trigger_oneshot_past_rolls_a_day():
    assert compute_next_trigger(14, 0, [], THU) == THU.replace(
        hour=14, minute=0, second=0
    ) + timedelta(days=1)


def test_next_trigger_repeat_same_day_still_ahead():
    result = compute_next_trigger(18, 0, ["thu"], THU)
    assert result.weekday() == 3 and (result.hour, result.minute) == (18, 0)
    assert result.date() == THU.date()


def test_next_trigger_repeat_same_weekday_but_past_jumps_a_week():
    result = compute_next_trigger(9, 0, ["thu"], THU)
    assert result == THU.replace(hour=9, minute=0, second=0) + timedelta(days=7)


def test_next_trigger_repeat_picks_nearest_future_day():
    # Thursday now; alarm on Mondays and Fridays -> Friday (tomorrow).
    result = compute_next_trigger(9, 0, ["mon", "fri"], THU)
    assert result.weekday() == 4
    assert result == THU.replace(hour=9, minute=0, second=0) + timedelta(days=1)


def test_alarm_dict_roundtrip():
    alarm = Alarm(
        id=7,
        label="Wake up",
        hour=7,
        minute=30,
        repeat=["mon", "fri"],
        next_trigger="2026-09-14T07:30:00",
        sound="C:/chime.wav",
        snooze_minutes=5,
    )
    assert Alarm.from_dict(alarm.to_dict()) == alarm


def test_alarm_from_dict_tolerates_missing_optional_fields():
    alarm = Alarm.from_dict(
        {"id": 1, "hour": 6, "minute": 0, "next_trigger": "2026-09-11T06:00:00"}
    )
    assert alarm.label == "" and alarm.repeat == [] and alarm.enabled is True
    assert alarm.snooze_minutes == 9
