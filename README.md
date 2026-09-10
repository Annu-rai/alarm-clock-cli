# alarm — a command-line alarm clock

[![CI](https://github.com/Annu-rai/alarm-clock-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/Annu-rai/alarm-clock-cli/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A small, dependency-free alarm clock for your terminal. Standard library only,
cross-platform (Windows / macOS / Linux), no web UI, no database — alarms live in
one human-readable JSON file.

See [`DESIGN.md`](DESIGN.md) for the requirements/design/plan write-up.

## Quick start

```console
$ python -m alarmclock set 07:30 --label "Wake up" --repeat weekdays
alarm #1 set for 2026-09-11 07:30 (11h 52m 48s from now) repeating weekdays

$ python -m alarmclock set "in 20m" --label "Tea"
alarm #2 set for 2026-09-10 20:05 (20m from now)

$ python -m alarmclock list
 ID  TIME   REPEAT               NEXT              IN           LABEL
  2  20:05  once                 Thu 09-10 20:05   20m          Tea
  1  07:30  weekdays             Fri 09-11 07:30   11h 52m 48s  Wake up

$ python -m alarmclock run        # blocks here, rings alarms as they come due
alarm daemon running (pid 41210).  Ctrl-C to stop.
  next: #2 20:05 "Tea" in 19m 41s   (2 active)
```

When an alarm fires:

```
==============================================
  ALARM  20:05:00
  Tea
==============================================
  [Enter] dismiss  |  [s] snooze 9m  |  [s N] snooze N min:
```

> **Note** — alarms only ring while `alarm run` (or `alarm ring`) is in the
> foreground. There is no background service. To have alarms fire unattended,
> launch `alarm run` from Task Scheduler / cron / a login item.

## Install

Run it straight from the source tree with no install:

```console
python -m alarmclock <command>
```

Or install it to get the short `alarm` command:

```console
pip install .          # then:  alarm set 07:30 -l "Wake up"
```

## Commands

| Command | What it does |
|---|---|
| `set <when>` | Create an alarm. `--label/-l`, `--repeat/-r`, `--sound/-s`, `--snooze MIN`, `--run`. |
| `list` | Show every alarm with its next fire time and countdown. |
| `status` | Show just the next alarm and time remaining. |
| `cancel <id>` / `cancel --all` | Delete one alarm, or all of them. |
| `disable <id>` / `enable <id>` | Keep an alarm but stop / resume it ringing. |
| `run` | Foreground loop: live countdown, rings due alarms, reschedules recurring ones. `--once` = wait for the next alarm, ring it, then exit. |
| `ring <when>` | One-off timer: block now, ring at the target, save nothing. |

### `<when>` formats

- **Clock time** — `7`, `07:30`, `7:30pm`, `23:15`, `12:00am`. If it's already
  past today, it rolls to tomorrow (unless `--repeat` is set).
- **Delay** — `45s`, `30m`, `90m`, `1h`, `1h30m`, `2h15m30s`, optionally written
  `in 30m` / `after 1h` / `+90m`.

### `--repeat` formats

`daily`, `weekdays`, `weekends`, or a comma list of day codes: `mon,wed,fri`
(order doesn't matter). Requires a clock time, not a delay.

## Examples

```console
alarm set 06:45 -l "Gym" -r mon,wed,fri
alarm set "1h30m" -l "Laundry"
alarm set 22:30 -l "Wind down" -r daily --snooze 5
alarm set "in 10m" -l "Stand up" --run          # create, then start the loop
alarm ring "5m" -l "Pomodoro"                    # quick throwaway timer
alarm set 08:00 -l "Wake" -s ~/sounds/chime.wav  # custom .wav instead of beeps
```

## Where alarms are stored

`~/.alarmclock/alarms.json` by default. Override with the `ALARMCLOCK_HOME`
environment variable (the file is `alarms.json` inside it) or a per-command
`--store PATH`. Writes are atomic (temp file + rename); a missing or corrupt file
is treated as empty.

## Sound

- **Windows** — `winsound.Beep` (a short three-tone chime), or `winsound.PlaySound`
  for a `--sound file.wav`.
- **macOS / Linux** — `afplay` / `paplay` / `aplay` for a `--sound file.wav`.
- **Fallback everywhere** — the terminal bell (`\a`).

A sound failure never crashes or blocks the alarm; it falls back to the bell. The
ring loop stops itself after ~2 minutes if nobody dismisses it.

## Development

```console
pip install -e ".[dev]"
python -m pytest        # 65 tests, ~0.3s
```

CI runs the suite on every push and pull request across Linux, macOS, and
Windows on Python 3.9 / 3.11 / 3.13
([`.github/workflows/ci.yml`](.github/workflows/ci.yml)).

Layout: `timefmt` (parsing), `models` (Alarm + scheduling maths), `store` (JSON
persistence), `sound` (the `Ringer` thread), `cli` (argparse + command handlers).
The parsing/scheduling core is pure and takes an injectable `now`, so it is
tested without sleeping or making noise.

## License

[MIT](LICENSE) © Annu-rai
