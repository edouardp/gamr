"""Tree data structure building, sorting, and view computation for FileTreeTable.

This module is the single source of truth for what the DataTable should display.
visible_rows() computes the flat list of nodes given tree state, view mode, and sort.
FileTreeTable._sync_table() diffs this against the current table and applies incremental updates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gamr.models import FileEntry


@dataclass
class TreeNode:
    """A node in the file tree."""

    path: Path
    entry: FileEntry | None  # None for directory-only nodes
    depth: int
    expanded: bool = True
    is_dir: bool = False
    children: list[TreeNode] = field(default_factory=list)


def build_tree(entries: list[FileEntry], root_path: Path) -> list[TreeNode]:
    """Build tree nodes from a flat list of file entries."""
    dir_nodes: dict[Path, TreeNode] = {}
    # Virtual root at depth -1 — its children become the top-level nodes
    root_node = TreeNode(path=root_path, entry=None, depth=-1, is_dir=True)
    dir_nodes[root_path] = root_node

    # Sort entries so directories are created in order (parents before children)
    for entry in sorted(entries, key=lambda e: str(e.path)):
        parent_dir = entry.path.parent
        # Lazily create intermediate directory nodes up to root
        _ensure_dir(parent_dir, root_path, dir_nodes)
        depth = len(entry.path.relative_to(root_path).parts)
        node = TreeNode(path=entry.path, entry=entry, depth=depth, is_dir=False)
        dir_nodes[parent_dir].children.append(node)

    return root_node.children


def _ensure_dir(dir_path: Path, root_path: Path, dir_nodes: dict[Path, TreeNode]) -> TreeNode:
    """Recursively ensure all ancestor dirs exist up to root, creating nodes as needed."""
    if dir_path in dir_nodes:
        return dir_nodes[dir_path]
    parent = _ensure_dir(dir_path.parent, root_path, dir_nodes)
    depth = len(dir_path.relative_to(root_path).parts)
    node = TreeNode(path=dir_path, entry=None, depth=depth, is_dir=True)
    dir_nodes[dir_path] = node
    parent.children.append(node)
    return node


def collect_leaves(nodes: list[TreeNode]) -> list[TreeNode]:
    """Recursively collect all non-directory nodes."""
    result: list[TreeNode] = []
    for node in nodes:
        if node.is_dir:
            result.extend(collect_leaves(node.children))
        else:
            result.append(node)
    return result


def visible_rows(
    nodes: list[TreeNode],
    view_mode: str,
    sort_column: str | None = None,
    sort_reverse: bool = False,
) -> list[TreeNode]:
    """Compute the flat list of visible rows given tree state and view mode.

    This is the single source of truth for what the DataTable should display.
    """
    if view_mode == "tree":
        return _visible_tree_rows(nodes)
    else:
        leaves = collect_leaves(nodes)
        if sort_column:
            leaves = sort_leaves(leaves, sort_column, sort_reverse)
        return leaves


def _visible_tree_rows(nodes: list[TreeNode]) -> list[TreeNode]:
    """Recursively collect visible rows in tree mode (respecting expanded state)."""
    result: list[TreeNode] = []
    for node in nodes:
        result.append(node)
        if node.is_dir and node.expanded and node.children:
            result.extend(_visible_tree_rows(node.children))
    return result


def sort_leaves(leaves: list[TreeNode], column: str, reverse: bool) -> list[TreeNode]:
    """Sort leaf nodes by a column key."""

    def sort_key(node: TreeNode):
        entry = node.entry
        if not entry:
            return 0
        match column:
            case "name":
                return entry.name.lower()
            case "size":
                return entry.size
            case "mtime":
                return entry.mtime
            case "status":
                return entry.git_status.value if entry.git_status else ""
            case "lines":
                return (entry.lines_added or 0) + (entry.lines_removed or 0)
            case "author":
                return entry.last_author or ""
            case "git_time":
                return entry.last_git_modified or 0
            case _:
                return 0

    return sorted(leaves, key=sort_key, reverse=reverse)
