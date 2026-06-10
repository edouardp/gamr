---
status: accepted
date: 2026-06-11
deciders: edouard
---

# ADR-024: Single Git Modified Filter Keybinding

## Context and Problem Statement

The FilterBar had five toggle buttons (M, A, D, ?, S) for git status filtering plus a separate `m` keybinding. This was visually noisy and rarely used — the common case is toggling between "all files" and "modified files only."

## Decision Outcome

Replace all filter buttons with a single `g` keybinding that toggles the git modified filter. The filter bar now contains only the search input.

### Key changes

- Removed all `Button` widgets from `FilterBar`
- Added `FilterBar.toggle_modified()` method for programmatic toggling
- State persistence only tracks `"modified"` as a valid filter ID; legacy filter IDs are discarded on load
- Collapsed folder state is preserved across filter toggles via a persistent `_collapsed_dirs` set on `FileTreeTable`

### Consequences

- Good, because the UI is cleaner — one keybinding replaces five buttons
- Good, because collapsed folders are no longer lost when toggling the filter (dirs that disappear from the filtered tree retain their state)
- Neutral, individual status filters (added, deleted, untracked, staged) are no longer directly accessible. The search input still provides file-level filtering.
- Bad (acceptable), old state files with non-"modified" filter IDs are silently ignored on load
