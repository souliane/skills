#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pikepdf>=9.0"]
# ///
r"""Apply deterministic content-stream replacements from a JSON spec.

This is the durable replacement for one-off `/tmp/fix_*.py` scripts that
only tweak a few BT/ET blocks or text operators.

Usage:
    uv run scripts/apply_content_stream_replacements.py spec.json
"""

import argparse
import json
import re
from pathlib import Path

import pikepdf  # ty: ignore[unresolved-import]


def _read_stream(page: pikepdf.Page) -> str:
    contents = page.get("/Contents")
    if contents is None:
        return ""
    if isinstance(contents, pikepdf.Array):
        return b"".join(bytes(ref.read_bytes()) for ref in contents).decode("latin-1")
    return bytes(contents.read_bytes()).decode("latin-1")


def _write_stream(pdf: pikepdf.Pdf, page: pikepdf.Page, data: str) -> None:
    page["/Contents"] = pdf.make_indirect(pikepdf.Stream(pdf, data.encode("latin-1")))


def _compile_flags(flag_names: list[str]) -> int:
    flag_map = {
        "IGNORECASE": re.IGNORECASE,
        "MULTILINE": re.MULTILINE,
        "DOTALL": re.DOTALL,
    }
    flags = 0
    for name in flag_names:
        try:
            flags |= flag_map[name]
        except KeyError as exc:
            msg = f"unknown regex flag: {name}"
            raise SystemExit(msg) from exc
    return flags


def _apply_replacement(data: str, replacement: dict, pdf_label: str) -> tuple[str, str]:
    description = replacement.get("description", "(unnamed replacement)")

    if "match" in replacement:
        match = replacement["match"]
        count = int(replacement.get("count", 1))
        actual = data.count(match)
        expected = int(replacement.get("expected_matches", count))
        if actual < expected:
            msg = f"{pdf_label}: {description}: expected at least {expected} literal matches, found {actual}"
            raise SystemExit(msg)
        return data.replace(match, replacement["replace"], count), description

    if "regex" in replacement:
        pattern = replacement["regex"]
        repl = replacement["replace"]
        count = int(replacement.get("count", 0))
        expected = int(replacement.get("expected_matches", 1))
        flags = _compile_flags(replacement.get("flags", []))
        new_data, actual = re.subn(pattern, repl, data, count=count, flags=flags)
        if actual != expected:
            msg = f"{pdf_label}: {description}: expected {expected} regex replacements, got {actual}"
            raise SystemExit(msg)
        return new_data, description

    msg = f"{pdf_label}: replacement must define either 'match' or 'regex'"
    raise SystemExit(msg)


def apply_spec(spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for pdf_spec in spec["pdfs"]:
        pdf_path = Path(pdf_spec["pdf"])
        page_index = int(pdf_spec.get("page", 1))
        pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
        page = pdf.pages[page_index]
        data = _read_stream(page)
        original = data
        applied: list[str] = []

        for replacement in pdf_spec["replacements"]:
            data, description = _apply_replacement(data, replacement, str(pdf_path))
            applied.append(description)

        if data != original:
            _write_stream(pdf, page, data)
            pdf.save(pdf_path)
        pdf.close()
        print(f"{pdf_path}: applied {len(applied)} content replacements")
        for item in applied:
            print(f"  - {item}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path, help="Path to JSON spec")
    args = parser.parse_args()
    apply_spec(args.spec)


if __name__ == "__main__":
    main()
