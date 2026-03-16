#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4.0", "typer>=0.12"]
# ///
"""Inspect AcroForm fields, content stream text, and font maps in a PDF.

This is the first step before any PDF template modification — it reveals
field names, types, coordinates, font glyph mappings, and content stream
structure.

Usage:
    uv run inspect_fields.py <pdf> [--page N] [--fonts] [--content] [--labels]
"""

import re
from pathlib import Path

import pypdf
import typer

app = typer.Typer(no_args_is_help=True)


def _extract_font_maps(page: pypdf.generic.DictionaryObject) -> dict:
    """Extract ToUnicode CMap for each font on a page."""
    fonts_dict = page["/Resources"].get("/Font", {})
    result = {}
    for font_name in fonts_dict:
        font_obj = fonts_dict[font_name].get_object()
        base_font = str(font_obj.get("/BaseFont", "unknown"))
        tounicode = font_obj.get("/ToUnicode")
        mapping = {}
        if tounicode:
            cmap = tounicode.get_object().get_data().decode("latin-1")
            in_bf = False
            for line in cmap.split("\n"):
                if "beginbfchar" in line:
                    in_bf = True
                    continue
                if "endbfchar" in line:
                    in_bf = False
                    continue
                if in_bf and "<" in line:
                    m = re.findall(r"<([0-9A-Fa-f]+)>", line)
                    if len(m) == 2:
                        gid = m[0].upper().zfill(4)
                        try:
                            ch = chr(int(m[1], 16))
                        except (ValueError, OverflowError):
                            continue
                        mapping[gid] = ch
        result[font_name] = {"base_font": base_font, "glyphs": mapping}
    return result


def _decode_hex(hex_str: str, glyphs: dict) -> str:
    clean = hex_str.strip("<>")
    return "".join(glyphs.get(clean[i : i + 4].upper(), "?") for i in range(0, len(clean), 4))


