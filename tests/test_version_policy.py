"""The version policy is prose; this is the grep that makes it fail loud.

`ac-django/SKILL.md` and `ac-python/SKILL.md` each carry a "Version Policy"
section saying the skill documents ONE line — the current one — with in-line
additions carrying a `(6.1+)`-shaped marker and everything older confined to a
single trailing section in `SKILL.md`. Nothing enforced that, so a
`### Django 5.2 note` heading or an "On Python 3.14+, ..." conditional could
creep back into the main path on the next refresh and nobody would notice.

Only the banned-phrasing grep is encoded. The policy's sibling grep — the one
for previous-line *content* (`django 5.2`, `celery`, `django-csp`, ...) — cannot
be a zero assertion: it has 14 legitimate hits today, including three main-path
mentions of Celery/RQ that are current-line prose. Pinning those would need an
allowlist that goes stale and becomes the place a real regression hides, so it
stays a review read (the policy's "Research order" step) rather than a gate.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
POLICY_SKILLS = ("ac-django", "ac-python")

# Verbatim from the version-policy plan's structural greps. The marker suffix is
# the whole convention, so a competing form is a defect wherever it appears.
BANNED_PHRASING = re.compile(
    r"django [0-9]+(\.[0-9]+)?\+? (adds|note|lacking)"
    r"|on python 3\.[0-9]+\+"
    r"|^#+ +(Django|Python) [0-9]"
    r"|as of (django|python) [0-9]"
    r"|new in (django|python)",
    re.IGNORECASE | re.MULTILINE,
)

BANNED_SAMPLES = (
    "Django 6.1+ adds `QuerySet.fetch_mode()`.",
    "### Django 5.2 note",
    "## Python 3.13 note",
    "On Python 3.14+, prefer t-strings.",
    "This is the default as of Django 6.1.",
    "`JSONNull` is new in Django 6.1.",
    "Django 5.2 lacking native Tasks means Celery.",
)

ALLOWED_SAMPLES = (
    "`QuerySet.fetch_mode()` (6.1+) picks how related objects load.",
    "## Previous line: Django 5.2 LTS",
    "## Previous line: Python 3.13",
    "**Targets:** Django **6.1** on Python **3.14**",
    "### 15.2 Admin performance",
)


def _policy_docs() -> list[Path]:
    """Every markdown file the version policy governs."""
    return sorted(path for skill in POLICY_SKILLS for path in (REPO_ROOT / skill).rglob("*.md"))


def test_the_scan_reaches_both_skills() -> None:
    """A gate that scans nothing must not pass silently."""
    docs = _policy_docs()
    relative = {path.relative_to(REPO_ROOT).as_posix() for path in docs}
    assert {"ac-django/SKILL.md", "ac-python/SKILL.md"} <= relative
    assert len(docs) > 10, f"only {len(docs)} docs scanned — the glob is broken"


def test_the_pattern_detects_what_it_is_looking_for() -> None:
    """The RED control: without it a typo'd pattern is a green that means nothing."""
    for sample in BANNED_SAMPLES:
        assert BANNED_PHRASING.search(sample), f"pattern missed: {sample!r}"
    for sample in ALLOWED_SAMPLES:
        assert not BANNED_PHRASING.search(sample), f"pattern over-fired: {sample!r}"


def test_no_banned_version_phrasing() -> None:
    """One marker form only — no "new in X.Y", no `### Django X.Y note` heading."""
    violations = [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{text[: match.start()].count(chr(10)) + 1}: {match.group(0)!r}"
        for path in _policy_docs()
        for text in [path.read_text(encoding="utf-8")]
        for match in BANNED_PHRASING.finditer(text)
    ]
    assert not violations, "banned version phrasing (see each SKILL.md § Version Policy):\n" + "\n".join(violations)
