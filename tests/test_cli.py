import json
from datetime import datetime, timedelta

import pytest

import alarmclock.cli as climod
from alarmclock.cli import main
from alarmclock.models import Alarm
from alarmclock.store import AlarmStore


class _DummyRinger:
    """Stand-in for sound.Ringer so tests never actually beep."""

    def __init__(self, *args, **kwargs):
        pass

    def start(self):
        pass

    def stop(self):
        pass


@pytest.fixture()
def run(tmp_path, capsys):
    store_path = str(tmp_path / "alarms.json")

    def _run(*args):
        code = main(["--store", store_path, *args])
        captured = capsys.readouterr()
        return code, captured.out, captured.err

    _run.store_path = store_path
    return _run


def test_no_command_prints_help(run):
    code, out, _ = run()
    assert code == 0
    assert "usage" in out.lower()


def test_set_then_list(run):
    code, out, _ = run("set", "07:30", "--label", "Wake up")
    assert code == 0
    assert "alarm #1 set for" in out

    code, out, _ = run("list")
    assert code == 0
    assert "Wake up" in out and "07:30" in out


def test_set_duration_reports_countdown(run):
    code, out, _ = run("set", "in 90m")
    assert code == 0
    assert "from now" in out


def test_set_repeat_persists_days(run):
    code, out, _ = run("set", "07:00", "--repeat", "mon,wed,fri")
    assert code == 0
    assert "repeating mon,wed,fri" in out
    data = json.loads(open(run.store_path, encoding="utf-8").read())
    assert data["alarms"][0]["repeat"] == ["mon", "wed", "fri"]


def test_repeat_with_duration_is_rejected(run):
    code, _, err = run("set", "30m", "--repeat", "daily")
    assert code == 2
    assert "clock time" in err


def test_invalid_time_is_rejected(run):
    code, _, err = run("set", "banana")
    assert code == 2
    assert "understand" in err


def test_cancel_by_id(run):
    run("set", "07:30")
    code, out, _ = run("cancel", "1")
    assert code == 0 and "cancelled" in out
    _, out, _ = run("list")
    assert "no alarms" in out


def test_cancel_unknown_id(run):
    code, _, err = run("cancel", "42")
    assert code == 1
    assert "no alarm #42" in err


def test_cancel_all(run):
    run("set", "07:30")
    run("set", "08:30")
    code, out, _ = run("cancel", "--all")
    assert code == 0
    _, out, _ = run("list")
    assert "no alarms" in out


def test_disable_then_enable(run):
    run("set", "07:30")

    code, out, _ = run("disable", "1")
    assert code == 0 and "disabled" in out
    _, out, _ = run("status")
    assert "no active alarms" in out

    code, out, _ = run("enable", "1")
    assert code == 0 and "enabled" in out
    _, out, _ = run("status")
    assert "next alarm: #1" in out


def test_status_empty(run):
    code, out, _ = run("status")
    assert code == 0
    assert "no active alarms (0 total)" in out


def test_ring_rejects_bad_spec(run):
    code, _, err = run("ring", "nope")
    assert code == 2


# --- run --once fire paths (sound + stdin stubbed) --------------------------
@pytest.fixture()
def no_sound(monkeypatch):
    monkeypatch.setattr(climod, "Ringer", _DummyRinger)


def _add_due(store_path, **overrides):
    store = AlarmStore(store_path)
    past = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="seconds")
    fields = dict(
        id=0, label="Ping", hour=6, minute=0, repeat=[], next_trigger=past
    )
    fields.update(overrides)
    return store.add(Alarm(**fields))


def test_run_once_fires_and_deletes_oneshot(run, no_sound, monkeypatch):
    _add_due(run.store_path)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")  # Enter = dismiss

    code, out, _ = run("run", "--once")
    assert code == 0
    assert "alarm #1 done" in out
    assert AlarmStore(run.store_path).load() == []


def test_run_once_snooze_reschedules(run, no_sound, monkeypatch):
    _add_due(run.store_path)
    monkeypatch.setattr("builtins.input", lambda *a, **k: "s 2")

    code, out, _ = run("run", "--once")
    assert code == 0
    assert "snoozed until" in out
    remaining = AlarmStore(run.store_path).load()
    assert len(remaining) == 1
    assert datetime.fromisoformat(remaining[0].next_trigger) > datetime.now()


def test_run_once_recurring_advances_and_stays(run, no_sound, monkeypatch):
    _add_due(run.store_path, repeat=["mon", "tue", "wed", "thu", "fri", "sat", "sun"])
    monkeypatch.setattr("builtins.input", lambda *a, **k: "")

    code, out, _ = run("run", "--once")
    assert code == 0
    assert "next occurrence" in out
    remaining = AlarmStore(run.store_path).load()
    assert len(remaining) == 1
    assert datetime.fromisoformat(remaining[0].next_trigger) > datetime.now()


def test_run_once_with_no_alarms_exits_immediately(run):
    code, out, _ = run("run", "--once")
    assert code == 0
    assert "no alarms to wait for" in out
