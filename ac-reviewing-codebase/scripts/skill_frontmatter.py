"""Parsing and validating the YAML frontmatter block at the top of a SKILL.md."""

import re
import subprocess
from pathlib import Path
from typing import cast

FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)
REQUIRED_FRONTMATTER = ("name", "description")
REQUIRED_METADATA_FRONTMATTER = ("version",)
IGNORED_TOP_LEVEL_DIRS = {"external"}
BLOCK_SCALAR_INDICATORS = {">", "|", ">-", "|-"}


def git_ls_files(root_dir: Path, *patterns: str) -> list[Path]:
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


def parse_frontmatter(text: str) -> dict[str, object]:
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


def check_frontmatter(root_dir: Path, skill_files: list[Path]) -> list[Finding]:
    findings: list[Finding] = []
    for path in skill_files:
        meta = parse_frontmatter(path.read_text(encoding="utf-8"))
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


def collect_skill_files(root_dir: Path) -> list[Path]:
    """Every tracked SKILL.md under ``root_dir``, ignored top-level dirs excluded."""
    return [
        path
        for path in git_ls_files(root_dir)
        if path.name == "SKILL.md"
        and path.exists()
        and (not path.relative_to(root_dir).parts or path.relative_to(root_dir).parts[0] not in IGNORED_TOP_LEVEL_DIRS)
    ]
