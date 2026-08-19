"""Rendering ``assess`` metrics for a human.

The one rule this module exists to keep: no number is printed without the
scope it was measured over. A figure the reader has to guess the meaning of is
worse than no figure, because they will guess.
"""

import vendored_paths
from codebase_metrics import COVERAGE_GOOD_THRESHOLD, COVERAGE_WARN_THRESHOLD
from rich.markup import escape
from suppressions import print_counts
from ui import console, truncate
from vendored_paths import FIRST_PARTY, VENDORED, VendoredPaths


def print_report(metrics: dict) -> None:
    vendored = vendored_paths.from_report(metrics["vendored"])
    console.print("[bold]Codebase Metrics[/bold]")
    console.print()
    _print_vendored(vendored)
    _print_lint(metrics["lint"], vendored=vendored)
    _print_todos(metrics["todos"], vendored=vendored)
    _print_complexity(metrics["complexity"], vendored=vendored)
    _print_coverage(metrics["coverage"], vendored=vendored)
    _print_deps(metrics["dependencies"])
    print_counts(metrics["suppressions"], vendored)


def _print_vendored(vendored: VendoredPaths) -> None:
    if not vendored.declared:
        console.print("  Vendored: [dim]nothing declared — every count below covers the whole repo[/dim]")
        console.print()
        return
    console.print(f"  Vendored (not this repo's code): [cyan]{escape(', '.join(vendored.prefixes))}[/cyan]")
    console.print(f"    detected from: [dim]{escape(vendored.source)}[/dim]")
    if vendored.unlinted:
        # Otherwise "vendored 0" reads as a clean bill of health on a tree ruff
        # never opened.
        console.print(
            f"    [dim]ruff is configured to skip {escape(', '.join(vendored.unlinted))}, so the lint and "
            f"complexity counts below are first-party only — not a verdict on the vendored code[/dim]"
        )
    console.print()


def _print_lint(lint: dict, *, vendored: VendoredPaths) -> None:
    if "error" in lint:
        console.print(f"  Lint: [red]{escape(str(lint['error']))}[/red]")
        return
    color = "green" if lint["total"] == 0 else "yellow"
    scopes = lint["scopes"]
    note = _ruff_note(scopes[FIRST_PARTY]["total"], scopes[VENDORED]["total"], vendored=vendored)
    console.print(
        f"  Lint violations: [{color}]{lint['total']}[/{color}]{note} [dim](under this repo's own ruff config)[/dim]"
    )
    for scope, bucket in scopes.items():
        if bucket["by_code"]:
            codes = ", ".join(f"{code}={n}" for code, n in bucket["by_code"].items())
            console.print(f"    {vendored.label(scope)}: {codes}")


def _print_todos(todos: dict, *, vendored: VendoredPaths) -> None:
    scopes = todos.get("scopes", {})
    note = vendored.split_note(scopes.get(FIRST_PARTY, 0), scopes.get(VENDORED, 0))
    console.print(f"  TODOs/FIXMEs: {todos['total']}{note}")
    if todos.get("by_type"):
        console.print(f"    {', '.join(f'{k}={v}' for k, v in todos['by_type'].items())}")


def _print_complexity(cx: dict, *, vendored: VendoredPaths) -> None:
    if "error" in cx:
        console.print(f"  Complexity: [red]{escape(str(cx['error']))}[/red]")
        return
    scopes = cx.get("scopes", {})
    note = _ruff_note(scopes.get(FIRST_PARTY, 0), scopes.get(VENDORED, 0), vendored=vendored)
    console.print(f"  Complex functions (C901): {cx['violations']}{note}")


def _ruff_note(first_party: int, vendored_count: int, *, vendored: VendoredPaths) -> str:
    """The scope tail for a ruff-derived count.

    A tree ruff was told to skip contributes no findings, and printing that as
    ``vendored 0`` claims a measurement that was never taken.
    """
    if vendored.fully_unlinted:
        return f" — first-party {first_party}, vendored [dim]not linted[/dim]"
    return vendored.split_note(first_party, vendored_count)


def _print_coverage(cov: dict, *, vendored: VendoredPaths) -> None:
    if not cov.get("available"):
        reason = truncate(str(cov.get("error", "no .coverage file")), 160)
        console.print(f"  Test coverage: [dim]{escape(reason)}[/dim]")
        return
    pct = cov["percent"]
    color = "green" if pct >= COVERAGE_GOOD_THRESHOLD else "yellow" if pct >= COVERAGE_WARN_THRESHOLD else "red"
    console.print(f"  Test coverage: [{color}]{pct:.1f}%[/{color}]")
    for scope, bucket in cov.get("scopes", {}).items():
        if scope == VENDORED and not vendored.declared:
            continue
        console.print(f"    {_coverage_line(scope, bucket, vendored=vendored)}")


def _coverage_line(scope: str, bucket: dict, *, vendored: VendoredPaths) -> str:
    label = vendored.label(scope)
    if bucket["percent"] is None:
        return f"{label}: [dim]not measured[/dim]"
    return f"{label}: {bucket['percent']:.1f}% over {bucket['files']} files ({bucket['measured']} measurable)"


def _print_deps(deps: dict) -> None:
    if deps.get("available"):
        n = deps["outdated_count"]
        color = "green" if n == 0 else "yellow"
        console.print(f"  Outdated deps: [{color}]{n}[/{color}]")
    elif deps.get("error"):
        console.print(f"  Outdated deps: [dim]{deps['error']}[/dim]")
    else:
        console.print("  Outdated deps: [dim]not a uv project[/dim]")
