#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["typer>=0.15", "rich"]
# requires-python = ">=3.12"
# ///
"""Deterministic checks and metrics for codebase review.

Subcommands:
    review-checklist — Render the review manifest into a working checklist (run FIRST).
    review-verify    — Completion gate; non-zero until every mandatory item is evidenced.
    check   — Validate SKILL.md frontmatter in a tracked skills repo.
    status  — Show delivery status across all managed repos.
    config  — Inventory config files and health checks.
    assess  — Run deterministic codebase metrics (ruff, coverage, complexity, TODOs, deps).

Repo selection is one flag everywhere: ``--root`` is the path to a repository.
``status`` works across every managed repo, so it narrows by directory name with
``--name`` instead.

The command bodies live here; everything they call lives in the sibling modules
next to this file, which is why that directory is put on the import path first.
"""

import json
import sys
from pathlib import Path
from typing import Annotated

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent))

import codebase_metrics
import repo_status
import review_config
import review_gate
import skill_frontmatter
from rich.table import Table
from ui import console, truncate

app = typer.Typer(help="Deterministic checks and metrics for codebase review.")


@app.command()
def check(
    root: Annotated[Path, typer.Option(help="Repository root to check")] = Path.cwd(),
) -> None:
    """Validate SKILL.md frontmatter in a tracked skills repo."""
    root_dir = root.resolve()
    findings = skill_frontmatter.check_frontmatter(root_dir, skill_frontmatter.collect_skill_files(root_dir))
    if findings:
        print(f"Errors ({len(findings)}):")
        for finding in findings:
            print(finding)
        print("FAIL")
        raise typer.Exit(1)
    print("PASS")


@app.command()
def status(
    name: Annotated[
        list[str] | None,
        # ``--repo``/``-r`` is the pre-unification spelling, kept so existing
        # callers and docs keep working.
        typer.Option("--name", "-n", "--repo", "-r", help="Filter to specific repo(s) by directory name"),
    ] = None,
    *,
    verbose: Annotated[bool, typer.Option("--verbose", "-v", help="Show individual commit lines")] = False,
) -> None:
    """Show delivery status across all managed repos."""
    config = review_config.load_config()
    paths = repo_status.discover_repos(config)
    if name:
        paths = [p for p in paths if p.name in name]
        if not paths:
            console.print(f"[red]No matching repos for:[/red] {', '.join(name)}")
            raise typer.Exit(1)
    table = Table(title="Managed Repos Status", show_lines=False)
    table.add_column("Repo", style="bold")
    table.add_column("Branch")
    table.add_column("Unpushed", justify="right")
    table.add_column("Dirty", justify="right")
    table.add_column("Stashes", justify="right")
    table.add_column("Branches", justify="right")
    table.add_column("Status")
    has_work = False
    detail_repos: list[tuple[str, dict]] = []
    for path in paths:
        info = repo_status.build_repo_status(path)
        has_work = has_work or not repo_status.is_clean(info)
        unpushed_str = str(info["n_unpushed"]) if not info["no_upstream"] else "?"
        stash_str = str(info["stashes"]) if info["stashes"] else "-"
        branch_str = str(len(info["other_branches"])) if info["other_branches"] else "-"
        table.add_row(
            path.name,
            info["branch"],
            unpushed_str,
            str(info["dirty"]),
            stash_str,
            branch_str,
            repo_status.format_status(info),
        )
        if verbose and (info["unpushed"] or info["dirty_files"] or info["other_branches"] or info["stashes"]):
            detail_repos.append((path.name, info))
    console.print(table)
    if verbose and detail_repos:
        console.print()
        for repo_name, info in detail_repos:
            repo_status.print_repo_detail(repo_name, info)
    if not has_work:
        console.print("\n[green]All repos are clean.[/green]")
    else:
        raise typer.Exit(1)


@app.command("config")
def show_config() -> None:
    """Inventory config files and run health checks for managed repos."""
    table = Table(title="Configuration Files", show_lines=True)
    table.add_column("File", style="bold")
    table.add_column("Exists")
    table.add_column("Purpose")
    table.add_column("Keys / Values")
    for raw_path, purpose in review_config.CONFIG_FILES.items():
        path = Path(raw_path).expanduser()
        exists = path.exists()
        exists_str = "[green]yes[/green]" if exists else "[red]no[/red]"
        if exists:
            parsed = review_config.parse_shell_config(path)
            keys_str = (
                "\n".join(f"[cyan]{k}[/cyan]={truncate(str(v), 60)}" for k, v in parsed.items())
                if parsed
                else "[dim](empty)[/dim]"
            )
        else:
            keys_str = "-"
        table.add_row(raw_path, exists_str, purpose, keys_str)
    console.print(table)
    console.print()
    console.print("[bold]Health Checks:[/bold]")
    review_config.print_config_health()


@app.command("review-checklist")
def review_checklist(
    out: Annotated[Path, typer.Option(help="Where to write the working checklist")] = Path(".review-checklist.md"),
) -> None:
    """Render the review manifest into a working checklist for this review."""
    if not review_gate.MANIFEST_PATH.exists():
        console.print(f"[red]Manifest missing: {review_gate.MANIFEST_PATH}[/red]")
        raise typer.Exit(1)
    out.write_text(review_gate.MANIFEST_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    items = review_gate.parse_manifest(out.read_text(encoding="utf-8"))
    mandatory = sum(1 for i in items if i.mandatory)
    console.print(f"Wrote [bold]{out}[/bold] — {len(items)} items, [yellow]{mandatory}[/yellow] non-negotiable.")
    console.print("Tick each item and record evidence, then run [bold]review-verify[/bold].")


@app.command("review-verify")
def review_verify(
    checklist: Annotated[Path, typer.Argument(help="The filled-in checklist")] = Path(".review-checklist.md"),
) -> None:
    """Fail unless every non-negotiable item is ticked and every tick has evidence."""
    if not checklist.exists():
        console.print(f"[red]No checklist at {checklist}.[/red] Run `review-checklist` first.")
        console.print("A review with no checklist is not a review that can be called complete.")
        raise typer.Exit(1)
    items = review_gate.parse_manifest(checklist.read_text(encoding="utf-8"))
    if not items:
        console.print(f"[red]{checklist} parsed to zero items[/red] — wrong file, or the format drifted.")
        raise typer.Exit(1)
    failures = review_gate.verify_items(items)
    done = sum(1 for i in items if i.checked)
    if failures:
        console.print(f"[red]Review INCOMPLETE[/red] — {done}/{len(items)} ticked, {len(failures)} problem(s):")
        for failure in failures:
            console.print(f"  [red]x[/red] {failure}")
        raise typer.Exit(1)
    console.print(f"[green]Review complete[/green] — {done}/{len(items)} items ticked, all evidenced.")


@app.command()
def assess(
    root: Annotated[Path, typer.Option(help="Repository root to assess")] = Path.cwd(),
    *,
    output_json: Annotated[bool, typer.Option("--json", help="Output as JSON")] = False,
) -> None:
    """Run deterministic codebase metrics."""
    metrics = codebase_metrics.collect(root.resolve())
    if output_json:
        print(json.dumps(metrics, indent=2))
        return
    codebase_metrics.print_report(metrics)


if __name__ == "__main__":  # pragma: no cover
    app()
