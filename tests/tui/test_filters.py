"""Tests for filtering: g toggle, / focus, state preservation.

Fixture `tree_repo` provides:
    docs/readme.md       (clean)
    src/alpha.py         (modified — has git diff)
    src/beta.py          (clean)
    main.py              (clean)

Only src/alpha.py has GitStatus.MODIFIED.
"""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.toolbar import Toolbar


async def test_g_toggles_modified_filter(tree_repo: Path) -> None:
    """
    Start state:  all files visible (no filter)
    Action:       press 'g' (toggle modified filter ON)
    Expected:     only modified file(s) + parent dirs visible; row count drops

        Before 'g':              After 'g':
        ▼ docs/                  ▼ src/
          readme.md                alpha.py  ← only modified file
        ▼ src/
          alpha.py  (M)
          beta.py
        main.py

    Action:       press 'g' again (toggle OFF)
    Expected:     all files visible again
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        toolbar = app.query_one(Toolbar)

        rows_all = tree.row_count

        await pilot.press("g")
        await pilot.pause(delay=0.2)  # wait for 150ms debounce
        assert "modified" in toolbar.selected_filter_ids
        rows_filtered = tree.row_count
        assert rows_filtered < rows_all

        await pilot.press("g")
        await pilot.pause(delay=0.2)
        assert "modified" not in toolbar.selected_filter_ids


async def test_ctrl_f_focuses_search_input(tree_repo: Path) -> None:
    """
    Start state:  tree has focus (default after launch)
    Action:       press /
    Expected:     focus moves to the search input in the filter bar

        ┌─ Filter Bar ─────────────────────┐
        │ 🔍 Filter files...  ← focus here │
        └──────────────────────────────────┘
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        await pilot.press("/")
        await pilot.pause()
        focused = app.focused
        assert focused is not None
        assert focused.id == "search-input"


async def test_filter_preserves_collapsed_dirs(tree_repo: Path) -> None:
    """
    Start state:  docs/ is collapsed by user
    Action:       toggle 'g' ON then OFF
    Expected:     docs/ remains collapsed after round-trip

    This verifies that the persistent _collapsed_dirs set survives
    filtering, where dirs that disappear from the filtered view don't
    lose their collapsed state.

        Before:          Filter ON:         Filter OFF:
        ▶ docs/          ▼ src/             ▶ docs/  ← still collapsed ✓
        ▼ src/             alpha.py         ▼ src/
          alpha.py (M)                        alpha.py
          beta.py                             beta.py
        main.py                             main.py
    """
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
