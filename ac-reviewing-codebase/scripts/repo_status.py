"""Discovering the managed repos and reading each one's delivery status from git."""

import os
import re
import subprocess
from pathlib import Path

import typer
from review_config import get_workspace_dir
from ui import console

MAX_SCAN_DEPTH = 3


def scan_repos(workspace: Path, pattern: str) -> list[Path]:
    """Find git repos under workspace matching a regex."""
    regex = re.compile(pattern)
    repos: list[Path] = []
    for root, dirs, _files in os.walk(str(workspace), topdown=True):
        root_path = Path(root)
        if (root_path / ".git").exists() or (root_path / ".git").is_file():
            rel = str(root_path.relative_to(workspace))
            if regex.search(rel):
                repos.append(root_path)
                dirs.clear()
                continue
        depth = len(root_path.relative_to(workspace).parts)
        if depth >= MAX_SCAN_DEPTH:
            dirs.clear()
    return sorted(repos, key=lambda p: p.name)


def discover_repos(config: dict[str, str]) -> list[Path]:
    pattern = config.get("MANAGED_REPOS", "")
    if not pattern:
        console.print("[red]MANAGED_REPOS not set in ~/.ac-reviewing-codebase[/red]")
        raise typer.Exit(1)
    return scan_repos(get_workspace_dir(), pattern)


def git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip()


def git_ok(repo: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0


def get_unpushed(repo: Path) -> list[str]:
    branch = git_output(repo, "branch", "--show-current")
    if not branch:
        return []
    if not git_ok(repo, "rev-parse", "--verify", "@{upstream}"):
        return [f"(no upstream for {branch})"]
    raw = git_output(repo, "log", "--oneline", "@{upstream}..HEAD")
    return raw.splitlines() if raw else []


def get_dirty_count(repo: Path) -> int:
    raw = git_output(repo, "status", "--short", "--no-branch")
    return len(raw.splitlines()) if raw else 0


def default_branch(repo: Path) -> str:
    """Resolve the repo's default branch.

    Prefer ``origin/HEAD`` (the real remote default); fall back to the local
    ``init.defaultBranch`` config, then ``main``. Single source of truth so
    every caller detects the default the same way.
    """
    origin_head = git_output(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "--short")
    if origin_head:
        return origin_head.removeprefix("origin/")
    return git_output(repo, "config", "init.defaultBranch") or "main"


def strip_branch_marker(line: str) -> str:
    """Strip git's ``* `` (current) / ``+ `` (worktree-checked-out) branch markers."""
    return line.strip().removeprefix("* ").removeprefix("+ ")


def get_stale_branches(repo: Path) -> list[str]:
    raw = git_output(repo, "branch", "--merged", "HEAD", "--no-color")
    if not raw:
        return []
    current = git_output(repo, "branch", "--show-current")
    default = default_branch(repo)
    skip = {current, default, "main", "master"}
    return [
        strip_branch_marker(b)
        for b in raw.splitlines()
        if strip_branch_marker(b) not in skip and not b.strip().startswith("remotes/")
    ]


def get_stash_count(repo: Path) -> int:
    raw = git_output(repo, "stash", "list")
    return len(raw.splitlines()) if raw else 0


def get_non_main_branches(repo: Path) -> list[str]:
    default = default_branch(repo)
    raw = git_output(repo, "branch", "--no-merged", default, "--no-color")
    if not raw:
        return []
    current = git_output(repo, "branch", "--show-current")
    return [strip_branch_marker(b) for b in raw.splitlines() if strip_branch_marker(b) != current]


def get_dirty_files(repo: Path, limit: int = 5) -> list[str]:
    raw = git_output(repo, "status", "--short", "--no-branch")
    lines = raw.splitlines() if raw else []
    return lines[:limit]


def build_repo_status(path: Path) -> dict:
    branch = git_output(path, "branch", "--show-current") or "(detached)"
    unpushed = get_unpushed(path)
    dirty = get_dirty_count(path)
    stale = get_stale_branches(path)
    stashes = get_stash_count(path)
    other_branches = get_non_main_branches(path)
    dirty_files = get_dirty_files(path)
    no_upstream = bool(unpushed) and unpushed[0].startswith("(no upstream")
    n_unpushed = len(unpushed) if unpushed and not no_upstream else 0
    return {
        "branch": branch,
        "unpushed": unpushed,
        "n_unpushed": n_unpushed,
        "dirty": dirty,
        "dirty_files": dirty_files,
        "stale": stale,
        "stashes": stashes,
        "other_branches": other_branches,
        "no_upstream": no_upstream,
    }


def is_clean(info: dict) -> bool:
    return not any(
        [
            info["n_unpushed"],
            info["dirty"],
            info["stale"],
            info["no_upstream"],
            info["stashes"],
            info["other_branches"],
        ]
    )


def format_status(info: dict) -> str:
    if is_clean(info):
        return "[green]clean[/green]"
    parts = []
    if info["n_unpushed"] > 0:
        parts.append("[yellow]needs push[/yellow]")
    if info["no_upstream"]:
        parts.append("[red]no upstream[/red]")
    if info["dirty"] > 0:
        parts.append("[yellow]dirty[/yellow]")
    if info["stashes"]:
        parts.append("[magenta]stashes[/magenta]")
    if info["other_branches"]:
        parts.append("[cyan]branches[/cyan]")
    if info["stale"]:
        parts.append("[dim]stale[/dim]")
    return ", ".join(parts)


def print_repo_detail(name: str, info: dict) -> None:
    console.print(f"[bold]{name}[/bold]:")
    if info["unpushed"] and not info["no_upstream"]:
        for line in info["unpushed"]:
            console.print(f"  [yellow]\u2191[/yellow] {line}")
    if info["dirty_files"]:
        for line in info["dirty_files"]:
            console.print(f"  [dim]{line}[/dim]")
        if info["dirty"] > len(info["dirty_files"]):
            console.print(f"  [dim]  \u2026 and {info['dirty'] - len(info['dirty_files'])} more[/dim]")
    if info["other_branches"]:
        console.print(f"  [cyan]branches:[/cyan] {', '.join(info['other_branches'])}")
    if info["stashes"]:
        console.print(f"  [magenta]stashes:[/magenta] {info['stashes']}")
    console.print()
