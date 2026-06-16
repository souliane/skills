#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["typer>=0.12"]
# requires-python = ">=3.12"
# ///
"""prek entry points for the ac-django testing-convention checkers.

Each subcommand takes the filenames prek passes plus optional tolerance:

* ``--allow=<path-or-glob>`` (repeatable) — inline grandfathered entries.
* ``--baseline=<file>`` — a committed grandfather path-list (CONSUMING repo).
* ``--update-baseline`` — rewrite the ``--baseline`` file to the current set.

With no ``--allow`` and no ``--baseline`` the checks are strict: any violation
fails (fail-closed). The ratchet only tightens — a baseline that still lists a
path/entry which no longer violates is reported so it must be shrunk.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hooks import checkers, ratchet
from hooks.ratchet import Violation

app = typer.Typer(
    help="ac-django testing-convention checkers (ratcheting).",
    add_completion=False,
)

AllowOpt = Annotated[
    list[str] | None,
    typer.Option("--allow", help="Grandfathered path or glob (repeatable)."),
]
BaselineOpt = Annotated[
    str | None,
    typer.Option("--baseline", help="Path to a committed newline-delimited baseline file."),
]
UpdateOpt = Annotated[
    bool,
    typer.Option("--update-baseline", help="Rewrite the --baseline file to the current violations."),
]


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


@dataclass(frozen=True)
class _RunContext:
    """One invocation's tolerance config and the files it scanned."""

    label: str
    scanned_keys: list[str]
    allow: list[str]
    baseline: str | None
    update: bool


def _finish(violations: list[Violation], ctx: _RunContext) -> None:
    if ctx.update:
        if ctx.baseline is None:
            typer.echo("--update-baseline requires --baseline=<file>", err=True)
            raise typer.Exit(code=2)
        scanned = {ratchet.normalize(k) for k in ctx.scanned_keys}
        kept = [e for e in ratchet.read_baseline(ctx.baseline) if ratchet.file_key(e) not in scanned]
        entries = sorted(set(kept) | set(ratchet.current_violation_paths(violations)))
        ratchet.write_baseline(ctx.baseline, entries)
        typer.echo(f"{ctx.label}: wrote {len(entries)} entr(ies) to {ctx.baseline}")
        raise typer.Exit(code=0)

    result = ratchet.evaluate(violations, ctx.allow, ctx.baseline, scanned_keys=ctx.scanned_keys)
    if result.ok:
        raise typer.Exit(code=0)
    for failure in result.failures:
        typer.echo(f"{ctx.label}: {failure.path}: {failure.detail}", err=True)
    for stale in result.stale_baseline_entries:
        typer.echo(
            f"{ctx.label}: baseline entry no longer violates (shrink the baseline): {stale}",
            err=True,
        )
    raise typer.Exit(code=1)


def _context(
    label: str,
    filenames: list[str],
    allow: list[str] | None,
    baseline: str | None,
    update: bool,
) -> _RunContext:
    return _RunContext(
        label=label,
        scanned_keys=filenames,
        allow=allow or [],
        baseline=baseline,
        update=update,
    )


def _line_violations(
    filenames: list[str],
    detector,  # noqa: ANN001
    message: str,
) -> list[Violation]:
    out: list[Violation] = []
    for name in filenames:
        out.extend(Violation(path=name, detail=f"{message} (line {lineno})") for lineno in detector(_read(name)))
    return out


@app.command("no-django-db")
def no_django_db(
    filenames: list[str],
    allow: AllowOpt = None,
    baseline: BaselineOpt = None,
    update_baseline: UpdateOpt = False,
) -> None:
    """Fail on ``@pytest.mark.django_db`` (use django.test.TestCase)."""
    violations = _line_violations(
        filenames,
        checkers.check_django_db,
        "uses @pytest.mark.django_db; ac-django mandates django.test.TestCase",
    )
    _finish(violations, _context("ac-django-no-pytest-django-db", filenames, allow, baseline, update_baseline))


@app.command("testcase-no-parametrize")
def testcase_no_parametrize(
    filenames: list[str],
    allow: AllowOpt = None,
    baseline: BaselineOpt = None,
    update_baseline: UpdateOpt = False,
) -> None:
    """Fail on ``@pytest.mark.parametrize`` inside a TestCase subclass."""
    violations = _line_violations(
        filenames,
        checkers.check_testcase_parametrize,
        "@pytest.mark.parametrize inside a TestCase subclass is silently ignored; use unittest_parametrize",
    )
    _finish(
        violations,
        _context("ac-django-testcase-no-pytest-parametrize", filenames, allow, baseline, update_baseline),
    )


@app.command("no-complexity-suppressions")
def no_complexity_suppressions(
    filenames: list[str],
    allow: AllowOpt = None,
    baseline: BaselineOpt = None,
    update_baseline: UpdateOpt = False,
) -> None:
    """Fail on ``# noqa: C901``/``PLR09xx`` in files and on the same codes in a pyproject ignore list."""
    violations: list[Violation] = []
    for name in filenames:
        source = _read(name)
        if Path(name).name == "pyproject.toml":
            violations.extend(
                Violation(
                    path=f"{name}::{entry.code}@{entry.location}",
                    detail=f"complexity suppression {entry.code} in {entry.location}",
                )
                for entry in checkers.check_pyproject_complexity(source)
            )
            continue
        violations.extend(
            Violation(
                path=name,
                detail=f"# noqa complexity suppression (C901/PLR09xx) (line {lineno})",
            )
            for lineno in checkers.check_complexity_noqa(source)
        )
    _finish(
        violations,
        _context("ac-django-no-complexity-suppressions", filenames, allow, baseline, update_baseline),
    )


if __name__ == "__main__":
    app()
