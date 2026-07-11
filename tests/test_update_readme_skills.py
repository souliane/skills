"""Tests for the README skills-catalogue generator.

The generator once shipped a phantom ``typer`` catalogue entry because it
scanned the filesystem with ``rglob`` and picked up an untracked scratch dir.
These tests lock in the two guarantees that prevent a recurrence: only tracked
``SKILL.md`` files are listed, and folded/literal YAML descriptions are parsed
correctly.
"""

import importlib.util
import shutil
import subprocess
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "update_readme_skills.py"
SPEC = importlib.util.spec_from_file_location("update_readme_skills", SCRIPT_PATH)
assert SPEC is not None
assert SPEC.loader is not None
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)


def _git_binary() -> str:
    git = shutil.which("git")
    assert git is not None
    return git


_GIT = _git_binary()
_SKILL = "---\nname: {name}\ndescription: {desc}\nmetadata:\n  version: 0.0.1\n---\n# {name}\n"


def _run_git(cwd: Path, *args: str) -> None:
    subprocess.run([_GIT, *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    _run_git(path, "init", "-q", "-b", "main")
    _run_git(path, "config", "user.email", "test@test.com")
    _run_git(path, "config", "user.name", "Test")


def _make_skill(root: Path, name: str, desc: str = "A skill.") -> Path:
    skill_dir = root / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(_SKILL.format(name=name, desc=desc), encoding="utf-8")
    return skill_md


class TestSkillMdFiles:
    def test_lists_only_tracked_skill_files(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _make_skill(tmp_path, "ac-tracked")
        _run_git(tmp_path, "add", ".")
        _run_git(tmp_path, "commit", "-q", "-m", "init")
        # An untracked skill dir must NOT leak into the catalogue.
        _make_skill(tmp_path, "phantom-untracked")

        listed = [p.parent.name for p in mod._skill_md_files(tmp_path)]
        assert "ac-tracked" in listed
        assert "phantom-untracked" not in listed

    def test_falls_back_to_rglob_outside_git(self, tmp_path: Path) -> None:
        _make_skill(tmp_path, "ac-standalone")
        listed = [p.parent.name for p in mod._skill_md_files(tmp_path)]
        assert listed == ["ac-standalone"]


class TestParseFrontmatter:
    def test_inline_description(self, tmp_path: Path) -> None:
        skill_md = _make_skill(tmp_path, "ac-demo", desc="Plain inline description.")
        meta = mod._parse_frontmatter(skill_md)
        assert meta["name"] == "ac-demo"
        assert meta["description"] == "Plain inline description."
        assert meta["metadata.version"] == "0.0.1"

    def test_folded_description(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "ac-folded"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: ac-folded\ndescription: >\n  Line one.\n  Line two.\nmetadata:\n  version: 0.0.1\n---\n",
            encoding="utf-8",
        )
        meta = mod._parse_frontmatter(skill_dir / "SKILL.md")
        assert meta["description"] == "Line one. Line two."


class TestBuildTable:
    def test_table_lists_tracked_skills_alphabetically(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _make_skill(tmp_path, "ac-beta", desc="Beta skill.")
        _make_skill(tmp_path, "ac-alpha", desc="Alpha skill.")
        _run_git(tmp_path, "add", ".")
        _run_git(tmp_path, "commit", "-q", "-m", "init")
        _make_skill(tmp_path, "phantom")  # untracked

        table = mod._build_table(tmp_path)
        assert "| `ac-alpha` | 0.0.1 | Alpha skill. |" in table
        assert "| `ac-beta` | 0.0.1 | Beta skill. |" in table
        assert "phantom" not in table
        assert table.index("ac-alpha") < table.index("ac-beta")

    def test_truncates_at_trigger_words(self, tmp_path: Path) -> None:
        _init_repo(tmp_path)
        _make_skill(tmp_path, "ac-trig", desc="Core purpose. Use when the user says foo.")
        _run_git(tmp_path, "add", ".")
        _run_git(tmp_path, "commit", "-q", "-m", "init")
        table = mod._build_table(tmp_path)
        # The ". Use when" trigger phrase (and everything after) is dropped.
        assert "| `ac-trig` | 0.0.1 | Core purpose |" in table
        assert "Use when" not in table
