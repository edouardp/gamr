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


def _entry(path: str, status: GitStatus | None = GitStatus.MODIFIED) -> FileEntry:
    p = Path(path)
    return FileEntry(path=p, size=100, git_status=status)


class TestIsPreviewable:
    def test_regular_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        entry = FileEntry(path=f)
        assert PreviewController.is_previewable(entry)

    def test_deleted_file(self) -> None:
        entry = FileEntry(path=Path("/nonexistent"), git_status=GitStatus.DELETED)
        assert PreviewController.is_previewable(entry)

    def test_staged_deleted(self) -> None:
        entry = FileEntry(path=Path("/nonexistent"), git_status=GitStatus.STAGED_DELETED)
        assert PreviewController.is_previewable(entry)

    def test_directory_not_previewable(self, tmp_path: Path) -> None:
        entry = FileEntry(path=tmp_path)
        assert not PreviewController.is_previewable(entry)


class TestHunkTracking:
    def test_snapshot_hunks_records_positions(self, tmp_path: Path) -> None:
        diff = "@@ -1,3 +1,4 @@\n+new\n @@ -10,3 +11,5 @@\n+more\n"
        ctrl = _make_controller(diff=diff)
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1, git_status=GitStatus.MODIFIED)
        ctrl._snapshot_hunks(entry)
        assert ctrl._known_hunks[f] == {1, 11}

    def test_snapshot_hunks_empty_for_no_status(self, tmp_path: Path) -> None:
        ctrl = _make_controller()
        f = tmp_path / "a.py"
        f.write_text("x")
        entry = FileEntry(path=f, size=1)
        ctrl._snapshot_hunks(entry)
        assert ctrl._known_hunks[f] == set()

    def test_show_followed_detects_new_hunks(self, tmp_path: Path) -> None:
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
        path = Path("/project/a.py")
        ctrl = _make_controller()
        ctrl.previewed_path = path
        entry = _entry(str(path))

        pane = MagicMock()
        ctrl.on_node_highlighted(entry, pane)
        pane.get_source_line_at_scroll.assert_not_called()

    def test_saves_scroll_on_switch(self, tmp_path: Path) -> None:
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
