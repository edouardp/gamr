"""FilterBar widget for git status filtering and fuzzy search."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input

from gamr.models import GitStatus
from gamr.services.filter import (
    STATUS_FILTERS,
    STATUS_FILTERS_BY_ID,
    statuses_for_filter_ids,
)


class FilterBar(Widget):
    """Horizontal bar with git status filter toggles."""

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
    FilterBar Button {
        min-width: 5;
        margin: 0 1;
    }
    FilterBar Button.active {
        background: $accent;
    }
    FilterBar Input {
        width: 1fr;
    }
    """

    def compose(self) -> ComposeResult:
        with Horizontal():
            for sf in STATUS_FILTERS:
                yield Button(
                    sf.label,
                    id=f"filter-{sf.id}",
                    classes="filter-btn",
                )
            yield Input(placeholder="🔍 Filter files...", id="search-input")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button
        if "filter-btn" not in btn.classes:
            return

        filter_id = btn.id.replace("filter-", "")
        selected = set(self.selected_filter_ids)
        if filter_id in selected:
            selected.remove(filter_id)
        else:
            selected.add(filter_id)

        self.selected_filter_ids = selected
        self.sync_button_classes()
        self.post_message(self.FiltersChanged(self.active_statuses, self.search_query))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value
            self.post_message(self.FiltersChanged(self.active_statuses, event.value))

    @property
    def active_statuses(self) -> set[GitStatus]:
        """Return Git statuses matched by the explicitly selected filters."""
        return statuses_for_filter_ids(set(self.selected_filter_ids))

    def sync_button_classes(self) -> None:
        """Update button styling from the explicitly selected filter IDs."""
        selected = set(self.selected_filter_ids)
        for status_filter in STATUS_FILTERS:
            button = self.query_one(f"#filter-{status_filter.id}", Button)
            button.set_class(status_filter.id in selected, "active")

    def restore_state(self, filter_ids: set[str], search_query: str) -> None:
        """Restore selected filters and search text from persistent state."""
        self.selected_filter_ids = filter_ids.intersection(STATUS_FILTERS_BY_ID)
        self.sync_button_classes()
        self.search_query = search_query
        self.query_one("#search-input", Input).value = search_query
