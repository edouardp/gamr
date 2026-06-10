"""Gamr TUI application — main entry point and orchestration.

Lifecycle: loads persisted state, initializes services (git, scanner, index),
composes the UI (filter bar, split pane with tree table + preview), starts
the file watcher, and manages background workers for expensive git data.

Data flow on file change:
  watchdog → queue → _poll_filesystem worker → _handle_file_changes (main thread)
  → FileIndex.build() → _apply_filters() → tree.load_entries() → _sync_table()

Data flow on git state change (.git/index, HEAD):
  _GitHandler → GIT_STATE_CHANGED event → same path as above
  → only refreshes preview if previewed file's git_status actually changed

Domain model owns all preview decisions:
  _previewed_path        — which file is shown (prevents spurious switches)
  _previewed_git_status  — last-rendered git status (prevents unnecessary re-renders)
  _scroll_positions      — per-file source line cache (persists across file switches)
  restore_line           — passed atomically through show methods (no post-render scroll)
"""

from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Footer, Header
from textual.worker import get_current_worker

from gamr.commands import GamrCommands
from gamr.config import TIMESTAMP_REFRESH_INTERVAL, WATCHER_POLL_INTERVAL
from gamr.models import DiffMode, FileEntry, GitStatus
from gamr.services.file_index import FileIndex
from gamr.services.file_scanner import FileScanner
from gamr.services.filter import filter_by_status, fuzzy_filter
from gamr.services.git_provider import DulwichGitProvider, NullGitProvider
from gamr.state import AppState
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.filter_bar import FilterBar
from gamr.widgets.preview_pane import PreviewPane
from gamr.widgets.split import HorizontalSplit, SplitHandle


