"""Tests for filtering: g toggle, ctrl+f focus."""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.filter_bar import FilterBar


async def test_g_toggles_modified_filter(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        filter_bar = app.query_one(FilterBar)

        rows_all = tree.row_count

        await pilot.press("g")
        await pilot.pause(delay=0.2)  # wait for 150ms debounce
        assert "modified" in filter_bar.selected_filter_ids
        rows_filtered = tree.row_count
        assert rows_filtered < rows_all

        await pilot.press("g")
        await pilot.pause(delay=0.2)
        assert "modified" not in filter_bar.selected_filter_ids


async def test_ctrl_f_focuses_search_input(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("ctrl+f")
        await pilot.pause()
        focused = app.focused
        assert focused is not None
        assert focused.id == "search-input"


async def test_filter_preserves_collapsed_dirs(tree_repo: Path) -> None:
    """Toggling git filter should not lose collapsed folder state."""
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        docs = tree_repo / "docs"

        # Collapse docs/
        tree.restore_cursor(docs)
        await pilot.press("left")
        await pilot.pause()
        collapsed_before = tree.get_collapsed_dirs()
        assert "docs" in collapsed_before

        # Toggle filter on and off
        await pilot.press("g")
        await pilot.pause(delay=0.2)
        await pilot.press("g")
        await pilot.pause(delay=0.2)

        # docs/ should still be collapsed
        collapsed_after = tree.get_collapsed_dirs()
        assert "docs" in collapsed_after
