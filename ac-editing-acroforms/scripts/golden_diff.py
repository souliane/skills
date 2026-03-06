#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["typer>=0.9"]
# ///
"""Compare golden PDFs between a git base ref and the current branch.

Shows side-by-side montage (only differing pages) and overlay diff for each
changed golden PDF, one document at a time. Press Enter to advance.

Requires: diff-pdf, montage (ImageMagick), gs (GhostScript).

Usage:
    uv run golden_diff.py                          # changed golden PDFs vs upstream
    uv run golden_diff.py --filter "fr_*broker*"   # filter by pattern
    uv run golden_diff.py --base origin/main       # compare against a specific ref
    uv run golden_diff.py --dpi 300                # higher resolution
"""

import contextlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=False)

# Track child viewer processes for cleanup
_viewer_procs: list[subprocess.Popen] = []

# ---------------------------------------------------------------------------
# Core helpers (testable, no side effects)
# ---------------------------------------------------------------------------


def find_changed_pdfs(
    base_ref: str,
    pattern: str = "src/test/resources/**/*.pdf",
    filter_glob: str = "",
    cwd: Path | None = None,
) -> list[str]:
    """Return list of PDF paths that differ between *base_ref* and HEAD."""
    cmd = ["git", "diff", "--name-only", base_ref, "--", pattern]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        return []
    paths = [p for p in result.stdout.strip().splitlines() if p]
    if filter_glob:
        import fnmatch

        paths = [p for p in paths if fnmatch.fnmatch(Path(p).name, filter_glob)]
    return paths


def resolve_base_ref(base_ref: str | None, cwd: Path | None = None) -> str:
    """Resolve the git base ref for comparisons.

    Priority:
    1. Explicit CLI value
    2. Current branch upstream (for feature branches)
    3. Previous commit as a generic fallback
    """
    if base_ref:
        return base_ref

    upstream = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if upstream.returncode == 0:
        resolved = upstream.stdout.strip()
        if resolved:
            return resolved

    return "HEAD^"


def extract_master_pdf(base_ref: str, pdf_path: str, dest: Path, cwd: Path | None = None) -> bool:
    """Extract *pdf_path* from *base_ref* into *dest*. Returns True on success."""
    cmd = ["git", "show", f"{base_ref}:{pdf_path}"]
    result = subprocess.run(cmd, capture_output=True, cwd=cwd)
    if result.returncode != 0:
        return False
    dest.write_bytes(result.stdout)
    return True


def render_page(pdf_path: str | Path, page: int, out_png: Path, dpi: int = 72) -> bool:
    """Render a single page of *pdf_path* to PNG via GhostScript."""
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


def find_differing_pages(master_pdf: Path, branch_pdf: Path, tmp: Path) -> list[int]:
    """Return 1-based page numbers that differ visually (low-res quick compare)."""
    master_count = pdf_page_count(master_pdf)
    branch_count = pdf_page_count(branch_pdf)
    max_pages = max(master_count, branch_count)

    diff_pages: list[int] = []
    for p in range(1, max_pages + 1):
        mp = tmp / f"_cmp_m_p{p}.png"
        bp = tmp / f"_cmp_b_p{p}.png"

        m_ok = render_page(master_pdf, p, mp, dpi=72) if p <= master_count else False
        b_ok = render_page(branch_pdf, p, bp, dpi=72) if p <= branch_count else False

        if m_ok and b_ok:
            if mp.read_bytes() != bp.read_bytes():
                diff_pages.append(p)
        elif m_ok or b_ok:
            diff_pages.append(p)

        mp.unlink(missing_ok=True)
        bp.unlink(missing_ok=True)
    return diff_pages


def create_side_by_side(master_png: Path, branch_png: Path, out: Path, page_num: int) -> bool:
    """Create a side-by-side montage of two PNGs with labels."""
    montage = shutil.which("montage")
    if not montage:
        return False
    cmd = [
        montage,
        "-label",
        f"master (p{page_num})",
        str(master_png),
        "-label",
        f"branch (p{page_num})",
        str(branch_png),
        "-tile",
        "2x1",
        "-geometry",
        "+10+0",
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True)
    return r.returncode == 0 and out.exists()


def create_overlay_diff(master_pdf: Path, branch_pdf: Path, out: Path) -> bool:
    """Create an overlay diff PDF using diff-pdf."""
    diff_pdf = shutil.which("diff-pdf")
    if not diff_pdf:
        return False
    cmd = [
        diff_pdf,
        f"--output-diff={out}",
        "--mark-differences",
        "--grayscale",
        str(master_pdf),
        str(branch_pdf),
    ]
    subprocess.run(cmd, capture_output=True)
    # diff-pdf returns 1 when files differ (which is expected)
    return out.exists()


