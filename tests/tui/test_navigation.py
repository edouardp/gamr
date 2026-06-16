"""Tests for tree navigation: arrows, j/k, expand/collapse, ← parent.

Fixture `tree_repo` provides this structure:
    docs/
        readme.md
    src/
        alpha.py    ← modified (has git diff)
        beta.py
    main.py
"""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable


async def test_down_arrow_moves_cursor(tree_repo: Path) -> None:
    """
    Start state:  cursor on row 0 (first item)
    Action:       press ↓
    Expected:     cursor moves to row 1

        [ docs/     ] ← was here
        [ src/      ] ← now here
          ...
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        initial = tree.cursor_row
        await pilot.press("down")
        await pilot.pause()
        assert tree.cursor_row == initial + 1


async def test_j_moves_cursor_down(tree_repo: Path) -> None:
    """
    Same as ↓ — vim 'j' key should move cursor down one row.

        [ docs/     ] ← was here
        [ src/      ] ← now here (after 'j')
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        initial = tree.cursor_row
        await pilot.press("j")
        await pilot.pause()
        assert tree.cursor_row == initial + 1


async def test_k_moves_cursor_up(tree_repo: Path) -> None:
    """
    Start state:  cursor on row 2
    Action:       press 'k'
    Expected:     cursor moves to row 1

        [ docs/     ]
        [ src/      ] ← now here (after 'k')
        [ main.py   ] ← was here
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        await pilot.press("down")
        await pilot.press("down")
        await pilot.pause()
        row_before = tree.cursor_row
        await pilot.press("k")
        await pilot.pause()
        assert tree.cursor_row == row_before - 1


async def test_right_expands_directory(tree_repo: Path) -> None:
    """
    Start state:  cursor on src/ (collapsed)
    Action:       press →
    Expected:     src/ expands, children become visible, row count increases

        ▶ src/          →    ▼ src/
                                alpha.py
                                beta.py
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"

        tree.restore_cursor(src)
        await pilot.press("left")  # collapse first
        await pilot.pause()
        rows_collapsed = tree.row_count

        await pilot.press("right")
        await pilot.pause()
        assert tree.row_count > rows_collapsed


async def test_left_collapses_directory(tree_repo: Path) -> None:
    """
    Start state:  cursor on src/ (expanded, children visible)
    Action:       press ←
    Expected:     src/ collapses, children hidden, row count decreases

        ▼ src/          →    ▶ src/
          alpha.py
          beta.py
    """
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
        assert tree.cursor_row >= 0


async def test_left_on_file_collapses_parent(tree_repo: Path) -> None:
    """
    Start state:  cursor on alpha.py (inside expanded src/)
    Action:       press ←
    Expected:     parent src/ collapses, cursor moves to src/

        ▼ src/
          alpha.py  ← cursor here     →    ▶ src/  ← cursor moves here
          beta.py
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        alpha = tree_repo / "src" / "alpha.py"

        tree.restore_cursor(alpha)
        await pilot.pause()
        rows_before = tree.row_count

        await pilot.press("left")
        await pilot.pause()
        assert tree.row_count < rows_before


async def test_expand_collapse_preserves_cursor(tree_repo: Path) -> None:
    """
    Start state:  cursor on src/ (expanded)
    Actions:      ← (collapse), then → (expand)
    Expected:     cursor stays on src/ row throughout

        ▼ src/ ← cursor     →    ▶ src/ ← cursor    →    ▼ src/ ← cursor
          alpha.py                                           alpha.py
          beta.py                                            beta.py
    """
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
    """
    Start state:  cursor on src/ (expanded)
    Action:       press space (toggle), then space again
    Expected:     first space collapses, second space expands back

        ▼ src/       space→    ▶ src/       space→    ▼ src/
          alpha.py                                      alpha.py
          beta.py                                       beta.py
    """
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


async def test_ensure_visible_expands_collapsed_ancestor(tree_repo: Path) -> None:
    """
    Start state:  src/ is collapsed
    Action:       call ensure_visible(src/alpha.py)
    Expected:     src/ expands, alpha.py becomes a visible row

        ▶ src/       ensure_visible→    ▼ src/
                                          alpha.py  ← now visible
                                          beta.py
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"
        alpha = tree_repo / "src" / "alpha.py"

        # Collapse src/
        tree.restore_cursor(src)
        await pilot.press("left")
        await pilot.pause()
        assert str(alpha) not in tree._row_to_node

        # ensure_visible should expand the parent
        tree.ensure_visible(alpha)
        await pilot.pause()
        assert str(alpha) in tree._row_to_node


async def test_ensure_visible_noop_when_already_visible(tree_repo: Path) -> None:
    """
    Start state:  src/ is expanded, alpha.py is visible
    Action:       call ensure_visible(src/alpha.py)
    Expected:     no change, row count stays the same

        ▼ src/
          alpha.py  ← already visible
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        alpha = tree_repo / "src" / "alpha.py"
        rows_before = tree.row_count

        tree.ensure_visible(alpha)
        await pilot.pause()
        assert tree.row_count == rows_before


async def test_follow_mode_expands_collapsed_dir(tree_repo: Path) -> None:
    """
    Start state:  follow mode ON, src/ is collapsed
    Action:       a file inside src/ changes on disk
    Expected:     src/ auto-expands, cursor moves to the changed file

        ▶ src/       file change→    ▼ src/
        main.py                        alpha.py  ← cursor here
                                       beta.py
                                     main.py
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        src = tree_repo / "src"
        alpha = tree_repo / "src" / "alpha.py"

        # Collapse src/
        tree.restore_cursor(src)
        await pilot.press("left")
        await pilot.pause()
        assert str(alpha) not in tree._row_to_node

        # Enable follow mode
        await pilot.press("f")
        await pilot.pause()

        # Simulate a file change that triggers follow mode
        (tree_repo / "src" / "alpha.py").write_text("a = 1\nb = 2\nc = 3\nd = 4\n")
        await pilot.pause(delay=2.0)

        # alpha.py should now be visible and selected
        assert str(alpha) in tree._row_to_node
        current = tree.get_current_entry()
        assert current is not None
        assert current.path == alpha
