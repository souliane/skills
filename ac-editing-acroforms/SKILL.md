---
name: ac-editing-acroforms
description: Inspects, patches, verifies, or diffs AcroForm-based PDF templates — especially when widget geometry, content streams, or filled-output alignment need deterministic scriptable fixes.
compatibility: macOS/Linux, python3, pypdf or pikepdf. Do NOT use pdfrw.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# AcroForm Editor

Generic toolkit for repairing and inspecting AcroForm-based PDF templates.

This skill is intentionally narrow: it focuses on deterministic PDF mechanics that are reusable across projects. It is not a home for document-family playbooks, customer-specific layouts, or repo-specific field schemas.

## Dependencies

Standalone. No dependencies on other skills.

## Layer Contract

This skill is **layer 1 only**.

Layer 1 means generic capabilities that are worth publishing:

- inspect AcroForm fields, widget rects, fonts, and content streams
- apply deterministic content-stream replacements
- realign widget rects
- add or update simple fields
- verify field-to-underline alignment
- diff rendered PDFs

This skill must **not** contain layer 2+ material:

- project-specific field names as rules
- customer or product names
- language/variant matrices for one document family
- repo-specific pipelines
- hardcoded private paths
- one-off scripts that only work for a single private template family

If a fix depends on private template knowledge, keep it in repo-local documentation or in a separate private overlay skill. Do not add it here.

## When To Use

Use this skill when you need to:

- inspect a form template before editing it
- add or move AcroForm widgets
- patch static text in a page content stream
- fix filled values that render above, below, or outside the expected underline
- compare generated PDFs against a baseline
- turn an ad-hoc PDF repair into a reusable script or JSON-driven helper

Do not use this skill as the canonical place for project workflow. If the task depends on a specific repository's fixtures, test classes, naming rules, or document variants, read that repository's local documentation first and keep those details there.

## Generic Workflow

Use this order unless there is a strong reason not to:

1. Read any repo-local docs that describe the target PDFs.
2. Inspect fields, fonts, and page content before touching the file.
3. Decide whether the change is:
   - a generic helper use case,
   - a small spec-driven patch,
   - or a project-specific repair that does **not** belong in this skill.
4. Apply the smallest deterministic change possible.
5. Verify both structure and rendered output.
6. If the automation is reusable, promote it into this skill as a generic helper or sanitized example.

## Durable Helpers

These scripts are intentionally generic and safe to keep in a public niche toolkit:

- `scripts/inspect_fields.py`
  - Inspect field names, rects, fonts, labels, and raw content stream data.
- `scripts/set_field_flags.py`
  - Batch-set readonly and required flags.
- `scripts/add_row.py`
  - Heuristic helper for inserting a paired row of widgets and matching label/content shifts in tabular layouts.
- `scripts/apply_content_stream_replacements.py`
  - Apply literal or regex-based content-stream replacements from a JSON spec.
- `scripts/apply_rect_updates.py`
  - Apply named or rect-matched widget rect updates from a JSON spec.
- `scripts/verify_field_alignment.py`
  - Check whether field rects align with underline bars and optionally compare against filled outputs.
- `scripts/golden_diff.py`
  - Render and compare changed PDFs against a git base revision.

Checked-in examples must stay sanitized and reusable:

- `examples/single_text_position_shift.json`
- `examples/field_rect_realignment.json`

## Spec-Driven Helpers

Prefer a generic helper plus a small JSON spec over a new hardcoded script.

### Content-stream replacement spec

Use `scripts/apply_content_stream_replacements.py` for narrow text or operator edits.

```json
{
  "description": "Move a single text operator in two related templates.",
  "pdfs": [
    {
      "pdf": "/path/to/project/templates/template-a.pdf",
      "page": 1,
      "replacements": [
        {
          "description": "Lower one marker by 3 points",
          "match": "0.009 Tc 532.515 111.967 Td",
          "replace": "0.009 Tc 532.515 108.801 Td",
          "count": 1,
          "expected_matches": 1
        }
      ]
    }
  ]
}
```

### Widget-rect update spec

