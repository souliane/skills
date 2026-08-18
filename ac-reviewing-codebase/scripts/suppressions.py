"""Lint suppressions, split by who wrote them, by which rule, and by how far they reach.

One headline number for suppressions is close to useless, and worse than
useless when it appears to contradict the repo's own standard. Four things
have to be visible or the reader draws the wrong conclusion:

* **Which rule.** One deliberate convention repeated thousands of times (a
    deferred-import pattern that breaks cycles, say) is not broad debt.
    Printing the top rule codes next to the total is what stops one pattern
    masquerading as many problems.
* **Whose code.** A vendored upstream's suppressions are not this repo's to
    answer for — see ``vendored_paths``.
* **Whether a rule was named.** ``# noqa: PLC0415`` silences one rule on
    purpose; a bare ``# noqa`` silences every rule it covers, forever, and is
    the suppression that actually signals debt. They must never share a count.
* **How far it reaches.** ``# ruff: noqa`` on its own line silences a WHOLE
    FILE. Folding that into the per-line total understates it by the size of
    the file.

Counting reads **comment tokens**, not grep lines, and a token only counts as
a directive where it can actually silence something:

* a line-level marker (``# noqa``, ``# type: ignore``, ``# pragma: no cover``)
    counts only when it TRAILS code — standing on its own line it suppresses
    nothing, and ruff's own ``RUF100`` flags such a marker as unused;
* a file-level marker (``# ruff: noqa``, ``# flake8: noqa``) counts only when
    it stands alone, which is the only place those are honoured.

Both halves matter. Every repo that reasons about suppressions writes the
markers in prose — in docstrings, in a hook's own message strings, in a test's
expected input, and in comments explaining the rule. Tokens alone still left
one fork reporting 2 bare ``# noqa`` where the true answer is 0, both of them
comments ABOUT bare ``# noqa`` — the very number a reader would act on.

Boundary worth knowing: mypy's file-level form is a bare ``# type: ignore`` on
the first line of a file, and is deliberately NOT counted here — recognising it
by shape alone would re-admit the standalone false positives this module exists
to exclude.
"""

import io
import re
import tokenize
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from scanning import scan_files
from ui import console
from vendored_paths import SCOPES, VendoredPaths

TOP_CODES = 5

FILE_NOQA = "file_noqa"

# Silences one line, and only where it trails that line's code.
LINE_MATCHERS = {
    "noqa": re.compile(r"#\s*noqa", re.IGNORECASE),
    "type_ignore": re.compile(r"#\s*type:\s*ignore", re.IGNORECASE),
    "pragma_no_cover": re.compile(r"#\s*pragma:\s*no\s+cover", re.IGNORECASE),
}

# Silences the whole file, and only where it stands on a line of its own.
FILE_MATCHERS = {
    FILE_NOQA: re.compile(r"#\s*(?:ruff|flake8)\s*:\s*noqa", re.IGNORECASE),
}

_CODES = r"[A-Z]+[0-9]+(?:\s*,\s*[A-Z]+[0-9]+)*"

# `pragma: no cover` takes no rule codes, so it can never be "uncoded".
CODE_MATCHERS = {
    "noqa": re.compile(rf"#\s*noqa\s*:\s*(?P<codes>{_CODES})", re.IGNORECASE),
    "type_ignore": re.compile(r"#\s*type:\s*ignore\[(?P<codes>[^\]]+)\]"),
    FILE_NOQA: re.compile(rf"#\s*(?:ruff|flake8)\s*:\s*noqa\s*:\s*(?P<codes>{_CODES})", re.IGNORECASE),
}

# Deliberately looser than the matchers above: POSIX ERE only has to over-select
# the candidate FILES, and the precise dialect stays in Python where it is ours.
# `noqa` is unanchored so the file-level directive selects its file too.
CANDIDATE_REGEX = "noqa|# *type: *ignore|# *pragma: *no +cover"


@dataclass(frozen=True)
class Comment:
    text: str
    # Trails code on its own line, rather than standing alone — which of the
    # two matcher sets applies, and the difference between a live directive
    # and a comment that merely names one.
    inline: bool


@dataclass
class ScopeTally:
    by_kind: Counter[str] = field(default_factory=Counter)
    by_code: Counter[str] = field(default_factory=Counter)
    uncoded: Counter[str] = field(default_factory=Counter)

    @property
    def total(self) -> int:
        return sum(self.by_kind.values())

    def add(self, kind: str, codes: list[str]) -> None:
        self.by_kind[kind] += 1
        self.by_code.update(codes)
        if kind in CODE_MATCHERS and not codes:
            self.uncoded[kind] += 1

    def as_dict(self) -> dict[str, object]:
        return {
            "total": self.total,
            "by_kind": dict(self.by_kind.most_common()),
            "uncoded": sum(self.uncoded.values()),
            "uncoded_by_kind": dict(self.uncoded.most_common()),
            "file_level": self.by_kind[FILE_NOQA],
            "top_codes": dict(self.by_code.most_common(TOP_CODES)),
        }


