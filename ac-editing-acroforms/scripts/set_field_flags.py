#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4.0", "typer>=0.9"]
# ///
"""Batch-modify AcroForm field flags in a PDF template.

Common operations:
- Make fields readonly (prevent user editing)
- Make fields required
- Clear all flags

Usage:
    uv run set_field_flags.py <pdf> --readonly --match "clientsBorrower/*" [-o output.pdf]
    uv run set_field_flags.py <pdf> --readonly --all
    uv run set_field_flags.py <pdf> --clear-readonly --match "logo"
"""

import fnmatch
from pathlib import Path

import pypdf
import typer
from pypdf.generic import NameObject, NumberObject

app = typer.Typer(no_args_is_help=True)

# PDF field flag bits (Table 227 in PDF spec)
FF_READONLY = 1
FF_REQUIRED = 1 << 1
FF_NO_EXPORT = 1 << 2


@app.command()
def set_flags(
    pdf_path: str = typer.Argument(help="Path to the PDF file"),
    readonly: bool = typer.Option(False, "--readonly", help="Set fields as read-only"),
    clear_readonly: bool = typer.Option(False, "--clear-readonly", help="Remove read-only flag"),
    required: bool = typer.Option(False, "--required", help="Set fields as required"),
    clear_required: bool = typer.Option(False, "--clear-required", help="Remove required flag"),
    match: str | None = typer.Option(
        None, "--match", "-m", help="Glob pattern to match field names (e.g., 'clientsBorrower/*')"
    ),
    all_fields: bool = typer.Option(False, "--all", help="Apply to all fields"),
    page_index: int | None = typer.Option(None, "--page", "-p", help="Only modify on this page (0-based)"),
    output: str | None = typer.Option(None, "-o", help="Output path (default: overwrite)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without modifying"),
) -> None:
    """Set or clear field flags (readonly, required) on AcroForm fields."""
    resolved = Path(pdf_path).expanduser()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} not found", err=True)
        raise typer.Exit(1)

    if not (readonly or clear_readonly or required or clear_required):
        typer.echo("Error: specify at least one flag operation", err=True)
        raise typer.Exit(1)

    if not (match or all_fields):
        typer.echo("Error: specify --match pattern or --all", err=True)
        raise typer.Exit(1)

    reader = pypdf.PdfReader(str(resolved))
    writer = pypdf.PdfWriter(clone_from=reader)

    output_path = output or str(resolved)
    modified = 0
    skipped = 0

    pages_to_check = [page_index] if page_index is not None else range(len(writer.pages))

    for pi in pages_to_check:
        if pi >= len(writer.pages):
            continue
        page = writer.pages[pi]
        annots = page.get("/Annots")
        if not annots:
            continue
        annots_list = annots if isinstance(annots, pypdf.generic.ArrayObject) else annots.get_object()

        for a_ref in annots_list:
            obj = a_ref.get_object()
            name = str(obj.get("/T", ""))
            if not name:
                continue

            if not all_fields and match and not fnmatch.fnmatch(name, match):
                skipped += 1
                continue

            old_ff = int(obj.get("/Ff", 0))
            new_ff = old_ff

            if readonly:
                new_ff |= FF_READONLY
            if clear_readonly:
                new_ff &= ~FF_READONLY
            if required:
                new_ff |= FF_REQUIRED
            if clear_required:
                new_ff &= ~FF_REQUIRED

            if new_ff != old_ff:
                if dry_run:
                    typer.echo(f"  [DRY RUN] {name}: flags {old_ff} → {new_ff}")
                else:
                    obj[NameObject("/Ff")] = NumberObject(new_ff)
                modified += 1

    if dry_run:
        typer.echo(f"\nDry run: {modified} fields would change, {skipped} skipped")
    else:
        Path(output_path).resolve().parent.mkdir(exist_ok=True, parents=True)
        with Path(output_path).open("wb") as f:
            writer.write(f)
        typer.echo(f"Modified {modified} fields, skipped {skipped}")
        typer.echo(f"Written: {output_path} ({Path(output_path).stat().st_size} bytes)")


if __name__ == "__main__":
    app()
