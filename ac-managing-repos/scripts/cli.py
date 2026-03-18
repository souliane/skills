#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["typer>=0.15", "rich"]
# requires-python = ">=3.12"
# ///
"""Cross-repo management CLI for maintained repositories.

Discovers repos by scanning T3_WORKSPACE_DIR for git repos matching
the MANAGED_REPOS regex from ~/.ac-managing-repos.
"""

import os
import re
import subprocess
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Manage a portfolio of maintained repositories.")
console = Console()

MAX_SCAN_DEPTH = 3
BYTES_PER_UNIT = 1024

# Config files this tool reads (and that the `config` command inventories)
CONFIG_FILES: dict[str, str] = {
    "~/.teatree": (
        "Teatree core config (shell-sourceable). Provides T3_WORKSPACE_DIR, T3_AUTO_SQUASH, T3_REVIEW_SKILL, etc."
    ),
    "~/.ac-reviewing-skills": "Skill ownership (shell-sourceable). Provides MAINTAINED_SKILLS regex.",
    "~/.ac-managing-repos": "Repo management (shell-sourceable). Provides MANAGED_REPOS regex, BOILERPLATE_MAP.",
    "~/.ac-writing-blog-posts.yml": "Blog publishing config (YAML). Outlet targets.",
}

# Data/cache directories this ecosystem uses
DATA_DIRS: dict[str, str] = {
    "${XDG_DATA_HOME:-~/.local/share}/teatree": (
        "Teatree runtime data (ticket cache, MR reminders, followup dashboard)."
    ),
}


