"""Tests for FileIndex build_fast and fill_line_counts."""

from pathlib import Path
from unittest.mock import MagicMock

from gamr.services.file_index import FileIndex
from gamr.services.file_scanner import FileScanner


def test_build_fast_skips_line_counts(tmp_path: Path) -> None:
    # Testing: build_fast() returns entries without row_count populated.
    # Input: two text files with known line counts (3 and 1 lines).
    # Expected: both entries have row_count=None — line counting is deferred.
    # Asserts: build_fast skips the expensive _count_lines call for faster startup.
    (tmp_path / "a.py").write_text("line1\nline2\nline3\n")
    (tmp_path / "b.py").write_text("x\n")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    entries = index.build_fast()
    assert len(entries) == 2
    for entry in entries:
        assert entry.row_count is None


def test_fill_line_counts_populates(tmp_path: Path) -> None:
    # Testing: fill_line_counts() fills in row_count after build_fast().
    # Input: two text files (3 lines and 1 line), built with build_fast().
    # Expected: row_count correctly set to 3 and 1; both paths in returned list.
    # Asserts: the deferred line counting produces correct results when run later.
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
    # Testing: fill_line_counts() skips binary files (leaves row_count as None).
    # Input: one binary file (contains null byte in first 8KB).
    # Expected: row_count stays None, empty updated list returned.
    # Asserts: binary detection (null byte check) prevents counting garbage lines.
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
    # Testing: the original build() still includes line counts (backwards compat).
    # Input: one text file with 2 lines.
    # Expected: row_count == 2 immediately after build().
    # Asserts: build() wasn't accidentally broken when build_fast() was added.
    (tmp_path / "a.py").write_text("one\ntwo\n")

    scanner = FileScanner(tmp_path)
    git = MagicMock()
    git.get_status.return_value = {}
    git.is_git_repo.return_value = False
    index = FileIndex(scanner, git)

    entries = index.build()
    assert entries[0].row_count == 2
