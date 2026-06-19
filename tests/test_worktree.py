"""Integration tests for git worktree support."""

import subprocess
from pathlib import Path

import pytest
from dulwich import porcelain
from dulwich.repo import Repo

from gamr.models import GitStatus
from gamr.services.git_provider import DulwichGitProvider


@pytest.fixture
def worktree_setup(tmp_path: Path) -> tuple[Path, Path]:
    """Create a repo with a linked worktree. Returns (main_dir, worktree_dir)."""
    main_dir = tmp_path / "main"
    main_dir.mkdir()
    repo = Repo.init(str(main_dir))
    # Initial commit (required before worktree add)
    f = main_dir / "hello.txt"
    f.write_text("hello world\n")
    porcelain.add(repo, paths=["hello.txt"])
    porcelain.commit(
        repo,
        message=b"initial commit",
        committer=b"Test User <test@test.com>",
        author=b"Test User <test@test.com>",
    )
    # Create a branch and worktree using git CLI (dulwich has no worktree add)
    wt_dir = tmp_path / "feature"
    subprocess.run(
        ["git", "worktree", "add", str(wt_dir), "-b", "feature"],
        cwd=main_dir,
        check=True,
        capture_output=True,
    )
    return main_dir, wt_dir


@pytest.fixture
def _skip_if_no_git() -> None:
    """Skip tests if git binary is not available."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        pytest.skip("git binary not available")


pytestmark = pytest.mark.usefixtures("_skip_if_no_git")


def test_worktree_root_detection(worktree_setup: tuple[Path, Path]) -> None:
    _, wt_dir = worktree_setup
    provider = DulwichGitProvider(wt_dir)

    assert provider.is_git_repo()
    assert provider.repo_root == wt_dir.resolve()


def test_worktree_git_common_dir(worktree_setup: tuple[Path, Path]) -> None:
    main_dir, wt_dir = worktree_setup
    provider = DulwichGitProvider(wt_dir)

    common = provider.git_common_dir
    assert common is not None
    # Common dir should point to the main repo's .git/
    assert common == (main_dir / ".git").resolve()


def test_worktree_git_dir_is_per_worktree(worktree_setup: tuple[Path, Path]) -> None:
    main_dir, wt_dir = worktree_setup
    provider = DulwichGitProvider(wt_dir)

    git_dir = provider.git_dir
    assert git_dir is not None
    # Per-worktree gitdir lives inside main/.git/worktrees/
    assert "worktrees" in str(git_dir)


def test_worktree_status(worktree_setup: tuple[Path, Path]) -> None:
    _, wt_dir = worktree_setup
    (wt_dir / "hello.txt").write_text("modified in worktree\n")

    provider = DulwichGitProvider(wt_dir)
    status = provider.get_status()

    assert (wt_dir / "hello.txt").resolve() in status
    assert status[(wt_dir / "hello.txt").resolve()] == GitStatus.MODIFIED


def test_worktree_diff(worktree_setup: tuple[Path, Path]) -> None:
    _, wt_dir = worktree_setup
    (wt_dir / "hello.txt").write_text("changed\n")

    provider = DulwichGitProvider(wt_dir)
    diff = provider.get_diff(wt_dir / "hello.txt")

    assert "-hello world" in diff
    assert "+changed" in diff


def test_worktree_blame(worktree_setup: tuple[Path, Path]) -> None:
    _, wt_dir = worktree_setup

    provider = DulwichGitProvider(wt_dir)
    info = provider.get_blame_info(wt_dir / "hello.txt")

    assert info is not None
    assert info.last_author == "Test User"


def test_worktree_subdirectory(worktree_setup: tuple[Path, Path]) -> None:
    """Provider works when started from a subdirectory of the worktree."""
    _, wt_dir = worktree_setup
    sub = wt_dir / "src"
    sub.mkdir()
    (sub / "mod.py").write_text("x = 1\n")

    provider = DulwichGitProvider(sub)

    assert provider.is_git_repo()
    assert provider.repo_root == wt_dir.resolve()
    assert provider.get_status()[(sub / "mod.py").resolve()] == GitStatus.UNTRACKED
