r"""Verify that paired content-stream bars have matching counterparts.

In multi-column PDF templates (e.g. Borrower 1 / Borrower 2), underline bars
for each column should appear in matched pairs at the same y-coordinate.
This script finds bars in the content stream and reports any that are missing
their counterpart in the paired column.

Usage:
    uv run verify_paired_bars.py template.pdf --page 2
    uv run verify_paired_bars.py template.pdf --page 2 --y-range 100-300
    uv run verify_paired_bars.py template.pdf --page 2 --col1-x 142 --col2-x 358
    uv run verify_paired_bars.py template.pdf --page 2 --fix  # insert missing bars
"""

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import pikepdf  # ty: ignore[unresolved-import]

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Bar:
    """A horizontal bar extracted from the content stream."""

    x: float
    y: float
    scale_x: float
    length: float
    offset: int  # byte offset in the content stream
    raw: str  # the full q...Q block text

    @property
    def column(self) -> str:
        """Classify as col1 or col2 based on x position."""
        return ""  # Set externally


# ---------------------------------------------------------------------------
# Content stream extraction
# ---------------------------------------------------------------------------


def get_content_stream(pdf: pikepdf.Pdf, page_idx: int) -> str:
    """Extract the full content stream for a page."""
    page = pdf.pages[page_idx]
    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        data = b""
        for ref in contents:
            data += ref.read_bytes()
        return data.decode("latin-1", errors="replace")
    return contents.read_bytes().decode("latin-1", errors="replace")


BAR_PATTERN = re.compile(
    r"q\s+"
    r"([.\d]+)\s+0\s+0\s+([.\d]+)\s+"  # sx 0 0 sy
    r"([.\d]+)\s+([.\d]+)\s+cm\s+"  # tx ty cm
    r"0\s+0\s+m\s+"  # 0 0 m
    r"([.\d]+)\s+0\s+l\s+"  # length 0 l
    r"S\s+Q"  # S Q
)


def extract_bars(
    stream: str,
    y_min: float = 0,
    y_max: float = 1000,
) -> list[Bar]:
    """Extract all horizontal bars from the content stream within the y range."""
    bars: list[Bar] = []
    for m in BAR_PATTERN.finditer(stream):
        sx = float(m.group(1))
        tx = float(m.group(3))
        ty = float(m.group(4))
        length = float(m.group(5))
        if y_min <= ty <= y_max:
            bars.append(
                Bar(
                    x=tx,
                    y=ty,
                    scale_x=sx,
                    length=length,
                    offset=m.start(),
                    raw=m.group(0),
                )
            )
    return bars


# ---------------------------------------------------------------------------
# Pairing logic
# ---------------------------------------------------------------------------


def detect_columns(
    bars: list[Bar],
    col1_x: float | None = None,
    col2_x: float | None = None,
) -> tuple[float, float]:
    """Auto-detect column x-positions from bar clusters, or use explicit values."""
    if col1_x is not None and col2_x is not None:
        return col1_x, col2_x

    # Cluster bar x-values
    xs = sorted({round(b.x, 0) for b in bars})
    if len(xs) < 2:
        print("ERROR: Cannot detect two columns — found x-values:", xs, file=sys.stderr)
        sys.exit(1)

    # Assume the two most common x-clusters
    x_groups: dict[float, int] = {}
    for b in bars:
        key = round(b.x, 0)
        x_groups[key] = x_groups.get(key, 0) + 1

    top2 = sorted(x_groups, key=lambda k: x_groups[k], reverse=True)[:2]
    c1, c2 = sorted(top2)
    return col1_x or c1, col2_x or c2


def find_missing_pairs(
    bars: list[Bar],
    col1_x: float,
    col2_x: float,
    tolerance: float = 5.0,
    y_tolerance: float = 1.0,
) -> tuple[list[Bar], list[Bar]]:
    """Find bars in col1 without a col2 match and vice versa.

    Returns (missing_in_col2, missing_in_col1).
    """
    col1 = [b for b in bars if abs(b.x - col1_x) < tolerance]
    col2 = [b for b in bars if abs(b.x - col2_x) < tolerance]

    col1_ys = {round(b.y, 1) for b in col1}
    col2_ys = {round(b.y, 1) for b in col2}

    def has_match(y: float, ys: set[float]) -> bool:
        return any(abs(y - y2) < y_tolerance for y2 in ys)

    missing_in_col2 = [b for b in col1 if not has_match(round(b.y, 1), col2_ys)]
    missing_in_col1 = [b for b in col2 if not has_match(round(b.y, 1), col1_ys)]
    return missing_in_col2, missing_in_col1


# ---------------------------------------------------------------------------
# Fix mode
# ---------------------------------------------------------------------------


