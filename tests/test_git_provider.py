"""Tests for GitProvider."""

from pathlib import Path

from dulwich import porcelain
from dulwich.repo import Repo

from gamr.models import GitStatus
from gamr.services.git_provider import DulwichGitProvider, NullGitProvider


def _init_repo(tmp_path: Path) -> Repo:
    """Helper to init a git repo with one committed file."""
    repo = Repo.init(str(tmp_path))
    # Create and commit a file
    f = tmp_path / "hello.txt"
    f.write_text("hello world\n")
    porcelain.add(repo, paths=["hello.txt"])
    porcelain.commit(
        repo,
        message=b"initial commit",
        committer=b"Test User <test@test.com>",
        author=b"Test User <test@test.com>",
    )
    return repo


def test_is_git_repo(tmp_path: Path) -> None:
    # Testing: DulwichGitProvider.is_git_repo() detection.
    # Input: first a plain directory (no .git), then same path after Repo.init.
    # Expected: False before init, True after.
    # Asserts: the provider correctly detects presence/absence of a git repository.
    provider = DulwichGitProvider(tmp_path)
    assert not provider.is_git_repo()

    Repo.init(str(tmp_path))
    provider = DulwichGitProvider(tmp_path)
    assert provider.is_git_repo()


def test_status_modified(tmp_path: Path) -> None:
    # Testing: get_status() detects a modified tracked file.
    # Input: committed hello.txt then overwritten with different content.
    # Expected: status map has hello.txt → MODIFIED.
    # Asserts: working tree changes to committed files are detected.
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("changed\n")

    provider = DulwichGitProvider(tmp_path)
    status = provider.get_status()

    assert (tmp_path / "hello.txt") in status
    assert status[tmp_path / "hello.txt"] == GitStatus.MODIFIED


def test_status_untracked(tmp_path: Path) -> None:
    # Testing: get_status() detects an untracked file.
    # Input: new.txt created but never added/committed.
    # Expected: status map has new.txt → UNTRACKED.
    # Asserts: files not in the index are correctly flagged as untracked.
    _init_repo(tmp_path)
    (tmp_path / "new.txt").write_text("new file\n")

    provider = DulwichGitProvider(tmp_path)
    status = provider.get_status()

    assert (tmp_path / "new.txt") in status
    assert status[tmp_path / "new.txt"] == GitStatus.UNTRACKED


def test_status_deleted(tmp_path: Path) -> None:
    # Testing: get_status() detects a deleted tracked file.
    # Input: committed hello.txt then deleted from disk.
    # Expected: status map has hello.txt → DELETED.
    # Asserts: removal of a tracked file is detected as a deletion.
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").unlink()

    provider = DulwichGitProvider(tmp_path)

    assert provider.get_status()[tmp_path / "hello.txt"] == GitStatus.DELETED


def test_discovers_repo_from_subdirectory(tmp_path: Path) -> None:
    # Testing: DulwichGitProvider discovers the repo when initialized from a subdirectory.
    # Input: git repo at tmp_path, provider opened on tmp_path/src.
    # Expected: is_git_repo=True, repo_root=tmp_path, src/module.py is UNTRACKED.
    # Asserts: upward repo discovery works and paths are resolved relative to the repo root.
    _init_repo(tmp_path)
    subdirectory = tmp_path / "src"
    subdirectory.mkdir()
    file = subdirectory / "module.py"
    file.write_text("x = 1\n")

    provider = DulwichGitProvider(subdirectory)

    assert provider.is_git_repo()
    assert provider.repo_root == tmp_path.resolve()
    assert provider.get_status()[file.resolve()] == GitStatus.UNTRACKED


def test_get_diff(tmp_path: Path) -> None:
    # Testing: get_diff() returns a unified diff for a modified file.
    # Input: hello.txt committed with "hello world" then changed to "changed content".
    # Expected: diff contains "-hello world" and "+changed content".
    # Asserts: the diff output correctly shows old and new content.
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("changed content\n")

    provider = DulwichGitProvider(tmp_path)
    diff = provider.get_diff(tmp_path / "hello.txt")

    assert "-hello world" in diff
    assert "+changed content" in diff


def test_get_file_stats(tmp_path: Path) -> None:
    # Testing: get_file_stats() returns lines added/removed counts.
    # Input: hello.txt changed from 1 line to 3 lines.
    # Expected: lines_added=3, lines_removed=1.
    # Asserts: diff stat computation correctly counts line-level changes.
    _init_repo(tmp_path)
    (tmp_path / "hello.txt").write_text("line1\nline2\nline3\n")

    provider = DulwichGitProvider(tmp_path)
    stats = provider.get_file_stats(tmp_path / "hello.txt")

    assert stats is not None
    assert stats.lines_added == 3
    assert stats.lines_removed == 1


def test_get_blame_info(tmp_path: Path) -> None:
    # Testing: get_blame_info() extracts author and timestamp from git history.
    # Input: hello.txt committed by "Test User".
    # Expected: last_author="Test User", last_modified > 0.
    # Asserts: blame metadata is correctly extracted from the commit that last touched the file.
    _init_repo(tmp_path)

    provider = DulwichGitProvider(tmp_path)
    info = provider.get_blame_info(tmp_path / "hello.txt")

    assert info is not None
    assert info.last_author == "Test User"
    assert info.last_modified > 0


def test_null_provider() -> None:
    # Testing: NullGitProvider returns safe empty/None values for all operations.
    # Input: NullGitProvider instance (used for non-git directories).
    # Expected: is_git_repo=False, empty status, empty diff, None for stats/blame.
    # Asserts: the null implementation is a safe no-op that never raises.
    provider = NullGitProvider()
    assert not provider.is_git_repo()
    assert provider.get_status() == {}
    assert provider.get_diff(Path("/fake")) == ""
    assert provider.get_file_stats(Path("/fake")) is None
    assert provider.get_blame_info(Path("/fake")) is None
