"""FilterBar widget for git status filtering and fuzzy search."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input

from gamr.models import GitStatus
from gamr.services.filter import statuses_for_filter_ids


class FilterBar(Widget):
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
    FilterBar {
        height: 3;
        dock: top;
        layout: horizontal;
    }
    FilterBar Horizontal {
        height: 3;
        width: 100%;
    }
    FilterBar Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Input(placeholder="🔍 Filter files...", id="search-input")

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value
            self.post_message(self.FiltersChanged(self.active_statuses, event.value))

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
