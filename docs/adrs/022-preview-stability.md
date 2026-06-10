---
status: accepted
date: 2026-06-10
deciders: edouard
---

# ADR-022: Preview Pane Stability

## Context

File watcher updates cause the DataTable to sync rows (add/remove), which can move the cursor and fire `NodeHighlighted` events. This was causing the preview pane to jump to a different file when unrelated files were added or removed.

Additionally, when the previewed file's content changes on disk, re-rendering would reset the scroll to the top.

## Decision

### 1. Suppress preview changes during file watcher sync

A `_suppress_preview` flag is set `True` during `_handle_file_changes` → `load_entries`. The `on_file_tree_table_node_highlighted` handler exits early when suppressed. Follow mode handles its own preview update after the flag is cleared.

### 2. Preserve scroll by source line on content change

When the previewed file changes on disk:
1. Save current source line (`get_source_line_at_scroll`)
2. Invalidate and re-render (`scroll_to_top=False`)
3. Restore scroll to same source line (`scroll_to_source_line`)

The `_row_to_source` mapping allows translating between display rows (which change in diff mode when removed lines are inserted) and source file line numbers (which are stable).

## Consequences

- Good: preview stays on the selected file regardless of tree churn
- Good: viewing lines 100-140 remains stable even when lines are added above
- Good: follow mode still overrides both behaviors as expected
- Neutral: source line mapping means the view tracks the *logical* position, not pixel position
