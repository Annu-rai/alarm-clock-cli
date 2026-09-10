"""Make noise, portably. Every failure degrades to the terminal bell."""

from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import threading
import time

_WAV_PLAYERS = (("afplay",), ("paplay",), ("aplay", "-q"))


class Ringer:
    """Loop a beep (or a ``.wav``) on a background thread until :meth:`stop`.

    A hard ``max_seconds`` cap stops the noise if nobody dismisses the alarm, so
    walking away from the keyboard does not mean beeping forever.
    """

    def __init__(self, sound_path=None, max_seconds=120, gap=0.6):
        self.sound_path = sound_path
        self.max_seconds = max_seconds
        self.gap = gap
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)

    # -- internals -------------------------------------------------------
    def _run(self):
        deadline = time.monotonic() + self.max_seconds
        while not self._stop.is_set() and time.monotonic() < deadline:
            try:
                self._beep_once()
            except Exception:
                _bell()
            self._stop.wait(self.gap)

    def _beep_once(self):
        system = platform.system()
        if self.sound_path:
            if system == "Windows":
                import winsound

                winsound.PlaySound(
                    self.sound_path,
                    winsound.SND_FILENAME | winsound.SND_NODEFAULT,
                )
                return
            for cmd in _WAV_PLAYERS:
                if shutil.which(cmd[0]):
                    subprocess.run(
                        [*cmd, self.sound_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        check=False,
                    )
                    return
        if system == "Windows":
            import winsound

            for freq in (880, 988, 1175):
                winsound.Beep(freq, 260)
            return
        _bell()


def _bell():
    try:
        sys.stdout.write("\a")
        sys.stdout.flush()
    except Exception:
        pass
