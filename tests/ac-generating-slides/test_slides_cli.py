"""Rendering slides depends on three things the user may not have.

Marp needs a Chromium binary it cannot find by itself, so this script's real job
is to detect one and fail with a usable message when a prerequisite is missing —
rather than letting marp die with a Chrome stack trace.
"""

import importlib
import subprocess
from pathlib import Path

import pytest
import typer

slides = importlib.import_module("cli")


@pytest.fixture
def deck(tmp_path: Path) -> Path:
    source = tmp_path / "slides.md"
    source.write_text("---\nmarp: true\n---\n\n# Hello\n", encoding="utf-8")
    # marp is stubbed out, so the PDF it would have written is staged here.
    (tmp_path / "slides.pdf").write_bytes(b"%PDF-1.4\n")
    return source


def _stub_environment(monkeypatch, *, marp: bool = True, browser: str | None = "/usr/bin/chromium") -> list[list[str]]:
    calls: list[list[str]] = []

    def _run(cmd, **_kwargs):
        calls.append(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(slides.shutil, "which", lambda _name: "/usr/bin/marp" if marp else None)
    monkeypatch.setattr(slides, "_find_browser", lambda: browser)
    monkeypatch.setattr(slides.subprocess, "run", _run)
    return calls


class TestPrerequisites:
    def test_a_missing_input_file_stops_before_touching_marp(self, tmp_path: Path, monkeypatch, capsys) -> None:
        _stub_environment(monkeypatch)
        with pytest.raises(typer.Exit) as raised:
            slides.main(tmp_path / "absent.md", None, open_after=False)
        assert raised.value.exit_code == 1
        assert "not found" in capsys.readouterr().err

    def test_a_missing_marp_cli_says_how_to_install_it(self, deck: Path, monkeypatch, capsys) -> None:
        _stub_environment(monkeypatch, marp=False)
        with pytest.raises(typer.Exit) as raised:
            slides.main(deck, None, open_after=False)
        assert raised.value.exit_code == 1
        assert "brew install marp-cli" in capsys.readouterr().err

    def test_no_chromium_anywhere_is_reported_as_such(self, deck: Path, monkeypatch, capsys) -> None:
        _stub_environment(monkeypatch, browser=None)
        with pytest.raises(typer.Exit) as raised:
            slides.main(deck, None, open_after=False)
        assert raised.value.exit_code == 1
        assert "no Chromium-based browser found" in capsys.readouterr().err

    def test_a_failing_marp_run_is_not_reported_as_success(self, deck: Path, monkeypatch, capsys) -> None:
        _stub_environment(monkeypatch)
        monkeypatch.setattr(
            slides.subprocess,
            "run",
            lambda cmd, **_k: subprocess.CompletedProcess(args=cmd, returncode=3),
        )
        with pytest.raises(typer.Exit) as raised:
            slides.main(deck, None, open_after=False)
        assert raised.value.exit_code == 1
        assert "marp rendering failed" in capsys.readouterr().err


class TestRendering:
    def test_output_defaults_to_the_input_name_with_a_pdf_suffix(self, deck: Path, monkeypatch) -> None:
        calls = _stub_environment(monkeypatch)
        slides.main(deck, None, open_after=False)
        assert calls[0] == [
            "marp",
            str(deck),
            "--pdf",
            "--allow-local-files",
            "-o",
            str(deck.with_suffix(".pdf")),
        ]

    def test_an_explicit_output_path_wins(self, deck: Path, tmp_path: Path, monkeypatch) -> None:
        out = tmp_path / "custom.pdf"
        out.write_bytes(b"%PDF-1.4\n")
        calls = _stub_environment(monkeypatch)
        slides.main(deck, out, open_after=False)
        assert calls[0][-1] == str(out)

    def test_open_after_hands_the_pdf_to_the_desktop_opener(self, deck: Path, monkeypatch) -> None:
        calls = _stub_environment(monkeypatch)
        slides.main(deck, None, open_after=True)
        assert calls[1][0] in {"open", "xdg-open"}
        assert calls[1][1] == str(deck.with_suffix(".pdf"))

    def test_the_detected_browser_is_passed_to_marp_as_chrome_path(self, deck: Path, monkeypatch) -> None:
        captured: dict[str, dict[str, str]] = {}

        def _run(cmd, **kwargs):
            captured["env"] = kwargs.get("env", {})
            return subprocess.CompletedProcess(args=cmd, returncode=0)

        monkeypatch.setattr(slides.shutil, "which", lambda _name: "/usr/bin/marp")
        monkeypatch.setattr(slides, "_find_browser", lambda: "/opt/brave")
        monkeypatch.setattr(slides.subprocess, "run", _run)
        slides.main(deck, None, open_after=False)
        assert captured["env"]["CHROME_PATH"] == "/opt/brave"
