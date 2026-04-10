# Changelog

All notable changes to this project will be documented in this file.

## [v0.0.7] - 2026-04-10

- Changed the first-run default to one slot window labeled `Slot 1`.
- Made the `Slots` control start collapsed by default.
- Added configurable spin cadence with `spin_trigger_every_n` and
  `spin_trigger_chance`.

## [v0.0.6] - 2026-04-09

- Switched reel resolution to a position-first backend model so `game.py`
  chooses real landing positions and derives visible symbols from those stops.
- Added real reel-track rotation with config-driven timing, same-event refresh
  protection, and delayed payout/highlight feedback until settle.
- Mixed the reel strip into a stable backend-defined order that preserves the
  configured face counts while reducing visible 3x3 clumping.
- Stopped replaying old spins on startup, slot-window creation, and undo
  refreshes.

## [v0.0.5] - 2026-04-09

- Added multi-slot support with a shared bankroll and stats.
- Added reviewer controls to add, close, and hide slot windows.

## [v0.0.4] - 2026-04-09

- Added a live terminal-style stats window and a `Stats` button in the floating
  slot UI.
- Expanded stored history from `30` to `1000` and reworked stats around recent
  performance.
- Improved window-layout handling, instance-scoped reviewer bindings, and state
  backup loading/writing.

## [v0.0.3] - 2026-04-08

### Added

- Persistent slot window layout saving, including size and position restoration
  across reviewer refreshes and Anki restarts.
- Reviewer tests covering saved window layout refresh and layout persistence
  messages.

### Changed

- Reworked the floating slot window so it can be dragged, resized, closed, and
  reopened from the reviewer.
- Simplified the window chrome to a single close control plus resize handle.
- Fixed the resize architecture so the slot UI uses one stable inner coordinate
  system while the outer window scales around it.
- Improved the fail-state animation so `Again` no longer reuses win-style reel
  highlighting.
- Fixed the loss shake so it follows the current floating window size and
  position correctly.
- Made the floating payout amount much more visible, with stronger styling,
  green positive wins, neutral `-$0`, and amount-based text scaling for large
  wins and losses.
- Cleaned up stale frontend code and removed unused CSS animation leftovers.

## [v0.0.2] - 2026-04-07

### Added

- Packaged slot profile presets under `src/anki_slot_machine/slot_profiles/`.
- Local terminal and plot tools to evaluate real slot distributions.
- Undo support with proper slot-state restoration and persistence tests.

### Changed

- Refactored the slot architecture so the add-on now loads a slot profile file
  as the source of truth for reel faces and pair/triple payouts.
- Updated the `Again` rule so it now runs the slot and removes money using the
  rolled multiplier instead of applying a fixed `-$1`.
- Clamped loss spins so the balance never goes below zero.
- Updated the reviewer UI, tests, and documentation to match the new slot
  profile architecture and `Again` behavior.
