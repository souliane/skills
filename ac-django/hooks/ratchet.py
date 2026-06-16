"""Shared ratchet machinery for the ac-django prek checkers.

A checker reports a ``Violation`` per offending file. Tolerance comes from two
composable sources supplied by the consuming repo's ``.pre-commit-config.yaml``:

* ``--allow=<path-or-glob>`` — repeatable inline entries for small sets.
* ``--baseline=<file>`` — a committed path-list for large grandfather sets.

With neither configured the ratchet is strict: every violation fails. The
ratchet only tightens — ``--update-baseline`` may shrink a baseline but a run
whose baseline file lists paths that no longer violate is itself reported so a
grown/stale baseline cannot hide behind the data file.
"""

import fnmatch
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Violation:
    """One offending file and a human-readable reason."""

    path: str
    detail: str


def normalize(path: str) -> str:
    """Normalize a repo-relative path for stable comparison across inputs."""
    return Path(path).as_posix().lstrip("./")


def read_baseline(baseline_path: str | None) -> list[str]:
    """Read a newline-delimited baseline file; missing file means empty."""
    if baseline_path is None:
        return []
    path = Path(baseline_path)
    if not path.exists():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    return [normalize(line.strip()) for line in lines if line.strip() and not line.startswith("#")]


def write_baseline(baseline_path: str, paths: Iterable[str]) -> None:
    """Write a sorted, de-duplicated, newline-delimited baseline file."""
    unique = sorted({normalize(p) for p in paths})
    body = "".join(f"{p}\n" for p in unique)
    Path(baseline_path).write_text(body, encoding="utf-8")


def is_tolerated(path: str, allow: Sequence[str], baseline: Sequence[str]) -> bool:
    """True when ``path`` is grandfathered by an allow-glob or the baseline."""
    norm = normalize(path)
    if norm in baseline:
        return True
    return any(fnmatch.fnmatch(norm, normalize(pattern)) for pattern in allow)


@dataclass(frozen=True)
class RatchetResult:
    """Outcome of evaluating violations against tolerance."""

    failures: list[Violation]
    stale_baseline_entries: list[str]

    @property
    def ok(self) -> bool:
        return not self.failures and not self.stale_baseline_entries


def file_key(entry: str) -> str:
    """The file-path component of a violation/baseline key.

    A pyproject entry is keyed ``pyproject.toml::CODE@location``; everything else
    is keyed by the plain path. Staleness is judged per scanned file.
    """
    return normalize(entry.split("::", 1)[0])


def evaluate(
    violations: Sequence[Violation],
    allow: Sequence[str],
    baseline_path: str | None,
    scanned_keys: Sequence[str] | None = None,
) -> RatchetResult:
    """Split violations into tolerated vs. failing and flag a stale baseline.

    A baseline entry that no longer corresponds to a current violation — *within
    the set of files actually scanned this run* — is reported as
    ``stale_baseline_entries`` so the committed baseline must shrink as the
    codebase improves; the ratchet can only tighten. When ``scanned_keys`` is
    ``None`` every baseline entry is in scope (a full-tree assertion run);
    otherwise an entry whose file was not scanned is left untouched so a partial
    prek invocation cannot falsely flag a still-violating file as fixed.
    """
    baseline = read_baseline(baseline_path)
    failures = [v for v in violations if not is_tolerated(v.path, allow, baseline)]
    violating_paths = {normalize(v.path) for v in violations}
    scanned = None if scanned_keys is None else {normalize(k) for k in scanned_keys}
    stale = [
        entry for entry in baseline if entry not in violating_paths and (scanned is None or file_key(entry) in scanned)
    ]
    return RatchetResult(failures=failures, stale_baseline_entries=sorted(set(stale)))


def current_violation_paths(violations: Sequence[Violation]) -> list[str]:
    """Sorted unique normalized paths, for regenerating a baseline."""
    return sorted({normalize(v.path) for v in violations})
