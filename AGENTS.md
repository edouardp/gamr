# AGENTS.md

Rules and processes for AI agents working on this repo.

## Commit workflow

- Run `uv run pytest` before committing. All tests must pass.
- Pre-commit hooks run automatically (ruff, ruff-format, bandit, shellcheck). If they modify files, re-stage and commit again.
- Commit messages: short imperative sentence. No prefixes like "feat:" or "fix:".
- Push to `main` directly unless asked to use a branch.

## CHANGELOG.md

- **Never** update CHANGELOG.md unless explicitly asked.
- The placeholder `<!-- Fill in release notes -->` stays until a release is requested.
- Only the user decides when to release.

## Documentation

- Update `docs/UI_DESIGN.md` when adding or changing user-facing behavior.
- Update `README.md` keybindings table, features list, and architecture diagram when relevant.
- Create a new ADR in `docs/adrs/` for significant architectural decisions. Follow the format of existing ADRs.
- Update `docs/adrs/README.md` index when adding an ADR.
- Update the built-in help (`src/gamr/widgets/help.py`) when keybindings change.

## Code style

- Python 3.11+. Type hints on function signatures.
- Textual for TUI. Dulwich for git. No git binary dependency.
- App-level keybindings use `priority=True` so they work regardless of focus.
- Widgets are presentational; the app (`app.py`) owns domain logic.
- Match existing patterns. Read before writing.

## Testing

- Run `uv run pytest` to verify.
- Tests are in `tests/`. Use Textual's `run_test()` pilot for TUI tests.
- If something is hard to test manually, write a programmatic test.

## Project structure

```
src/gamr/
├── app.py              # Main app, keybindings, orchestration
├── models.py           # Data types
├── state.py            # Persistent state
├── preferences.py      # User preferences
├── services/           # Business logic (git, scanning, filtering)
└── widgets/            # Presentational TUI widgets
```

## Misc

- `gamr.sh` is the launcher script. It accepts an optional directory argument.
- Logo uses sextant Unicode chars (terminal-detected) with box-drawing fallback.
- The app gracefully degrades on non-git directories.
