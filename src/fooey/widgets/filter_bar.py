"""FilterBar widget for git status filtering and fuzzy search."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input

from fooey.services.git_provider import GitStatus

_FILTER_BUTTONS = [
    ("M", GitStatus.MODIFIED, "yellow", "modified"),
    ("A", GitStatus.ADDED, "green", "added"),
    ("D", GitStatus.DELETED, "red", "deleted"),
    ("?", GitStatus.UNTRACKED, "white", "untracked"),
    ("S", GitStatus.STAGED_MODIFIED, "cyan", "staged"),
]


class FilterBar(Widget):
    """Horizontal bar with git status filter toggles."""

    class FiltersChanged(Message):
        """Sent when active filters change."""

        def __init__(self, active_statuses: set[GitStatus], search_query: str) -> None:
            super().__init__()
            self.active_statuses = active_statuses
            self.search_query = search_query

    active_statuses: reactive[set[GitStatus]] = reactive(set, always_update=True)
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
            for label, status, _color, id_name in _FILTER_BUTTONS:
                yield Button(label, id=f"filter-{id_name}", classes="filter-btn")
            yield Input(placeholder="🔍 Filter files...", id="search-input")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        btn = event.button
        if "filter-btn" not in btn.classes:
            return

        # Toggle active state
        id_name = btn.id.replace("filter-", "")
        status = next(s for _, s, _, n in _FILTER_BUTTONS if n == id_name)

        current = set(self.active_statuses)
        if status in current:
            current.discard(status)
            btn.remove_class("active")
        else:
            current.add(status)
            btn.add_class("active")

        self.active_statuses = current
        self.post_message(self.FiltersChanged(current, self.search_query))

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self.search_query = event.value
            self.post_message(self.FiltersChanged(set(self.active_statuses), event.value))
