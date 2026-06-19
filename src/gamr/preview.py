"""Preview orchestration — decides what to show and manages scroll state.

Extracted from app.py to reduce its size. The controller owns the preview
decision logic (which file, which mode, scroll position) while the widget
(PreviewPane) owns rendering.
"""

from __future__ import annotations

import re
from pathlib import Path

from gamr.models import DiffMode, FileEntry, GitStatus
from gamr.services.file_index import FileIndex
from gamr.services.git_provider import GitProvider
from gamr.widgets.preview_pane import PreviewPane


class PreviewController:
    """Manages preview state and delegates rendering to PreviewPane."""

    def __init__(self, git: GitProvider, file_index: FileIndex) -> None:
        self._git = git
        self._file_index = file_index
        self.previewed_path: Path | None = None
        self.previewed_git_status: GitStatus | None = None
        self.scroll_positions: dict[Path, int] = {}

    def on_node_highlighted(self, entry: FileEntry | None, pane: PreviewPane) -> None:
        """Handle user navigating to a new file."""
        if entry is None or not self.is_previewable(entry):
            return
        if entry.path == self.previewed_path:
            return
        # Save scroll position of the file we're leaving
        if self.previewed_path:
            self.scroll_positions[self.previewed_path] = pane.get_source_line_at_scroll()
        self.previewed_path = entry.path
        self.previewed_git_status = entry.git_status
        saved = self.scroll_positions.get(entry.path, 0)
        self.render(entry, pane, restore_line=saved)

    def render(
        self,
        entry: FileEntry,
        pane: PreviewPane,
        *,
        diff_mode: DiffMode | None = None,
        scroll_to_top: bool = True,
        restore_line: int = 0,
    ) -> None:
        """Render file content or diff in the preview pane."""
        if diff_mode is None:
            diff_mode = pane.show_diff
        pane.loading = False
        pane.show_diff = diff_mode
        is_diffable = entry.git_status and self._git.is_git_repo()
        diff = self._git.get_diff(entry.path) if is_diffable else ""
        kwargs = {"scroll_to_top": scroll_to_top, "restore_line": restore_line}

        if diff:
            dispatch = {
                DiffMode.UNIFIED: lambda: pane.show_diff_content(diff, path=entry.path, **kwargs),
                DiffMode.FULL: lambda: pane.show_full_diff(entry.path, diff, **kwargs),
                DiffMode.GUTTER: lambda: pane.show_gutter_diff(entry.path, diff, **kwargs),
            }
            dispatch[diff_mode]()
            return

        pane.show_file(entry.path, **kwargs)

    def render_error(self, path: Path, message: str, pane: PreviewPane) -> None:
        """Show error/info message if path is still current."""
        if self.previewed_path != path:
            return
        pane.loading = False
        pane.show_message(message)

    def show_followed_path(self, path: Path, pane: PreviewPane, diff_mode: DiffMode) -> None:
        """Update preview for a followed file; scroll to last hunk only if off-screen."""
        entry = self._file_index.entries.get(path)
        if not entry or not self.is_previewable(entry):
            return

        # Find the last diff hunk (most likely the newest change)
        target_line = 0
        if entry.git_status and self._git.is_git_repo():
            diff = self._git.get_diff(path)
            if diff:
                for m in re.finditer(r"@@ [^+]*\+(\d+)", diff):
                    target_line = int(m.group(1))

        # If the target is already visible, just re-render in place (no scroll jump)
        already_visible = target_line > 0 and pane.is_source_line_visible(target_line)
        pane.invalidate()
        if already_visible:
            current_line = pane.get_source_line_at_scroll()
            self.render(entry, pane, diff_mode=diff_mode, scroll_to_top=False, restore_line=current_line)
        else:
            self.render(entry, pane, diff_mode=diff_mode, restore_line=target_line)

    def refresh_if_needed(
        self, changed_paths: list[Path] | None, git_changed: bool, pane: PreviewPane, diff_mode: DiffMode
    ) -> None:
        """Re-render preview if the previewed file's content or git status changed."""
        if not self.previewed_path:
            return
        entry = self._file_index.entries.get(self.previewed_path)
        file_content_changed = changed_paths and self.previewed_path in set(changed_paths)
        git_status_changed = git_changed and entry and entry.git_status != self.previewed_git_status
        if (file_content_changed or git_status_changed) and entry and self.is_previewable(entry):
            source_line = pane.get_source_line_at_scroll()
            pane.invalidate()
            self.render(entry, pane, diff_mode=diff_mode, scroll_to_top=False, restore_line=source_line)
        if entry:
            self.previewed_git_status = entry.git_status

    @staticmethod
    def is_previewable(entry: FileEntry) -> bool:
        """Return whether an entry has file contents or a deletion diff to show."""
        return entry.path.is_file() or entry.git_status in {
            GitStatus.DELETED,
            GitStatus.STAGED_DELETED,
        }
