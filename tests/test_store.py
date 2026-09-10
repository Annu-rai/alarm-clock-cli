from alarmclock.models import Alarm
from alarmclock.store import AlarmStore


def _store(tmp_path):
    return AlarmStore(tmp_path / "alarms.json")


def _alarm():
    return Alarm(
        id=0,
        label="wake",
        hour=7,
        minute=0,
        repeat=[],
        next_trigger="2026-09-11T07:00:00",
    )


def test_missing_file_reads_as_empty(tmp_path):
    assert _store(tmp_path).load() == []


def test_add_assigns_incrementing_ids(tmp_path):
    store = _store(tmp_path)
    first = store.add(_alarm())
    second = store.add(_alarm())
    assert (first.id, second.id) == (1, 2)
    assert len(store.load()) == 2


def test_persistence_across_instances(tmp_path):
    _store(tmp_path).add(_alarm())
    reopened = _store(tmp_path)
    assert len(reopened.load()) == 1
    assert reopened.load()[0].label == "wake"


def test_get_update_remove(tmp_path):
    store = _store(tmp_path)
    alarm = store.add(_alarm())

    alarm.label = "changed"
    assert store.update(alarm) is True
    assert store.get(alarm.id).label == "changed"

    assert store.remove(alarm.id) is True
    assert store.get(alarm.id) is None
    assert store.remove(alarm.id) is False


def test_set_enabled(tmp_path):
    store = _store(tmp_path)
    alarm = store.add(_alarm())
    assert store.set_enabled(alarm.id, False) is True
    assert store.get(alarm.id).enabled is False
    assert store.set_enabled(999, False) is False


def test_clear(tmp_path):
    store = _store(tmp_path)
    store.add(_alarm())
    store.add(_alarm())
    store.clear()
    assert store.load() == []


def test_corrupt_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "alarms.json"
    path.write_text("{ not json", encoding="utf-8")
    store = AlarmStore(path)
    assert store.load() == []
    store.add(_alarm())  # still writable afterwards
    assert len(store.load()) == 1


def test_ids_keep_incrementing_after_removal(tmp_path):
    store = _store(tmp_path)
    store.add(_alarm())
    store.add(_alarm())
    store.remove(1)
    third = store.add(_alarm())
    assert third.id == 3
