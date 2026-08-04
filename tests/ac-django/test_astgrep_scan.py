"""Behaviour tests for the ast-grep prek wrapper's own decisions.

`test_astgrep_rules.py` exercises the YAML rules THROUGH this wrapper, which
only ever takes the happy path: a real rule, a real engine, a real file. The
wrapper's own decisions are the ones a consuming repo depends on and none of
those tests reach — that a misconfiguration exits 2 rather than 1 (prek reports
a rule violation and a broken hook identically otherwise), that the engine is
resolved uv-first so the version stays pinned, and that a rule with nothing
staged does not shell out at all.
"""

import subprocess
from dataclasses import dataclass

import astgrep_scan
import pytest

RULE_STEM = "no-pytest-django-db"


@dataclass
class _FakeCompleted:
    returncode: int


class TestMisconfigurationExitsTwo:
    def test_no_arguments_prints_usage(self, capsys) -> None:
        assert astgrep_scan.main([]) == 2
        assert capsys.readouterr().err.startswith("usage: astgrep_scan.py")

    def test_an_unknown_rule_stem_names_the_file_it_looked_for(self, capsys) -> None:
        assert astgrep_scan.main(["no-such-rule", "sample.py"]) == 2
        assert "no-such-rule.yml" in capsys.readouterr().err

    def test_no_engine_on_path_says_which_engines_it_accepts(self, monkeypatch, capsys) -> None:
        monkeypatch.setattr(astgrep_scan.shutil, "which", lambda _name: None)
        assert astgrep_scan.main([RULE_STEM, "sample.py"]) == 2
        message = capsys.readouterr().err
        assert astgrep_scan.ASTGREP_PIN in message
        assert "ast-grep" in message


class TestEngineResolution:
    def _which(self, monkeypatch, available: set[str]) -> None:
        monkeypatch.setattr(
            astgrep_scan.shutil,
            "which",
            lambda name: f"/usr/bin/{name}" if name in available else None,
        )

    def test_uv_is_preferred_and_pins_the_engine_version(self, monkeypatch) -> None:
        self._which(monkeypatch, {"uv", "ast-grep"})
        assert astgrep_scan._astgrep_argv() == [
            "uvx",
            "--from",
            f"ast-grep-cli=={astgrep_scan.ASTGREP_PIN}",
            "ast-grep",
        ]

    def test_a_system_binary_is_the_unpinned_fallback(self, monkeypatch) -> None:
        self._which(monkeypatch, {"ast-grep"})
        assert astgrep_scan._astgrep_argv() == ["ast-grep"]

    def test_neither_available_resolves_to_nothing(self, monkeypatch) -> None:
        self._which(monkeypatch, set())
        assert astgrep_scan._astgrep_argv() == []


class TestScanInvocation:
    """The engine is pinned to uvx here so the assertions hold on any host."""

    def _record(self, monkeypatch, returncode: int) -> list[list[str]]:
        calls: list[list[str]] = []

        def fake_run(argv: list[str], **_kwargs: object) -> _FakeCompleted:
            calls.append(argv)
            return _FakeCompleted(returncode)

        monkeypatch.setattr(astgrep_scan.shutil, "which", lambda name: "/usr/bin/uv" if name == "uv" else None)
        monkeypatch.setattr(subprocess, "run", fake_run)
        return calls

    def test_nothing_staged_skips_the_engine_entirely(self, monkeypatch) -> None:
        calls = self._record(monkeypatch, 0)
        assert astgrep_scan.main([RULE_STEM]) == 0
        assert calls == []

    def test_the_rule_path_and_every_file_reach_the_engine(self, monkeypatch) -> None:
        calls = self._record(monkeypatch, 0)
        assert astgrep_scan.main([RULE_STEM, "a.py", "b.py"]) == 0
        rule_path = str(astgrep_scan.RULES_DIR / f"{RULE_STEM}.yml")
        pinned = f"ast-grep-cli=={astgrep_scan.ASTGREP_PIN}"
        assert calls == [["uvx", "--from", pinned, "ast-grep", "scan", "--rule", rule_path, "a.py", "b.py"]]

    @pytest.mark.parametrize("returncode", [1, 2])
    def test_the_engines_exit_code_is_the_hooks_exit_code(self, monkeypatch, returncode: int) -> None:
        self._record(monkeypatch, returncode)
        assert astgrep_scan.main([RULE_STEM, "a.py"]) == returncode
