r"""Sync underline bars between sibling PDF templates.

When two templates share the same page layout (e.g., LRF and broker both have
identical page 2), bars added to one template should also exist in the other.
This script finds bars present in a reference template but missing in a target
template, and inserts them.

Usage:
    uv run sync_sibling_bars.py reference.pdf target.pdf --page 2
    uv run sync_sibling_bars.py reference.pdf target.pdf --page 2 --dry-run
    uv run sync_sibling_bars.py reference.pdf target.pdf --page 2 --matching 60-210,1.0
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pikepdf  # ty: ignore[unresolved-import]
import typer

BAR_PATTERN = re.compile(
    r"q\s+"
    r"([\d.]+)\s+0\s+0\s+([\d.]+)\s+"  # sx 0 0 sy
    r"([\d.]+)\s+([\d.]+)\s+cm\s+"  # tx ty cm
    r"0\s+0\s+m\s+"  # 0 0 m
    r"([\d.]+)\s+0\s+l\s+"  # length 0 l
    r"S\s+Q"  # S Q
)


@dataclass
class Bar:
    x: float
    y: float
    sx: float
    length: float
    offset: int
    raw: str

    @property
    def col(self) -> str:
        return "col1" if self.x < 300 else "col2"


def _get_stream(pdf: pikepdf.Pdf, page_idx: int) -> str:
    page = pdf.pages[page_idx]
    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        data = b""
        for ref in contents:
            data += ref.read_bytes()
        return data.decode("latin-1", errors="replace")
    return contents.read_bytes().decode("latin-1", errors="replace")


def _extract_bars(stream: str, y_min: float, y_max: float) -> list[Bar]:
    bars: list[Bar] = []
    for m in BAR_PATTERN.finditer(stream):
        sx, tx, ty, length = (
            float(m.group(1)),
            float(m.group(3)),
            float(m.group(4)),
            float(m.group(5)),
        )
        if y_min <= ty <= y_max:
            bars.append(Bar(x=tx, y=ty, sx=sx, length=length, offset=m.start(), raw=m.group(0)))
    return bars


def _bar_key(bar: Bar, tolerance: float = 1.0) -> tuple[str, float]:
    """Return a (col, rounded_y) key for matching bars across templates."""
    return (bar.col, round(bar.y / tolerance) * tolerance)


def _find_missing(ref_bars: list[Bar], tgt_bars: list[Bar], tolerance: float = 1.0) -> list[Bar]:
    """Find bars in ref that have no match in tgt (by column + y-position)."""
    tgt_keys = {_bar_key(b, tolerance) for b in tgt_bars}
    return [b for b in ref_bars if _bar_key(b, tolerance) not in tgt_keys]


def _find_shifted(ref_bars: list[Bar], tgt_bars: list[Bar], tolerance: float = 1.0) -> list[tuple[Bar, Bar]]:
    """Find bars in tgt whose y differs from ref (same col, closest match)."""
    pairs: list[tuple[Bar, Bar]] = []
    for rb in ref_bars:
        same_col = [tb for tb in tgt_bars if tb.col == rb.col]
        if not same_col:
            continue
        closest = min(same_col, key=lambda tb: abs(tb.y - rb.y))
        dy = abs(closest.y - rb.y)
        if tolerance < dy < 50:  # shifted but not a completely different bar
            pairs.append((rb, closest))
    return pairs


def _report_diffs(missing: list[Bar], shifted: list[tuple[Bar, Bar]]) -> None:
    if missing:
        typer.echo(f"\n{len(missing)} bar(s) in reference but missing in target:")
        for b in sorted(missing, key=lambda b: (-b.y, b.x)):
            typer.echo(f"  {b.col} x={b.x:.2f} y={b.y:.2f} sx={b.sx:.3f} len={b.length:.2f}")
    if shifted:
        typer.echo(f"\n{len(shifted)} bar(s) with shifted y-position:")
        for ref_b, tgt_b in shifted:
            dy = tgt_b.y - ref_b.y
            typer.echo(f"  {ref_b.col} ref y={ref_b.y:.2f} → tgt y={tgt_b.y:.2f} (dy={dy:+.2f})")


def _apply_shifts(stream: str, shifted: list[tuple[Bar, Bar]]) -> str:
    for ref_b, tgt_b in sorted(shifted, key=lambda p: p[1].offset, reverse=True):
        old_text = tgt_b.raw
        new_text = old_text.replace(f" {_fmt(tgt_b.y)} cm", f" {_fmt(ref_b.y)} cm")
        if new_text != old_text:
            stream = stream[: tgt_b.offset] + new_text + stream[tgt_b.offset + len(old_text) :]
            typer.echo(f"  Fixed shift: {tgt_b.col} y={tgt_b.y:.2f} → {ref_b.y:.2f}")
    return stream


def _insert_missing(stream: str, missing: list[Bar], y_min: float, y_max: float) -> str:
    updated_bars = _extract_bars(stream, y_min, y_max)
    for mb in sorted(missing, key=lambda b: -b.y):
        candidates = [b for b in updated_bars if b.y >= mb.y]
        if candidates:
            anchor = min(candidates, key=lambda b: b.y)
        elif updated_bars:
            anchor = max(updated_bars, key=lambda b: b.offset)
        else:
            typer.echo(f"  WARNING: no anchor bar found for y={mb.y:.2f}, skipping")
            continue
        insert_pos = anchor.offset + len(anchor.raw)
        new_block = f"\nq\n{mb.sx} 0 0 1 {mb.x} {mb.y} cm\n0 0 m\n{mb.length} 0 l\nS\nQ"
        stream = stream[:insert_pos] + new_block + stream[insert_pos:]
        typer.echo(f"  Inserted: {mb.col} x={mb.x:.2f} y={mb.y:.2f}")
        updated_bars = _extract_bars(stream, y_min, y_max)
    return stream


def _write_stream(pdf: pikepdf.Pdf, page_idx: int, stream: str, out_path: Path) -> None:
    page = pdf.pages[page_idx]
    contents = page.get("/Contents")
    if isinstance(contents, pikepdf.Array):
        page[pikepdf.Name.Contents] = pdf.make_stream(stream.encode("latin-1"))
    else:
        contents.write(stream.encode("latin-1"))
    pdf.save(out_path)


@dataclass
class MatchSpec:
    y_min: float = 0.0
    y_max: float = 1000.0
    tolerance: float = 1.0

    @classmethod
    def parse(cls, raw: str) -> "MatchSpec":
        range_part, _, tol_part = raw.partition(",")
        y_min, y_max = (float(v) for v in range_part.split("-"))
        tolerance = float(tol_part) if tol_part else 1.0
        return cls(y_min=y_min, y_max=y_max, tolerance=tolerance)


def main(
    reference: str = typer.Argument(help="Reference template PDF (source of truth for bars)"),
    target: str = typer.Argument(help="Target template PDF to sync bars into (modified in place)"),
    page: int = typer.Option(..., "--page", "-p", help="1-based page number"),
    *,
    matching: str = typer.Option("0-1000", "--matching", help="'ymin-ymax[,tolerance]' (e.g. 60-210,1.0)"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Show what would change without modifying"),
) -> None:
    """Sync underline bars from reference template to target template."""
    spec = MatchSpec.parse(matching)

    ref_pdf = pikepdf.open(reference)
    tgt_pdf = pikepdf.open(target)

    ref_bars = _extract_bars(_get_stream(ref_pdf, page - 1), spec.y_min, spec.y_max)
    tgt_stream = _get_stream(tgt_pdf, page - 1)
    tgt_bars = _extract_bars(tgt_stream, spec.y_min, spec.y_max)

    typer.echo(f"Reference: {len(ref_bars)} bars, Target: {len(tgt_bars)} bars (y {spec.y_min}-{spec.y_max})")

    missing = _find_missing(ref_bars, tgt_bars, spec.tolerance)
    shifted = _find_shifted(ref_bars, tgt_bars, spec.tolerance)

    if not missing and not shifted:
        typer.echo("Target bars match reference. Nothing to do.")
        ref_pdf.close()
        tgt_pdf.close()
        return

    _report_diffs(missing, shifted)

    if dry_run:
        typer.echo("\nDry run — no changes made.")
        ref_pdf.close()
        tgt_pdf.close()
        return

    modified = _apply_shifts(tgt_stream, shifted)
    modified = _insert_missing(modified, missing, spec.y_min, spec.y_max)

    _write_stream(tgt_pdf, page - 1, modified, Path(target))
    typer.echo(f"\nSaved to {target}")

    ref_pdf.close()
    tgt_pdf.close()


def _fmt(v: float) -> str:
    """Format a float to match content-stream number formatting."""
    if v == int(v):
        return str(int(v))
    # Match original precision
    s = f"{v:.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s
