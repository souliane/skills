"""Which directories in a repo hold somebody else's code.

A metric that mixes vendored code with the repo's own is a number about a
codebase nobody here can change. A fork whose vendored upstream carries
thousands of deliberate ``# noqa`` reads as a fork drowning in suppressions,
which is very nearly the inverse of the truth. Every split ``assess`` reports
is decided here.

The vendored set is never a hardcoded project path. It is read from what the
repo already says about itself, first source that yields anything:

1. ``--vendored`` on the command line, when the caller states it outright.
2. ``.gitattributes`` entries carrying git's ``linguist-vendored`` attribute —
    the one marker that means *vendored* and nothing else.
3. ``pyproject.toml`` ``[tool.ruff] exclude`` / ``extend-exclude`` — the repo
    naming the trees it does not lint, which is the trees it does not own.
4. Conventional vendor directory names, when nothing above is declared.

A candidate only survives if the repo actually tracks files under it, so
ignored build and virtualenv directories drop out without being enumerated.
"""

import re
import tomllib
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

from scanning import is_git_repo, tracked_under

VENDORED_ATTRIBUTE = "linguist-vendored"

CONVENTIONAL_VENDOR_DIRS = (
    "vendor",
    "vendored",
    "third_party",
    "third-party",
    "thirdparty",  # codespell:ignore
    "external",
)

NOTHING_DECLARED = "nothing declared"

FIRST_PARTY = "first_party"
VENDORED = "vendored"
SCOPES = (FIRST_PARTY, VENDORED)

_TRAILING_GLOB_RE = re.compile(r"/\*+$")


@dataclass(frozen=True)
class VendoredPaths:
    """The vendored path prefixes of one repo, and where they were read from."""

    prefixes: tuple[str, ...] = ()
    source: str = NOTHING_DECLARED

    @property
    def declared(self) -> bool:
        return bool(self.prefixes)

    def covers(self, path: str) -> bool:
        return any(path == prefix or path.startswith(f"{prefix}/") for prefix in self.prefixes)

    def scope_of(self, path: str) -> str:
        return VENDORED if self.covers(path) else FIRST_PARTY

    def label(self, scope: str) -> str:
        """How ``scope`` should read in a report.

        With no vendored tree declared there is only one scope, and calling it
        "first-party" implies a second one the reader will go looking for.
        """
        if not self.declared:
            return "whole repo"
        if scope == VENDORED:
            return f"vendored ({', '.join(self.prefixes)})"
        return scope.replace("_", "-")

    def as_dict(self) -> dict[str, object]:
        return {"paths": list(self.prefixes), "source": self.source}


def from_report(info: dict) -> VendoredPaths:
    """Rebuild the value ``assess --json`` serialised, so printing and JSON agree."""
    return VendoredPaths(tuple(info.get("paths", [])), str(info.get("source", NOTHING_DECLARED)))


def resolve(root: Path, override: Sequence[str] = ()) -> VendoredPaths:
    if override:
        return VendoredPaths(_normalize(override), "--vendored")
    for source, candidates in (
        (f".gitattributes {VENDORED_ATTRIBUTE}", _from_gitattributes(root)),
        ("pyproject [tool.ruff] exclude", _from_ruff_exclude(root)),
        ("conventional vendor directory", _from_conventional_dirs(root)),
    ):
        prefixes = _really_present(root, candidates)
        if prefixes:
            return VendoredPaths(prefixes, source)
    return VendoredPaths()


def _from_gitattributes(root: Path) -> list[str]:
    attributes_file = root / ".gitattributes"
    if not attributes_file.exists():
        return []
    patterns: list[str] = []
    for raw_line in attributes_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        pattern, *attributes = line.split()
        # `-linguist-vendored` unsets the attribute and must not match.
        if VENDORED_ATTRIBUTE in attributes or f"{VENDORED_ATTRIBUTE}=true" in attributes:
            patterns.append(pattern)
    return patterns


def _from_ruff_exclude(root: Path) -> list[str]:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return []
    try:
        config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return []
    ruff = config.get("tool", {}).get("ruff", {})
    return [*ruff.get("exclude", []), *ruff.get("extend-exclude", [])]


def _from_conventional_dirs(root: Path) -> list[str]:
    return [name for name in CONVENTIONAL_VENDOR_DIRS if (root / name).is_dir()]


def _really_present(root: Path, entries: Iterable[str]) -> tuple[str, ...]:
    """Keep the entries naming a directory whose files the repo really carries.

    In a git repo "really carries" means *tracked*. An excluded ``.venv`` or
    ``build`` is not somebody else's source, and every scan here is
    tracked-only anyway — labelling those vendored would attach a name to a
    directory that contributes no numbers at all.
    """
    present = [entry for entry in _normalize(entries) if (root / entry).is_dir()]
    if not is_git_repo(root):
        return tuple(present)
    return tuple(entry for entry in present if tracked_under(root, entry))


def _normalize(entries: Iterable[str]) -> tuple[str, ...]:
    """Reduce config spellings (``./vendor/``, ``vendor/**``) to one path prefix."""
    cleaned: list[str] = []
    for raw in entries:
        entry = _TRAILING_GLOB_RE.sub("", raw.strip().removeprefix("./").strip("/"))
        if entry and "*" not in entry:
            cleaned.append(entry)
    return tuple(dict.fromkeys(cleaned))
