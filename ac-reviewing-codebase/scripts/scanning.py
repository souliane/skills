"""Running external tools over a repo, and grepping only the files it tracks."""

import functools
import shutil
import subprocess
from pathlib import Path

SCAN_INCLUDES = ("*.py", "*.ts", "*.js")


@functools.cache
def ruff_cmd() -> tuple[str, ...]:
    """Return a runnable ruff invocation.

    `shutil.which("ruff")` can return a pyenv shim that fails at dispatch when
    the active Python version doesn't have ruff installed. Smoke-test with
    `--version` before trusting the resolved path; otherwise fall back to
    `uv tool run ruff`, which is always available in this skill's runtime.
    """
    ruff = shutil.which("ruff")
    if ruff:
        probe = subprocess.run(
            [ruff, "--version"],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if probe.returncode == 0:
            return (ruff,)
    return ("uv", "tool", "run", "ruff")


def run_tool(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=cwd, check=False)


def is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def tracked_under(root: Path, entry: str) -> bool:
    """Whether the repo tracks any file under ``entry``."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "--", entry],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return bool(result.stdout.strip())


def scan_lines(root: Path, regex: str, includes: tuple[str, ...] = SCAN_INCLUDES) -> list[str]:
    """Grep ``regex`` over ``includes``-matching files under ``root``.

    In a git repo, only **tracked** files are scanned (``git grep``), so a
    vendored ``.venv`` or a nested agent worktree under ``.claude/worktrees``
    cannot inflate the count — git grep never sees untracked/ignored paths,
    and a nested worktree is a separate repo whose files are untracked here.
    Outside a git repo (e.g. a unit-test ``tmp_path``) it falls back to a
    filtered recursive grep so the metric still works.
    """
    if is_git_repo(root):
        result = subprocess.run(
            ["git", "-C", str(root), "grep", "-nIE", regex, "--", *includes],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        # git grep: 0 = matches, 1 = no matches; >1 = real error -> fs fallback.
        if result.returncode in {0, 1}:
            return result.stdout.strip().splitlines() if result.stdout else []
    includes_glob = [f"--include={g}" for g in includes]
    result = run_tool(
        [
            "grep",
            "-rnIE",
            regex,
            *includes_glob,
            "--exclude-dir=.venv",
            "--exclude-dir=node_modules",
            "--exclude-dir=.tox",
            "--exclude-dir=.git",
            "--exclude-dir=.claude",
            ".",
        ],
        cwd=root,
    )
    return result.stdout.strip().splitlines() if result.stdout else []


def scan_files(root: Path, regex: str, includes: tuple[str, ...] = SCAN_INCLUDES) -> list[str]:
    """Repo-relative paths of the ``includes``-matching files that contain ``regex``.

    Same tracked-only guarantee as :func:`scan_lines`; used when the caller has
    to open the file itself rather than judge a grep line.
    """
    return sorted({grep_path(line) for line in _matching_paths(root, regex, includes)})


def _matching_paths(root: Path, regex: str, includes: tuple[str, ...]) -> list[str]:
    if is_git_repo(root):
        result = subprocess.run(
            ["git", "-C", str(root), "grep", "-lIE", regex, "--", *includes],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if result.returncode in {0, 1}:
            return result.stdout.splitlines()
    includes_glob = [f"--include={g}" for g in includes]
    result = run_tool(
        [
            "grep",
            "-rlIE",
            regex,
            *includes_glob,
            "--exclude-dir=.venv",
            "--exclude-dir=node_modules",
            "--exclude-dir=.tox",
            "--exclude-dir=.git",
            "--exclude-dir=.claude",
            ".",
        ],
        cwd=root,
    )
    return result.stdout.splitlines()


def strip_grep_location(line: str) -> str:
    """Drop the ``path:lineno:`` prefix ``grep -n`` emits, keeping the content.

    Without this a path like ``fixtures/XXX/a.py`` counts as a marker, and the
    line number column can never be told apart from code.
    """
    return line.split(":", 2)[-1]


def grep_path(line: str) -> str:
    """The repo-relative path a ``grep -n`` line came from.

    ``git grep`` emits repo-relative paths; the filesystem fallback runs with
    ``cwd=root`` and emits ``./``-prefixed ones. Both must key the same way,
    because that key is what decides vendored from first-party.
    """
    return line.split(":", 1)[0].removeprefix("./")
