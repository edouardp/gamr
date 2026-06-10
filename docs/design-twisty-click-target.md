# Design: Click-Target-Specific Tree Twisty

## Goal

Only toggle expand/collapse when the user clicks on the `▶`/`▼` character itself, not anywhere on the directory row.

## Current Behaviour

Clicking anywhere on a directory row triggers `on_data_table_row_selected` → toggles expand/collapse. This matches VS Code and Finder list view UX.

## Proposed Approach

### 1. Override `on_click` on FileTreeTable

DataTable's `on_click` provides the mouse event with screen coordinates. We can intercept it before the default row selection fires.

```python
def on_click(self, event: Click) -> None:
    # Get the row at click position
    row_idx = self._get_row_at_y(event.y)
    node = self._get_node_at_row(row_idx)

    if node and node.is_dir:
        # Calculate twisty x position within the Name column
        twisty_x = self._get_twisty_offset(node)
        # Check if click x falls on the twisty character (±1 for tolerance)
        if abs(event.x - twisty_x) <= 1:
            node.expanded = not node.expanded
            self._rebuild_table()
            self.restore_cursor(node.path)
            event.stop()  # Prevent default row selection
```

### 2. Calculate Twisty Position

The twisty offset within the Name cell depends on:

- **Row label column width** (if visible): `show_row_labels` width
- **Cell padding**: `DataTable.cell_padding` (default 1) on each side
- **Indent**: `2 * (node.depth - 1)` characters
- **Column offset**: sum of all columns to the left of Name (Name is first, so 0)

```python
def _get_twisty_offset(self, node: TreeNode) -> int:
    # Account for: row labels + left cell padding + indent
    padding = self.cell_padding
    indent = 2 * (node.depth - 1) if node.depth > 0 else 0
    return padding + indent
```

### 3. Challenges

| Issue | Impact | Mitigation |
|-------|--------|------------|
| DataTable doesn't expose `_get_row_at_y` publicly | Need to use `get_row_at` or coordinate math | Use `self.scroll_offset.y + event.y - header_height` |
| Column widths may change on rebuild | Twisty offset calculation becomes stale | Recalculate on each click |
| Fixed columns/scrolling | Horizontal scroll shifts x position | Subtract `self.scroll_offset.x` |
| Row height > 1 | Y calculation assumes 1-row height | Check `get_row_height` |
| Unicode character width | `▶` is 1 cell wide, but some fonts render wider | Use ±1 tolerance |

### 4. Alternative: Rich Click Markup

If Rich/Textual ever supports `[@click]` markup within Text renderables (like `[@click=toggle_node(id)]▶[/]`), we could make the twisty itself a clickable link. This would be the cleanest approach but requires upstream Textual support.

### 5. Recommendation

Keep the whole-row click for now. It's the standard UX pattern. If we implement twisty-only clicking:

1. Add it as an **option** (not replacing the current behaviour)
2. Fall back to whole-row click if the position calculation seems off
3. Add visual feedback (cursor changes to pointer on hover over twisty)

### 6. Testing

- Click at exact twisty position → toggles
- Click elsewhere on the row → selects but doesn't toggle
- Click on file row → no toggle regardless of position
- Verify after scrolling horizontally/vertically
- Verify with different cell_padding values
