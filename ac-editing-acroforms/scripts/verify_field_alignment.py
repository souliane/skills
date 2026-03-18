r"""Verify that AcroForm field rectangles align with content stream underline bars.

Checks structural integrity of PDF templates by comparing:
1. Underline bar positions from content stream (cm + line-draw operators)
2. AcroForm field annotation rects
3. Cross-template consistency for same-named fields

Usage:
    uv run verify_field_alignment.py templates/nl_broker/.../template.pdf --page 1
    uv run verify_field_alignment.py templates/**/*.pdf --page 1 --cross
    uv run verify_field_alignment.py templates/**/*.pdf --page 1 \\
        --golden-dir src/test/resources/com/example/docGen/ --pixel
"""

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import pikepdf  # ty: ignore[unresolved-import]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Underline:
    """An underline bar extracted from the content stream."""

    x: float
    y: float
    width: float
    scale: float
    column: int  # 1 or 2

    @property
    def col_label(self) -> str:
        return f"col{self.column}"


@dataclass
class FieldRect:
    """An AcroForm field annotation."""

    name: str
    x1: float
    y1: float
    x2: float
    y2: float
    column: int  # 1 or 2

    @property
    def col_label(self) -> str:
        return f"col{self.column}"

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def width(self) -> float:
        return self.x2 - self.x1


@dataclass
class AlignmentResult:
    """Result of checking one field against its nearest underline."""

    field: FieldRect
    nearest_underline: Underline | None
    offset: float  # underline_y - field_y1
    aligned: bool
    suggested_rect: tuple[float, float] | None = None  # (y1, y2) if misaligned
    unmatched_underline_y: float | None = None


