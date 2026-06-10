---
status: accepted
date: 2026-06-09
deciders: edouard
---

# ADR-019: Incremental DataTable Updates with Stable Path-Based Keys

## Context and Problem Statement

The original design cleared and rebuilt the entire DataTable on every change (filter, file watcher, timestamp refresh, column toggle). This caused:
- Cursor position loss (requiring complex `restore_cursor` logic)
- Preview scroll resets (RowHighlighted events fired during rebuild)
- Visual flicker (brief empty table)

Multiple guard layers (`_rebuilding` flag, `_displayed_preview`, `_last_highlighted_path`, `_last_rendered_path`) were added to suppress these side effects, creating fragile, hard-to-reason-about code.

## Decision Outcome

Replace clear+rebuild with **incremental updates using stable path-based row keys**:

1. **`visible_rows()`** computes the desired row list from tree state, view mode, and sort
2. **`_sync_table()`** diffs the desired rows against current DataTable rows
3. Only rows that actually changed are added/removed
4. Row keys are `str(path)` — stable across data refreshes (same file = same key)
5. **`update_cell()`** used for in-place updates (timestamps, blame data)

### Key Design Rules

- DataTable is never fully cleared during normal operation
- Cursor stays in place automatically (its row key persists)
- `RowHighlighted` only fires on genuine user navigation
- Column changes still require a full rebuild (DataTable limitation)

### What This Eliminated

- `_rebuilding` synchronous flag (useless against async messages)
- `_displayed_preview` guard tuple
- `restore_cursor` calls for expand/collapse operations
- The scroll-reset bug entirely

### What Remains

- `_last_highlighted_path` — still needed to dedup messages from DataTable
- `_last_rendered_path` in PreviewPane — prevents re-rendering same file
- `restore_cursor` — still used for initial state restore, follow mode, and file-set changes

### Consequences

- Good, because scroll position is inherently stable (no events from rebuilds)
- Good, because the code is simpler (fewer guard layers)
- Good, because filter/watcher updates are faster (only diff, not full rebuild)
- Neutral, order changes still require remove+re-add all rows (DataTable doesn't support reorder)
