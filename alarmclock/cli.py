"""Command-line alarm clock. Standard library only.

Subcommands: set, list, cancel, enable, disable, status, run, ring.
Run ``alarm --help`` or ``alarm <command> --help`` for details.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime, timedelta

from . import __version__
from .models import (
    Alarm,
    compute_next_trigger,
    parse_repeat,
    repeat_label,
    RepeatError,
)
from .sound import Ringer
from .store import AlarmStore, default_store_path
from .timefmt import humanize, parse_when, TimeSpecError

_STATUS_WIDTH = 78


# --------------------------------------------------------------------------- #
# shared UI helpers
# --------------------------------------------------------------------------- #
def _banner(title, when=None):
    when = when or datetime.now()
    bar = "=" * 46
    print("\n" + bar)
    print("  ALARM  " + when.strftime("%H:%M:%S"))
    if title:
        print("  " + title)
    print(bar)


def _status_line(text):
    sys.stdout.write("\r" + text[:_STATUS_WIDTH].ljust(_STATUS_WIDTH))
    sys.stdout.flush()


def _clear_status_line():
    sys.stdout.write("\r" + " " * _STATUS_WIDTH + "\r")
    sys.stdout.flush()


def _dismiss_prompt(snooze_minutes):
    """Return ``('dismiss', 0)`` or ``('snooze', minutes)``."""
    hint = "[Enter] dismiss"
    if snooze_minutes:
        hint += "  |  [s] snooze %dm  |  [s N] snooze N min" % snooze_minutes
    try:
        resp = input("  " + hint + ": ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return ("dismiss", 0)
    if snooze_minutes and resp in ("s", "snooze", "z"):
        return ("snooze", snooze_minutes)
    if snooze_minutes and resp.startswith("s "):
        try:
            return ("snooze", max(1, int(resp[2:].strip())))
        except ValueError:
            return ("snooze", snooze_minutes)
    return ("dismiss", 0)


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
def cmd_set(args, store):
    now = datetime.now()
    try:
        target, kind = parse_when(args.when, now=now)
    except TimeSpecError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2

    repeat = []
    if args.repeat:
        try:
            repeat = parse_repeat(args.repeat)
        except RepeatError as exc:
            print("error: %s" % exc, file=sys.stderr)
            return 2
        if kind == "duration":
            print(
                "error: --repeat needs a clock time (e.g. 07:30), not a duration",
                file=sys.stderr,
            )
            return 2
        target = compute_next_trigger(target.hour, target.minute, repeat, now)

    alarm = Alarm(
        id=0,
        label=args.label or "",
        hour=target.hour,
        minute=target.minute,
        repeat=repeat,
        next_trigger=target.isoformat(timespec="seconds"),
        sound=args.sound,
        snooze_minutes=max(1, args.snooze),
        enabled=True,
        created=now.isoformat(timespec="seconds"),
    )
    alarm = store.add(alarm)

    message = "alarm #%d set for %s (%s from now)" % (
        alarm.id,
        target.strftime("%Y-%m-%d %H:%M"),
        humanize(target - now),
    )
    if repeat:
        message += " repeating " + repeat_label(repeat)
    print(message)

    if args.run:
        return _run_loop(store, once=False)
    return 0


def cmd_list(args, store):
    alarms = sorted(store.load(), key=lambda a: (not a.enabled, a.next_trigger))
    if not alarms:
        print('no alarms.  create one with:  alarm set 07:30 --label "Wake up"')
        return 0
    now = datetime.now()
    print(
        "%3s  %-5s  %-19s  %-16s  %-11s  %s"
        % ("ID", "TIME", "REPEAT", "NEXT", "IN", "LABEL")
    )
    for a in alarms:
        trig = datetime.fromisoformat(a.next_trigger)
        nxt = trig.strftime("%a %m-%d %H:%M")
        rel = humanize(trig - now) if a.enabled else "disabled"
        label = a.label + ("" if a.enabled else "  (off)")
        print(
            "%3d  %02d:%02d  %-19s  %-16s  %-11s  %s"
            % (a.id, a.hour, a.minute, repeat_label(a.repeat), nxt, rel, label)
        )
    return 0


def cmd_cancel(args, store):
    if args.all:
        store.clear()
        print("all alarms cancelled")
        return 0
    if args.id is None:
        print("error: give an alarm id or --all", file=sys.stderr)
        return 2
    if store.remove(args.id):
        print("alarm #%d cancelled" % args.id)
        return 0
    print("error: no alarm #%d" % args.id, file=sys.stderr)
    return 1


def _toggle(store, alarm_id, enabled):
    if store.set_enabled(alarm_id, enabled):
        print("alarm #%d %s" % (alarm_id, "enabled" if enabled else "disabled"))
        return 0
    print("error: no alarm #%d" % alarm_id, file=sys.stderr)
    return 1


def cmd_enable(args, store):
    return _toggle(store, args.id, True)


def cmd_disable(args, store):
    return _toggle(store, args.id, False)


def cmd_status(args, store):
    everything = store.load()
    active = sorted((a for a in everything if a.enabled), key=lambda a: a.next_trigger)
    if not active:
        print("no active alarms (%d total)" % len(everything))
        return 0
    now = datetime.now()
    a = active[0]
    trig = datetime.fromisoformat(a.next_trigger)
    tag = (' "%s"' % a.label) if a.label else ""
    print("next alarm: #%d %s%s" % (a.id, trig.strftime("%A %H:%M"), tag))
    print(
        "  fires in %s  (%s)"
        % (humanize(trig - now), trig.strftime("%Y-%m-%d %H:%M:%S"))
    )
    print("  %d active, %d total" % (len(active), len(everything)))
    return 0


def cmd_ring(args, store):
    now = datetime.now()
    try:
        target, _ = parse_when(args.when, now=now)
    except TimeSpecError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    print(
        "ringing at %s  --  %s from now  (Ctrl-C to cancel)"
        % (target.strftime("%H:%M:%S"), humanize(target - now))
    )
    try:
        _sleep_until(target, args.label)
    except KeyboardInterrupt:
        _clear_status_line()
        print("cancelled")
        return 130
    _clear_status_line()
    _ring_and_wait(args.label, args.sound, snooze_minutes=0)
    return 0


def cmd_run(args, store):
    return _run_loop(store, once=args.once)


# --------------------------------------------------------------------------- #
# ring / loop internals
# --------------------------------------------------------------------------- #
def _sleep_until(target, label):
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        _status_line("  %s: %s remaining" % (label, humanize(target - now)))
        time.sleep(min(1.0, remaining))


def _ring_and_wait(title, sound, snooze_minutes):
    _banner(title)
    ringer = Ringer(sound)
    ringer.start()
    try:
        return _dismiss_prompt(snooze_minutes)
    finally:
        ringer.stop()


def _fire_alarm(alarm, store):
    action, minutes = _ring_and_wait(
        alarm.label or ("alarm #%d" % alarm.id), alarm.sound, alarm.snooze_minutes
    )

    fresh = store.get(alarm.id)
    if fresh is None:  # cancelled from another terminal while ringing
        return

    if action == "snooze":
        target = datetime.now() + timedelta(minutes=minutes)
        fresh.next_trigger = target.isoformat(timespec="seconds")
        store.update(fresh)
        print("  snoozed until %s" % target.strftime("%H:%M:%S"))
        return

    if fresh.repeat:
        target = compute_next_trigger(
            fresh.hour, fresh.minute, fresh.repeat, datetime.now()
        )
        fresh.next_trigger = target.isoformat(timespec="seconds")
        store.update(fresh)
        print("  next occurrence %s" % target.strftime("%Y-%m-%d %H:%M"))
    else:
        store.remove(fresh.id)
        print("  alarm #%d done" % fresh.id)


def _run_loop(store, once=False):
    print("alarm daemon running (pid %d).  Ctrl-C to stop." % os.getpid())
    try:
        while True:
            now = datetime.now()
            active = sorted(
                (a for a in store.load() if a.enabled),
                key=lambda a: a.next_trigger,
            )
            if not active:
                if once:
                    print("no alarms to wait for -- exiting")
                    return 0
                _status_line("  no active alarms")
                time.sleep(2)
                continue

            nxt = active[0]
            trig = datetime.fromisoformat(nxt.next_trigger)
            if trig <= now:
                _clear_status_line()
                _fire_alarm(nxt, store)
                if once:
                    return 0
                continue

            tag = (' "%s"' % nxt.label) if nxt.label else ""
            _status_line(
                "  next: #%d %s%s in %s   (%d active)"
                % (nxt.id, trig.strftime("%H:%M"), tag, humanize(trig - now), len(active))
            )
            time.sleep(min(1.0, (trig - now).total_seconds()))
    except KeyboardInterrupt:
        _clear_status_line()
        print("daemon stopped")
        return 0


# --------------------------------------------------------------------------- #
# entry point
# --------------------------------------------------------------------------- #
def build_parser():
    parser = argparse.ArgumentParser(
        prog="alarm", description="A dependency-free command-line alarm clock."
    )
    parser.add_argument(
        "--version", action="version", version="%(prog)s " + __version__
    )
    parser.add_argument(
        "--store",
        metavar="PATH",
        help="alarms file to use (default: ~/.alarmclock/alarms.json or "
        "$ALARMCLOCK_HOME/alarms.json)",
    )
    sub = parser.add_subparsers(dest="command")

    s = sub.add_parser("set", help="create an alarm")
    s.add_argument(
        "when",
        help="clock time (07:30, 7:30pm) or delay (30m, 1h30m, 'in 45s')",
    )
    s.add_argument("-l", "--label", default="", help="text shown when it rings")
    s.add_argument(
        "-r",
        "--repeat",
        help="daily | weekdays | weekends | comma list e.g. mon,wed,fri",
    )
    s.add_argument(
        "-s", "--sound", metavar="WAV", help="path to a .wav to play instead of beeps"
    )
    s.add_argument(
        "--snooze",
        type=int,
        default=9,
        metavar="MIN",
        help="snooze length in minutes (default 9)",
    )
    s.add_argument(
        "--run",
        action="store_true",
        help="start the ringing daemon right after creating",
    )

    sub.add_parser("list", help="list every alarm")

    c = sub.add_parser("cancel", help="delete an alarm (or --all)")
    c.add_argument("id", nargs="?", type=int)
    c.add_argument("--all", action="store_true", help="delete every alarm")

    en = sub.add_parser("enable", help="re-enable a disabled alarm")
    en.add_argument("id", type=int)
    di = sub.add_parser("disable", help="keep an alarm but stop it ringing")
    di.add_argument("id", type=int)

    r = sub.add_parser("run", help="foreground daemon: ring alarms as they come due")
    r.add_argument(
        "--once",
        action="store_true",
        help="wait for the next alarm, ring it, then exit (don't keep looping)",
    )

    sub.add_parser("status", help="show the next alarm and countdown")

    g = sub.add_parser(
        "ring", help="one-off timer: block now, ring later, nothing saved"
    )
    g.add_argument("when", help="clock time or delay, same formats as 'set'")
    g.add_argument("-l", "--label", default="timer")
    g.add_argument("-s", "--sound", metavar="WAV")

    return parser


_HANDLERS = {
    "set": cmd_set,
    "list": cmd_list,
    "cancel": cmd_cancel,
    "enable": cmd_enable,
    "disable": cmd_disable,
    "run": cmd_run,
    "status": cmd_status,
    "ring": cmd_ring,
}


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    store = AlarmStore(args.store or default_store_path())
    try:
        return _HANDLERS[args.command](args, store) or 0
    except KeyboardInterrupt:
        print()
        return 130


if __name__ == "__main__":
    sys.exit(main())
