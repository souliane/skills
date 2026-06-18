"""Meta-tests for the ac-django ast-grep rules + the standalone pyproject hook.

The AST-shaped checks ship as ast-grep YAML rules run via ``astgrep_scan.py``;
the ``pyproject.toml`` ruff ignore-list surface (which ast-grep 0.42.3 cannot
parse) ships as the standalone ``pyproject_complexity.py`` hook. Both grandfather
INLINE — ast-grep via ``# ast-grep-ignore[<rule-id>]``, the pyproject hook via
``--grandfather`` args — with no baseline file and no count cap.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RULES_DIR = Path(__file__).resolve().parents[2] / "ac-django" / "rules"
ASTGREP_SCAN = RULES_DIR / "astgrep_scan.py"
PYPROJECT_HOOK = RULES_DIR / "pyproject_complexity.py"

requires_astgrep = pytest.mark.skipif(
    shutil.which("ast-grep") is None,
    reason="ast-grep binary not on PATH",
)


def _scan(rule_stem: str, source: str, tmp_path: Path, name: str = "sample.py") -> int:
    f = tmp_path / name
    f.write_text(source, encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(ASTGREP_SCAN), rule_stem, str(f)],
        capture_output=True,
        check=False,
    ).returncode


@requires_astgrep
class TestNoPytestDjangoDb:
    def test_flags_decorator(self, tmp_path: Path) -> None:
        src = "import pytest\n\n\n@pytest.mark.django_db\ndef test_x():\n    pass\n"
        assert _scan("no-pytest-django-db", src, tmp_path) == 1

    def test_flags_module_level_assignment(self, tmp_path: Path) -> None:
        src = "import pytest\n\npytestmark = pytest.mark.django_db\n"
        assert _scan("no-pytest-django-db", src, tmp_path) == 1

    def test_flags_module_level_list(self, tmp_path: Path) -> None:
        src = "import pytest\n\npytestmark = [pytest.mark.django_db]\n"
        assert _scan("no-pytest-django-db", src, tmp_path) == 1

    def test_passes_testcase(self, tmp_path: Path) -> None:
        src = "from django.test import TestCase\n\n\nclass T(TestCase):\n    def test_x(self):\n        pass\n"
        assert _scan("no-pytest-django-db", src, tmp_path) == 0

    def test_inline_ignore_suppresses_decorator(self, tmp_path: Path) -> None:
        src = (
            "import pytest\n\n\n"
            "# ast-grep-ignore[ac-django-no-pytest-django-db]\n"
            "@pytest.mark.django_db\ndef test_x():\n    pass\n"
        )
        assert _scan("no-pytest-django-db", src, tmp_path) == 0

    def test_inline_ignore_suppresses_module_assignment(self, tmp_path: Path) -> None:
        src = "import pytest\n\n# ast-grep-ignore[ac-django-no-pytest-django-db]\npytestmark = pytest.mark.django_db\n"
        assert _scan("no-pytest-django-db", src, tmp_path) == 0


@requires_astgrep
class TestTestcaseNoParametrize:
    def test_flags_inside_testcase(self, tmp_path: Path) -> None:
        src = (
            "import pytest\n"
            "from django.test import TestCase\n\n\n"
            "class T(TestCase):\n"
            "    @pytest.mark.parametrize('x', [1])\n"
            "    def test_x(self, x):\n"
            "        pass\n"
        )
        assert _scan("testcase-no-pytest-parametrize", src, tmp_path) == 1

    def test_passes_module_level_function(self, tmp_path: Path) -> None:
        src = "import pytest\n\n\n@pytest.mark.parametrize('x', [1])\ndef test_x(x):\n    assert x\n"
        assert _scan("testcase-no-pytest-parametrize", src, tmp_path) == 0

    def test_inline_ignore_suppresses(self, tmp_path: Path) -> None:
        src = (
            "import pytest\n"
            "from django.test import TestCase\n\n\n"
            "class T(TestCase):\n"
            "    # ast-grep-ignore[ac-django-testcase-no-pytest-parametrize]\n"
            "    @pytest.mark.parametrize('x', [1])\n"
            "    def test_x(self, x):\n"
            "        pass\n"
        )
        assert _scan("testcase-no-pytest-parametrize", src, tmp_path) == 0


@requires_astgrep
class TestNoComplexitySuppressions:
    def test_flags_c901_noqa(self, tmp_path: Path) -> None:
        assert _scan("no-complexity-suppressions", "def f():  # noqa: C901\n    return 1\n", tmp_path) == 1

    def test_flags_plr09_family(self, tmp_path: Path) -> None:
        assert _scan("no-complexity-suppressions", "def f():  # noqa: PLR0912\n    return 1\n", tmp_path) == 1

    def test_passes_unrelated_noqa(self, tmp_path: Path) -> None:
        assert _scan("no-complexity-suppressions", "import os  # noqa: F401\n", tmp_path) == 0

    def test_inline_ignore_suppresses(self, tmp_path: Path) -> None:
        src = "# ast-grep-ignore[ac-django-no-complexity-suppressions]\ndef f():  # noqa: C901\n    return 1\n"
        assert _scan("no-complexity-suppressions", src, tmp_path) == 0


def _pyproject(argv: list[str]) -> int:
    return subprocess.run(
        [sys.executable, str(PYPROJECT_HOOK), *argv],
        capture_output=True,
        check=False,
    ).returncode


class TestPyprojectComplexityHook:
    def _write(self, tmp_path: Path, body: str) -> str:
        f = tmp_path / "pyproject.toml"
        f.write_text(body, encoding="utf-8")
        return str(f)

    def test_has_no_tomllib_runtime_dependency(self) -> None:
        assert "tomllib" not in PYPROJECT_HOOK.read_text(encoding="utf-8")

    def test_flags_new_global_ignore(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff]\nlint.ignore = ["C901", "D100"]\n')
        assert _pyproject([path]) == 1

    def test_flags_multiline_global_ignore(self, tmp_path: Path) -> None:
        path = self._write(
            tmp_path,
            '[tool.ruff.lint]\nignore = [\n  "D100",\n  "PLR0915",\n]\n',
        )
        assert _pyproject([path]) == 1

    def test_flags_new_per_file_ignore(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff.lint.per-file-ignores]\n"tests/*.py" = ["PLR0912"]\n')
        assert _pyproject([path]) == 1

    def test_flags_dotted_per_file_ignore(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff]\nlint.per-file-ignores."scripts/**/*.py" = ["C901"]\n')
        assert _pyproject([path]) == 1

    def test_grandfathered_entry_passes(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff]\nlint.ignore = ["C901"]\n')
        assert _pyproject(["--grandfather", "C901@lint.ignore", path]) == 0

    def test_non_grandfathered_among_grandfathered_fails(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff]\nlint.ignore = ["C901", "PLR0915"]\n')
        assert _pyproject(["--grandfather=C901@lint.ignore", path]) == 1

    def test_passes_without_complexity_codes(self, tmp_path: Path) -> None:
        path = self._write(tmp_path, '[tool.ruff]\nlint.ignore = ["D100", "COM812"]\n')
        assert _pyproject([path]) == 0
