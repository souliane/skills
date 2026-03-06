#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# requires-python = ">=3.12"
# ///
"""Auto-update the skills catalogue in README.md from SKILL.md frontmatter."""

import re
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
README_PATH = ROOT_DIR / "README.md"

BEGIN = "<!-- BEGIN SKILLS -->"
END = "<!-- END SKILLS -->"
FRONTMATTER_RE = re.compile(r"^---\s*\n(.+?)\n---", re.DOTALL)


def _parse_frontmatter(path: Path) -> dict[str, str]:
    """Extract YAML-ish key: value pairs from SKILL.md frontmatter."""
    m = FRONTMATTER_RE.match(path.read_text(encoding="utf-8"))
    if not m:
        return {}
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def _build_table() -> str:
    skills: list[tuple[str, str, str]] = []  # (name, version, description)

    for skill_md in sorted(ROOT_DIR.rglob("SKILL.md")):
        meta = _parse_frontmatter(skill_md)
        name = meta.get("name", skill_md.parent.name)
        desc = meta.get("description", "")
        # Truncate at trigger words
        short = desc.split(". Use when")[0].split(". Use this")[0]
        version = meta.get("version", "—")
        skills.append((name, version, short))

    lines = [
        "| Skill | Version | Description |",
        "|-------|---------|-------------|",
    ]
    for name, version, desc in skills:
        lines.append(f"| `{name}` | {version} | {desc} |")
    return "\n".join(lines)


def main() -> int:
    if not README_PATH.exists():
        print(f"Error: {README_PATH} not found", file=sys.stderr)
        return 1

    text = README_PATH.read_text(encoding="utf-8")

    if BEGIN not in text or END not in text:
        print(f"Error: README.md missing {BEGIN} / {END} markers", file=sys.stderr)
        return 1

    before = text[: text.index(BEGIN) + len(BEGIN)]
    after = text[text.index(END) :]
    new_text = before + "\n" + _build_table() + "\n" + after

    if text == new_text:
        return 0

    README_PATH.write_text(new_text, encoding="utf-8")
    print("Updated README.md skills catalogue")
    return 1  # signal pre-commit that file was modified


if __name__ == "__main__":
    sys.exit(main())
