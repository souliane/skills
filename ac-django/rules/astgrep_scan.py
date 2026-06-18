#!/usr/bin/env python3
"""prek entry point that runs one ac-django ast-grep rule over the staged files.

ast-grep is the engine for the AST-shaped ac-django checks. Each rule lives in a
sibling ``<rule-id>.yml`` and is grandfathered INLINE via ast-grep's native
``# ast-grep-ignore[<rule-id>]`` comment — there is no count cap and no baseline
file. A new (un-ignored) violation fails the hook; every existing occurrence in a
consuming repo carries an inline ignore.

ast-grep is PINNED to ``ASTGREP_PIN`` and resolved in this order: first via
``uvx --from ast-grep-cli==<pin> ast-grep`` when ``uv`` is on PATH (the pinned,
hermetic path — no system install needed, version guaranteed), otherwise a
system ``ast-grep`` on PATH (used as-is — pin it on the consuming side).

Usage (wired from ``.pre-commit-hooks.yaml``)::

    astgrep_scan.py <rule-stem> <file> [<file> ...]

``<rule-stem>`` is the YAML basename without extension (e.g. ``no-pytest-django-db``).
The rule file is resolved relative to this script, so it works from a pre-commit
checkout cache without any path configuration.
"""

import shutil
import subprocess
import sys
from pathlib import Path

RULES_DIR = Path(__file__).resolve().parent
ASTGREP_PIN = "0.42.3"


def _astgrep_argv() -> list[str]:
    """The pinned ast-grep invocation prefix, or an empty list when unavailable."""
    if shutil.which("uv") is not None:
        return ["uvx", "--from", f"ast-grep-cli=={ASTGREP_PIN}", "ast-grep"]
    if shutil.which("ast-grep") is not None:
        return ["ast-grep"]
    return []


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: astgrep_scan.py <rule-stem> <file> [<file> ...]\n")
        return 2
    rule_stem, files = argv[0], argv[1:]
    rule_path = RULES_DIR / f"{rule_stem}.yml"
    if not rule_path.is_file():
        sys.stderr.write(f"astgrep_scan: no rule file at {rule_path}\n")
        return 2
    runner = _astgrep_argv()
    if not runner:
        sys.stderr.write(
            f"astgrep_scan: need `uv` (preferred, pins ast-grep-cli=={ASTGREP_PIN}) or a system `ast-grep` on PATH.\n",
        )
        return 2
    if not files:
        return 0
    completed = subprocess.run(
        [*runner, "scan", "--rule", str(rule_path), *files],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