class GamrApp(App):
    """A git-aware file browser TUI."""

    COMMANDS = App.COMMANDS | {GamrCommands}
    CSS_PATH = "gamr.tcss"
    TITLE = "Gamr"

    # All bindings use priority=True so they work regardless of which widget has focus.
    # See docs/UI_DESIGN.md for the full interaction specification.
    BINDINGS = [
        # Navigation & focus
        Binding("tab", "switch_pane", "Switch pane", show=True, priority=True),
        Binding("ctrl+f", "focus_filter", "Filter", show=True, priority=True),
        # Modes
        Binding("f", "toggle_follow", "Follow", show=True, priority=True),
        Binding("v", "cycle_view", "View mode", show=True, priority=True),
        Binding("d", "toggle_diff", "Diff toggle", show=True, priority=True),
        Binding("D", "toggle_diff_reverse", show=False, priority=True),
        # Columns
        Binding("b", "toggle_blame", "Blame cols", show=True, priority=True),
        Binding("1", "toggle_col('status')", "Status col", show=False, priority=True),
        Binding("2", "toggle_col('lines')", "Lines col", show=False, priority=True),
        Binding("3", "toggle_col('size')", "Size col", show=False, priority=True),
        Binding("4", "toggle_col('mtime')", "Mtime col", show=False, priority=True),
        Binding("5", "toggle_col('author')", "Author col", show=False, priority=True),
        Binding("6", "toggle_col('git_time')", "Git time col", show=False, priority=True),
        # Filters
        Binding("g", "toggle_modified", "Git modified", show=True, priority=True),
        # App lifecycle
        Binding("q", "quit", "Quit", show=True, priority=True),
    ]

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def __init__(self, path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.target_path = (path or Path.cwd()).resolve()
        self._all_entries: list[FileEntry] = []
        # Load persisted state from ~/.config/gamr/state.json
        self._state = AppState.load(self.target_path)
        self._diff_mode: DiffMode = self._state.diff_mode
        self._follow_mode: bool = False
        self._previewed_path: Path | None = None
        self._previewed_git_status = None
        self._scroll_positions: dict[Path, int] = {}  # path → source line

    def compose(self) -> ComposeResult:
        yield Header()
        yield FilterBar()
        with HorizontalSplit(id="main"):
            yield FileTreeTable(id="left-pane")
            yield SplitHandle()
            yield PreviewPane(id="right-pane")
        yield Footer()

    def on_mount(self) -> None:
        # --- Initialize services ---
        git = DulwichGitProvider(self.target_path)
        if not git.is_git_repo():
            git = NullGitProvider()
        scanner = FileScanner(self.target_path, ignore_filter=git.get_ignore_filter())
        self._git = git
        self._scanner = scanner
        self._file_index = FileIndex(scanner, git)
        self._all_entries = self._file_index.build()

        # --- Restore widget state from persisted session ---
        tree = self.query_one(FileTreeTable)
        self._update_global_mtime_range(tree)
        filter_bar = self.query_one(FilterBar)
        split = self.query_one(HorizontalSplit)
        self._state.apply_to_widgets(tree, filter_bar, split)
        filtered = self._apply_filters(filter_bar.active_statuses, filter_bar.search_query)
        tree.load_entries(
            filtered,
            self.target_path,
            collapsed_dirs=self._state.collapsed_dirs,
        )
        if self._state.selected_path:
            tree.restore_cursor(Path(self._state.selected_path))

        # --- Start background services ---
        self._scanner.start_watching(git_root=self._git.git_dir if self._git.is_git_repo() else None)
        self._poll_filesystem()

        # --- Git-specific UI adjustments ---
        if not self._git.is_git_repo():
            tree.show_status = False
            tree.show_lines = False
        else:
            self._load_diff_stats()

        tree.focus()
        self.set_interval(TIMESTAMP_REFRESH_INTERVAL, self._refresh_timestamps)

    def on_unmount(self) -> None:
        """Release native filesystem watcher resources during every shutdown path."""
        scanner = getattr(self, "_scanner", None)
        if scanner is not None:
            scanner.stop()

    def watch_theme(self, theme: str) -> None:
        """Switch syntax highlight theme when Textual theme changes."""
        try:
            is_dark = self.current_theme.dark if self.current_theme else True
        except Exception:
            is_dark = True
        preview = self.query_one(PreviewPane)
        preview.syntax_theme = "monokai" if is_dark else "default"
        # Re-render current preview with new theme
        if self._previewed_path:
            entry = self._file_index.entries.get(self._previewed_path)
            if entry and self._is_previewable(entry):
                preview.invalidate()
                source_line = preview.get_source_line_at_scroll()
                self._show_preview_for(entry, scroll_to_top=False, restore_line=source_line)

    # -------------------------------------------------------------------------
    # File watching and live updates
    # -------------------------------------------------------------------------

    @work(thread=True, group="watcher")
    def _poll_filesystem(self) -> None:
        """Long-running thread worker: drains file change events from the scanner queue."""
        import time

        from gamr.services.file_scanner import ChangeType

        worker = get_current_worker()
        while not worker.is_cancelled:
            time.sleep(WATCHER_POLL_INTERVAL)
            self._scanner.poll_changes()
            changes = self._scanner.drain()
            if changes:
                git_changed = any(c.change_type == ChangeType.GIT_STATE_CHANGED for c in changes)
                changed_paths = [c.path for c in changes if c.change_type != ChangeType.GIT_STATE_CHANGED]
                self.call_from_thread(self._handle_file_changes, changed_paths, git_changed)

    def _handle_file_changes(self, changed_paths: list[Path] | None = None, git_changed: bool = False) -> None:
        """Respond to filesystem changes: rebuild index, re-filter, sync table."""
        tree = self.query_one(FileTreeTable)
        collapsed = tree.get_collapsed_dirs()

        # Auto-expand parents of changed files so they're always visible
        if changed_paths:
            for path in changed_paths:
                parent = path.parent
                while parent != self.target_path:
                    try:
                        collapsed.discard(str(parent.relative_to(self.target_path)))
                    except ValueError:
                        break
                    parent = parent.parent

        # Cancel background workers that reference old entries before rebuilding
        self.workers.cancel_group(self, "diff_stats")
        self.workers.cancel_group(self, "blame")

        # Rebuild index (picks up new git statuses, file additions/deletions)
        self._all_entries = self._file_index.build()
        self._update_global_mtime_range(tree)

        # Re-apply filters and sync the table (incremental — only changed rows update)
        filter_bar = self.query_one(FilterBar)
        filtered = self._apply_filters(filter_bar.active_statuses, filter_bar.search_query)
        tree.load_entries(filtered, self.target_path, collapsed_dirs=collapsed)

        # Update preview if the currently previewed file's content or git status changed
        if self._previewed_path:
            file_content_changed = changed_paths and self._previewed_path in set(changed_paths)
            entry = self._file_index.entries.get(self._previewed_path)
            # On git state change, only refresh if this file's status actually differs
            git_status_changed = False
            if git_changed and entry:
                old_status = getattr(self, "_previewed_git_status", None)
                if entry.git_status != old_status:
                    git_status_changed = True
            if (file_content_changed or git_status_changed) and entry and self._is_previewable(entry):
                preview = self.query_one(PreviewPane)
                source_line = preview.get_source_line_at_scroll()
                preview.invalidate()
                self._show_preview_for(entry, scroll_to_top=False, restore_line=source_line)
            if entry:
                self._previewed_git_status = entry.git_status

        # Follow mode: jump to the last changed file
        if self._follow_mode and changed_paths:
            follow_path = changed_paths[-1]
            tree.restore_cursor(follow_path)
            self._previewed_path = follow_path
            self._show_followed_path(follow_path)

        # Re-trigger background workers (only when git state changed or files modified)
        if self._git.is_git_repo() and (git_changed or changed_paths):
            self._load_diff_stats()
            if tree.show_author or tree.show_git_time:
                self._load_blame_data()

    # -------------------------------------------------------------------------
    # Preview pane management
    # -------------------------------------------------------------------------

    def on_file_tree_table_node_highlighted(self, event: FileTreeTable.NodeHighlighted) -> None:
        """Domain decision: only update preview when user navigates to a new file."""
        entry = event.entry
        if entry is None or not self._is_previewable(entry):
            return
        if entry.path == self._previewed_path:
            return
        # Save scroll position of the file we're leaving
        try:
            preview = self.query_one(PreviewPane)
            if self._previewed_path:
                self._scroll_positions[self._previewed_path] = preview.get_source_line_at_scroll()
        except NoMatches:
            pass
        self._previewed_path = entry.path
        self._previewed_git_status = entry.git_status
        try:
            saved = self._scroll_positions.get(entry.path, 0)
            self._show_preview_for(entry, restore_line=saved)
        except NoMatches:
            pass  # Preview pane may not be mounted yet during startup

    def _show_preview_for(self, entry: FileEntry, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Render file content or diff in the preview pane based on current diff mode."""
        preview = self.query_one(PreviewPane)
        preview.show_diff = self._diff_mode
        is_diffable = entry.git_status and self._git.is_git_repo()

        if is_diffable and self._diff_mode == DiffMode.UNIFIED:
            diff = self._git.get_diff(entry.path)
            if diff:
                preview.show_diff_content(diff, path=entry.path, scroll_to_top=scroll_to_top, restore_line=restore_line)
                return
        elif is_diffable and self._diff_mode == DiffMode.FULL:
            diff = self._git.get_diff(entry.path)
            if diff:
                preview.show_full_diff(entry.path, diff, scroll_to_top=scroll_to_top, restore_line=restore_line)
                return
        elif is_diffable and self._diff_mode == DiffMode.GUTTER:
            diff = self._git.get_diff(entry.path)
            if diff:
                preview.show_gutter_diff(entry.path, diff, scroll_to_top=scroll_to_top, restore_line=restore_line)
                return

        preview.show_file(entry.path, scroll_to_top=scroll_to_top, restore_line=restore_line)

    @staticmethod
    def _is_previewable(entry: FileEntry) -> bool:
        """Return whether an entry has file contents or a deletion diff to show."""
        return entry.path.is_file() or entry.git_status in {
            GitStatus.DELETED,
            GitStatus.STAGED_DELETED,
        }

    def _show_followed_path(self, path: Path) -> None:
        """Force preview update for a followed file; scroll to first diff hunk."""
        import re

        entry = self._file_index.entries.get(path)
        if not entry or not self._is_previewable(entry):
            return

        # Scroll to the first diff hunk if the file is git-modified
        restore_line = 0
        if entry.git_status and self._git.is_git_repo():
            diff = self._git.get_diff(path)
            if diff:
                m = re.search(r"@@ [^+]*\+(\d+)", diff)
                if m:
                    restore_line = int(m.group(1))

        preview = self.query_one(PreviewPane)
        preview.invalidate()
        self._show_preview_for(entry, restore_line=restore_line)

    # -------------------------------------------------------------------------
    # Background data workers
    # -------------------------------------------------------------------------

    @work(thread=True, group="blame")
    def _load_blame_data(self) -> None:
        """Populate last_author and last_git_modified for all entries (expensive)."""
        worker = get_current_worker()
        for path, _entry in list(self._file_index.entries.items()):
            if worker.is_cancelled:
                return
            self._file_index.update_blame(path)
        if not worker.is_cancelled:
            self.call_from_thread(self._refresh_tree_labels)

    @work(thread=True, group="diff_stats")
    def _load_diff_stats(self) -> None:
        """Populate lines_added/removed for modified files."""
        worker = get_current_worker()
        for path, entry in list(self._file_index.entries.items()):
            if worker.is_cancelled:
                return
            if entry.git_status:
                self._file_index.update_diff_stats(path)
        if not worker.is_cancelled:
            self.call_from_thread(self._refresh_tree_labels)

    def _refresh_tree_labels(self) -> None:
        """Refresh tree data after a background worker completes."""
        self.query_one(FileTreeTable).refresh_data()

    def _refresh_timestamps(self) -> None:
        """Called every 10s to update relative time displays in-place."""
        tree = self.query_one(FileTreeTable)
        if tree.show_mtime or tree.show_git_time:
            tree.refresh_time_cells()

    # -------------------------------------------------------------------------
    # Filter logic
    # -------------------------------------------------------------------------

    def on_filter_bar_filters_changed(self, event: FilterBar.FiltersChanged) -> None:
        """Re-filter and reload tree when filter buttons or search text change."""
        # Debounce: cancel pending filter and schedule a new one
        if hasattr(self, "_filter_timer") and self._filter_timer:
            self._filter_timer.stop()
        self._pending_filter = (event.active_statuses, event.search_query)
        self._filter_timer = self.set_timer(0.15, self._apply_pending_filter)

    def _apply_pending_filter(self) -> None:
        """Apply the debounced filter after 150ms of inactivity."""
        if not hasattr(self, "_pending_filter"):
            return
        statuses, query = self._pending_filter
        tree = self.query_one(FileTreeTable)
        collapsed = tree.get_collapsed_dirs()
        filtered = self._apply_filters(statuses, query)

        # Skip rebuild if result set hasn't changed
        new_paths = {e.path for e in filtered}
        if hasattr(self, "_last_filtered_paths") and new_paths == self._last_filtered_paths:
            return
        self._last_filtered_paths = new_paths

        tree.load_entries(filtered, self.target_path, collapsed_dirs=collapsed)

    def _update_global_mtime_range(self, tree: FileTreeTable) -> None:
        """Set the global mtime range from all entries (stable across filters)."""
        mtimes = [e.mtime for e in self._all_entries if e.mtime > 0]
        if mtimes:
            tree.set_global_mtime_range(min(mtimes), max(mtimes))

    def _apply_filters(self, statuses: set[GitStatus], search_query: str) -> list[FileEntry]:
        """Apply git status filter then fuzzy search to the full entry list."""
        entries = filter_by_status(self._all_entries, statuses)
        if search_query.strip():
            entries = fuzzy_filter(entries, search_query.strip())
        return entries

    # -------------------------------------------------------------------------
    # Keybinding actions
    # -------------------------------------------------------------------------

    def action_focus_filter(self) -> None:
        self.query_one("#search-input").focus()

    def action_toggle_follow(self) -> None:
        """Toggle follow mode — auto-select last changed file on watch events."""
        self._follow_mode = not self._follow_mode
        self.notify(f"Follow mode: {'ON' if self._follow_mode else 'OFF'}")

    def action_toggle_diff(self) -> None:
        self._cycle_diff_mode(1)

    def action_toggle_diff_reverse(self) -> None:
        self._cycle_diff_mode(-1)

    def _cycle_diff_mode(self, direction: int) -> None:
        """Cycle through diff modes, preserving scroll position by source line."""
        modes = list(DiffMode)
        idx = modes.index(self._diff_mode)
        self._diff_mode = modes[(idx + direction) % len(modes)]
        tree = self.query_one(FileTreeTable)
        entry = tree.get_current_entry()
        if entry and self._is_previewable(entry):
            preview = self.query_one(PreviewPane)
            source_line = preview.get_source_line_at_scroll()
            preview.invalidate()
            self._show_preview_for(entry, scroll_to_top=False, restore_line=source_line)

    def action_toggle_blame(self) -> None:
        """Toggle blame columns (author + git time) and load data if needed."""
        tree = self.query_one(FileTreeTable)
        show = not tree.show_author
        tree.show_author = show
        tree.show_git_time = show
        if show and self._git.is_git_repo():
            self._load_blame_data()

    def action_toggle_col(self, col: str) -> None:
        """Toggle a column by its reactive attribute name (e.g. 'size', 'mtime')."""
        tree = self.query_one(FileTreeTable)
        attr = f"show_{col}"
        if hasattr(tree, attr):
            setattr(tree, attr, not getattr(tree, attr))

    def action_switch_pane(self) -> None:
        """Move focus between the file tree and the preview pane."""
        tree = self.query_one(FileTreeTable)
        preview = self.query_one(PreviewPane)
        (preview if tree.has_focus else tree).focus()

    def action_cycle_view(self) -> None:
        self.query_one(FileTreeTable).action_cycle_view()

    def action_toggle_modified(self) -> None:
        self.query_one(FilterBar).toggle_modified()

    # -------------------------------------------------------------------------
    # State persistence
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        """Capture all app state from live widgets and persist to disk."""
        tree = self.query_one(FileTreeTable)
        split = self.query_one(HorizontalSplit)
        filter_bar = self.query_one(FilterBar)
        entry = tree.get_current_entry()

        self._state.capture_from_widgets(
            tree,
            filter_bar,
            split,
            diff_mode=self._diff_mode,
            selected_path=entry.path if entry else None,
        )
        self._state.save()

    def action_quit(self) -> None:
        """Save state and exit."""
        self._save_state()
        self.exit()


def main() -> None:
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    GamrApp(path=path).run()


if __name__ == "__main__":
    main()
