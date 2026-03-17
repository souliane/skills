#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""Scan Phase 2 enforcement queue for real violation counts.

Reads the queue rules between the Phase 1/Phase 2 markers in pyproject.toml,
temporarily clears lint.ignore to get accurate counts, then restores the file.

Usage:
    ./scan_queue.py [PATH]          # scan cwd or PATH
    ./scan_queue.py --json [PATH]   # output as JSON for scripting
"""

import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import typer

QUEUE_START = "# --- To enforce:"
QUEUE_END = "# --- Permanently disabled"


def _extract_queue_rules(toml_content: str) -> list[str]:
    if QUEUE_START not in toml_content:
        print(f"ERROR: missing queue marker — expected: {QUEUE_START}", file=sys.stderr)
        raise typer.Exit(1)
    section = toml_content.split(QUEUE_START)[1]
    if QUEUE_END in section:
        section = section[: section.index(QUEUE_END)]
    return sorted(set(re.findall(r'"([A-Z]+\d+)"', section)))


def _clear_lint_ignore(toml_content: str) -> str:
    lines = toml_content.split("\n")
    new_lines: list[str] = []
    in_ignore = False
    for line in lines:
        if "lint.ignore" in line and "=" in line and "extend" not in line and "per-file" not in line:
            new_lines.append("lint.ignore = []")
            in_ignore = True
            continue
        if in_ignore:
            if line.strip() == "]":
                in_ignore = False
            continue
        new_lines.append(line)
    return "\n".join(new_lines)


def _load_rule_names() -> dict[str, str]:
    result = subprocess.run(
        ["ruff", "rule", "--all", "--output-format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if not result.stdout:
        return {}
    return {r["code"]: r["name"] for r in json.loads(result.stdout)}


def main(
    path: Path = typer.Argument(Path(), help="Path to check for ruff violations"),
    as_json: bool = typer.Option(False, "--json", help="Output as JSON"),
) -> None:
    """Scan the Phase 2 enforcement queue for real violation counts."""
    pyproject = Path("pyproject.toml")
    if not pyproject.exists():
        print("ERROR: pyproject.toml not found in cwd", file=sys.stderr)
        raise typer.Exit(1)

    original = pyproject.read_text(encoding="utf-8")
    queue = _extract_queue_rules(original)

    # Temporarily clear lint.ignore to get real violation counts
    pyproject.write_text(_clear_lint_ignore(original), encoding="utf-8")
    try:
        proc = subprocess.run(
            [
                "ruff",
                "check",
                "--select",
                ",".join(queue),
                "--preview",
                "--no-fix",
                "--output-format",
                "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        data = json.loads(proc.stdout) if proc.stdout else []
    finally:
        pyproject.write_text(original, encoding="utf-8")

    rule_names = _load_rule_names()
    counts: Counter[str] = Counter(d["code"] for d in data)
    fixable: Counter[str] = Counter(d["code"] for d in data if d.get("fix"))
    manual: Counter[str] = Counter(d["code"] for d in data if not d.get("fix"))
    files_per_rule: defaultdict[str, set[str]] = defaultdict(set)
    for d in data:
        files_per_rule[d["code"]].add(d["filename"])

    zero = sorted(set(queue) - set(counts))
    auto_only = sorted(
        [c for c in queue if c in fixable and c not in manual],
        key=lambda c: fixable[c],
    )
    mixed = sorted(
        [c for c in queue if c in fixable and c in manual],
        key=lambda c: counts[c],
    )
    manual_only = sorted(
        [c for c in queue if c not in fixable and c in manual],
        key=lambda c: manual[c],
    )

    if as_json:
        print(
            json.dumps(
                {
                    "queue_size": len(queue),
                    "zero_violation": zero,
                    "auto_only": [
                        {"code": c, "violations": fixable[c], "files": len(files_per_rule[c])} for c in auto_only
                    ],
                    "mixed": [
                        {"code": c, "auto": fixable[c], "manual": manual[c], "files": len(files_per_rule[c])}
                        for c in mixed
                    ],
                    "manual_only": [
                        {"code": c, "violations": manual[c], "files": len(files_per_rule[c])} for c in manual_only
                    ],
                },
                indent=2,
            )
        )
        return

    name = lambda c: rule_names.get(c, "unknown")  # noqa: E731

    print(f"Enforceable rules in queue: {len(queue)}")
    print(f"\nZero-violation rules ({len(zero)}) — safe to enable immediately:")
    for c in zero:
        print(f"  {c:<10} {name(c)}")

    print(f"\nAuto-fixable-only rules ({len(auto_only)}):")
    for c in auto_only:
        print(f"  {fixable[c]:5d} violations, {len(files_per_rule[c]):4d} files  {c:<10} {name(c)}")

    if mixed:
        print(f"\nPartially auto-fixable rules ({len(mixed)}):")
        for c in mixed:
            print(
                f"  {fixable[c]:5d} auto + {manual[c]:5d} manual, {len(files_per_rule[c]):4d} files  {c:<10} {name(c)}"
            )

    if manual_only:
        print(f"\nManual-only rules ({len(manual_only)}):")
        for c in manual_only:
            print(f"  {manual[c]:5d} violations, {len(files_per_rule[c]):4d} files  {c:<10} {name(c)}")


if __name__ == "__main__":
    typer.run(main)
