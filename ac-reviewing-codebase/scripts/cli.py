#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["typer>=0.15", "rich"]
# requires-python = ">=3.12"
# ///
"""Deterministic checks and metrics for codebase review.

Subcommands:
    check   — Validate SKILL.md frontmatter in a tracked skills repo.
    status  — Show delivery status across all managed repos.
    config  — Inventory config files and health checks.
    assess  — Run deterministic codebase metrics (ruff, coverage, complexity, TODOs, deps).
"""

import json
import os
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Annotated, cast

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Deterministic checks and metrics for codebase review.")
console = Console()

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
REQUIRED_FRONTMATTER = ("name", "description")
REQUIRED_METADATA_FRONTMATTER = ("version",)
IGNORED_TOP_LEVEL_DIRS = {"external"}
MAX_SCAN_DEPTH = 3
BYTES_PER_UNIT = 1024
COVERAGE_GOOD_THRESHOLD = 80
COVERAGE_WARN_THRESHOLD = 60
CONFIG_PATH = Path("~/.ac-reviewing-codebase").expanduser()

CONFIG_FILES: dict[str, str] = {
    "~/.teatree.toml": ("Teatree core config (TOML). Provides workspace_dir, auto_squash, review_skill."),
    "~/.ac-reviewing-codebase": ("Codebase review config (shell). MAINTAINED_SKILLS, MANAGED_REPOS, BOILERPLATE_MAP."),
}

DATA_DIRS: dict[str, str] = {
    "${XDG_DATA_HOME:-~/.local/share}/teatree": (
        "Teatree runtime data (ticket cache, MR reminders, followup dashboard)."
    ),
}


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


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


def _expand_env(path: str) -> str:
    """Expand ${VAR:-default} patterns and ~."""

    def _repl(m: re.Match) -> str:
        var = m.group(1)
        default = m.group(2) or ""
        return os.environ.get(var, _expand(default))

    return re.sub(r"\$\{(\w+):-([^}]*)\}", _repl, path)


def _load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        console.print(f"[red]Config not found:[/red] {CONFIG_PATH}")
        console.print("Create it with MAINTAINED_SKILLS and MANAGED_REPOS. See SKILL.md.")
        raise typer.Exit(1)
    return _parse_shell_config(CONFIG_PATH)


def _parse_toml(path: Path) -> dict:
    """Parse a TOML file, returning empty dict if missing or invalid."""
    if not path.exists():
        return {}
    with path.open("rb") as f:
        return tomllib.load(f)


