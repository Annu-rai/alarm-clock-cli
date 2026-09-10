# Alarm Clock CLI — Requirements, Design & Plan

This document is the "think before coding" pass. It captures the requirements
refinement, the design decisions, and the implementation plan that the code in
this repo follows.

---

## 1. Requirements refinement

The brief was one line: *"Build an alarm clock as a Python CLI application.
CLI only, no web UI, no database. Decide what to build."* I refined that into a
concrete spec by asking and answering the questions a spec would normally settle.

### Q&A

**Q: What is the core job of the tool?**
Let a person schedule a time (or a countdown) at which the terminal will make
noise and show a message, and manage a small set of such schedules.

**Q: One-shot timers, wall-clock alarms, or both?**
Both. They cover different needs — "remind me in 10 minutes" vs. "wake me at
07:30" — and share almost all the machinery. Also support **recurring** alarms
(daily / weekdays / specific weekdays) because a real alarm clock repeats.

**Q: Does it need a always-on background daemon?**
No. A CLI that forks a real background service is a much bigger, OS-specific
project (launchd / systemd / Task Scheduler / pythonw). Scope that out. Instead:
alarms are **stored**, and a **foreground `run` command** blocks in the terminal,
shows a live countdown, and rings alarms as they come due. That is honest about
what a single process can do and still genuinely useful. A pure "fire once now"
mode (`ring`) covers the quick-timer case without touching storage.

**Q: Persistence — the brief says no database.**
A single JSON file under `~/.alarmclock/` (overridable via `$ALARMCLOCK_HOME` or
`--store`). Human-readable, diffable, zero dependencies, written atomically
(temp file + `os.replace`) so a crash mid-write can't corrupt it. That is not a
"database" in any meaningful sense.

**Q: How does it make noise, portably?**
Layered fallback: `winsound.Beep` on Windows; `afplay` / `paplay` / `aplay` for a
user-supplied `.wav` on macOS/Linux; the terminal bell (`\a`) as the universal
last resort. A sound failure must never crash or block the alarm — it is wrapped
and degrades to the bell.

**Q: What must the ring interaction do?**
Print a clear banner (label + time), beep on a repeating loop from a background
thread, and prompt: `[Enter] dismiss` / `[s] snooze` / `[s N] snooze N minutes`.
Ctrl-C or EOF counts as dismiss. Snooze re-arms the same alarm N minutes out.

**Q: Third-party libraries?**
None for the runtime. Standard library only — it ships everywhere Python does and
keeps the tool trivially auditable. `pytest` is the only dev dependency.

**Q: Python version?**
3.9+. Uses `datetime.fromisoformat`, `dataclasses`, `argparse` — all long-stable.

### Functional requirements (the settled spec)

| # | Requirement |
|---|-------------|
| F1 | Create an alarm from a **clock time** (`07:30`, `7:30pm`, `23:15`) — rolls to tomorrow if already past today. |
| F2 | Create an alarm from a **delay** (`30m`, `1h30m`, `90m`, `45s`, `in 10m`, `+2h`). |
| F3 | **Recurring** alarms: `--repeat daily|weekdays|weekends|mon,wed,fri`. |
| F4 | Optional **label** shown when the alarm rings. |
| F5 | Optional **custom sound** (`--sound path.wav`). |
| F6 | **List** all alarms with their next fire time and countdown. |
| F7 | **Cancel** one alarm by id, or `--all`. |
| F8 | **Enable / disable** an alarm without deleting it. |
| F9 | **`status`** — the next alarm and time remaining. |
| F10 | **`run`** — foreground loop: live countdown, rings due alarms, reschedules recurring ones, deletes spent one-shots. `--once` waits for the next alarm, rings it, then exits. |
| F11 | **`ring <when>`** — ephemeral: block now, ring at the target, persist nothing. |
| F12 | When ringing: banner, looping sound, **dismiss / snooze / snooze N**. |
| F13 | Alarms **persist** across invocations in a JSON file; location overridable. |

### Non-functional

- Standard library only at runtime; cross-platform (Windows / macOS / Linux).
- Atomic, corruption-safe writes; tolerant of a missing/empty/partial store file.
- Pure, `now`-injectable time logic so it is unit-testable without sleeping.
- Clear `--help` for every subcommand; sensible exit codes (0 ok, 1 not-found,
  2 bad usage, 130 interrupted).
- ASCII-only output (safe on a default Windows code page).

### Out of scope (deliberately)

- A true OS background service / auto-start on boot.
- Web UI, TUI, React, any GUI.
- A database engine or any network access.
- Audio synthesis / bundled sound files / volume control.
- Multi-user, timezones other than the host's local time, natural-language dates
  ("next Tuesday").

---

## 2. Design

### Module layout (flat package, `alarmclock/`)

