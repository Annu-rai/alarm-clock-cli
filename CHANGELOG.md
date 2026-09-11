# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.1] - 2026-09-11

### Changed

- README: documented installing straight from a tagged release
  (`pip install git+...@v0.1.0`), plus `pipx` alternative.
- README: added a release-version badge.
- Packaging: added `[project.urls]` (Repository, Issues, Changelog) to
  `pyproject.toml` so they surface on PyPI-style project pages.

## [0.1.0] - 2026-09-10

Initial release.

### Added

- `set <when>` — create an alarm from a **clock time** (`07:30`, `7:30pm`,
  `23:15`; rolls to tomorrow if already past) or a **delay** (`45s`, `30m`,
  `1h30m`, `in 10m`, `+90m`).
- **Recurring alarms** via `--repeat daily|weekdays|weekends|mon,wed,fri`.
- Per-alarm `--label`, custom `--sound` (`.wav`), and `--snooze MIN`.
- `list` — every alarm with its next fire time and countdown.
- `status` — the next alarm and time remaining.
- `cancel <id>` / `cancel --all`.
- `disable <id>` / `enable <id>` — keep an alarm but silence it.
- `run` — foreground loop with a live countdown that rings due alarms,
  reschedules recurring ones, and deletes spent one-shots; `--once` waits for
  the next alarm, rings it, then exits. `set ... --run` creates then starts it.
- `ring <when>` — ephemeral timer: block now, ring at the target, persist nothing.
- Ring interaction: banner, looping sound, `[Enter]` dismiss / `[s]` snooze /
  `[s N]` snooze N minutes; Ctrl-C / EOF counts as dismiss.
- Atomic JSON persistence at `~/.alarmclock/alarms.json`, overridable with
  `$ALARMCLOCK_HOME` or `--store PATH`; missing or corrupt files read as empty.
- Cross-platform sound: `winsound` on Windows, `afplay`/`paplay`/`aplay` for a
  `.wav` on macOS/Linux, terminal bell everywhere as a fallback; a ~2-minute cap
  so an undismissed alarm stops on its own.
- Standard-library-only runtime; `console_scripts` entry point `alarm`.
- 65 tests; GitHub Actions CI across Linux/macOS/Windows on Python 3.9/3.11/3.13.

[Unreleased]: https://github.com/Annu-rai/alarm-clock-cli/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/Annu-rai/alarm-clock-cli/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/Annu-rai/alarm-clock-cli/releases/tag/v0.1.0
