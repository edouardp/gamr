"""Tests for tree_data.py sort logic."""

from pathlib import Path

from gamr.models import FileEntry, GitStatus
from gamr.widgets.tree_data import TreeNode, sort_leaves


def _node(name: str, **kwargs) -> TreeNode:
    """Helper to create a leaf TreeNode with a FileEntry."""
    entry = FileEntry(path=Path(f"/root/{name}"), **kwargs)
    return TreeNode(path=entry.path, entry=entry, depth=1)


class TestSortByName:
    def test_alphabetical(self):
        nodes = [_node("b.py"), _node("a.py"), _node("c.py")]
        result = sort_leaves(nodes, "name", reverse=False)
        assert [n.path.name for n in result] == ["a.py", "b.py", "c.py"]

    def test_reverse(self):
        nodes = [_node("a.py"), _node("b.py")]
        result = sort_leaves(nodes, "name", reverse=True)
        assert [n.path.name for n in result] == ["b.py", "a.py"]

    def test_case_insensitive(self):
        nodes = [_node("Beta.py"), _node("alpha.py")]
        result = sort_leaves(nodes, "name", reverse=False)
        assert [n.path.name for n in result] == ["alpha.py", "Beta.py"]


class TestSortBySize:
    def test_ascending(self):
        nodes = [_node("big.py", size=1000), _node("small.py", size=10)]
        result = sort_leaves(nodes, "size", reverse=False)
        assert [n.entry.size for n in result] == [10, 1000]

    def test_descending(self):
        nodes = [_node("small.py", size=10), _node("big.py", size=1000)]
        result = sort_leaves(nodes, "size", reverse=True)
        assert [n.entry.size for n in result] == [1000, 10]


class TestSortByMtime:
    def test_ascending(self):
        nodes = [_node("new.py", mtime=200.0), _node("old.py", mtime=100.0)]
        result = sort_leaves(nodes, "mtime", reverse=False)
        assert [n.entry.mtime for n in result] == [100.0, 200.0]


class TestSortByStatus:
    def test_groups_by_status(self):
        nodes = [
            _node("m.py", git_status=GitStatus.MODIFIED),
            _node("a.py", git_status=GitStatus.ADDED),
            _node("clean.py"),
        ]
        result = sort_leaves(nodes, "status", reverse=False)
        statuses = [n.entry.git_status.value if n.entry.git_status else "" for n in result]
        assert statuses == ["", "A", "M"]


class TestSortByLines:
    def test_by_total_changes(self):
        nodes = [
            _node("big.py", lines_added=10, lines_removed=5),
            _node("small.py", lines_added=1, lines_removed=0),
        ]
        result = sort_leaves(nodes, "lines", reverse=False)
        assert [n.path.name for n in result] == ["small.py", "big.py"]

    def test_none_values_treated_as_zero(self):
        nodes = [_node("a.py", lines_added=5), _node("b.py")]
        result = sort_leaves(nodes, "lines", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortByAuthor:
    def test_alphabetical(self):
        nodes = [_node("b.py", last_author="Zoe"), _node("a.py", last_author="Alice")]
        result = sort_leaves(nodes, "author", reverse=False)
        assert [n.entry.last_author for n in result] == ["Alice", "Zoe"]

    def test_none_sorts_first(self):
        nodes = [_node("a.py", last_author="Bob"), _node("b.py")]
        result = sort_leaves(nodes, "author", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortByGitTime:
    def test_ascending(self):
        nodes = [_node("new.py", last_git_modified=200.0), _node("old.py", last_git_modified=100.0)]
        result = sort_leaves(nodes, "git_time", reverse=False)
        assert [n.entry.last_git_modified for n in result] == [100.0, 200.0]

    def test_none_sorts_as_zero(self):
        nodes = [_node("a.py", last_git_modified=50.0), _node("b.py")]
        result = sort_leaves(nodes, "git_time", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortUnknownColumn:
    def test_preserves_order(self):
        nodes = [_node("b.py"), _node("a.py")]
        result = sort_leaves(nodes, "unknown", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]  # stable sort, original order
