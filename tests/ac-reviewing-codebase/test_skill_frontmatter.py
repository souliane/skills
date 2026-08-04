"""Tests for deterministic skill repo frontmatter checks."""

from pathlib import Path

from _cli_import import load
from _gitutil import run_git

skill_frontmatter = load("skill_frontmatter")


def _make_skill(tmp_path: Path, name: str, content: str) -> Path:
    skill_dir = tmp_path / name
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(content, encoding="utf-8")
    return skill_md


class TestParseFrontmatter:
    def test_parses_valid_frontmatter(self) -> None:
        text = "---\nname: demo-skill\ndescription: A test skill\nmetadata:\n  version: 0.0.1\n---\n# Content"
        result = skill_frontmatter.parse_frontmatter(text)
        assert result["name"] == "demo-skill"
        assert result["description"] == "A test skill"
        assert result["metadata"]["version"] == "0.0.1"

    def test_returns_empty_on_missing_frontmatter(self) -> None:
        assert skill_frontmatter.parse_frontmatter("# No frontmatter") == {}

    def test_strips_quotes(self) -> None:
        text = '---\nname: "quoted"\nmetadata:\n  version: "0.0.1"\n---\n'
        parsed = skill_frontmatter.parse_frontmatter(text)
        assert parsed["name"] == "quoted"
        assert parsed["metadata"]["version"] == "0.0.1"

    def test_folded_scalar_description_is_assembled(self) -> None:
        # A YAML folded (``>``) description must be joined from its indented
        # continuation lines, not stored as the literal ``>`` marker.
        text = (
            "---\n"
            "name: demo\n"
            "description: >\n"
            "  First line of the description.\n"
            "  Second line continues it.\n"
            "metadata:\n"
            "  version: 0.0.1\n"
            "---\n"
        )
        parsed = skill_frontmatter.parse_frontmatter(text)
        assert parsed["description"] == "First line of the description. Second line continues it."
        assert parsed["metadata"]["version"] == "0.0.1"

    def test_literal_scalar_description_is_assembled(self) -> None:
        text = "---\nname: demo\ndescription: |\n  Line one.\n  Line two.\n---\n"
        parsed = skill_frontmatter.parse_frontmatter(text)
        assert parsed["description"] == "Line one. Line two."


class TestCheckFrontmatter:
    def test_valid_skill_passes(self, tmp_path: Path) -> None:
        skill_md = _make_skill(
            tmp_path,
            "demo-skill",
            "---\nname: demo-skill\ndescription: Desc\nmetadata:\n  version: 0.0.1\n---\n",
        )
        assert skill_frontmatter.check_frontmatter(tmp_path, [skill_md]) == []

    def test_missing_frontmatter_fails(self, tmp_path: Path) -> None:
        skill_md = _make_skill(tmp_path, "demo-skill", "# No frontmatter")
        findings = skill_frontmatter.check_frontmatter(tmp_path, [skill_md])
        assert len(findings) == 1
        assert "missing or invalid" in findings[0].message

    def test_missing_metadata_version_fails(self, tmp_path: Path) -> None:
        skill_md = _make_skill(tmp_path, "demo-skill", "---\nname: demo-skill\ndescription: Desc\n---\n")
        findings = skill_frontmatter.check_frontmatter(tmp_path, [skill_md])
        assert len(findings) == 1
        assert "metadata.version" in findings[0].message


class TestCollectSkillFiles:
    def _tracked_skill_repo(self, tmp_path: Path, *parents: str) -> Path:
        for parent in parents:
            skill_dir = tmp_path / parent / "demo-skill" if parent else tmp_path / "demo-skill"
            skill_dir.mkdir(parents=True)
            (skill_dir / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo.\nmetadata:\n  version: 0.0.1\n---\n"
            )
        run_git(tmp_path, "init")
        run_git(tmp_path, "add", ".")
        return tmp_path.resolve()

    def test_returns_tracked_skill_files(self, tmp_path: Path) -> None:
        root = self._tracked_skill_repo(tmp_path, "")
        assert [p.name for p in skill_frontmatter.collect_skill_files(root)] == ["SKILL.md"]

    def test_ignores_the_external_top_level_dir(self, tmp_path: Path) -> None:
        root = self._tracked_skill_repo(tmp_path, "mine", "external")
        found = [str(p.relative_to(root)) for p in skill_frontmatter.collect_skill_files(root)]
        assert found == ["mine/demo-skill/SKILL.md"]
