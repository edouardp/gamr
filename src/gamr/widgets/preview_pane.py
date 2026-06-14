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
from dataclasses import dataclass, field
from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.events import Click
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from gamr.config import DIFF_PAD_WIDTH
from gamr.models import DiffMode
from gamr.services.diff_parser import compute_gutter_markers, parse_diff_hunks


@dataclass
class RenderResult:
    """Result from _render_highlighted — avoids a 6-tuple."""

    styled: Text
    total_lines: int
    added_lines: set[int] = field(default_factory=set)
    removed_context: dict[int, list[str]] = field(default_factory=dict)
    display_green: set[int] = field(default_factory=set)
    display_red: set[int] = field(default_factory=set)


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
    use_quadrant: reactive[bool] = reactive(False)
    use_sextant: reactive[bool] = reactive(False)

    def set_diff_map(self, total_lines: int, added: set[int], removed: dict[int, list[str]]) -> None:
        """Build overview from full-diff data (added lines + removed context dict)."""
        if total_lines == 0:
            self.update("")
            return

        self._total_lines = total_lines
        self._green = added
        self._red: set[int] = set()
        self._orange: set[int] = set()
        self._render_overview()

    def set_display_row_map(self, total_rows: int, green: set[int], red: set[int]) -> None:
        """Build overview from display-row-level data (used by full diff mode)."""
        if total_rows == 0:
            self.update("")
            return

        self._total_lines = total_rows
        self._green = green
        self._red = red
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

        # Use the widget's allocated height as the overview bar height
        height = self.size.height
        if height < 2:
            height = 20

        if self.use_sextant:
            result = self._render_sextant(total_lines, height, green, red, orange)
        elif self.use_braille:
            result = self._render_braille(total_lines, height, green, red, orange)
        elif self.use_quadrant:
            result = self._render_quadrant(total_lines, height, green, red, orange)
        else:
            result = self._render_lines(total_lines, height, green, red, orange)

        self.update(result)

    @staticmethod
    def _classify_color(has_green: bool, has_red: bool, has_orange: bool) -> str:
        """Return style string based on which change types are present."""
        if has_orange or (has_green and has_red):
            return "#ff8c00"
        if has_green:
            return "green"
        if has_red:
            return "red"
        return "dim"

    def _render_lines(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using ┃/│ line characters (1 line per row)."""
        return self._render_subcell(total_lines, height, green, red, orange, slots_per_row=1, char_fn=self._char_line)

    def _render_quadrant(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using lower-half block characters (2 lines per row)."""
        return self._render_subcell(
            total_lines, height, green, red, orange, slots_per_row=2, char_fn=self._char_quadrant
        )

    def _render_sextant(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using sextant right-column characters (3 lines per row)."""
        return self._render_subcell(
            total_lines, height, green, red, orange, slots_per_row=3, char_fn=self._char_sextant
        )

    def _render_braille(self, total_lines: int, height: int, green: set[int], red: set[int], orange: set[int]) -> Text:
        """Render using braille left-column characters (4 lines per row)."""
        return self._render_subcell(
            total_lines, height, green, red, orange, slots_per_row=4, char_fn=self._char_braille
        )

    def _render_subcell(
        self,
        total_lines: int,
        height: int,
        green: set[int],
        red: set[int],
        orange: set[int],
        *,
        slots_per_row: int,
        char_fn,
    ) -> Text:
        """Generic sub-cell renderer with adaptive scaling.

        Principles:
        - When total_lines <= height: 1:1 mode, one full-height mark per line
        - When total_lines > height: use sub-cell slots to encode multiple lines per row
        - Never miss a changed line (any line touching a slot's range lights it)
        - For braille (discrete dots): each dot represents ≥1 line
        """
        all_changes = green | red | orange
        result = Text(no_wrap=True)

        total_slots = height * slots_per_row
        # When file fits in view, use 1:1 positioning (no stretching).
        # When file overflows, scale to fill all available slots.
        if total_lines <= height:
            scale = float(slots_per_row)  # 1 line = slots_per_row slots = 1 full row
        else:
            scale = total_slots / total_lines

        # Pass 1: Build slot bitmap — map each changed line to its slot(s)
        slot_lit = [False] * total_slots
        slot_green = [False] * total_slots
        slot_red = [False] * total_slots
        slot_orange = [False] * total_slots

        for line in all_changes:
            # Each line occupies a proportional range of slots
            s_start = int((line - 1) * scale)
            s_end = max(s_start + 1, int(line * scale))
            for s in range(s_start, min(s_end, total_slots)):
                slot_lit[s] = True
                if line in green:
                    slot_green[s] = True
                if line in red:
                    slot_red[s] = True
                if line in orange:
                    slot_orange[s] = True

        # Pass 2: Render slots into characters
        for row in range(height):
            base = row * slots_per_row
            slot_hits = slot_lit[base : base + slots_per_row]
            has_green = any(slot_green[base : base + slots_per_row])
            has_red = any(slot_red[base : base + slots_per_row])
            has_orange = any(slot_orange[base : base + slots_per_row])
            char = char_fn(slot_hits)
            style = self._classify_color(has_green, has_red, has_orange)
            result.append(char + "\n", style=style)

        return result

    @staticmethod
    def _char_line(slots: list[bool]) -> str:
        return "▐" if slots[0] else " "

    @staticmethod
    def _char_quadrant(slots: list[bool]) -> str:
        # Right half: ▝ = top-right, ▗ = bottom-right, ▐ = both
        top, bot = slots
        if top and bot:
            return "▐"
        if top:
            return "▝"
        if bot:
            return "▗"
        return " "

    @staticmethod
    def _char_braille(slots: list[bool]) -> str:
        # Right column dots: positions 3,4,5,7 in braille encoding
        _BITS = [0x08, 0x10, 0x20, 0x80]
        dots = sum(b for hit, b in zip(slots, _BITS, strict=True) if hit)
        return chr(0x2800 + dots)

    @staticmethod
    def _char_sextant(slots: list[bool]) -> str:
        # User-specified characters for right-column sextant rendering
        _LOOKUP = {
            (False, False, False): " ",
            (True, False, False): "🬁",  # TR
            (False, True, False): "🬇",  # MR
            (False, False, True): "🬞",  # BR
            (True, True, False): "🬉",  # TR MR
            (True, False, True): "🬠",  # TR BR
            (False, True, True): "🬦",  # MR BR
            (True, True, True): "▐",  # TR MR BR (full right half)
        }
        return _LOOKUP[tuple(slots)]

    def watch_use_braille(self, value: bool) -> None:
        self._render_overview()

    def watch_use_quadrant(self, value: bool) -> None:
        self._render_overview()

    def watch_use_sextant(self, value: bool) -> None:
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

    can_focus = True

    BINDINGS = [
        Binding("j", "scroll_down", "Scroll down", show=False),
        Binding("k", "scroll_up", "Scroll up", show=False),
        Binding("down", "scroll_down", "Scroll down", show=False),
        Binding("up", "scroll_up", "Scroll up", show=False),
        Binding("space", "page_down", "Page down", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
    ]

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
    PreviewPane #preview-message {
        width: auto;
        height: auto;
        padding: 1 3;
        border: round $accent;
        border-title-align: center;
        border-title-color: $warning;
        border-title-style: bold;
        text-align: center;
        color: $text-muted;
    }
    PreviewPane #preview-body.show-message {
        align: center middle;
    }
    PreviewPane .hidden {
        display: none;
    }
    """

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._row_to_source: list[int] = []
        self._change_source_lines: list[int] = []
        self._rendered_content: Text | None = None
        self._line_offsets: list[int] | None = None
        self._last_rendered_path: Path | None = None
        self._drag_start_row: int | None = None
        self._drag_current_row: int | None = None
        self._highlight_timer = None

    def compose(self) -> ComposeResult:
        yield PreviewHeader(id="preview-header")
        with Horizontal(id="preview-body"):
            with VerticalScroll(id="preview-scroll"):
                yield _PreviewContent(id="preview-content")
            yield DiffOverview(id="diff-overview")
            yield Static(id="preview-message", classes="hidden")

    def action_scroll_down(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_down()

    def action_scroll_up(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_up()

    def action_page_down(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_page_down()

    def action_page_up(self) -> None:
        self.query_one("#preview-scroll", VerticalScroll).scroll_page_up()

    def action_next_change(self) -> None:
        """Jump to the next change hunk not currently visible."""
        hunks = self._change_hunk_starts()
        if not hunks:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        visible_bottom = int(scroller.scroll_y + scroller.size.height)
        mapping = self._row_to_source
        bottom_source = mapping[min(visible_bottom, len(mapping) - 1)] if mapping else 0
        for line in hunks:
            if line > bottom_source:
                self._scroll_to_source_with_context(line)
                return

    def action_prev_change(self) -> None:
        """Jump to the previous change hunk not currently visible."""
        hunks = self._change_hunk_starts()
        if not hunks:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        visible_top = int(scroller.scroll_y)
        mapping = self._row_to_source
        top_source = mapping[min(visible_top, len(mapping) - 1)] if mapping else 0
        for line in reversed(hunks):
            if line < top_source:
                self._scroll_to_source_with_context(line)
                return

    def _change_hunk_starts(self) -> list[int]:
        """Return the first line of each contiguous group of changed lines."""
        lines = self._change_source_lines
        if not lines:
            return []
        starts = [lines[0]]
        for i in range(1, len(lines)):
            if lines[i] != lines[i - 1] + 1:
                starts.append(lines[i])
        return starts

    def _scroll_to_source_with_context(self, source_line: int, context: int = 3) -> None:
        """Scroll so source_line is visible with context lines above it."""
        self.scroll_to_source_line(max(1, source_line - context))

    def update_header(self) -> None:
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
            pad = max(1, 60 - len(name) - len(mode))
            header.update(f"{name}{' ' * pad}{mode}")
        else:
            header.update("")

    def show_file(self, path: Path, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Display a file with syntax highlighting (no diff markers)."""
        self.current_path = path
        content = self._read_file(path)
        if content is None:
            return
        result = self._render_highlighted(path, content)
        self._change_source_lines = []
        self._update_overview_for_diff(0, set(), {})
        self._set_content(result.styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

    def show_full_diff(self, path: Path, diff_text: str, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Display file with syntax highlighting + diff markers."""
        self.current_path = path
        if path.exists():
            content = self._read_file(path)
            if content is None:
                return
        else:
            content = ""
        r = self._render_highlighted(path, content, diff_text=diff_text)
        self._change_source_lines = sorted(r.added_lines | set(r.removed_context.keys()))
        # Overview uses display-row positions (matching preview rendering)
        total_display_rows = len(self._row_to_source)
        overview = self.query_one(DiffOverview)
        if total_display_rows > 0 and (r.display_green or r.display_red):
            overview.set_display_row_map(total_display_rows, r.display_green, r.display_red)
            overview.display = True
        else:
            overview.clear_overview()
            overview.display = False
        self._set_content(r.styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

    def show_gutter_diff(
        self, path: Path, diff_text: str, *, scroll_to_top: bool = True, restore_line: int = 0
    ) -> None:
        """Display file with syntax highlighting + a single gutter column for changes."""
        self.current_path = path
        content = self._read_file(path)
        if content is None:
            return

        total_lines = len(content.splitlines())
        markers = compute_gutter_markers(diff_text, total_lines)
        gutter = (markers.changed, markers.pure_added, markers.has_deletion_after)

        r = self._render_highlighted(path, content, gutter_markers=gutter)

        self._change_source_lines = sorted(markers.changed | markers.pure_added | markers.has_deletion_after)
        overview = self.query_one(DiffOverview)
        has_any_markers = bool(markers.changed or markers.pure_added or markers.has_deletion_after)
        if has_any_markers:
            overview.set_gutter_map(r.total_lines, markers.changed, markers.pure_added, markers.has_deletion_after)
            overview.display = True
        else:
            overview.clear_overview()
            overview.display = False
        self._set_content(r.styled, scroll_to_top=scroll_to_top, restore_line=restore_line)

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
        self._change_source_lines = []

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

    def show_message(self, message: str, *, title: str = "Notice") -> None:
        """Show a styled dialog message in the preview area."""
        msg = self.query_one("#preview-message", Static)
        body = self.query_one("#preview-body", Horizontal)
        self.query_one("#preview-scroll", VerticalScroll).add_class("hidden")
        self.query_one(DiffOverview).add_class("hidden")
        msg.border_title = title
        msg.update(message)
        msg.remove_class("hidden")
        body.add_class("show-message")
        self._last_rendered_path = None

    def _read_file(self, path: Path) -> str | None:
        """Read file, handle errors and binary detection."""
        if not path.exists():
            self.show_message(path.name, title="ℹ️ File Deleted")
            return None
        try:
            size = path.stat().st_size
        except OSError:
            self.show_message("Cannot read file", title="⚠️ Error")
            return None

        # Skip very large files (>10MB)
        if size > 10 * 1024 * 1024:
            self.show_message(f"{path.name}\n\n{size // 1024 // 1024} MB", title="⚠️ File Too Large")
            return None

        try:
            raw = path.read_bytes()
        except OSError:
            self.show_message("Cannot read file", title="⚠️ Error")
            return None

        # Null byte in first 8KB is a heuristic for binary files
        if b"\x00" in raw[:8192]:
            self.show_message(path.name, title="Binary File")
            return None

        return raw.decode(errors="replace")

    def _render_highlighted(
        self,
        path: Path,
        content: str,
        diff_text: str | None = None,
        gutter_markers: tuple[set[int], set[int], set[int]] | None = None,
    ) -> RenderResult:
        """Shared renderer: syntax-highlighted file with optional diff/gutter markers."""
        diff_data = parse_diff_hunks(diff_text)
        added_lines = diff_data.added_lines
        removed_context = diff_data.removed_context
        trailing_removed = diff_data.trailing_removed

        # Syntax highlight the content. Deleted/empty files have no source rows.
        # Skip syntax highlighting for large files (>100KB) to keep rendering fast.
        if content and len(content) <= 100 * 1024:
            lexer = Syntax.guess_lexer(str(path), content)
            syntax = Syntax(content, lexer=lexer, line_numbers=False, word_wrap=False, theme=self.syntax_theme)
            highlighted = syntax.highlight(content)
            hi_lines = highlighted.split(allow_blank=True)
        elif content:
            hi_lines = [Text(line) for line in content.split("\n")]
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
        display_green: set[int] = set()
        display_red: set[int] = set()

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
                    display_red.add(len(row_to_source))

            # Line number
            styled.append(f"{str(i).rjust(ln_width)} ", style="dim")

            # Gutter marker column (gutter mode)
            if gutter_markers:
                g_changed, g_added, g_deleted = gutter_markers
                if i in g_changed:
                    styled.append("●", style="bold #ff8c00")
                elif i in g_added:
                    styled.append("+", style="bold green")
                elif i in g_deleted:
                    styled.append("_", style="bold red")
                elif g_changed or g_added or g_deleted:
                    styled.append(" ")
                styled.append(" ")
                styled.append_text(hi_line)
            # Diff marker + content (full diff mode)
            elif diff_text and i in added_lines:
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
            if diff_text and i in added_lines:
                display_green.add(len(row_to_source))

        # Trailing removed lines
        for rline in trailing_removed:
            ln_pad = " " * ln_width
            styled.append(f"{ln_pad} ", style="dim")
            line_content = f"- {rline}"
            styled.append(line_content.ljust(pad_width) + "\n", style=f"on {self._diff_bg_removed}")
            row_to_source.append(total_lines)
            display_red.add(len(row_to_source))

        self._row_to_source = row_to_source

        return RenderResult(styled, total_lines, added_lines, removed_context, display_green, display_red)

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
        # Snap to animation target (sync alternative to async stop_animation)
        scroller.scroll_y = scroller.scroll_target_y
        row = int(scroller.scroll_y)
        mapping = self._row_to_source
        if not mapping:
            return row + 1
        # Find the first valid source line at or after the scroll position
        for i in range(min(row, len(mapping) - 1), len(mapping)):
            if mapping[i] > 0:
                return mapping[i]
        # Fall back: search backwards
        for i in range(min(row, len(mapping) - 1), -1, -1):
            if mapping[i] > 0:
                return mapping[i]
        return 1

    def scroll_to_source_line(self, source_line: int) -> None:
        """Scroll to the display row corresponding to a source line number."""
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        mapping = self._row_to_source
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
        # Hide message widget, show content widget
        self.query_one("#preview-message", Static).add_class("hidden")
        self.query_one("#preview-scroll", VerticalScroll).remove_class("hidden")
        self.query_one("#preview-body", Horizontal).remove_class("show-message")
        self._rendered_content = content if isinstance(content, Text) else None
        # Precompute line start offsets for O(1) highlight lookups
        if isinstance(content, Text):
            plain = content.plain
            self._line_offsets = [0] + [i + 1 for i, c in enumerate(plain) if c == "\n"]
        else:
            self._line_offsets = None
        static = self.query_one("#preview-content", Static)
        static.update(content)
        self.update_header()
        self._last_rendered_path = self.current_path
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        if restore_line > 1:
            scroller.scroll_y = scroller.scroll_target_y
            self.scroll_to_source_line(restore_line)
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
        mapping = self._row_to_source
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
        start = self._drag_start_row
        if start is None or not self.current_path:
            return
        scroller = self.query_one("#preview-scroll", VerticalScroll)
        offset = event.screen_y - scroller.content_region.y
        if offset < 0:
            return
        new_row = scroller.scroll_offset.y + offset
        if new_row != self._drag_current_row:
            self._drag_current_row = new_row
            # Throttle: schedule highlight update, cancelling any pending one
            if self._highlight_timer:
                self._highlight_timer.stop()
            self._highlight_timer = self.set_timer(0.03, self._update_selection_highlight)

    def _update_selection_highlight(self) -> None:
        """Re-render content with selection highlight on dragged lines."""
        start = self._drag_start_row
        end = self._drag_current_row
        rendered = self._rendered_content
        offsets = self._line_offsets
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
        rendered = self._rendered_content
        if rendered is not None:
            static = self.query_one("#preview-content", Static)
            static.update(rendered)

    def on_mouse_up(self, event) -> None:
        """End drag selection — if dragged across lines, copy file:start-end."""
        start = self._drag_start_row
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