def _flatten_toml(data: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested TOML dict to dot-separated keys for display."""
    result: dict[str, str] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            result.update(_flatten_toml(value, full_key))
        else:
            result[full_key] = str(value)
    return result


def _get_workspace_dir() -> Path:
    """Read workspace_dir from ~/.teatree.toml or fall back to ~/workspace."""
    toml = _parse_toml(Path("~/.teatree.toml").expanduser())
    raw = toml.get("teatree", {}).get("workspace_dir", "~/workspace")
    return Path(_expand(str(raw))).resolve()


# ---------------------------------------------------------------------------
# Frontmatter validation (check command)
# ---------------------------------------------------------------------------


def _git_ls_files(root_dir: Path, *patterns: str) -> list[Path]:
    command = ["git", "-C", str(root_dir), "ls-files"]
    command.extend(patterns)
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    if result.returncode != 0:
        children = [d for d in root_dir.iterdir() if d.is_dir() and (d / ".git").exists()]
        if children:
            hint = ", ".join(d.name for d in children[:5])
            message = (
                f"{root_dir} is not a git repo, but contains git repos: {hint}. "
                f"Run with --root pointing to a specific repo (e.g., --root {children[0]})."
            )
        else:
            message = f"git ls-files failed for {root_dir}: {result.stderr.strip()}"
        raise RuntimeError(message)
    return sorted(root_dir / line for line in result.stdout.splitlines() if line)


class Finding:
    """A single check finding."""

    def __init__(self, root_dir: Path, path: Path, message: str) -> None:
        self.root_dir = root_dir
        self.path = path
        self.message = message

    def __str__(self) -> str:
        rel = self.path.relative_to(self.root_dir) if self.path.is_relative_to(self.root_dir) else self.path
        return f"  ERROR: {rel}: {self.message}"


def _parse_frontmatter(text: str) -> dict[str, object]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta: dict[str, object] = {}
    nested_key: str | None = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") and nested_key:
            stripped = line.strip()
            if ":" not in stripped:
                continue
            key, value = stripped.split(":", 1)
            nested = cast("dict[str, str]", meta.setdefault(nested_key, {}))
            nested[key.strip()] = value.strip().strip('"').strip("'")
            continue
        nested_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_value:
            meta[cleaned_key] = cleaned_value
        else:
            meta[cleaned_key] = {}
            nested_key = cleaned_key
    return meta


def _check_frontmatter(root_dir: Path, skill_files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in skill_files:
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        if not meta:
            findings.append(Finding(root_dir, path, "missing or invalid YAML frontmatter"))
            continue
        findings.extend(
            Finding(root_dir, path, f"missing required frontmatter field: {field}")
            for field in REQUIRED_FRONTMATTER
            if not meta.get(field)
        )
        metadata = meta.get("metadata")
        if not isinstance(metadata, dict):
            findings.append(Finding(root_dir, path, "missing required frontmatter field: metadata.version"))
            continue
        typed_metadata = cast("dict[str, str]", metadata)
        findings.extend(
            Finding(root_dir, path, f"missing required frontmatter field: metadata.{field}")
            for field in REQUIRED_METADATA_FRONTMATTER
            if not typed_metadata.get(field)
        )
    return findings


def _collect_files(root_dir: Path) -> dict[str, list[Path]]:
    tracked = [
        path
        for path in _git_ls_files(root_dir)
        if path.exists()
        and (not path.relative_to(root_dir).parts or path.relative_to(root_dir).parts[0] not in IGNORED_TOP_LEVEL_DIRS)
    ]
    skills = [path for path in tracked if path.name == "SKILL.md"]
    return {"skills": skills}


# ---------------------------------------------------------------------------
# Repo management (status / config commands)
# ---------------------------------------------------------------------------


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


def _discover_repos(config: dict[str, str]) -> list[Path]:
    pattern = config.get("MANAGED_REPOS", "")
    if not pattern:
        console.print("[red]MANAGED_REPOS not set in ~/.ac-reviewing-codebase[/red]")
        raise typer.Exit(1)
    return _scan_repos(_get_workspace_dir(), pattern)


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


def _git_output(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.stdout.strip()


def _git_ok(repo: Path, *args: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0


def _get_unpushed(repo: Path) -> list[str]:
    branch = _git_output(repo, "branch", "--show-current")
    if not branch:
        return []
    if not _git_ok(repo, "rev-parse", "--verify", "@{upstream}"):
        return [f"(no upstream for {branch})"]
    raw = _git_output(repo, "log", "--oneline", "@{upstream}..HEAD")
    return raw.splitlines() if raw else []


def _get_dirty_count(repo: Path) -> int:
    raw = _git_output(repo, "status", "--short", "--no-branch")
    return len(raw.splitlines()) if raw else 0


def _get_stale_branches(repo: Path) -> list[str]:
    raw = _git_output(repo, "branch", "--merged", "HEAD", "--no-color")
    if not raw:
        return []
    current = _git_output(repo, "branch", "--show-current")
    default = _git_output(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "--short").removeprefix("origin/")
    skip = {current, default, "main", "master"}
    return [
        b.strip().removeprefix("* ")
        for b in raw.splitlines()
        if b.strip().removeprefix("* ") not in skip and not b.strip().startswith("remotes/")
    ]


def _get_stash_count(repo: Path) -> int:
    raw = _git_output(repo, "stash", "list")
    return len(raw.splitlines()) if raw else 0


def _get_non_main_branches(repo: Path) -> list[str]:
    default = _git_output(repo, "config", "init.defaultBranch") or "main"
    raw = _git_output(repo, "branch", "--no-merged", default, "--no-color")
    if not raw:
        return []
    current = _git_output(repo, "branch", "--show-current")
    return [
        b.strip().removeprefix("* ").removeprefix("+ ")
        for b in raw.splitlines()
        if b.strip().removeprefix("* ").removeprefix("+ ") != current
    ]


def _get_dirty_files(repo: Path, limit: int = 5) -> list[str]:
    raw = _git_output(repo, "status", "--short", "--no-branch")
    lines = raw.splitlines() if raw else []
    return lines[:limit]


def _build_repo_status(path: Path) -> dict:
    branch = _git_output(path, "branch", "--show-current") or "(detached)"
    unpushed = _get_unpushed(path)
    dirty = _get_dirty_count(path)
    stale = _get_stale_branches(path)
    stashes = _get_stash_count(path)
    other_branches = _get_non_main_branches(path)
    dirty_files = _get_dirty_files(path)
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


def _is_clean(info: dict) -> bool:
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


def _format_status(info: dict) -> str:
    if _is_clean(info):
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


def _print_repo_detail(name: str, info: dict) -> None:
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


# ---------------------------------------------------------------------------
# Assess (deterministic metrics)
# ---------------------------------------------------------------------------


def _run_tool(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=cwd, check=False)


def _count_lint_violations(root: Path) -> dict[str, object]:
    result = _run_tool(["ruff", "check", "--output-format", "json", "."], cwd=root)
    if result.returncode == 0:
        return {"total": 0, "by_category": {}}
    try:
        violations = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return {"error": "ruff not available or produced invalid output"}
    by_code: dict[str, int] = {}
    for v in violations:
        code = v.get("code", "unknown")
        by_code[code] = by_code.get(code, 0) + 1
    return {"total": len(violations), "by_category": dict(sorted(by_code.items(), key=lambda x: -x[1])[:20])}


def _count_todos(root: Path) -> dict[str, object]:
    result = _run_tool(
        [
            "grep",
            "-rn",
            r"TODO\|FIXME\|HACK\|XXX",
            "--include=*.py",
            "--include=*.ts",
            "--include=*.js",
            "--exclude-dir=.venv",
            "--exclude-dir=node_modules",
            "--exclude-dir=.tox",
            ".",
        ],
        cwd=root,
    )
    lines = result.stdout.strip().splitlines() if result.stdout else []
    by_type: dict[str, int] = {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}
    for line in lines:
        for marker in by_type:
            if marker in line:
                by_type[marker] += 1
    return {"total": len(lines), "by_type": {k: v for k, v in by_type.items() if v > 0}}


def _count_complexity(root: Path) -> dict[str, object]:
    result = _run_tool(["ruff", "check", "--select", "C901", "--output-format", "json", "."], cwd=root)
    try:
        violations = json.loads(result.stdout) if result.stdout else []
    except (json.JSONDecodeError, ValueError):
        return {"error": "ruff not available"}
    return {"violations": len(violations)}


def _check_coverage(root: Path) -> dict[str, object]:
    coverage_file = root / ".coverage"
    if not coverage_file.exists():
        return {"available": False}
    result = _run_tool(["coverage", "json", "-o", "/dev/stdout"], cwd=root)
    try:
        data = json.loads(result.stdout)
        return {"available": True, "percent": data.get("totals", {}).get("percent_covered", 0)}
    except (json.JSONDecodeError, ValueError):
        return {"available": False, "error": "coverage json failed"}


def _check_outdated_deps(root: Path) -> dict[str, object]:
    if not (root / "pyproject.toml").exists():
        return {"available": False}
    result = _run_tool(["uv", "pip", "list", "--outdated", "--format", "json"], cwd=root)
    try:
        packages = json.loads(result.stdout) if result.stdout else []
        return {"available": True, "outdated_count": len(packages), "packages": packages[:10]}
    except (json.JSONDecodeError, ValueError):
        return {"available": False, "error": "uv pip list failed"}


def _count_suppressions(root: Path) -> dict[str, int]:
    """Count lint suppressions (noqa, type: ignore, pragma: no cover)."""
    counts: dict[str, int] = {}
    patterns = {
        "noqa": r"# noqa",
        "type_ignore": r"# type: ignore",
        "pragma_no_cover": r"# pragma: no cover",
    }
    for name, pattern in patterns.items():
        result = _run_tool(
            [
                "grep",
                "-rn",
                pattern,
                "--include=*.py",
                "--exclude-dir=.venv",
                "--exclude-dir=node_modules",
                "--exclude-dir=.tox",
                ".",
            ],
            cwd=root,
        )
        lines = result.stdout.strip().splitlines() if result.stdout else []
        if lines:
            counts[name] = len(lines)
    return counts


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def check(
    root: Annotated[Path, typer.Option(help="Repository root to check")] = Path.cwd(),
) -> None:
    """Validate SKILL.md frontmatter in a tracked skills repo."""
    root_dir = root.resolve()
    files = _collect_files(root_dir)
    findings: list[Finding] = []
    findings.extend(_check_frontmatter(root_dir, files["skills"]))
    if findings:
        print(f"Errors ({len(findings)}):")
        for finding in findings:
            print(finding)
        print("FAIL")
        raise typer.Exit(1)
    print("PASS")


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
    config = _load_config()
    paths = _discover_repos(config)
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
    table.add_column("Stashes", justify="right")
    table.add_column("Branches", justify="right")
    table.add_column("Status")
    has_work = False
    detail_repos: list[tuple[str, dict]] = []
    for path in paths:
        info = _build_repo_status(path)
        has_work = has_work or not _is_clean(info)
        unpushed_str = str(info["n_unpushed"]) if not info["no_upstream"] else "?"
        stash_str = str(info["stashes"]) if info["stashes"] else "-"
        branch_str = str(len(info["other_branches"])) if info["other_branches"] else "-"
        table.add_row(
            path.name,
            info["branch"],
            unpushed_str,
            str(info["dirty"]),
            stash_str,
            branch_str,
            _format_status(info),
        )
        if verbose and (info["unpushed"] or info["dirty_files"] or info["other_branches"] or info["stashes"]):
            detail_repos.append((path.name, info))
    console.print(table)
    if verbose and detail_repos:
        console.print()
        for name, info in detail_repos:
            _print_repo_detail(name, info)
    if not has_work:
        console.print("\n[green]All repos are clean.[/green]")
    elif has_work:
        raise typer.Exit(1)


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
            parsed = _flatten_toml(_parse_toml(path)) if raw_path.endswith(".toml") else _parse_shell_config(path)
            keys_str = (
                "\n".join(f"[cyan]{k}[/cyan]={_truncate(str(v), 60)}" for k, v in parsed.items())
                if parsed
                else "[dim](empty)[/dim]"
            )
        else:
            keys_str = "-"
        table.add_row(raw_path, exists_str, purpose, keys_str)
    console.print(table)
    console.print()
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
    console.print("[bold]Health Checks:[/bold]")
    _check_config_health()


@app.command()
def assess(
    root: Annotated[Path, typer.Option(help="Repository root to assess")] = Path.cwd(),
    *,
    output_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run deterministic codebase metrics."""
    root_dir = root.resolve()
    metrics = {
        "lint": _count_lint_violations(root_dir),
        "todos": _count_todos(root_dir),
        "complexity": _count_complexity(root_dir),
        "coverage": _check_coverage(root_dir),
        "dependencies": _check_outdated_deps(root_dir),
        "suppressions": _count_suppressions(root_dir),
    }
    if output_json:
        print(json.dumps(metrics, indent=2))
        return
    console.print("[bold]Codebase Metrics[/bold]")
    console.print()
    _print_lint(metrics["lint"])
    _print_todos(metrics["todos"])
    _print_complexity(metrics["complexity"])
    _print_coverage(metrics["coverage"])
    _print_deps(metrics["dependencies"])
    _print_suppressions(metrics["suppressions"])


# ---------------------------------------------------------------------------
# Assess output helpers
# ---------------------------------------------------------------------------


def _print_lint(lint: dict) -> None:
    if "error" in lint:
        console.print(f"  Lint: [red]{lint['error']}[/red]")
    else:
        color = "green" if lint["total"] == 0 else "yellow"
        console.print(f"  Lint violations: [{color}]{lint['total']}[/{color}]")
        if lint.get("by_category"):
            for code, count in list(lint["by_category"].items())[:10]:
                console.print(f"    {code}: {count}")


def _print_todos(todos: dict) -> None:
    console.print(f"  TODOs/FIXMEs: {todos['total']}")
    if todos.get("by_type"):
        parts = [f"{k}={v}" for k, v in todos["by_type"].items()]
        console.print(f"    {', '.join(parts)}")


def _print_complexity(cx: dict) -> None:
    if "error" in cx:
        console.print(f"  Complexity: [red]{cx['error']}[/red]")
    else:
        console.print(f"  Complex functions (C901): {cx['violations']}")


def _print_coverage(cov: dict) -> None:
    if cov.get("available"):
        pct = cov["percent"]
        color = "green" if pct >= COVERAGE_GOOD_THRESHOLD else "yellow" if pct >= COVERAGE_WARN_THRESHOLD else "red"
        console.print(f"  Test coverage: [{color}]{pct:.1f}%[/{color}]")
    else:
        console.print("  Test coverage: [dim]no .coverage file[/dim]")


def _print_deps(deps: dict) -> None:
    if deps.get("available"):
        n = deps["outdated_count"]
        color = "green" if n == 0 else "yellow"
        console.print(f"  Outdated deps: [{color}]{n}[/{color}]")
    else:
        console.print("  Outdated deps: [dim]not a uv project[/dim]")


def _print_suppressions(supps: dict) -> None:
    if supps:
        total = sum(supps.values())
        console.print(f"  Lint suppressions: [yellow]{total}[/yellow]")
        for name, count in supps.items():
            console.print(f"    {name}: {count}")
    else:
        console.print("  Lint suppressions: [green]0[/green]")


# ---------------------------------------------------------------------------
# Config health checks
# ---------------------------------------------------------------------------


def _check_config_health() -> None:
    issues: list[str] = []
    config = _parse_shell_config(CONFIG_PATH)
    if not config.get("MANAGED_REPOS"):
        issues.append("[yellow]MANAGED_REPOS not set in ~/.ac-reviewing-codebase[/yellow]")
    if not config.get("MAINTAINED_SKILLS"):
        issues.append("[yellow]MAINTAINED_SKILLS not set in ~/.ac-reviewing-codebase[/yellow]")
    if not issues:
        console.print("  [green]All checks passed.[/green]")
    else:
        for issue in issues:
            console.print(f"  {issue}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _truncate(value: str, max_len: int) -> str:
    return value if len(value) <= max_len else value[: max_len - 3] + "..."


def _dir_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < BYTES_PER_UNIT:
            return f"{total:.0f} {unit}"
        total /= BYTES_PER_UNIT
    return f"{total:.1f} TB"


if __name__ == "__main__":  # pragma: no cover
    app()
