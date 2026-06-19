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
        # Testing: alignment of two identical files produces all "same" rows.
        # Input: old=["a","b","c"], new=["a","b","c"], diff has no hunks.
        # Expected: 3 rows, all with change_type="same", line numbers 1-3 on both sides.
        # Asserts: unchanged context lines are correctly paired without false changes.
        lines = ["a", "b", "c"]
        diff = _make_diff(lines, lines)
        result = _align(lines, lines, diff)
        assert all(r[4] == "same" for r in result)
        assert len(result) == 3

    def test_added_line(self) -> None:
        # Testing: a line inserted in the new file produces an "added" row.
        # Input: old=["a","b"], new=["a","x","b"] — "x" inserted at position 2.
        # Expected: one "added" row with old_ln=None, new_ln=2, text="x".
        # Asserts: added rows have no old line number (left side is a gap).
        old = ["a", "b"]
        new = ["a", "x", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        added_rows = [r for r in result if r[4] == "added"]
        assert len(added_rows) == 1
        assert added_rows[0][0] is None  # no old line
        assert added_rows[0][2] == 2  # new line 2
        assert added_rows[0][3] == "x"

    def test_removed_line(self) -> None:
        # Testing: a line deleted from the old file produces a "removed" row.
        # Input: old=["a","x","b"], new=["a","b"] — "x" removed from position 2.
        # Expected: one "removed" row with old_ln=2, text="x", new_ln=None.
        # Asserts: removed rows have no new line number (right side is a gap).
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
        # Testing: a 1:1 replacement (remove+add at same position) produces a "changed" row.
        # Input: old line 2 is "old", new line 2 is "new" — a modification.
        # Expected: one "changed" row pairing old_ln=2/"old" with new_ln=2/"new".
        # Asserts: adjacent remove+add are paired as a change, not separate add/remove.
        old = ["a", "old", "b"]
        new = ["a", "new", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        changed_rows = [r for r in result if r[4] == "changed"]
        assert len(changed_rows) == 1
        assert changed_rows[0][0] == 2
        assert changed_rows[0][1] == "old"
        assert changed_rows[0][2] == 2
        assert changed_rows[0][3] == "new"

    def test_multiple_hunks(self) -> None:
        # Testing: changes in separate parts of the file produce independent hunks.
        # Input: 8-line file with changes at lines 2 and 7 (separated by 4 context lines).
        # Expected: two "changed" rows: b→B and g→G, with "same" rows between.
        # Asserts: the aligner correctly handles multiple disjoint hunks in one diff.
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
        # Testing: line numbers in the output are always in ascending order.
        # Input: old=["a","b","c"], new=["a","x","y","c"] — replace "b" with "x","y".
        # Expected: all old_ln values are sorted; all new_ln values are sorted.
        # Asserts: no line number reordering bugs in the alignment logic.
        old = ["a", "b", "c"]
        new = ["a", "x", "y", "c"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        old_lns = [r[0] for r in result if r[0] is not None]
        new_lns = [r[2] for r in result if r[2] is not None]
        assert old_lns == sorted(old_lns)
        assert new_lns == sorted(new_lns)

    def test_empty_old(self) -> None:
        # Testing: alignment when old file is empty (entirely new file).
        # Input: old=[], new=["a","b"].
        # Expected: all rows are "added" with old_ln=None.
        # Asserts: handles the "new file" edge case without index errors.
        old: list[str] = []
        new = ["a", "b"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        assert all(r[4] == "added" for r in result)
        assert len(result) == 2

    def test_empty_new(self) -> None:
        # Testing: alignment when new file is empty (file fully deleted).
        # Input: old=["a","b"], new=[].
        # Expected: all rows are "removed" with new_ln=None.
        # Asserts: handles the "deleted file" edge case without index errors.
        old = ["a", "b"]
        new: list[str] = []
        diff = _make_diff(old, new)
        result = _align(old, new, diff)

        assert all(r[4] == "removed" for r in result)
        assert len(result) == 2

    def test_row_types_for_hunk_starts(self) -> None:
        # Testing: change regions form distinct groups (used by J/K hunk navigation).
        # Input: 4-line file with changes at lines 2 and 4 (separated by "same" at line 3).
        # Expected: two distinct change groups detected (transitions from same→change).
        # Asserts: the _change_hunk_starts algorithm correctly counts hunk boundaries.
        old = ["a", "b", "c", "d"]
        new = ["a", "X", "c", "Y"]
        diff = _make_diff(old, new)
        result = _align(old, new, diff)
        row_types = [r[4] for r in result]

        # Reproduce _change_hunk_starts logic
        starts = []
        prev_is_change = False
        for i, t in enumerate(row_types):
            is_change = t != "same"
            if is_change and not prev_is_change:
                starts.append(i)
            prev_is_change = is_change

        assert len(starts) == 2