| Module | Responsibility |
|--------|----------------|
| `timefmt.py` | Parse time specs (`parse_when` → `(datetime, kind)`), parse durations, `humanize(timedelta)`. Pure functions, `now` injected. |
| `models.py` | `Alarm` dataclass + `to_dict`/`from_dict`; `parse_repeat`; `compute_next_trigger(hour, minute, repeat, now)`. Pure. |
| `store.py` | `AlarmStore` — JSON load/save, atomic write, `add`/`get`/`update`/`remove`/`clear`/`set_enabled`, id allocation. `default_store_path()`. |
| `sound.py` | `Ringer` — background thread that loops a beep/wav until `stop()`, with a hard time cap. All failures degrade to the terminal bell. |
| `cli.py` | `argparse` wiring, the eight subcommand handlers, the ring/countdown loops, `main()`. |
| `__main__.py` | `python -m alarmclock`. |

Dependency direction: `cli` → (`timefmt`, `models`, `store`, `sound`); those four
do not import each other except `store` → `models`. Keeps the testable core free
of I/O.

### Data model

```jsonc
// ~/.alarmclock/alarms.json
{
  "version": 1,
  "next_id": 4,
  "alarms": [
    {
      "id": 3,
      "label": "Wake up",
      "hour": 7, "minute": 30,
      "repeat": ["mon", "tue", "wed", "thu", "fri"],  // [] => one-shot
      "next_trigger": "2026-09-11T07:30:00",          // authoritative fire time
      "sound": null,                                   // or "C:/sounds/chime.wav"
      "snooze_minutes": 9,
      "enabled": true,
      "created": "2026-09-10T21:14:03"
    }
  ]
}
```

`next_trigger` is always kept in sync so `list`/`status`/`run` never recompute to
decide *whether* to fire — only after firing, a recurring alarm's `next_trigger`
is advanced via `compute_next_trigger`.

### Scheduling logic

- **One-shot**: `next_trigger` = the parsed datetime; if `<= now`, add one day.
- **Recurring**: from `HH:MM` today, walk forward up to 7 days to the first day
  whose weekday code is in `repeat` and whose datetime is strictly after `now`.
- **Snooze**: `next_trigger = now + snooze_minutes`; alarm otherwise unchanged.
- `run` sleeps in ≤1s slices so the countdown stays live and newly added alarms
  (from another terminal) are picked up within a second — the store is re-read
  every tick.

### Ring UX

```
==============================================
  ALARM  07:30:00
  Wake up
==============================================
  [Enter] dismiss  |  [s] snooze 9m  |  [s N] snooze N min:
```

Sound loops from a daemon thread (`threading.Event` to stop, ~2 min hard cap so a
walk-away doesn't beep forever). The prompt runs on the main thread.

### Error / exit-code contract

| Code | Meaning |
|------|---------|
| 0 | success |
| 1 | referenced alarm id not found |
| 2 | bad usage / unparseable time / `--repeat` with a duration |
| 130 | interrupted (Ctrl-C) |

---

## 3. Implementation plan

1. **`timefmt.py`** — duration regex, clock regex (with am/pm), `parse_when`,
   `humanize`. Unit tests first (frozen `now`).
2. **`models.py`** — `Alarm` dataclass, `parse_repeat` (aliases + `mon,wed`),
   `compute_next_trigger` (one-shot + recurring, nearest-day). Unit tests.
3. **`store.py`** — `_read`/`_write` (atomic, fault-tolerant), CRUD, id counter,
   `default_store_path`. Round-trip + persistence tests using `tmp_path`.
4. **`sound.py`** — `Ringer` thread with platform beep + wav players + bell
   fallback, all guarded. (Not unit-tested — side-effecting; kept tiny.)
5. **`cli.py`** — parser + handlers: `set`, `list`, `cancel`, `enable`,
   `disable`, `status`, `run`, `ring`. Countdown + fire loops.
6. **`__main__.py`**, `pyproject.toml` (console script `alarm`), `conftest.py`.
7. **Integration tests** driving `main([...])` with `--store tmp` for every
   command that doesn't block on sound/stdin.
8. **README** — quickstart, command reference, examples.

## 4. Risks & trade-offs

- **No real daemon** → alarms only fire while `alarm run` is open. Accepted;
  documented. A user can wrap it in Task Scheduler / cron / a login item.
- **Beep quality** varies by OS and terminal; `\a` may be silent if the terminal
  bell is disabled. `--sound file.wav` is the escape hatch.
- **Concurrent writes** (daemon + a second `alarm set`) use last-write-wins with
  atomic replace. Fine for a single-user local tool; not a multi-writer store.
- **Second-level precision** only; drift under heavy system load is possible but
  bounded by the ≤1s poll.
