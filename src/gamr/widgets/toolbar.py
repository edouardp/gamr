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
                "  🭆🬋🭑 🭆🬋🭑 🬹🬿🭊🬹 🬹🬋🭑 ╷ Git-aware\n"
                + "  █🬇🬹 █🬋█ █🭕🭠█ █🬹🬝 │ Agentic coding assisstant\n"
                + "  🭧🬋🭜 🬎 🬎 🬎  🬎 🬎 🬎 ╵ Monitor & Review tool",
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
