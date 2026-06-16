"""Meta-tests for the ratchet: strict default, allow, baseline, anti-growth."""

from pathlib import Path

from _loader import Violation, ratchet


def _v(path: str) -> Violation:
    return Violation(path=path, detail="bad")


class TestStrictDefault:
    def test_no_tolerance_fails_on_violation(self) -> None:
        result = ratchet.evaluate([_v("tests/test_a.py")], allow=[], baseline_path=None)
        assert not result.ok
        assert [f.path for f in result.failures] == ["tests/test_a.py"]

    def test_no_violations_passes(self) -> None:
        result = ratchet.evaluate([], allow=[], baseline_path=None)
        assert result.ok


class TestAllowGlobs:
    def test_exact_allow_grandfathers(self) -> None:
        result = ratchet.evaluate([_v("tests/test_a.py")], allow=["tests/test_a.py"], baseline_path=None)
        assert result.ok

    def test_glob_allow_grandfathers(self) -> None:
        result = ratchet.evaluate([_v("tests/legacy/test_a.py")], allow=["tests/legacy/*.py"], baseline_path=None)
        assert result.ok

    def test_allow_does_not_grandfather_other_files(self) -> None:
        result = ratchet.evaluate(
            [_v("tests/test_a.py"), _v("tests/test_b.py")],
            allow=["tests/test_a.py"],
            baseline_path=None,
        )
        assert [f.path for f in result.failures] == ["tests/test_b.py"]


class TestBaselineGrandfather:
    def test_baselined_file_passes(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\n", encoding="utf-8")
        result = ratchet.evaluate([_v("tests/test_a.py")], allow=[], baseline_path=str(baseline))
        assert result.ok

    def test_new_violation_outside_baseline_fails(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\n", encoding="utf-8")
        result = ratchet.evaluate(
            [_v("tests/test_a.py"), _v("tests/test_new.py")],
            allow=[],
            baseline_path=str(baseline),
        )
        assert [f.path for f in result.failures] == ["tests/test_new.py"]

    def test_allow_and_baseline_compose(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\n", encoding="utf-8")
        result = ratchet.evaluate(
            [_v("tests/test_a.py"), _v("tests/test_b.py")],
            allow=["tests/test_b.py"],
            baseline_path=str(baseline),
        )
        assert result.ok


class TestRatchetOnlyTightens:
    def test_shrunk_baseline_is_fine(self, tmp_path: Path) -> None:
        # Baseline lists exactly the current violation — nothing stale.
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\n", encoding="utf-8")
        result = ratchet.evaluate([_v("tests/test_a.py")], allow=[], baseline_path=str(baseline))
        assert result.ok

    def test_stale_baseline_entry_is_reported_full_tree(self, tmp_path: Path) -> None:
        # A fixed file still listed in the baseline must force the baseline to shrink.
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\ntests/test_fixed.py\n", encoding="utf-8")
        result = ratchet.evaluate([_v("tests/test_a.py")], allow=[], baseline_path=str(baseline))
        assert not result.ok
        assert result.stale_baseline_entries == ["tests/test_fixed.py"]

    def test_stale_only_within_scanned_set(self, tmp_path: Path) -> None:
        # A partial prek run that did not scan tests/test_other.py must NOT flag it
        # stale just because it produced no violation this run.
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\ntests/test_other.py\n", encoding="utf-8")
        result = ratchet.evaluate(
            [_v("tests/test_a.py")],
            allow=[],
            baseline_path=str(baseline),
            scanned_keys=["tests/test_a.py"],
        )
        assert result.ok

    def test_stale_within_scanned_set_is_reported(self, tmp_path: Path) -> None:
        # A scanned file that is baselined but no longer violates IS flagged.
        baseline = tmp_path / "b.baseline"
        baseline.write_text("tests/test_a.py\ntests/test_fixed.py\n", encoding="utf-8")
        result = ratchet.evaluate(
            [_v("tests/test_a.py")],
            allow=[],
            baseline_path=str(baseline),
            scanned_keys=["tests/test_a.py", "tests/test_fixed.py"],
        )
        assert result.stale_baseline_entries == ["tests/test_fixed.py"]


class TestUpdateBaseline:
    def test_writes_sorted_unique(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.baseline"
        ratchet.write_baseline(str(baseline), ["tests/b.py", "tests/a.py", "tests/a.py"])
        assert baseline.read_text(encoding="utf-8") == "tests/a.py\ntests/b.py\n"

    def test_roundtrip_grandfathers_everything(self, tmp_path: Path) -> None:
        baseline = tmp_path / "b.baseline"
        violations = [_v("tests/test_a.py"), _v("tests/test_b.py")]
        ratchet.write_baseline(str(baseline), ratchet.current_violation_paths(violations))
        result = ratchet.evaluate(violations, allow=[], baseline_path=str(baseline))
        assert result.ok
