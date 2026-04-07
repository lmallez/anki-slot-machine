# Changelog

All notable changes to this project will be documented in this file.

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
