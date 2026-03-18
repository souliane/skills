"""Compare golden PDFs between a git base ref and the current branch.

Shows side-by-side montage (only differing pages) and overlay diff for each
changed golden PDF, one document at a time. Press Enter to advance.

Requires: diff-pdf, montage (ImageMagick), gs (GhostScript).

Usage:
    uv run golden_diff.py                          # changed golden PDFs vs upstream
    uv run golden_diff.py --filter "fr_*broker*"   # filter by pattern
    uv run golden_diff.py --base origin/main       # compare against a specific ref
    uv run golden_diff.py --dpi 300                # higher resolution
    uv run golden_diff.py --gitlab --mr 1030 --include-templates  # templates + golden
    uv run golden_diff.py --gitlab --mr 1030 --update-note 12345  # update existing comment
    uv run golden_diff.py --gitlab --mr 1030 --force              # render all, even no GS diff
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

    font = _find_montage_font()
    font_args = ["-font", font] if font else []
    cmd = [
        montage,
        *font_args,
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
    if r.returncode == 0 and out.exists():
        return True

    # Retry without labels if font rendering failed
    out.unlink(missing_ok=True)
    cmd_no_labels = [
        montage,
        str(master_png),
        str(branch_png),
        "-tile",
        "2x1",
        "-geometry",
        "+10+0",
        str(out),
    ]
    r = subprocess.run(cmd_no_labels, capture_output=True)
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


def _find_montage_font() -> str | None:
    """Find a usable font for ImageMagick montage labels."""
    candidates = [
        "/System/Library/Fonts/Helvetica.ttc",  # macOS
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",  # Debian/Ubuntu
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",  # Fedora/RHEL
    ]
    for path in candidates:
        if Path(path).exists():
            return path
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


def _render_all_diffs(
    changed: list[str],
    resolved_base: str,
    dpi: int,
    outdir: Path,
    *,
    force: bool = False,
) -> list[tuple[str, list[Path]]]:
    """Render side-by-side PNGs for all changed golden PDFs.

    Returns a list of (document_name, [sbs_png_paths]).
    When *force* is True, render all pages even if GhostScript sees no diff
    (useful for AcroForm-only changes invisible to GhostScript).
    """
    results: list[tuple[str, list[Path]]] = []
    total = len(changed)

    for idx, pdf_path in enumerate(changed, 1):
        name = Path(pdf_path).stem

        typer.echo(f"[{idx}/{total}] {name}")

        master_pdf = outdir / f"{name}_master.pdf"
        if not extract_master_pdf(resolved_base, pdf_path, master_pdf):
            typer.echo("  New file (no master version) — skipping")
            continue

        branch_pdf = Path(pdf_path)

        diff_pages = find_differing_pages(master_pdf, branch_pdf, outdir)
        if not diff_pages:
            if force:
                # Render all pages even without visual diff
                page_count = pdf_page_count(branch_pdf)
                diff_pages = list(range(1, page_count + 1))
                typer.echo(f"  No GS diff — force-rendering all {page_count} page(s)")
            else:
                typer.echo("  No visual differences (binary diff only) — skipping")
                continue
        else:
            typer.echo(f"  Differing pages: {', '.join(str(p) for p in diff_pages)}")

        sbs_files: list[Path] = []
        for page_num in diff_pages:
            mp_hq = outdir / f"{name}_master_p{page_num}.png"
            bp_hq = outdir / f"{name}_branch_p{page_num}.png"
            sbs = outdir / f"{name}_p{page_num}_sidebyside.png"

            render_page(master_pdf, page_num, mp_hq, dpi=dpi)
            render_page(branch_pdf, page_num, bp_hq, dpi=dpi)

            if mp_hq.exists() and bp_hq.exists() and create_side_by_side(mp_hq, bp_hq, sbs, page_num):
                sbs_files.append(sbs)

        if sbs_files:
            results.append((name, sbs_files))

    return results


# ---------------------------------------------------------------------------
# GitLab posting
# ---------------------------------------------------------------------------


def _get_gitlab_token() -> str | None:
    """Get GitLab token from glab CLI config."""
    r = subprocess.run(
        ["glab", "config", "get", "token", "--host", "gitlab.com"],
        capture_output=True,
        text=True,
    )
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def _detect_gitlab_project() -> str | None:
    """Detect the GitLab project path from the git remote."""
    r = subprocess.run(["git", "remote", "get-url", "origin"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    url = r.stdout.strip()
    # git@gitlab.com:org/repo.git or https://gitlab.com/org/repo.git
    import re

    m = re.search(r"gitlab\.com[:/](.+?)(?:\.git)?$", url)
    return m.group(1).replace("/", "%2F") if m else None


def _detect_mr_iid() -> str | None:
    """Detect MR IID for the current branch."""
    r = subprocess.run(["glab", "mr", "view", "--json", "iid"], capture_output=True, text=True)
    if r.returncode != 0:
        return None
    import json

    try:
        return str(json.loads(r.stdout)["iid"])
    except (json.JSONDecodeError, KeyError):
        return None


def _upload_to_gitlab(png_path: Path, token: str, project_id: str) -> str | None:
    """Upload a PNG to GitLab project uploads. Returns the markdown image ref."""
    import json

    url = f"https://gitlab.com/api/v4/projects/{project_id}/uploads"

    # Use curl for multipart upload (urllib doesn't support it easily)
    r = subprocess.run(
        [
            "curl",
            "-s",
            "--request",
            "POST",
            "--header",
            f"PRIVATE-TOKEN: {token}",
            "--form",
            f"file=@{png_path}",
            url,
        ],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    try:
        data = json.loads(r.stdout)
        return data.get("markdown")
    except json.JSONDecodeError:
        return None


def _post_mr_comment(body: str, token: str, project_id: str, mr_iid: str, *, note_id: str | None = None) -> int | None:
    """Post or update a comment on a GitLab MR. Returns the note ID or None."""
    import json
    import urllib.request

    payload = json.dumps({"body": body}).encode()
    if note_id:
        url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes/{note_id}"
        method = "PUT"
    else:
        url = f"https://gitlab.com/api/v4/projects/{project_id}/merge_requests/{mr_iid}/notes"
        method = "POST"
    req = urllib.request.Request(  # noqa: S310 — URL is always https://gitlab.com
        url,
        data=payload,
        headers={"PRIVATE-TOKEN": token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        resp = urllib.request.urlopen(req)  # noqa: S310
        return json.loads(resp.read()).get("id")
    except Exception:  # noqa: BLE001 — catch-all for network/parse errors
        return None


def _render_template_diffs(
    base_ref: str,
    dpi: int,
    outdir: Path,
    *,
    filter_glob: str = "",
) -> list[tuple[str, list[Path]]]:
    """Render side-by-side PNGs for changed template PDFs.

    Returns a list of (template_name, [sbs_png_paths]).
    """
    changed = find_changed_pdfs(base_ref, pattern="templates/**/*.pdf", filter_glob=filter_glob)
    if not changed:
        typer.echo("No template PDFs differ from base.")
        return []

    typer.echo(f"Found {len(changed)} changed template(s).")
    results: list[tuple[str, list[Path]]] = []
    for idx, pdf_path in enumerate(changed, 1):
        name = Path(pdf_path).stem
        typer.echo(f"[tpl {idx}/{len(changed)}] {name}")

        master_pdf = outdir / f"{name}_tpl_master.pdf"
        if not extract_master_pdf(base_ref, pdf_path, master_pdf):
            typer.echo("  New template — skipping")
            continue

        branch_pdf = Path(pdf_path)
        diff_pages = find_differing_pages(master_pdf, branch_pdf, outdir)
        if not diff_pages:
            diff_pages = list(range(1, pdf_page_count(branch_pdf) + 1))
        typer.echo(f"  Differing pages: {', '.join(str(p) for p in diff_pages)}")
        sbs_files: list[Path] = []
        for page_num in diff_pages:
            mp = outdir / f"{name}_tpl_master_p{page_num}.png"
            bp = outdir / f"{name}_tpl_branch_p{page_num}.png"
            sbs = outdir / f"{name}_tpl_p{page_num}_sidebyside.png"

            render_page(master_pdf, page_num, mp, dpi=dpi)
            render_page(branch_pdf, page_num, bp, dpi=dpi)

            if mp.exists() and bp.exists() and create_side_by_side(mp, bp, sbs, page_num):
                sbs_files.append(sbs)

        if sbs_files:
            results.append((f"{name} (template)", sbs_files))

    return results


def _post_gitlab_comment(
    results: list[tuple[str, list[Path]]],
    token: str,
    project_id: str,
    mr_iid: str,
    *,
    update_note: str | None = None,
) -> None:
    """Upload all side-by-side images and post/update an MR comment."""
    action = f"Updating note {update_note}" if update_note else "Posting"
    typer.echo(f"{action} on MR !{mr_iid}...")

    # Upload all images
    rows: list[tuple[str, str]] = []  # (doc_name, markdown_img)
    for doc_name, sbs_files in results:
        for sbs in sbs_files:
            md = _upload_to_gitlab(sbs, token, project_id)
            if md:
                rows.append((doc_name, md))
                typer.echo(f"  Uploaded: {sbs.name}")
            else:
                typer.echo(f"  FAILED: {sbs.name}")

    if not rows:
        typer.echo("No images uploaded — skipping comment.")
        return

    # Build comment body — first image of each doc shown, rest in <details>
    body_parts = ["## Visual Diff — All Modified PDFs (Page 2)\n"]
    body_parts.append("Side-by-side: master (left) → this MR (right).\n")
    current_doc = ""
    doc_images: list[str] = []

    def flush_doc() -> None:
        if not doc_images:
            return
        body_parts.append(f"### {current_doc}\n")
        body_parts.append(f"{doc_images[0]}\n")
        if len(doc_images) > 1:
            body_parts.append(f"<details><summary>{len(doc_images) - 1} more page(s)</summary>\n")
            body_parts.extend(f"{img}\n" for img in doc_images[1:])
            body_parts.append("</details>\n")

    for doc_name, md_img in rows:
        if doc_name != current_doc:
            flush_doc()
            current_doc = doc_name
            doc_images = []
        doc_images.append(md_img)
    flush_doc()

    body = "\n".join(body_parts)
    note_id = _post_mr_comment(body, token, project_id, mr_iid, note_id=update_note)
    if note_id:
        typer.echo(f"Posted note {note_id} on MR !{mr_iid}")
    else:
        typer.echo("ERROR: Failed to post comment")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


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
    gitlab: bool = typer.Option(False, "--gitlab", help="Upload images and post as GitLab MR comment"),
    mr: str | None = typer.Option(None, "--mr", help="GitLab MR IID (auto-detected if omitted)"),
    include_templates: bool = typer.Option(False, "--include-templates", help="Also render changed template PDFs"),
    update_note: str | None = typer.Option(
        None, "--update-note", help="Update an existing GitLab note instead of creating new"
    ),
    force: bool = typer.Option(False, "--force", help="Render all changed PDFs even without GhostScript visual diff"),
) -> None:
    """Compare golden PDFs between a git base ref and the current branch."""
    resolved_base = resolve_base_ref(base_ref)
    missing = check_dependencies()
    if missing:
        typer.echo(f"Missing dependencies: {', '.join(missing)}")
        typer.echo("Install with: brew install " + " ".join(missing))
        raise typer.Exit(1)

    outdir = Path(tempfile.mkdtemp(prefix="pdf-golden-diff-"))
    all_results: list[tuple[str, list[Path]]] = []

    # Template diffs (if requested)
    if include_templates:
        tpl_results = _render_template_diffs(resolved_base, dpi, outdir, filter_glob=filter_glob)
        all_results.extend(tpl_results)
        typer.echo("")

    # Golden PDF diffs
    changed = find_changed_pdfs(resolved_base, pattern=pdf_glob, filter_glob=filter_glob)
    if changed:
        typer.echo(f"Found {len(changed)} changed golden PDF(s).")
        typer.echo("")
        golden_results = _render_all_diffs(changed, resolved_base, dpi, outdir, force=force)
        all_results.extend(golden_results)
    elif not include_templates:
        typer.echo(f"No golden PDFs differ from {resolved_base}")
        if filter_glob:
            typer.echo(f"(filter: {filter_glob})")
        raise typer.Exit(0)

    if not all_results:
        typer.echo("No visual diffs to show.")
        raise typer.Exit(0)

    if gitlab:
        # GitLab mode: upload and post/update comment
        token = _get_gitlab_token()
        if not token:
            typer.echo("ERROR: No GitLab token — run `glab auth login` first")
            raise typer.Exit(1)
        project_id = _detect_gitlab_project()
        if not project_id:
            typer.echo("ERROR: Cannot detect GitLab project from git remote")
            raise typer.Exit(1)
        mr_iid = mr or _detect_mr_iid()
        if not mr_iid:
            typer.echo("ERROR: No MR found for current branch — use --mr to specify")
            raise typer.Exit(1)
        _post_gitlab_comment(all_results, token, project_id, mr_iid, update_note=update_note)
    else:
        # Interactive mode: open viewers
        for doc_name, sbs_files in all_results:
            for sbs in sbs_files:
                typer.echo(f"  Side-by-side: {sbs}")
                _open_image(sbs)

            # Find master PDF for overlay diff
            master_pdf = outdir / f"{doc_name}_master.pdf"
            branch_pdf_candidates = [p for p in (changed or []) if Path(p).stem == doc_name]
            if master_pdf.exists() and branch_pdf_candidates:
                typer.echo("  Overlay diff: diff-pdf --view")
                _open_overlay_diff(master_pdf, Path(branch_pdf_candidates[0]))

            typer.echo("")
            if doc_name != all_results[-1][0]:
                input("  Press Enter for next document... ")
            else:
                input("  Press Enter to close viewers... ")
            _close_viewers()
            typer.echo("")

    typer.echo(f"All done. Output in {outdir}")
