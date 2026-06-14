# Mouse clicks not registering on top terminal rows in cmux

## Description

Mouse click events are not delivered to TUI applications for cells in the first ~1-2 rows of the terminal pane when running inside cmux. The same application works correctly in Ghostty (standalone) with all rows receiving clicks.

## Environment

- cmux (latest as of 2026-06-14)
- macOS (Apple Silicon)
- Textual 8.2.7 (Python TUI framework)
- Also reproducible with any TUI that uses mouse reporting

## Reproduction

Save this as `click_test.py` and run with `python click_test.py` (requires `pip install textual`):

```python
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
```

## Expected behavior

Clicking any row shows a toast notification "Clicked: row-N".

## Actual behavior in cmux

- Row 0: click does **not** register (no notification)
- Row 1: click only registers at the very bottom pixels of the row
- Row 2+: clicks work normally

## Behavior in Ghostty (standalone)

All rows (0–4) register clicks immediately and correctly.

## Behavior in Terminal.app

All rows (0–4) register clicks immediately and correctly.

## Root Cause

**Minimal mode.** When cmux's top toolbar is hidden (minimal mode), the tab bar moves up but the hidden toolbar's hit-test area remains active — it still captures/consumes mouse events in its original pixel region, creating a dead zone at the top of the terminal pane.

The masked area exactly matches the height of the hidden toolbar.

## Workaround

Disable minimal mode (show the toolbar), or avoid placing clickable TUI elements in the top ~1-2 terminal rows.

## Analysis

The clicks are not offset — they are **masked**. Click events simply don't reach the terminal application for a fixed vertical pixel region at the top of the pane.

Key observation: **changing the font size does not change the masked pixel area, but does change how many rows are affected.** With a smaller font, more rows fall within the masked zone; with a larger font, fewer rows are affected. The masked area is a constant number of vertical pixels from the top of the terminal pane.

This confirms an invisible view (the hidden toolbar) still has `userInteractionEnabled` / accepts hit-testing despite being visually hidden. The fix would be to disable hit-testing on the toolbar view when it's in minimal/hidden mode.
