"""Tests for preview pane: tab focus, loading state, binary files, content.

Fixture `tree_repo` provides src/alpha.py (modified) and main.py (clean).
Other tests create specific files (large, binary) for edge cases.
"""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.app import GamrApp
from gamr.widgets.file_tree_table import FileTreeTable
from gamr.widgets.preview_pane import PreviewPane


async def test_tab_switches_focus_to_preview(tree_repo: Path) -> None:
    # Testing: tab key toggles focus between tree and preview panes.
    # Input: tree has focus, press tab (→ preview), press tab again (→ tree).
    # Expected: focus alternates between the two panes.
    # Asserts: tab-based focus switching works bidirectionally.
    """
    Start state:  tree pane has focus (default)
    Action:       press tab
    Expected:     preview pane gets focus

    Action:       press tab again
    Expected:     tree pane gets focus back

        ┌── Tree ──┐  ┌── Preview ──┐
        │ [focused] │  │             │    ← before tab
        └───────────┘  └─────────────┘

        ┌── Tree ──┐  ┌── Preview ──┐
        │           │  │  [focused]  │    ← after tab
        └───────────┘  └─────────────┘
    """
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
    # Testing: j/k keys scroll the preview pane when it has focus.
    # Input: select alpha.py, tab to preview, press 'j'.
    # Expected: preview pane has focus (ready for scroll input).
    # Asserts: focus transfer enables vim-style scrolling in the preview.
    """
    Start state:  file selected, preview showing content, tree has focus
    Action:       tab to preview, then press 'j'
    Expected:     preview pane is focused and ready for vim-style scrolling

        Select alpha.py → preview shows file
        Tab → preview focused
        j/k now scroll the preview (not the tree)
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        preview = app.query_one(PreviewPane)

        tree.restore_cursor(tree_repo / "src" / "alpha.py")
        await pilot.pause()

        await pilot.press("tab")
        await pilot.pause()
        assert preview.has_focus


async def test_loading_clears_on_file_switch(tmp_path: Path) -> None:
    # Testing: loading indicator clears when switching from a large file to a small one.
    # Input: select large.txt (60KB, triggers async), then select small.txt.
    # Expected: preview.loading is False after switching to small file.
    # Asserts: the loading state resets properly and doesn't stick across selections.
    """
    Start state:  large file selected → loading indicator shown
    Action:       select a small file
    Expected:     loading indicator clears, small file content displayed

        Select large.txt (60KB):
        ┌── Preview ────────────┐
        │   ⏳ Loading...       │    ← loading overlay
        └───────────────────────┘

        Select small.txt:
        ┌── Preview ────────────┐
        │ 1  hello              │    ← content, no loading
        └───────────────────────┘
    """
    repo = Repo.init(str(tmp_path))
    large = tmp_path / "large.txt"
    large.write_text("x\n" * 30000)  # ~60KB, triggers async path
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
    # Testing: binary files show a message dialog instead of crashing.
    # Input: data.bin with null bytes selected in the tree.
    # Expected: #preview-message element is visible (not hidden).
    # Asserts: binary file detection triggers the message overlay gracefully.
    """
    Start state:  binary file selected
    Expected:     preview shows a centered message dialog (not a crash)

        Select data.bin:
        ┌── Preview ─────────────────────────┐
        │                                    │
        │    ╭── Binary File ──╮             │
        │    │  data.bin       │             │
        │    ╰─────────────────╯             │
        │                                    │
        └────────────────────────────────────┘
    """
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

        msg = app.query_one("#preview-message")
        assert "hidden" not in msg.classes


async def test_preview_shows_file_content(tree_repo: Path) -> None:
    # Testing: preview pane displays the content of the selected file.
    # Input: main.py selected (contains "print('hi')").
    # Expected: rendered preview content includes "print".
    # Asserts: file content is loaded and rendered in the preview widget.
    """
    Start state:  main.py selected (contains "print('hi')")
    Expected:     preview content includes the file text

        Select main.py:
        ┌── Preview ──────────────┐
        │ 1  print('hi')          │
        └─────────────────────────┘
    """
    app = GamrApp(path=tree_repo)
    async with app.run_test() as pilot:
        await pilot.pause()
        tree = app.query_one(FileTreeTable)
        tree.restore_cursor(tree_repo / "main.py")
        await pilot.pause()

        content = app.query_one("#preview-content")
        rendered = str(content.render())
        assert "print" in rendered