def _parse_shell_config(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE pairs from a shell-sourceable config file."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _expand(value: str) -> str:
    """Expand $HOME and ~ in a config value."""
    return value.replace("$HOME", str(Path.home())).replace("~", str(Path.home()))


def load_config() -> dict[str, str]:
    path = Path("~/.ac-managing-repos").expanduser()
    if not path.exists():
        console.print(f"[red]Config not found:[/red] {path}")
        console.print("Create it with MANAGED_REPOS and BOILERPLATE_MAP. See SKILL.md for format.")
        raise typer.Exit(1)
    return _parse_shell_config(path)


def load_teatree_config() -> dict[str, str]:
    return _parse_shell_config(Path("~/.teatree").expanduser())


def get_workspace_dir() -> Path:
    teatree = load_teatree_config()
    raw = teatree.get("T3_WORKSPACE_DIR", "~/workspace")
    return Path(_expand(raw)).resolve()


def _scan_repos(workspace: Path, pattern: str) -> list[Path]:
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
    """Scan T3_WORKSPACE_DIR for git repos matching MANAGED_REPOS regex."""
    pattern = config.get("MANAGED_REPOS", "")
    if not pattern:
        console.print("[red]MANAGED_REPOS not set in ~/.ac-managing-repos[/red]")
        raise typer.Exit(1)
    return _scan_repos(get_workspace_dir(), pattern)


def parse_boilerplate_map(config: dict[str, str]) -> dict[str, list[str]]:
    raw = config.get("BOILERPLATE_MAP", "")
    if not raw:
        return {}
    result: dict[str, list[str]] = {}
    for part in raw.split(";"):
        cleaned = part.strip()
        if ":" not in cleaned:
            continue
        key, _, deps = cleaned.partition(":")
        result[key.strip()] = [d.strip() for d in deps.split(",") if d.strip()]
    return result


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


def get_stale_branches(repo: Path) -> list[str]:
    raw = git_output(repo, "branch", "--merged", "HEAD", "--no-color")
    if not raw:
        return []
    current = git_output(repo, "branch", "--show-current")
    default = git_output(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "--short").removeprefix("origin/")
    skip = {current, default, "main", "master"}
    return [
        b.strip().removeprefix("* ")
        for b in raw.splitlines()
        if b.strip().removeprefix("* ") not in skip and not b.strip().startswith("remotes/")
    ]


def _build_repo_status(path: Path) -> dict:
    """Collect git status for a single repo."""
    branch = git_output(path, "branch", "--show-current") or "(detached)"
    unpushed = get_unpushed(path)
    dirty = get_dirty_count(path)
    stale = get_stale_branches(path)
    no_upstream = bool(unpushed) and unpushed[0].startswith("(no upstream")
    n_unpushed = len(unpushed) if unpushed and not no_upstream else 0
    return {
        "branch": branch,
        "unpushed": unpushed,
        "n_unpushed": n_unpushed,
        "dirty": dirty,
        "stale": stale,
        "no_upstream": no_upstream,
    }


def _format_status(info: dict) -> str:
    if info["n_unpushed"] == 0 and info["dirty"] == 0 and not info["stale"] and not info["no_upstream"]:
        return "[green]clean[/green]"
    parts = []
    if info["n_unpushed"] > 0:
        parts.append("[yellow]needs push[/yellow]")
    if info["no_upstream"]:
        parts.append("[red]no upstream[/red]")
    if info["dirty"] > 0:
        parts.append("[yellow]dirty[/yellow]")
    if info["stale"]:
        parts.append("[dim]stale branches[/dim]")
    return ", ".join(parts)


@app.command()
def status(
    repo: Annotated[
        list[str] | None,
        typer.Option("--repo", "-r", help="Filter to specific repo(s) by directory name"),
    ] = None,
    *,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show individual commit lines")] = False,
) -> None:
    """Show delivery status across all managed repos."""
    config = load_config()
    paths = discover_repos(config)

    if repo:
        paths = [p for p in paths if p.name in repo]
        if not paths:
            console.print(f"[red]No matching repos for:[/red] {', '.join(repo)}")
            raise typer.Exit(1)

    table = Table(title="Managed Repos Status", show_lines=False)
    table.add_column("Repo", style="bold")
    table.add_column("Branch")
    table.add_column("Unpushed", justify="right")
    table.add_column("Dirty", justify="right")
    table.add_column("Stale branches", justify="right")
    table.add_column("Status")

    has_work = False
    details: list[tuple[str, list[str]]] = []

    for path in paths:
        info = _build_repo_status(path)
        has_work = has_work or _format_status(info) != "[green]clean[/green]"
        unpushed_str = str(info["n_unpushed"]) if not info["no_upstream"] else "?"
        stale_str = str(len(info["stale"])) if info["stale"] else "-"

        table.add_row(path.name, info["branch"], unpushed_str, str(info["dirty"]), stale_str, _format_status(info))

        if verbose and info["unpushed"] and not info["no_upstream"]:
            details.append((path.name, info["unpushed"]))

    console.print(table)

    if verbose and details:
        console.print()
        for name, commits in details:
            console.print(f"[bold]{name}[/bold] unpushed:")
            for line in commits:
                console.print(f"  {line}")
            console.print()

    if not has_work:
        console.print("\n[green]All repos are clean.[/green]")

    raise typer.Exit(0 if not has_work else 1)


@app.command("config")
def show_config() -> None:
    """Inventory all config, data, and cache files for managed repos."""
    table = Table(title="Configuration Files", show_lines=True)
    table.add_column("File", style="bold")
    table.add_column("Exists")
    table.add_column("Purpose")
    table.add_column("Keys / Values")

    for raw_path, purpose in CONFIG_FILES.items():
        path = Path(raw_path).expanduser()
        exists = path.exists()
        exists_str = "[green]yes[/green]" if exists else "[red]no[/red]"

        if exists:
            parsed = _parse_shell_config(path)
            if parsed:
                keys_str = "\n".join(f"[cyan]{k}[/cyan]={_truncate(v, 60)}" for k, v in parsed.items())
            elif raw_path.endswith(".yml"):
                keys_str = "[dim](YAML — use cat to inspect)[/dim]"
            else:
                keys_str = "[dim](empty)[/dim]"
        else:
            keys_str = "-"

        table.add_row(raw_path, exists_str, purpose, keys_str)

    console.print(table)
    console.print()

    # Data directories
    table2 = Table(title="Data / Cache Directories", show_lines=True)
    table2.add_column("Directory", style="bold")
    table2.add_column("Exists")
    table2.add_column("Purpose")
    table2.add_column("Size")

    for raw_path, purpose in DATA_DIRS.items():
        expanded = _expand_env(raw_path)
        path = Path(expanded).expanduser()
        exists = path.exists()
        exists_str = "[green]yes[/green]" if exists else "[red]no[/red]"
        size_str = _dir_size(path) if exists else "-"
        table2.add_row(raw_path, exists_str, purpose, size_str)

    console.print(table2)
    console.print()

    # Cross-check: detect issues
    console.print("[bold]Health Checks:[/bold]")
    _check_config_health()


def _check_config_health() -> None:
    """Detect common config issues and suggest improvements."""
    issues: list[str] = []

    mr_config = _parse_shell_config(Path("~/.ac-managing-repos").expanduser())
    if not mr_config.get("MANAGED_REPOS"):
        issues.append("[red]MANAGED_REPOS not set in ~/.ac-managing-repos[/red]")

    t3_config = _parse_shell_config(Path("~/.teatree").expanduser())
    if not t3_config.get("T3_WORKSPACE_DIR"):
        issues.append("[red]T3_WORKSPACE_DIR not set in ~/.teatree[/red]")

    rs_config = _parse_shell_config(Path("~/.ac-reviewing-skills").expanduser())
    if not rs_config.get("MAINTAINED_SKILLS"):
        issues.append("[yellow]MAINTAINED_SKILLS not set in ~/.ac-reviewing-skills[/yellow]")

    # Check overlap: for each managed repo, check if its path matches MAINTAINED_SKILLS
    managed_re = mr_config.get("MANAGED_REPOS", "")
    maintained_re = rs_config.get("MAINTAINED_SKILLS", "")
    if managed_re and maintained_re:
        workspace = Path(_expand(t3_config.get("T3_WORKSPACE_DIR", "~/workspace"))).resolve()
        managed_repos = _scan_repos(workspace, managed_re)
        maintained_regex = re.compile(maintained_re)

        # MAINTAINED_SKILLS matches full paths (with trailing /), so append /
        not_maintained = [
            p.name for p in managed_repos if not maintained_regex.search(str(p.relative_to(workspace)) + "/")
        ]

        if not_maintained:
            issues.append(
                f"[yellow]In MANAGED_REPOS but not matched by MAINTAINED_SKILLS:[/yellow] "
                f"{', '.join(sorted(not_maintained))} — consider adding to MAINTAINED_SKILLS if you own these"
            )

    # Check T3_REVIEW_SKILL chaining
    review_skill = t3_config.get("T3_REVIEW_SKILL")
    if review_skill:
        rs_cfg = _parse_shell_config(Path("~/.ac-reviewing-skills").expanduser())
        delivery_skill = rs_cfg.get("DELIVERY_SKILL")
        if not delivery_skill:
            issues.append(
                f"[yellow]T3_REVIEW_SKILL={review_skill} but DELIVERY_SKILL not set"
                " in ~/.ac-reviewing-skills[/yellow]"
                " — chain is incomplete (retro → review → ???)"
            )

    if not issues:
        console.print("  [green]All checks passed.[/green]")
    else:
        for issue in issues:
            console.print(f"  {issue}")


def _truncate(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[: max_len - 3] + "..."


def _expand_env(path: str) -> str:
    """Expand ${VAR:-default} patterns and ~."""

    def _repl(m: re.Match) -> str:
        var = m.group(1)
        default = m.group(2) or ""
        return os.environ.get(var, _expand(default))

    return re.sub(r"\$\{(\w+):-([^}]*)\}", _repl, path)


def _dir_size(path: Path) -> str:
    """Human-readable directory size."""
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < BYTES_PER_UNIT:
            return f"{total:.0f} {unit}"
        total /= BYTES_PER_UNIT
    return f"{total:.1f} TB"


if __name__ == "__main__":
    app()
