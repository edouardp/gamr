"""Fooey TUI application."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static
from textual.worker import get_current_worker
from textual import work

from fooey.models import FileEntry
from fooey.services.file_index import FileIndex
from fooey.services.file_scanner import FileScanner
from fooey.services.git_provider import DulwichGitProvider, GitStatus, NullGitProvider
from fooey.widgets.file_tree_table import FileTreeTable
from fooey.widgets.filter_bar import FilterBar
from fooey.widgets.preview_pane import PreviewPane


class FooeyApp(App):
    """A git-aware file browser TUI."""

    CSS = """
    #main {
        height: 1fr;
    }
    #left-pane {
        width: 1fr;
        height: 100%;
        border-right: solid $surface-lighten-2;
    }
    #right-pane {
        width: 1fr;
        height: 100%;
    }
    """

    TITLE = "Fooey"

    BINDINGS = [
        Binding("f", "focus_filter", "Filter", show=True),
        Binding("d", "toggle_diff", "Diff toggle", show=True),
        Binding("b", "toggle_blame", "Blame cols", show=True),
        Binding("1", "toggle_col('status')", "Status col", show=False),
        Binding("2", "toggle_col('lines')", "Lines col", show=False),
        Binding("3", "toggle_col('size')", "Size col", show=False),
        Binding("4", "toggle_col('mtime')", "Mtime col", show=False),
        Binding("5", "toggle_col('author')", "Author col", show=False),
        Binding("6", "toggle_col('git_time')", "Git time col", show=False),
        Binding("tab", "switch_pane", "Switch pane", show=True),
        Binding("q", "quit", "Quit", show=True),
    ]

    def __init__(self, path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.target_path = (path or Path.cwd()).resolve()
        self._all_entries: list[FileEntry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield FilterBar()
        with Horizontal(id="main"):
            yield FileTreeTable(id="left-pane")
            yield PreviewPane(id="right-pane")
        yield Footer()

    def on_mount(self) -> None:
        scanner = FileScanner(self.target_path)
        scanner.load_gitignore()
        git = DulwichGitProvider(self.target_path)
        if not git.is_git_repo():
            git = NullGitProvider()
        self._git = git
        self._scanner = scanner
        self._file_index = FileIndex(scanner, git)
        self._all_entries = self._file_index.build()
        tree = self.query_one(FileTreeTable)
        tree.load_entries(self._all_entries, self.target_path)
        # Start watching for live updates
        self._scanner.start_watching()
        self._poll_filesystem()
        # Hide git-related UI if not a git repo
        if not self._git.is_git_repo():
            tree.show_status = False
            tree.show_lines = False
            for btn in self.query(".filter-btn"):
                btn.display = False
        tree.focus()

    @work(thread=True, group="watcher")
    def _poll_filesystem(self) -> None:
        """Background worker that polls the file scanner queue for changes."""
        import time

        worker = get_current_worker()
        while not worker.is_cancelled:
            time.sleep(0.5)
            # If polling fallback, trigger a scan
            self._scanner.poll_changes()
            changes = self._scanner.drain()
            if changes:
                self.call_from_thread(self._handle_file_changes)

    def _handle_file_changes(self) -> None:
        """Rebuild the index and refresh the tree (runs on main thread)."""
        self._all_entries = self._file_index.build()
        tree = self.query_one(FileTreeTable)
        tree.load_entries(self._all_entries, self.target_path)

    def on_file_tree_table_node_highlighted(self, event: FileTreeTable.NodeHighlighted) -> None:
        """Update preview when a row is highlighted."""
        entry = event.entry
        if entry is None:
            return
        if not entry.path.is_file():
            return
        preview = self.query_one(PreviewPane)
        # Show diff if file has git changes, otherwise show file content
        if entry.git_status and self._git.is_git_repo():
            diff = self._git.get_diff(entry.path)
            if diff:
                preview.show_diff_content(diff, entry.name)
                return
        preview.show_file(entry.path)

    def on_filter_bar_filters_changed(self, event: FilterBar.FiltersChanged) -> None:
        """Re-filter the tree based on active status filters."""
        filtered = self._apply_filters(event.active_statuses, event.search_query)
        tree = self.query_one(FileTreeTable)
        tree.load_entries(filtered, self.target_path)

    @work(thread=True, group="blame")
    def _load_blame_data(self) -> None:
        """Background worker to populate blame info for all entries."""
        worker = get_current_worker()
        for path, entry in list(self._file_index.entries.items()):
            if worker.is_cancelled:
                return
            self._file_index.update_blame(path)
        # Refresh tree labels on the main thread
        if not worker.is_cancelled:
            self.call_from_thread(self._refresh_tree_labels)

    def _refresh_tree_labels(self) -> None:
        """Refresh the table after blame data loads."""
        tree = self.query_one(FileTreeTable)
        tree._rebuild_table()

    def action_focus_filter(self) -> None:
        """Focus the search input in the filter bar."""
        self.query_one("#search-input").focus()

    def action_toggle_diff(self) -> None:
        """Toggle between diff and file view for current selection."""
        tree = self.query_one(FileTreeTable)
        if tree.row_count == 0:
            return
        row_key, _ = tree.coordinate_to_cell_key(tree.cursor_coordinate)
        node = tree._row_to_node.get(row_key)
        if node and node.entry and node.entry.path.is_file():
            preview = self.query_one(PreviewPane)
            if preview.show_diff:
                preview.show_diff = False
                preview.show_file(node.entry.path)
            else:
                preview.show_diff = True
                if node.entry.git_status and self._git.is_git_repo():
                    diff = self._git.get_diff(node.entry.path)
                    preview.show_diff_content(diff, node.entry.name)

    def action_toggle_blame(self) -> None:
        """Toggle blame columns and trigger background load."""
        tree = self.query_one(FileTreeTable)
        show = not tree.show_author
        tree.show_author = show
        tree.show_git_time = show
        if show and self._git.is_git_repo():
            self._load_blame_data()

    def action_toggle_col(self, col: str) -> None:
        """Toggle a specific column by name."""
        tree = self.query_one(FileTreeTable)
        attr = f"show_{col}"
        if hasattr(tree, attr):
            setattr(tree, attr, not getattr(tree, attr))

    def action_switch_pane(self) -> None:
        """Switch focus between tree and preview."""
        tree = self.query_one(FileTreeTable)
        preview = self.query_one(PreviewPane)
        if tree.has_focus:
            preview.focus()
        else:
            tree.focus()

    def _apply_filters(
        self, statuses: set[GitStatus], search_query: str
    ) -> list[FileEntry]:
        entries = self._all_entries
        if statuses:
            entries = [e for e in entries if e.git_status in statuses]
        if search_query.strip():
            entries = _fuzzy_filter(entries, search_query.strip())
        return entries


def _fuzzy_filter(entries: list[FileEntry], query: str) -> list[FileEntry]:
    """Filter entries using RapidFuzz partial ratio scoring."""
    from rapidfuzz import fuzz

    scored = []
    for entry in entries:
        # Score against filename and relative path parts
        name_score = fuzz.partial_ratio(query.lower(), entry.name.lower())
        path_score = fuzz.partial_ratio(query.lower(), str(entry.path).lower())
        score = max(name_score, path_score)
        if score >= 50:
            scored.append((score, entry))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [entry for _, entry in scored]


def main() -> None:
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    app = FooeyApp(path=path)
    app.run()


if __name__ == "__main__":
    main()
