"""The deterministic numbers behind ``assess``: lint, TODOs, complexity, coverage, deps, suppressions."""

import functools
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ui import console

COVERAGE_GOOD_THRESHOLD = 80
COVERAGE_WARN_THRESHOLD = 60

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


def count_lint_violations(root: Path) -> dict[str, object]:
    result = run_tool([*ruff_cmd(), "check", "--output-format", "json", "."], cwd=root)
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


def is_git_repo(root: Path) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    return result.returncode == 0 and result.stdout.strip() == "true"


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


_TODO_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def strip_grep_location(line: str) -> str:
    """Drop the ``path:lineno:`` prefix ``grep -n`` emits, keeping the content.

    Without this a path like ``fixtures/XXX/a.py`` counts as a marker, and the
    line number column can never be told apart from code.
    """
    return line.split(":", 2)[-1]


def count_todos(root: Path) -> dict[str, object]:
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
    for line in scan_lines(root, "TODO|FIXME|HACK|XXX"):
        match = _TODO_MARKER_RE.search(strip_grep_location(line))
        if match:
            by_type[match.group(1)] += 1
    return {
        "total": sum(by_type.values()),
        "by_type": {k: v for k, v in by_type.items() if v > 0},
    }


def count_complexity(root: Path) -> dict[str, object]:
    result = run_tool([*ruff_cmd(), "check", "--select", "C901", "--output-format", "json", "."], cwd=root)
    try:
        violations = json.loads(result.stdout) if result.stdout else []
    except (json.JSONDecodeError, ValueError):
        return {"error": "ruff not available"}
    return {"violations": len(violations)}


def check_coverage(root: Path) -> dict[str, object]:
    coverage_file = root / ".coverage"
    if not coverage_file.exists():
        return {"available": False}
    # `coverage json -o /dev/stdout` fails on real repos (coverage opens the
    # path for atomic-rename write); use a real temp file and read it back.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "coverage.json"
        run_tool(["coverage", "json", "-o", str(out)], cwd=root)
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
            return {"available": True, "percent": data.get("totals", {}).get("percent_covered", 0)}
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            return {"available": False, "error": "coverage json failed"}


def check_outdated_deps(root: Path) -> dict[str, object]:
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
    result = run_tool(
        ["uv", "pip", "list", "--outdated", "--format", "json", "--python", str(venv_python)],
        cwd=root,
    )
    try:
        packages = json.loads(result.stdout) if result.stdout else []
        return {"available": True, "outdated_count": len(packages), "packages": packages[:10]}
    except (json.JSONDecodeError, ValueError):
        return {"available": False, "error": "uv pip list failed"}


def count_suppressions(root: Path) -> dict[str, int]:
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
            line for line in scan_lines(root, pattern, includes=("*.py",)) if real.search(strip_grep_location(line))
        ]
        if lines:
            counts[name] = len(lines)
    return counts


def collect(root: Path) -> dict[str, object]:
    """Every metric for ``root``, in the shape ``assess --json`` prints."""
    return {
        "lint": count_lint_violations(root),
        "todos": count_todos(root),
        "complexity": count_complexity(root),
        "coverage": check_coverage(root),
        "dependencies": check_outdated_deps(root),
        "suppressions": count_suppressions(root),
    }


def print_report(metrics: dict) -> None:
    console.print("[bold]Codebase Metrics[/bold]")
    console.print()
    _print_lint(metrics["lint"])
    _print_todos(metrics["todos"])
    _print_complexity(metrics["complexity"])
    _print_coverage(metrics["coverage"])
    _print_deps(metrics["dependencies"])
    _print_suppressions(metrics["suppressions"])


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