@dataclass
class TemplateReport:
    """Full verification report for one template."""

    path: str
    name: str
    page: int
    underlines_col1: list[Underline] = field(default_factory=list)
    underlines_col2: list[Underline] = field(default_factory=list)
    fields_col1: list[FieldRect] = field(default_factory=list)
    fields_col2: list[FieldRect] = field(default_factory=list)
    alignments: list[AlignmentResult] = field(default_factory=list)
    unmatched_underlines: list[Underline] = field(default_factory=list)
    unmatched_fields: list[FieldRect] = field(default_factory=list)
    pixel_results: list[tuple[str, bool, str]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return (
            all(a.aligned for a in self.alignments)
            and not self.unmatched_underlines
            and not self.unmatched_fields
            and not self.errors
            and all(ok for _, ok, _ in self.pixel_results)
        )


# ---------------------------------------------------------------------------
# Content stream parsing
# ---------------------------------------------------------------------------

# Matches: scale 0 0 1 x y cm (underline transform)
CM_PATTERN = re.compile(r"([\d.]+)\s+0\s+0\s+1\s+([\d.]+)\s+([\d.]+)\s+cm")

# Matches: width 0 l (line-to for underline)
LINE_PATTERN = re.compile(r"([\d.]+)\s+0\s+l")


def _get_content_stream(page: pikepdf.Page) -> str:
    """Extract the full content stream text from a page."""
    contents = page.get("/Contents")
    if contents is None:
        return ""
    if isinstance(contents, pikepdf.Array):
        parts = []
        for ref in contents:
            obj = ref.get_object() if hasattr(ref, "get_object") else ref
            data = obj.read_bytes() if hasattr(obj, "read_bytes") else bytes(obj)
            parts.append(data)
        return b"".join(parts).decode("latin-1")
    obj = contents.get_object() if hasattr(contents, "get_object") else contents
    data = obj.read_bytes() if hasattr(obj, "read_bytes") else bytes(obj)
    return data.decode("latin-1")


def extract_underlines(
    content: str,
    y_min: float = 5.0,
    y_max: float = 300.0,
    col_boundary: float = 300.0,
) -> list[Underline]:
    """Extract underline bar positions from content stream.

    Pattern: q -> scale 0 0 1 x y cm -> 0 0 m -> width 0 l -> S -> Q
    """
    underlines: list[Underline] = []
    lines = content.split("\n")

    i = 0
    while i < len(lines):
        s = lines[i].strip()
        # Look for cm pattern
        cm_m = CM_PATTERN.match(s)
        if cm_m:
            scale = float(cm_m.group(1))
            x = float(cm_m.group(2))
            y = float(cm_m.group(3))

            if y_min <= y <= y_max:
                # Look ahead for 0 0 m, then width 0 l, then S
                has_move = False
                width = 0.0
                has_stroke = False
                for j in range(i + 1, min(i + 5, len(lines))):
                    sj = lines[j].strip()
                    if sj == "0 0 m":
                        has_move = True
                    lm = LINE_PATTERN.match(sj)
                    if lm and has_move:
                        width = float(lm.group(1))
                    if sj == "S" and has_move and width > 50:
                        has_stroke = True
                        break

                if has_stroke:
                    col = 1 if x < col_boundary else 2
                    underlines.append(Underline(x=x, y=y, width=width, scale=scale, column=col))
        i += 1

    return underlines


# ---------------------------------------------------------------------------
# Field annotation parsing
# ---------------------------------------------------------------------------


def extract_fields(
    page: pikepdf.Page,
    y_min: float = 5.0,
    y_max: float = 300.0,
    col_boundary: float = 300.0,
    min_field_width: float = 100.0,
) -> list[FieldRect]:
    """Extract AcroForm field rects from page annotations."""
    fields: list[FieldRect] = []
    annots = page.get("/Annots")
    if annots is None:
        return fields

    annot_list = list(annots)
    unnamed_idx = 0
    for aref in annot_list:
        obj = aref.get_object() if hasattr(aref, "get_object") else aref
        rect = obj.get("/Rect")
        if rect is None:
            continue

        x1, y1, x2, y2 = float(rect[0]), float(rect[1]), float(rect[2]), float(rect[3])
        w = x2 - x1

        # Filter to section-sized fields (skip signature boxes, checkboxes, etc.)
        if not (y_min <= y1 <= y_max and w >= min_field_width and w < 250):
            continue

        name_obj = obj.get("/T")
        if name_obj is not None:
            name = str(name_obj)
        else:
            # Include unnamed fields — they still need alignment verification
            unnamed_idx += 1
            col = 1 if x1 < col_boundary else 2
            name = f"(unnamed#{unnamed_idx} col{col} y={y1:.0f})"

        col = 1 if x1 < col_boundary else 2
        fields.append(FieldRect(name=name, x1=x1, y1=y1, x2=x2, y2=y2, column=col))

    return fields


# ---------------------------------------------------------------------------
# Alignment checking
# ---------------------------------------------------------------------------


def match_fields_to_underlines(
    fields: list[FieldRect],
    underlines: list[Underline],
    tolerance: float = 3.0,
) -> tuple[list[AlignmentResult], list[Underline], list[FieldRect]]:
    """Match fields to their nearest underline by Y proximity within same column.

    Primary check: underline_y must fall inside [field_y1 - tolerance, field_y2 + tolerance].
    This handles fields of varying heights (single-line ~12pt vs multi-line ~20pt).

    Secondary check (ordering): fields and underlines sorted by Y should pair 1-to-1.
    A field matched to the WRONG underline (even if contained) is still misaligned.
    """
    results: list[AlignmentResult] = []
    matched_underline_indices: set[int] = set()
    matched_field_indices: set[int] = set()

    # Strategy: sort fields and underlines by Y descending per column, match 1-to-1
    for col in (1, 2):
        col_fields = [(fi, f) for fi, f in enumerate(fields) if f.column == col]
        col_uls = [(ui, u) for ui, u in enumerate(underlines) if u.column == col]
        col_fields.sort(key=lambda p: -p[1].y1)  # top to bottom (highest y first)
        col_uls.sort(key=lambda p: -p[1].y)

        # Try 1-to-1 ordered matching first (most reliable)
        # For each field, find the best underline that:
        # 1. Falls inside or near the field rect
        # 2. Hasn't been matched yet
        for fi, f in col_fields:
            best_ui = None
            best_u = None
            best_dist = 999.0

            for ui, u in col_uls:
                if ui in matched_underline_indices:
                    continue
                # Check containment: underline_y inside field rect (with tolerance)
                if f.y1 - tolerance <= u.y <= f.y2 + tolerance:
                    dist = abs(u.y - (f.y1 + f.y2) / 2)
                    if dist < best_dist:
                        best_dist = dist
                        best_ui = ui
                        best_u = u

            if best_u is None:
                # No containing underline — find nearest for diagnostics
                available = [(ui, u) for ui, u in col_uls if ui not in matched_underline_indices]
                if available:
                    best_ui, best_u = min(available, key=lambda p: abs(p[1].y - (f.y1 + 1.5)))

            if best_u is None:
                results.append(AlignmentResult(field=f, nearest_underline=None, offset=999, aligned=False))
                continue

            offset = best_u.y - f.y1
            # Aligned if underline is inside field rect (with tolerance)
            inside = f.y1 - tolerance <= best_u.y <= f.y2 + tolerance
            aligned = inside

            result = AlignmentResult(field=f, nearest_underline=best_u, offset=offset, aligned=aligned)

            if aligned:
                matched_underline_indices.add(best_ui)
                matched_field_indices.add(fi)
            else:
                # Suggest corrected rect based on nearest underline
                # Use typical offset pattern: field_y1 ≈ underline_y - 1.5
                suggested_y1 = best_u.y - 1.5
                suggested_y2 = suggested_y1 + f.height
                result.suggested_rect = (suggested_y1, suggested_y2)

            results.append(result)

    # Collect unmatched
    unmatched_uls = [u for ui, u in enumerate(underlines) if ui not in matched_underline_indices]
    unmatched_fs = [f for fi, f in enumerate(fields) if fi not in matched_field_indices]

    return results, unmatched_uls, unmatched_fs


# ---------------------------------------------------------------------------
# Pixel-level verification
# ---------------------------------------------------------------------------


def _find_gs() -> str | None:
    """Find GhostScript binary."""
    for candidate in ["/opt/homebrew/bin/gs", "gs"]:
        if shutil.which(candidate):
            return candidate
    return None


def render_pdf_page(pdf_path: str | Path, page: int, out_png: Path, dpi: int = 300) -> bool:
    """Render a single PDF page to PNG via GhostScript."""
    gs = _find_gs()
    if not gs:
        return False
    cmd = [
        gs,
        "-sDEVICE=png16m",
        f"-r{dpi}",
        f"-dFirstPage={page}",
        f"-dLastPage={page}",
        "-dTextAlphaBits=4",
        "-dGraphicsAlphaBits=4",
        "-o",
        str(out_png),
        str(pdf_path),
    ]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0 and out_png.exists()


def check_pixel_coverage(
    golden_pdf: str | Path,
    page: int,
    fields: list[FieldRect],
    underlines: list[Underline],
    dpi: int = 300,
) -> list[tuple[str, bool, str]]:
    """Check that field positions have non-white pixels in the rendered golden PDF.

    Returns list of (field_name, ok, detail_message).
    """
    try:
        from PIL import Image
    except ImportError:
        return [("(pixel check)", False, "Pillow not installed")]

    with tempfile.TemporaryDirectory(prefix="verify-pixel-") as tmpdir:
        png_path = Path(tmpdir) / "page.png"
        if not render_pdf_page(golden_pdf, page, png_path, dpi=dpi):
            return [("(pixel check)", False, "GhostScript render failed")]

        img = Image.open(png_path).convert("RGB")
        img_w, img_h = img.size

        # PDF coordinate system: origin at bottom-left
        # PNG coordinate system: origin at top-left
        # We need the page mediabox to convert coordinates
        pdf = pikepdf.open(str(golden_pdf))
        pg = pdf.pages[page - 1]
        mediabox = pg.get("/MediaBox")
        if mediabox:
            pdf_w = float(mediabox[2]) - float(mediabox[0])
            pdf_h = float(mediabox[3]) - float(mediabox[1])
        else:
            pdf_w, pdf_h = 595.0, 842.0  # A4 default

        scale_x = img_w / pdf_w
        scale_y = img_h / pdf_h

        results: list[tuple[str, bool, str]] = []

        for f in fields:
            # Convert PDF coords to pixel coords
            px1 = int(f.x1 * scale_x)
            px2 = int(f.x2 * scale_x)
            # PDF y is from bottom, PNG y is from top
            py1 = int((pdf_h - f.y2) * scale_y)
            py2 = int((pdf_h - f.y1) * scale_y)

            # Clamp to image bounds
            px1 = max(0, min(px1, img_w - 1))
            px2 = max(0, min(px2, img_w - 1))
            py1 = max(0, min(py1, img_h - 1))
            py2 = max(0, min(py2, img_h - 1))

            if px2 <= px1 or py2 <= py1:
                results.append((f.name, False, "invalid pixel region"))
                continue

            # Sample the field region for non-white pixels
            region = img.crop((px1, py1, px2, py2))
            pixels = list(region.getdata())
            non_white = sum(1 for r, g, b in pixels if r < 240 or g < 240 or b < 240)
            total = len(pixels)
            coverage = non_white / total if total > 0 else 0

            if coverage < 0.01:
                results.append((f.name, False, f"no AP visible (coverage={coverage:.1%})"))
            else:
                results.append((f.name, True, f"coverage={coverage:.1%}"))

        # Check underline bars have grey pixels
        for u in underlines:
            px_start = int(u.x * scale_x)
            px_end = int((u.x + u.width * u.scale) * scale_x)
            # Underline is a thin bar; check a 5px band around it
            py_center = int((pdf_h - u.y) * scale_y)
            py1 = max(0, py_center - 3)
            py2 = min(img_h - 1, py_center + 3)

            px_start = max(0, min(px_start, img_w - 1))
            px_end = max(0, min(px_end, img_w - 1))

            if px_end <= px_start or py2 <= py1:
                continue

            region = img.crop((px_start, py1, px_end, py2))
            pixels = list(region.getdata())
            grey_count = sum(1 for r, g, b in pixels if 150 < r < 230 and 150 < g < 230 and 150 < b < 230)
            if grey_count < 5:
                results.append(
                    (
                        f"underline@y={u.y:.1f}({u.col_label})",
                        False,
                        "no grey pixels found at underline position",
                    )
                )

        pdf.close()

    return results


# ---------------------------------------------------------------------------
# Cross-template consistency
# ---------------------------------------------------------------------------


def check_cross_consistency(
    reports: list[TemplateReport],
) -> list[str]:
    """Compare field Y positions across templates for same-named fields."""
    warnings: list[str] = []
    if len(reports) < 2:
        return warnings

    # Build a map: field_base_name -> [(template_name, y1)]
    field_map: dict[str, list[tuple[str, float]]] = {}
    for report in reports:
        for f in report.fields_col1 + report.fields_col2:
            # Normalize field name: strip borrower index prefix
            # e.g., "clientsBorrower/0/childAllowance" -> "childAllowance"
            parts = f.name.split("/")
            base_name = parts[-1] if len(parts) > 1 else f.name
            key = f"{base_name}_col{f.column}"
            field_map.setdefault(key, []).append((report.name, f.y1))

    for key, entries in sorted(field_map.items()):
        if len(entries) < 2:
            continue
        ys = [y for _, y in entries]
        max_delta = max(ys) - min(ys)
        if max_delta > 5.0:
            pairs = " vs ".join(f"{name} y={y:.1f}" for name, y in entries)
            warnings.append(f"{key}: {pairs} -- DELTA={max_delta:.1f}pt WARNING")

    return warnings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def format_report(report: TemplateReport, *, verbose: bool = False) -> str:
    """Format a template report for console output."""
    lines: list[str] = []
    lines.extend(
        [
            f"\n{'=' * 70}",
            f"  {report.name}",
            f"  {report.path}",
            f"{'=' * 70}",
        ]
    )

    n_ul1 = len(report.underlines_col1)
    n_ul2 = len(report.underlines_col2)
    n_f1 = len(report.fields_col1)
    n_f2 = len(report.fields_col2)

    count_status_1 = "OK" if n_ul1 == n_f1 else "MISMATCH"
    count_status_2 = "OK" if n_ul2 == n_f2 else "MISMATCH"

    lines.extend(
        [
            f"\n  Page {report.page}:",
            f"    Col1: {n_ul1} underlines, {n_f1} fields -- {count_status_1}",
            f"    Col2: {n_ul2} underlines, {n_f2} fields -- {count_status_2}",
        ]
    )

    # Field alignment details
    misaligned = [a for a in report.alignments if not a.aligned]
    aligned_count = len(report.alignments) - len(misaligned)

    lines.append(f"\n  Field alignment: {aligned_count}/{len(report.alignments)} OK")

    if verbose:
        for a in report.alignments:
            if a.nearest_underline:
                status = "OK" if a.aligned else f"MISALIGNED (underline outside rect by {abs(a.offset):.1f}pt)"
                lines.append(
                    f"    {a.field.name}:"
                    f"  rect_y=[{a.field.y1:.1f}, {a.field.y2:.1f}]"
                    f"  underline_y={a.nearest_underline.y:.1f}"
                    f"  offset={a.offset:+.1f}  {status}"
                )
            else:
                lines.append(f"    {a.field.name}:  NO UNDERLINE FOUND")

    if misaligned:
        lines.append("\n  Misaligned fields:")
        for a in misaligned:
            if a.nearest_underline:
                lines.append(
                    f"    {a.field.name}:"
                    f"  rect_y=[{a.field.y1:.1f}, {a.field.y2:.1f}]"
                    f"  nearest_underline_y={a.nearest_underline.y:.1f}"
                    f"  offset={a.offset:+.1f}"
                )
                if a.suggested_rect:
                    lines.append(f"      suggested_rect_y=[{a.suggested_rect[0]:.1f}, {a.suggested_rect[1]:.1f}]")
            else:
                lines.append(f"    {a.field.name}:  no matching underline")

    if report.unmatched_underlines:
        lines.append("\n  Unmatched underlines:")
        lines.extend(f"    y={u.y:.1f} ({u.col_label}, x={u.x:.1f})" for u in report.unmatched_underlines)

    if report.unmatched_fields:
        lines.append("\n  Unmatched fields:")
        lines.extend(f"    {f.name} rect_y=[{f.y1:.1f}, {f.y2:.1f}] ({f.col_label})" for f in report.unmatched_fields)

    if report.pixel_results:
        ok_count = sum(1 for _, ok, _ in report.pixel_results if ok)
        fail_count = len(report.pixel_results) - ok_count
        lines.append(f"\n  [Pixel check] {ok_count}/{len(report.pixel_results)} OK")
        if fail_count:
            for name, ok, detail in report.pixel_results:
                if not ok:
                    lines.append(f"    FAIL: {name} -- {detail}")

    if report.errors:
        lines.append("\n  Errors:")
        lines.extend(f"    {e}" for e in report.errors)

    return "\n".join(lines)


def format_fix_commands(report: TemplateReport) -> str:
    """Generate pikepdf fix commands for misaligned fields."""
    lines: list[str] = []
    misaligned = [a for a in report.alignments if not a.aligned and a.suggested_rect]
    if not misaligned:
        return ""

    lines.extend(
        [
            f"\n# Fix commands for {report.name}",
            f"# pdf_path = {report.path!r}",
            "import pikepdf",
            f"pdf = pikepdf.open({report.path!r})",
            f"page = pdf.pages[{report.page - 1}]",
            "annots = list(page['/Annots'])",
            "for annot in annots:",
            "    obj = annot.get_object() if hasattr(annot, 'get_object') else annot",
            "    name = str(obj.get('/T', ''))",
            "    rect = obj.get('/Rect')",
            "    if rect is None:",
            "        continue",
        ]
    )

    for a in misaligned:
        sy1, sy2 = a.suggested_rect  # type: ignore[misc]
        lines.extend(
            [
                f"    if name == {a.field.name!r}:",
                f"        rect[1] = pikepdf.Object.parse('{sy1:.3f}')",
                f"        rect[3] = pikepdf.Object.parse('{sy2:.3f}')",
                f"        # was y=[{a.field.y1:.1f}, {a.field.y2:.1f}], underline_y={a.nearest_underline.y:.1f}",
            ]
        )

    lines.append(f"pdf.save({report.path!r})")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main verification logic
# ---------------------------------------------------------------------------


def verify_template(
    pdf_path: str,
    page: int,
    tolerance: float,
    section: str | None,
    golden_dir: str | None,
    pixel: bool,
) -> TemplateReport:
    """Run all verification checks on a single template."""
    name = Path(pdf_path).stem
    report = TemplateReport(path=pdf_path, name=name, page=page)

    try:
        pdf = pikepdf.open(pdf_path)
    except (OSError, pikepdf.PdfError) as err:
        report.errors.append(f"Cannot open PDF: {err}")
        return report

    if page < 1 or page > len(pdf.pages):
        report.errors.append(f"Page {page} out of range (PDF has {len(pdf.pages)} pages)")
        pdf.close()
        return report

    pg = pdf.pages[page - 1]

    # Determine Y range based on section filter
    y_min, y_max = 5.0, 300.0
    if section:
        if section == "income":
            y_min, y_max = 50.0, 280.0
        elif section == "charges":
            y_min, y_max = 0.0, 50.0
        elif "-" in section:
            parts = section.split("-")
            y_min, y_max = float(parts[0]), float(parts[1])

    # 1. Extract underlines from content stream
    content = _get_content_stream(pg)
    if not content:
        report.errors.append("Empty content stream")
        pdf.close()
        return report

    all_underlines = extract_underlines(content, y_min=y_min, y_max=y_max)
    report.underlines_col1 = sorted([u for u in all_underlines if u.column == 1], key=lambda u: -u.y)
    report.underlines_col2 = sorted([u for u in all_underlines if u.column == 2], key=lambda u: -u.y)

    # 2. Extract field annotations
    all_fields = extract_fields(pg, y_min=y_min, y_max=y_max)
    report.fields_col1 = sorted([f for f in all_fields if f.column == 1], key=lambda f: -f.y1)
    report.fields_col2 = sorted([f for f in all_fields if f.column == 2], key=lambda f: -f.y1)

    # 3. Match and check alignment
    results, unmatched_uls, unmatched_fs = match_fields_to_underlines(all_fields, all_underlines, tolerance=tolerance)
    report.alignments = results
    report.unmatched_underlines = unmatched_uls
    report.unmatched_fields = unmatched_fs

    pdf.close()

    # 4. Pixel-level checks (optional)
    if pixel and golden_dir:
        golden_pdf = _find_golden_pdf(pdf_path, golden_dir)
        if golden_pdf:
            report.pixel_results = check_pixel_coverage(golden_pdf, page, all_fields, all_underlines)
        else:
            report.errors.append(f"No golden PDF found in {golden_dir} for {name}")

    return report


def _find_golden_pdf(template_path: str, golden_dir: str) -> str | None:
    """Find the golden (filled) PDF corresponding to a template.

    Heuristic: match template stem in golden directory filenames.
    """
    stem = Path(template_path).stem
    golden_path = Path(golden_dir)
    if not golden_path.exists():
        return None

    # Try exact match first
    for p in golden_path.rglob("*.pdf"):
        if stem in p.stem:
            return str(p)

    # Try partial match (template name without _form suffix)
    short = stem.replace("_form", "").replace("loan_request_", "")
    for p in golden_path.rglob("*.pdf"):
        if short in p.stem:
            return str(p)

    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify AcroForm field alignment with content stream underlines.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
    # Check a single template (page 2, 1-indexed)
    uv run verify_field_alignment.py templates/nl_broker/.../template.pdf --page 2

    # Check all templates with cross-template consistency
    uv run verify_field_alignment.py 'templates/**/*.pdf' --page 2 --cross

    # Include pixel-level checks
    uv run verify_field_alignment.py 'templates/**/*.pdf' --page 2 \\
        --golden-dir src/test/resources/com/example/docGen/ --pixel

    # Focus on income section with custom tolerance
    uv run verify_field_alignment.py template.pdf --page 2 --section income --tolerance 2.0
""",
    )
    parser.add_argument(
        "pdf_paths",
        nargs="+",
        help="PDF template path(s). Supports shell globs.",
    )
    parser.add_argument(
        "--page",
        "-p",
        type=int,
        default=2,
        help="Page number to check (1-indexed, default: 2).",
    )
    parser.add_argument(
        "--tolerance",
        "-t",
        type=float,
        default=3.0,
        help="Alignment tolerance in points (default: 3.0).",
    )
    parser.add_argument(
        "--section",
        "-s",
        type=str,
        default=None,
        help="Section filter: 'income', 'charges', or 'min-max' Y range.",
    )
    parser.add_argument(
        "--golden-dir",
        type=str,
        default=None,
        help="Directory containing golden (filled) PDFs for pixel checks.",
    )
    parser.add_argument(
        "--pixel",
        action="store_true",
        help="Enable pixel-level verification (requires --golden-dir and GhostScript).",
    )
    parser.add_argument(
        "--cross",
        action="store_true",
        help="Enable cross-template consistency checks.",
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Output suggested pikepdf commands to fix misaligned fields.",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show all field alignments, not just misaligned ones.",
    )
    return parser


def resolve_pdf_paths(patterns: list[str]) -> list[str]:
    """Expand glob patterns to actual file paths."""
    paths: list[str] = []
    for pattern in patterns:
        if "*" in pattern or "?" in pattern or "[" in pattern:
            if Path(pattern).is_absolute():
                root = Path(Path(pattern).anchor)
                expanded = root.glob(pattern[len(Path(pattern).anchor) :])
            else:
                expanded = Path().glob(pattern)
            paths.extend(str(p) for p in expanded if p.suffix == ".pdf")
        elif Path(pattern).exists():
            paths.append(pattern)
        else:
            print(f"Warning: {pattern} not found", file=sys.stderr)
    return sorted(set(paths))


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.pixel and not args.golden_dir:
        parser.error("--pixel requires --golden-dir")

    if args.pixel and not _find_gs():
        print("Error: GhostScript not found. Install with: brew install ghostscript", file=sys.stderr)
        return 1

    pdf_paths = resolve_pdf_paths(args.pdf_paths)
    if not pdf_paths:
        print("No PDF files found matching the given patterns.", file=sys.stderr)
        return 1

    print(f"Checking {len(pdf_paths)} template(s), page {args.page}, tolerance={args.tolerance}pt")

    reports: list[TemplateReport] = []
    all_ok = True

    for pdf_path in pdf_paths:
        report = verify_template(
            pdf_path=pdf_path,
            page=args.page,
            tolerance=args.tolerance,
            section=args.section,
            golden_dir=args.golden_dir,
            pixel=args.pixel,
        )
        reports.append(report)
        print(format_report(report, verbose=args.verbose))

        if args.fix:
            fix_cmds = format_fix_commands(report)
            if fix_cmds:
                print(fix_cmds)

        if not report.ok:
            all_ok = False

    # Cross-template consistency
    if args.cross and len(reports) > 1:
        print(f"\n{'=' * 70}")
        print("  Cross-template consistency")
        print(f"{'=' * 70}")
        warnings = check_cross_consistency(reports)
        if warnings:
            for w in warnings:
                print(f"    {w}")
            all_ok = False
        else:
            print("    All field positions consistent across templates.")

    # Summary
    ok_count = sum(1 for r in reports if r.ok)
    print(f"\n{'=' * 70}")
    print(f"  Summary: {ok_count}/{len(reports)} templates OK")
    if all_ok:
        print("  All checks passed.")
    else:
        fail_names = [r.name for r in reports if not r.ok]
        print(f"  Issues found in: {', '.join(fail_names)}")
    print(f"{'=' * 70}")

    return 0 if all_ok else 1
