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
        # Testing: _render_lines with no changes (all lines clean).
        # Input: 10 lines, 10 rows, empty green/red/orange sets.
        # Expected: all rows are dim spaces (no colored markers).
        # Asserts: unchanged files produce only dim placeholder characters.
        result = self.overview._render_lines(10, 10, set(), set(), set())
        for row in range(10):
            assert " " in result.plain.splitlines()[row]
            assert "dim" in _style_at(result, row)

    def test_added_line_is_green(self):
        # Testing: an added line renders with green styling in the overview.
        # Input: 5 lines, green={3} (line 3 added).
        # Expected: row 2 (0-indexed) has green style and ▐ character.
        # Asserts: added lines are visually distinct with green color.
        result = self.overview._render_lines(5, 5, green={3}, red=set(), orange=set())
        assert "green" in _style_at(result, 2)  # line 3 → row 2
        assert "▐" in result.plain.splitlines()[2]

    def test_removed_line_is_red(self):
        # Testing: a removed line renders with red styling.
        # Input: 5 lines, red={2} (deletion marker at line 2).
        # Expected: row 1 has red style.
        # Asserts: deletion markers are visually distinct with red color.
        result = self.overview._render_lines(5, 5, green=set(), red={2}, orange=set())
        assert "red" in _style_at(result, 1)

    def test_both_added_and_removed_is_orange(self):
        # Testing: a line that is both added and removed renders as orange.
        # Input: 5 lines, green={1} and red={1} (same line).
        # Expected: row 0 has orange (#ff8c00) style.
        # Asserts: overlapping add+remove at same line shows as a modification (orange).
        result = self.overview._render_lines(5, 5, green={1}, red={1}, orange=set())
        assert "ff8c00" in _style_at(result, 0)

    def test_lines_compress_to_fewer_rows(self):
        # Testing: lines are compressed when file has more lines than available rows.
        # Input: 10 lines compressed into 5 rows, green at line 2.
        # Expected: line 2 maps to row 0 (lines 1-2 share row 0), which is green.
        # Asserts: the compression mapping correctly assigns changes to their display row.
        # 10 lines into 5 rows → 2 lines per row
        result = self.overview._render_lines(10, 5, green={2}, red=set(), orange=set())
        # Line 2 maps to row 0 (lines 1-2)
        assert "green" in _style_at(result, 0)

    def test_no_changes_all_dim(self):
        # Testing: a larger file with no changes has all dim rows.
        # Input: 20 lines, 10 rows, no changes.
        # Expected: all 10 rows have "dim" style.
        # Asserts: compressed clean files don't produce false positive markers.
        result = self.overview._render_lines(20, 10, set(), set(), set())
        for row in range(10):
            assert "dim" in _style_at(result, row)


class TestRenderLinesGutterMode:
    """_render_lines with orange (changed) markers."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_orange_changed_line(self):
        # Testing: an orange (changed) marker renders with orange style.
        # Input: 5 lines, orange={3}.
        # Expected: row 2 has #ff8c00 (orange) style.
        # Asserts: gutter mode correctly renders changed-line markers.
        result = self.overview._render_lines(5, 5, green=set(), red=set(), orange={3})
        assert "ff8c00" in _style_at(result, 2)

    def test_green_added_line(self):
        # Testing: a green (added) marker in gutter mode.
        # Input: 5 lines, green={4}.
        # Expected: row 3 has green style.
        # Asserts: pure additions show green in gutter overview.
        result = self.overview._render_lines(5, 5, green={4}, red=set(), orange=set())
        assert "green" in _style_at(result, 3)

    def test_red_deletion_marker(self):
        # Testing: a red (deletion) marker in gutter mode.
        # Input: 5 lines, red={2}.
        # Expected: row 1 has red style.
        # Asserts: deletion markers show red in gutter overview.
        result = self.overview._render_lines(5, 5, green=set(), red={2}, orange=set())
        assert "red" in _style_at(result, 1)

    def test_orange_takes_priority_over_green_and_red(self):
        # Testing: orange takes priority when all three colors apply to the same line.
        # Input: 5 lines, green={1}, red={1}, orange={1}.
        # Expected: row 0 has orange style (orange wins).
        # Asserts: priority ordering is orange > green > red for the same position.
        result = self.overview._render_lines(5, 5, green={1}, red={1}, orange={1})
        assert "ff8c00" in _style_at(result, 0)

    def test_mixed_in_same_row_when_compressed(self):
        # Testing: green and red in the same compressed row produce orange.
        # Input: 10 lines in 5 rows, green at line 1 and red at line 2 → same row.
        # Expected: row 0 has orange style (mixed changes merge to orange).
        # Asserts: compression correctly blends multiple change types per row.
        # 10 lines into 5 rows, green at line 1 and red at line 2 → same row → orange
        result = self.overview._render_lines(10, 5, green={1}, red={2}, orange=set())
        assert "ff8c00" in _style_at(result, 0)


class TestRenderBrailleFullDiff:
    """_render_braille in full-diff mode."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_all_clean_is_blank_braille(self):
        # Testing: _render_braille with no changes produces empty braille chars.
        # Input: 20 lines, 5 rows, empty change sets.
        # Expected: all rows are dim with base braille character (⠀).
        # Asserts: unchanged files render as empty braille dots.
        result = self.overview._render_braille(20, 5, set(), set(), set())
        # All should be base braille char (empty dots = ⠀)
        for row in range(5):
            assert "dim" in _style_at(result, row)

    def test_added_line_lights_dot(self):
        # Testing: an added line lights a braille dot in the correct row.
        # Input: 20 lines, 5 rows, green={1}.
        # Expected: row 0 has a non-empty braille char with green style.
        # Asserts: braille dots are lit for changed lines.
        result = self.overview._render_braille(20, 5, green={1}, red=set(), orange=set())
        # Line 1 → row 0, dot 0 → should not be empty braille
        char = result.plain.splitlines()[0]
        assert char != "⠀"
        assert "green" in _style_at(result, 0)

    def test_removed_line_is_red(self):
        # Testing: a removed line shows red in braille mode.
        # Input: 20 lines, 5 rows, red={5}.
        # Expected: row 1 (lines 5-8 map to row 1) has red style.
        # Asserts: deletion markers are correctly colored in braille rendering.
        result = self.overview._render_braille(20, 5, green=set(), red={5}, orange=set())
        # Line 5 → row 1 (lines 5-8 map to row 1 with 4 lines/row for 20 lines / 5 rows)
        assert "red" in _style_at(result, 1)

    def test_both_green_and_red_same_row_is_orange(self):
        # Testing: green and red in the same braille row blend to orange.
        # Input: 4 lines in 1 row, green={1}, red={2}.
        # Expected: row 0 has orange (#ff8c00) style.
        # Asserts: mixed changes in one braille cell merge to orange color.
        result = self.overview._render_braille(4, 1, green={1}, red={2}, orange=set())
        assert "ff8c00" in _style_at(result, 0)


