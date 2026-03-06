#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pypdf>=4.0"]
# ///
"""Generate minimal test PDFs for golden_diff tests.

Creates two 2-page PDFs that differ on page 2 only:
    - fixture_v1.pdf: page 1 = "Hello", page 2 = "Version 1"
    - fixture_v2.pdf: page 1 = "Hello", page 2 = "Version 2"

Usage:
    uv run create_test_pdfs.py [output_dir]
"""

from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)


def create_fixture_pdf(output: Path, page1_text: str, page2_text: str) -> None:
    """Create a 2-page PDF with given text on each page."""
    writer = PdfWriter()

    for _text in [page1_text, page2_text]:
        writer.add_blank_page(width=595, height=842)

    # Write content streams after pages exist
    for i, text in enumerate([page1_text, page2_text]):
        page = writer.pages[i]

        # Add font resource
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
        font_ref = writer._add_object(font)
        page[NameObject("/Resources")] = DictionaryObject(
            {
                NameObject("/Font"): DictionaryObject(
                    {
                        NameObject("/F1"): font_ref,
                    }
                ),
            }
        )

        # Add content stream
        stream = DecodedStreamObject()
        content = f"BT /F1 24 Tf 100 421 Td ({text}) Tj ET"
        stream.set_data(content.encode("latin-1"))
        stream_ref = writer._add_object(stream)
        page[NameObject("/Contents")] = stream_ref

    with output.open("wb") as f:
        writer.write(f)


def main(output_dir: Path | None = None) -> None:
    dest = output_dir or Path(__file__).parent
    dest.mkdir(parents=True, exist_ok=True)

    create_fixture_pdf(dest / "fixture_v1.pdf", "Hello", "Version 1")
    create_fixture_pdf(dest / "fixture_v2.pdf", "Hello", "Version 2")
    print(f"Created fixture_v1.pdf and fixture_v2.pdf in {dest}")


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    main(out)
