"""Meta-tests: each detector FLAGS a known-bad snippet and PASSES known-good."""

from _loader import checkers


class TestDjangoDbDetector:
    def test_flags_pytest_django_db(self) -> None:
        bad = "import pytest\n\n\n@pytest.mark.django_db\ndef test_thing():\n    assert True\n"
        assert checkers.check_django_db(bad) == [4]

    def test_flags_bare_mark_django_db(self) -> None:
        bad = "from pytest import mark\n\n\n@mark.django_db\ndef test_thing():\n    assert True\n"
        assert checkers.check_django_db(bad) == [4]

    def test_passes_testcase(self) -> None:
        good = "from django.test import TestCase\n\n\nclass T(TestCase):\n    def test_x(self):\n        pass\n"
        assert checkers.check_django_db(good) == []

    def test_ignores_unrelated_marker(self) -> None:
        ok = "import pytest\n\n\n@pytest.mark.slow\ndef test_thing():\n    pass\n"
        assert checkers.check_django_db(ok) == []

    def test_tolerates_syntax_error(self) -> None:
        assert checkers.check_django_db("def (:\n") == []


class TestTestcaseParametrizeDetector:
    def test_flags_parametrize_inside_testcase(self) -> None:
        bad = (
            "import pytest\n"
            "from django.test import TestCase\n\n\n"
            "class T(TestCase):\n"
            "    @pytest.mark.parametrize('x', [1, 2])\n"
            "    def test_x(self, x):\n"
            "        pass\n"
        )
        assert checkers.check_testcase_parametrize(bad) == [6]

    def test_flags_inside_transaction_testcase(self) -> None:
        bad = (
            "import pytest\n"
            "from django.test import TransactionTestCase\n\n\n"
            "class T(TransactionTestCase):\n"
            "    @pytest.mark.parametrize('x', [1])\n"
            "    def test_x(self, x):\n"
            "        pass\n"
        )
        assert checkers.check_testcase_parametrize(bad) == [6]

    def test_passes_module_level_pytest_function(self) -> None:
        good = "import pytest\n\n\n@pytest.mark.parametrize('x', [1, 2])\ndef test_x(x):\n    assert x\n"
        assert checkers.check_testcase_parametrize(good) == []

    def test_passes_unittest_parametrize_in_testcase(self) -> None:
        good = (
            "from django.test import TestCase\n"
            "from unittest_parametrize import parametrize, ParametrizedTestCase\n\n\n"
            "class T(ParametrizedTestCase, TestCase):\n"
            "    @parametrize('x', [(1,), (2,)])\n"
            "    def test_x(self, x):\n"
            "        pass\n"
        )
        assert checkers.check_testcase_parametrize(good) == []


class TestComplexityNoqaDetector:
    def test_flags_c901(self) -> None:
        bad = "def f():  # noqa: C901\n    return 1\n"
        assert checkers.check_complexity_noqa(bad) == [1]

    def test_flags_plr0911_family(self) -> None:
        for code in ("PLR0911", "PLR0912", "PLR0915"):
            bad = f"def f():  # noqa: {code}\n    return 1\n"
            assert checkers.check_complexity_noqa(bad) == [1], code

    def test_flags_among_multiple_codes(self) -> None:
        bad = "def f():  # noqa: E501, C901, F401\n    return 1\n"
        assert checkers.check_complexity_noqa(bad) == [1]

    def test_passes_unrelated_noqa(self) -> None:
        ok = "import os  # noqa: F401\nx = 1  # noqa: E501\n"
        assert checkers.check_complexity_noqa(ok) == []

    def test_plr0904_is_in_family(self) -> None:
        assert checkers.check_complexity_noqa("y = 1  # noqa: PLR0904\n") == [1]

    def test_word_boundary_avoids_false_positive(self) -> None:
        # A longer token that merely starts with a complexity code must not trip.
        assert checkers.check_complexity_noqa("x = 1  # noqa: PLR0904XYZ\n") == []
        assert checkers.check_complexity_noqa("x = 1  # noqa: NOTC9011\n") == []


class TestPyprojectComplexityDetector:
    def test_flags_global_ignore(self) -> None:
        src = '[tool.ruff]\nlint.ignore = ["C901", "D100"]\n'
        found = checkers.check_pyproject_complexity(src)
        assert [f.code for f in found] == ["C901"]
        assert found[0].location == "lint.ignore"

    def test_flags_per_file_ignore(self) -> None:
        src = '[tool.ruff.lint.per-file-ignores]\n"tests/*.py" = ["PLR0912", "S101"]\n'
        found = checkers.check_pyproject_complexity(src)
        assert [f.code for f in found] == ["PLR0912"]
        assert found[0].location == "lint.per-file-ignores.tests/*.py"

    def test_passes_pyproject_without_complexity_codes(self) -> None:
        src = '[tool.ruff]\nlint.ignore = ["D100", "COM812"]\n'
        assert checkers.check_pyproject_complexity(src) == []

    def test_tolerates_invalid_toml(self) -> None:
        assert checkers.check_pyproject_complexity("[[[not toml") == []
