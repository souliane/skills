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

import functools
import json
import os
import re
import shutil
import subprocess
import tempfile
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
COVERAGE_GOOD_THRESHOLD = 80
COVERAGE_WARN_THRESHOLD = 60
CONFIG_PATH = Path("~/.ac-reviewing-codebase").expanduser()

CONFIG_FILES: dict[str, str] = {
    "~/.ac-reviewing-codebase": (
        "Codebase review config (shell). WORKSPACE_DIR, MAINTAINED_SKILLS, MANAGED_REPOS, BOILERPLATE_MAP."
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
    """Expand a leading ``~`` (or ``$HOME``) to the home directory.

    Only the leading path component is expanded; a ``~`` elsewhere in the value
    is a literal character (e.g. a backup-file suffix like ``foo~``), not a home
    reference, so it is left untouched.
    """
    home = str(Path.home())
    expanded = value.replace("$HOME", home)
    if expanded.startswith("~"):
        expanded = home + expanded[1:]
    return expanded


def _load_config() -> dict[str, str]:
    if not CONFIG_PATH.exists():
        console.print(f"[red]Config not found:[/red] {CONFIG_PATH}")
        console.print("Create it with MAINTAINED_SKILLS and MANAGED_REPOS. See SKILL.md.")
        raise typer.Exit(1)
    return _parse_shell_config(CONFIG_PATH)


def _get_workspace_dir() -> Path:
    """Read ``WORKSPACE_DIR`` from ~/.ac-reviewing-codebase, defaulting to ~/workspace."""
    config = _parse_shell_config(CONFIG_PATH)
    raw = config.get("WORKSPACE_DIR", "~/workspace")
    return Path(_expand(raw)).resolve()


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


BLOCK_SCALAR_INDICATORS = {">", "|", ">-", "|-"}


def _parse_frontmatter(text: str) -> dict[str, object]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    meta: dict[str, object] = {}
    nested_key: str | None = None
    folded_key: str | None = None
    for raw_line in match.group(1).splitlines():
        line = raw_line.rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") and folded_key:
            existing = cast("str", meta.get(folded_key, ""))
            meta[folded_key] = f"{existing} {line.strip()}".strip()
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
        folded_key = None
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        cleaned_key = key.strip()
        cleaned_value = value.strip().strip('"').strip("'")
        if cleaned_value in BLOCK_SCALAR_INDICATORS:
            # YAML folded (``>``) / literal (``|``) scalar: the value is on the
            # following indented lines. Accumulate them (space-joined) rather
            # than storing the ``>`` marker as the value.
            meta[cleaned_key] = ""
            folded_key = cleaned_key
        elif cleaned_value:
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


def _default_branch(repo: Path) -> str:
    """Resolve the repo's default branch.

    Prefer ``origin/HEAD`` (the real remote default); fall back to the local
    ``init.defaultBranch`` config, then ``main``. Single source of truth so
    every caller detects the default the same way.
    """
    origin_head = _git_output(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "--short")
    if origin_head:
        return origin_head.removeprefix("origin/")
    return _git_output(repo, "config", "init.defaultBranch") or "main"


def _strip_branch_marker(line: str) -> str:
    """Strip git's ``* `` (current) / ``+ `` (worktree-checked-out) branch markers."""
    return line.strip().removeprefix("* ").removeprefix("+ ")


def _get_stale_branches(repo: Path) -> list[str]:
    raw = _git_output(repo, "branch", "--merged", "HEAD", "--no-color")
    if not raw:
        return []
    current = _git_output(repo, "branch", "--show-current")
    default = _default_branch(repo)
    skip = {current, default, "main", "master"}
    return [
        _strip_branch_marker(b)
        for b in raw.splitlines()
        if _strip_branch_marker(b) not in skip and not b.strip().startswith("remotes/")
    ]


def _get_stash_count(repo: Path) -> int:
    raw = _git_output(repo, "stash", "list")
    return len(raw.splitlines()) if raw else 0


def _get_non_main_branches(repo: Path) -> list[str]:
    default = _default_branch(repo)
    raw = _git_output(repo, "branch", "--no-merged", default, "--no-color")
    if not raw:
        return []
    current = _git_output(repo, "branch", "--show-current")
    return [_strip_branch_marker(b) for b in raw.splitlines() if _strip_branch_marker(b) != current]


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


@functools.cache
def _ruff_cmd() -> tuple[str, ...]:
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


def _run_tool(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, capture_output=True, text=True, timeout=120, cwd=cwd, check=False)


def _count_lint_violations(root: Path) -> dict[str, object]:
    result = _run_tool([*_ruff_cmd(), "check", "--output-format", "json", "."], cwd=root)
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


_SCAN_INCLUDES = ("*.py", "*.ts", "*.js")


def _is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


def _scan_lines(root: Path, regex: str, includes: tuple[str, ...] = _SCAN_INCLUDES) -> list[str]:
    """Grep ``regex`` over ``includes``-matching files under ``root``.

    In a git repo, only **tracked** files are scanned (``git grep``), so a
    vendored ``.venv`` or a nested agent worktree under ``.claude/worktrees``
    cannot inflate the count — git grep never sees untracked/ignored paths,
    and a nested worktree is a separate repo whose files are untracked here.
    Outside a git repo (e.g. a unit-test ``tmp_path``) it falls back to a
    filtered recursive grep so the metric still works.
    """
    if _is_git_repo(root):
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
    result = _run_tool(
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


_TODO_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def _strip_grep_location(line: str) -> str:
    """Drop the ``path:lineno:`` prefix ``grep -n`` emits, keeping the content.

    Without this a path like ``fixtures/XXX/a.py`` counts as a marker, and the
    line number column can never be told apart from code.
    """
    return line.split(":", 2)[-1]


def _count_todos(root: Path) -> dict[str, object]:
    # `total` and `by_type` must describe the same thing. Counting `total` as
    # matched *lines* while incrementing every marker whose name appears
    # anywhere in the line made them disagree (a dict literal naming all four
    # markers scored 4), so attribute each line to its first marker only and
    # derive the total from the buckets.
    #
    # The grep stays a plain alternation: `git grep -E` is POSIX ERE and has no
    # `\b`, so a word-boundary pattern there matches nothing at all rather than
    # erroring. Word-boundary precision belongs in Python, where the dialect is
    # ours — grep only has to over-select.
    by_type: dict[str, int] = {"TODO": 0, "FIXME": 0, "HACK": 0, "XXX": 0}
    for line in _scan_lines(root, "TODO|FIXME|HACK|XXX"):
        match = _TODO_MARKER_RE.search(_strip_grep_location(line))
        if match:
            by_type[match.group(1)] += 1
    return {
        "total": sum(by_type.values()),
        "by_type": {k: v for k, v in by_type.items() if v > 0},
    }


def _count_complexity(root: Path) -> dict[str, object]:
    result = _run_tool([*_ruff_cmd(), "check", "--select", "C901", "--output-format", "json", "."], cwd=root)
    try:
        violations = json.loads(result.stdout) if result.stdout else []
    except (json.JSONDecodeError, ValueError):
        return {"error": "ruff not available"}
    return {"violations": len(violations)}


def _check_coverage(root: Path) -> dict[str, object]:
    coverage_file = root / ".coverage"
    if not coverage_file.exists():
        return {"available": False}
    # `coverage json -o /dev/stdout` fails on real repos (coverage opens the
    # path for atomic-rename write); use a real temp file and read it back.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "coverage.json"
        _run_tool(["coverage", "json", "-o", str(out)], cwd=root)
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            return {"available": True, "percent": data.get("totals", {}).get("percent_covered", 0)}
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {"available": False, "error": "coverage json failed"}


def _check_outdated_deps(root: Path) -> dict[str, object]:
    if not (root / "pyproject.toml").exists():
        return {"available": False}
    # `uv pip list` reports the *active* environment. Run from this skill's
    # runtime it would report the assessor's own deps for every repo
    # (identical false hits everywhere). Scope to the target repo's venv;
    # if it has none, the check is genuinely unavailable — never substitute
    # the assessor's environment.
    venv_python = root / ".venv" / "bin" / "python"
    if not venv_python.exists():
        return {"available": False, "error": "no repo venv (cannot scope dependency check)"}
    result = _run_tool(
        ["uv", "pip", "list", "--outdated", "--format", "json", "--python", str(venv_python)],
        cwd=root,
    )
    try:
        packages = json.loads(result.stdout) if result.stdout else []
        return {"available": True, "outdated_count": len(packages), "packages": packages[:10]}
    except (json.JSONDecodeError, ValueError):
        return {"available": False, "error": "uv pip list failed"}


def _count_suppressions(root: Path) -> dict[str, int]:
    """Count lint suppressions (noqa, type: ignore, pragma: no cover).

    A suppression only counts as one when it is a real trailing comment. The
    same text inside a string literal is a *mention* — a linter's own pattern
    table, a test fixture asserting on the marker — and counting those made
    every repo that reasons about suppressions look like it was drowning in
    them. Requiring the ``#`` not to be immediately preceded by a quote drops
    the mentions without needing to parse Python.
    """
    counts: dict[str, int] = {}
    patterns = {
        "noqa": "# noqa",
        "type_ignore": "# type: ignore",
        "pragma_no_cover": "# pragma: no cover",
    }
    for name, pattern in patterns.items():
        real = re.compile(rf"""(?:^|[^"'#]){re.escape(pattern)}""")
        lines = [
            line for line in _scan_lines(root, pattern, includes=("*.py",)) if real.search(_strip_grep_location(line))
        ]
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
    else:
        raise typer.Exit(1)


@app.command("config")
def show_config() -> None:
    """Inventory config files and run health checks for managed repos."""
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
    elif deps.get("error"):
        console.print(f"  Outdated deps: [dim]{deps['error']}[/dim]")
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


_REPO_ALTERNATION_RE = re.compile(r"([\w.-]+)/\(([^)]+)\)")
_REPO_LITERAL_RE = re.compile(r"^([\w.-]+/[\w.-]+)\$?$")


def unresolvable_managed_repos(config: dict[str, str]) -> list[str]:
    """Repos named literally in MANAGED_REPOS that are not git repos on disk.

    MANAGED_REPOS is a regex, so the set of repos it *intends* cannot be
    enumerated in general — but the literal alternations people actually write
    (``org/(a|b|c)$``) can be. Without this, a repo that is renamed or deleted
    just stops matching: it silently drops out of every review while the config
    still claims it, which is how two long-dead repos stayed listed for months.
    """
    workspace = _get_workspace_dir()
    pattern = config.get("MANAGED_REPOS", "")
    named: set[str] = set()
    for org, alternatives in _REPO_ALTERNATION_RE.findall(pattern):
        named |= {f"{org}/{alt.strip()}" for alt in alternatives.split("|") if alt.strip()}
    # Whatever is left once the `org/(a|b)` groups are removed splits cleanly on
    # `|`, because the only pipes that survive are the top-level alternation.
    for branch in _REPO_ALTERNATION_RE.sub("", pattern).split("|"):
        literal = _REPO_LITERAL_RE.match(branch.strip())
        if literal:
            named.add(literal.group(1))
    return sorted(repo for repo in named if not (workspace / repo / ".git").exists())


def _check_config_health() -> None:
    issues: list[str] = []
    config = _parse_shell_config(CONFIG_PATH)
    if not config.get("MANAGED_REPOS"):
        issues.append("[yellow]MANAGED_REPOS not set in ~/.ac-reviewing-codebase[/yellow]")
    if not config.get("MAINTAINED_SKILLS"):
        issues.append("[yellow]MAINTAINED_SKILLS not set in ~/.ac-reviewing-codebase[/yellow]")
    issues += [
        f"[yellow]MANAGED_REPOS names '{repo}', which is not a git repo under {_get_workspace_dir()}[/yellow]"
        for repo in unresolvable_managed_repos(config)
    ]
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


if __name__ == "__main__":  # pragma: no cover
    app()
