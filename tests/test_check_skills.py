"""Tests for deterministic skill repo frontmatter checks."""

import importlib.util
import shutil
import subprocess
from pathlib import Path

CHECK_FRONTMATTER_DIR = Path(__file__).resolve().parents[1] / "ac-reviewing-skills" / "scripts"
CHECK_FRONTMATTER_PATH = CHECK_FRONTMATTER_DIR / "cli.py"
SPEC = importlib.util.spec_from_file_location("check_frontmatter", CHECK_FRONTMATTER_PATH)
assert SPEC is not None
assert SPEC.loader is not None
check_frontmatter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check_frontmatter)


def _git_binary() -> str:
    git = shutil.which("git")
    assert git is not None
    return git


GIT = _git_binary()


def _make_skill(tmp_path: Path, name: str, content: str) -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


def _run_git(tmp_path: Path, *args: str) -> None:
    command: list[str] = [GIT, *args]
    subprocess.run(command, cwd=tmp_path, check=True, capture_output=True, text=True)  # noqa: S603


class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self) -> None:
        text = "---\nname: demo-skill\ndescription: A test skill\nmetadata:\n  version: 0.0.1\n---\n# Content"
        result = check_frontmatter._parse_frontmatter(text)
        assert result["name"] == "demo-skill"
        assert result["description"] == "A test skill"
        assert result["metadata"]["version"] == "0.0.1"

    def test_returns_empty_on_missing_frontmatter(self) -> None:
        assert check_frontmatter._parse_frontmatter("# No frontmatter") == {}

    def test_strips_quotes(self) -> None:
        text = '---\nname: "quoted"\nmetadata:\n  version: "0.0.1"\n---\n'
        parsed = check_frontmatter._parse_frontmatter(text)
        assert parsed["name"] == "quoted"
        assert parsed["metadata"]["version"] == "0.0.1"


class TestCheckFrontmatter:
    def test_valid_skill_passes(self, tmp_path: Path) -> None:
        skill_md = _make_skill(
            tmp_path,
            "demo-skill",
            "---\nname: demo-skill\ndescription: Desc\nmetadata:\n  version: 0.0.1\n---\n",
        )
        assert check_frontmatter.check_frontmatter(tmp_path, [skill_md]) == []

    def test_missing_frontmatter_fails(self, tmp_path: Path) -> None:
        skill_md = _make_skill(tmp_path, "demo-skill", "# No frontmatter")
        findings = check_frontmatter.check_frontmatter(tmp_path, [skill_md])
        assert len(findings) == 1
        assert "missing or invalid" in findings[0].message

    def test_missing_metadata_version_fails(self, tmp_path: Path) -> None:
        skill_md = _make_skill(tmp_path, "demo-skill", "---\nname: demo-skill\ndescription: Desc\n---\n")
        findings = check_frontmatter.check_frontmatter(tmp_path, [skill_md])
        assert len(findings) == 1
        assert "metadata.version" in findings[0].message


class TestCollectFiles:
    def test_returns_skill_category(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "demo-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo.\nmetadata:\n  version: 0.0.1\n---\n"
        )
        _run_git(tmp_path, "init")
        _run_git(tmp_path, "add", ".")
        files = check_frontmatter.collect_files(tmp_path.resolve())
        assert any(path.name == "SKILL.md" for path in files["skills"])


class TestMain:
    def test_pass_on_clean_repo(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "demo-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: Demo.\nmetadata:\n  version: 0.0.1\n---\n"
        )
        _run_git(tmp_path, "init")
        _run_git(tmp_path, "add", ".")
        assert check_frontmatter.main(["--root", str(tmp_path)]) == 0

    def test_fail_on_errors(self, tmp_path: Path) -> None:
        skill_dir = tmp_path / "demo-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# No frontmatter")
        _run_git(tmp_path, "init")
        _run_git(tmp_path, "add", ".")
        assert check_frontmatter.main(["--root", str(tmp_path)]) == 1
