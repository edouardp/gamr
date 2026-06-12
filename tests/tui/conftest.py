"""Shared fixtures for TUI (pilot-based) tests."""

from pathlib import Path

import pytest
from dulwich import porcelain
from dulwich.repo import Repo


@pytest.fixture
def git_repo(tmp_path: Path):
    """Create a git repo with a modified file for testing."""
    repo = Repo.init(str(tmp_path))
    (tmp_path / "file.txt").write_text("original\n")
    porcelain.add(repo, paths=["file.txt"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")
    (tmp_path / "file.txt").write_text("modified\n")
    return tmp_path


@pytest.fixture
def tree_repo(tmp_path: Path):
    """Create a git repo with a directory structure for navigation tests."""
    repo = Repo.init(str(tmp_path))
    src = tmp_path / "src"
    src.mkdir()
    (src / "alpha.py").write_text("a = 1\n")
    (src / "beta.py").write_text("b = 2\n")
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "readme.md").write_text("# Hello\n")
    (tmp_path / "main.py").write_text("print('hi')\n")
    porcelain.add(repo, paths=["src/alpha.py", "src/beta.py", "docs/readme.md", "main.py"])
    porcelain.commit(repo, message=b"init", committer=b"T <t@t>", author=b"T <t@t>")
    # Modify one file for diff testing
    (src / "alpha.py").write_text("a = 1\nb = 2\nc = 3\n")
    return tmp_path
