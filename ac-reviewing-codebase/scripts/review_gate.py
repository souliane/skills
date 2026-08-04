"""The review-completion contract: parse the manifest, and say why a checklist is not done."""

import re
from pathlib import Path

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "references" / "review-manifest.md"

_ITEM_RE = re.compile(r"^- \[( |x|X)\]\s+`([^`]+)`\s+(.*)$")
_EVIDENCE_RE = re.compile(r"^\s*evidence:\s*(.*)$")
_NON_NEGOTIABLE = "(non-negotiable)"


class ReviewItem:
    def __init__(self, item_id: str, description: str, *, checked: bool) -> None:
        self.id = item_id
        self.description = description
        self.checked = checked
        self.evidence = ""

    @property
    def mandatory(self) -> bool:
        return _NON_NEGOTIABLE in self.description.lower()


def parse_manifest(text: str) -> list[ReviewItem]:
    items: list[ReviewItem] = []
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            # The manifest documents its own line format inside a fence. Parsing
            # that example as an item would put a permanently-unsatisfiable
            # `<id>` in every checklist.
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _ITEM_RE.match(line)
        if match:
            items.append(ReviewItem(match.group(2), match.group(3), checked=match.group(1).lower() == "x"))
            continue
        evidence = _EVIDENCE_RE.match(line)
        if evidence and items:
            items[-1].evidence = evidence.group(1).strip()
    return items


def verify_items(items: list[ReviewItem]) -> list[str]:
    """Reasons the review is not complete. Empty means it is."""
    failures = [
        f"{i.id}: unchecked, and it is non-negotiable — {i.description}" for i in items if i.mandatory and not i.checked
    ]
    # A tick with no evidence is the failure mode this gate exists for: it costs
    # one keystroke and looks identical to real work in a diff.
    failures += [f"{i.id}: checked but no evidence recorded" for i in items if i.checked and not i.evidence]
    return failures
