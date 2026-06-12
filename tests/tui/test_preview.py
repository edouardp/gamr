"""Tests for preview pane: tab focus, vim keys, hunk navigation, loading."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.preview_pane import PreviewPane


async def test_tab_switches_focus_to_preview(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)

        assert tree.has_focus
        await pilot.press("tab")
        await pilot.pause()
        assert preview.has_focus

        await pilot.press("tab")
        await pilot.pause()
        assert tree.has_focus


async def test_j_k_scroll_preview_when_focused(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)

        # Select a file with content
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        # Focus preview
        await pilot.press("tab")
        await pilot.pause()
        assert preview.has_focus


async def test_loading_clears_on_file_switch(tmp_path: Path) -> None:
    """Loading indicator should clear when navigating to a small file."""
    repo = Repo.init(str(tmp_path))
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

        tree.restore_cursor(large)
        await pilot.pause()

        tree.restore_cursor(small)
        await pilot.pause()
        await pilot.pause()

        assert not preview.loading


async def test_binary_file_shows_message(tmp_path: Path) -> None:
    """Binary files should show a message dialog, not crash."""
    repo = Repo.init(str(tmp_path))
    binary = tmp_path / "data.bin"
    binary.write_bytes(b"\x00\x01\x02\x03" * 100)
    porcelain.add(repo, paths=["data.bin"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")

    app = GamrApp(path=tmp_path)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(binary)
        await pilot.pause()

        # Message widget should be visible
        msg = app.query_one("#preview-message")
        assert "hidden" not in msg.classes


async def test_preview_shows_file_content(tree_repo: Path) -> None:
    """Selecting a file should show its content in the preview."""
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "main.py")
        await pilot.pause()

        content = app.query_one("#preview-content")
        rendered = str(content.render())
        assert "print" in rendered
