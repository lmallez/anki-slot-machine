# Contributing

Thanks for helping with `anki-slot-machine`.

This repo is small on purpose, so the best contributions are focused, readable,
and easy to review.

## Workflow

1. Create a branch from `main`.
2. Keep each pull request scoped to one topic.
3. Prefer small, reviewable changes over broad refactors.
4. Update tests and docs when behavior changes.
5. Make sure local checks pass before opening a PR.

## Local checks

Run these before asking for review:

```bash
make check
make test
```

Useful optional commands:

```bash
make real-slot-report
make real-slot-plot
```

## Project rules

- Do not change Anki scheduling, intervals, note fields, or card content.
- Keep slot logic and UI logic separated.
- Keep profile changes inside `src/anki_slot_machine/slot_profiles/`.
- Prefer updating existing tests over adding untested behavior.
- If a change affects the add-on page text, update `src/anki_slot_machine/README.md`.
- If a change affects the GitHub/project page text, update `README.md`.
- If a change affects a released behavior, update `CHANGELOG.md`.

## Sensitive files

The following files are intentionally treated as protected and should be edited
carefully:

- `.github/workflows/*`
- `build.sh`
- `install.sh`
- `src/anki_slot_machine/manifest.json`
- `src/anki_slot_machine/config.json`
- `src/anki_slot_machine/slot_profiles/*`
- `src/anki_slot_machine/README.md`
- `CHANGELOG.md`

For these files:

- avoid drive-by edits in unrelated PRs
- explain clearly why the change is needed
- prefer one dedicated PR if the change is release- or distribution-related

## Pull request guidance

A good PR description should include:

- what changed
- why it changed
- how it was tested
- whether docs or config/profile files changed

## Style

- Keep changes simple and explicit.
- Avoid hidden magic in the slot economy.
- Prefer stable, boring architecture over clever abstractions.
- Preserve the reviewer safety guarantee: this add-on is a UI/game layer, not a scheduler modification.
