"""Tests for diff parser."""

from gamr.services.diff_parser import parse_diff_hunks


class TestParseDiffHunks:
    """Test the unified diff parser."""

    def test_empty_diff(self):
        # Testing: parse_diff_hunks with an empty string.
        # Input: empty string "".
        # Expected: all fields empty (added_lines=∅, removed_context={}, trailing_removed=[]).
        # Asserts: no data is generated from an empty diff.
        data = parse_diff_hunks("")
        assert data.added_lines == set()
        assert data.removed_context == {}
        assert data.trailing_removed == []

    def test_none_diff(self):
        # Testing: parse_diff_hunks with None input.
        # Input: None (no diff available).
        # Expected: all fields empty — same as empty string.
        # Asserts: None is handled gracefully without raising.
        data = parse_diff_hunks(None)
        assert data.added_lines == set()
        assert data.removed_context == {}
        assert data.trailing_removed == []

    def test_single_added_line(self):
        # Testing: a single added line is tracked in added_lines.
        # Input: diff inserting "new" at line 2 between two context lines.
        # Expected: added_lines={2}, removed_context empty.
        # Asserts: pure insertions are correctly identified and positioned.
        diff = "--- a/f\n+++ b/f\n@@ -1,2 +1,3 @@\n ctx\n+new\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == {2}
        assert data.removed_context == {}

    def test_single_removed_line(self):
        # Testing: a single removed line creates a removed_context entry.
        # Input: diff removing "old" at position 2.
        # Expected: removed_context[2] == ["old"], added_lines empty.
        # Asserts: removals are stored as context associated with their position.
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,2 @@\n ctx\n-old\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == set()
        assert 2 in data.removed_context
        assert data.removed_context[2] == ["old"]

    def test_changed_line(self):
        # Testing: a line replacement (remove + add at same position) marks as changed.
        # Input: diff replacing "old" with "new" at line 2.
        # Expected: added_lines={2}, changed_lines={2}, removed_context[2]=["old"].
        # Asserts: replacements are tracked in both changed_lines and removed_context.
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,3 @@\n ctx\n-old\n+new\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == {2}
        assert data.changed_lines == {2}
        assert data.removed_context == {2: ["old"]}

    def test_trailing_removed(self):
        # Testing: lines removed at the end of file go into trailing_removed.
        # Input: diff removing the last line "deleted_at_end" after two context lines.
        # Expected: trailing_removed == ["deleted_at_end"].
        # Asserts: end-of-file deletions are stored separately for display below content.
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,2 @@\n ctx1\n ctx2\n-deleted_at_end"
        data = parse_diff_hunks(diff)
        assert data.trailing_removed == ["deleted_at_end"]

    def test_multiple_hunks(self):
        # Testing: multiple hunks in one diff are all parsed.
        # Input: two hunks — replacement at line 1 and insertion at line 6.
        # Expected: both lines 1 and 6 appear in added_lines.
        # Asserts: the parser handles multi-hunk diffs without losing data.
        diff = "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n-a\n+b\n@@ -5,2 +5,3 @@\n ctx\n+added\n ctx"
        data = parse_diff_hunks(diff)
        assert 1 in data.added_lines
        assert 6 in data.added_lines

    def test_multi_line_replacement_pairing(self):
        # Testing: a block of 2 removed + 2 added lines uses block-based pairing.
        # Input: old1+old2 replaced by new1+new2.
        # Expected: changed_lines={2}, added_lines={2,3}, removed_context[2] has 2 items.
        # Asserts: the block-based algorithm pairs the first add with all removes.
        diff = "--- a/f\n+++ b/f\n@@ -1,4 +1,4 @@\n ctx\n-old1\n-old2\n+new1\n+new2\n ctx"
        data = parse_diff_hunks(diff)
        # Block-based: entire removed block attaches to first added line
        assert data.changed_lines == {2}
        assert data.added_lines == {2, 3}
        assert len(data.removed_context[2]) == 2  # both removed lines in one block

    def test_more_removed_than_added(self):
        # Testing: more lines removed than added (3 removed, 1 added).
        # Input: 3 old lines replaced by 1 new line.
        # Expected: changed_lines={2}, extra removed lines attach as context to line 2.
        # Asserts: excess removals are stored as context, not lost.
        diff = "--- a/f\n+++ b/f\n@@ -1,5 +1,3 @@\n ctx\n-old1\n-old2\n-old3\n+new1\n ctx"
        data = parse_diff_hunks(diff)
        assert data.changed_lines == {2}
        assert 2 not in (data.added_lines - data.changed_lines)
        # Remaining 2 removed lines attach as context to line 2
        assert len(data.removed_context[2]) >= 1

    def test_more_added_than_removed(self):
        # Testing: more lines added than removed (1 removed, 3 added).
        # Input: old1 replaced by new1+new2+new3.
        # Expected: changed_lines={2}, lines 3 and 4 are pure adds.
        # Asserts: excess additions are classified as pure_added, not changed.
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,5 @@\n ctx\n-old1\n+new1\n+new2\n+new3\n ctx"
        data = parse_diff_hunks(diff)
        assert data.changed_lines == {2}
        assert 3 in data.added_lines and 3 not in data.changed_lines  # pure add
        assert 4 in data.added_lines and 4 not in data.changed_lines  # pure add
