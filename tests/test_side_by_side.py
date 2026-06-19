"""Tests for SideBySideDiffScreen alignment logic."""

from gamr.widgets.side_by_side import SideBySideDiffScreen

# Use the static method directly — no TUI needed
_align = SideBySideDiffScreen._align_from_diff


def _make_diff(old: list[str], new: list[str]) -> str:
    """Generate a unified diff from old/new line lists."""
    import difflib

    return "".join(
        difflib.unified_diff(
            [ln + "\n" for ln in old],
            [ln + "\n" for ln in new],
            fromfile="a/f",
            tofile="b/f",
        )
    )


class TestAlignFromDiff:
    def test_identical_files(self) -> None:
        lines = ["a", "b", "c"]
        diff = _make_diff(lines, lines)
        # No diff hunks → all same
        result = _align(lines, lines, diff)
        assert all(r[4] == "same" for r in result)
        assert len(result) == 3

    def test_added_line(self) -> None:
        old = ["a", "b"]
        new = ["a", "x", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        types = [r[4] for r in result]
        assert "added" in types
        # The added row should have new_ln set and old_ln None
        added_rows = [r for r in result if r[4] == "added"]
        assert len(added_rows) == 1
        assert added_rows[0][0] is None  # no old line
        assert added_rows[0][2] == 2  # new line 2
        assert added_rows[0][3] == "x"

    def test_removed_line(self) -> None:
        old = ["a", "x", "b"]
        new = ["a", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        removed_rows = [r for r in result if r[4] == "removed"]
        assert len(removed_rows) == 1
        assert removed_rows[0][0] == 2  # old line 2
        assert removed_rows[0][1] == "x"
        assert removed_rows[0][2] is None  # no new line

    def test_changed_line(self) -> None:
        old = ["a", "old", "b"]
        new = ["a", "new", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        changed_rows = [r for r in result if r[4] == "changed"]
        assert len(changed_rows) == 1
        assert changed_rows[0][0] == 2  # old line 2
        assert changed_rows[0][1] == "old"
        assert changed_rows[0][2] == 2  # new line 2
        assert changed_rows[0][3] == "new"

    def test_multiple_hunks(self) -> None:
        old = ["a", "b", "c", "d", "e", "f", "g", "h"]
        new = ["a", "B", "c", "d", "e", "f", "G", "h"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        changed_rows = [r for r in result if r[4] == "changed"]
        assert len(changed_rows) == 2
        assert changed_rows[0][1] == "b"
        assert changed_rows[0][3] == "B"
        assert changed_rows[1][1] == "g"
        assert changed_rows[1][3] == "G"

    def test_line_numbers_monotonic(self) -> None:
        old = ["a", "b", "c"]
        new = ["a", "x", "y", "c"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        old_lns = [r[0] for r in result if r[0] is not None]
        new_lns = [r[2] for r in result if r[2] is not None]
        assert old_lns == sorted(old_lns)
        assert new_lns == sorted(new_lns)

    def test_empty_old(self) -> None:
        old: list[str] = []
        new = ["a", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        assert all(r[4] == "added" for r in result)
        assert len(result) == 2

    def test_empty_new(self) -> None:
        old = ["a", "b"]
        new: list[str] = []
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        assert all(r[4] == "removed" for r in result)
        assert len(result) == 2

    def test_row_types_for_hunk_starts(self) -> None:
        """_change_hunk_starts logic (tested via row_types output)."""
        old = ["a", "b", "c", "d"]
        new = ["a", "X", "c", "Y"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)
        row_types = [r[4] for r in result]

        # Find hunk start indices (same logic as _change_hunk_starts)
        starts = []
        prev_is_change = False
        for i, t in enumerate(row_types):
            is_change = t != "same"
            if is_change and not prev_is_change:
                starts.append(i)
            prev_is_change = is_change

        assert len(starts) == 2  # Two separate changed regions
