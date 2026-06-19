"""Tests for FileIndex build_fast and fill_line_counts."""

from pathlib import Path
from unittest.mock import MagicMock

from gamr.services.file_index import FileIndex
from gamr.services.file_scanner import FileScanner


def test_build_fast_skips_line_counts(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    (tmp_path / "b.py").write_text("x\n")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    entries = index.build_fast()
    assert len(entries) == 2
    # row_count should be None (skipped)
    for entry in entries:
        assert entry.row_count is None


def test_fill_line_counts_populates(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    (tmp_path / "b.py").write_text("x\n")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    index.build_fast()
    updated = index.fill_line_counts()

    assert len(updated) == 2
    counts = {e.path.name: e.row_count for e in index.entries.values()}
    assert counts["a.py"] == 3
    assert counts["b.py"] == 1


def test_fill_line_counts_skips_binary(tmp_path: Path) -> None:
    (tmp_path / "bin.dat").write_bytes(b"\x00\x01\x02\x03")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    index.build_fast()
    updated = index.fill_line_counts()

    assert updated == []
    entry = list(index.entries.values())[0]
    assert entry.row_count is None


def test_build_includes_line_counts(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text("one\ntwo\n")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    entries = index.build()
    assert entries[0].row_count == 2
