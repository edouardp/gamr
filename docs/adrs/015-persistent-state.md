---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-015: Persistent App State Between Sessions

## Context and Problem Statement

Users expect to resume where they left off. Without persistence, every launch resets view mode, column toggles, collapsed folders, and selection.

## Decision Outcome

Persist app state to `~/.config/gamr/state.json` on quit. Restore on next launch if the saved state matches the current target directory.

### Persisted State

- View mode, diff mode, column toggles, spaced paths, gradient
- Collapsed directory set (relative paths)
- Split pane fraction
- Selected file path
- Selected filter IDs and search query

### Design Choices

- **Per-directory state**: Only restored if `target` path matches. Different directories get independent state.
- **JSON format**: Human-readable, easy to debug, no dependencies.
- **Save on quit only**: No continuous writes. State is captured from live widget reactives at exit time.
- **Graceful fallback**: If state file is missing, corrupted, or for a different directory, all defaults apply.

### Consequences

- Good, because users resume exactly where they left off
- Good, because collapsed folders persist (important for large repos)
- Neutral, only one state file (last directory wins); could extend to per-directory files later
