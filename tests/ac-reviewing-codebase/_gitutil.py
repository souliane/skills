"""Shared git helpers for ac-reviewing-codebase tests.

Several test modules need a throwaway git repo. Keeping one copy here
avoids the git-binary / run_git triplication across test files.
"""

import shutil
import subprocess
from pathlib import Path


def _git_binary() -> str:
    git = shutil.which("git")
    assert git is not None
    return git


GIT = _git_binary()


# A fixture repo must not depend on the developer's global git config. With
# `commit.gpgsign = true` set globally, every commit here goes through gpg —
# and a stale keyring lock left by a dead process then fails the whole suite
# with an error that says nothing about the code under test.
NO_SIGNING = ("-c", "commit.gpgsign=false")


def run_git(cwd: Path, *args: str) -> None:
    subprocess.run([GIT, *NO_SIGNING, *args], cwd=cwd, check=True, capture_output=True, text=True)


def init_repo(path: Path) -> Path:
    """Create an empty git repo on ``main`` with a configured identity.

    No initial commit — callers add their own files and commit via
    :func:`run_git` so each test controls exactly what is tracked.
    """
    path.mkdir(parents=True, exist_ok=True)
    run_git(path, "init", "-q", "-b", "main")
    run_git(path, "config", "user.email", "test@test.com")
    run_git(path, "config", "user.name", "Test")
    return path
