import importlib
import sys
from types import ModuleType

import pytest


def import_with_pikepdf_stub(module_name: str):
    sys.modules.pop(module_name, None)
    stub = ModuleType("pikepdf")
    stub.__dict__.update(
        {
            "Array": list,
            "Dictionary": dict,
            "Page": object,
            "Pdf": object,
            "Stream": object,
        }
    )
    sys.modules["pikepdf"] = stub
    return importlib.import_module(module_name)


class TestApplyContentStreamReplacements:
    def test_compile_flags_combines_regex_flags(self):
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        flags = module._compile_flags(["IGNORECASE", "MULTILINE"])

        assert flags & module.re.IGNORECASE
        assert flags & module.re.MULTILINE

    def test_compile_flags_rejects_unknown_flag(self):
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        with pytest.raises(SystemExit, match="unknown regex flag"):
            module._compile_flags(["NOT_A_FLAG"])

    def test_apply_literal_replacement(self):
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        updated, description = module._apply_replacement(
            "alpha 111 omega",
            {
                "description": "lower one marker",
                "match": "111",
                "replace": "108",
                "count": 1,
                "expected_matches": 1,
            },
            "template.pdf",
        )

        assert updated == "alpha 108 omega"
        assert description == "lower one marker"

    def test_apply_regex_replacement(self):
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        updated, description = module._apply_replacement(
            "0.009 Tc 532.515 111.967 Td",
            {
                "description": "shift marker",
                "regex": r"111\.967",
                "replace": "108.801",
                "expected_matches": 1,
            },
            "template.pdf",
        )

        assert updated == "0.009 Tc 532.515 108.801 Td"
        assert description == "shift marker"

    def test_apply_replacement_fails_when_expected_match_missing(self):
        module = import_with_pikepdf_stub("apply_content_stream_replacements")

        with pytest.raises(SystemExit, match="expected at least 1 literal matches, found 0"):
            module._apply_replacement(
                "alpha",
                {
                    "description": "missing marker",
                    "match": "beta",
                    "replace": "gamma",
                },
                "template.pdf",
            )


class TestApplyRectUpdates:
    def test_matches_named_field(self):
        module = import_with_pikepdf_stub("apply_rect_updates")

        widget = {"/T": "section/0/exampleField", "/Rect": [1, 2, 3, 4]}

        assert module._matches(widget, {"name": "section/0/exampleField"})
        assert not module._matches(widget, {"name": "section/1/exampleField"})

    def test_matches_by_name_and_rect(self):
        module = import_with_pikepdf_stub("apply_rect_updates")

        widget = {"/T": "", "/Rect": [141.76, 93.1, 315.487, 105.1]}

        assert module._matches(
            widget,
            {"name": "", "match_rect": [141.76, 93.1, 315.487, 105.1]},
        )
        assert not module._matches(
            widget,
            {"name": "", "match_rect": [141.76, 107.129, 315.487, 119.091]},
        )


class TestVerifyFieldAlignment:
    def test_extract_underlines_finds_line_bars_in_two_columns(self):
        module = import_with_pikepdf_stub("verify_field_alignment")

        content = """173.7 0 0 1 141.76 127.1 cm
0 0 m
173.7 0 l
S
173.7 0 0 1 359.125 113.1 cm
0 0 m
173.7 0 l
S"""

        underlines = module.extract_underlines(content, y_min=100, y_max=140)

        assert len(underlines) == 2
        assert underlines[0].column == 1
        assert underlines[1].column == 2

    def test_match_fields_to_underlines_reports_alignment_and_unmatched_items(self):
        module = import_with_pikepdf_stub("verify_field_alignment")

        fields = [
            module.FieldRect("aligned", 141.76, 121.3, 315.48, 133.2, 1),
            module.FieldRect("too-low", 141.76, 90.0, 315.48, 102.0, 1),
        ]
        underlines = [
            module.Underline(141.76, 127.1, 173.7, 1.0, 1),
            module.Underline(141.76, 113.1, 173.7, 1.0, 1),
        ]

        results, unmatched_underlines, unmatched_fields = module.match_fields_to_underlines(fields, underlines)

        assert len(results) == 2
        assert results[0].field.name == "aligned"
        assert results[0].aligned is True
        assert results[1].field.name == "too-low"
        assert results[1].aligned is False
        assert results[1].suggested_rect == pytest.approx((111.6, 123.6))
        assert len(unmatched_underlines) == 1
        assert len(unmatched_fields) == 1
