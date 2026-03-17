#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pikepdf>=9.0", "pypdf>=4.0", "Pillow>=10.0", "typer>=0.12"]
# ///
"""acroform — Unified CLI for AcroForm PDF template tools.

Usage: cli.py <command> [args...]

Each command maps to an individual script that can also be run standalone.
"""

import typer

app = typer.Typer(
    name="acroform",
    help="AcroForm PDF template tools",
    add_completion=False,
    no_args_is_help=True,
)

# Import the typer-annotated functions from each script and register them.
# Scripts guard their own `app()` / `typer.run()` behind `if __name__ == "__main__"`,
# so importing them is safe.

from add_row import add_field
from apply_content_stream_replacements import main as apply_content_main
from apply_rect_updates import main as apply_rects_main
from golden_diff import main as golden_diff_main
from inspect_fields import inspect
from set_field_flags import set_flags
from verify_field_alignment import main as verify_main

app.command(name="inspect")(inspect)
app.command(name="set-flags")(set_flags)
app.command(name="add-row")(add_field)
app.command(name="apply-content")(apply_content_main)
app.command(name="apply-rects")(apply_rects_main)
app.command(name="verify-alignment")(verify_main)
app.command(name="golden-diff")(golden_diff_main)


if __name__ == "__main__":
    app()
