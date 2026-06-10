---
status: accepted
date: 2026-06-08
deciders: edouard
---

# ADR-014: Preserve State Across File Watcher Updates

## Context and Problem Statement

When the filesystem watcher detects changes and rebuilds the file index, we must not lose user state: view mode, active filters, sort order, or cursor position.

## Decision Outcome

On file change events, `_handle_file_changes`:

1. Captures the currently selected file path
2. Rebuilds the file index from disk
3. Re-applies the current filter bar state (status filters + search query)
4. Reloads the tree (which preserves view_mode, sort, and column toggles as they're reactive attributes on the widget)
5. Restores the cursor to the previously selected path
6. Falls back to row 0 if the selected file was deleted

### Consequences

- Good, because user never notices the rebuild unless files actually appear/disappear
- Good, because reactive attributes on FileTreeTable survive reload (they're not reset by `load_entries`)
- Neutral, full rebuild on every change; acceptable for typical repos but could be optimized to surgical updates later
