#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pikepdf>=9.0", "pypdf>=4.0", "Pillow>=10.0", "typer>=0.12"]
# ///
"""acroform — the entry point for the AcroForm PDF template tools.

Usage: ./cli.py <command> [args...]

This is the ONLY runnable entry point in the skill. The sibling modules hold the
command bodies and the PDF mechanics; none of them declares a Typer app or runs
anything on import, so this file owns the whole command surface.

Exit codes are uniform across commands: 0 success, 1 the PDF did not match what
the spec asserted, 2 the spec itself is malformed (see acroform_errors.py).
"""

import typer
from add_row import add_field
from apply_content_stream_replacements import main as apply_content_main
from apply_rect_updates import main as apply_rects_main
from golden_diff import main as golden_diff_main
from inspect_fields import inspect
from set_field_flags import set_flags
from sync_sibling_bars import main as sync_bars_main
from verify_field_alignment import main as verify_main
from verify_paired_bars import main as verify_paired_main

app = typer.Typer(
    name="acroform",
    help="AcroForm PDF template tools",
    add_completion=False,
    no_args_is_help=True,
)

app.command(name="inspect")(inspect)
app.command(name="set-flags")(set_flags)
app.command(name="add-row")(add_field)
app.command(name="apply-content")(apply_content_main)
app.command(name="apply-rects")(apply_rects_main)
app.command(name="verify-alignment")(verify_main)
app.command(name="verify-paired")(verify_paired_main)
app.command(name="sync-bars")(sync_bars_main)
app.command(name="golden-diff")(golden_diff_main)


if __name__ == "__main__":
    app()
