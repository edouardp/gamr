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

    term_program = os.environ.get("TERM_PROGRAM", "").lower()
    # Terminals known to support kitty graphics protocol
    supported = ("ghostty", "kitty", "wezterm")
    return any(name in term_program for name in supported)


def _transmit_logo_image() -> int | None:
    """Transmit the logo PNG via kitty graphics protocol, return image id or None."""
    import base64
    import os
    from pathlib import Path

    if not _supports_kitty_graphics():
        return None

    # Find the logo PNG bundled with the package
    logo_path = Path(__file__).parent.parent / "logo.png"
    if not logo_path.exists():
        return None

    image_id = 9999  # Fixed id for the logo
    png_data = logo_path.read_bytes()
    encoded = base64.standard_b64encode(png_data).decode("ascii")

    # Transmit in chunks of 4096, using quiet mode (q=2) to suppress responses
    # Create a virtual placement for Unicode placeholders (U=1)
    chunks = [encoded[i : i + 4096] for i in range(0, len(encoded), 4096)]

    try:
        fd = os.open("/dev/tty", os.O_WRONLY)
        for idx, chunk in enumerate(chunks):
            is_first = idx == 0
            is_last = idx == len(chunks) - 1
            m = 0 if is_last else 1
            if is_first:
                header = f"\033_Ga=T,f=100,i={image_id},q=2,U=1,c=20,r=3,m={m};"
            else:
                header = f"\033_Gm={m};"
            os.write(fd, (header + chunk + "\033\\").encode())
        os.close(fd)
    except OSError:
        return None

    return image_id


def _make_placeholder(image_id: int, cols: int, rows: int) -> str:
    """Build a Unicode placeholder string for a kitty graphics image."""
    # U+10EEEE is the placeholder character
    # Row/column diacritics: U+0305 = 0, U+030D = 1, U+0310 = 2, etc.
    row_diacritics = [
        "\u0305",
        "\u030d",
        "\u0310",
        "\u0312",
        "\u033d",
        "\u033e",
        "\u033f",
        "\u0346",
        "\u034a",
        "\u034b",
    ]
    col_diacritics = row_diacritics  # Same set for columns

    placeholder = "\U0010eeee"
    lines = []
    for r in range(rows):
        row_d = row_diacritics[r] if r < len(row_diacritics) else row_diacritics[0]
        line_chars = []
        for c in range(cols):
            col_d = col_diacritics[c] if c < len(col_diacritics) else col_diacritics[0]
            line_chars.append(f"{placeholder}{row_d}{col_d}")
        lines.append("".join(line_chars))
    # Wrap with foreground color set to image_id (using 256-color if id < 256, else truecolor)
    if image_id < 256:
        color_start = f"\033[38;5;{image_id}m"
    else:
        r = (image_id >> 16) & 0xFF
        g = (image_id >> 8) & 0xFF
        b = image_id & 0xFF
        color_start = f"\033[38;2;{r};{g};{b}m"
    color_end = "\033[39m"
    return "\n".join(f"{color_start}{line}{color_end}" for line in lines)


# Module-level: attempt to transmit logo on import if supported
_KITTY_LOGO_ID: int | None = None


def _get_logo() -> str:
    """Return the appropriate logo based on terminal capabilities."""
    global _KITTY_LOGO_ID
    if _KITTY_LOGO_ID is None and _supports_kitty_graphics():
        _KITTY_LOGO_ID = _transmit_logo_image()

    if _KITTY_LOGO_ID is not None:
        # Return Unicode placeholder text + taglines
        # The placeholder occupies the left side, taglines on the right
        return _make_placeholder(_KITTY_LOGO_ID, 16, 3)

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
