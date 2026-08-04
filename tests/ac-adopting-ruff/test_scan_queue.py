"""The scan temporarily rewrites the caller's pyproject.toml.

That is the whole risk of this script: it clears `lint.ignore` to get honest
violation counts, and if it fails to put the file back, the consuming repo is
left with its lint config silently deleted. Every test here runs against a real
file on disk for that reason.
"""

import importlib
import json
import subprocess
from pathlib import Path

import pytest
import typer

scan_queue = importlib.import_module("scan_queue")

PYPROJECT = """\
[tool.ruff]
lint.ignore = [
    # --- To enforce: Phase 2 queue
    "ANN001",
    "D401",
    "PLR2004",
    # --- Permanently disabled
    "CPY001",
]
lint.extend-ignore = [ "COM812" ]
lint.per-file-ignores."tests/**/*.py" = [ "S101" ]
"""


def _violations(*rows: tuple[str, str, bool]) -> str:
    return json.dumps(
        [
            {"code": code, "filename": filename, "fix": {"applicability": "safe"} if fixable else None}
            for code, filename, fixable in rows
        ]
    )


@pytest.fixture
def project(tmp_path: Path, monkeypatch) -> Path:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(PYPROJECT, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return pyproject


def _stub_ruff(monkeypatch, stdout: str) -> None:
    def _run(_cmd, **_kwargs):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout=stdout, stderr="")

    monkeypatch.setattr(scan_queue.subprocess, "run", _run)


class TestQueueExtraction:
    def test_reads_only_the_rules_between_the_markers(self) -> None:
        assert scan_queue._extract_queue_rules(PYPROJECT) == ["ANN001", "D401", "PLR2004"]

    def test_a_missing_marker_is_a_hard_stop(self) -> None:
        with pytest.raises(typer.Exit):
            scan_queue._extract_queue_rules("[tool.ruff]\nlint.ignore = []\n")


class TestClearLintIgnore:
    def test_clears_lint_ignore_only(self) -> None:
        cleared = scan_queue._clear_lint_ignore(PYPROJECT)
        assert "lint.ignore = []" in cleared
        assert "ANN001" not in cleared
        # The two neighbouring keys must survive: clearing them would change
        # which rules ruff reports and make every count wrong.
        assert 'lint.extend-ignore = [ "COM812" ]' in cleared
        assert 'lint.per-file-ignores."tests/**/*.py" = [ "S101" ]' in cleared


class TestPyprojectIsAlwaysRestored:
    def test_restored_byte_for_byte_after_a_successful_scan(self, project: Path, monkeypatch) -> None:
        _stub_ruff(monkeypatch, _violations(("ANN001", "a.py", True)))
        scan_queue.main(Path(), as_json=True)
        assert project.read_text(encoding="utf-8") == PYPROJECT

    def test_restored_even_when_ruff_returns_garbage(self, project: Path, monkeypatch) -> None:
        _stub_ruff(monkeypatch, "not json at all")
        with pytest.raises(json.JSONDecodeError):
            scan_queue.main(Path(), as_json=True)
        assert project.read_text(encoding="utf-8") == PYPROJECT

    def test_the_cleared_file_is_what_ruff_actually_sees(self, project: Path, monkeypatch) -> None:
        seen: dict[str, str] = {}

        def _run(_cmd, **_kwargs):
            seen["pyproject"] = project.read_text(encoding="utf-8")
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="[]", stderr="")

        monkeypatch.setattr(scan_queue.subprocess, "run", _run)
        scan_queue.main(Path(), as_json=True)
        assert "lint.ignore = []" in seen["pyproject"]
        assert "ANN001" not in seen["pyproject"]

    def test_no_pyproject_in_cwd_is_an_error_not_a_crash(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with pytest.raises(typer.Exit):
            scan_queue.main(Path(), as_json=True)


class TestPrioritisation:
    def test_json_output_buckets_rules_by_fixability(self, project: Path, monkeypatch, capsys) -> None:
        _stub_ruff(
            monkeypatch,
            _violations(
                ("ANN001", "a.py", True),
                ("ANN001", "b.py", True),
                ("D401", "a.py", True),
                ("D401", "b.py", False),
            ),
        )
        scan_queue.main(Path(), as_json=True)
        report = json.loads(capsys.readouterr().out)

        assert report["queue_size"] == 3
        # PLR2004 is in the queue but has no violations — safe to enable now.
        assert report["zero_violation"] == ["PLR2004"]
        assert report["auto_only"] == [{"code": "ANN001", "violations": 2, "files": 2}]
        assert report["mixed"] == [{"code": "D401", "auto": 1, "manual": 1, "files": 2}]
        assert report["manual_only"] == []

    def test_human_output_names_every_bucket(self, project: Path, monkeypatch, capsys) -> None:
        _stub_ruff(monkeypatch, _violations(("D401", "a.py", False)))
        monkeypatch.setattr(scan_queue, "_load_rule_names", lambda: {"D401": "non-imperative-mood"})
        scan_queue.main(Path(), as_json=False)
        out = capsys.readouterr().out

        assert "Enforceable rules in queue: 3" in out
        assert "Zero-violation rules (2)" in out
        assert "non-imperative-mood" in out
