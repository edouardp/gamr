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

import os
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
from gamr.preferences import Preferences
from gamr.services.file_index import FileIndex
from gamr.services.file_scanner import FileScanner
from gamr.services.filter import filter_by_status, fuzzy_filter
from gamr.services.git_provider import DulwichGitProvider, NullGitProvider
from gamr.state import AppState
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.help import HelpScreen
from gamr.widgets.preview_pane import DiffOverview, PreviewPane
from gamr.widgets.side_by_side import SideBySideDiffScreen
from gamr.widgets.split import HorizontalSplit, SplitHandle
from gamr.widgets.toolbar import Toolbar


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
        Binding("/", "focus_filter", "Filter", show=True, priority=True),
        # Modes
        Binding("f", "toggle_follow", "Follow", show=True, priority=True),
        Binding("v", "cycle_view", "View mode", show=True, priority=True),
        Binding("V", "cycle_view_reverse", show=False, priority=True),
        Binding("d", "toggle_diff", "Diff mode", show=True, priority=True),
        Binding("D", "toggle_diff_reverse", show=False, priority=True),
        # Columns
        Binding("b", "toggle_blame", "Blame cols", show=False, priority=True),
        Binding("1", "toggle_col('status')", "Status col", show=False, priority=True),
        Binding("2", "toggle_col('lines')", "Lines col", show=False, priority=True),
        Binding("3", "toggle_col('size')", "Size col", show=False, priority=True),
        Binding("4", "toggle_col('rows')", "Lines col", show=False, priority=True),
        Binding("5", "toggle_col('mtime')", "Mtime col", show=False, priority=True),
        Binding("6", "toggle_col('author')", "Author col", show=False, priority=True),
        Binding("7", "toggle_col('git_time')", "Git time col", show=False, priority=True),
        # Filters
        Binding("g", "toggle_modified", "Git modified", show=True, priority=True),
        Binding("o", "cycle_overview", "Overview mode", show=True, priority=True),
        Binding("s", "side_by_side", "Side-by-side", show=True, priority=True),
        Binding("e", "open_editor", "Editor", show=True, priority=True),
        Binding("O", "open_macos", show=False, priority=True),
        Binding("escape", "unfocus_filter", show=False, priority=True),
        # App lifecycle
        Binding("q", "quit", "Quit", show=True, priority=True),
        Binding("question_mark", "show_help", "Help", show=False, priority=True),
    ]

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def __init__(self, path: Path | None = None, **kwargs) -> None:
        super().__init__(**kwargs)
        self.target_path = (path or Path.cwd()).resolve()
        self._all_entries: list[FileEntry] = []
        self._prefs = Preferences.load()
        # Load persisted state from ~/.config/gamr/state.json
        self._state = AppState.load(self.target_path)
        self._diff_mode: DiffMode = self._state.diff_mode
        self._follow_mode: bool = False
        self._previewed_path: Path | None = None
        self._previewed_git_status = None
        self._scroll_positions: dict[Path, int] = {}  # path → source line

    def compose(self) -> ComposeResult:
        yield Header()
        yield Toolbar()
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
        toolbar = self.query_one(Toolbar)
        split = self.query_one(HorizontalSplit)
        self._state.apply_to_widgets(tree, toolbar, split)
        self.query_one(PreviewPane).query_one(DiffOverview).use_braille = self._state.use_braille
        self.query_one(PreviewPane).query_one(DiffOverview).use_quadrant = self._state.use_quadrant
        self.query_one(PreviewPane).query_one(DiffOverview).use_sextant = self._state.use_sextant
        filtered = self._apply_filters(toolbar.active_statuses, toolbar.search_query)
        tree.load_entries(
            filtered,
            self.target_path,
            collapsed_dirs=self._state.collapsed_dirs,
        )
        if self._state.selected_path:
            tree.restore_cursor(Path(self._state.selected_path))
            if self._state.scroll_line > 1:
                self._scroll_positions[Path(self._state.selected_path)] = self._state.scroll_line

        # --- Start background services ---
        self._scanner.start_watching(git_root=self._git.git_dir if self._git.is_git_repo() else None)
        self._poll_filesystem()

        # --- Git-specific UI adjustments ---
        if not self._git.is_git_repo():
            tree.show_status = False
            tree.show_lines = False
        else:
            self._load_diff_stats()
            if tree.show_author or tree.show_git_time:
                self._load_blame_data()

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
        if git_changed:
            self.workers.cancel_group(self, "blame")
            # Invalidate blame cache for changed files so they get re-blamed
            if changed_paths:
                for path in changed_paths:
                    self._file_index._blame_cache.pop(path, None)
            else:
                # Full git state change (e.g. branch switch) — clear all
                self._file_index._blame_cache.clear()

        self._rebuild_and_reload_tree(tree, collapsed)
        # Restore cursor to the currently previewed file
        if self._previewed_path:
            tree.restore_cursor(self._previewed_path)
        if self._follow_mode and changed_paths:
            # Follow mode handles preview — skip normal refresh to avoid restoring old scroll
            pass
        else:
            self._refresh_preview_if_needed(changed_paths, git_changed)
        self._handle_follow_mode(changed_paths, tree)
        self._restart_background_workers(tree, changed_paths, git_changed)

    def _rebuild_and_reload_tree(self, tree: FileTreeTable, collapsed: set[str]) -> None:
        """Rebuild the file index and reload the tree with current filters."""
        self._all_entries = self._file_index.build()
        self._update_global_mtime_range(tree)
        toolbar = self.query_one(Toolbar)
        filtered = self._apply_filters(toolbar.active_statuses, toolbar.search_query)
        tree.load_entries(filtered, self.target_path, collapsed_dirs=collapsed)

    def _refresh_preview_if_needed(self, changed_paths: list[Path] | None, git_changed: bool) -> None:
        """Re-render preview if the previewed file's content or git status changed."""
        if not self._previewed_path:
            return
        entry = self._file_index.entries.get(self._previewed_path)
        file_content_changed = changed_paths and self._previewed_path in set(changed_paths)
        git_status_changed = git_changed and entry and entry.git_status != self._previewed_git_status
        if (file_content_changed or git_status_changed) and entry and self._is_previewable(entry):
            preview = self.query_one(PreviewPane)
            source_line = preview.get_source_line_at_scroll()
            preview.invalidate()
            self._show_preview_for(entry, scroll_to_top=False, restore_line=source_line)
            # Refresh side-by-side modal if open
            if self._has_modal():
                self._refresh_side_by_side(entry)
        if entry:
            self._previewed_git_status = entry.git_status

    def _refresh_side_by_side(self, entry: FileEntry) -> None:
        """Refresh the side-by-side modal with updated file content."""
        screen = self.screen
        if not isinstance(screen, SideBySideDiffScreen):
            return
        diff = self._git.get_diff(entry.path)
        if not diff:
            screen.dismiss()
            return
        old_content = self._git.get_old_content(entry.path)
        try:
            new_content = entry.path.read_text(errors="replace")
        except OSError:
            new_content = ""
        screen.refresh_content(diff, old_content, new_content)

    def _handle_follow_mode(self, changed_paths: list[Path] | None, tree: FileTreeTable) -> None:
        """In follow mode, jump cursor to the last changed file."""
        if not self._follow_mode or not changed_paths:
            return
        follow_path = changed_paths[-1]
        tree.restore_cursor(follow_path)
        self._previewed_path = follow_path
        self._show_followed_path(follow_path)

    def _restart_background_workers(
        self, tree: FileTreeTable, changed_paths: list[Path] | None, git_changed: bool
    ) -> None:
        """Re-trigger diff stats and blame workers after changes."""
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
        # For files > 50KB, render in background to avoid blocking the UI
        try:
            size = entry.path.stat().st_size if entry.path.exists() else 0
        except OSError:
            size = 0
        if size > 50 * 1024:
            preview = self.query_one(PreviewPane)
            preview.current_path = entry.path
            preview.show_diff = self._diff_mode
            preview.update_header()
            preview.loading = True
            self._render_preview_async(entry, scroll_to_top=scroll_to_top, restore_line=restore_line)
            return
        self._render_preview_sync(entry, scroll_to_top=scroll_to_top, restore_line=restore_line)

    @work(thread=True, group="preview", exclusive=True)
    def _render_preview_async(self, entry: FileEntry, *, scroll_to_top: bool, restore_line: int) -> None:
        """Heavy preview work in background: file read, diff calc, syntax highlight."""
        worker = get_current_worker()
        path = entry.path

        # Pre-read file in background to check binary/errors before main-thread render
        try:
            raw = path.read_bytes() if path.exists() else b""
        except OSError:
            if not worker.is_cancelled:
                self.call_from_thread(self._apply_preview_error, path, "Cannot read file")
            return

        if worker.is_cancelled:
            return

        if raw and b"\x00" in raw[:8192]:
            if not worker.is_cancelled:
                self.call_from_thread(self._apply_preview_error, path, path.name)
            return

        # Pre-compute diff in background (Dulwich is thread-safe)
        is_diffable = entry.git_status and self._git.is_git_repo()
        if is_diffable:
            self._git.get_diff(entry.path)  # warms cache

        if worker.is_cancelled:
            return

        # Syntax highlighting (CPU-bound, the main bottleneck)
        # Skip for files >100KB is handled in _render_highlighted

        # Apply on main thread
        def _apply():
            if worker.is_cancelled or self._previewed_path != path:
                return
            preview = self.query_one(PreviewPane)
            preview.loading = False
            preview.invalidate()
            self._render_preview_sync(entry, scroll_to_top=scroll_to_top, restore_line=restore_line)

        self.call_from_thread(_apply)

    def _apply_preview_error(self, path: Path, message: str) -> None:
        """Show an error/info message in preview if the path is still current."""
        if self._previewed_path != path:
            return
        preview = self.query_one(PreviewPane)
        preview.loading = False
        preview.show_message(message)

    def _render_preview_sync(self, entry: FileEntry, *, scroll_to_top: bool = True, restore_line: int = 0) -> None:
        """Render file content or diff in the preview pane based on current diff mode."""
        preview = self.query_one(PreviewPane)
        preview.loading = False
        preview.show_diff = self._diff_mode
        is_diffable = entry.git_status and self._git.is_git_repo()
        diff = self._git.get_diff(entry.path) if is_diffable else ""
        kwargs = {"scroll_to_top": scroll_to_top, "restore_line": restore_line}

        if diff:
            dispatch = {
                DiffMode.UNIFIED: lambda: preview.show_diff_content(diff, path=entry.path, **kwargs),
                DiffMode.FULL: lambda: preview.show_full_diff(entry.path, diff, **kwargs),
                DiffMode.GUTTER: lambda: preview.show_gutter_diff(entry.path, diff, **kwargs),
            }
            dispatch[self._diff_mode]()
            return

        preview.show_file(entry.path, **kwargs)

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
        """Populate last_author and last_git_modified for entries missing blame."""
        worker = get_current_worker()
        # Collect files that need blame
        paths_needed = [path for path, entry in self._file_index.entries.items() if entry.last_author is None]
        if not paths_needed:
            return

        # Bulk walk: single log traversal for all files
        results = self._git.get_bulk_blame(paths_needed)
        if worker.is_cancelled:
            return

        # Apply results to entries and cache
        for path, info in results.items():
            entry = self._file_index.entries.get(path)
            if entry:
                entry.last_author = info.last_author
                entry.last_git_modified = info.last_modified
                self._file_index._blame_cache[path] = info

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
        """Refresh tree cell content after a background worker completes."""
        self.query_one(FileTreeTable).refresh_cells()

    def _refresh_timestamps(self) -> None:
        """Called every 10s to update relative time displays in-place."""
        tree = self.query_one(FileTreeTable)
        if tree.show_mtime or tree.show_git_time:
            tree.refresh_time_cells()

    # -------------------------------------------------------------------------
    # Filter logic
    # -------------------------------------------------------------------------

    def on_toolbar_filters_changed(self, event: Toolbar.FiltersChanged) -> None:
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
        self.query_one(Toolbar).show_search()

    def action_unfocus_filter(self) -> None:
        """Return focus to tree when escape pressed, or dismiss modal."""
        if self._has_modal():
            self._dismiss_modal()
            return
        if self.query_one("#search-input").has_focus:
            self.query_one(Toolbar).hide_search()
            self.query_one(FileTreeTable).focus()

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
        modes = self._prefs.diff_modes
        old_mode = self._diff_mode
        try:
            idx = modes.index(old_mode)
        except ValueError:
            idx = 0
        self._diff_mode = modes[(idx + direction) % len(modes)]
        tree = self.query_one(FileTreeTable)
        entry = tree.get_current_entry()
        if entry and self._is_previewable(entry):
            preview = self.query_one(PreviewPane)
            source_line = preview.get_source_line_at_scroll()
            # Unified diff only shows changes, so its scroll position maps to
            # change locations, not the user's original position. Use the saved
            # position from before we entered unified mode.
            if old_mode == DiffMode.UNIFIED:
                source_line = self._scroll_positions.get(entry.path, source_line)
            else:
                self._scroll_positions[entry.path] = source_line
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
            if col in ("author", "git_time") and getattr(tree, attr) and self._git.is_git_repo():
                self._load_blame_data()

    def action_switch_pane(self) -> None:
        """Move focus between the file tree and the preview pane."""
        tree = self.query_one(FileTreeTable)
        preview = self.query_one(PreviewPane)
        (preview if tree.has_focus else tree).focus()

    def action_cycle_view(self) -> None:
        self.query_one(FileTreeTable).action_cycle_view()

    def action_cycle_view_reverse(self) -> None:
        self.query_one(FileTreeTable).action_cycle_view_reverse()

    def action_toggle_modified(self) -> None:
        self.query_one(Toolbar).toggle_modified()

    def _has_modal(self) -> bool:
        """Return True if a modal screen is currently displayed."""
        return len(self.screen_stack) > 1

    def _dismiss_modal(self) -> None:
        """Dismiss the topmost modal screen."""
        screen = self.screen
        if isinstance(screen, SideBySideDiffScreen):
            screen.dismiss(screen._get_current_source_line())
        else:
            screen.dismiss()

    def action_show_help(self) -> None:
        """Show keyboard shortcuts popup."""
        if self._has_modal():
            self._dismiss_modal()
            return
        self.push_screen(HelpScreen())

    def action_side_by_side(self) -> None:
        """Show side-by-side diff in a modal popup."""
        if self._has_modal():
            self._dismiss_modal()
            return
        tree = self.query_one(FileTreeTable)
        entry = tree.get_current_entry()
        if not entry or not entry.git_status or not self._git.is_git_repo():
            return
        diff = self._git.get_diff(entry.path)
        if not diff:
            return
        old_content = self._git.get_old_content(entry.path)
        try:
            new_content = entry.path.read_text(errors="replace")
        except OSError:
            new_content = ""
        preview = self.query_one(PreviewPane)
        source_line = preview.get_source_line_at_scroll()
        self.push_screen(
            SideBySideDiffScreen(entry.path.name, diff, old_content, new_content, scroll_to=source_line),
            callback=self._on_side_by_side_dismiss,
        )

    def _on_side_by_side_dismiss(self, source_line: int) -> None:
        """Restore preview scroll position to match where the side-by-side was scrolled."""
        if source_line and source_line > 1:
            preview = self.query_one(PreviewPane)
            preview.scroll_to_source_line(source_line)

    def action_open_editor(self) -> None:
        """Open the previewed file in $EDITOR at the current scroll position."""
        import subprocess  # nosec B404

        if not self._previewed_path or not self._previewed_path.is_file():
            return
        editor = os.environ.get("VISUAL", os.environ.get("EDITOR", "vim"))
        preview = self.query_one(PreviewPane)
        line = preview.get_source_line_at_scroll()
        # Build command — vim/nvim/vi get line numbers and scroll position
        cmd = [editor]
        editor_name = Path(editor).name
        if editor_name in ("vim", "nvim", "vi"):
            cmd.append("+set number")
            if line > 1:
                cmd.append(f"+{line}")
                cmd.append("+normal! zt")
        cmd.append(str(self._previewed_path))

        with self.suspend():
            subprocess.run(cmd)  # nosec B603

    def action_open_macos(self) -> None:
        """Open the selected file with macOS 'open' command."""
        import subprocess  # nosec B404
        import sys

        if sys.platform != "darwin":
            return
        if not self._previewed_path or not self._previewed_path.exists():
            return
        subprocess.Popen(["open", str(self._previewed_path)])  # nosec B603 B607

    def action_cycle_overview(self) -> None:
        """Cycle diff overview style through preferences.overview_styles."""
        overview = self.query_one(PreviewPane).query_one(DiffOverview)
        styles = self._prefs.overview_styles
        current = self._get_overview_style(overview)
        try:
            idx = styles.index(current)
        except ValueError:
            idx = -1
        next_style = styles[(idx + 1) % len(styles)]
        self._set_overview_style(overview, next_style)

    def _get_overview_style(self, overview: DiffOverview) -> str:
        if not overview.display:
            return "off"
        if overview.use_braille:
            return "braille"
        if overview.use_sextant:
            return "sextant"
        if overview.use_quadrant:
            return "quadrant"
        return "line"

    def _set_overview_style(self, overview: DiffOverview, style: str) -> None:
        overview.use_braille = style == "braille"
        overview.use_quadrant = style == "quadrant"
        overview.use_sextant = style == "sextant"
        overview.display = style != "off"

    # -------------------------------------------------------------------------
    # State persistence
    # -------------------------------------------------------------------------

    def _save_state(self) -> None:
        """Capture all app state from live widgets and persist to disk."""
        tree = self.query_one(FileTreeTable)
        split = self.query_one(HorizontalSplit)
        toolbar = self.query_one(Toolbar)
        entry = tree.get_current_entry()

        self._state.capture_from_widgets(
            tree,
            toolbar,
            split,
            diff_mode=self._diff_mode,
            selected_path=entry.path if entry else None,
        )
        preview = self.query_one(PreviewPane)
        self._state.scroll_line = preview.get_source_line_at_scroll()
        overview = preview.query_one(DiffOverview)
        self._state.use_braille = overview.use_braille
        self._state.use_quadrant = overview.use_quadrant
        self._state.use_sextant = overview.use_sextant
        self._state.save()

    def action_quit(self) -> None:
        """Save state and exit."""
        if self._has_modal():
            self._dismiss_modal()
            return
        self._save_state()
        self.exit()


def main() -> None:
    import sys

    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    GamrApp(path=path).run()


if __name__ == "__main__":
    main()
