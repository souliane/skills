"""The deterministic numbers behind ``assess``: lint, TODOs, complexity, coverage, deps, suppressions.

Every count that can span vendored code is reported per scope rather than as
one figure, because a single number over a fork and its vendored upstream
describes neither. What counts as vendored is decided in ``vendored_paths``;
rendering lives in ``metrics_report``.
"""

import json
import re
import tempfile
from collections.abc import Sequence
from pathlib import Path

import suppressions
import vendored_paths
from scanning import grep_path, ruff_cmd, run_tool, scan_lines, strip_grep_location
from vendored_paths import SCOPES, VendoredPaths

# Assessing a repo must never change it. `[tool.ruff] fix = true` is a common
# setting, and without this flag `ruff check` REWRITES the tree it was asked to
# measure — this command silently edited four unrelated files before the flag
# was added.
NO_FIX = "--no-fix"

COVERAGE_GOOD_THRESHOLD = 80
COVERAGE_WARN_THRESHOLD = 60

_TODO_MARKER_RE = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b")


def count_lint_violations(root: Path) -> dict[str, object]:
    result = run_tool([*ruff_cmd(), "check", NO_FIX, "--output-format", "json", "."], cwd=root)
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


def count_todos(root: Path, vendored: VendoredPaths) -> dict[str, object]:
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
    by_scope: dict[str, int] = dict.fromkeys(SCOPES, 0)
    for line in scan_lines(root, "TODO|FIXME|HACK|XXX"):
        match = _TODO_MARKER_RE.search(strip_grep_location(line))
        if match:
            by_type[match.group(1)] += 1
            by_scope[vendored.scope_of(grep_path(line))] += 1
    return {
        "total": sum(by_type.values()),
        "by_type": {k: v for k, v in by_type.items() if v > 0},
        "scopes": by_scope,
    }


def count_complexity(root: Path) -> dict[str, object]:
    result = run_tool([*ruff_cmd(), "check", NO_FIX, "--select", "C901", "--output-format", "json", "."], cwd=root)
    try:
        violations = json.loads(result.stdout) if result.stdout else []
    except (json.JSONDecodeError, ValueError):
        return {"error": "ruff not available"}
    return {"violations": len(violations)}


def check_coverage(root: Path, vendored: VendoredPaths) -> dict[str, object]:
    """Line/branch coverage from ``.coverage``, split by scope.

    The percentage alone invites a false "coverage regressed" read whenever the
    enforced floor belongs to one lane and the measurement spans more than that
    lane. Reporting per-scope percentages and the file counts behind them says
    plainly what the number covers.
    """
    if not (root / ".coverage").exists():
        return {"available": False}
    # `coverage json -o /dev/stdout` fails on real repos (coverage opens the
    # path for atomic-rename write); use a real temp file and read it back.
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "coverage.json"
        result = run_tool(["coverage", "json", "-o", str(out)], cwd=root)
        try:
            data = json.loads(out.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, ValueError):
            # Never report this as "no .coverage file": a stale data file
            # naming a since-deleted module fails here while the file is right
            # there, and blaming the wrong cause sends the reader hunting.
            return {"available": False, "error": f"coverage json failed: {_first_line(result.stdout, result.stderr)}"}
    return {
        "available": True,
        "percent": data.get("totals", {}).get("percent_covered", 0),
        "scopes": _coverage_scopes(data.get("files", {}), vendored),
    }


def _first_line(*streams: str) -> str:
    for stream in streams:
        head = stream.strip().splitlines()
        if head:
            return head[0]
    return "no output"


def _coverage_scopes(files: dict, vendored: VendoredPaths) -> dict[str, dict[str, object]]:
    scopes: dict[str, dict[str, float]] = {scope: {"files": 0, "measured": 0, "covered": 0} for scope in SCOPES}
    for path, entry in files.items():
        summary = entry.get("summary", {})
        bucket = scopes[vendored.scope_of(path)]
        bucket["files"] += 1
        bucket["measured"] += summary.get("num_statements", 0) + summary.get("num_branches", 0)
        bucket["covered"] += summary.get("covered_lines", 0) + summary.get("covered_branches", 0)
    return {
        scope: {
            "files": int(bucket["files"]),
            "measured": int(bucket["measured"]),
            "percent": round(bucket["covered"] / bucket["measured"] * 100, 4) if bucket["measured"] else None,
        }
        for scope, bucket in scopes.items()
    }


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


def collect(root: Path, vendored_override: Sequence[str] = ()) -> dict[str, object]:
    """Every metric for ``root``, in the shape ``assess --json`` prints."""
    vendored = vendored_paths.resolve(root, vendored_override)
    return {
        "vendored": vendored.as_dict(),
        "lint": count_lint_violations(root),
        "todos": count_todos(root, vendored),
        "complexity": count_complexity(root),
        "coverage": check_coverage(root, vendored),
        "dependencies": check_outdated_deps(root),
        "suppressions": suppressions.count(root, vendored),
    }
