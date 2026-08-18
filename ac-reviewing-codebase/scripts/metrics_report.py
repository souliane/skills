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
from vendored_paths import VendoredPaths


def print_report(metrics: dict) -> None:
    vendored = vendored_paths.from_report(metrics["vendored"])
    console.print("[bold]Codebase Metrics[/bold]")
    console.print()
    _print_vendored(vendored)
    _print_lint(metrics["lint"])
    _print_todos(metrics["todos"], vendored=vendored)
    _print_complexity(metrics["complexity"])
    _print_coverage(metrics["coverage"], vendored=vendored)
    _print_deps(metrics["dependencies"])
    print_counts(metrics["suppressions"], vendored)


def _print_vendored(vendored: VendoredPaths) -> None:
    if vendored.declared:
        console.print(f"  Vendored (not this repo's code): [cyan]{escape(', '.join(vendored.prefixes))}[/cyan]")
        console.print(f"    detected from: [dim]{escape(vendored.source)}[/dim]")
    else:
        console.print("  Vendored: [dim]nothing declared — every count below covers the whole repo[/dim]")
    console.print()


def _print_lint(lint: dict) -> None:
    if "error" in lint:
        console.print(f"  Lint: [red]{lint['error']}[/red]")
        return
    color = "green" if lint["total"] == 0 else "yellow"
    scope_note = "[dim](under the repo's own ruff config)[/dim]"
    console.print(f"  Lint violations: [{color}]{lint['total']}[/{color}] {scope_note}")
    for code, count in list(lint.get("by_category", {}).items())[:10]:
        console.print(f"    {code}: {count}")


def _print_todos(todos: dict, *, vendored: VendoredPaths) -> None:
    console.print(f"  TODOs/FIXMEs: {todos['total']}{_scope_note(todos.get('scopes', {}), vendored=vendored)}")
    if todos.get("by_type"):
        console.print(f"    {', '.join(f'{k}={v}' for k, v in todos['by_type'].items())}")


def _print_complexity(cx: dict) -> None:
    if "error" in cx:
        console.print(f"  Complexity: [red]{cx['error']}[/red]")
    else:
        console.print(f"  Complex functions (C901): {cx['violations']}")


def _print_coverage(cov: dict, *, vendored: VendoredPaths) -> None:
    if not cov.get("available"):
        reason = truncate(str(cov.get("error", "no .coverage file")), 160)
        console.print(f"  Test coverage: [dim]{escape(reason)}[/dim]")
        return
    pct = cov["percent"]
    color = "green" if pct >= COVERAGE_GOOD_THRESHOLD else "yellow" if pct >= COVERAGE_WARN_THRESHOLD else "red"
    console.print(f"  Test coverage: [{color}]{pct:.1f}%[/{color}]")
    for scope, bucket in cov.get("scopes", {}).items():
        if scope == vendored_paths.VENDORED and not vendored.declared:
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


def _scope_note(scopes: dict, *, vendored: VendoredPaths) -> str:
    if not vendored.declared or not scopes:
        return ""
    return f" — first-party {scopes.get('first_party', 0)}, vendored {scopes.get('vendored', 0)}"
