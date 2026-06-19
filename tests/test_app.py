"""Integration tests for GamrApp lifecycle and state."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.app import GamrApp
from gamr.models import GitStatus
from gamr.services.file_scanner import FileScanner
from gamr.state import AppState
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.split import HorizontalSplit
from gamr.widgets.toolbar import Toolbar


async def test_app_mounts_on_git_repo(tmp_path: Path) -> None:
    # Testing: GamrApp mounting and displaying files in a valid git repo.
    # Input: a tmp_path git repo with one committed file (hello.py).
    # Expected: the FileTreeTable has at least 1 row after mounting.
    # Asserts: the app can initialize and render a file tree from a git repo.
    """App should mount and display files in a git repo."""
    repo = Repo.init(str(tmp_path))
    (tmp_path / "hello.py").write_text("x = 1\n")
    porcelain.add(repo, paths=["hello.py"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        assert tree.row_count >= 1


async def test_app_mounts_on_non_git_dir(tmp_path: Path) -> None:
    # Testing: graceful degradation when app opens a non-git directory.
    # Input: a plain directory with one file, no .git.
    # Expected: tree has rows and show_status is False (git UI hidden).
    # Asserts: the app works on non-git dirs without crashing and hides git columns.
    """App should mount gracefully on a non-git directory."""
    (tmp_path / "file.txt").write_text("data")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        assert tree.row_count >= 1
        assert not tree.show_status


async def test_app_uses_git_repo_when_browsing_subdirectory(tmp_path: Path) -> None:
    # Testing: git status detection when app is opened on a subdirectory of a repo.
    # Input: git repo with src/module.py committed then modified; app opened on src/.
    # Expected: show_status is True and the file shows MODIFIED status.
    # Asserts: git discovery works from subdirectories and status propagates correctly.
    repo = Repo.init(str(tmp_path))
    subdirectory = tmp_path / "src"
    subdirectory.mkdir()
    file = subdirectory / "module.py"
    file.write_text("x = 1\n")
    porcelain.add(repo, paths=["src/module.py"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")
    file.write_text("x = 2\n")

    app = GamrApp(path=subdirectory)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        assert tree.show_status
        assert app._all_entries[0].git_status == GitStatus.MODIFIED


async def test_file_change_refreshes_selected_preview(tmp_path: Path) -> None:
    # Testing: live preview refresh when the selected file changes on disk.
    # Input: file.txt initially contains "OLD", then overwritten with "NEW".
    # Expected: preview content updates to show "NEW" and no longer shows "OLD".
    # Asserts: the file watcher callback triggers a preview re-render.
    file = tmp_path / "file.txt"
    file.write_text("OLD\n")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        content = app.query_one("#preview-content")
        assert "OLD" in str(content.render())

        file.write_text("NEW\n")
        app._handle_file_changes([file])
        await pilot.pause()

        rendered = str(content.render())
        assert "NEW" in rendered
        assert "OLD" not in rendered


async def test_app_stops_scanner_on_shutdown(tmp_path: Path, monkeypatch) -> None:
    # Testing: FileScanner is properly stopped when the app shuts down.
    # Input: app opened on a directory, then closed via run_test context exit.
    # Expected: FileScanner.stop() is called (stopped flag becomes True).
    # Asserts: no dangling watcher threads after app exit.
    (tmp_path / "file.txt").write_text("data")
    stopped = False
    original_stop = FileScanner.stop

    def stop(scanner: FileScanner) -> None:
        nonlocal stopped
        stopped = True
        original_stop(scanner)

    monkeypatch.setattr(FileScanner, "stop", stop)

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()

    assert stopped


async def test_app_applies_and_captures_persistent_widget_state(tmp_path: Path, monkeypatch) -> None:
    # Testing: persistent state is restored on launch and captured on save.
    # Input: saved AppState with show_size=False, split_fraction=0.7, filter=modified; then modify and save.
    # Expected: widgets reflect saved state on mount; re-saved state matches new widget values.
    # Asserts: the full state persistence round-trip (load → apply → modify → save → reload) works.
    repo = Repo.init(str(tmp_path))
    file = tmp_path / "file.txt"
    file.write_text("old\n")
    porcelain.add(repo, paths=["file.txt"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")
    file.write_text("new\n")

    AppState(
        tmp_path,
        show_size=False,
        split_fraction=0.7,
        active_filter_ids={"modified"},
    ).save()

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        toolbar = app.query_one(Toolbar)
        split = app.query_one(HorizontalSplit)

        assert not tree.show_size
        assert toolbar.selected_filter_ids == {"modified"}
        assert split.split_fraction == 0.7

        tree.show_mtime = False
        toolbar.selected_filter_ids = {"modified"}
        split.split_fraction = 0.6
        app._save_state()

    restored = AppState.load(tmp_path)
    assert not restored.show_mtime
    assert restored.active_filter_ids == {"modified"}
    assert restored.split_fraction == 0.6
