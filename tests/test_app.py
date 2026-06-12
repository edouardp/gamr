"""Integration tests for GamrApp."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.app import GamrApp
from gamr.models import GitStatus
from gamr.services.file_scanner import FileScanner
from gamr.state import AppState
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.filter_bar import FilterBar
from gamr.widgets.preview_pane import PreviewPane
from gamr.widgets.split import HorizontalSplit


async def test_app_mounts_on_git_repo(tmp_path: Path) -> None:
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
    """App should mount gracefully on a non-git directory."""
    (tmp_path / "file.txt").write_text("data")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        assert tree.row_count >= 1
        # Git columns should be hidden
        assert not tree.show_status


async def test_app_uses_git_repo_when_browsing_subdirectory(tmp_path: Path) -> None:
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
        filter_bar = app.query_one(FilterBar)
        split = app.query_one(HorizontalSplit)

        assert not tree.show_size
        assert filter_bar.selected_filter_ids == {"modified"}
        assert split.split_fraction == 0.7

        tree.show_mtime = False
        filter_bar.selected_filter_ids = {"modified"}
        split.split_fraction = 0.6
        app._save_state()

    restored = AppState.load(tmp_path)
    assert not restored.show_mtime
    assert restored.active_filter_ids == {"modified"}
    assert restored.split_fraction == 0.6


async def test_expand_collapse_preserves_cursor(tmp_path: Path) -> None:
    """Expanding/collapsing a folder should keep the cursor on that folder."""
    repo = Repo.init(str(tmp_path))
    subdir = tmp_path / "src"
    subdir.mkdir()
    (subdir / "a.py").write_text("a\n")
    (subdir / "b.py").write_text("b\n")
    (tmp_path / "top.py").write_text("top\n")
    porcelain.add(repo, paths=["src/a.py", "src/b.py", "top.py"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)

        # Navigate to the src/ directory
        tree.restore_cursor(subdir)
        await pilot.pause()

        # Collapse it
        await pilot.press("left")
        await pilot.pause()
        # Cursor should still be on src/ (a directory)
        cursor_row = tree.cursor_row
        assert cursor_row >= 0

        # Expand it
        await pilot.press("right")
        await pilot.pause()
        # Cursor should still be on the same row (the directory)
        assert tree.cursor_row == cursor_row


async def test_loading_clears_when_selecting_small_file(tmp_path: Path) -> None:
    """Selecting a small file after a large one should clear the loading state."""
    repo = Repo.init(str(tmp_path))
    # Create a file just over the 50KB threshold
    large = tmp_path / "large.txt"
    large.write_text("x\n" * 30000)  # ~60KB
    small = tmp_path / "small.txt"
    small.write_text("hello\n")
    porcelain.add(repo, paths=["large.txt", "small.txt"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)

        # Select the large file — should trigger loading
        tree.restore_cursor(large)
        await pilot.pause()

        # Now select the small file
        tree.restore_cursor(small)
        await pilot.pause()
        await pilot.pause()  # extra pause for async worker

        # Loading should be cleared
        assert not preview.loading
