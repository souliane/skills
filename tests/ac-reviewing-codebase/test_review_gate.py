"""The completion gate: a review is not done until this says so.

The failure this guards against is a review reported complete at a fraction of
its scope. Every assertion here is about the gate REFUSING — a gate that only
passes is indistinguishable from no gate.
"""

from pathlib import Path

from _cli_import import load, load_cli
from typer.testing import CliRunner

cli = load_cli()
review_gate = load("review_gate")

runner = CliRunner()

ITEM = "- [{mark}] `{id}` {desc}\n      evidence:{ev}\n"


def _checklist(*rows: tuple[str, str, str, str]) -> str:
    return "".join(ITEM.format(mark=m, id=i, desc=d, ev=e) for m, i, d, e in rows)


class TestParseManifest:
    def test_reads_id_description_and_checked_state(self) -> None:
        items = review_gate.parse_manifest(_checklist(("x", "1.1", "Did a thing", " ran it")))
        assert [(i.id, i.checked, i.evidence) for i in items] == [("1.1", True, "ran it")]

    def test_non_negotiable_is_detected_from_the_description(self) -> None:
        items = review_gate.parse_manifest(_checklist((" ", "1.1", "A thing (non-negotiable)", "")))
        assert items[0].mandatory is True

    def test_the_format_example_in_a_fence_is_not_an_item(self) -> None:
        # The manifest documents its own line format. Parsing that example would
        # put a permanently-unsatisfiable `<id>` into every checklist.
        text = "```\n- [ ] `<id>` <description> (non-negotiable)\n```\n" + _checklist((" ", "1.1", "Real", ""))
        assert [i.id for i in review_gate.parse_manifest(text)] == ["1.1"]


class TestVerifyRefuses:
    def test_unticked_non_negotiable_fails(self) -> None:
        items = review_gate.parse_manifest(_checklist((" ", "1.1", "A thing (non-negotiable)", "")))
        assert review_gate.verify_items(items)

    def test_ticked_without_evidence_fails(self) -> None:
        # Rubber-stamping is one keystroke and looks identical to real work.
        items = review_gate.parse_manifest(_checklist(("x", "1.1", "A thing (non-negotiable)", "")))
        assert any("no evidence" in f for f in review_gate.verify_items(items))

    def test_unticked_optional_item_does_not_fail(self) -> None:
        items = review_gate.parse_manifest(_checklist((" ", "1.1", "A nice-to-have", "")))
        assert review_gate.verify_items(items) == []

    def test_fully_evidenced_checklist_passes(self) -> None:
        items = review_gate.parse_manifest(_checklist(("x", "1.1", "A thing (non-negotiable)", " grepped X, found Y")))
        assert review_gate.verify_items(items) == []

    def test_not_applicable_is_a_recorded_judgment_not_a_skip(self) -> None:
        items = review_gate.parse_manifest(
            _checklist(("x", "1.1", "A thing (non-negotiable)", " n/a — no Django in scope"))
        )
        assert review_gate.verify_items(items) == []


class TestReviewVerifyCommand:
    def test_exits_nonzero_when_no_checklist_exists(self, tmp_path: Path) -> None:
        result = runner.invoke(cli.app, ["review-verify", str(tmp_path / "absent.md")])
        assert result.exit_code == 1

    def test_exits_nonzero_on_a_freshly_rendered_checklist(self, tmp_path: Path) -> None:
        out = tmp_path / "checklist.md"
        assert runner.invoke(cli.app, ["review-checklist", "--out", str(out)]).exit_code == 0
        assert runner.invoke(cli.app, ["review-verify", str(out)]).exit_code == 1

    def test_exits_nonzero_when_the_file_parses_to_nothing(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.md"
        empty.write_text("# not a checklist\n", encoding="utf-8")
        assert runner.invoke(cli.app, ["review-verify", str(empty)]).exit_code == 1


class TestShippedManifest:
    """A format drift would silently empty the gate — it must stay parseable."""

    def test_manifest_ships_and_parses_to_a_substantial_checklist(self) -> None:
        items = review_gate.parse_manifest(review_gate.MANIFEST_PATH.read_text(encoding="utf-8"))
        assert len(items) > 50
        assert sum(1 for i in items if i.mandatory) > 20

    def test_every_shipped_item_starts_unticked(self) -> None:
        items = review_gate.parse_manifest(review_gate.MANIFEST_PATH.read_text(encoding="utf-8"))
        assert [i.id for i in items if i.checked] == []

    def test_item_ids_are_unique(self) -> None:
        ids = [i.id for i in review_gate.parse_manifest(review_gate.MANIFEST_PATH.read_text(encoding="utf-8"))]
        assert len(ids) == len(set(ids))

    def test_the_shipped_manifest_covers_every_review_phase(self) -> None:
        ids = [i.id for i in review_gate.parse_manifest(review_gate.MANIFEST_PATH.read_text(encoding="utf-8"))]
        for phase in ("0.", "1.", "2.", "3.", "4.", "A.", "5.", "6."):
            assert any(i.startswith(phase) for i in ids), f"no items for phase {phase}"
