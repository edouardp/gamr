"""Tests for GitProvider."""

import os
from pathlib import Path

from dulwich.repo import Repo

from fooey.services.git_provider import DulwichGitProvider, GitStatus, NullGitProvider


def _init_repo(tmp_path: Path) -> Repo:
    """Helper to init a git repo with one committed file."""
    repo = Repo.init(str(tmp_path))
    # Create and commit a file
    f = tmp_path / "hello.txt"
    f.write_text("hello world\n")
    repo.stage(["hello.txt"])
    repo.do_commit(
        b"initial commit",
        committer=b"Test User <test@test.com>",
        author=b"Test User <test@test.com>",
    )
    return repo


def test_is_git_repo(tmp_path: Path) -> None:
    provider = DulwichGitProvider(tmp_path)
    assert not provider.is_git_repo()

    Repo.init(str(tmp_path))
    provider = DulwichGitProvider(tmp_path)
    assert provider.is_git_repo()


def test_status_modified(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("changed\n")

    provider = DulwichGitProvider(tmp_path)
    status = provider.get_status()

    assert (tmp_path / "hello.txt") in status
    assert status[tmp_path / "hello.txt"] == GitStatus.MODIFIED


def test_status_untracked(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("new file\n")

    provider = DulwichGitProvider(tmp_path)
    status = provider.get_status()

    assert (tmp_path / "new.txt") in status
    assert status[tmp_path / "new.txt"] == GitStatus.UNTRACKED


def test_get_diff(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("changed content\n")

    provider = DulwichGitProvider(tmp_path)
    diff = provider.get_diff(tmp_path / "hello.txt")

    assert "-hello world" in diff
    assert "+changed content" in diff


def test_get_file_stats(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("line1\nline2\nline3\n")

    provider = DulwichGitProvider(tmp_path)
    stats = provider.get_file_stats(tmp_path / "hello.txt")

    assert stats is not None
    assert stats.lines_added == 3
    assert stats.lines_removed == 1


def test_get_blame_info(tmp_path: Path) -> None:
    _init_repo(tmp_path)

    provider = DulwichGitProvider(tmp_path)
    info = provider.get_blame_info(tmp_path / "hello.txt")

    assert info is not None
    assert info.last_author == "Test User"
    assert info.last_modified > 0


def test_null_provider() -> None:
    provider = NullGitProvider()
    assert not provider.is_git_repo()
    assert provider.get_status() == {}
    assert provider.get_diff(Path("/fake")) == ""
    assert provider.get_file_stats(Path("/fake")) is None
    assert provider.get_blame_info(Path("/fake")) is None
