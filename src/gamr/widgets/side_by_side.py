"""Side-by-side diff modal screen — full file view with aligned padding."""

from __future__ import annotations

import difflib
import re

from rich.cells import cell_len
from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class _DiffContent(Static):
    """Static widget for diff content, no wrapping."""

    ALLOW_SELECT = False


class SideBySideDiffScreen(ModalScreen[int]):
    """Full-screen modal showing old and new file side by side with padding alignment."""

    def on_key(self, event) -> None:
        """Intercept keys so app-level priority bindings don't fire."""
        key = event.key
        if key in ("escape", "s", "q"):
            event.stop()
            event.prevent_default()
            self.dismiss(self._get_current_source_line())
        elif key in ("j", "down"):
            event.stop()
            self.query_one("#sbs-scroll", VerticalScroll).scroll_down()
        elif key in ("k", "up"):
            event.stop()
            self.query_one("#sbs-scroll", VerticalScroll).scroll_up()
        elif key in ("space", "pagedown"):
            event.stop()
            self.query_one("#sbs-scroll", VerticalScroll).scroll_page_down()
        elif key == "pageup":
            event.stop()
            self.query_one("#sbs-scroll", VerticalScroll).scroll_page_up()
        elif key in ("J", "n"):
            event.stop()
            self._jump_to_next_change()
        elif key in ("K", "N"):
            event.stop()
            self._jump_to_prev_change()
        else:
            # Block other keys from reaching app-level bindings
            event.stop()

    def _get_current_source_line(self) -> int:
        """Get the new-file line number at the current scroll position."""
        scroller = self.query_one("#sbs-scroll", VerticalScroll)
        row = int(scroller.scroll_y)
        row_to_new_ln = getattr(self, "_row_to_new_ln", [])
        if not row_to_new_ln:
            return 1
        for i in range(min(row, len(row_to_new_ln) - 1), len(row_to_new_ln)):
            if row_to_new_ln[i]:
                return row_to_new_ln[i]
        return 1

    def _change_hunk_starts(self) -> list[int]:
        """Return display row indices where each change hunk begins."""
        row_types = getattr(self, "_row_types", [])
        if not row_types:
            return []
        starts = []
        prev_is_change = False
        for i, t in enumerate(row_types):
            is_change = t != "same"
            if is_change and not prev_is_change:
                starts.append(i)
            prev_is_change = is_change
        return starts

    def _jump_to_next_change(self) -> None:
        """Jump to the next diff hunk below the visible area."""
        scroller = self.query_one("#sbs-scroll", VerticalScroll)
        visible_bottom = int(scroller.scroll_y + scroller.size.height)
        for row in self._change_hunk_starts():
            if row > visible_bottom:
                scroller.scroll_to(0, max(0, row - 3), animate=False)
                return

    def _jump_to_prev_change(self) -> None:
        """Jump to the previous diff hunk above the visible area."""
        scroller = self.query_one("#sbs-scroll", VerticalScroll)
        visible_top = int(scroller.scroll_y)
        for row in reversed(self._change_hunk_starts()):
            if row < visible_top:
                scroller.scroll_to(0, max(0, row - 3), animate=False)
                return

    DEFAULT_CSS = """
    SideBySideDiffScreen {
        align: center middle;
    }
    #sbs-container {
        width: 95%;
        height: 95%;
        background: #1e1e1e;
        border: thick #555555;
    }
    #sbs-header {
        height: 1;
        background: $surface-lighten-1;
        color: $text;
        padding: 0 1;
    }
    #sbs-scroll {
        height: 1fr;
        background: #272822;
        overflow-x: hidden;
    }
    #sbs-content {
        background: #272822;
        width: auto;
    }
    #sbs-body {
        height: 1fr;
    }
    #sbs-overview {
        width: 1;
        height: 100%;
        background: $surface;
    }
    """

    # Background colors for diff regions
    _BG_CHANGED = "#3d2b00"
    _BG_REMOVED = "#330000"
    _BG_ADDED = "#003300"
    _BG_GAP = "#1a1a1a"
    _BG_CHANGED_BRIGHT = "#664400"
    _BG_REMOVED_BRIGHT = "#501010"
    _BG_ADDED_BRIGHT = "#104010"

    def __init__(self, filename: str, diff_text: str, old_content: str, new_content: str, scroll_to: int = 0) -> None:
        super().__init__()
        self._filename = filename
        self._diff_text = diff_text
        self._old_content = old_content
        self._new_content = new_content
        self._scroll_to = scroll_to

    def compose(self) -> ComposeResult:
        from textual.containers import Horizontal

        with Vertical(id="sbs-container"):
            yield Static(f" {self._filename} — side-by-side diff (esc to close)", id="sbs-header")
            with Horizontal(id="sbs-body"):
                with VerticalScroll(id="sbs-scroll"):
                    yield _DiffContent(id="sbs-content")
                yield Static("", id="sbs-overview")

    def on_mount(self) -> None:
        content, row_to_new_ln, row_types = self._build_combined_view()
        self.query_one("#sbs-content", _DiffContent).update(content)
        self._row_to_new_ln = row_to_new_ln
        self._row_types = row_types
        self._render_overview()
        if self._scroll_to > 1:
            for row, ln in enumerate(row_to_new_ln):
                if ln and ln >= self._scroll_to:
                    scroller = self.query_one("#sbs-scroll", VerticalScroll)
                    scroller.scroll_to(0, row, animate=False)
                    break
        self.query_one("#sbs-scroll", VerticalScroll).focus()

    def _render_overview(self) -> None:
        """Render the 1-column diff overview bar."""
        overview = self.query_one("#sbs-overview", Static)
        height = overview.size.height or 20
        row_types = getattr(self, "_row_types", [])
        if not row_types:
            return
        total = len(row_types)
        result = Text(no_wrap=True)
        for row_idx in range(height):
            # Map this overview row to a range of display rows
            start = int(row_idx * total / height)
            end = int((row_idx + 1) * total / height)
            chunk = row_types[start:end] if end > start else [row_types[min(start, total - 1)]]
            # Determine color from the chunk
            has_changed = "changed" in chunk
            has_added = "added" in chunk
            has_removed = "removed" in chunk
            if has_changed:
                result.append("▐\n", style="#ff8c00")
            elif has_added:
                result.append("▐\n", style="green")
            elif has_removed:
                result.append("▐\n", style="red")
            else:
                result.append(" \n", style="dim")
        overview.update(result)

    def on_resize(self, event) -> None:
        self._render_overview()

    def refresh_content(self, diff_text: str, old_content: str, new_content: str) -> None:
        """Re-render with updated content (called when file changes on disk)."""
        self._diff_text = diff_text
        self._old_content = old_content
        self._new_content = new_content
        scroller = self.query_one("#sbs-scroll", VerticalScroll)
        scroll_y = scroller.scroll_y
        content, row_to_new_ln, row_types = self._build_combined_view()
        self.query_one("#sbs-content", _DiffContent).update(content)
        self._row_to_new_ln = row_to_new_ln
        self._row_types = row_types
        self._render_overview()
        scroller.scroll_to(0, scroll_y, animate=False)

    def _build_combined_view(self) -> tuple[Text, list[int | None], list[str]]:
        """Build a single Text with syntax-highlighted left | right columns.

        Returns the rendered Text, a list mapping display row → new file line number,
        and a list of change types per row.
        """
        old_lines = self._old_content.splitlines()
        new_lines = self._new_content.splitlines()
        aligned = self._align_from_diff(old_lines, new_lines, self._diff_text)

        # Syntax highlight both full files
        old_hi = self._highlight_lines(self._old_content, self._filename)
        new_hi = self._highlight_lines(self._new_content, self._filename)

        max_old = len(old_lines)
        max_new = len(new_lines)
        ln_width = max(len(str(max_old)), len(str(max_new)), 1)

        try:
            term_width = self.app.size.width
        except Exception:
            term_width = 160
        col_width = (int(term_width * 0.95) - 3) // 2
        text_width = col_width - ln_width - 2  # space for line number + 2 spaces

        result = Text(no_wrap=True)
        row_to_new_ln: list[int | None] = []
        row_types: list[str] = []

        for old_ln, old_text, new_ln, new_text, change_type in aligned:
            # Build left cell
            left_start = len(result)
            if old_ln is not None:
                result.append(f"{str(old_ln).rjust(ln_width)}  ", style="dim")
                hi_line = old_hi.get(old_ln)
                if hi_line:
                    self._append_truncated(result, hi_line, text_width)
                else:
                    self._append_truncated_str(result, old_text, text_width)
            else:
                result.append(f"{''.rjust(ln_width)}  ")
            # Pad left cell to col_width
            current_len = cell_len(result.plain[left_start:])
            if current_len < col_width:
                result.append(" " * (col_width - current_len))
            left_end = len(result)

            # Apply line-level background for left
            if change_type == "changed":
                result.stylize(f"on {self._BG_CHANGED}", left_start, left_end)
            elif change_type == "removed":
                result.stylize(f"on {self._BG_REMOVED}", left_start, left_end)
            elif change_type == "added":
                result.stylize(f"on {self._BG_GAP}", left_start, left_end)

            # Divider
            result.append("│", style="dim")

            # Build right cell
            right_start = len(result)
            if new_ln is not None:
                result.append(f"{str(new_ln).rjust(ln_width)}  ", style="dim")
                hi_line = new_hi.get(new_ln)
                if hi_line:
                    self._append_truncated(result, hi_line, text_width)
                else:
                    self._append_truncated_str(result, new_text, text_width)
            else:
                result.append(f"{''.rjust(ln_width)}  ")
            # Pad right cell to col_width
            current_len = cell_len(result.plain[right_start:])
            if current_len < col_width:
                result.append(" " * (col_width - current_len))
            right_end = len(result)

            # Apply line-level background for right
            if change_type == "changed":
                result.stylize(f"on {self._BG_CHANGED}", right_start, right_end)
            elif change_type == "added":
                result.stylize(f"on {self._BG_ADDED}", right_start, right_end)
            elif change_type == "removed":
                result.stylize(f"on {self._BG_GAP}", right_start, right_end)

            # Sub-line highlighting for changed lines
            if change_type == "changed" and old_ln is not None and new_ln is not None:
                prefix_len = ln_width + 2
                self._apply_inline_diff(
                    result,
                    old_text,
                    new_text,
                    text_width,
                    prefix_len,
                    left_start,
                    right_start,
                )

            result.append("\n")
            row_to_new_ln.append(new_ln)
            row_types.append(change_type)

        return result, row_to_new_ln, row_types

    def _apply_inline_diff(
        self,
        result: Text,
        old_text: str,
        new_text: str,
        text_width: int,
        prefix_len: int,
        left_start: int,
        right_start: int,
    ) -> None:
        """Highlight character-level differences within a changed line pair."""
        sm = difflib.SequenceMatcher(None, old_text, new_text)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag == "equal":
                continue
            # Highlight changed region on the left (old)
            lo = min(i1, text_width)
            hi = min(i2, text_width)
            if lo < hi:
                result.stylize(
                    f"on {self._BG_CHANGED_BRIGHT}",
                    left_start + prefix_len + lo,
                    left_start + prefix_len + hi,
                )
            # Highlight changed region on the right (new)
            lo = min(j1, text_width)
            hi = min(j2, text_width)
            if lo < hi:
                result.stylize(
                    f"on {self._BG_CHANGED_BRIGHT}",
                    right_start + prefix_len + lo,
                    right_start + prefix_len + hi,
                )

    @staticmethod
    def _append_truncated(result: Text, hi_line: Text, max_width: int) -> None:
        """Append a highlighted line to result, truncated to max_width cell width."""
        plain = hi_line.plain
        if cell_len(plain) <= max_width:
            result.append_text(hi_line)
        else:
            # Truncate by cell width
            w = 0
            cut = 0
            for i, ch in enumerate(plain):
                cw = cell_len(ch)
                if w + cw > max_width:
                    break
                w += cw
                cut = i + 1
            result.append_text(hi_line[:cut])

    @staticmethod
    def _append_truncated_str(result: Text, text: str, max_width: int) -> None:
        """Append a plain string truncated to max_width cell width."""
        if cell_len(text) <= max_width:
            result.append(text)
        else:
            w = 0
            cut = 0
            for i, ch in enumerate(text):
                cw = cell_len(ch)
                if w + cw > max_width:
                    break
                w += cw
                cut = i + 1
            result.append(text[:cut])

    @staticmethod
    def _highlight_lines(content: str, filename: str) -> dict[int, Text]:
        """Syntax highlight content and return a dict of line_number → highlighted Text."""
        if not content:
            return {}
        lexer = Syntax.guess_lexer(filename, content)
        syntax = Syntax(content, lexer=lexer, line_numbers=False, word_wrap=False, theme="monokai")
        highlighted = syntax.highlight(content)
        lines = highlighted.split(allow_blank=True)
        return {i + 1: line for i, line in enumerate(lines)}

    @staticmethod
    def _align_from_diff(
        old_lines: list[str], new_lines: list[str], diff_text: str
    ) -> list[tuple[int | None, str, int | None, str, str]]:
        """Produce aligned rows: (old_ln, old_text, new_ln, new_text, change_type).

        change_type: 'same', 'added', 'removed', 'changed'
        """
        hunks: list[tuple[int, int, int, int, list[str]]] = []
        current_hunk_lines: list[str] = []
        old_start = new_start = old_count = new_count = 0

        for line in diff_text.splitlines():
            if line.startswith("@@"):
                if current_hunk_lines:
                    hunks.append((old_start, old_count, new_start, new_count, current_hunk_lines))
                current_hunk_lines = []
                m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
                if m:
                    old_start = int(m.group(1))
                    old_count = int(m.group(2)) if m.group(2) else 1
                    new_start = int(m.group(3))
                    new_count = int(m.group(4)) if m.group(4) else 1
            elif line.startswith("---") or line.startswith("+++"):
                continue
            elif line and line[0] in ("+", "-", " "):
                current_hunk_lines.append(line)

        if current_hunk_lines:
            hunks.append((old_start, old_count, new_start, new_count, current_hunk_lines))

        result: list[tuple[int | None, str, int | None, str, str]] = []
        old_pos = 0
        new_pos = 0

        for h_old_start, _, h_new_start, _, hunk_lines in hunks:
            h_old_idx = h_old_start - 1
            h_new_idx = h_new_start - 1

            while old_pos < h_old_idx and new_pos < h_new_idx:
                result.append((old_pos + 1, old_lines[old_pos], new_pos + 1, new_lines[new_pos], "same"))
                old_pos += 1
                new_pos += 1

            removed_buf: list[tuple[int, str]] = []
            added_buf: list[tuple[int, str]] = []
            for hline in hunk_lines:
                if hline.startswith("-"):
                    # Flush any pending added-only if we hit a new remove block
                    if added_buf and not removed_buf:
                        for new_ln, new_text in added_buf:
                            result.append((None, "", new_ln, new_text, "added"))
                        added_buf = []
                    removed_buf.append((old_pos + 1, old_lines[old_pos] if old_pos < len(old_lines) else hline[1:]))
                    old_pos += 1
                elif hline.startswith("+"):
                    new_text = new_lines[new_pos] if new_pos < len(new_lines) else hline[1:]
                    added_buf.append((new_pos + 1, new_text))
                    new_pos += 1
                else:
                    # Context line — flush remove/add block
                    # Pair up as many as possible as "changed", remainder is added/removed
                    paired = min(len(removed_buf), len(added_buf))
                    for i in range(paired):
                        result.append(
                            (removed_buf[i][0], removed_buf[i][1], added_buf[i][0], added_buf[i][1], "changed")
                        )
                    for i in range(paired, len(removed_buf)):
                        result.append((removed_buf[i][0], removed_buf[i][1], None, "", "removed"))
                    for i in range(paired, len(added_buf)):
                        result.append((None, "", added_buf[i][0], added_buf[i][1], "added"))
                    removed_buf = []
                    added_buf = []
                    result.append(
                        (
                            old_pos + 1,
                            old_lines[old_pos] if old_pos < len(old_lines) else hline[1:],
                            new_pos + 1,
                            new_lines[new_pos] if new_pos < len(new_lines) else hline[1:],
                            "same",
                        )
                    )
                    old_pos += 1
                    new_pos += 1

            # Flush remaining remove/add block at end of hunk
            paired = min(len(removed_buf), len(added_buf))
            for i in range(paired):
                result.append((removed_buf[i][0], removed_buf[i][1], added_buf[i][0], added_buf[i][1], "changed"))
            for i in range(paired, len(removed_buf)):
                result.append((removed_buf[i][0], removed_buf[i][1], None, "", "removed"))
            for i in range(paired, len(added_buf)):
                result.append((None, "", added_buf[i][0], added_buf[i][1], "added"))

        while old_pos < len(old_lines) and new_pos < len(new_lines):
            result.append((old_pos + 1, old_lines[old_pos], new_pos + 1, new_lines[new_pos], "same"))
            old_pos += 1
            new_pos += 1

        while old_pos < len(old_lines):
            result.append((old_pos + 1, old_lines[old_pos], None, "", "removed"))
            old_pos += 1
        while new_pos < len(new_lines):
            result.append((None, "", new_pos + 1, new_lines[new_pos], "added"))
            new_pos += 1

        return result
