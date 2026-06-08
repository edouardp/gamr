"""Preview pane widget — syntax-highlighted file view and diff view."""

from __future__ import annotations

from pathlib import Path

from rich.syntax import Syntax
from rich.text import Text
from textual.reactive import reactive
from textual.scroll_view import ScrollView
from textual.widgets import Static


class PreviewPane(Static):
    """Displays file contents with syntax highlighting or a diff view."""

    current_path: reactive[Path | None] = reactive(None)
    show_diff: reactive[bool] = reactive(False)

    DEFAULT_CSS = """
    PreviewPane {
        width: 100%;
        height: 100%;
        overflow-y: auto;
        overflow-x: auto;
    }
    """

    def show_file(self, path: Path) -> None:
        """Display a file with syntax highlighting."""
        self.current_path = path
        try:
            content = path.read_text(errors="replace")
        except OSError:
            self.update("Cannot read file")
            return

        syntax = Syntax(
            content,
            lexer=Syntax.guess_lexer(str(path), content),
            line_numbers=True,
            word_wrap=False,
            theme="monokai",
        )
        self.update(syntax)

    def show_diff_content(self, diff_text: str, filename: str = "") -> None:
        """Display a unified diff with coloured lines."""
        if not diff_text:
            self.update(Text("No changes", style="dim"))
            return

        styled = Text()
        for line in diff_text.splitlines(keepends=True):
            if line.startswith("+++") or line.startswith("---"):
                styled.append(line, style="bold")
            elif line.startswith("@@"):
                styled.append(line, style="cyan")
            elif line.startswith("+"):
                styled.append(line, style="green")
            elif line.startswith("-"):
                styled.append(line, style="red")
            else:
                styled.append(line)

        self.update(styled)

    def clear_preview(self) -> None:
        """Clear the preview pane."""
        self.current_path = None
        self.update("")
