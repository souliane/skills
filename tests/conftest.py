"""Root conftest — shared fixtures for all skill tests."""

import os


def _strip_git_hook_env() -> None:
    """Strip GIT_* env vars inherited from pre-commit hooks.

    When pytest runs as a prek/pre-commit hook via ``git commit -a``, git sets
    ``GIT_INDEX_FILE`` to ``.git/index.lock``. Hook subprocesses inherit this,
    so any git operation in a test (e.g. ``git init`` in a temp dir) corrupts
    the parent repo's index. Stripping all ``GIT_*`` vars at session start
    prevents this. See https://github.com/j178/prek/issues/1786.
    """
    for var in list(os.environ):
        if var.startswith("GIT_"):
            del os.environ[var]


_strip_git_hook_env()
