"""Tests for diff parser."""

from gamr.services.diff_parser import parse_diff_hunks


class TestParseDiffHunks:
    """Test the unified diff parser."""

    def test_empty_diff(self):
        data = parse_diff_hunks("")
        assert data.added_lines == set()
        assert data.removed_context == {}
        assert data.trailing_removed == []

    def test_none_diff(self):
        data = parse_diff_hunks(None)
        assert data.added_lines == set()
        assert data.removed_context == {}
        assert data.trailing_removed == []

    def test_single_added_line(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,2 +1,3 @@\n ctx\n+new\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == {2}
        assert data.removed_context == {}

    def test_single_removed_line(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,2 @@\n ctx\n-old\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == set()
        assert 2 in data.removed_context
        assert data.removed_context[2] == ["old"]

    def test_changed_line(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,3 @@\n ctx\n-old\n+new\n ctx"
        data = parse_diff_hunks(diff)
        assert data.added_lines == {2}
        assert data.changed_lines == {2}
        assert data.removed_context == {2: ["old"]}

    def test_trailing_removed(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,2 @@\n ctx1\n ctx2\n-deleted_at_end"
        data = parse_diff_hunks(diff)
        assert data.trailing_removed == ["deleted_at_end"]

    def test_multiple_hunks(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,2 +1,2 @@\n-a\n+b\n@@ -5,2 +5,3 @@\n ctx\n+added\n ctx"
        data = parse_diff_hunks(diff)
        assert 1 in data.added_lines
        assert 6 in data.added_lines

    def test_multi_line_replacement_pairing(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,4 +1,4 @@\n ctx\n-old1\n-old2\n+new1\n+new2\n ctx"
        data = parse_diff_hunks(diff)
        assert data.changed_lines == {2, 3}
        assert data.added_lines == {2, 3}

    def test_more_removed_than_added(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,5 +1,3 @@\n ctx\n-old1\n-old2\n-old3\n+new1\n ctx"
        data = parse_diff_hunks(diff)
        assert data.changed_lines == {2}
        assert 2 not in (data.added_lines - data.changed_lines)
        # Remaining 2 removed lines attach as context to line 2
        assert len(data.removed_context[2]) >= 1

    def test_more_added_than_removed(self):
        diff = "--- a/f\n+++ b/f\n@@ -1,3 +1,5 @@\n ctx\n-old1\n+new1\n+new2\n+new3\n ctx"
        data = parse_diff_hunks(diff)
        assert data.changed_lines == {2}
        assert 3 in data.added_lines and 3 not in data.changed_lines  # pure add
        assert 4 in data.added_lines and 4 not in data.changed_lines  # pure add
