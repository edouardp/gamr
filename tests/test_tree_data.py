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
        # Testing: sort_leaves by "name" in ascending order.
        # Input: nodes [b.py, a.py, c.py] unsorted.
        # Expected: sorted as [a.py, b.py, c.py].
        # Asserts: alphabetical name sorting works correctly.
        nodes = [_node("b.py"), _node("a.py"), _node("c.py")]
        result = sort_leaves(nodes, "name", reverse=False)
        assert [n.path.name for n in result] == ["a.py", "b.py", "c.py"]

    def test_reverse(self):
        # Testing: sort_leaves by "name" in descending (reverse) order.
        # Input: nodes [a.py, b.py].
        # Expected: sorted as [b.py, a.py].
        # Asserts: the reverse flag correctly inverts sort order.
        nodes = [_node("a.py"), _node("b.py")]
        result = sort_leaves(nodes, "name", reverse=True)
        assert [n.path.name for n in result] == ["b.py", "a.py"]

    def test_case_insensitive(self):
        # Testing: name sort is case-insensitive.
        # Input: nodes [Beta.py, alpha.py] (uppercase B vs lowercase a).
        # Expected: [alpha.py, Beta.py] (alpha before Beta regardless of case).
        # Asserts: sorting uses lowercased comparison to avoid ASCII-order surprises.
        nodes = [_node("Beta.py"), _node("alpha.py")]
        result = sort_leaves(nodes, "name", reverse=False)
        assert [n.path.name for n in result] == ["alpha.py", "Beta.py"]


class TestSortBySize:
    def test_ascending(self):
        # Testing: sort_leaves by "size" ascending.
        # Input: nodes with sizes [1000, 10].
        # Expected: sorted as [10, 1000].
        # Asserts: smaller files appear first in ascending size sort.
        nodes = [_node("big.py", size=1000), _node("small.py", size=10)]
        result = sort_leaves(nodes, "size", reverse=False)
        assert [n.entry.size for n in result] == [10, 1000]

    def test_descending(self):
        # Testing: sort_leaves by "size" descending.
        # Input: nodes with sizes [10, 1000].
        # Expected: sorted as [1000, 10].
        # Asserts: larger files appear first in descending size sort.
        nodes = [_node("small.py", size=10), _node("big.py", size=1000)]
        result = sort_leaves(nodes, "size", reverse=True)
        assert [n.entry.size for n in result] == [1000, 10]


class TestSortByMtime:
    def test_ascending(self):
        # Testing: sort_leaves by "mtime" ascending.
        # Input: nodes with mtime [200.0, 100.0].
        # Expected: sorted as [100.0, 200.0] (oldest first).
        # Asserts: modification time sorting orders by timestamp value.
        nodes = [_node("new.py", mtime=200.0), _node("old.py", mtime=100.0)]
        result = sort_leaves(nodes, "mtime", reverse=False)
        assert [n.entry.mtime for n in result] == [100.0, 200.0]


class TestSortByStatus:
    def test_groups_by_status(self):
        # Testing: sort_leaves by "status" groups files by their git status value.
        # Input: nodes with MODIFIED, ADDED, and None statuses.
        # Expected: sorted as ["", "A", "M"] (None first, then alphabetical by status value).
        # Asserts: status sorting uses the enum value string for ordering.
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
        # Testing: sort_leaves by "lines" uses sum of lines_added + lines_removed.
        # Input: big.py (10+5=15 changes) and small.py (1+0=1 change).
        # Expected: sorted as [small.py, big.py] (fewest changes first).
        # Asserts: the sort key is total churn, not just additions.
        nodes = [
            _node("big.py", lines_added=10, lines_removed=5),
            _node("small.py", lines_added=1, lines_removed=0),
        ]
        result = sort_leaves(nodes, "lines", reverse=False)
        assert [n.path.name for n in result] == ["small.py", "big.py"]

    def test_none_values_treated_as_zero(self):
        # Testing: None lines_added/lines_removed treated as 0 in sort key.
        # Input: a.py with 5 added, b.py with None (no diff stats).
        # Expected: b.py (0 changes) sorts before a.py (5 changes).
        # Asserts: missing diff stats don't crash the sort and default to zero.
        nodes = [_node("a.py", lines_added=5), _node("b.py")]
        result = sort_leaves(nodes, "lines", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortByAuthor:
    def test_alphabetical(self):
        # Testing: sort_leaves by "author" sorts alphabetically by author name.
        # Input: nodes with authors "Zoe" and "Alice".
        # Expected: sorted as ["Alice", "Zoe"].
        # Asserts: author name sort is alphabetical ascending.
        nodes = [_node("b.py", last_author="Zoe"), _node("a.py", last_author="Alice")]
        result = sort_leaves(nodes, "author", reverse=False)
        assert [n.entry.last_author for n in result] == ["Alice", "Zoe"]

    def test_none_sorts_first(self):
        # Testing: None author sorts before any actual author name.
        # Input: a.py with author "Bob", b.py with no author.
        # Expected: b.py (None) before a.py ("Bob").
        # Asserts: files without blame data appear at the top, not at the end.
        nodes = [_node("a.py", last_author="Bob"), _node("b.py")]
        result = sort_leaves(nodes, "author", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortByGitTime:
    def test_ascending(self):
        # Testing: sort_leaves by "git_time" ascending.
        # Input: nodes with last_git_modified [200.0, 100.0].
        # Expected: sorted as [100.0, 200.0] (oldest first).
        # Asserts: git timestamp sorting orders correctly by value.
        nodes = [_node("new.py", last_git_modified=200.0), _node("old.py", last_git_modified=100.0)]
        result = sort_leaves(nodes, "git_time", reverse=False)
        assert [n.entry.last_git_modified for n in result] == [100.0, 200.0]

    def test_none_sorts_as_zero(self):
        # Testing: None last_git_modified is treated as 0 (sorts first).
        # Input: a.py with git_time=50, b.py with None.
        # Expected: b.py (None→0) before a.py (50).
        # Asserts: missing blame timestamps don't crash and sort at the beginning.
        nodes = [_node("a.py", last_git_modified=50.0), _node("b.py")]
        result = sort_leaves(nodes, "git_time", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]


class TestSortUnknownColumn:
    def test_preserves_order(self):
        # Testing: sort_leaves with an unrecognized column name preserves input order.
        # Input: nodes [b.py, a.py] sorted by "unknown" column.
        # Expected: order unchanged [b.py, a.py].
        # Asserts: unknown columns fall through gracefully without reordering.
        nodes = [_node("b.py"), _node("a.py")]
        result = sort_leaves(nodes, "unknown", reverse=False)
        assert [n.path.name for n in result] == ["b.py", "a.py"]  # stable sort, original order
