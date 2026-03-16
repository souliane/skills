#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# requires-python = ">=3.12"
# ///
"""Minimal deterministic checks for skill repositories.

This script only validates `SKILL.md` frontmatter in a tracked skills repo.
It intentionally checks just the structural fields that every skill should
have: `name`, `description`, and `metadata.version`.
"""

import argparse  # Intentionally not typer — this script has zero dependencies.
import re
import subprocess
import sys
from pathlib import Path
from typing import cast

FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
REQUIRED_FRONTMATTER = ("name", "description")
REQUIRED_METADATA_FRONTMATTER = ("version",)
IGNORED_TOP_LEVEL_DIRS = {"external"}


class Finding:
    """A single check finding."""

    def __init__(self, root_dir: Path, path: Path, message: str) -> None:
        self.root_dir = root_dir
        self.path = path
        self.message = message

    def __str__(self) -> str:
        rel = self.path.relative_to(self.root_dir) if self.path.is_relative_to(self.root_dir) else self.path
        return f"  ERROR: {rel}: {self.message}"


def _git_ls_files(root_dir: Path, *patterns: str) -> list[Path]:
    command = ["git", "-C", str(root_dir), "ls-files"]
    command.extend(patterns)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if result.returncode != 0:
        message = f"git ls-files failed for {root_dir}: {result.stderr.strip()}"
        raise RuntimeError(message)
    return sorted(root_dir / line for line in result.stdout.splitlines() if line)


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


def check_frontmatter(root_dir: Path, skill_files: list[Path]) -> list[Finding]:
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


def collect_files(root_dir: Path) -> dict[str, list[Path]]:
    tracked = [
        path
        for path in _git_ls_files(root_dir)
        if path.exists()
        and (not path.relative_to(root_dir).parts or path.relative_to(root_dir).parts[0] not in IGNORED_TOP_LEVEL_DIRS)
    ]
    skills = [path for path in tracked if path.name == "SKILL.md"]
    return {"skills": skills}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to check")
    args = parser.parse_args(argv)

    root_dir = args.root.resolve()
    files = collect_files(root_dir)

    findings: list[Finding] = []
    findings.extend(check_frontmatter(root_dir, files["skills"]))

    if findings:
        print(f"Errors ({len(findings)}):")
        for finding in findings:
            print(finding)
        print("FAIL")
        return 1

    print("PASS")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
