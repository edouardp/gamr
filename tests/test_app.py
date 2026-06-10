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
        filter_bar.selected_filter_ids = {"staged"}
        split.split_fraction = 0.6
        app._save_state()

    restored = AppState.load(tmp_path)
    assert not restored.show_mtime
    assert restored.active_filter_ids == {"staged"}
    assert restored.split_fraction == 0.6
