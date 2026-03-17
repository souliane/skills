#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["typer>=0.12"]
# ///
"""ruff — Unified CLI for ruff adoption tools.

Usage: cli.py <command> [args...]
"""

import typer

app = typer.Typer(
    name="ruff",
    help="Ruff adoption tools",
    add_completion=False,
    no_args_is_help=True,
)

from discover_violations import main as discover_main
from scan_queue import main as scan_queue_main

app.command(name="discover")(discover_main)
app.command(name="scan-queue")(scan_queue_main)


if __name__ == "__main__":
    app()