def pdf_page_count(pdf_path: Path) -> int:
    """Get number of pages in a PDF using GhostScript."""
    gs = _find_gs()
    if not gs:
        return 1
    cmd = [
        gs,
        "-q",
        "-dNODISPLAY",
        "-dNOSAFER",  # Required for runpdfbegin; only used on local trusted PDFs
        "-c",
        f"({pdf_path}) (r) file runpdfbegin pdfpagecount = quit",
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode == 0:
        try:
            return int(r.stdout.strip())
        except ValueError:
            pass
    return 1


def check_dependencies() -> list[str]:
    """Return list of missing required external tools."""
    missing = []
    if not _find_gs():
        missing.append("ghostscript")
    if not shutil.which("montage"):
        missing.append("imagemagick")
    if not shutil.which("diff-pdf"):
        missing.append("diff-pdf")
    return missing


def _find_gs() -> str | None:
    """Find GhostScript binary."""
    for candidate in ["/opt/homebrew/bin/gs", "gs"]:
        if shutil.which(candidate):
            return candidate
    return None


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _open_image(path: Path) -> None:
    """Open an image file and track the viewer process for later cleanup."""
    if sys.platform == "darwin":
        # qlmanage -p opens Quick Look — stays alive as a process we can kill
        proc = subprocess.Popen(
            ["qlmanage", "-p", str(path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        _viewer_procs.append(proc)
    elif sys.platform == "linux":
        proc = subprocess.Popen(["xdg-open", str(path)])
        _viewer_procs.append(proc)


def _open_overlay_diff(master_pdf: Path, branch_pdf: Path) -> None:
    """Open diff-pdf interactive overlay viewer and track the process."""
    diff_pdf = shutil.which("diff-pdf")
    if not diff_pdf:
        return
    proc = subprocess.Popen(
        [diff_pdf, "--view", str(master_pdf), str(branch_pdf)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    _viewer_procs.append(proc)


def _close_viewers() -> None:
    """Terminate all tracked viewer processes."""
    for proc in _viewer_procs:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except (ProcessLookupError, subprocess.TimeoutExpired):
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
    _viewer_procs.clear()


@app.command()
def main(
    filter_glob: str = typer.Option("", "--filter", "-f", help="Glob pattern to filter PDF names"),
    base_ref: str | None = typer.Option(
        None,
        "--base",
        "-b",
        help="Git ref to compare against (defaults to the current branch upstream)",
    ),
    dpi: int = typer.Option(200, "--dpi", help="Render resolution for side-by-side"),
    pdf_glob: str = typer.Option("src/test/resources/**/*.pdf", "--glob", "-g", help="Git diff glob for PDF paths"),
) -> None:
    """Compare golden PDFs between a git base ref and the current branch."""
    resolved_base = resolve_base_ref(base_ref)
    missing = check_dependencies()
    if missing:
        typer.echo(f"Missing dependencies: {', '.join(missing)}")
        typer.echo("Install with: brew install " + " ".join(missing))
        raise typer.Exit(1)

    changed = find_changed_pdfs(resolved_base, pattern=pdf_glob, filter_glob=filter_glob)
    if not changed:
        typer.echo(f"No golden PDFs differ from {resolved_base}")
        if filter_glob:
            typer.echo(f"(filter: {filter_glob})")
        raise typer.Exit(0)

    typer.echo(f"Found {len(changed)} changed golden PDF(s).")
    typer.echo("")

    outdir = Path(tempfile.mkdtemp(prefix="pdf-golden-diff-"))
    total = len(changed)

    for idx, pdf_path in enumerate(changed, 1):
        name = Path(pdf_path).stem

        typer.echo(f"[{idx}/{total}] {name}")

        # Extract master version
        master_pdf = outdir / f"{name}_master.pdf"
        if not extract_master_pdf(resolved_base, pdf_path, master_pdf):
            typer.echo("  New file (no master version) — skipping")
            continue

        branch_pdf = Path(pdf_path)

        # Find differing pages
        diff_pages = find_differing_pages(master_pdf, branch_pdf, outdir)
        if not diff_pages:
            typer.echo("  No visual differences (binary diff only) — skipping")
            continue

        typer.echo(f"  Differing pages: {', '.join(str(p) for p in diff_pages)}")

        # Render side-by-side for each differing page
        sbs_files: list[Path] = []
        for page_num in diff_pages:
            mp_hq = outdir / f"{name}_master_p{page_num}.png"
            bp_hq = outdir / f"{name}_branch_p{page_num}.png"
            sbs = outdir / f"{name}_p{page_num}_sidebyside.png"

            render_page(master_pdf, page_num, mp_hq, dpi=dpi)
            render_page(branch_pdf, page_num, bp_hq, dpi=dpi)

            if mp_hq.exists() and bp_hq.exists() and create_side_by_side(mp_hq, bp_hq, sbs, page_num):
                sbs_files.append(sbs)

        # Open side-by-side images
        for sbs in sbs_files:
            typer.echo(f"  Side-by-side: {sbs}")
            _open_image(sbs)

        # Open overlay diff (interactive viewer)
        typer.echo("  Overlay diff: diff-pdf --view")
        _open_overlay_diff(master_pdf, branch_pdf)

        # Wait for user, then close viewers before next document
        typer.echo("")
        if idx < total:
            input("  Press Enter for next document... ")
        else:
            input("  Press Enter to close viewers... ")
        _close_viewers()
        typer.echo("")

    typer.echo(f"All done. Output in {outdir}")


if __name__ == "__main__":
    app()