Use `scripts/apply_rect_updates.py` when the content stream is already fine but the widget geometry is wrong.

```json
{
  "description": "Realign named and unnamed widgets onto their correct bars.",
  "pdfs": [
    {
      "pdf": "/path/to/project/templates/template.pdf",
      "page": 1,
      "updates": [
        {
          "description": "Move first field",
          "name": "section/0/exampleField",
          "rect": [141.76, 121.305, 315.487, 133.267]
        },
        {
          "description": "Move unnamed widget matched by old rect",
          "name": "",
          "match_rect": [141.76, 93.1, 315.487, 105.1],
          "rect": [141.76, 107.129, 315.487, 119.091]
        }
      ]
    }
  ]
}
```

## Core Rules

### Prefer `pikepdf` for template modification

Use `pikepdf` for content-stream edits and widget updates when preserving untouched pages matters.

Use `pypdf` when you need to create new fields or clone/edit whole documents in memory.

Do not use `pdfrw`.

### Match neighboring field attributes exactly

Before adding a field, inspect a nearby field in the same section and match:

- `/DA`
- `/MK`
- `/P`
- `/Ff`
- `/F`
- `/Rect`
- presence or absence of `/AP`
- presence or absence of `/V`

If the surrounding fields have no `/AP`, do not add one just because it seems safer.

### Content-stream positioning is not just `Td`

PDF text and bars may be positioned using different operators:

- `Td` / `TD` for relative moves
- `Tm` for absolute text matrices
- `cm` for transformed bar placement

If you shift one family of operators and ignore the others, the page will drift out of alignment.

### Font subsets are real constraints

Embedded font subsets may not encode every character you need. If a glyph is missing:

- inspect the page fonts and `ToUnicode` maps first
- switch to another subset of the same typeface only if the glyph really exists there
- avoid guessing glyph IDs across subsets

### Field geometry affects filled output

If the runtime filler generates appearances from widget rects, changing `/Rect` can change the visible filled PDF even when the page content stream is unchanged.

Do not assume a "rect-only" fix is render-neutral. Verify the filled output.

## Verification

Use both structural and rendered checks.

### Structural

- inspect fields after edits
- verify field counts and positions
- run `scripts/verify_field_alignment.py` when the template uses underline bars or other line-based alignment

### Rendered

- render affected pages with GhostScript or another deterministic renderer
- compare against a known baseline
- inspect only the pages that changed, not the whole file if unnecessary

### Appearance-stream blind spot

GhostScript-based page comparisons can miss broken form appearance generation in some workflows.

If the final user-facing PDF depends on runtime-generated widget appearances:

- verify the filled output, not just the template
- confirm fields that should display values actually render values in a viewer or via a workflow that generates appearances

## Open-Source Safety Rules

Everything checked into this skill must be safe to publish:

- no home-directory paths
- no customer names
- no repository-specific branches, refs, or ticket IDs
- no private field schemas as canonical examples
- no screenshots or examples containing personal data

Sanitized examples may still describe a repair class, but they must use placeholder paths and generic field names.

## Contribution Gate

Before adding anything new to this skill, ask:

1. Is this reusable outside one private document family?
2. Can it be expressed as a generic helper or sanitized example?
3. Does it avoid private paths, names, and repo assumptions?
4. Is the logic still understandable without knowing the original project?

If the answer to any of these is no, the change does not belong in this skill.

## Maintenance Rule

Treat this skill as publishable by default.

- if a helper needs private template names, private file layouts, or a customer-specific repair sequence, move it to an internal overlay or the target repo
- if a checked-in example only makes sense with private field names or private coordinates, replace it with a sanitized example before merging
- if a future change mixes generic mechanics with a private workflow, split it before commit instead of leaving a temporary exception behind

## Review Checklist

Before committing changes to this skill:

- `ruff check` passes on the Python helpers
- formatter hooks pass
- checked-in JSON examples are valid
- examples use placeholder paths
- no project-specific scripts were added
- no private/internal identifiers leaked into docs or examples

This skill should stay a small, generic AcroForm repair toolkit. If it starts accumulating private document-family heuristics, it has crossed the layer boundary and needs to be split.
