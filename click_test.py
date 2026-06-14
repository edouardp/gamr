"""Minimal repro: click each row — top rows don't fire in cmux."""

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Static


class ClickableRow(Static):
    ALLOW_SELECT = False

    def on_click(self) -> None:
        self.app.notify(f"Clicked: {self.id}", timeout=3)


class ClickTestApp(App):
    CSS = """
    #rows {
        dock: top;
        height: 5;
    }
    .row {
        height: 1;
        width: 100%;
        padding: 0 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="rows"):
            yield ClickableRow("Row 0 - click me", id="row-0", classes="row")
            yield ClickableRow("Row 1 - click me", id="row-1", classes="row")
            yield ClickableRow("Row 2 - click me", id="row-2", classes="row")
            yield ClickableRow("Row 3 - click me", id="row-3", classes="row")
            yield ClickableRow("Row 4 - click me", id="row-4", classes="row")
        yield Static("Click each row above. A notification should appear.")


if __name__ == "__main__":
    ClickTestApp().run()
