"""Tests for gutter diff marker computation."""

from gamr.services.diff_parser import compute_gutter_markers


def _make_diff(*hunks: str) -> str:
    """Build a minimal unified diff from hunk bodies."""
    return "--- a/f\n+++ b/f\n" + "\n".join(hunks)


class TestSingleLineChange:
    """A single line replaced — only ● on the changed line."""

    def test_changed_line_gets_bullet(self):
        # Testing: a single-line replacement marks the changed line.
        # Input: diff replacing "old" with "new" at line 2 of a 3-line file.
        # Expected: changed={2}, no pure_added, no has_deletion_after.
        # Asserts: a simple substitution is classified as a "changed" line only.
        diff = _make_diff("@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3")
        m = compute_gutter_markers(diff, 3)
        assert m.changed == {2}
        assert m.pure_added == set()
        assert m.has_deletion_after == set()

    def test_no_underscore_on_preceding_line(self):
        # Testing: a replacement does NOT mark the preceding line as having a deletion after.
        # Input: same single-line replacement diff as above.
        # Expected: line 1 is not in has_deletion_after.
        # Asserts: the deletion marker is not falsely placed before a changed line.
        diff = _make_diff("@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3")
        m = compute_gutter_markers(diff, 3)
        assert 1 not in m.has_deletion_after


class TestPureAddition:
    """Lines added without any corresponding removal."""

    def test_single_added_line(self):
        # Testing: a line inserted without any removal is marked as pure_added.
        # Input: diff inserting one line between two context lines.
        # Expected: pure_added={2}, no changed, no has_deletion_after.
        # Asserts: insertions without paired removals are categorized correctly.
        diff = _make_diff("@@ -1,2 +1,3 @@\n line1\n+inserted\n line2")
        m = compute_gutter_markers(diff, 3)
        assert m.changed == set()
        assert m.pure_added == {2}
        assert m.has_deletion_after == set()

    def test_multiple_added_lines(self):
        # Testing: multiple consecutive insertions are all marked as pure_added.
        # Input: diff inserting two lines between context lines.
        # Expected: pure_added={2, 3}, no changed.
        # Asserts: multi-line insertions produce one marker per added line.
        diff = _make_diff("@@ -1,2 +1,4 @@\n line1\n+new1\n+new2\n line2")
        m = compute_gutter_markers(diff, 4)
        assert m.pure_added == {2, 3}
        assert m.changed == set()


class TestPureDeletion:
    """Lines deleted without replacement — underscore on preceding line."""

    def test_deletion_after_line(self):
        # Testing: a deleted line places an underscore marker on the preceding context line.
        # Input: diff removing one line between line1 and line3 (now line2).
        # Expected: has_deletion_after={1}, no changed, no pure_added.
        # Asserts: deletions are signaled on the closest visible line above.
        # line2 was deleted between line1 and line3(now line2)
        diff = _make_diff("@@ -1,3 +1,2 @@\n line1\n-removed\n line3")
        m = compute_gutter_markers(diff, 2)
        assert m.has_deletion_after == {1}
        assert m.changed == set()
        assert m.pure_added == set()

    def test_deletion_at_end_of_file(self):
        # Testing: a deletion at file end marks the last remaining line.
        # Input: diff removing the third line at end of a 3-line file (result: 2 lines).
        # Expected: has_deletion_after={2}.
        # Asserts: trailing deletions correctly anchor to the file's last line.
        diff = _make_diff("@@ -1,3 +1,2 @@\n line1\n line2\n-removed")
        m = compute_gutter_markers(diff, 2)
        assert m.has_deletion_after == {2}

    def test_multiple_lines_deleted(self):
        # Testing: multiple consecutive deletions produce a single underscore marker.
        # Input: diff removing two lines between line1 and line4.
        # Expected: has_deletion_after={1} (one marker for the block).
        # Asserts: a block of deletions consolidates into one preceding-line marker.
        # Two lines removed between line1 and line2
        diff = _make_diff("@@ -1,4 +1,2 @@\n line1\n-del1\n-del2\n line4")
        m = compute_gutter_markers(diff, 2)
        assert m.has_deletion_after == {1}


