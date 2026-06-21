"""Toolbar widget — shows logo when idle, search input when filtering."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from gamr.models import GitStatus
from gamr.services.filter import statuses_for_filter_ids


def _supports_sextants() -> bool:
    """Check if the terminal supports Unicode Symbols for Legacy Computing."""
    import os

    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    # Terminals with confirmed sextant/legacy computing support
    supported = ("ghostty", "kitty", "wezterm", "cmux")
    return any(name in term or name in term_program for name in supported)


def _supports_kitty_graphics() -> bool:
    """Check if the terminal supports the kitty graphics protocol."""
    import os

    term = os.environ.get("TERM", "").lower()
    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    return (
        "KITTY_WINDOW_ID" in os.environ
        or term == "xterm-ghostty"
        or "GHOSTTY_RESOURCES_DIR" in os.environ
        or "wezterm" in term_program
    )


# Full diacritics table from kitty protocol spec (row/column encoding)
_ROW_COL_DIACRITICS = (
    "\u0305\u030d\u030e\u0310\u0312\u033d\u033e\u033f"
    "\u0346\u034a\u034b\u034c\u0350\u0351\u0352\u0357"
    "\u035b\u0363\u0364\u0365\u0366\u0367\u0368\u0369"
    "\u036a\u036b\u036c\u036d\u036e\u036f\u0483\u0484"
    "\u0485\u0486\u0487\u0592\u0593\u0594\u0595\u0597"
    "\u0598\u0599\u059c\u059d\u059e\u059f\u05a0\u05a1"
    "\u05a8\u05a9\u05ab\u05ac\u05af\u05c4\u0610\u0611"
    "\u0612\u0613\u0614\u0615\u0616\u0617\u0657\u0658"
)


def _transmit_logo_image() -> int | None:
    """Transmit the logo PNG via kitty graphics protocol, return image id or None."""
    import base64
    import os
    from pathlib import Path

    if not _supports_kitty_graphics():
        return None

    logo_path = Path(__file__).parent.parent / "logo.png"
    if not logo_path.exists():
        return None

    image_id = 42
    png_data = logo_path.read_bytes()
    encoded = base64.standard_b64encode(png_data).decode("ascii")
    chunks = [encoded[i : i + 4096] for i in range(0, len(encoded), 4096)]

    # Transmit only (a=t), no placement yet
    buf = []
    for idx, chunk in enumerate(chunks):
        is_first = idx == 0
        is_last = idx == len(chunks) - 1
        m = 0 if is_last else 1
        if is_first:
            buf.append(f"\033_Ga=t,f=100,q=2,i={image_id},m={m};{chunk}\033\\")
        else:
            buf.append(f"\033_Gm={m};{chunk}\033\\")

    try:
        fd = os.open("/dev/tty", os.O_WRONLY)
        os.write(fd, "".join(buf).encode())
        os.close(fd)
    except OSError:
        return None

    return image_id


def _make_placeholder(image_id: int, cols: int, rows: int) -> str:
    """Build Unicode placeholder string for a kitty graphics virtual placement."""
    placeholder = "\U0010eeee"
    # Encode image_id as RGB foreground color (lower 24 bits)
    r = (image_id >> 16) & 0xFF
    g = (image_id >> 8) & 0xFF
    b = image_id & 0xFF
    # MSB of image_id (upper 8 bits) goes as 3rd diacritic
    msb = (image_id >> 24) & 0xFF

    color_start = f"\033[38;2;{r};{g};{b}m"
    color_end = "\033[39m"

    lines = []
    for row in range(rows):
        row_d = _ROW_COL_DIACRITICS[row]
        msb_d = _ROW_COL_DIACRITICS[msb]
        line_chars = []
        for col in range(cols):
            col_d = _ROW_COL_DIACRITICS[col]
            line_chars.append(f"{placeholder}{row_d}{col_d}{msb_d}")
        lines.append(f"{color_start}{''.join(line_chars)}{color_end}")
    return "\n".join(lines)


# Module-level: attempt to transmit logo on import if supported
_KITTY_LOGO_ID: int | None = None


def _get_logo() -> str:
    """Return the appropriate logo based on terminal capabilities."""
    global _KITTY_LOGO_ID
    if _KITTY_LOGO_ID is None and _supports_kitty_graphics():
        _KITTY_LOGO_ID = _transmit_logo_image()

    if _KITTY_LOGO_ID is not None:
        # Return blank space so the sextant logo doesn't show through
        return " \n \n "

    if _supports_sextants():
        return (
            "  🭆🬋🭑 🭆🬋🭑 🬹🬿🭊🬹 🬹🬋🭑 ╷ Git-aware\n"
            "  █🬇🬹 █🬋█ █🭕🭠█ █🬋🬴 │ Agentic coding assistant\n"
            "  🭧🬋🭜 🬎 🬎 🬎  🬎 🬎 🬎 ╵ Monitor & Review tool"
        )
    return "  ┏━╸┏━┓┏┳┓┏━┓  Git-aware\n  ┃╺┓┣━┫┃┃┃┣┳┛  Agentic coding assistant\n  ┗━┛╹ ╹╹ ╹╹┗╸  Monitor & Review tool"


class _StatusItem(Static):
    """Clickable status indicator."""

    ALLOW_SELECT = False

    def on_click(self) -> None:
        actions = {
            "st-view": "action_cycle_view",
            "st-files": "action_toggle_modified",
            "st-follow": "action_toggle_follow",
            "st-diff": "action_toggle_diff",
            "st-overview": "action_cycle_overview",
            "st-blame": "action_toggle_blame",
        }
        action = actions.get(self.id or "")
        if action:
            getattr(self.app, action)()


class Toolbar(Widget):
    """Horizontal bar with search input and programmatic filter state."""

    class FiltersChanged(Message):
        """Sent when active filters change."""

        def __init__(self, active_statuses: set[GitStatus], search_query: str) -> None:
            super().__init__()
            self.active_statuses = active_statuses
            self.search_query = search_query

    selected_filter_ids: reactive[set[str]] = reactive(set, always_update=True)
    search_query: reactive[str] = reactive("")

    DEFAULT_CSS = """
    Toolbar {
        height: 3;
        dock: top;
        layout: horizontal;
    }
    Toolbar Horizontal {
        height: 3;
        width: 100%;
    }
    Toolbar Input {
        width: 1fr;
    }
    Toolbar .hidden {
        display: none;
    }
    Toolbar #logo {
        width: 1fr;
        content-align: center middle;
        color: $text-muted;
    }
    Toolbar #status-left {
        width: 16;
        height: 3;
        padding: 0 1;
    }
    Toolbar #status-right {
        width: 16;
        height: 3;
        padding: 0 1;
    }
    Toolbar .status-item {
        height: 1;
        width: 100%;
        color: $text-muted;
    }
    Toolbar #status-right .status-item {
        text-align: right;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="status-left"):
                yield _StatusItem("", id="st-view", classes="status-item")
                yield _StatusItem("", id="st-files", classes="status-item")
                yield _StatusItem("", id="st-blame", classes="status-item")
            yield Static(
                _get_logo(),
                id="logo",
            )
            yield Input(placeholder="🔍 Filter files...", id="search-input", classes="hidden")
            with Vertical(id="status-right"):
                yield _StatusItem("", id="st-diff", classes="status-item")
                yield _StatusItem("", id="st-overview", classes="status-item")
                yield _StatusItem("", id="st-follow", classes="status-item")

    def on_mount(self) -> None:
        if _KITTY_LOGO_ID is not None:
            self.call_after_refresh(self._place_logo_image)

    def on_resize(self) -> None:
        if _KITTY_LOGO_ID is not None:
            self.call_after_refresh(self._place_logo_image)

    def _place_logo_image(self) -> None:
        """Place the kitty graphics image at the logo widget's screen position."""
        if _KITTY_LOGO_ID is None:
            return
        logo = self.query_one("#logo", Static)
        region = logo.region
        if region.width < 1:
            return
        # Delete previous placement, then re-place
        img_cols = 20
        rows = region.height or 3
        x_offset = max(0, (region.width - img_cols) // 2)
        x = region.x + x_offset + 1  # 1-based
        y = region.y + 1  # 1-based
        seq = (
            # Delete old placements of this image
            f"\033_Ga=d,d=i,i={_KITTY_LOGO_ID},q=2;\033\\"
            # Save cursor, position, place, restore
            f"\033[s"
            f"\033[{y};{x}H"
            f"\033_Ga=p,i={_KITTY_LOGO_ID},q=2,c={img_cols},r={rows},C=1;\033\\"
            f"\033[u"
        )
        if self.app._driver is not None:
            self.app._driver.write(seq)

    def update_status(
        self,
        *,
        git_filter: bool,
        follow: bool,
        diff_mode: str,
        view_mode: str,
        file_count: int = 0,
        total_files: int = 0,
        overview_style: str = "",
        blame_visible: bool = False,
    ) -> None:
        """Update the status indicators."""
        # Left: file pane state
        view_icons = {"tree": "🌳 tree", "flat": "📄 flat", "path": "📁 path", "sorted": "↕️ sorted"}
        self.query_one("#st-view", _StatusItem).update(view_icons.get(view_mode, ""))

        if git_filter:
            self.query_one("#st-files", _StatusItem).update(f"🔸 git ({file_count}/{total_files})")
        else:
            if file_count < total_files:
                self.query_one("#st-files", _StatusItem).update(f"📋 {file_count}/{total_files} files")
            else:
                self.query_one("#st-files", _StatusItem).update(f"📋 {total_files} files")

        self.query_one("#st-blame", _StatusItem).update("👤 blame" if blame_visible else "👤 ·")

        # Right: preview pane state
        self.query_one("#st-diff", _StatusItem).update(f"{diff_mode} 👓")

        if overview_style and overview_style != "off":
            overview_labels = {"line": "1x", "quadrant": "2x", "sextant": "3x", "braille": "⣿"}
            self.query_one("#st-overview", _StatusItem).update(
                f"overview {overview_labels.get(overview_style, overview_style)}"
            )
        else:
            self.query_one("#st-overview", _StatusItem).update("overview ·")

        self.query_one("#st-follow", _StatusItem).update("follow 👀" if follow else "· 👀")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value
            self.post_message(self.FiltersChanged(self.active_statuses, event.value))
            # Show/hide logo based on whether there's a query
            self.query_one("#logo").set_class(bool(event.value), "hidden")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "search-input":
            self.hide_search()
            self.app.query_one("FileTreeTable").focus()

    def show_search(self) -> None:
        """Show the search input and hide the logo."""
        self.query_one("#logo").add_class("hidden")
        inp = self.query_one("#search-input", Input)
        inp.remove_class("hidden")
        inp.focus()

    def hide_search(self) -> None:
        """Hide the search input and show the logo if query is empty."""
        inp = self.query_one("#search-input", Input)
        if not inp.value:
            inp.add_class("hidden")
            self.query_one("#logo").remove_class("hidden")

    @property
    def active_statuses(self) -> set[GitStatus]:
        """Return Git statuses matched by the explicitly selected filters."""
        return statuses_for_filter_ids(set(self.selected_filter_ids))

    def toggle_modified(self) -> None:
        """Toggle the 'modified' filter and emit a change event."""
        selected = set(self.selected_filter_ids)
        if "modified" in selected:
            selected.remove("modified")
        else:
            selected.add("modified")
        self.selected_filter_ids = selected
        self.post_message(self.FiltersChanged(self.active_statuses, self.search_query))

    def restore_state(self, filter_ids: set[str], search_query: str) -> None:
        """Restore selected filters and search text from persistent state."""
        self.selected_filter_ids = filter_ids & {"modified"}
        self.search_query = search_query
        inp = self.query_one("#search-input", Input)
        inp.value = search_query
        if search_query:
            inp.remove_class("hidden")
            self.query_one("#logo").add_class("hidden")
        else:
            inp.add_class("hidden")
            self.query_one("#logo").remove_class("hidden")
