"""FileTreeTable — a DataTable with tree semantics in the first column.

Uses stable path-based row keys so the cursor is never displaced by data refreshes.
Updates are incremental: _sync_table() diffs desired vs current rows and only
adds/removes what changed. Column toggles, view mode, and sort are reactive attributes
that trigger a re-sync. The 10s timestamp refresh uses update_cell() for zero disruption.
"""

from __future__ import annotations

import time
from enum import Enum
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable

from gamr.config import GRADIENT_COLORS
from gamr.models import FileEntry, GitStatus
from gamr.services.icons import IconResolver
from gamr.widgets.tree_data import TreeNode, build_tree, collect_leaves


class ViewMode(Enum):
    """Display modes for the file list."""

    FLAT_NAME = "flat"
    TREE = "tree"
    FLAT_PATH = "flat_path"


_STATUS_STYLES = {
    GitStatus.MODIFIED: ("M", "yellow"),
    GitStatus.ADDED: ("A", "green"),
    GitStatus.DELETED: ("D", "red"),
    GitStatus.UNTRACKED: ("?", "dim"),
    GitStatus.STAGED_MODIFIED: ("SM", "cyan"),
    GitStatus.STAGED_ADDED: ("SA", "green bold"),
    GitStatus.STAGED_DELETED: ("SD", "red bold"),
}

# xterm-256 color indices forming a blue→purple→red gradient for magnitude visualization
_GRADIENT_COLORS = GRADIENT_COLORS


def _gradient_style(value: float, min_val: float, max_val: float, log_scale: bool = False) -> str:
    """Map a value to a gradient color string (normalized across all visible entries)."""
    if max_val <= min_val:
        return f"color({_GRADIENT_COLORS[0]})"
    ratio = (value - min_val) / (max_val - min_val)
    if log_scale:
        ratio = max(0.0, ratio)
    idx = int(ratio * (len(_GRADIENT_COLORS) - 1))
    idx = max(0, min(len(_GRADIENT_COLORS) - 1, idx))
    return f"color({_GRADIENT_COLORS[idx]})"


def _mtime_color_index(mtime: float, min_t: float, max_t: float) -> int:
    """Map an mtime to a color index (0=coldest, 15=hottest).

    Uses log(age) so that recency differences are perceptually uniform:
    minutes-old files are visually distinct from hours-old, which are
    distinct from days-old. Range is stable (computed from all project files).
    """
    import math
    import time

    now = time.time()
    age = max(60.0, now - mtime)  # clamp minimum age to 1 minute
    max_age = max(60.0, now - min_t)  # oldest file's age
    min_age = 60.0

    log_min = math.log(min_age)
    log_max = math.log(max_age)
    if log_max <= log_min:
        return len(_GRADIENT_COLORS) - 1  # single file → hottest
    # Invert: small age (recent) = hot, large age (old) = cold
    log_age = math.log(age)
    ratio = 1.0 - (log_age - log_min) / (log_max - log_min)
    ratio = max(0.0, min(1.0, ratio))
    # Bias toward hot end
    ratio = ratio**0.7
    idx = int(ratio * (len(_GRADIENT_COLORS) - 1))
    return max(0, min(len(_GRADIENT_COLORS) - 1, idx))


def _human_size(size: int) -> str:
    for unit in ("B", "K", "M", "G"):
        if size < 1024:
            return f"{size:.0f}{unit}" if unit == "B" else f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}T"


def _relative_time(ts: float) -> str:
    if ts == 0:
        return ""
    delta = time.time() - ts
    if delta < 60:
        return "just now"
    elif delta < 3600:
        return f"{int(delta // 60)}m ago"
    elif delta < 86400:
        return f"{int(delta // 3600)}h ago"
    elif delta < 604800:
        return f"{int(delta // 86400)}d ago"
    else:
        return f"{int(delta // 604800)}w ago"


