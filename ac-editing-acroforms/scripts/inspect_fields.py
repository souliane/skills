"""Inspect AcroForm fields, content stream text, and font maps in a PDF.

This is the first step before any PDF template modification — it reveals
field names, types, coordinates, font glyph mappings, and content stream
structure.

Usage:
    uv run inspect_fields.py <pdf> [--page N] [--show fonts --show content --show labels]
"""

import re
from enum import StrEnum
from pathlib import Path

import pypdf
import typer

app = typer.Typer(no_args_is_help=True)


class Show(StrEnum):
    fields_only = "fields-only"
    fonts = "fonts"
    content = "content"
    labels = "labels"


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


def _print_global_fields(reader: pypdf.PdfReader) -> None:
    all_fields = reader.get_fields() or {}
    for name, field in sorted(all_fields.items()):
        ft = field.get("/FT", "?")
        ff = field.get("/Ff", 0)
        typer.echo(f"  {name}: type={ft} flags={ff}")


def _print_annotations(pg: pypdf.PageObject) -> None:
    annots = pg.get("/Annots")
    if not annots:
        return
    annots_list = annots if isinstance(annots, pypdf.generic.ArrayObject) else annots.get_object()
    typer.echo(f"\nAnnotations ({len(annots_list)}):")
    for a_ref in annots_list:
        obj = a_ref.get_object()
        name = str(obj.get("/T", "(unnamed)"))
        rect = obj.get("/Rect")
        ft = str(obj.get("/FT", ""))
        ff = int(obj.get("/Ff", 0))
        da = str(obj.get("/DA", ""))
        if not rect:
            typer.echo(f"  {name}: {ft} (no rect)")
            continue
        x1, y1, x2, y2 = [float(r) for r in rect]
        flags_str = (" READONLY" if ff & 1 else "") + (" REQUIRED" if ff & 2 else "")
        typer.echo(f"  {name}: {ft} rect=[{x1:.1f},{y1:.1f},{x2:.1f},{y2:.1f}] flags={ff}{flags_str} DA='{da}'")


def _glyph_line(label: str, glyphs: dict, predicate) -> str | None:
    selected = {ch: gid for gid, ch in glyphs.items() if predicate(ch)}
    if not selected:
        return None
    return f"    {label}: {' '.join(f'{ch}=0x{gid}' for ch, gid in sorted(selected.items()))}"


def _print_fonts(pg: pypdf.PageObject) -> None:
    font_maps = _extract_font_maps(pg)
    typer.echo(f"\nFonts ({len(font_maps)}):")
    for fname, info in sorted(font_maps.items()):
        glyphs = info["glyphs"]
        typer.echo(f"  {fname} ({info['base_font']}): {len(glyphs)} glyphs")
        for label, predicate in (("Uppercase", str.isupper), ("Lowercase", str.islower)):
            line = _glyph_line(label, glyphs, predicate)
            if line:
                typer.echo(line)
        specials = {ch: gid for gid, ch in glyphs.items() if not ch.isalnum() and ch != " "}
        if specials:
            typer.echo(f"    Special: {' '.join(f'{ch!r}=0x{gid}' for ch, gid in sorted(specials.items()))}")


def _page_content_data(pg: pypdf.PageObject) -> str | None:
    contents = pg.get("/Contents")
    if contents is None:
        return None
    if isinstance(contents, pypdf.generic.ArrayObject):
        return b"".join(ref.get_object().get_data() for ref in contents).decode("latin-1")
    return contents.get_object().get_data().decode("latin-1")


TEXT_OPERATORS = ("BT", "ET", "Tf", "Tm", "Td", "TD", "T*", "Tj", "TJ", "Tr", "Tc", "Tw")


def _print_content_operators(lines: list[str]) -> None:
    typer.echo(f"\nContent stream ({len(lines)} lines):")
    for i, line in enumerate(lines):
        s = line.strip()
        if any(op in s for op in TEXT_OPERATORS):
            typer.echo(f"  {i:5d}: {s}")


def _section_range(section: str | None) -> tuple[float, float]:
    if not section:
        return 0.0, 9999.0
    if section == "income":
        return 100.0, 300.0
    if section == "charges":
        return 0.0, 100.0
    if "-" in section:
        parts = section.split("-")
        return float(parts[0]), float(parts[1])
    return 0.0, 9999.0


