"""Tests for DiffOverview _render_lines and _render_braille."""

from rich.text import Text

from gamr.widgets.preview_pane import DiffOverview


def _style_at(result: Text, row: int) -> str:
    """Get the style string for a given row (0-indexed).

    Each row is 2 chars (character + newline), so span at offset row*2.
    """
    offset = row * 2
    for span in result._spans:
        if span.start <= offset < span.end:
            return span.style or ""
    return ""


class TestRenderLinesFullDiff:
    """_render_lines in full-diff mode (green + red, no orange)."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_all_clean_lines(self):
        result = self.overview._render_lines(10, 10, set(), set(), set())
        for row in range(10):
            assert "│" in result.plain.splitlines()[row]
            assert "dim" in _style_at(result, row)

    def test_added_line_is_green(self):
        result = self.overview._render_lines(5, 5, green={3}, red=set(), orange=set())
        assert "green" in _style_at(result, 2)  # line 3 → row 2
        assert "┃" in result.plain.splitlines()[2]

    def test_removed_line_is_red(self):
        result = self.overview._render_lines(5, 5, green=set(), red={2}, orange=set())
        assert "red" in _style_at(result, 1)

    def test_both_added_and_removed_is_orange(self):
        result = self.overview._render_lines(5, 5, green={1}, red={1}, orange=set())
        assert "ff8c00" in _style_at(result, 0)

    def test_lines_compress_to_fewer_rows(self):
        # 10 lines into 5 rows → 2 lines per row
        result = self.overview._render_lines(10, 5, green={2}, red=set(), orange=set())
        # Line 2 maps to row 0 (lines 1-2)
        assert "green" in _style_at(result, 0)

    def test_no_changes_all_dim(self):
        result = self.overview._render_lines(20, 10, set(), set(), set())
        for row in range(10):
            assert "dim" in _style_at(result, row)


class TestRenderLinesGutterMode:
    """_render_lines with orange (changed) markers."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_orange_changed_line(self):
        result = self.overview._render_lines(5, 5, green=set(), red=set(), orange={3})
        assert "ff8c00" in _style_at(result, 2)

    def test_green_added_line(self):
        result = self.overview._render_lines(5, 5, green={4}, red=set(), orange=set())
        assert "green" in _style_at(result, 3)

    def test_red_deletion_marker(self):
        result = self.overview._render_lines(5, 5, green=set(), red={2}, orange=set())
        assert "red" in _style_at(result, 1)

    def test_orange_takes_priority_over_green_and_red(self):
        result = self.overview._render_lines(5, 5, green={1}, red={1}, orange={1})
        assert "ff8c00" in _style_at(result, 0)

    def test_mixed_in_same_row_when_compressed(self):
        # 10 lines into 5 rows, green at line 1 and red at line 2 → same row → orange
        result = self.overview._render_lines(10, 5, green={1}, red={2}, orange=set())
        assert "ff8c00" in _style_at(result, 0)


class TestRenderBrailleFullDiff:
    """_render_braille in full-diff mode."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_all_clean_is_blank_braille(self):
        result = self.overview._render_braille(20, 5, set(), set(), set())
        # All should be base braille char (empty dots = ⠀)
        for row in range(5):
            assert "dim" in _style_at(result, row)

    def test_added_line_lights_dot(self):
        result = self.overview._render_braille(20, 5, green={1}, red=set(), orange=set())
        # Line 1 → row 0, dot 0 → should not be empty braille
        char = result.plain.splitlines()[0]
        assert char != "⠀"
        assert "green" in _style_at(result, 0)

    def test_removed_line_is_red(self):
        result = self.overview._render_braille(20, 5, green=set(), red={5}, orange=set())
        # Line 5 → row 1 (lines 5-8 map to row 1 with 4 lines/row for 20 lines / 5 rows)
        assert "red" in _style_at(result, 1)

    def test_both_green_and_red_same_row_is_orange(self):
        result = self.overview._render_braille(4, 1, green={1}, red={2}, orange=set())
        assert "ff8c00" in _style_at(result, 0)


class TestRenderBrailleGutterMode:
    """_render_braille with orange markers."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_orange_changed(self):
        result = self.overview._render_braille(4, 1, green=set(), red=set(), orange={2})
        assert "ff8c00" in _style_at(result, 0)

    def test_green_only(self):
        result = self.overview._render_braille(4, 1, green={3}, red=set(), orange=set())
        assert "green" in _style_at(result, 0)

    def test_red_only(self):
        result = self.overview._render_braille(4, 1, green=set(), red={1}, orange=set())
        assert "red" in _style_at(result, 0)

    def test_no_changes_empty_dots(self):
        result = self.overview._render_braille(4, 1, green=set(), red=set(), orange=set())
        assert result.plain.splitlines()[0] == "⠀"
        assert "dim" in _style_at(result, 0)

    def test_single_change_near_end_of_large_file(self):
        """Regression: braille must not miss a change due to sampling."""
        # 700 lines, 20 rows height, change at line 690
        result = self.overview._render_braille(700, 20, green=set(), red=set(), orange={690})
        # Should have at least one non-dim row
        found = False
        for row in range(20):
            if "ff8c00" in _style_at(result, row):
                found = True
                break
        assert found, "Change at line 690/700 was not visible in braille overview"
