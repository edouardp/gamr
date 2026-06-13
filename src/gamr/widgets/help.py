"""Help popup showing keyboard shortcuts."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

HELP_TEXT = """\
[bold]Navigation[/]
  [cyan]↑/↓  j/k[/]       Navigate files
  [cyan]→[/]              Expand directory
  [cyan]←[/]              Collapse directory / go to parent
  [cyan]space[/]          Toggle expand (tree) / page down (preview)
  [cyan]tab[/]            Switch focus between tree and preview

[bold]View & Diff[/]
  [cyan]v[/]              Cycle view mode (tree → flat name → flat path)
  [cyan]d / D[/]          Cycle diff mode forward / reverse
  [cyan]s[/]              Side-by-side diff popup
  [cyan]o[/]              Cycle diff overview style
  [cyan]g[/]              Toggle git modified filter
  [cyan]f[/]              Toggle follow mode

[bold]Preview[/]
  [cyan]j/k  ↑/↓[/]       Scroll (when preview focused)
  [cyan]space[/]          Page down
  [cyan]J / n[/]          Jump to next diff hunk
  [cyan]K / N[/]          Jump to previous diff hunk
  [cyan]e[/]              Open in $EDITOR
  [cyan]O[/]              Open in default app (macOS)

[bold]Columns[/]
  [cyan]b[/]              Toggle blame columns
  [cyan]1–7[/]            Toggle individual columns

[bold]Other[/]
  [cyan]/[/]              Focus search input
  [cyan]ctrl+p[/]         Command palette
  [cyan]?[/]              This help
  [cyan]q[/]              Quit
"""


class HelpScreen(ModalScreen[None]):
    """Modal showing keyboard shortcuts."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    #help-container {
        width: auto;
        height: auto;
        background: #1e1e1e;
        border: thick #444444;
    }
    #help-header {
        height: 1;
        background: $surface-lighten-2;
        color: $text;
        padding: 0 2;
    }
    #help-content {
        background: #1e1e1e;
        padding: 1 3;
        width: auto;
        height: auto;
    }
    """

    def on_key(self, event) -> None:
        key = event.key
        if key in ("escape", "question_mark", "?"):
            event.stop()
            event.prevent_default()
            self.dismiss()
        else:
            event.stop()

    def compose(self) -> ComposeResult:
        with Vertical(id="help-container"):
            yield Static(" Keyboard Shortcuts (? or esc to close)", id="help-header")
            yield Static(HELP_TEXT, id="help-content")
