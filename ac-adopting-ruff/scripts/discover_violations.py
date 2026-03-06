#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""Discover all ruff violations and generate a ready-to-paste lint.ignore block.

Run AFTER configuring lint.select = ["ALL"] and lint.preview = true
in pyproject.toml, but BEFORE populating lint.ignore.
"""

import json
import subprocess
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import typer

# Rules that conflict with ruff format — these go in lint.extend-ignore, not lint.ignore.
# Ref: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
FORMATTER_CONFLICTS = frozenset(
    {
        "COM812",
        "COM819",
        "D206",
        "D300",
        "E111",
        "E114",
        "E117",
        "ISC001",
        "Q000",
        "Q001",
        "Q002",
        "Q003",
        "Q004",
        "W191",
    }
)


def _load_rule_metadata() -> dict[str, dict[str, str]]:
    """Build {code: {"name": ..., "fix": ...}} from ``ruff rule --all``."""
    result = subprocess.run(
        ["ruff", "rule", "--all", "--output-format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout:
        return {}
    rules = json.loads(result.stdout)
    meta: dict[str, dict[str, str]] = {}
    for r in rules:
        fix_avail = r.get("fix_availability", "None")
        if fix_avail == "None":
            fix = "manual"
        elif fix_avail == "Always":
            fix = "auto-fix (always)"
        else:
            fix = f"auto-fix ({fix_avail.lower()})"
        meta[r["code"]] = {"name": r["name"], "fix": fix}
    return meta


def _print_report(counts: Counter[str], rule_meta: dict[str, dict[str, str]]) -> None:
    """Print summary table and ready-to-paste config blocks."""

    def _name(code: str) -> str:
        return rule_meta.get(code, {}).get("name", "unknown")

    def _fix(code: str) -> str:
        return rule_meta.get(code, {}).get("fix", "?")

    project_rules = sorted(c for c in counts if c not in FORMATTER_CONFLICTS)
    conflict_rules = sorted(c for c in counts if c in FORMATTER_CONFLICTS)
    total = sum(counts.values())
    auto_total = sum(counts[c] for c in counts if "auto-fix" in _fix(c))

    print(f"\n{'=' * 80}")
    print(f"  {total} violations across {len(counts)} rules")
    print(f"  Auto-fixable: {auto_total}/{total} ({100 * auto_total // max(total, 1)}%)")
    print(f"  Project rules: {len(project_rules)}  |  Formatter conflicts: {len(conflict_rules)}")
    print(f"{'=' * 80}\n")

    # Summary table.
    print(f"{'Code':<10} {'Name':<45} {'Count':>6}  {'Fix'}")
    print(f"{'-' * 10} {'-' * 45} {'-' * 6}  {'-' * 20}")
    for code in sorted(counts):
        marker = " [fmt-conflict]" if code in FORMATTER_CONFLICTS else ""
        print(f"{code:<10} {_name(code):<45} {counts[code]:>6}  {_fix(code)}{marker}")

    _print_ignore_block(project_rules, _name)
    _print_conflict_block(conflict_rules, _name)


def _print_ignore_block(project_rules: list[str], name_fn: Callable[[str], str]) -> None:
    if not project_rules:
        return
    print(f"\n{'=' * 80}")
    print("  lint.ignore — paste into pyproject.toml:")
    print(f"{'=' * 80}\n")
    print("lint.ignore = [")
    for code in project_rules:
        pad = " " * max(1, 7 - len(code))
        print(f'  "{code}",{pad}# {name_fn(code)}')
    print("]")


def _print_conflict_block(conflict_rules: list[str], name_fn: Callable[[str], str]) -> None:
    if not conflict_rules:
        return
    print(f"\n{'=' * 80}")
    print("  Formatter-conflicting rules found (should be in lint.extend-ignore):")
    print(f"{'=' * 80}\n")
    for code in conflict_rules:
        pad = " " * max(1, 7 - len(code))
        print(f'  "{code}",{pad}# {name_fn(code)}')
    print()
    print("  These are already handled by the lint.extend-ignore template.")
    print("  Do NOT add them to lint.ignore.")


def main(path: Path = typer.Argument(Path(), help="Path to check for ruff violations")) -> None:
    result = subprocess.run(
        ["ruff", "check", str(path), "--output-format", "json", "--no-fix"],
        capture_output=True,
        text=True,
        check=False,
    )

    if not result.stdout or result.stdout.strip() == "[]":
        print("No violations found!")
        return

    try:
        violations = json.loads(result.stdout)
    except json.JSONDecodeError:
        print(f"Error parsing ruff output:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    if not violations:
        print("No violations found!")
        return

    rule_meta = _load_rule_metadata()
    counts: Counter[str] = Counter()
    for v in violations:
        counts[v["code"]] += 1

    _print_report(counts, rule_meta)


if __name__ == "__main__":
    typer.run(main)
