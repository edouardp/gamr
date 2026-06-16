---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-015: Persistent App State Between Sessions

## Context and Problem Statement

Users expect to resume where they left off. Without persistence, every launch resets view mode, column toggles, collapsed folders, and selection.

## Decision Outcome

Persist app state to `$XDG_STATE_HOME/gamr/<hash>.json` (defaulting to `~/.local/state/gamr/`) on quit. Each target directory gets its own state file, keyed by a truncated SHA-256 hash of the resolved path.

### Persisted State

- View mode, diff mode, column toggles, spaced paths, gradient
- Collapsed directory set (relative paths)
- Split pane fraction
- Selected file path
- Selected filter IDs and search query

### Design Choices

- **Per-directory state**: Each directory gets an independent state file via path hashing. State is only restored if the saved `target` path matches.
- **XDG compliance**: Uses `$XDG_STATE_HOME` (not config) since this is runtime state, not user configuration.
- **JSON format**: Human-readable, easy to debug, no dependencies.
- **Save on quit only**: No continuous writes. State is captured from live widget reactives at exit time.
- **Graceful fallback**: If state file is missing, corrupted, or for a different directory, all defaults apply.

### Consequences

- Good, because users resume exactly where they left off
- Good, because collapsed folders persist (important for large repos)
- Good, because multiple directories maintain independent state simultaneously
