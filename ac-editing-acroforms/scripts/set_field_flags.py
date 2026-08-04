"""Batch-modify AcroForm field flags in a PDF template.

Common operations:
- Make fields readonly (prevent user editing)
- Make fields required
- Clear all flags

Usage:
    uv run set_field_flags.py <pdf> --op readonly --match "clientsBorrower/*"
    uv run set_field_flags.py <pdf> --op readonly          # match defaults to '*' (all)
    uv run set_field_flags.py <pdf> --op clear-readonly --match "logo"
"""

import fnmatch
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import pypdf
import typer
from pypdf.generic import NameObject, NumberObject

# PDF field flag bits (Table 227 in PDF spec)
FF_READONLY = 1
FF_REQUIRED = 1 << 1
FF_NO_EXPORT = 1 << 2


class FlagOp(StrEnum):
    readonly = "readonly"
    clear_readonly = "clear-readonly"
    required = "required"
    clear_required = "clear-required"


OP_BITS = {
    FlagOp.readonly: (FF_READONLY, True),
    FlagOp.clear_readonly: (FF_READONLY, False),
    FlagOp.required: (FF_REQUIRED, True),
    FlagOp.clear_required: (FF_REQUIRED, False),
}


def apply_ops(flags: int, ops: list[FlagOp]) -> int:
    for op in ops:
        bit, set_bit = OP_BITS[op]
        flags = flags | bit if set_bit else flags & ~bit
    return flags


def _named_annotations(page: pypdf.PageObject):
    annots = page.get("/Annots")
    if not annots:
        return
    annots_list = annots if isinstance(annots, pypdf.generic.ArrayObject) else annots.get_object()
    for a_ref in annots_list:
        obj = a_ref.get_object()
        name = str(obj.get("/T", ""))
        if name:
            yield name, obj


@dataclass
class FlagPlan:
    ops: list[FlagOp]
    match: str
    dry_run: bool

    def selects(self, name: str) -> bool:
        return fnmatch.fnmatch(name, self.match)


def _apply_to_pages(writer: pypdf.PdfWriter, page_indices, plan: FlagPlan) -> tuple[int, int]:
    modified = 0
    skipped = 0
    for pi in page_indices:
        if pi >= len(writer.pages):
            continue
        for name, obj in _named_annotations(writer.pages[pi]):
            if not plan.selects(name):
                skipped += 1
                continue
            old_ff = int(obj.get("/Ff", 0))
            new_ff = apply_ops(old_ff, plan.ops)
            if new_ff == old_ff:
                continue
            if plan.dry_run:
                typer.echo(f"  [DRY RUN] {name}: flags {old_ff} → {new_ff}")
            else:
                obj[NameObject("/Ff")] = NumberObject(new_ff)
            modified += 1
    return modified, skipped


def set_flags(
    pdf_path: str = typer.Argument(help="Path to the PDF file (modified in place)"),
    op: list[FlagOp] = typer.Option(
        [],
        "--op",
        help="Flag operations (repeatable): readonly, clear-readonly, required, clear-required",
    ),
    match: str = typer.Option("*", "--match", "-m", help="Glob over field names ('*' = all, default)"),
    page_index: int | None = typer.Option(None, "--page", "-p", help="Only modify on this page (0-based)"),
    *,
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would change without modifying"),
) -> None:
    """Set or clear field flags (readonly, required) on AcroForm fields."""
    resolved = Path(pdf_path).expanduser()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} not found", err=True)
        raise typer.Exit(1)

    if not op:
        typer.echo("Error: specify at least one --op", err=True)
        raise typer.Exit(1)

    reader = pypdf.PdfReader(str(resolved))
    writer = pypdf.PdfWriter(clone_from=reader)

    page_indices = [page_index] if page_index is not None else range(len(writer.pages))
    plan = FlagPlan(ops=op, match=match, dry_run=dry_run)
    modified, skipped = _apply_to_pages(writer, page_indices, plan)

    if dry_run:
        typer.echo(f"\nDry run: {modified} fields would change, {skipped} skipped")
        return

    with resolved.open("wb") as f:
        writer.write(f)
    typer.echo(f"Modified {modified} fields, skipped {skipped}")
    typer.echo(f"Written: {resolved} ({resolved.stat().st_size} bytes)")
