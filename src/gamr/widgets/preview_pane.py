"""Preview pane widget — syntax-highlighted file view and diff view.

Layout: pinned PreviewHeader (filename + mode) on top, scrollable content below,
optional DiffOverview bar docked right (visible in full diff and gutter modes).

Rendering uses a shared _render_highlighted() method for both plain file and full-diff
modes, ensuring consistent line numbers and styling. A _last_rendered_path guard
prevents re-rendering the same file (which would reset scroll position via static.update).
Call invalidate() to force a re-render when content has changed on disk.

Scroll is handled atomically via restore_line parameter passed through show_*() →
_set_content(). The app (domain layer) decides what line to show; this widget never
decides scroll position on its own.
"""

from __future__ import annotations

import re
from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from gamr.config import DIFF_PAD_WIDTH
from gamr.models import DiffMode
from gamr.services.diff_parser import compute_gutter_markers, parse_diff_hunks


class PreviewHeader(Static):
    """Header bar showing filename and diff mode."""

    DEFAULT_CSS = """
    PreviewHeader {
        height: 1;
        background: $surface-lighten-1;
        color: $text;
        padding: 0 1;
    }
    """


class DiffOverview(Static):
    """Single-column overview bar showing diff changes across the file.

    Supports two styles:
    - "line": uses ┃/│ characters (one per row)
    - "braille": uses braille dots to pack 4 source lines per terminal row
    """

    DEFAULT_CSS = """
    DiffOverview {
        width: 1;
        height: 100%;
        background: $surface;
    }
    """

    use_braille: reactive[bool] = reactive(False)

    def set_diff_map(self, total_lines: int, added: set[int], removed: dict[int, list[str]]) -> None:
        """Build overview from full-diff data (added lines + removed context dict)."""
        if total_lines == 0:
            self.update("")
            return

        removed_positions: set[int] = {ln - 1 for ln in removed}
        self._total_lines = total_lines
        self._green = added
        self._red = removed_positions
        self._orange: set[int] = set()
        self._render_overview()

    def set_gutter_map(
        self, total_lines: int, changed: set[int], pure_added: set[int], has_deletion_after: set[int]
    ) -> None:
        """Build overview from gutter marker data."""
        if total_lines == 0:
            self.update("")
            return

        self._total_lines = total_lines
        self._green = pure_added
        self._red = has_deletion_after
        self._orange = changed
        self._render_overview()

    def _render_overview(self) -> None:
        total_lines = getattr(self, "_total_lines", 0)
        green = getattr(self, "_green", set())
        red = getattr(self, "_red", set())
        orange = getattr(self, "_orange", set())
        if total_lines == 0:
            self.update("")
            return

        # Use content_size.height if available, fall back to parent height
        height = self.content_size.height
        if height < 2:
            height = self.size.height
        if height < 2:
            height = 20

        if self.use_braille:
            result = self._render_braille(total_lines, height, green, red, orange)
        else:
            result = self._render_lines(total_lines, height, green, red, orange)

        self.update(result)

    def _render_lines(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using ┃/│ line characters."""
        lines_per_row = max(1, total_lines / height)
        result = Text(no_wrap=True)
        for row in range(height):
            start = int(row * lines_per_row) + 1
            end = int((row + 1) * lines_per_row) + 1
            has_orange = any(i in orange for i in range(start, end))
            has_green = any(i in green for i in range(start, end))
            has_red = any(i in red for i in range(start, end))
            if has_orange or (has_green and has_red):
                result.append("┃\n", style="#ff8c00")
            elif has_green:
                result.append("┃\n", style="green")
            elif has_red:
                result.append("┃\n", style="red")
            else:
                result.append("│\n", style="dim")
        return result

    def _render_braille(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using braille characters (4 source lines per row via 2x2 dot grid)."""
        rows_available = height
        lines_per_dot = max(1, total_lines / (rows_available * 4))
        result = Text(no_wrap=True)

        for row in range(rows_available):
            dots = 0
            for dot in range(4):
                dot_start = int((row * 4 + dot) * lines_per_dot) + 1
                dot_end = int((row * 4 + dot + 1) * lines_per_dot) + 1
                if any(i in green or i in red or i in orange for i in range(dot_start, dot_end)):
                    dots |= [0x01, 0x02, 0x04, 0x40][dot]

            char = chr(0x2800 + dots)

            # Determine color from all lines in this row's range
            row_start = int(row * 4 * lines_per_dot) + 1
            row_end = int((row + 1) * 4 * lines_per_dot) + 1
            has_orange = any(i in orange for i in range(row_start, row_end))
            has_green = any(i in green for i in range(row_start, row_end))
            has_red = any(i in red for i in range(row_start, row_end))
            if has_orange or (has_green and has_red):
                result.append(char + "\n", style="#ff8c00")
            elif has_green:
                result.append(char + "\n", style="green")
            elif has_red:
                result.append(char + "\n", style="red")
            else:
                result.append(char + "\n", style="dim")

        return result

    def watch_use_braille(self, value: bool) -> None:
        self._render_overview()

    def on_resize(self, event) -> None:
        """Re-render when the widget height changes."""
        self._render_overview()

    def clear_overview(self) -> None:
        self.update("")


class _PreviewContent(Static):
    """Static widget with native text selection disabled."""

    ALLOW_SELECT = False


class PreviewPane(Widget):
    """Displays file contents with syntax highlighting or a diff view."""

    current_path: reactive[Path | None] = reactive(None)
    show_diff = reactive(DiffMode.FULL)
    syntax_theme: reactive[str] = reactive("monokai")
    _last_rendered_path: Path | None = None

    # Diff background colors per theme mode
    _DIFF_COLORS = {
        "dark": {"added": "#002200", "removed": "#300000"},
        "light": {"added": "#ccffcc", "removed": "#ffcccc"},
    }

    @property
    def _diff_bg_added(self) -> str:
        mode = "light" if self.syntax_theme == "default" else "dark"
        return self._DIFF_COLORS[mode]["added"]

    @property
    def _diff_bg_removed(self) -> str:
        mode = "light" if self.syntax_theme == "default" else "dark"
        return self._DIFF_COLORS[mode]["removed"]

    DEFAULT_CSS = """
    PreviewPane {
        width: 100%;
        height: 100%;
        layout: vertical;
    }
    PreviewPane #preview-header {
        height: 1;
        background: $surface-lighten-1;
        color: $text;
        padding: 0 1;
    }
    PreviewPane #preview-body {
        height: 1fr;
        layout: horizontal;
    }
    PreviewPane #preview-scroll {
        width: 1fr;
        height: 100%;
        background: #272822;
        overflow-x: hidden;
    }
    PreviewPane #preview-content {
        background: #272822;
        width: auto;
    }
    PreviewPane #diff-overview {
        width: 1;
        height: 100%;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        yield PreviewHeader(id="preview-header")
        with Horizontal(id="preview-body"):
            with VerticalScroll(id="preview-scroll"):
                yield _PreviewContent(id="preview-content")
            yield DiffOverview(id="diff-overview")

    def _update_header(self) -> None:
        """Update the header with current filename and diff mode."""
        name = self.current_path.name if self.current_path else ""
        mode_labels = {
            DiffMode.UNIFIED: "diff",
            DiffMode.FULL: "full diff",
            DiffMode.GUTTER: "gutter",
        }
        mode = mode_labels.get(self.show_diff, "")
        header = self.query_one("#preview-header", PreviewHeader)
        if name:
            # Right-align the mode by padding
            header.update(f"{name}{'':>{60 - len(name) - len(mode)}}{mode}")
        else:
            header.update("")

    def show_file(self, path: Path, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Display a file with syntax highlighting (no diff markers)."""
        self.current_path = path
        content = self._read_file(path)
        if content is None:
            return
        styled, _total, _added, _removed = self._render_highlighted(path, content)
        self._update_overview_for_diff(0, set(), {})
        self._set_content(styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

    def show_full_diff(self, path: Path, diff_text: str, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Display file with syntax highlighting + diff markers."""
        self.current_path = path
        if path.exists():
            content = self._read_file(path)
            if content is None:
                return
        else:
            content = ""
        styled, total_lines, added_lines, removed_context = self._render_highlighted(path, content, diff_text=diff_text)
        self._update_overview_for_diff(total_lines, added_lines, removed_context)
        self._set_content(styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

    def show_gutter_diff(
        self, path: Path, diff_text: str, *, scroll_to_top: bool = True, restore_line: int = 0
    ) -> None:
        """Display file with syntax highlighting + a single gutter column for changes."""
        self.current_path = path
        content = self._read_file(path)
        if content is None:
            return

        total_lines = len(content.splitlines())
        changed_lines, pure_added, has_deletion_after = compute_gutter_markers(diff_text, total_lines)

        lexer = Syntax.guess_lexer(str(path), content)
        syntax = Syntax(content, lexer=lexer, line_numbers=False, word_wrap=False, theme=self.syntax_theme)
        highlighted = syntax.highlight(content)
        hi_lines = highlighted.split(allow_blank=True)

        total_lines = len(hi_lines)
        ln_width = len(str(total_lines))
        styled = Text(no_wrap=True)
        row_to_source: list[int] = []
        has_any_markers = bool(changed_lines or pure_added or has_deletion_after)

        for i, hi_line in enumerate(hi_lines, 1):
            # Line number
            styled.append(f"{str(i).rjust(ln_width)} ", style="dim")
            # Gutter column (only when there are changes)
            if has_any_markers:
                if i in changed_lines:
                    styled.append("●", style="bold #ff8c00")
                elif i in pure_added:
                    styled.append("+", style="bold green")
                elif i in has_deletion_after:
                    styled.append("_", style="bold red")
                else:
                    styled.append(" ")
            # Content
            styled.append(" ")
            styled.append_text(hi_line)
            styled.append("\n")
            row_to_source.append(i)

        self._row_to_source = row_to_source
        overview = self.query_one(DiffOverview)
        if has_any_markers:
            overview.set_gutter_map(total_lines, changed_lines, pure_added, has_deletion_after)
            overview.display = True
        else:
            overview.clear_overview()
            overview.display = False
        self._set_content(styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

    def show_diff_content(
        self, diff_text: str, *, path: Path | None = None, scroll_to_top: bool = True, restore_line: int = 0
    ) -> None:
        """Display a unified diff with coloured lines."""
        if path:
            self.current_path = path
        if not diff_text:
            self._set_content(Text("No changes", style="dim"), scroll_to_top=scroll_to_top)
            return

        styled = Text(no_wrap=True)
        row_to_source: list[int] = []
        current_line = 0
        for line in diff_text.splitlines(keepends=True):
            if line.startswith("+++") or line.startswith("---"):
                styled.append(line, style="bold")
                row_to_source.append(0)  # header — not a valid source line
            elif line.startswith("@@"):
                styled.append(line, style="cyan")
                # Parse target line from @@ -a,b +c,d @@
                m = re.search(r"\+(\d+)", line)
                current_line = int(m.group(1)) - 1 if m else 0
                row_to_source.append(0)  # hunk header — not a valid source line
            elif line.startswith("+"):
                styled.append(line, style="green")
                current_line += 1
                row_to_source.append(current_line)
            elif line.startswith("-"):
                styled.append(line, style="red")
                row_to_source.append(0)  # removed line — not in current file
            else:
                styled.append(line)
                current_line += 1
                row_to_source.append(current_line)

        self._row_to_source = row_to_source

        self._set_content(styled, scroll_to_top=scroll_to_top, restore_line=restore_line)
        # Hide overview bar in unified diff mode
        self.query_one(DiffOverview).display = False

    def clear_preview(self) -> None:
        """Clear the preview pane."""
        self.current_path = None
        self._last_rendered_path = None
        self._set_content("")

    def invalidate(self) -> None:
        """Force next _set_content to re-render even for the same file."""
        self._last_rendered_path = None

    def _read_file(self, path: Path) -> str | None:
        """Read file, handle errors and binary detection."""
        try:
            raw = path.read_bytes()
        except OSError:
            self._set_content("Cannot read file")
            return None

        # Null byte in first 8KB is a heuristic for binary files
        if b"\x00" in raw[:8192]:
            self._set_content(Text(f"Binary file: {path.name}", style="dim italic"))
            return None

        return raw.decode(errors="replace")

    def _render_highlighted(
        self, path: Path, content: str, diff_text: str | None = None
    ) -> tuple[Text, int, set[int], dict[int, list[str]]]:
        """Shared renderer: syntax-highlighted file with optional diff markers."""
        diff_data = parse_diff_hunks(diff_text)
        added_lines = diff_data.added_lines
        removed_context = diff_data.removed_context
        trailing_removed = diff_data.trailing_removed

        # Syntax highlight the content. Deleted/empty files have no source rows.
        if content:
            lexer = Syntax.guess_lexer(str(path), content)
            syntax = Syntax(content, lexer=lexer, line_numbers=False, word_wrap=False, theme=self.syntax_theme)
            highlighted = syntax.highlight(content)
            hi_lines = highlighted.split(allow_blank=True)
        else:
            hi_lines = []

        # Layout constants
        total_lines = len(hi_lines)
        ln_width = len(str(total_lines))
        # pad_width: wide enough to extend background color across the full pane width
        pad_width = DIFF_PAD_WIDTH

        styled = Text(no_wrap=True)
        # Maps display row index → source file line number (for scroll position tracking)
        row_to_source: list[int] = []

        for i, hi_line in enumerate(hi_lines, 1):
            # Show removed lines before this line
            if i in removed_context:
                for rline in removed_context[i]:
                    ln_pad = " " * ln_width
                    styled.append(f"{ln_pad} ", style="dim")
                    start = len(styled)
                    line_content = f"- {rline}"
                    styled.append(line_content.ljust(pad_width) + "\n", style=f"on {self._diff_bg_removed}")
                    row_to_source.append(i)

            # Line number
            styled.append(f"{str(i).rjust(ln_width)} ", style="dim")

            # Diff marker + content, or plain content
            if diff_text and i in added_lines:
                start = len(styled)
                styled.append("+ ", style="bold green")
                styled.append_text(hi_line)
                current_len = len(styled) - start
                if current_len < pad_width:
                    styled.append(" " * (pad_width - current_len))
                styled.stylize(f"on {self._diff_bg_added}", start, len(styled))
            else:
                styled.append("  ")
                styled.append_text(hi_line)

            styled.append("\n")
            row_to_source.append(i)

        # Trailing removed lines
        for rline in trailing_removed:
            ln_pad = " " * ln_width
            styled.append(f"{ln_pad} ", style="dim")
            line_content = f"- {rline}"
            styled.append(line_content.ljust(pad_width) + "\n", style=f"on {self._diff_bg_removed}")
            row_to_source.append(total_lines)

        self._row_to_source = row_to_source

        return styled, total_lines, added_lines, removed_context

    def _update_overview_for_diff(self, total_lines: int, added_lines: set[int], removed_context: dict) -> None:
        """Update the diff overview bar based on diff data."""
        overview = self.query_one(DiffOverview)
        if total_lines > 0 and (added_lines or removed_context):
            overview.set_diff_map(total_lines, added_lines, removed_context)
            overview.display = True
        else:
            overview.clear_overview()
            overview.display = False

    def get_source_line_at_scroll(self) -> int:
        """Get the source file line number at the current scroll position."""
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        row = scroller.scroll_offset.y
        mapping = getattr(self, "_row_to_source", [])
        if not mapping:
            return row + 1
        idx = min(row, len(mapping) - 1)
        return mapping[idx] if idx >= 0 else 1

    def scroll_to_source_line(self, source_line: int) -> None:
        """Scroll to the display row corresponding to a source line number."""
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        mapping = getattr(self, "_row_to_source", [])
        if not mapping:
            scroller.scroll_to(0, source_line - 1, animate=False)
            return
        for display_row, src in enumerate(mapping):
            if src >= source_line:
                scroller.scroll_to(0, display_row, animate=False)
                return
        scroller.scroll_to(0, len(mapping) - 1, animate=False)

    def _set_content(self, content: Text | str, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Update the preview content.

        Dedup: if scroll_to_top=True and the same file is already rendered, skip entirely
        (prevents scroll reset on redundant highlight events).
        Use invalidate() before calling with restore_line to force re-render of same file.
        """
        if scroll_to_top and restore_line == 0 and self.current_path == self._last_rendered_path:
            return
        self._rendered_content = content if isinstance(content, Text) else None
        # Precompute line start offsets for O(1) highlight lookups
        if isinstance(content, Text):
            plain = content.plain
            self._line_offsets = [0] + [i + 1 for i, c in enumerate(plain) if c == "\n"]
        else:
            self._line_offsets = None
        static = self.query_one("#preview-content", Static)
        static.update(content)
        self._update_header()
        self._last_rendered_path = self.current_path
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        if restore_line > 1:
            # Restore to a specific source line (preserving scroll across re-renders)
            mapping = getattr(self, "_row_to_source", [])
            if mapping:
                for display_row, src in enumerate(mapping):
                    if src >= restore_line:
                        scroller.scroll_to(0, display_row, animate=False)
                        return
                scroller.scroll_to(0, len(mapping) - 1, animate=False)
            else:
                scroller.scroll_to(0, restore_line - 1, animate=False)
        elif scroll_to_top:
            scroller.scroll_home(animate=False)

    # -------------------------------------------------------------------------
    # Line selection and clipboard copy
    # -------------------------------------------------------------------------

    def _format_file_ref(self, start_line: int, end_line: int | None = None) -> str:
        """Format a file:line reference string for the clipboard."""
        try:
            rel = str(self.current_path.relative_to(Path.cwd()))
        except (ValueError, TypeError):
            rel = str(self.current_path)
        if end_line and end_line != start_line:
            return f"{rel}:{start_line}-{end_line}"
        return f"{rel}:{start_line}"

    def _display_row_to_source(self, display_row: int) -> int:
        """Convert a display row index to a source file line number. Returns 0 if invalid."""
        mapping = getattr(self, "_row_to_source", [])
        if not mapping:
            return display_row + 1
        idx = min(display_row, len(mapping) - 1)
        if idx < 0:
            return 0
        return mapping[idx]

    def _get_display_row_from_click(self, y: int) -> int:
        """Get the display row from a click y-coordinate on the scroller."""
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        return scroller.scroll_offset.y + y

    def on_click(self, event: Click) -> None:
        """Double-click copies file:line to clipboard."""
        if event.chain < 2 or not self.current_path:
            return
        # y is relative to the preview-scroll widget
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        offset = event.screen_y - scroller.content_region.y
        if offset < 0:
            return
        display_row = scroller.scroll_offset.y + offset
        source_line = self._display_row_to_source(display_row)
        if source_line < 1:
            return  # Invalid line (diff header, removed line, etc.)
        ref = self._format_file_ref(source_line)
        self.app.copy_to_clipboard(ref)
        self.app.notify(f"File ref copied: {ref}", timeout=2)
        # Flash highlight on the clicked line
        self._drag_start_row = display_row
        self._drag_current_row = display_row
        self._update_selection_highlight()
        self._drag_start_row = None
        self._drag_current_row = None
        self.set_timer(0.5, self._clear_selection_highlight)

    def on_mouse_down(self, event) -> None:
        """Start drag selection."""
        if not self.current_path:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        offset = event.screen_y - scroller.content_region.y
        if offset >= 0:
            self._drag_start_row = scroller.scroll_offset.y + offset
            self._drag_current_row = self._drag_start_row

    def on_mouse_move(self, event) -> None:
        """Update selection highlight during drag."""
        start = getattr(self, "_drag_start_row", None)
        if start is None or not self.current_path:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        offset = event.screen_y - scroller.content_region.y
        if offset < 0:
            return
        new_row = scroller.scroll_offset.y + offset
        if new_row != getattr(self, "_drag_current_row", None):
            self._drag_current_row = new_row
            self._update_selection_highlight()

    def _update_selection_highlight(self) -> None:
        """Re-render content with selection highlight on dragged lines."""
        start = getattr(self, "_drag_start_row", None)
        end = getattr(self, "_drag_current_row", None)
        rendered = getattr(self, "_rendered_content", None)
        offsets = getattr(self, "_line_offsets", None)
        if start is None or end is None or rendered is None or offsets is None:
            return
        lo, hi = sorted([start, end])
        # Check all lines in range are valid
        for row in range(lo, hi + 1):
            if self._display_row_to_source(row) < 1:
                return
        if lo >= len(offsets):
            return
        highlight_start = offsets[lo]
        highlight_end = offsets[hi + 1] if hi + 1 < len(offsets) else len(rendered.plain)
        highlighted = rendered.copy()
        highlighted.stylize("on #44475a", highlight_start, highlight_end)
        static = self.query_one("#preview-content", Static)
        static.update(highlighted)

    def _clear_selection_highlight(self) -> None:
        """Restore original content (remove selection highlight)."""
        rendered = getattr(self, "_rendered_content", None)
        if rendered is not None:
            static = self.query_one("#preview-content", Static)
            static.update(rendered)

    def on_mouse_up(self, event) -> None:
        """End drag selection — if dragged across lines, copy file:start-end."""
        start = getattr(self, "_drag_start_row", None)
        if start is None or not self.current_path:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        offset = event.screen_y - scroller.content_region.y
        if offset < 0:
            self._drag_start_row = None
            self._clear_selection_highlight()
            return
        end_row = scroller.scroll_offset.y + offset
        self._drag_start_row = None
        self._drag_current_row = None
        start_line = self._display_row_to_source(start)
        end_line = self._display_row_to_source(end_row)
        if start_line < 1 or end_line < 1:
            self._clear_selection_highlight()
            return
        if start_line == end_line:
            self._clear_selection_highlight()
            return  # Single line — let double-click handle it
        lo, hi = sorted([start_line, end_line])
        ref = self._format_file_ref(lo, hi)
        self.app.copy_to_clipboard(ref)
        self.app.notify(f"File ref copied: {ref}", timeout=2)
        # Clear highlight after a brief moment
        self.set_timer(0.5, self._clear_selection_highlight)
