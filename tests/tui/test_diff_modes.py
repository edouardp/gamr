"""Tests for diff mode cycling: d/D keys, scroll preservation."""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.preview_pane import PreviewPane


async def test_d_cycles_diff_mode_forward(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        initial_mode = app._diff_mode
        await pilot.press("d")
        await pilot.pause()
        assert app._diff_mode != initial_mode


async def test_D_cycles_diff_mode_backward(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        # Cycle forward twice, then backward once
        await pilot.press("d")
        await pilot.pause()
        mode_after_d = app._diff_mode
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        assert app._diff_mode == mode_after_d


async def test_diff_mode_cycles_through_preferences(tree_repo: Path) -> None:
    """Diff mode should cycle through the modes defined in preferences."""
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        modes_seen = [app._diff_mode]
        for _ in range(len(app._prefs.diff_modes)):
            await pilot.press("d")
            await pilot.pause()
            modes_seen.append(app._diff_mode)

        # Should cycle back to original
        assert modes_seen[-1] == modes_seen[0]


async def test_scroll_preserved_across_diff_mode_switch(tree_repo: Path) -> None:
    """Switching diff modes should preserve scroll position by source line."""
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        # Get initial source line
        source_before = preview.get_source_line_at_scroll()

        # Cycle through all modes and back
        for _ in range(len(app._prefs.diff_modes)):
            await pilot.press("d")
            await pilot.pause()

        source_after = preview.get_source_line_at_scroll()
        assert source_after == source_before
