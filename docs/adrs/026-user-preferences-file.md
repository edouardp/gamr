---
status: accepted
date: 2026-06-12
deciders: edouard
---

# ADR-026: User Preferences File

## Context and Problem Statement

Some settings are user-specific defaults that shouldn't change per-project (unlike state, which is per-directory). For example, which diff modes to cycle through is a personal preference, not project state.

## Decision Outcome

Add `~/.config/gamr/preferences.toml` for user-level defaults, parsed with Python's built-in `tomllib`.

### Design principles

- **Read-only** — the app never writes to the preferences file; users edit it manually
- **Graceful fallback** — missing file or invalid values silently use defaults
- **Separate from state** — state is per-project, auto-managed; preferences are global, user-managed

### Current settings

| Section     | Key          | Type            | Default                         | Description              |
| ----------- | ------------ | --------------- | ------------------------------- | ------------------------ |
| `[preview]` | `diff_modes` | list of strings | `["full", "gutter", "unified"]` | Modes `d` cycles through |

### Consequences

- Good, because users can customize behaviour without touching code
- Good, because TOML is human-readable and Python 3.11+ has `tomllib` built in
- Neutral, adding new preferences requires updating the `Preferences` class