class TestRenderBrailleGutterMode:
    """_render_braille with orange markers."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_orange_changed(self):
        # Testing: orange marker in braille gutter mode.
        # Input: 4 lines in 1 row, orange={2}.
        # Expected: row 0 has orange (#ff8c00) style.
        # Asserts: changed-line markers render correctly in braille.
        result = self.overview._render_braille(4, 1, green=set(), red=set(), orange={2})
        assert "ff8c00" in _style_at(result, 0)

    def test_green_only(self):
        # Testing: green-only braille marker.
        # Input: 4 lines in 1 row, green={3}.
        # Expected: row 0 has green style.
        # Asserts: pure additions show green in braille mode.
        result = self.overview._render_braille(4, 1, green={3}, red=set(), orange=set())
        assert "green" in _style_at(result, 0)

    def test_red_only(self):
        # Testing: red-only braille marker.
        # Input: 4 lines in 1 row, red={1}.
        # Expected: row 0 has red style.
        # Asserts: pure deletions show red in braille mode.
        result = self.overview._render_braille(4, 1, green=set(), red={1}, orange=set())
        assert "red" in _style_at(result, 0)

    def test_no_changes_empty_dots(self):
        # Testing: no changes produce empty braille character with dim style.
        # Input: 4 lines in 1 row, no changes.
        # Expected: row 0 is "⠀" (empty braille) with dim style.
        # Asserts: clean braille cells are visually distinguishable from active ones.
        result = self.overview._render_braille(4, 1, green=set(), red=set(), orange=set())
        assert result.plain.splitlines()[0] == "⠀"
        assert "dim" in _style_at(result, 0)

    def test_single_change_near_end_of_large_file(self):
        # Testing: a change near file end is visible in braille overview.
        # Input: 700 lines, 20 rows, orange at line 690.
        # Expected: at least one row has orange (#ff8c00) style.
        # Asserts: braille doesn't miss changes near the end due to sampling/rounding.
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


class TestBraille1to1WhenContentFits:
    """Braille scales file to fill available height (4 slots per row)."""

    def setup_method(self):
        self.overview = DiffOverview()

    def test_change_at_line_10_appears_in_correct_region(self):
        # Testing: 1:1 mapping when lines fit in available height.
        # Input: 15 lines in 40 rows, green at line 10.
        # Expected: row 9 has green style (line 10 → row 9 in 1:1 mode).
        # Asserts: small files get direct line-to-row mapping.
        """With 15 lines in 40 rows, line 10 → row 9 (1:1 since 15 <= 40)."""
        result = self.overview._render_braille(15, 40, green={10}, red=set(), orange=set())
        assert "green" in _style_at(result, 9)

    def test_change_at_last_line_near_bottom(self):
        # Testing: change at the last line appears near the bottom of the overview.
        # Input: 20 lines in 30 rows, red at line 20.
        # Expected: row 19 has red style, row 0 is dim.
        # Asserts: last-line changes map to the correct bottom row.
        """With 20 lines in 30 rows, line 20 → row 19 (1:1 since 20 <= 30)."""
        result = self.overview._render_braille(20, 30, green=set(), red={20}, orange=set())
        assert "red" in _style_at(result, 19)
        assert "dim" in _style_at(result, 0)

    def test_fills_available_height(self):
        # Testing: braille overview fills all available rows for files longer than height.
        # Input: 178 lines in 80 rows, green at line 178.
        # Expected: output has exactly 80 non-empty lines.
        # Asserts: the overview always uses the full available vertical space.
        """Braille overview should fill all available rows for files longer than height."""
        result = self.overview._render_braille(178, 80, green={178}, red=set(), orange=set())
        lines = result.plain.split("\n")
        assert len([line for line in lines if line]) == 80
