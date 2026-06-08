"""FileTreeTable — a DataTable with tree semantics in the first column."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path

from rich.text import Text
from textual.binding import Binding
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import DataTable
from textual.widgets.data_table import RowKey

from fooey.models import FileEntry
from fooey.services.git_provider import GitStatus

_STATUS_STYLES = {
    GitStatus.MODIFIED: ("M", "yellow"),
    GitStatus.ADDED: ("A", "green"),
    GitStatus.DELETED: ("D", "red"),
    GitStatus.UNTRACKED: ("?", "dim"),
    GitStatus.STAGED_MODIFIED: ("SM", "cyan"),
    GitStatus.STAGED_ADDED: ("SA", "green bold"),
    GitStatus.STAGED_DELETED: ("SD", "red bold"),
}


@dataclass
class _TreeNode:
    """Internal node tracking tree state."""

    path: Path
    entry: FileEntry | None  # None for directory-only nodes
    depth: int
    expanded: bool = True
    is_dir: bool = False
    children: list[_TreeNode] = field(default_factory=list)


class FileTreeTable(DataTable):
    """File tree rendered as a DataTable with proper column alignment."""

    BINDINGS = [
        Binding("space", "toggle_node", "Expand/Collapse", show=False),
    ]

    show_status = reactive(True)
    show_lines = reactive(True)
    show_size = reactive(True)
    show_mtime = reactive(True)
    show_author = reactive(False)
    show_git_time = reactive(False)

    class NodeHighlighted(Message):
        """Posted when cursor moves to a new row."""

        def __init__(self, entry: FileEntry | None) -> None:
            super().__init__()
            self.entry = entry

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.cursor_type = "row"
        self.zebra_stripes = True
        self._tree_nodes: list[_TreeNode] = []
        self._row_to_node: dict[RowKey, _TreeNode] = {}
        self._root_path: Path = Path(".")

    def on_mount(self) -> None:
        self._setup_columns()

    def _setup_columns(self) -> None:
        self.clear(columns=True)
        self.add_column("Name", key="name", width=None)
        if self.show_status:
            self.add_column("St", key="status", width=4)
        if self.show_lines:
            self.add_column("+/-", key="lines", width=10)
        if self.show_size:
            self.add_column("Size", key="size", width=7)
        if self.show_mtime:
            self.add_column("Modified", key="mtime", width=10)
        if self.show_author:
            self.add_column("Author", key="author", width=14)
        if self.show_git_time:
            self.add_column("Git Time", key="git_time", width=10)

    def load_entries(self, entries: list[FileEntry], root_path: Path) -> None:
        """Populate the table from a list of FileEntry objects."""
        self._root_path = root_path
        self._tree_nodes = self._build_tree(entries, root_path)
        self._rebuild_table()

    def _build_tree(self, entries: list[FileEntry], root_path: Path) -> list[_TreeNode]:
        """Build a flat list of tree nodes with depth info from file entries."""
        # Group files by their directory
        dir_nodes: dict[Path, _TreeNode] = {}
        root_node = _TreeNode(path=root_path, entry=None, depth=-1, is_dir=True)
        dir_nodes[root_path] = root_node

        for entry in sorted(entries, key=lambda e: str(e.path)):
            # Ensure parent directory nodes exist
            parent_dir = entry.path.parent
            self._ensure_dir(parent_dir, root_path, dir_nodes)
            # Add file as leaf
            depth = len(entry.path.relative_to(root_path).parts)
            node = _TreeNode(path=entry.path, entry=entry, depth=depth, is_dir=False)
            dir_nodes[parent_dir].children.append(node)

        return root_node.children

    def _ensure_dir(self, dir_path: Path, root_path: Path, dir_nodes: dict[Path, _TreeNode]) -> _TreeNode:
        if dir_path in dir_nodes:
            return dir_nodes[dir_path]
        parent = self._ensure_dir(dir_path.parent, root_path, dir_nodes)
        depth = len(dir_path.relative_to(root_path).parts)
        node = _TreeNode(path=dir_path, entry=None, depth=depth, is_dir=True)
        dir_nodes[dir_path] = node
        parent.children.append(node)
        return node

    def _rebuild_table(self) -> None:
        """Clear and repopulate the DataTable from the tree state."""
        self._setup_columns()
        self._row_to_node.clear()
        self._add_visible_nodes(self._tree_nodes)

    def _add_visible_nodes(self, nodes: list[_TreeNode]) -> None:
        """Recursively add visible nodes as rows."""
        for node in nodes:
            row_data = self._make_row(node)
            row_key = self.add_row(*row_data, key=str(id(node)))
            self._row_to_node[row_key] = node
            if node.is_dir and node.expanded and node.children:
                self._add_visible_nodes(node.children)

    def _make_row(self, node: _TreeNode) -> list:
        """Build the cell values for a single row."""
        cells = []

        # Column 1: Name with tree indentation
        indent = "  " * (node.depth - 1) if node.depth > 0 else ""
        if node.is_dir:
            icon = "▼ " if node.expanded else "▶ "
            name_text = Text(f"{indent}{icon}{node.path.name}/", style="bold")
        else:
            name_text = Text(f"{indent}  {node.path.name}")
        cells.append(name_text)

        entry = node.entry

        # Status column
        if self.show_status:
            if entry and entry.git_status and entry.git_status in _STATUS_STYLES:
                sym, color = _STATUS_STYLES[entry.git_status]
                cells.append(Text(sym, style=color))
            else:
                cells.append("")

        # Lines +/- column
        if self.show_lines:
            if entry and (entry.lines_added is not None or entry.lines_removed is not None):
                t = Text()
                t.append(f"+{entry.lines_added or 0}", style="green")
                t.append(f"/-{entry.lines_removed or 0}", style="red")
                cells.append(t)
            else:
                cells.append("")

        # Size column
        if self.show_size:
            if entry:
                cells.append(Text(_human_size(entry.size), style="dim", justify="right"))
            else:
                cells.append("")

        # Mtime column
        if self.show_mtime:
            if entry:
                cells.append(Text(_relative_time(entry.mtime), style="dim"))
            else:
                cells.append("")

        # Author column
        if self.show_author:
            if entry and entry.last_author:
                cells.append(Text(entry.last_author[:13], style="dim italic"))
            elif entry:
                cells.append(Text("...", style="dim"))
            else:
                cells.append("")

        # Git time column
        if self.show_git_time:
            if entry and entry.last_git_modified:
                cells.append(Text(_relative_time(entry.last_git_modified), style="dim italic"))
            elif entry:
                cells.append(Text("...", style="dim"))
            else:
                cells.append("")

        return cells

    def action_toggle_node(self) -> None:
        """Toggle expand/collapse of the currently highlighted row."""
        if self.row_count == 0:
            return
        row_key, _ = self.coordinate_to_cell_key(self.cursor_coordinate)
        node = self._row_to_node.get(row_key)
        if node and node.is_dir:
            node.expanded = not node.expanded
            self._rebuild_table()

    def on_data_table_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        """Post our own message with the FileEntry when row changes."""
        node = self._row_to_node.get(event.row_key)
        entry = node.entry if node else None
        self.post_message(self.NodeHighlighted(entry))

    def watch_show_status(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()

    def watch_show_lines(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()

    def watch_show_size(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()

    def watch_show_mtime(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()

    def watch_show_author(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()

    def watch_show_git_time(self, value: bool) -> None:
        if self._tree_nodes:
            self._rebuild_table()


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
