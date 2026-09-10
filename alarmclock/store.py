"""JSON-file persistence for alarms -- no database, atomic writes."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import Alarm

SCHEMA_VERSION = 1


def default_store_path():
    """``$ALARMCLOCK_HOME/alarms.json`` or ``~/.alarmclock/alarms.json``."""
    home = os.environ.get("ALARMCLOCK_HOME")
    base = Path(home) if home else Path.home() / ".alarmclock"
    return base / "alarms.json"


class AlarmStore:
    """Load/mutate/save a list of :class:`~alarmclock.models.Alarm`.

    Every public method reads the file fresh and (for mutations) writes it back
    atomically, so two processes sharing a store never see a half-written file.
    """

    def __init__(self, path):
        self.path = Path(path)

    # -- low level -----------------------------------------------------------
    def _read(self):
        try:
            with open(self.path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, dict):
                data = {}
        except (FileNotFoundError, ValueError):
            data = {}
        data.setdefault("version", SCHEMA_VERSION)
        data.setdefault("next_id", 1)
        data.setdefault("alarms", [])
        return data

    def _write(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name("%s.%d.tmp" % (self.path.name, os.getpid()))
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp, self.path)

    # -- public API --------------------------------------------------------
    def load(self):
        return [Alarm.from_dict(item) for item in self._read()["alarms"]]

    def next_id(self):
        return self._read()["next_id"]

    def add(self, alarm):
        """Assign the next id, append, persist, return the stored alarm."""
        data = self._read()
        alarm.id = data["next_id"]
        data["next_id"] = alarm.id + 1
        data["alarms"].append(alarm.to_dict())
        self._write(data)
        return alarm

    def get(self, alarm_id):
        for item in self._read()["alarms"]:
            if item["id"] == alarm_id:
                return Alarm.from_dict(item)
        return None

    def update(self, alarm):
        data = self._read()
        for index, item in enumerate(data["alarms"]):
            if item["id"] == alarm.id:
                data["alarms"][index] = alarm.to_dict()
                self._write(data)
                return True
        return False

    def remove(self, alarm_id):
        data = self._read()
        kept = [i for i in data["alarms"] if i["id"] != alarm_id]
        if len(kept) == len(data["alarms"]):
            return False
        data["alarms"] = kept
        self._write(data)
        return True

    def clear(self):
        data = self._read()
        data["alarms"] = []
        self._write(data)

    def set_enabled(self, alarm_id, enabled):
        alarm = self.get(alarm_id)
        if alarm is None:
            return False
        alarm.enabled = enabled
        return self.update(alarm)
