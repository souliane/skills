"""High-precision AST/regex detectors for the ac-django testing conventions.

Each ``check_*`` takes the file contents and returns the offending line numbers
(or detail strings). The CLI maps these to ``Violation`` records and runs them
through the shared ratchet.
"""

import ast
import re
import tomllib
from dataclasses import dataclass

TESTCASE_BASES = frozenset(
    {"TestCase", "TransactionTestCase", "SimpleTestCase", "LiveServerTestCase"},
)

COMPLEXITY_CODES_RE = re.compile(r"\b(C901|PLR09\d{2})\b")
NOQA_RE = re.compile(r"#\s*noqa:(?P<codes>[^#\n]*)")


def _attr_chain(node: ast.expr) -> list[str]:
    """Return the dotted name chain of an attribute/name expression."""
    parts: list[str] = []
    current: ast.expr | None = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return parts[::-1]


def _decorator_chain(decorator: ast.expr) -> list[str]:
    target = decorator.func if isinstance(decorator, ast.Call) else decorator
    return _attr_chain(target)


def _is_marker(decorator: ast.expr, marker: str) -> bool:
    """True for ``@pytest.mark.<marker>`` / ``@mark.<marker>`` decorators."""
    chain = _decorator_chain(decorator)
    return bool(chain) and chain[-1] == marker and "mark" in chain


def _base_names(class_def: ast.ClassDef) -> set[str]:
    names: set[str] = set()
    for base in class_def.bases:
        chain = _attr_chain(base)
        if chain:
            names.add(chain[-1])
    return names


def check_django_db(source: str) -> list[int]:
    """Lines where a test is marked with ``@pytest.mark.django_db``.

    ac-django mandates ``django.test.TestCase`` for DB-backed tests; the pytest
    DB marker means the test bypasses that base class.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits = [
        decorator.lineno
        for node in ast.walk(tree)
        for decorator in getattr(node, "decorator_list", [])
        if _is_marker(decorator, "django_db")
    ]
    return sorted(hits)


def check_testcase_parametrize(source: str) -> list[int]:
    """Lines where ``@pytest.mark.parametrize`` decorates a ``TestCase`` method.

    pytest silently ignores ``parametrize`` on unittest-style methods, so inside
    a ``TestCase`` subclass it is a latent no-op bug — ``unittest_parametrize``
    must be used instead. Module-level pytest-style functions are NOT flagged.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    hits = [
        decorator.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and (_base_names(node) & TESTCASE_BASES)
        for item in node.body
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
        for decorator in item.decorator_list
        if _is_marker(decorator, "parametrize")
    ]
    return sorted(hits)


def check_complexity_noqa(source: str) -> list[int]:
    """Lines carrying a ``# noqa: C901`` / ``# noqa: PLR09xx`` suppression.

    ac-django bans suppressing the complexity rule family; a too-complex
    function must be refactored, not silenced.
    """
    hits: list[int] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        match = NOQA_RE.search(line)
        if match and COMPLEXITY_CODES_RE.search(match.group("codes")):
            hits.append(lineno)
    return hits


@dataclass(frozen=True)
class PyprojectComplexity:
    """A complexity code found in a ruff ignore list inside a pyproject."""

    code: str
    location: str


def check_pyproject_complexity(source: str) -> list[PyprojectComplexity]:
    """Complexity codes in any ruff ``ignore`` / ``per-file-ignores`` list.

    Scans ``[tool.ruff]`` ``lint.ignore``, ``lint.extend-ignore`` and every
    ``lint.per-file-ignores`` entry for ``C901`` / ``PLR09xx``. Returns one
    record per (code, location) so a documented baseline can grandfather exactly
    the entries that already exist.
    """
    try:
        data = tomllib.loads(source)
    except tomllib.TOMLDecodeError:
        return []
    ruff = data.get("tool", {}).get("ruff", {})
    lint = ruff.get("lint", ruff)
    found = [
        PyprojectComplexity(code=str(code), location=f"lint.{key}")
        for key in ("ignore", "extend-ignore")
        for code in lint.get(key, []) or []
        if COMPLEXITY_CODES_RE.fullmatch(str(code))
    ]
    per_file = lint.get("per-file-ignores", {}) or {}
    found.extend(
        PyprojectComplexity(code=str(code), location=f"lint.per-file-ignores.{pattern}")
        for pattern, codes in per_file.items()
        for code in codes or []
        if COMPLEXITY_CODES_RE.fullmatch(str(code))
    )
    return found
