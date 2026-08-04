#!/usr/bin/env python3
"""prek entry point: flag NEW C901/PLR09xx ignores in a pyproject ruff config.

ast-grep 0.44.1 has no TOML language, so the ``pyproject.toml`` ruff
ignore-list surface is out of scope for the ast-grep ``no-complexity-suppressions``
rule. This tiny standalone hook covers exactly that surface: it parses every
``[tool.ruff] lint.ignore`` / ``lint.extend-ignore`` / ``lint.per-file-ignores``
entry and fails on any ``C901`` / ``PLR09xx`` code that is NOT in the inline
grandfather allow-list passed by the consuming repo.

Grandfathering is INLINE (mirroring ast-grep's ``# ast-grep-ignore``): the
consuming repo lists its existing entries as ``--grandfather`` args — there is no
baseline data file and no count cap. A new complexity ignore that is not on the
allow-list fails; the allow-list only shrinks as the codebase improves.

Usage (wired from ``.pre-commit-hooks.yaml``)::

    pyproject_complexity.py [--grandfather <code@location> ...] <pyproject.toml> [...]

``<location>`` is the detector's ``lint.<key>`` / ``lint.per-file-ignores.<pattern>``
string, e.g. ``--grandfather "C901@lint.per-file-ignores.scripts/**/*.py"``.
"""

import re
import sys
from collections.abc import Iterable
from pathlib import Path

COMPLEXITY_CODES_RE = re.compile(r"\b(C901|PLR09\d{2})\b")
SECTION_RE = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
ASSIGNMENT_RE = re.compile(r"^\s*([^=#]+?)\s*=\s*(.*)$")


def _normalise_key(key: str) -> str:
    return key.strip().replace('"', "").replace("'", "")


def _collect_value(lines: list[str], start: int, initial: str) -> tuple[str, int]:
    value = initial
    index = start
    balance = initial.count("[") - initial.count("]")
    while balance > 0 and index + 1 < len(lines):
        index += 1
        value = f"{value}\n{lines[index]}"
        balance += lines[index].count("[") - lines[index].count("]")
    return value, index


def _location(section: str, key: str) -> str:
    normalized_key = _normalise_key(key)
    if section in {"tool.ruff.lint.per-file-ignores", "tool.ruff.per-file-ignores"}:
        return f"lint.per-file-ignores.{normalized_key}"
    if section == "tool.ruff.lint":
        return f"lint.{normalized_key}"
    if section == "tool.ruff":
        if normalized_key.startswith("lint."):
            return normalized_key
        return f"lint.{normalized_key}"
    return ""


def _entries(source: str) -> list[str]:
    """Return ``<code>@<location>`` keys for every complexity ignore in a pyproject."""
    found: list[str] = []
    section = ""
    lines = source.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        section_match = SECTION_RE.match(line)
        if section_match:
            section = section_match.group(1).strip()
            index += 1
            continue
        assignment = ASSIGNMENT_RE.match(line)
        if assignment:
            key, raw_value = assignment.groups()
            location = _location(section, key)
            value, index = _collect_value(lines, index, raw_value)
            if location in {"lint.ignore", "lint.extend-ignore"} or location.startswith("lint.per-file-ignores."):
                found.extend(f"{code}@{location}" for code in COMPLEXITY_CODES_RE.findall(value))
        index += 1
    return found


def _split_args(argv: list[str]) -> tuple[set[str], list[str]]:
    grandfather: set[str] = set()
    files: list[str] = []
    it = iter(argv)
    for arg in it:
        if arg == "--grandfather":
            grandfather.add(next(it, ""))
        elif arg.startswith("--grandfather="):
            grandfather.add(arg.split("=", 1)[1])
        else:
            files.append(arg)
    grandfather.discard("")
    return grandfather, files


def _failures(files: Iterable[str], grandfather: set[str]) -> list[str]:
    out: list[str] = []
    for name in files:
        source = Path(name).read_text(encoding="utf-8")
        new = [entry for entry in _entries(source) if entry not in grandfather]
        out.extend(f"{name}: new complexity suppression {entry}" for entry in new)
    return out


def main(argv: list[str]) -> int:
    grandfather, files = _split_args(argv)
    failures = _failures(files, grandfather)
    for failure in failures:
        sys.stderr.write(f"ac-django-no-complexity-suppressions: {failure}\n")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