@app.command()
def inspect(
    pdf_path: str = typer.Argument(help="Path to the PDF file"),
    page: int = typer.Option(-1, "--page", "-p", help="Page index (0-based). -1 = all pages"),
    fonts: bool = typer.Option(False, "--fonts", "-f", help="Show font glyph maps"),
    content: bool = typer.Option(False, "--content", "-c", help="Dump content stream text operators"),
    labels: bool = typer.Option(False, "--labels", "-l", help="Decode and list text labels with Y positions"),
    fields_only: bool = typer.Option(False, "--fields-only", help="Only show AcroForm fields, skip annotations"),
    section: str | None = typer.Option(
        None, "--section", "-s", help="Filter labels by Y range: 'income' (<300), 'charges' (<100), or 'min-max'"
    ),
) -> None:
    """Inspect AcroForm fields, fonts, and content stream in a PDF."""
    resolved = Path(pdf_path).expanduser()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} not found", err=True)
        raise typer.Exit(1)

    reader = pypdf.PdfReader(str(resolved))
    typer.echo(f"PDF: {resolved}")
    typer.echo(f"Pages: {len(reader.pages)}")

    # Global fields
    all_fields = reader.get_fields() or {}
    typer.echo(f"Total AcroForm fields: {len(all_fields)}")

    if fields_only:
        for name, field in sorted(all_fields.items()):
            ft = field.get("/FT", "?")
            ff = field.get("/Ff", 0)
            typer.echo(f"  {name}: type={ft} flags={ff}")
        return

    pages_to_inspect = range(len(reader.pages)) if page < 0 else [page]

    for pi in pages_to_inspect:
        if pi >= len(reader.pages):
            typer.echo(f"\nPage {pi}: does not exist")
            continue

        pg = reader.pages[pi]
        typer.echo(f"\n{'=' * 60}")
        typer.echo(f"Page {pi}")
        typer.echo(f"{'=' * 60}")

        # Annotations (fields on this page)
        annots = pg.get("/Annots")
        if annots:
            annots_list = annots if isinstance(annots, pypdf.generic.ArrayObject) else annots.get_object()
            typer.echo(f"\nAnnotations ({len(annots_list)}):")
            for a_ref in annots_list:
                obj = a_ref.get_object()
                name = str(obj.get("/T", "(unnamed)"))
                rect = obj.get("/Rect")
                ft = str(obj.get("/FT", ""))
                ff = int(obj.get("/Ff", 0))
                da = str(obj.get("/DA", ""))
                if rect:
                    x1, y1, x2, y2 = [float(r) for r in rect]
                    flags_str = ""
                    if ff & 1:
                        flags_str += " READONLY"
                    if ff & 2:
                        flags_str += " REQUIRED"
                    typer.echo(
                        f"  {name}: {ft} rect=[{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}] flags={ff}{flags_str} DA='{da}'"
                    )
                else:
                    typer.echo(f"  {name}: {ft} (no rect)")

        # Fonts
        if fonts:
            font_maps = _extract_font_maps(pg)
            typer.echo(f"\nFonts ({len(font_maps)}):")
            for fname, info in sorted(font_maps.items()):
                glyphs = info["glyphs"]
                typer.echo(f"  {fname} ({info['base_font']}): {len(glyphs)} glyphs")
                # Show available uppercase letters
                uppers = {ch: gid for gid, ch in glyphs.items() if ch.isupper()}
                if uppers:
                    typer.echo(f"    Uppercase: {' '.join(f'{ch}=0x{gid}' for ch, gid in sorted(uppers.items()))}")
                # Show available lowercase
                lowers = {ch: gid for gid, ch in glyphs.items() if ch.islower()}
                if lowers:
                    typer.echo(f"    Lowercase: {' '.join(f'{ch}=0x{gid}' for ch, gid in sorted(lowers.items()))}")
                # Show specials
                specials = {ch: gid for gid, ch in glyphs.items() if not ch.isalnum() and ch != " "}
                if specials:
                    typer.echo(f"    Special: {' '.join(f'{ch!r}=0x{gid}' for ch, gid in sorted(specials.items()))}")

        # Content stream labels
        if labels or content:
            contents = pg.get("/Contents")
            if contents is None:
                typer.echo("\n  (no content stream)")
                continue

            if isinstance(contents, pypdf.generic.ArrayObject):
                all_data = b""
                for ref in contents:
                    all_data += ref.get_object().get_data()
                data = all_data.decode("latin-1")
            else:
                data = contents.get_object().get_data().decode("latin-1")

            lines = data.split("\n")

            if content:
                typer.echo(f"\nContent stream ({len(lines)} lines):")
                # Show only text-related operators
                for i, line in enumerate(lines):
                    s = line.strip()
                    if any(op in s for op in ["BT", "ET", "Tf", "Tm", "Td", "TD", "T*", "Tj", "TJ", "Tr", "Tc", "Tw"]):
                        typer.echo(f"  {i:5d}: {s}")

            if labels:
                font_maps = _extract_font_maps(pg)
                # Parse section filter
                y_min, y_max = 0.0, 9999.0
                if section:
                    if section == "income":
                        y_min, y_max = 100.0, 300.0
                    elif section == "charges":
                        y_min, y_max = 0.0, 100.0
                    elif "-" in section:
                        parts = section.split("-")
                        y_min, y_max = float(parts[0]), float(parts[1])

                typer.echo(f"\nDecoded labels (y={y_min:.0f}-{y_max:.0f}):")
                cur_font = None
                cur_y = 0.0
                cur_leading = 0.0

                for i, line in enumerate(lines):
                    s = line.strip()
                    if s == "BT":
                        cur_y = 0.0
                        cur_leading = 0.0
                    m = re.match(r"/(C\w+_\d+)\s+\d+\s+Tf", s)
                    if m:
                        cur_font = "/" + m.group(1)
                    # Tm — absolute positioning
                    m = re.match(r".*?(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+Tm", s)
                    if m:
                        cur_y = float(m.group(6))
                    # Td or TD — relative positioning
                    m = re.search(r"([\d.\-]+)\s+([\d.\-]+)\s+(T[dD])\s*$", s)
                    if m:
                        cur_y += float(m.group(2))
                        if m.group(3) == "TD":
                            cur_leading = float(m.group(2))
                    if s == "T*":
                        cur_y += cur_leading
                    # Tj with hex
                    m = re.match(r"<([0-9A-Fa-f]+)>Tj", s)
                    if m and cur_font and cur_font in font_maps:
                        decoded = _decode_hex(m.group(1), font_maps[cur_font]["glyphs"])
                        if len(decoded) > 1 and "?" not in decoded and y_min <= cur_y <= y_max:
                            typer.echo(f'  line {i:5d} [{cur_font}] y={cur_y:.1f}: "{decoded}"')
                    # TJ array with hex segments and kerning adjustments
                    m = re.match(r"\[(.*)\]TJ", s)
                    if m and cur_font and cur_font in font_maps:
                        hex_parts = re.findall(r"<([0-9A-Fa-f]+)>", m.group(1))
                        if hex_parts:
                            decoded = "".join(_decode_hex(h, font_maps[cur_font]["glyphs"]) for h in hex_parts)
                            if len(decoded) > 1 and "?" not in decoded and y_min <= cur_y <= y_max:
                                typer.echo(f'  line {i:5d} [{cur_font}] y={cur_y:.1f}: "{decoded}"')

            # Underlines (cm patterns)
            if labels:
                cm_pattern = re.compile(r"([\d.]+) 0 0 1 ([\d.]+) ([\d.]+) cm")
                underlines = []
                for m in cm_pattern.finditer(data):
                    scale, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
                    if y < 300 and y > 5:
                        underlines.append((x, y, scale))
                if underlines:
                    typer.echo("\nUnderline positions (cm transforms, y<300):")
                    for x, y, sc in sorted(underlines, key=lambda t: -t[1]):
                        typer.echo(f"  x={x:.1f} y={y:.1f} scale={sc}")


if __name__ == "__main__":
    app()
