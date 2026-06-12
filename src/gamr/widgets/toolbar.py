"""Toolbar widget — shows logo when idle, search input when filtering."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Static

from gamr.models import GitStatus
from gamr.services.filter import statuses_for_filter_ids


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
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Static(
                " 🬖🬋🬏🬖🬋🬏🬱🬞🬓🬚🬋🬏 Git-aware\n ▌🬋🬓🬛🬋▌▌🬄▌🬛🬚🬀 Agentic coding assistant\n 🬈🬋🬀🬄 🬄🬄 🬄🬄🬁🬃 Monitor & Review",
                id="logo",
            )
            yield Input(placeholder="🔍 Filter files...", id="search-input", classes="hidden")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value
            self.post_message(self.FiltersChanged(self.active_statuses, event.value))
            # Show/hide logo based on whether there's a query
            self.query_one("#logo").set_class(bool(event.value), "hidden")

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
        self.query_one("#search-input", Input).value = search_query
