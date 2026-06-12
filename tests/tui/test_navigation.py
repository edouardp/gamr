"""Tests for tree navigation: arrows, j/k, expand/collapse, ← parent."""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable


async def test_down_arrow_moves_cursor(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        initial = tree.cursor_row
        await pilot.press("down")
        await pilot.pause()
        assert tree.cursor_row == initial + 1


async def test_j_moves_cursor_down(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        initial = tree.cursor_row
        await pilot.press("j")
        await pilot.pause()
        assert tree.cursor_row == initial + 1


async def test_k_moves_cursor_up(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        # Move down first then back up
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        row_before = tree.cursor_row
        await pilot.press("k")
        await pilot.pause()
        assert tree.cursor_row == row_before - 1


async def test_right_expands_directory(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"

        # Collapse src first
        tree.restore_cursor(src)
        await pilot.press("left")
        await pilot.pause()
        rows_collapsed = tree.row_count

        # Expand with right arrow
        await pilot.press("right")
        await pilot.pause()
        assert tree.row_count > rows_collapsed


async def test_left_collapses_directory(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"

        tree.restore_cursor(src)
        await pilot.pause()
        rows_expanded = tree.row_count

        await pilot.press("left")
        await pilot.pause()
        assert tree.row_count < rows_expanded
        # Cursor stays on the directory
        assert tree.cursor_row >= 0


async def test_left_on_file_collapses_parent(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        alpha = tree_repo / "src" / "alpha.py"

        tree.restore_cursor(alpha)
        await pilot.pause()
        rows_before = tree.row_count

        # ← on file should collapse parent (src/)
        await pilot.press("left")
        await pilot.pause()
        assert tree.row_count < rows_before


async def test_expand_collapse_preserves_cursor(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"

        tree.restore_cursor(src)
        await pilot.pause()
        cursor_row = tree.cursor_row

        await pilot.press("left")
        await pilot.pause()
        assert tree.cursor_row == cursor_row

        await pilot.press("right")
        await pilot.pause()
        assert tree.cursor_row == cursor_row


async def test_space_toggles_directory(tree_repo: Path) -> None:
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"

        tree.restore_cursor(src)
        await pilot.pause()
        rows_expanded = tree.row_count

        await pilot.press("space")
        await pilot.pause()
        rows_collapsed = tree.row_count
        assert rows_collapsed < rows_expanded

        await pilot.press("space")
        await pilot.pause()
        assert tree.row_count == rows_expanded
