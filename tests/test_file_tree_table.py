"""Tests for FileTreeTable widget."""

from pathlib import Path

from textual.app import App, ComposeResult

from gamr.models import FileEntry, GitStatus
from gamr.widgets.file_tree_table import FileTreeTable


class TreeApp(App):
    def __init__(self) -> None:
        super().__init__()
        self.highlighted_paths: list[Path | None] = []

    def compose(self) -> ComposeResult:
        yield FileTreeTable()

    def on_file_tree_table_node_highlighted(self, event: FileTreeTable.NodeHighlighted) -> None:
        self.highlighted_paths.append(event.entry.path if event.entry else None)


async def test_tree_loads_entries() -> None:
    app = TreeApp()
    async with app.run_test() as pilot:
        tree = app.query_one(FileTreeTable)
        entries = [
            FileEntry(
                path=Path("/root/src/main.py"),
                size=1024,
                mtime=0,
                git_status=GitStatus.MODIFIED,
                lines_added=3,
                lines_removed=1,
            ),
            FileEntry(path=Path("/root/README.md"), size=200, mtime=0, git_status=None),
        ]
        tree.load_entries(entries, Path("/root"))
        await pilot.pause()

        # Should have rows: src/ dir + main.py + README.md = 3 rows
        assert tree.row_count == 3


async def test_tree_has_proper_columns() -> None:
    app = TreeApp()
    async with app.run_test() as pilot:
        tree = app.query_one(FileTreeTable)
        entries = [
            FileEntry(
                path=Path("/root/mod.py"),
                size=100,
                mtime=0,
                git_status=GitStatus.MODIFIED,
                lines_added=5,
                lines_removed=2,
            ),
        ]
        tree.load_entries(entries, Path("/root"))
        await pilot.pause()

        # Should have Name + St + +/- + Size + Modified = 5 columns
        assert len(tree.columns) == 5


async def test_toggle_collapse() -> None:
    app = TreeApp()
    async with app.run_test() as pilot:
        tree = app.query_one(FileTreeTable)
        entries = [
            FileEntry(path=Path("/root/src/a.py"), size=100, mtime=0),
            FileEntry(path=Path("/root/src/b.py"), size=100, mtime=0),
        ]
        tree.load_entries(entries, Path("/root"))
        await pilot.pause()

        # src/ dir + a.py + b.py = 3 rows
        assert tree.row_count == 3

        # Collapse the dir (first row)
        tree.move_cursor(row=0)
        tree.action_toggle_node()
        await pilot.pause()

        # Only src/ dir visible now
        assert tree.row_count == 1


async def test_restore_cursor_can_suppress_highlight_event() -> None:
    app = TreeApp()
    async with app.run_test() as pilot:
        tree = app.query_one(FileTreeTable)
        target = Path("/root/b.py")
        tree.load_entries(
            [FileEntry(path=Path("/root/a.py")), FileEntry(path=target)],
            Path("/root"),
        )
        await pilot.pause()
        app.highlighted_paths.clear()

        tree.restore_cursor(target)
        await pilot.pause()

        assert tree.get_current_entry().path == target
