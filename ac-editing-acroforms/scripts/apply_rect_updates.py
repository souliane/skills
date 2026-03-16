#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["pikepdf>=9.0", "typer>=0.12"]
# ///
r"""Apply AcroForm widget rect updates from a JSON spec.

This is the durable replacement for one-off `/tmp/fix_*.py` scripts that only
realign a few named or unnamed widgets.

Usage:
    uv run scripts/apply_rect_updates.py spec.json
"""

import json
from pathlib import Path

import pikepdf  # ty: ignore[unresolved-import]
import typer


def _rect_tuple(obj: pikepdf.Dictionary) -> tuple[float, float, float, float]:
    return tuple(float(v) for v in obj["/Rect"])  # type: ignore[return-value]


def _set_rect(obj: pikepdf.Dictionary, rect: list[float]) -> None:
    obj["/Rect"] = pikepdf.Array(rect)


def _matches(obj: pikepdf.Dictionary, rule: dict) -> bool:
    name = str(obj.get("/T", ""))
    if "name" in rule and name != rule["name"]:
        return False
    return "match_rect" not in rule or _rect_tuple(obj) == tuple(rule["match_rect"])


def apply_spec(spec_path: Path) -> None:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    for pdf_spec in spec["pdfs"]:
        pdf_path = Path(pdf_spec["pdf"])
        page_index = int(pdf_spec.get("page", 1))
        pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)
        page = pdf.pages[page_index]
        annots = page.obj.get("/Annots")
        if annots is None:
            msg = f"{pdf_path}: page {page_index} has no annotations"
            raise SystemExit(msg)

        applied: list[str] = []
        seen: set[int] = set()
        for obj in annots:
            for idx, rule in enumerate(pdf_spec["updates"]):
                if idx in seen:
                    continue
                if _matches(obj, rule):
                    _set_rect(obj, rule["rect"])
                    seen.add(idx)
                    applied.append(rule.get("description", f"update #{idx + 1}"))
                    break

        missing = [
            pdf_spec["updates"][i].get("description", f"update #{i + 1}")
            for i in range(len(pdf_spec["updates"]))
            if i not in seen
        ]
        if missing:
            msg = f"{pdf_path}: missing rect targets: {missing}"
            raise SystemExit(msg)

        pdf.save(pdf_path)
        pdf.close()
        print(f"{pdf_path}: applied {len(applied)} rect updates")
        for item in applied:
            print(f"  - {item}")


def main(spec: Path = typer.Argument(help="Path to JSON spec")) -> None:
    apply_spec(spec)


if __name__ == "__main__":
    typer.run(main)
