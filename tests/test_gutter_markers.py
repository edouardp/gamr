"""Tests for gutter diff marker computation."""

from gamr.services.diff_parser import compute_gutter_markers


def _make_diff(*hunks: str) -> str:
    """Build a minimal unified diff from hunk bodies."""
    return "--- a/f\n+++ b/f\n" + "\n".join(hunks)


class TestSingleLineChange:
    """A single line replaced — only ● on the changed line."""

    def test_changed_line_gets_bullet(self):
        diff = _make_diff("@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3")
        changed, added, deleted = compute_gutter_markers(diff, 3)
        assert changed == {2}
        assert added == set()
        assert deleted == set()

    def test_no_underscore_on_preceding_line(self):
        diff = _make_diff("@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3")
        _, _, deleted = compute_gutter_markers(diff, 3)
        assert 1 not in deleted


class TestPureAddition:
    """Lines added without any corresponding removal."""

    def test_single_added_line(self):
        diff = _make_diff("@@ -1,2 +1,3 @@\n line1\n+inserted\n line2")
        changed, added, deleted = compute_gutter_markers(diff, 3)
        assert changed == set()
        assert added == {2}
        assert deleted == set()

    def test_multiple_added_lines(self):
        diff = _make_diff("@@ -1,2 +1,4 @@\n line1\n+new1\n+new2\n line2")
        changed, added, deleted = compute_gutter_markers(diff, 4)
        assert added == {2, 3}
        assert changed == set()


class TestPureDeletion:
    """Lines deleted without replacement — underscore on preceding line."""

    def test_deletion_after_line(self):
        # line2 was deleted between line1 and line3(now line2)
        diff = _make_diff("@@ -1,3 +1,2 @@\n line1\n-removed\n line3")
        changed, added, deleted = compute_gutter_markers(diff, 2)
        assert deleted == {1}
        assert changed == set()
        assert added == set()

    def test_deletion_at_end_of_file(self):
        diff = _make_diff("@@ -1,3 +1,2 @@\n line1\n line2\n-removed")
        changed, added, deleted = compute_gutter_markers(diff, 2)
        assert deleted == {2}

    def test_multiple_lines_deleted(self):
        # Two lines removed between line1 and line2
        diff = _make_diff("@@ -1,4 +1,2 @@\n line1\n-del1\n-del2\n line4")
        changed, added, deleted = compute_gutter_markers(diff, 2)
        assert deleted == {1}


class TestMixedChanges:
    """Combined adds, changes, and deletions."""

    def test_change_and_pure_add(self):
        diff = _make_diff("@@ -1,3 +1,4 @@\n line1\n-old\n+new\n+extra\n line3")
        changed, added, deleted = compute_gutter_markers(diff, 4)
        assert changed == {2}
        assert added == {3}
        assert deleted == set()

    def test_change_and_pure_deletion_separate_hunks(self):
        diff = _make_diff(
            "@@ -1,3 +1,3 @@\n line1\n-old\n+new\n line3",
            "@@ -5,3 +5,2 @@\n line5\n-removed\n line7",
        )
        changed, added, deleted = compute_gutter_markers(diff, 6)
        assert changed == {2}
        assert deleted == {5}
        assert added == set()

    def test_multi_line_replacement(self):
        # Two lines replaced by two lines — both are "changed"
        diff = _make_diff("@@ -1,4 +1,4 @@\n ctx\n-old1\n-old2\n+new1\n+new2\n ctx")
        changed, added, deleted = compute_gutter_markers(diff, 4)
        assert changed == {2, 3}
        assert added == set()
        assert deleted == set()


class TestEdgeCases:
    """Boundary conditions."""

    def test_empty_diff(self):
        changed, added, deleted = compute_gutter_markers("", 10)
        assert changed == set()
        assert added == set()
        assert deleted == set()

    def test_no_hunks(self):
        diff = "--- a/f\n+++ b/f\n"
        changed, added, deleted = compute_gutter_markers(diff, 5)
        assert changed == set()
        assert added == set()
        assert deleted == set()

    def test_deletion_at_start_of_file(self):
        # Lines deleted before line 1
        diff = _make_diff("@@ -1,3 +1,1 @@\n-removed1\n-removed2\n kept")
        changed, added, deleted = compute_gutter_markers(diff, 1)
        # removed_context[1] exists but line 0 doesn't exist — no underscore
        assert deleted == set()

    def test_entire_file_is_new(self):
        diff = _make_diff("@@ -0,0 +1,3 @@\n+line1\n+line2\n+line3")
        changed, added, deleted = compute_gutter_markers(diff, 3)
        assert added == {1, 2, 3}
        assert changed == set()
        assert deleted == set()

    def test_zero_total_lines(self):
        diff = _make_diff("@@ -1,2 +0,0 @@\n-line1\n-line2")
        changed, added, deleted = compute_gutter_markers(diff, 0)
        assert changed == set()
        assert added == set()
        assert deleted == set()

    def test_trailing_removed_marks_last_line(self):
        # File has 3 lines, but trailing lines were deleted after them
        diff = _make_diff("@@ -1,5 +1,3 @@\n line1\n line2\n line3\n-del1\n-del2")
        changed, added, deleted = compute_gutter_markers(diff, 3)
        assert deleted == {3}