def _decoded_segments(s: str, cur_font: str, font_maps: dict) -> str | None:
    glyphs = font_maps[cur_font]["glyphs"]
    m = re.match(r"<([0-9A-Fa-f]+)>Tj", s)
    if m:
        return _decode_hex(m.group(1), glyphs)
    m = re.match(r"\[(.*)\]TJ", s)
    if m:
        hex_parts = re.findall(r"<([0-9A-Fa-f]+)>", m.group(1))
        if hex_parts:
            return "".join(_decode_hex(h, glyphs) for h in hex_parts)
    return None


def _print_labels(lines: list[str], font_maps: dict, section: str | None) -> None:
    y_min, y_max = _section_range(section)
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
        m = re.match(r".*?(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+Tm", s)
        if m:
            cur_y = float(m.group(6))
        m = re.search(r"([\d.\-]+)\s+([\d.\-]+)\s+(T[dD])\s*$", s)
        if m:
            cur_y += float(m.group(2))
            if m.group(3) == "TD":
                cur_leading = float(m.group(2))
        if s == "T*":
            cur_y += cur_leading
        if cur_font and cur_font in font_maps:
            decoded = _decoded_segments(s, cur_font, font_maps)
            if decoded and len(decoded) > 1 and "?" not in decoded and y_min <= cur_y <= y_max:
                typer.echo(f'  line {i:5d} [{cur_font}] y={cur_y:.1f}: "{decoded}"')


def _print_underlines(data: str) -> None:
    cm_pattern = re.compile(r"([\d.]+) 0 0 1 ([\d.]+) ([\d.]+) cm")
    underlines = [
        (float(m.group(2)), float(m.group(3)), float(m.group(1)))
        for m in cm_pattern.finditer(data)
        if 5 < float(m.group(3)) < 300
    ]
    if underlines:
        typer.echo("\nUnderline positions (cm transforms, y<300):")
        for x, y, sc in sorted(underlines, key=lambda t: -t[1]):
            typer.echo(f"  x={x:.1f} y={y:.1f} scale={sc}")


def _inspect_page(pg: pypdf.PageObject, pi: int, show: set[Show], section: str | None) -> None:
    typer.echo(f"\n{'=' * 60}")
    typer.echo(f"Page {pi}")
    typer.echo(f"{'=' * 60}")

    _print_annotations(pg)
    if Show.fonts in show:
        _print_fonts(pg)

    if not (Show.labels in show or Show.content in show):
        return
    data = _page_content_data(pg)
    if data is None:
        typer.echo("\n  (no content stream)")
        return
    lines = data.split("\n")
    if Show.content in show:
        _print_content_operators(lines)
    if Show.labels in show:
        _print_labels(lines, _extract_font_maps(pg), section)
        _print_underlines(data)


@app.command()
def inspect(
    pdf_path: str = typer.Argument(help="Path to the PDF file"),
    page: int = typer.Option(-1, "--page", "-p", help="Page index (0-based). -1 = all pages"),
    show: list[Show] = typer.Option(
        [],
        "--show",
        "-s",
        help="What to display (repeatable): fields-only, fonts, content, labels",
    ),
    section: str | None = typer.Option(
        None, "--section", help="Filter labels by Y range: 'income' (<300), 'charges' (<100), or 'min-max'"
    ),
) -> None:
    """Inspect AcroForm fields, fonts, and content stream in a PDF."""
    resolved = Path(pdf_path).expanduser()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} not found", err=True)
        raise typer.Exit(1)

    show_set = set(show)
    reader = pypdf.PdfReader(str(resolved))
    typer.echo(f"PDF: {resolved}")
    typer.echo(f"Pages: {len(reader.pages)}")
    typer.echo(f"Total AcroForm fields: {len(reader.get_fields() or {})}")

    if Show.fields_only in show_set:
        _print_global_fields(reader)
        return

    pages_to_inspect = range(len(reader.pages)) if page < 0 else [page]
    for pi in pages_to_inspect:
        if pi >= len(reader.pages):
            typer.echo(f"\nPage {pi}: does not exist")
            continue
        _inspect_page(reader.pages[pi], pi, show_set, section)
