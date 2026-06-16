#!/usr/bin/env python3
"""prek entry point: flag NEW C901/PLR09xx ignores in a pyproject ruff config.

ast-grep 0.42.3 has no TOML language, so the ``pyproject.toml`` ruff
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
import tomllib
from collections.abc import Iterable
from pathlib import Path

COMPLEXITY_CODES_RE = re.compile(r"\b(C901|PLR09\d{2})\b")


def _entries(source: str) -> list[str]:
    """Return ``<code>@<location>`` keys for every complexity ignore in a pyproject."""
    try:
        data = tomllib.loads(source)
    except tomllib.TOMLDecodeError:
        return []
    ruff = data.get("tool", {}).get("ruff", {})
    lint = ruff.get("lint", ruff)
    found = [
        f"{code}@lint.{key}"
        for key in ("ignore", "extend-ignore")
        for code in lint.get(key, []) or []
        if COMPLEXITY_CODES_RE.fullmatch(str(code))
    ]
    per_file = lint.get("per-file-ignores", {}) or {}
    found.extend(
        f"{code}@lint.per-file-ignores.{pattern}"
        for pattern, codes in per_file.items()
        for code in codes or []
        if COMPLEXITY_CODES_RE.fullmatch(str(code))
    )
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
