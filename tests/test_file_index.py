"""Tests for FileIndex service."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.models import GitStatus
from gamr.services.file_index import FileIndex
from gamr.services.file_scanner import FileScanner
from gamr.services.git_provider import DulwichGitProvider


def test_build_index_with_git(tmp_path: Path) -> None:
    repo = Repo.init(str(tmp_path))
    (tmp_path / "a.py").write_text("x = 1\n")
    porcelain.add(repo, paths=["a.py"])
    porcelain.commit(repo, message=b"init", committer=b"A <a@a>", author=b"A <a@a>")
    (tmp_path / "a.py").write_text("x = 2\n")
    (tmp_path / "b.txt").write_text("new\n")

    scanner = FileScanner(tmp_path)
    git = DulwichGitProvider(tmp_path)
    index = FileIndex(scanner, git)
    entries = index.build()

    paths = {e.path.name: e for e in entries}
    assert "a.py" in paths
    assert paths["a.py"].git_status == GitStatus.MODIFIED
    # Diff stats are deferred — not populated by build()
    assert paths["a.py"].lines_added is None
    assert paths["b.txt"].git_status == GitStatus.UNTRACKED

    # But update_diff_stats populates them
    index.update_diff_stats(tmp_path / "a.py")
    assert paths["a.py"].lines_added == 1


def test_build_index_no_git(tmp_path: Path) -> None:
    (tmp_path / "file.txt").write_text("data")

    scanner = FileScanner(tmp_path)
    from gamr.services.git_provider import NullGitProvider

    git = NullGitProvider()
    index = FileIndex(scanner, git)
    entries = index.build()

    assert len(entries) == 1
    assert entries[0].path.name == "file.txt"
    assert entries[0].size > 0
    assert entries[0].git_status is None


def test_build_index_keeps_deleted_git_files(tmp_path: Path) -> None:
    repo = Repo.init(str(tmp_path))
    deleted = tmp_path / "deleted.txt"
    deleted.write_text("old\n")
    porcelain.add(repo, paths=["deleted.txt"])
    porcelain.commit(repo, message=b"init", committer=b"A <a@a>", author=b"A <a@a>")
    deleted.unlink()

    index = FileIndex(FileScanner(tmp_path), DulwichGitProvider(tmp_path))
    entries = index.build()

    assert [(entry.path, entry.git_status) for entry in entries] == [(deleted, GitStatus.DELETED)]


def test_update_blame(tmp_path: Path) -> None:
    repo = Repo.init(str(tmp_path))
    (tmp_path / "a.py").write_text("x = 1\n")
    porcelain.add(repo, paths=["a.py"])
    porcelain.commit(repo, message=b"init", committer=b"Bob <b@b>", author=b"Bob <b@b>")

    scanner = FileScanner(tmp_path)
    git = DulwichGitProvider(tmp_path)
    index = FileIndex(scanner, git)
    index.build()

    entry = index.update_blame(tmp_path / "a.py")
    assert entry is not None
    assert entry.last_author == "Bob"
    assert entry.last_git_modified is not None