def count(root: Path, vendored: VendoredPaths) -> dict[str, object]:
    tallies = {scope: ScopeTally() for scope in SCOPES}
    unparsed: list[str] = []
    for path in scan_files(root, CANDIDATE_REGEX, includes=("*.py",)):
        comments = comments_in(root / path)
        if comments is None:
            unparsed.append(path)
            continue
        tally = tallies[vendored.scope_of(path)]
        for comment in comments:
            for kind in directives_in(comment):
                tally.add(kind, codes_in(kind, comment.text))
    return {
        "total": sum(tally.total for tally in tallies.values()),
        "uncoded": sum(sum(tally.uncoded.values()) for tally in tallies.values()),
        "file_level": sum(tally.by_kind[FILE_NOQA] for tally in tallies.values()),
        "unparsed_files": len(unparsed),
        "scopes": {scope: tally.as_dict() for scope, tally in tallies.items()},
    }


def comments_in(path: Path) -> list[Comment] | None:
    """Every comment token in ``path``; ``None`` when the file will not tokenize.

    A file that cannot be read is never silently treated as suppression-free —
    the caller counts it and the report says so.
    """
    try:
        source = path.read_bytes()
    except OSError:
        return None
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(source).readline))
    except (tokenize.TokenError, SyntaxError, UnicodeDecodeError, ValueError):
        return None
    return [
        Comment(token.string, inline=bool(token.line[: token.start[1]].strip()))
        for token in tokens
        if token.type == tokenize.COMMENT
    ]


def directives_in(comment: Comment) -> list[str]:
    """Which suppressions ``comment`` actually applies.

    A comment can carry more than one (``# noqa: E501  # type: ignore``), and
    each is a separate decision, so each is counted. Its position decides which
    set can apply at all: see this module's docstring on reach.
    """
    matchers = LINE_MATCHERS if comment.inline else FILE_MATCHERS
    return [kind for kind, matcher in matchers.items() if matcher.search(comment.text)]


def codes_in(kind: str, comment: str) -> list[str]:
    matcher = CODE_MATCHERS.get(kind)
    if matcher is None:
        return []
    return [
        code.strip() for match in matcher.finditer(comment) for code in match.group("codes").split(",") if code.strip()
    ]


def print_counts(supps: dict, vendored: VendoredPaths) -> None:
    total = supps["total"]
    scopes = supps["scopes"]
    color = "green" if total == 0 else "yellow"
    console.print(f"  Lint suppressions: [{color}]{total}[/{color}]{_split_note(scopes, vendored=vendored.declared)}")
    uncoded = supps["uncoded"]
    console.print(
        f"    uncoded (no rule code, silences everything): "
        f"[{'green' if uncoded == 0 else 'red'}]{uncoded}[/{'green' if uncoded == 0 else 'red'}]"
    )
    if supps.get("unparsed_files"):
        console.print(f"    [yellow]{supps['unparsed_files']} file(s) would not tokenize and are NOT counted[/yellow]")
    for scope, tally in scopes.items():
        if tally["total"] or vendored.declared:
            _print_scope(scope, tally, vendored=vendored)


def _split_note(scopes: dict, *, vendored: bool) -> str:
    if not vendored:
        return ""
    return f" — first-party {scopes['first_party']['total']}, vendored {scopes['vendored']['total']}"


def _print_scope(scope: str, tally: dict, *, vendored: VendoredPaths) -> None:
    kinds = ", ".join(f"{kind}={n}" for kind, n in tally["by_kind"].items()) or "none"
    uncoded = ", ".join(f"{kind}={n}" for kind, n in tally["uncoded_by_kind"].items()) or "0"
    console.print(f"    {vendored.label(scope)}: {tally['total']} ({kinds}), uncoded {uncoded}")
    if tally["top_codes"]:
        codes = ", ".join(f"{code}={n}" for code, n in tally["top_codes"].items())
        console.print(f"      top rules: {codes}")
    if tally["file_level"]:
        console.print(
            f"      [yellow]{tally['file_level']} file-level (`# ruff: noqa`) — "
            f"each silences a whole file, not a line[/yellow]"
        )
