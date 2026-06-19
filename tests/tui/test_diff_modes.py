"""Tests for diff mode cycling: d/D keys, scroll preservation.

Fixture `tree_repo` provides src/alpha.py which is git-modified:
    Original:  "a = 1\\n"
    Current:   "a = 1\\nb = 2\\nc = 3\\n"
This gives us a file with diff data to exercise all three modes.
"""

from pathlib import Path

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.preview_pane import PreviewPane


async def test_d_cycles_diff_mode_forward(tree_repo: Path) -> None:
    # Testing: 'd' key advances the diff mode to the next in the cycle.
    # Input: alpha.py selected (has diff), press 'd'.
    # Expected: diff mode changes from initial to the next mode.
    # Asserts: the diff mode cycling advances forward on 'd' press.
    """
    Start state:  preview showing alpha.py in initial diff mode
    Action:       press 'd'
    Expected:     diff mode advances to next in cycle

        Preview header shows: "alpha.py    full diff"
        After 'd':            "alpha.py    gutter"  (or next in prefs)
    """
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
    # Testing: 'D' key cycles the diff mode backward (reverse direction).
    # Input: advance mode twice with 'd', then go back once with 'D'.
    # Expected: final mode equals the mode after the first 'd'.
    # Asserts: reverse cycling correctly undoes one forward step.
    """
    Start state:  preview in some diff mode
    Actions:      'd' twice (advance), then 'D' once (go back)
    Expected:     lands on the same mode as after first 'd'

        Mode A  →d→  Mode B  →d→  Mode C  →D→  Mode B
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        await pilot.press("d")
        await pilot.pause()
        mode_after_d = app._diff_mode
        await pilot.press("d")
        await pilot.pause()
        await pilot.press("D")
        await pilot.pause()
        assert app._diff_mode == mode_after_d


async def test_diff_mode_cycles_through_preferences(tree_repo: Path) -> None:
    # Testing: pressing 'd' N times (N = number of modes) returns to the start.
    # Input: press 'd' for each mode in the preferences cycle.
    # Expected: final mode equals the starting mode (full cycle).
    # Asserts: the mode list is circular and wraps correctly.
    """
    Start state:  any diff mode
    Action:       press 'd' N times (where N = number of modes in preferences)
    Expected:     cycles back to the starting mode

        If prefs = [gutter, full]:
        gutter →d→ full →d→ gutter  (back to start)
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        start_mode = app._diff_mode
        for _ in range(len(app._prefs.diff_modes)):
            await pilot.press("d")
            await pilot.pause()

        assert app._diff_mode == start_mode


async def test_scroll_preserved_across_diff_mode_switch(tree_repo: Path) -> None:
    # Testing: scroll position (by source line) is preserved across a full diff mode cycle.
    # Input: note the source line at scroll position, cycle through all modes and back.
    # Expected: source line at scroll position is the same before and after.
    # Asserts: mode switching translates scroll offsets correctly between different row layouts.
    """
    Start state:  preview scrolled to source line X in one diff mode
    Action:       cycle through all modes and back
    Expected:     scroll position (by source line) is the same as before

        Preview at line 1 → d → d → ... → d → still at line 1

    This tests that the source line mapping correctly translates
    between modes with different display row counts (full diff has
    extra removed-line rows, unified only shows changes).
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)
        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        source_before = preview.get_source_line_at_scroll()

        for _ in range(len(app._prefs.diff_modes)):
            await pilot.press("d")
            await pilot.pause()

        source_after = preview.get_source_line_at_scroll()
        assert source_after == source_before
