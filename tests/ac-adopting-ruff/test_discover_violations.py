"""The bootstrap report: what ruff found, and the config block to paste back.

Its one job is to hand the reader a `lint.ignore` list they can paste without
thinking. Getting the formatter-conflicting rules into that list instead of the
separate block is the failure that silently breaks `ruff format`.
"""

import importlib
import json
import subprocess
from collections import Counter
from pathlib import Path

import pytest
import typer

discover = importlib.import_module("discover_violations")


def _ruff_output(*codes: str) -> str:
    return json.dumps([{"code": code, "filename": "app.py"} for code in codes])


def _stub_ruff(monkeypatch, check_stdout: str, rules: list[dict] | None = None) -> None:
    def _run(cmd, **_kwargs):
        stdout = json.dumps(rules or []) if "rule" in cmd else check_stdout
        return subprocess.CompletedProcess(args=cmd, returncode=1, stdout=stdout, stderr="oops")

    monkeypatch.setattr(discover.subprocess, "run", _run)


class TestRuleMetadata:
    def test_translates_ruff_fix_availability_into_plain_words(self, monkeypatch) -> None:
        _stub_ruff(
            monkeypatch,
            "[]",
            rules=[
                {"code": "D401", "name": "non-imperative-mood", "fix_availability": "None"},
                {"code": "COM812", "name": "missing-trailing-comma", "fix_availability": "Always"},
                {"code": "ANN001", "name": "missing-type-function-argument", "fix_availability": "Sometimes"},
            ],
        )
        meta = discover._load_rule_metadata()
        assert meta["D401"]["fix"] == "manual"
        assert meta["COM812"]["fix"] == "auto-fix (always)"
        assert meta["ANN001"]["fix"] == "auto-fix (sometimes)"

    def test_no_ruff_output_is_no_metadata_not_a_crash(self, monkeypatch) -> None:
        _stub_ruff(monkeypatch, "")
        monkeypatch.setattr(
            discover.subprocess,
            "run",
            lambda *_a, **_k: subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr=""),
        )
        assert discover._load_rule_metadata() == {}


class TestReport:
    def test_formatter_conflicts_are_kept_out_of_the_paste_block(self, capsys) -> None:
        # COM812 in `lint.ignore` would silently fight `ruff format`; it belongs
        # in `lint.extend-ignore`, which the template already carries.
        counts = Counter({"D401": 3, "COM812": 7})
        meta = {"D401": {"name": "non-imperative-mood", "fix": "manual"}}
        discover._print_report(counts, meta)
        out = capsys.readouterr().out

        ignore_block = out.split("lint.ignore = [")[1].split("]")[0]
        assert '"D401",' in ignore_block
        assert "COM812" not in ignore_block
        assert "should be in lint.extend-ignore" in out
        assert "Do NOT add them to lint.ignore." in out

    def test_counts_the_share_that_ruff_can_fix_for_you(self, capsys) -> None:
        counts = Counter({"D401": 1, "ANN001": 3})
        meta = {
            "D401": {"name": "non-imperative-mood", "fix": "manual"},
            "ANN001": {"name": "missing-type", "fix": "auto-fix (always)"},
        }
        discover._print_report(counts, meta)
        out = capsys.readouterr().out
        assert "4 violations across 2 rules" in out
        assert "Auto-fixable: 3/4 (75%)" in out


class TestMain:
    def test_a_clean_tree_says_so_and_asks_ruff_nothing_else(self, monkeypatch, capsys) -> None:
        calls: list[list[str]] = []

        def _run(cmd, **_kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="[]", stderr="")

        monkeypatch.setattr(discover.subprocess, "run", _run)
        discover.main(Path())
        assert "No violations found!" in capsys.readouterr().out
        assert len(calls) == 1, "no need to fetch rule metadata when there is nothing to report"

    def test_unparseable_ruff_output_exits_nonzero(self, monkeypatch, capsys) -> None:
        _stub_ruff(monkeypatch, "<not json>")
        with pytest.raises(typer.Exit) as raised:
            discover.main(Path())
        assert raised.value.exit_code == 1
        assert "Error parsing ruff output" in capsys.readouterr().err

    def test_reports_the_violations_ruff_found(self, monkeypatch, capsys) -> None:
        _stub_ruff(
            monkeypatch,
            _ruff_output("D401", "D401", "ANN001"),
            rules=[{"code": "D401", "name": "non-imperative-mood", "fix_availability": "None"}],
        )
        discover.main(Path())
        out = capsys.readouterr().out
        assert "3 violations across 2 rules" in out
        assert "non-imperative-mood" in out
