"""The banned-terms gate ships into every repo scaffolded from this boilerplate.

It had no test, and it was inert: the hook passed `--config PATH` to a script with no argument
parsing, so the flag and its path were treated as filenames and dropped by the file loop. It also
exited 0 when the config was absent. A leak gate that silently passes is worse than no gate — the
repo believes it is protected.

Every assertion here is about the gate REFUSING. A test that only proves the happy path would have
passed against the broken version too.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parent.parent / "scripts" / "hooks" / "check-banned-terms.sh"
BANNED = "zzsecretterm"


def run(*args: str, home: Path | None = None) -> subprocess.CompletedProcess[str]:
    bash = shutil.which("bash")
    assert bash, "bash is required to exercise the hook"
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home)} if home else None
    return subprocess.run([bash, str(HOOK), *args], capture_output=True, text=True, check=False, env=env)


@pytest.fixture
def config(tmp_path: Path) -> Path:
    path = tmp_path / "banned.env"
    path.write_text(f'T3_BANNED_TERMS="{BANNED}"\n', encoding="utf-8")
    return path


@pytest.fixture
def offending(tmp_path: Path) -> Path:
    path = tmp_path / "doc.md"
    path.write_text(f"a line mentioning {BANNED} in passing\n", encoding="utf-8")
    return path


class TestConfigFlagIsHonoured:
    def test_banned_term_under_explicit_config_fails(self, config: Path, offending: Path) -> None:
        assert run("--config", str(config), str(offending)).returncode == 1

    def test_equals_form_of_the_flag_also_works(self, config: Path, offending: Path) -> None:
        assert run(f"--config={config}", str(offending)).returncode == 1

    def test_the_flag_is_not_scanned_as_if_it_were_a_file(self, config: Path, tmp_path: Path) -> None:
        # The old script had no arg parsing, so "--config" and its path fell through to the file
        # loop and were skipped by the `[ -f ]` guard — taking the whole gate with them.
        clean = tmp_path / "clean.md"
        clean.write_text("nothing to see\n", encoding="utf-8")
        assert run("--config", str(config), str(clean)).returncode == 0


class TestMissingConfigFailsLoud:
    def test_absent_config_exits_2_rather_than_passing(self, tmp_path: Path, offending: Path) -> None:
        assert run("--config", str(tmp_path / "nope.env"), str(offending)).returncode == 2

    def test_absent_default_config_exits_2(self, tmp_path: Path, offending: Path) -> None:
        assert run(str(offending), home=tmp_path).returncode == 2


class TestConfiguredButEmpty:
    def test_config_present_with_no_terms_passes(self, tmp_path: Path, offending: Path) -> None:
        empty = tmp_path / "empty.env"
        empty.write_text("# nothing configured\n", encoding="utf-8")
        assert run("--config", str(empty), str(offending)).returncode == 0