class TestMixedChanges:
    """Combined adds, changes, and deletions."""

    def test_change_and_pure_add(self):
        # Testing: a replacement followed by an extra addition.
        # Input: diff replacing "old" with "new" and adding "extra" at line 3.
        # Expected: changed={2}, pure_added={3}, no has_deletion_after.
        # Asserts: mixed replacement+insertion splits into correct marker types.
        diff = _make_diff("@@ -1,3 +1,4 @@\n line1\n-old\n+new\n+extra\n line3")
        m = compute_gutter_markers(diff, 4)
        assert m.changed == {2}
        assert m.pure_added == {3}
        assert m.has_deletion_after == set()

    def test_change_and_pure_deletion_separate_hunks(self):
        # Testing: a replacement in one hunk and a deletion in another.
        # Input: two hunks — first replaces at line 2, second deletes after line 5.
        # Expected: changed={2}, has_deletion_after={5}, pure_added empty.
        # Asserts: markers from independent hunks are computed independently.
        diff = _make_diff(
            "@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3",
            "@@ -5,3 +5,2 @@\n line5\n-removed\n line7",
        )
        m = compute_gutter_markers(diff, 6)
        assert m.changed == {2}
        assert m.has_deletion_after == {5}
        assert m.pure_added == set()

    def test_multi_line_replacement(self):
        # Testing: a block of 2 removed lines replaced by 2 new lines.
        # Input: diff replacing old1+old2 with new1+new2.
        # Expected: changed={2} (first paired line), pure_added={3} (excess addition).
        # Asserts: block-based pairing marks first as changed, rest as added.
        # Two lines replaced by two lines — block-based: first is "changed", second is "added"
        diff = _make_diff("@@ -1,4 +1,4 @@\n ctx\n-old1\n-old2\n+new1\n+new2\n ctx")
        m = compute_gutter_markers(diff, 4)
        assert m.changed == {2}
        assert m.pure_added == {3}
        assert m.has_deletion_after == set()


class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_diff(self):
        # Testing: compute_gutter_markers with an empty string diff.
        # Input: empty diff text, 10 total lines.
        # Expected: all marker sets empty.
        # Asserts: no markers are generated when there's no diff data.
        m = compute_gutter_markers("", 10)
        assert m.changed == set()
        assert m.pure_added == set()
        assert m.has_deletion_after == set()

    def test_no_hunks(self):
        # Testing: diff header present but no hunk content.
        # Input: diff with only --- and +++ lines, no @@ hunks.
        # Expected: all marker sets empty.
        # Asserts: a diff without hunks doesn't produce spurious markers.
        diff = "--- a/f\n+++ b/f\n"
        m = compute_gutter_markers(diff, 5)
        assert m.changed == set()
        assert m.pure_added == set()
        assert m.has_deletion_after == set()

    def test_deletion_at_start_of_file(self):
        # Testing: deletions before line 1 (no preceding line to anchor to).
        # Input: diff removing 2 lines before "kept", resulting file has 1 line.
        # Expected: has_deletion_after is empty (no valid anchor line at position 0).
        # Asserts: no crash or invalid marker when deletion precedes all content.
        # Lines deleted before line 1
        diff = _make_diff("@@ -1,3 +1,1 @@\n-removed1\n-removed2\n kept")
        m = compute_gutter_markers(diff, 1)
        # removed_context[1] exists but line 0 doesn't exist — no underscore
        assert m.has_deletion_after == set()

    def test_entire_file_is_new(self):
        # Testing: an entirely new file (all lines added from scratch).
        # Input: diff adding 3 lines from a zero-line base.
        # Expected: pure_added={1, 2, 3}, no changed, no has_deletion_after.
        # Asserts: new files have every line marked as a pure addition.
        diff = _make_diff("@@ -0,0 +1,3 @@\n+line1\n+line2\n+line3")
        m = compute_gutter_markers(diff, 3)
        assert m.pure_added == {1, 2, 3}
        assert m.changed == set()
        assert m.has_deletion_after == set()

    def test_zero_total_lines(self):
        # Testing: a file reduced to 0 lines (entirely deleted).
        # Input: diff removing all lines, total_lines=0.
        # Expected: all marker sets empty.
        # Asserts: no crash when the result file is empty.
        diff = _make_diff("@@ -1,2 +0,0 @@\n-line1\n-line2")
        m = compute_gutter_markers(diff, 0)
        assert m.changed == set()
        assert m.pure_added == set()
        assert m.has_deletion_after == set()

    def test_trailing_removed_marks_last_line(self):
        # Testing: deletions after the last remaining content line.
        # Input: 3-line file with 2 trailing lines deleted after line 3.
        # Expected: has_deletion_after={3}.
        # Asserts: trailing deletions anchor to the file's final line.
        # File has 3 lines, but trailing lines were deleted after them
        diff = _make_diff("@@ -1,5 +1,3 @@\n line1\n line2\n line3\n-del1\n-del2")
        m = compute_gutter_markers(diff, 3)
        assert m.has_deletion_after == {3}
