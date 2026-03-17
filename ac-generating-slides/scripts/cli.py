#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""Detect a Chromium browser and render Marp slides to PDF.

Usage:
    ./cli.py slides.md                  # → slides.pdf
    ./cli.py slides.md -o output.pdf    # custom output path
    ./cli.py slides.md --open           # render and open
"""

import platform
import shutil
import subprocess
import sys
from pathlib import Path

import typer

# Chromium-based browsers in preference order
_MACOS_BROWSERS = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
]

_LINUX_BROWSERS = [
    "google-chrome",
    "google-chrome-stable",
    "chromium-browser",
    "chromium",
    "brave-browser",
    "microsoft-edge",
]


def _find_browser() -> str | None:
    if platform.system() == "Darwin":
        for path in _MACOS_BROWSERS:
            if Path(path).exists():
                return path
    else:
        for name in _LINUX_BROWSERS:
            if shutil.which(name):
                return name
    return None


def main(
    input_file: Path = typer.Argument(..., help="Markdown file with Marp frontmatter"),
    output: Path | None = typer.Option(
        None, "-o", "--output", help="Output PDF path (default: same name as input with .pdf)"
    ),
    open_after: bool = typer.Option(False, "--open", help="Open the PDF after rendering"),
) -> None:
    """Render Marp slides to PDF."""
    if not input_file.exists():
        print(f"Error: {input_file} not found", file=sys.stderr)
        raise typer.Exit(1)

    if not shutil.which("marp"):
        print("Error: marp CLI not found. Install with: brew install marp-cli", file=sys.stderr)
        raise typer.Exit(1)

    browser = _find_browser()
    if not browser:
        print("Error: no Chromium-based browser found", file=sys.stderr)
        raise typer.Exit(1)

    output_path = output or input_file.with_suffix(".pdf")

    env = {"CHROME_PATH": browser}
    cmd = ["marp", str(input_file), "--pdf", "--allow-local-files", "-o", str(output_path)]

    print(f"Browser: {browser}")
    print(f"Rendering: {input_file} → {output_path}")

    import os

    full_env = {**os.environ, **env}
    result = subprocess.run(cmd, env=full_env, check=False)
    if result.returncode != 0:
        print("Error: marp rendering failed", file=sys.stderr)
        raise typer.Exit(1)

    print(f"Done: {output_path} ({output_path.stat().st_size / 1024:.0f} KB)")

    if open_after:
        opener = "open" if platform.system() == "Darwin" else "xdg-open"
        subprocess.run([opener, str(output_path)], check=False)


if __name__ == "__main__":
    typer.run(main)
