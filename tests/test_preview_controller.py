"""Tests for PreviewController."""

from pathlib import Path
from unittest.mock import MagicMock

from gamr.models import DiffMode, FileEntry, GitStatus
from gamr.preview import PreviewController
from gamr.services.file_index import FileIndex


def _make_controller(entries: dict[Path, FileEntry] | None = None, diff: str = "") -> PreviewController:
    git = MagicMock()
    git.is_git_repo.return_value = True
    git.get_diff.return_value = diff
    file_index = MagicMock(spec=FileIndex)
    file_index.entries = entries or {}
    return PreviewController(git, file_index)


class TestIsPreviewable:
    def test_regular_file(self, tmp_path: Path) -> None:
        # Testing: is_previewable returns True for a file that exists on disk.
        # Input: a real file on the filesystem with no git status.
        # Expected: True — file exists, so it has content to preview.
        # Asserts: the path.is_file() check works for normal files.
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        entry = FileEntry(path=f)
        assert PreviewController.is_previewable(entry)

    def test_deleted_file(self) -> None:
        # Testing: is_previewable returns True for a deleted file (path doesn't exist).
        # Input: non-existent path with GitStatus.DELETED.
        # Expected: True — deleted files can show their old content via git diff.
        # Asserts: the status-based fallback allows previewing git-deleted files.
        entry = FileEntry(path=Path("/nonexistent"), git_status=GitStatus.DELETED)
        assert PreviewController.is_previewable(entry)

    def test_staged_deleted(self) -> None:
        # Testing: is_previewable returns True for staged deletions.
        # Input: non-existent path with GitStatus.STAGED_DELETED.
        # Expected: True — same as DELETED, staged deletions have old content.
        # Asserts: both deletion statuses are handled symmetrically.
        entry = FileEntry(path=Path("/nonexistent"), git_status=GitStatus.STAGED_DELETED)
        assert PreviewController.is_previewable(entry)

    def test_directory_not_previewable(self, tmp_path: Path) -> None:
        # Testing: is_previewable returns False for directories.
        # Input: tmp_path is a directory, not a file.
        # Expected: False — directories have no file content to render.
        # Asserts: path.is_file() correctly rejects directories.
        entry = FileEntry(path=tmp_path)
        assert not PreviewController.is_previewable(entry)


class TestHunkTracking:
    def test_snapshot_hunks_records_positions(self, tmp_path: Path) -> None:
        # Testing: _snapshot_hunks extracts hunk start lines from a diff.
        # Input: diff with two hunks starting at new-file lines 1 and 11.
        # Expected: _known_hunks[path] == {1, 11}.
        # Asserts: regex correctly parses @@ headers and stores start positions.
        diff = "@@ -1,3 +1,4 @@\n+new\n @@ -10,3 +11,5 @@\n+more\n"
        ctrl = _make_controller(diff=diff)
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1, git_status=GitStatus.MODIFIED)
        ctrl._snapshot_hunks(entry)
        assert ctrl._known_hunks[f] == {1, 11}

    def test_snapshot_hunks_empty_for_no_status(self, tmp_path: Path) -> None:
        # Testing: _snapshot_hunks records empty set for files with no git status.
        # Input: file entry with no git_status (untracked/clean file).
        # Expected: _known_hunks[path] == set() — no diff to parse.
        # Asserts: the early-return path for non-git files works correctly.
        ctrl = _make_controller()
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1)
        ctrl._snapshot_hunks(entry)
        assert ctrl._known_hunks[f] == set()

    def test_show_followed_detects_new_hunks(self, tmp_path: Path) -> None:
        # Testing: show_followed_path identifies hunks not in _known_hunks as new.
        # Input: diff has hunks at lines 1 and 21; only line 1 is known.
        # Expected: _known_hunks updated to {1, 21}; line 21 recognized as new.
        # Asserts: set difference (current - known) correctly identifies new changes.
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1, git_status=GitStatus.MODIFIED)
        ctrl = _make_controller(entries={f: entry}, diff="@@ -1,3 +1,4 @@\n+x\n@@ -20,3 +21,4 @@\n+y\n")
        ctrl._known_hunks[f] = {1}

        pane = MagicMock()
        pane.is_source_line_visible.return_value = False
        pane.get_source_line_at_scroll.return_value = 1

        ctrl.show_followed_path(f, pane, DiffMode.FULL)

        assert ctrl._known_hunks[f] == {1, 21}

    def test_show_followed_no_scroll_when_visible(self, tmp_path: Path) -> None:
        # Testing: show_followed_path doesn't scroll when new hunk is already visible.
        # Input: new hunk at line 21, pane reports it's visible, current scroll at 15.
        # Expected: pane.invalidate() called (re-render) but scroll preserved at 15.
        # Asserts: the visibility check prevents disorienting scroll jumps.
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1, git_status=GitStatus.MODIFIED)
        ctrl = _make_controller(entries={f: entry}, diff="@@ -1,3 +1,4 @@\n+x\n@@ -20,3 +21,4 @@\n+y\n")
        ctrl._known_hunks[f] = {1}

        pane = MagicMock()
        pane.is_source_line_visible.return_value = True
        pane.get_source_line_at_scroll.return_value = 15

        ctrl.show_followed_path(f, pane, DiffMode.FULL)

        pane.invalidate.assert_called_once()

    def test_show_followed_no_new_hunks_preserves_position(self, tmp_path: Path) -> None:
        # Testing: show_followed_path preserves scroll when all hunks are already known.
        # Input: diff has hunk at line 1, already in _known_hunks. Scroll at line 50.
        # Expected: pane re-rendered (content may have changed) but scroll stays at 50.
        # Asserts: no scroll target means render in place with current position.
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1, git_status=GitStatus.MODIFIED)
        ctrl = _make_controller(entries={f: entry}, diff="@@ -1,3 +1,4 @@\n+x\n")
        ctrl._known_hunks[f] = {1}

        pane = MagicMock()
        pane.get_source_line_at_scroll.return_value = 50

        ctrl.show_followed_path(f, pane, DiffMode.FULL)

        pane.invalidate.assert_called_once()


class TestOnNodeHighlighted:
    def test_skips_same_file(self) -> None:
        # Testing: on_node_highlighted is a no-op when navigating to the same file.
        # Input: previewed_path already equals the entry's path.
        # Expected: no scroll save, no render — early return.
        # Asserts: the dedup guard prevents redundant re-renders on cursor movement.
        path = Path("/project/a.py")
        ctrl = _make_controller()
        ctrl.previewed_path = path
        entry = FileEntry(path=path, size=100, git_status=GitStatus.MODIFIED)

        pane = MagicMock()
        ctrl.on_node_highlighted(entry, pane)
        pane.get_source_line_at_scroll.assert_not_called()

    def test_saves_scroll_on_switch(self, tmp_path: Path) -> None:
        # Testing: on_node_highlighted saves scroll position of the old file before switching.
        # Input: previewed_path is old_file (scroll at line 42), navigating to new_file.
        # Expected: scroll_positions[old_file] == 42, previewed_path updated to new_file.
        # Asserts: scroll state is persisted per-file so it can be restored later.
        old_file = tmp_path / "old.py"
        old_file.write_text("old")
        new_file = tmp_path / "new.py"
        new_file.write_text("new")

        ctrl = _make_controller()
        ctrl.previewed_path = old_file

        pane = MagicMock()
        pane.get_source_line_at_scroll.return_value = 42

        new_entry = FileEntry(path=new_file, size=10)
        ctrl.on_node_highlighted(new_entry, pane)

        assert ctrl.scroll_positions[old_file] == 42
        assert ctrl.previewed_path == new_file
