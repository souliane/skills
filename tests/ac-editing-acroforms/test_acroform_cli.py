"""One entry point, one way to exit.

The skill used to ship five sibling modules that each declared their own
`typer.Typer(...)`, one module that parsed `sys.argv` with argparse (and was
therefore dead when registered on the unified app), and three different exit
mechanisms. These tests pin the single surface that replaced them.
"""

import ast
from pathlib import Path

import acroform_errors
import pytest
import typer
from _stubs import import_with_pikepdf_stub

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "ac-editing-acroforms" / "scripts"
CLI_PATH = SCRIPTS_DIR / "cli.py"
SIBLINGS = sorted(p for p in SCRIPTS_DIR.glob("*.py") if p != CLI_PATH)


def _declares_typer_app(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "Typer"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "typer"
        for node in ast.walk(tree)
    )


def _registered_commands() -> dict[str, str]:
    """``{module stem: function name}`` for every command cli.py registers."""
    tree = ast.parse(CLI_PATH.read_text(encoding="utf-8"))
    origin: dict[str, tuple[str, str]] = {
        alias.asname or alias.name: (node.module or "", alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    registered: dict[str, str] = {}
    for node in ast.walk(tree):
        # `app.command(name="x")(fn)` — the outer call's single arg is the fn.
        if (
            isinstance(node, ast.Call)
            and len(node.args) == 1
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id in origin
        ):
            module, func = origin[node.args[0].id]
            registered[module] = func
    return registered


def _takes_arguments(path: Path, func_name: str) -> bool:
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            return bool(node.args.args or node.args.kwonlyargs)
    msg = f"{path.name} has no function named {func_name}"
    raise AssertionError(msg)


class TestSingleEntryPoint:
    def test_only_cli_declares_a_typer_app(self) -> None:
        assert [p.name for p in SIBLINGS if _declares_typer_app(p)] == []
        assert _declares_typer_app(CLI_PATH)

    def test_only_cli_runs_anything_when_executed(self) -> None:
        offenders = [p.name for p in SIBLINGS if "__main__" in p.read_text(encoding="utf-8")]
        assert offenders == []

    def test_no_script_parses_its_own_arguments_with_argparse(self) -> None:
        # A module registered on the unified app but reading sys.argv itself is
        # dead on that app: typer gives its command no parameters at all.
        offenders = [p.name for p in SCRIPTS_DIR.glob("*.py") if "argparse" in p.read_text(encoding="utf-8")]
        assert offenders == []

    def test_every_registered_command_accepts_arguments(self) -> None:
        # `verify-alignment` used to register an argparse `main()` that takes no
        # parameters, so typer gave the command none either: every documented
        # invocation of it died on "No such option".
        argless = [
            f"{module}.{func}"
            for module, func in _registered_commands().items()
            if not _takes_arguments(SCRIPTS_DIR / f"{module}.py", func)
        ]
        assert argless == []


class TestUniformExitCodes:
    """A spec error and a verification failure must be tellable apart by a caller."""

    @pytest.mark.parametrize("module_name", ["apply_content_stream_replacements", "apply_rect_updates"])
    def test_a_verification_failure_exits_1(self, module_name: str, monkeypatch, tmp_path: Path) -> None:
        module = import_with_pikepdf_stub(module_name)

        def _fail(_spec: Path) -> None:
            msg = "the PDF did not match the spec"
            raise acroform_errors.VerificationError(msg)

        monkeypatch.setattr(module, "apply_spec", _fail)
        with pytest.raises(typer.Exit) as raised:
            module.main(tmp_path / "spec.json")
        assert raised.value.exit_code == 1

    def test_a_malformed_spec_exits_2(self, monkeypatch, tmp_path: Path) -> None:
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        def _fail(_spec: Path) -> None:
            msg = "unknown regex flag: NOPE"
            raise acroform_errors.SpecError(msg)

        monkeypatch.setattr(module, "apply_spec", _fail)
        with pytest.raises(typer.Exit) as raised:
            module.main(tmp_path / "spec.json")
        assert raised.value.exit_code == 2