def generate_bar_block(reference_bar: Bar, target_x: float) -> str:
    """Generate a bar block at target_x using the reference bar's other attributes."""
    return (
        f"\nq\n{reference_bar.scale_x} 0 0 1 {target_x} {reference_bar.y} cm\n0 0 m\n{reference_bar.length} 0 l\nS\nQ"
    )


def insert_missing_bars(
    stream: str,
    missing_in_col2: list[Bar],
    missing_in_col1: list[Bar],
    col1_x: float,
    col2_x: float,
) -> str:
    """Insert missing bar counterparts into the content stream.

    Inserts each missing bar right after its counterpart.
    Works from end to start to preserve offsets.
    """
    insertions: list[tuple[int, str]] = []

    for bar in missing_in_col2:
        # bar is in col1, missing in col2 — insert col2 version after it
        insert_pos = bar.offset + len(bar.raw)
        new_block = generate_bar_block(bar, col2_x)
        insertions.append((insert_pos, new_block))

    for bar in missing_in_col1:
        # bar is in col2, missing in col1 — insert col1 version after it
        insert_pos = bar.offset + len(bar.raw)
        new_block = generate_bar_block(bar, col1_x)
        insertions.append((insert_pos, new_block))

    # Apply insertions from end to start
    import operator

    for pos, text in sorted(insertions, key=operator.itemgetter(0), reverse=True):
        stream = stream[:pos] + text + stream[pos:]

    return stream


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", help="PDF template to check")
    parser.add_argument("--page", type=int, required=True, help="1-based page number")
    parser.add_argument("--y-range", default="0-1000", help="Y range to check (e.g. 100-300)")
    parser.add_argument("--col1-x", type=float, default=None, help="Column 1 x-coordinate (auto-detected if omitted)")
    parser.add_argument("--col2-x", type=float, default=None, help="Column 2 x-coordinate (auto-detected if omitted)")
    parser.add_argument("--tolerance", type=float, default=5.0, help="X tolerance for column matching (default: 5)")
    parser.add_argument("--fix", action="store_true", help="Insert missing bars and save")
    parser.add_argument("--output", "-o", default=None, help="Output path for fixed PDF (default: overwrite input)")
    args = parser.parse_args()

    y_min, y_max = (float(v) for v in args.y_range.split("-"))
    pdf_path = Path(args.pdf)

    pdf = pikepdf.open(pdf_path)
    stream = get_content_stream(pdf, args.page - 1)
    bars = extract_bars(stream, y_min, y_max)

    if not bars:
        print(f"No bars found on page {args.page} in y-range {y_min}-{y_max}")
        sys.exit(0)

    col1_x, col2_x = detect_columns(bars, args.col1_x, args.col2_x)
    print(f"Columns: col1 x≈{col1_x:.0f}, col2 x≈{col2_x:.0f}")
    print(f"Bars found: {len(bars)} in y-range [{y_min}, {y_max}]")

    missing_in_col2, missing_in_col1 = find_missing_pairs(bars, col1_x, col2_x, args.tolerance)

    if not missing_in_col2 and not missing_in_col1:
        print("All bars are paired. No issues found.")
        sys.exit(0)

    exit_code = 1
    for bar in missing_in_col2:
        print(f"  MISSING col2 bar at y={bar.y:.1f} (col1 has bar at x={bar.x:.1f})")
    for bar in missing_in_col1:
        print(f"  MISSING col1 bar at y={bar.y:.1f} (col2 has bar at x={bar.x:.1f})")

    total_missing = len(missing_in_col2) + len(missing_in_col1)
    print(f"\n{total_missing} missing bar(s) found.")

    if args.fix:
        # Re-read for fix (need exact x from existing bars)
        col2_ref_x = col2_x
        col1_ref_x = col1_x
        # Use exact x from existing bars in each column
        col2_bars = [b for b in bars if abs(b.x - col2_x) < args.tolerance]
        col1_bars = [b for b in bars if abs(b.x - col1_x) < args.tolerance]
        if col2_bars:
            col2_ref_x = col2_bars[0].x
        if col1_bars:
            col1_ref_x = col1_bars[0].x

        fixed = insert_missing_bars(stream, missing_in_col2, missing_in_col1, col1_ref_x, col2_ref_x)

        # Write back
        page = pdf.pages[args.page - 1]
        contents = page.get("/Contents")
        if isinstance(contents, pikepdf.Array):
            page[pikepdf.Name.Contents] = pdf.make_stream(fixed.encode("latin-1"))
        else:
            contents.write(fixed.encode("latin-1"))

        out_path = Path(args.output) if args.output else Path("/tmp/_paired_fix.pdf")  # noqa: S108
        pdf.save(out_path, recompress_flate=True)
        print(f"Fixed PDF saved to {out_path}")
        if not args.output:
            print(f"Copy to template: cp {out_path} {pdf_path}")
        exit_code = 0

    pdf.close()
    sys.exit(exit_code)