class FileTreeTable(DataTable):
    """File tree rendered as a DataTable with proper column alignment."""

    BINDINGS = [
        Binding("space", "toggle_node", "Expand/Collapse", show=False),
        Binding("right", "expand_node", "Expand", show=False),
        Binding("left", "collapse_node", "Collapse", show=False),
    ]

    show_status = reactive(True)
    show_lines = reactive(True)
    show_size = reactive(True)
    show_mtime = reactive(True)
    show_author = reactive(False)
    show_git_time = reactive(False)
    view_mode = reactive(ViewMode.TREE)
    spaced_paths = reactive(True)
    gradient_colors = reactive(True)

    class NodeHighlighted(Message):
        """Posted when cursor moves to a new row."""

        def __init__(self, entry: FileEntry | None) -> None:
            super().__init__()
            self.entry = entry

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._tree_nodes: list[TreeNode] = []
        self._row_to_node: dict[str, TreeNode] = {}  # key=str(path) → node
        self._root_path: Path = Path(".")
        self._size_range: tuple[float, float] = (0, 0)
        self._mtime_range: tuple[float, float] = (0, 0)
        self._global_mtime_range: tuple[float, float] = (0, 0)
        self._icons = IconResolver()
        self._sort_column: str | None = None
        self._sort_direction: str = "none"  # "asc", "desc", or "none"
        # Saved view mode so we can restore it when sort is cleared (tree can't sort)
        self._pre_sort_view_mode: ViewMode | None = None
        # Persistent collapsed state — survives filtering where dirs may disappear
        self._collapsed_dirs: set[str] = set()

    def on_mount(self) -> None:
        self._ensure_columns()

    # --- Public API ---

    def load_entries(self, entries: list[FileEntry], root_path: Path, collapsed_dirs: set[str] | None = None) -> None:
        """Populate the table from a list of FileEntry objects."""
        self._root_path = root_path
        self._tree_nodes = build_tree(entries, root_path)
        if collapsed_dirs:
            self._collapsed_dirs.update(collapsed_dirs)
        self._apply_collapsed(self._tree_nodes, self._collapsed_dirs)
        self._rebuild_table()

    def _apply_collapsed(self, nodes: list[TreeNode], collapsed_dirs: set[str]) -> None:
        """Apply collapsed state to tree nodes from saved state."""
        for node in nodes:
            if node.is_dir:
                try:
                    rel = str(node.path.relative_to(self._root_path))
                except ValueError:
                    rel = node.path.name
                if rel in collapsed_dirs:
                    node.expanded = False
                if node.children:
                    self._apply_collapsed(node.children, collapsed_dirs)

    def get_collapsed_dirs(self) -> set[str]:
        """Return relative paths of all currently collapsed directories."""
        self._sync_collapsed_from_tree()
        return set(self._collapsed_dirs)

    def _sync_collapsed_from_tree(self) -> None:
        """Sync persistent collapsed set from current tree node state."""
        self._update_collapsed(self._tree_nodes)

    def _update_collapsed(self, nodes: list[TreeNode]) -> None:
        for node in nodes:
            if node.is_dir:
                try:
                    rel = str(node.path.relative_to(self._root_path))
                except ValueError:
                    rel = node.path.name
                if node.expanded:
                    self._collapsed_dirs.discard(rel)
                else:
                    self._collapsed_dirs.add(rel)
                if node.children:
                    self._update_collapsed(node.children)

    def get_current_entry(self) -> FileEntry | None:
        """Return the FileEntry for the currently highlighted row."""
        node = self._get_cursor_node()
        return node.entry if node else None

    def _get_cursor_node(self) -> TreeNode | None:
        """Return the TreeNode at the current cursor position."""
        if self.row_count == 0:
            return None
        row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        return self._row_to_node.get(row_key.value)

    def refresh_data(self) -> None:
        """Rebuild the table, preserving cursor position."""
        if not self._tree_nodes:
            return
        entry = self.get_current_entry()
        selected_path = entry.path if entry else None
        self._rebuild_table()
        self.restore_cursor(selected_path)

    def refresh_time_cells(self) -> None:
        """Update only the mtime/git_time cells in-place (no rebuild)."""
        for row_key, node in self._row_to_node.items():
            if not node.entry:
                continue
            if self.show_mtime:
                self.update_cell(row_key, "mtime", self._render_mtime_cell(node.entry))
            if self.show_git_time:
                self.update_cell(row_key, "git_time", self._render_git_time_cell(node.entry))

    def restore_cursor(self, path: Path | None) -> None:
        """Move cursor to the row matching the given path, or row 0."""
        if path and self.row_count > 0:
            key = str(path)
            if key in self._row_to_node:
                try:
                    self.move_cursor(row=self.get_row_index(key))
                except Exception:
                    pass
                return
        if self.row_count > 0:
            self.move_cursor(row=0)

    # --- Actions ---

    def action_toggle_node(self) -> None:
        """Toggle expand/collapse of the currently highlighted row."""
        node = self._get_cursor_node()
        if node and node.is_dir:
            node.expanded = not node.expanded
            self._sync_table()

    def action_expand_node(self) -> None:
        """Expand the currently highlighted directory."""
        if self.view_mode != ViewMode.TREE:
            return
        node = self._get_cursor_node()
        if node and node.is_dir and not node.expanded:
            node.expanded = True
            self._sync_table()

    def action_collapse_node(self) -> None:
        """Collapse current dir, or navigate to parent if on file/collapsed dir.

        UI rule (see docs/UI_DESIGN.md → Navigation):
        ← on expanded dir: collapse it, cursor stays
        ← on file/collapsed dir: collapse parent, cursor moves to parent
        ← at root or in flat mode: no action
        """
        if self.view_mode != ViewMode.TREE:
            return
        node = self._get_cursor_node()
        if not node:
            return
        if node.is_dir and node.expanded:
            node.expanded = False
            self._sync_table()
        else:
            parent_path = node.path.parent
            if parent_path == self._root_path:
                return
            parent_node = self._find_node_by_path(self._tree_nodes, parent_path)
            if parent_node and parent_node.expanded:
                parent_node.expanded = False
                self._sync_table()
                self.restore_cursor(parent_path)

    def _find_node_by_path(self, nodes: list[TreeNode], path: Path) -> TreeNode | None:
        """Find a tree node by its path."""
        for node in nodes:
            if node.path == path:
                return node
            if node.is_dir and node.children:
                found = self._find_node_by_path(node.children, path)
                if found:
                    return found
        return None

    def action_cycle_view(self) -> None:
        """Cycle through view modes."""
        modes = list(ViewMode)
        idx = modes.index(self.view_mode)
        self.view_mode = modes[(idx + 1) % len(modes)]

    # --- Event handlers ---

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Always post NodeHighlighted — the app decides what to do with it."""
        node = self._row_to_node.get(event.row_key.value)
        entry = node.entry if node else None
        if entry is not None:
            self.post_message(self.NodeHighlighted(entry))

    def on_data_table_header_selected(self, event: DataTable.HeaderSelected) -> None:
        """Cycle sort on column header click."""
        col_key = event.column_key.value if hasattr(event.column_key, "value") else str(event.column_key)

        # Columns where descending is the natural first sort (newest/largest first)
        desc_first = {"mtime", "size", "lines", "git_time"}

        if self._sort_column == col_key:
            # Already sorting this column — cycle to next state
            if self._sort_direction == "desc" and col_key in desc_first:
                self._sort_direction = "asc"
            elif self._sort_direction == "asc" and col_key not in desc_first:
                self._sort_direction = "desc"
            else:
                # Clear sort, restore tree view if needed
                self._sort_column = None
                self._sort_direction = "none"
                if self._pre_sort_view_mode is not None:
                    self.view_mode = self._pre_sort_view_mode
                    self._pre_sort_view_mode = None
                self._refresh_column_labels()
                self._rebuild_table()
                return
        else:
            # New column: start with natural direction
            self._sort_column = col_key
            self._sort_direction = "desc" if col_key in desc_first else "asc"

        if self.view_mode == ViewMode.TREE:
            self._pre_sort_view_mode = ViewMode.TREE
            self.view_mode = ViewMode.FLAT_PATH
        else:
            self._rebuild_table()
        self._refresh_column_labels()

    # --- Watchers ---

    def watch_show_status(self, value: bool) -> None:
        self._on_column_changed()

    def watch_show_lines(self, value: bool) -> None:
        self._on_column_changed()

    def watch_show_size(self, value: bool) -> None:
        self._on_column_changed()

    def watch_show_mtime(self, value: bool) -> None:
        self._on_column_changed()

    def watch_show_author(self, value: bool) -> None:
        self._on_column_changed()

    def watch_show_git_time(self, value: bool) -> None:
        self._on_column_changed()

    def watch_view_mode(self, value: ViewMode) -> None:
        self._on_column_changed()

    def watch_spaced_paths(self, value: bool) -> None:
        if self._tree_nodes and self.view_mode == ViewMode.FLAT_PATH:
            self._rebuild_table()

    def watch_gradient_colors(self, value: bool) -> None:
        self._on_column_changed()

    def _on_column_changed(self) -> None:
        if self._tree_nodes:
            self._sync_table()

    # --- Internal table building ---

    def _sync_table(self) -> None:
        """Sync the DataTable to match the current desired view (incremental).

        Computes the visible row list, then diffs against what's displayed:
        - Rows present in new but not old → add_row
        - Rows present in old but not new → remove_row
        - Rows in both but at wrong position or with stale data → remove + re-add
        For column config changes, falls back to full rebuild.
        """
        from gamr.widgets.tree_data import visible_rows

        # If columns changed, we must do a full clear (can't incrementally change columns)
        if not self._ensure_columns():
            self._rebuild_all_rows()
            return

        # Compute desired rows
        self._compute_ranges()
        new_rows = visible_rows(
            self._tree_nodes,
            self.view_mode.value,
            self._sort_column,
            self._sort_direction == "desc",
        )
        new_keys = [str(n.path) for n in new_rows]
        old_keys = list(self._row_to_node.keys())

        # Fast path: if row keys and order are identical, update cells in-place
        if old_keys == new_keys:
            self._update_existing_rows(new_rows)
        else:
            self._replace_rows(new_rows, old_keys, set(new_keys))

        self._fit_name_column()

    def _rebuild_all_rows(self) -> None:
        """Full clear and rebuild (used when columns change)."""
        from gamr.widgets.tree_data import visible_rows

        self._row_to_node.clear()
        self._compute_ranges()
        new_rows = visible_rows(
            self._tree_nodes,
            self.view_mode.value,
            self._sort_column,
            self._sort_direction == "desc",
        )
        flat = self.view_mode != ViewMode.TREE
        show_path = self.view_mode == ViewMode.FLAT_PATH
        for node in new_rows:
            self._insert_row(node, flat, show_path)
        self._fit_name_column()

    def _update_existing_rows(self, new_rows: list) -> None:
        """Update cells in-place when row set and order are unchanged."""
        flat = self.view_mode != ViewMode.TREE
        show_path = self.view_mode == ViewMode.FLAT_PATH
        for node in new_rows:
            key = str(node.path)
            self._row_to_node[key] = node
            self._update_row_cells(key, node, flat, show_path)

    def _replace_rows(self, new_rows: list, old_keys: list[str], new_key_set: set[str]) -> None:
        """Remove old rows and re-add in correct order (DataTable can't reorder)."""
        for key in old_keys:
            if key not in new_key_set:
                try:
                    self.remove_row(key)
                except Exception:
                    pass
                self._row_to_node.pop(key, None)

        for key in list(self._row_to_node.keys()):
            try:
                self.remove_row(key)
            except Exception:
                pass
        self._row_to_node.clear()

        flat = self.view_mode != ViewMode.TREE
        show_path = self.view_mode == ViewMode.FLAT_PATH
        for node in new_rows:
            self._insert_row(node, flat, show_path)

    def _fit_name_column(self) -> None:
        """Shrink the Name column's content_width to match the widest visible row."""
        col = self.columns.get("name")
        if col is None:
            return
        max_w = col.label.cell_len
        for node in self._row_to_node.values():
            cell = self._render_name_cell(node, self.view_mode != ViewMode.TREE, self.view_mode == ViewMode.FLAT_PATH)
            max_w = max(max_w, cell.cell_len)
        col.content_width = max_w

    def _insert_row(self, node: TreeNode, flat: bool = False, show_path: bool = False) -> None:
        """Add a single row to the DataTable using path as stable key."""
        cells = [self._render_name_cell(node, flat, show_path)]
        entry = node.entry
        if self.show_status:
            cells.append(self._render_status_cell(entry))
        if self.show_lines:
            cells.append(self._render_lines_cell(entry))
        if self.show_size:
            cells.append(self._render_size_cell(entry))
        if self.show_mtime:
            cells.append(self._render_mtime_cell(entry))
        if self.show_author:
            cells.append(self._render_author_cell(entry))
        if self.show_git_time:
            cells.append(self._render_git_time_cell(entry))
        key = str(node.path)
        self.add_row(*cells, key=key)
        self._row_to_node[key] = node

    def _update_row_cells(self, key: str, node: TreeNode, flat: bool, show_path: bool) -> None:
        """Update all cells for an existing row in-place."""
        entry = node.entry
        self.update_cell(key, "name", self._render_name_cell(node, flat, show_path))
        if self.show_status:
            self.update_cell(key, "status", self._render_status_cell(entry))
        if self.show_lines:
            self.update_cell(key, "lines", self._render_lines_cell(entry))
        if self.show_size:
            self.update_cell(key, "size", self._render_size_cell(entry))
        if self.show_mtime:
            self.update_cell(key, "mtime", self._render_mtime_cell(entry))
        if self.show_author:
            self.update_cell(key, "author", self._render_author_cell(entry))
        if self.show_git_time:
            self.update_cell(key, "git_time", self._render_git_time_cell(entry))

    def _ensure_columns(self) -> bool:
        """Ensure correct columns exist. Returns True if no change needed, False if rebuilt."""
        needed = ["name"]
        if self.show_status:
            needed.append("status")
        if self.show_lines:
            needed.append("lines")
        if self.show_size:
            needed.append("size")
        if self.show_mtime:
            needed.append("mtime")
        if self.show_author:
            needed.append("author")
        if self.show_git_time:
            needed.append("git_time")

        current_keys = [k.value for k in self.columns] if self.columns else []
        if current_keys == needed:
            return True  # No change

        # Columns changed — full clear and re-add
        self.clear(columns=True)
        self.add_column(self._col_label("Name", "name"), key="name", width=None)
        if self.show_status:
            self.add_column(self._col_label("St", "status"), key="status", width=4)
        if self.show_lines:
            self.add_column(self._col_label("+/-", "lines"), key="lines", width=10)
        if self.show_size:
            self.add_column(self._col_label("Size", "size"), key="size", width=7)
        if self.show_mtime:
            self.add_column(self._col_label("Modified", "mtime"), key="mtime", width=10)
        if self.show_author:
            self.add_column(self._col_label("Author", "author"), key="author", width=14)
        if self.show_git_time:
            self.add_column(self._col_label("Git Time", "git_time"), key="git_time", width=10)
        return False

    # Keep legacy name for callers
    _rebuild_table = _sync_table

    def _col_label(self, label: str, key: str) -> str:
        if self._sort_column == key:
            return f"{label} {'▼' if self._sort_direction == 'desc' else '▲'}"
        return label

    def _refresh_column_labels(self) -> None:
        """Update column header labels to show current sort indicators."""
        col_keys = {
            "name": "Name",
            "status": "St",
            "lines": "+/-",
            "size": "Size",
            "mtime": "Modified",
            "author": "Author",
            "git_time": "Git Time",
        }
        for key, label in col_keys.items():
            if key in self.columns:
                from rich.text import Text

                self.columns[key].label = Text(self._col_label(label, key))

    def _compute_ranges(self) -> None:
        leaves = collect_leaves(self._tree_nodes)
        sizes = [n.entry.size for n in leaves if n.entry and n.entry.size > 0]
        mtimes = [n.entry.mtime for n in leaves if n.entry and n.entry.mtime > 0]
        self._size_range = (min(sizes), max(sizes)) if sizes else (0, 0)
        # Use global range for stable colors across filter changes
        if mtimes and not self._global_mtime_range[1]:
            self._mtime_range = (min(mtimes), max(mtimes))
        else:
            self._mtime_range = self._global_mtime_range

    def set_global_mtime_range(self, min_t: float, max_t: float) -> None:
        """Set the mtime range from all project files (stable across filtering)."""
        self._global_mtime_range = (min_t, max_t)
        self._mtime_range = (min_t, max_t)

    # --- Cell renderers ---

    def _render_name_cell(self, node: TreeNode, flat: bool, show_path: bool) -> Text:
        if flat:
            icon = self._icons.get_icon(node.path, node.is_dir)
            if show_path:
                try:
                    rel = str(node.path.relative_to(self._root_path))
                except ValueError:
                    rel = node.path.name
                if self.spaced_paths:
                    rel = rel.replace("/", " / ")
                return Text(f"{icon} {rel}")
            return Text(f"{icon} {node.path.name}")

        indent = "  " * (node.depth - 1) if node.depth > 0 else ""
        icon = self._icons.get_icon(node.path, is_dir=node.is_dir)
        if node.is_dir:
            arrow = "▼ " if node.expanded else "▶ "
            return Text(f"{indent}{arrow}{icon} {node.path.name}/", style="bold")
        return Text(f"{indent}  {icon} {node.path.name}")

    def _render_status_cell(self, entry: FileEntry | None) -> Text | str:
        if entry and entry.git_status and entry.git_status in _STATUS_STYLES:
            sym, color = _STATUS_STYLES[entry.git_status]
            return Text(sym, style=color)
        return ""

    def _render_lines_cell(self, entry: FileEntry | None) -> Text | str:
        if entry and (entry.lines_added is not None or entry.lines_removed is not None):
            t = Text()
            t.append(f"+{entry.lines_added or 0}", style="green")
            t.append(f"/-{entry.lines_removed or 0}", style="red")
            return t
        return ""

    def _render_size_cell(self, entry: FileEntry | None) -> Text | str:
        if not entry:
            return ""
        return Text(_human_size(entry.size), style="dim", justify="right")

    def _render_mtime_cell(self, entry: FileEntry | None) -> Text | str:
        if not entry:
            return ""
        style = "dim"
        if self.gradient_colors and entry.mtime > 0:
            idx = _mtime_color_index(entry.mtime, *self._mtime_range)
            style = f"color({_GRADIENT_COLORS[idx]})"
        return Text(_relative_time(entry.mtime), style=style)

    def _render_author_cell(self, entry: FileEntry | None) -> Text | str:
        if not entry:
            return ""
        if entry.last_author:
            return Text(entry.last_author[:13], style="dim italic")
        return Text("...", style="dim")

    def _render_git_time_cell(self, entry: FileEntry | None) -> Text | str:
        if not entry:
            return ""
        if entry.last_git_modified:
            return Text(_relative_time(entry.last_git_modified), style="dim italic")
        return Text("...", style="dim")
