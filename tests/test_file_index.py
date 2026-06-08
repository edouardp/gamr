"""Tests for FileIndex service."""

from pathlib import Path

from dulwich.repo import Repo

from fooey.services.file_index import FileIndex
from fooey.services.file_scanner import FileScanner
from fooey.services.git_provider import DulwichGitProvider, GitStatus


def test_build_index_with_git(tmp_path: Path) -> None:
    repo = Repo.init(str(tmp_path))
    (tmp_path / "a.py").write_text("x = 1\n")
    repo.stage(["a.py"])
    repo.do_commit(b"init", committer=b"A <a@a>", author=b"A <a@a>")
    (tmp_path / "a.py").write_text("x = 2\n")
    (tmp_path / "b.txt").write_text("new\n")

    scanner = FileScanner(tmp_path)
    git = DulwichGitProvider(tmp_path)
    index = FileIndex(scanner, git)
    entries = index.build()

    paths = {e.path.name: e for e in entries}
    assert "a.py" in paths
    assert paths["a.py"].git_status == GitStatus.MODIFIED
    assert paths["a.py"].lines_added == 1
    assert paths["b.txt"].git_status == GitStatus.UNTRACKED


def test_build_index_no_git(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("data")

    scanner = FileScanner(tmp_path)
    from fooey.services.git_provider import NullGitProvider
    git = NullGitProvider()
    index = FileIndex(scanner, git)
    entries = index.build()

    assert len(entries) == 1
    assert entries[0].path.name == "file.txt"
    assert entries[0].size > 0
    assert entries[0].git_status is None


def test_update_blame(tmp_path: Path) -> None:
    repo = Repo.init(str(tmp_path))
    (tmp_path / "a.py").write_text("x = 1\n")
    repo.stage(["a.py"])
    repo.do_commit(b"init", committer=b"Bob <b@b>", author=b"Bob <b@b>")

    scanner = FileScanner(tmp_path)
    git = DulwichGitProvider(tmp_path)
    index = FileIndex(scanner, git)
    index.build()

    entry = index.update_blame(tmp_path / "a.py")
    assert entry is not None
    assert entry.last_author == "Bob"
    assert entry.last_git_modified is not None
