"""Tests for FileScanner service."""

import time
from pathlib import Path
from queue import Queue

from watchdog.events import DirMovedEvent, FileMovedEvent

from gamr.services.file_scanner import ChangeType, FileChange, FileScanner, _Handler


def test_scan_finds_files(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.py").write_text("x = 1")

    scanner = FileScanner(tmp_path)
    files = scanner.scan()

    names = {f.name for f in files}
    assert "a.txt" in names
    assert "b.py" in names


def test_scan_ignores_git_dir(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")
    (tmp_path / "real.txt").write_text("data")

    scanner = FileScanner(tmp_path)
    files = scanner.scan()

    names = {f.name for f in files}
    assert "real.txt" in names
    assert "config" not in names


def test_explicit_empty_ignore_patterns_disables_defaults(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("")

    scanner = FileScanner(tmp_path, ignore_patterns=[])

    assert tmp_path / ".git" / "config" in scanner.scan()


def test_polling_detects_changes(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("v1")
    scanner = FileScanner(tmp_path)
    scanner._polling = True
    scanner._poll_snapshot = scanner._build_snapshot()

    # Create a new file
    (tmp_path / "b.txt").write_text("new")
    scanner.poll_changes()

    changes = scanner.drain()
    assert any(c.change_type == ChangeType.CREATED and c.path.name == "b.txt" for c in changes)


def test_watchdog_detects_creation(tmp_path: Path) -> None:
    scanner = FileScanner(tmp_path)
    scanner.start_watching()
    try:
        time.sleep(0.2)
        (tmp_path / "new.txt").write_text("hi")
        time.sleep(0.5)
        changes = scanner.drain()
        assert any(c.path.name == "new.txt" for c in changes)
    finally:
        scanner.stop()


def test_handler_translates_move_to_delete_and_create(tmp_path: Path) -> None:
    queue: Queue[FileChange] = Queue()
    handler = _Handler(tmp_path, queue, lambda _path: False)
    source = tmp_path / "old.txt"
    destination = tmp_path / "new.txt"

    handler.on_moved(FileMovedEvent(str(source), str(destination)))

    changes = [queue.get_nowait(), queue.get_nowait()]
    assert changes == [
        FileChange(source, ChangeType.DELETED),
        FileChange(destination, ChangeType.CREATED),
    ]


def test_handler_emits_change_for_directory_move(tmp_path: Path) -> None:
    queue: Queue[FileChange] = Queue()
    handler = _Handler(tmp_path, queue, lambda _path: False)

    handler.on_moved(DirMovedEvent(str(tmp_path / "old-dir"), str(tmp_path / "new-dir")))

    assert queue.qsize() == 2
