"""Add a field row to an AcroForm PDF template.

This script:
1. Parses the target section to find the insertion point
2. Encodes the new label using available font glyphs
3. Shifts content below the insertion point down
4. Inserts new label, underlines, currency markers, and AcroForm fields

Usage:
    uv run add_row.py <pdf> <field_name> <label> --insert-after <label> [-o output.pdf]
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pypdf
import typer
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

app = typer.Typer(no_args_is_help=True)


# ---------------------------------------------------------------------------
# Font handling
# ---------------------------------------------------------------------------


@dataclass
class FontInfo:
    name: str
    base_font: str
    char_to_glyph: dict[str, str] = field(default_factory=dict)
    glyph_to_char: dict[str, str] = field(default_factory=dict)

    def can_encode(self, text: str) -> bool:
        return all(ch in self.char_to_glyph for ch in text)

    def encode_hex(self, text: str) -> str:
        glyphs = []
        for ch in text:
            g = self.char_to_glyph.get(ch)
            if g is None:
                msg = f"Char '{ch}' not in font {self.name}"
                raise ValueError(msg)
            glyphs.append(g)
        return "<" + "".join(glyphs) + ">"


def extract_font_maps(page: pypdf.generic.DictionaryObject) -> dict[str, FontInfo]:
    fonts_dict = page["/Resources"].get("/Font", {})
    fonts: dict[str, FontInfo] = {}
    for font_name in fonts_dict:
        font_obj = fonts_dict[font_name].get_object()
        base_font = str(font_obj.get("/BaseFont", "unknown"))
        info = FontInfo(name=font_name, base_font=base_font)
        tounicode = font_obj.get("/ToUnicode")
        if tounicode:
            cmap = tounicode.get_object().get_data().decode("latin-1")
            in_bf = False
            for line in cmap.split("\n"):
                if "beginbfchar" in line:
                    in_bf = True
                    continue
                if "endbfchar" in line:
                    in_bf = False
                    continue
                if in_bf and "<" in line:
                    m = re.findall(r"<([0-9A-Fa-f]+)>", line)
                    if len(m) == 2:
                        gid = m[0].upper().zfill(4)
                        try:
                            ch = chr(int(m[1], 16))
                        except (ValueError, OverflowError):
                            continue
                        info.glyph_to_char[gid] = ch
                        info.char_to_glyph[ch] = gid
        fonts[font_name] = info
    return fonts


def decode_hex(hex_str: str, font: FontInfo) -> str:
    clean = hex_str.strip("<>")
    return "".join(font.glyph_to_char.get(clean[i : i + 4].upper(), "?") for i in range(0, len(clean), 4))


def find_best_font(fonts: dict[str, FontInfo], text: str) -> FontInfo | None:
    # Prefer C0_* fonts (CIDFont label fonts)
    for f in sorted(fonts.values(), key=lambda f: (not f.name.startswith("/C0_"), f.name)):
        if f.can_encode(text):
            return f
    return None


# ---------------------------------------------------------------------------
# Content stream analysis
# ---------------------------------------------------------------------------


@dataclass
class LabelInfo:
    line_idx: int
    font_name: str
    hex_string: str
    decoded: str
    y_approx: float


def find_labels_in_income_section(lines: list[str], fonts: dict[str, FontInfo]) -> list[LabelInfo]:
    """Find all text labels in the bottom half of page 2 (income section)."""
    labels = []
    cur_font = None
    cur_y = 0.0
    cur_leading = 0.0

    for i, line in enumerate(lines):
        s = line.strip()
        # Reset Y tracking at BT boundaries to prevent cross-block accumulation
        if s == "BT":
            cur_y = 0.0
            cur_leading = 0.0
        # Font
        m = re.match(r"/(C\w+_\d+)\s+\d+\s+Tf", s)
        if m:
            cur_font = "/" + m.group(1)
        # Tm — absolute positioning
        m = re.match(r".*?(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+Tm", s)
        if m:
            cur_y = float(m.group(6))
        # Td or TD — relative (use search to handle lines with Tc/Tw prefix)
        m = re.search(r"([\d.\-]+)\s+([\d.\-]+)\s+(T[dD])\s*$", s)
        if m:
            cur_y += float(m.group(2))
            if m.group(3) == "TD":
                cur_leading = float(m.group(2))
        # T*
        if s == "T*":
            cur_y += cur_leading
        # Tj with hex
        m = re.match(r"<([0-9A-Fa-f]+)>Tj", s)
        if m and cur_font and cur_font in fonts:
            decoded = decode_hex(m.group(1), fonts[cur_font])
            if len(decoded) > 1 and "?" not in decoded:
                labels.append(LabelInfo(i, cur_font, m.group(1), decoded, cur_y))

    return labels


CM_PATTERN = re.compile(r"([\d.]+) 0 0 1 ([\d.]+) ([\d.]+) cm")
"""Matches both `1 0 0 1 x y cm` and `0.97... 0 0 1 x y cm` (scaled underlines in NL)."""


def detect_emp1_x_range(content: str) -> tuple[float, float]:
    """Auto-detect the X range for Emp1 underlines by finding the most common X."""
    xs = []
    for m in CM_PATTERN.finditer(content):
        _scale, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if 130 < x < 160 and y < 250 and y > 20:
            xs.append(round(x))
    if not xs:
        return (150, 155)
    from collections import Counter

    most_common_x = Counter(xs).most_common(1)[0][0]
    return (most_common_x - 2, most_common_x + 3)


def find_underline_gap_near(content: str, y_target: float, emp1_x_range: tuple[float, float] = (150, 155)) -> float:
    """Find the gap between the underline at y_target and the one just below it.

    Underline Y is typically 8-15pt below the text label Y. We find the
    Emp1-side underline closest to y_target (within 15pt below) and return
    the gap to the next underline below it.
    """
    ys = []
    for m in CM_PATTERN.finditer(content):
        _scale, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if emp1_x_range[0] < x < emp1_x_range[1] and y < 250:
            ys.append(y)
    ys.sort(reverse=True)
    for i in range(len(ys) - 1):
        if abs(ys[i] - y_target) < 15:
            gap = ys[i] - ys[i + 1]
            if 10 < gap < 25:
                return round(gap, 1)
    return 14.0  # safe default


def find_after_row_underline_block(
    data: str, after_y: float, emp1_x_range: tuple[float, float] = (150, 155)
) -> tuple[str, float] | None:
    """Find the underline+EUR block for the 'after' row (FR-style contiguous block).

    Returns (block_text, underline_y) or None.

    Works for FR where Emp1 underline → Emp1 EUR → Emp2 underline → Emp2 EUR
    are in one contiguous block. Returns None for NL/EN where underlines and
    EUR labels are scattered (those use the individual-shift fallback).
    """
    # Find Emp1 underline cm closest to after_y (within 15pt below label)
    best_match = None
    best_dist = 999
    for m in CM_PATTERN.finditer(data):
        scale, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
        if emp1_x_range[0] < x < emp1_x_range[1]:
            dist = after_y - y
            if 0 < dist < 15 and dist < best_dist:
                best_dist = dist
                best_match = (m.start(), y, scale)

    if not best_match:
        return None

    cm_pos, underline_y, cm_scale = best_match

    # For NL-style (scaled cm, non-contiguous layout), skip block replacement
    # NL has underlines grouped separately from EUR labels — block approach won't work
    if cm_scale < 0.999:
        return None

    # Search backward from cm for block start (look for 'q' line)
    search_back = data[max(0, cm_pos - 200) : cm_pos]
    q_pos = search_back.rfind("\nq\n")
    if q_pos < 0:
        q_pos = search_back.rfind("q\n")
        block_start = max(0, cm_pos - 200) + q_pos
    else:
        block_start = max(0, cm_pos - 200) + q_pos + 1  # skip the leading \n

    # Search forward for the end: we need the ET after the Emp2 EUR
    # Pattern: after Emp1 underline+EUR, there's Emp2 underline+EUR ending with ET
    remaining = data[cm_pos:]
    et_pos = 0
    # The block has 2 BT/ET pairs (Emp1 EUR + Emp2 EUR), sometimes with Emp2 having
    # split Tj for individual EUR chars. Find the 2nd ET.
    for et_idx, m in enumerate(re.finditer(r"\nET\n", remaining), 1):
        if et_idx >= 2:
            et_pos = cm_pos + m.end()
            break

    if et_pos == 0:
        # Fallback: find at least one ET
        m = re.search(r"\nET\n", remaining)
        if m:
            et_pos = cm_pos + m.end()
        else:
            return None

    block = data[block_start:et_pos].rstrip("\n")
    return block, underline_y


# ---------------------------------------------------------------------------
# Form fields
# ---------------------------------------------------------------------------


def make_text_field(writer: pypdf.PdfWriter, name: str, x1: float, y1: float, x2: float, y2: float) -> DictionaryObject:
    w, h = x2 - x1, y2 - y1
    ap = DecodedStreamObject()
    ap.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                [NumberObject(0), NumberObject(0), NumberObject(int(w)), NumberObject(int(h))]
            ),
        }
    )
    ap.set_data(f"0.85 0.85 0.95 rg\n0 0 {w} {h} re f\n".encode())
    fd = DictionaryObject()
    fd.update(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Widget"),
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject(name),
            NameObject("/V"): TextStringObject(""),
            NameObject("/Rect"): ArrayObject([FloatObject(x1), FloatObject(y1), FloatObject(x2), FloatObject(y2)]),
            NameObject("/F"): NumberObject(4),
            NameObject("/Ff"): NumberObject(0),
            NameObject("/DA"): TextStringObject("/Helv 10 Tf 0 g"),
            NameObject("/AP"): DictionaryObject({NameObject("/N"): writer._add_object(ap)}),
        }
    )
    return fd


# ---------------------------------------------------------------------------
# Core edit logic
# ---------------------------------------------------------------------------


def edit_pdf(
    reader: pypdf.PdfReader,
    page_index: int,
    field_name: str,
    label_text: str,
    insert_after: str,
    capitalize_after: bool,
    borrower_prefix: str,
) -> pypdf.PdfWriter:
    page_r = reader.pages[page_index]
    fonts = extract_font_maps(page_r)
    content = page_r.get_contents().get_data().decode("latin-1")
    lines = content.split("\n")
    labels = find_labels_in_income_section(lines, fonts)

    typer.echo("Income labels found:")
    for lb in labels:
        if lb.y_approx < 300:
            typer.echo(f'  [{lb.font_name}] y={lb.y_approx:.1f}: "{lb.decoded}"')

    # Find insert-after label — prefer longest match (handles split labels)
    after = None
    ia_lower = insert_after.lower()
    best_score = 0
    for lb in labels:
        dec = lb.decoded.lower().strip()
        if ia_lower in dec:
            score = len(ia_lower)
        elif dec in ia_lower and len(dec) >= 4:
            score = len(dec)
        else:
            continue
        if score > best_score:
            best_score = score
            after = lb
    if not after:
        msg = f"Label '{insert_after}' not found. Available: {[lb.decoded for lb in labels]}"
        raise typer.BadParameter(msg)

    # Find the label below
    below = None
    for lb in labels:
        if lb.line_idx > after.line_idx and lb.y_approx < after.y_approx:
            below = lb
            break
    if not below:
        msg = "No label found below insertion point"
        raise typer.Abort(msg)

    typer.echo(f"Insert after: '{after.decoded}' (line {after.line_idx}, y≈{after.y_approx:.1f})")
    typer.echo(f"Shift from:   '{below.decoded}' (line {below.line_idx}, y≈{below.y_approx:.1f})")

    # Auto-detect Emp1 underline X range (varies by language: FR≈152, NL≈138)
    emp1_xr = detect_emp1_x_range(content)
    typer.echo(f"Emp1 underline X range: {emp1_xr}")

    # Compute shift from actual underline spacing (more accurate than TD value)
    shift = find_underline_gap_near(content, after.y_approx, emp1_xr)
    typer.echo(f"Shift amount: {shift}pt (from underline gap analysis)")

    # Row height for TD (text leading between labels)
    row_height = 13.5
    for i in range(after.line_idx, below.line_idx):
        m = re.match(r"\s*[\d.\-]+\s+([\d.\-]+)\s+T[dD]\s*$", lines[i])
        if m:
            row_height = abs(float(m.group(1)))
            break

    # Find font for new label (try progressively simplified versions)
    label_font = find_best_font(fonts, label_text)
    if not label_font:
        # Try common substitutions for characters not in font subsets
        subs = [
            ("'", " "),
            ("\u2019", " "),
            ("é", "e"),
            ("è", "e"),
            ("ê", "e"),
            ("à", "a"),
            ("â", "a"),
            ("ù", "u"),
            ("û", "u"),
            ("ô", "o"),
            ("ç", "c"),
            ("ë", "e"),
            ("ï", "i"),
            ("ü", "u"),
        ]
        alt = label_text
        for old_ch, new_ch in subs:
            alt = alt.replace(old_ch, new_ch)
        label_font = find_best_font(fonts, alt)
        if label_font:
            label_text = alt
            typer.echo(f"Simplified label for font: '{label_text}'")
        else:
            msg = f"No font can encode '{label_text}'"
            raise typer.BadParameter(msg)

    typer.echo(f"Label font: {label_font.name} ({label_font.base_font})")
    new_hex = label_font.encode_hex(label_text)

    # Capitalize the insert-after label
    after_hex = after.hex_string
    after_font = after.font_name
    if capitalize_after:
        first_glyph = after_hex[:4]
        first_char = fonts[after.font_name].glyph_to_char.get(first_glyph.upper(), "")
        if first_char.islower():
            uc = first_char.upper()
            ug = fonts[after.font_name].char_to_glyph.get(uc)
            if ug:
                # Same font has uppercase — just replace first glyph
                after_hex = ug + after_hex[4:]
                typer.echo(f"Capitalized: '{first_char}' → '{uc}' (same font)")
            else:
                # Need different font — must re-encode ENTIRE label to avoid glyph mismatch
                full_decoded = decode_hex(after.hex_string, fonts[after.font_name])
                full_uc = uc + full_decoded[1:]
                if label_font.can_encode(full_uc):
                    after_hex = label_font.encode_hex(full_uc).strip("<>")
                    after_font = label_font.name
                    typer.echo(f"Capitalized: '{first_char}' → '{uc}' (re-encoded in {label_font.name})")
                else:
                    typer.echo(f"Warning: cannot capitalize '{first_char}' — no font has all glyphs")

    # --- Build the block replacement for the label insertion ---
    # Original: <afterHex>Tj\n...(between)...\n<belowHex>Tj
    # New:      <afterHex>Tj\n/Font Tf\n0 -H TD\n<newHex>Tj\n...(between)...\n<belowHex>Tj

    old_block = "\n".join(lines[after.line_idx : below.line_idx + 1])
    between = lines[after.line_idx + 1 : below.line_idx]

    new_block_lines = []
    # After label (possibly with new hex for capitalization)
    after_line = lines[after.line_idx]
    if after_hex != after.hex_string:
        after_line = after_line.replace(f"<{after.hex_string}>", f"<{after_hex}>")
    new_block_lines.extend(
        [
            after_line,
            f"{label_font.name} 9 Tf",
            f"0 -{row_height} TD",
            f"{new_hex}Tj",
        ]
    )
    # Restore original font if different from new label font
    if label_font.name != after.font_name:
        # Find the font size from the original after label's Tf line
        orig_size = 8  # default
        for j in range(after.line_idx - 1, max(after.line_idx - 10, 0), -1):
            m = re.match(r"\s*" + re.escape(after.font_name) + r"\s+(\d+)\s+Tf", lines[j].strip())
            if m:
                orig_size = int(m.group(1))
                break
        new_block_lines.append(f"{after.font_name} {orig_size} Tf")
    # Original between + below label
    new_block_lines.extend(between)
    new_block_lines.append(lines[below.line_idx])

    new_block = "\n".join(new_block_lines)

    # Also handle font switch for capitalization (the Tf line BEFORE the after label)
    font_switch = None
    if after_font != after.font_name:
        for j in range(after.line_idx - 1, max(after.line_idx - 5, 0), -1):
            if re.match(r"\s*" + re.escape(after.font_name) + r"\s+\d+\s+Tf", lines[j].strip()):
                font_switch = (lines[j].strip(), f"{after_font} 9 Tf")
                break

    # --- Apply changes to writer's content stream ---
    writer = pypdf.PdfWriter(clone_from=reader)
    page = writer.pages[page_index]
    contents = page["/Contents"]

    if isinstance(contents, ArrayObject):
        all_data = b""
        for ref in contents:
            all_data += ref.get_object().get_data()
        data = all_data.decode("latin-1")
        first_stream = contents[0].get_object()
    else:
        first_stream = contents.get_object()
        data = first_stream.get_data().decode("latin-1")

    # 1. Block replacement for label insertion (text labels at left margin)
    assert old_block in data, "Label block not found in content stream"
    data = data.replace(old_block, new_block, 1)

    # 2. Font switch for capitalization (positional, not global)
    if font_switch:
        idx = data.index(f"<{after_hex}>Tj") if after_hex != after.hex_string else data.index(f"<{after.hex_string}>Tj")
        before_label = data[:idx]
        last_font_pos = before_label.rfind(font_switch[0])
        if last_font_pos >= 0:
            data = data[:last_font_pos] + font_switch[1] + data[last_font_pos + len(font_switch[0]) :]

    # 3. Block replacement for the after row's underline+EUR
    #    Strategy A (FR-style): contiguous block of Emp1 ul+EUR + Emp2 ul+EUR → replace
    #    Strategy B (NL-style): scattered underlines and EUR → shift individually + insert
    block_result = find_after_row_underline_block(data, after.y_approx, emp1_xr)
    if block_result:
        old_ul_block, after_ul_y = block_result
        typer.echo(f"Found contiguous underline+EUR block (underline y={after_ul_y:.1f})")

        # Create shifted version of the block (shift all Y coordinates down)
        shifted_block = old_ul_block
        for m in re.finditer(r"(1 0 0 1 [\d.]+ )([\d.]+)( cm)", old_ul_block):
            old_y = float(m.group(2))
            new_y = old_y - shift
            shifted_block = shifted_block.replace(m.group(0), f"{m.group(1)}{new_y:.7f}{m.group(3)}", 1)
        for m in re.finditer(r"([\d.]+) ([\d.]+) Td", old_ul_block):
            x_val, y_val = float(m.group(1)), float(m.group(2))
            if (320 < x_val < 340 or 525 < x_val < 545) or (y_val > 50 and x_val > 300):
                new_y = y_val - shift
                shifted_block = shifted_block.replace(
                    f"{m.group(1)} {m.group(2)} Td", f"{m.group(1)} {new_y:.3f} Td", 1
                )
        for m in re.finditer(r"(1 0 0 1 [\d.]+ )([\d.]+)( Tm)", old_ul_block):
            old_y = float(m.group(2))
            new_y = old_y - shift
            shifted_block = shifted_block.replace(m.group(0), f"{m.group(1)}{new_y:.4f}{m.group(3)}", 1)

        # Build new row's underline+EUR content
        emp1_ux = emp2_ux = ul_w = None
        for m in re.finditer(r"1 0 0 1 ([\d.]+) [\d.]+ cm", old_ul_block):
            x = float(m.group(1))
            if emp1_xr[0] - 5 < x < emp1_xr[1] + 5 and emp1_ux is None:
                emp1_ux = x
            elif 355 < x < 370 and emp2_ux is None:
                emp2_ux = x
        for m in re.finditer(r"([\d.]+) 0 l", old_ul_block):
            w = float(m.group(1))
            if 170 < w < 180:
                ul_w = w
                break

        emp1_eur_td = emp2_eur_td = None
        for m in re.finditer(r"([\d.]+) ([\d.]+) Td", old_ul_block):
            x = float(m.group(1))
            if 320 < x < 340 and emp1_eur_td is None:
                emp1_eur_td = (x, float(m.group(2)))
            elif 525 < x < 545 and emp2_eur_td is None:
                emp2_eur_td = (x, float(m.group(2)))

        emp1_ux = emp1_ux or 152.07
        emp2_ux = emp2_ux or 359.72
        ul_w = ul_w or 173.258

        new_ul_y = after_ul_y + 0.6  # slight offset like proven script

        eur_font = "/C2_0"
        eur_m = re.search(r"/(C2_\d+)\s+\d+\s+Tf", old_ul_block)
        if eur_m:
            eur_font = "/" + eur_m.group(1)

        new_row_block = f"""
0.817 0.816 0.815  SCN
11.3 w
/GS0 gs
q
1 0 0 1 {emp1_ux} {new_ul_y:.7f} cm
0 0 m
{ul_w} 0 l
S
Q
q
1 0 0 1 {emp2_ux} {new_ul_y:.7f} cm
0 0 m
{ul_w} 0 l
S
Q"""

        if emp1_eur_td:
            new_row_block += f"""
BT
/GS1 gs
{eur_font} 9 Tf
0.009 Tc 0.054 Tw {emp1_eur_td[0]} {emp1_eur_td[1]:.3f} Td
[<0003>-6 <002600360033>]TJ
ET"""

        if emp2_eur_td:
            has_split = "<0003>Tj" in old_ul_block and "0 Tw 2.565 0 Td" in old_ul_block
            if has_split:
                emp2_tms = []
                for m in re.finditer(r"1 0 0 1 ([\d.]+) ([\d.]+) Tm", old_ul_block):
                    x = float(m.group(1))
                    if x > 530:
                        emp2_tms.append((x, float(m.group(2))))
                new_row_block += f"""
BT
/GS1 gs
{eur_font} 9 Tf
0.009 Tc {emp2_eur_td[0]} {emp2_eur_td[1]:.3f} Td
<0003>Tj
0 Tw 2.565 0 Td
<0026>Tj"""
                for x, y in emp2_tms:
                    glyph = "<0036>" if emp2_tms.index((x, y)) == 0 else "<0033>"
                    new_row_block += f"\n1 0 0 1 {x:.4f} {y:.4f} Tm\n{glyph}Tj"
                new_row_block += "\nET"
            else:
                new_row_block += f"""
BT
/GS1 gs
{eur_font} 9 Tf
0.009 Tc 0.054 Tw {emp2_eur_td[0]} {emp2_eur_td[1]:.3f} Td
[<0003>-6 <002600360033>]TJ
ET"""

        replacement = shifted_block + "\n" + new_row_block.strip()

        block_idx = data.index(old_ul_block)
        before_block = data[:block_idx]
        after_block = data[block_idx + len(old_ul_block) :]

        # Find the lowest absolute Y in the old block to set the shift threshold
        block_ys = []
        for m in re.finditer(r"([\d.]+)\s+([\d.]+)\s+Td", old_ul_block):
            x, y = float(m.group(1)), float(m.group(2))
            if x > 100 and y > 10:
                block_ys.append(y)
        block_ys.extend(float(m.group(3)) for m in CM_PATTERN.finditer(old_ul_block))
        block_ys.extend(float(m.group(1)) for m in re.finditer(r"1 0 0 1 [\d.]+ ([\d.]+) Tm", old_ul_block))
        low_threshold = min(block_ys) - 5 if block_ys else after.y_approx - 25

    else:
        # Strategy B: NL-style — scattered underlines/EUR, no contiguous block.
        # Find the underline Y for the after row from the scaled cm pattern.
        # In NL, the underline can be ABOVE the label Y (larger Y = higher on page).
        after_ul_y = None
        best_ul_dist = 999
        for m in CM_PATTERN.finditer(data):
            _scale, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if emp1_xr[0] - 5 < x < emp1_xr[1] + 5:
                dist = abs(after.y_approx - y)
                if dist < 15 and dist < best_ul_dist:
                    best_ul_dist = dist
                    after_ul_y = y

        typer.echo("Using individual-shift strategy (NL/EN style)")
        if after_ul_y:
            typer.echo(f"After row underline Y: {after_ul_y:.1f}")

        before_block = data
        after_block = ""
        replacement = ""
        # Threshold: shift the "below" row and everything under it.
        # Must be above below's underline Y but below after's label Y.
        # Use midpoint between after and below labels to avoid shifting after row.
        low_threshold = (after.y_approx + below.y_approx) / 2
        typer.echo(
            f"Shift threshold: {low_threshold:.1f}"
            f" (between '{after.decoded}' y={after.y_approx:.1f} and '{below.decoded}' y={below.y_approx:.1f})"
        )

    # 4. Shift remaining content (outside the block) below the after row
    def shift_low_cm(m: re.Match[str]) -> str:
        """Shift cm positions (both 1 0 0 1 and scaled) below threshold."""
        full = m.group(0)
        scale, x_str, y_str = m.group(1), m.group(2), m.group(3)
        y = float(y_str)
        x = float(x_str)
        if y < low_threshold and y > 5.0:
            # Only shift underlines in income area (Emp1 or Emp2 x ranges)
            if (emp1_xr[0] - 5 < x < emp1_xr[1] + 5) or (350 < x < 370):
                return f"{scale} 0 0 1 {x_str} {y - shift:.7f} cm"
            # Also shift Vaste kosten underlines (x≈137-153, y<90)
            if 130 < x < 160 and y < 90:
                return f"{scale} 0 0 1 {x_str} {y - shift:.7f} cm"
        return full

    def shift_low_td(m: re.Match[str]) -> str:
        full = m.group(0)
        x, y = float(m.group(1)), float(m.group(2))
        if y < low_threshold and y > 5.0 and (320 < x < 345 or 525 < x < 550):
            new_y = y - shift
            return full.replace(m.group(2), f"{new_y:.3f}", 1)
        return full

    def shift_low_tm(m: re.Match[str]) -> str:
        full = m.group(0)
        prefix, y_str, suffix = m.group(1), m.group(2), m.group(3)
        y = float(y_str)
        if y < low_threshold and y > 5.0:
            x_m = re.search(r"([\d.]+)\s*$", prefix.strip())
            if x_m:
                x = float(x_m.group(1))
                if x < 100 or x > 330:
                    return f"{prefix}{y - shift:.4f}{suffix}"
        return full

    before_block = re.sub(CM_PATTERN, shift_low_cm, before_block)
    before_block = re.sub(r"([\d.]+)\s+([\d.]+)\s+Td", shift_low_td, before_block)
    before_block = re.sub(r"(1 0 0 1 [\d.]+ )([\d.]+)( Tm)", shift_low_tm, before_block)

    after_block = re.sub(CM_PATTERN, shift_low_cm, after_block)
    after_block = re.sub(r"([\d.]+)\s+([\d.]+)\s+Td", shift_low_td, after_block)
    after_block = re.sub(r"(1 0 0 1 [\d.]+ )([\d.]+)( Tm)", shift_low_tm, after_block)

    # Reassemble
    data = before_block + replacement + after_block

    # 5. For NL-style: insert new underlines and EUR labels
    if not block_result:
        # Detect underline geometry from existing ones
        ul_scale = "1"
        ul_w = 173.258
        emp1_ux = emp2_ux = None
        for m in CM_PATTERN.finditer(data):
            _sc, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if emp1_xr[0] - 5 < x < emp1_xr[1] + 5 and y < 250 and y > 20 and emp1_ux is None:
                emp1_ux = x
                ul_scale = m.group(1)
            if 350 < x < 370 and y < 250 and y > 20 and emp2_ux is None:
                emp2_ux = x
        emp1_ux = emp1_ux or 142.385
        emp2_ux = emp2_ux or 358.385

        # New underline Y: between after row underline and shifted below row underline.
        # In NL, underlines are typically 3pt above the label Y.
        # Place new underline at after_ul_y - shift/2 (midpoint)
        if after_ul_y:
            # Find the below-row underline Y (should be near after_ul_y - gap)
            below_ul_y = None
            for m in CM_PATTERN.finditer(data):
                _sc, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
                if emp1_xr[0] - 5 < x < emp1_xr[1] + 5 and after_ul_y - 40 < y < after_ul_y - 10:
                    below_ul_y = y
                    break
            # New underline between after_ul_y and below_ul_y
            new_ul_y = (after_ul_y + (below_ul_y or after_ul_y - shift)) / 2
        else:
            new_ul_y = after.y_approx - 5.0

        typer.echo(f"New underline Y: {new_ul_y:.1f}")

        # Find where to insert — right after the after-row's Emp1 underline Q
        insert_ul_pos = None
        for m in CM_PATTERN.finditer(data):
            _sc, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if emp1_xr[0] - 5 < x < emp1_xr[1] + 5 and after_ul_y and abs(y - after_ul_y) < 1:
                search_after = data[m.end() : m.end() + 100]
                q_match = re.search(r"\nQ\n", search_after)
                if q_match:
                    insert_ul_pos = m.end() + q_match.end() - 1
                    break

        if insert_ul_pos:
            new_underlines = f"""q
{ul_scale} 0 0 1 {emp1_ux} {new_ul_y:.7f} cm
0 0 m
{ul_w} 0 l
S
Q"""
            data = data[:insert_ul_pos] + "\n" + new_underlines + data[insert_ul_pos:]
            typer.echo(f"Inserted Emp1 underline at y={new_ul_y:.1f}")

        # Emp2 underline
        insert_ul2_pos = None
        for m in CM_PATTERN.finditer(data):
            _sc, x, y = float(m.group(1)), float(m.group(2)), float(m.group(3))
            if 350 < x < 370 and after_ul_y and abs(y - after_ul_y) < 1:
                search_after = data[m.end() : m.end() + 100]
                q_match = re.search(r"\nQ\n", search_after)
                if q_match:
                    insert_ul2_pos = m.end() + q_match.end() - 1
                    break

        if insert_ul2_pos:
            new_underlines2 = f"""q
{ul_scale} 0 0 1 {emp2_ux} {new_ul_y:.7f} cm
0 0 m
{ul_w} 0 l
S
Q"""
            data = data[:insert_ul2_pos] + "\n" + new_underlines2 + data[insert_ul2_pos:]
            typer.echo(f"Inserted Emp2 underline at y={new_ul_y:.1f}")

        # Insert EUR labels for the new row
        # Detect EUR X positions
        emp1_eur_x = emp2_eur_x = None
        for m in re.finditer(r"([\d.]+)\s+([\d.]+)\s+Td", data):
            x, y = float(m.group(1)), float(m.group(2))
            if abs(y - after.y_approx) < 15:
                if 310 < x < 345 and emp1_eur_x is None:
                    emp1_eur_x = x
                elif 525 < x < 550 and emp2_eur_x is None:
                    emp2_eur_x = x
        emp1_eur_x = emp1_eur_x or 323.647
        emp2_eur_x = emp2_eur_x or 536.647

        eur_y = new_ul_y - 5.0

        # Find the after-row's Emp1 EUR (unshifted) and insert new EUR after it
        for m in re.finditer(rf"({re.escape(str(emp1_eur_x))})\s+([\d.]+)\s+Td", data):
            y = float(m.group(2))
            if abs(y - after.y_approx) < 5:  # after row's EUR (not shifted)
                et_after = data.find("\nET\n", m.end())
                if et_after > 0:
                    insert_eur_pos = et_after + 4
                    new_eur_block = f"""BT
/GS1 gs
{emp1_eur_x} {eur_y:.3f} Td
<002600360033>Tj
ET
"""
                    data = data[:insert_eur_pos] + new_eur_block + data[insert_eur_pos:]
                    typer.echo(f"Inserted Emp1 EUR at y={eur_y:.1f}")
                break

        # Emp2 EUR
        for m in re.finditer(rf"({re.escape(str(emp2_eur_x))})\s+([\d.]+)\s+Td", data):
            y = float(m.group(2))
            if abs(y - after.y_approx) < 5:
                et_after2 = data.find("\nET\n", m.end())
                if et_after2 > 0:
                    insert_eur2_pos = et_after2 + 4
                    new_eur2_block = f"""BT
/GS1 gs
{emp2_eur_x} {eur_y:.3f} Td
<002600360033>Tj
ET
"""
                    data = data[:insert_eur2_pos] + new_eur2_block + data[insert_eur2_pos:]
                    typer.echo(f"Inserted Emp2 EUR at y={eur_y:.1f}")
                break

    # 6. Adjust the Td jump from below label to next section
    #    Only for FR-style (block replacement): the block shifts by `shift` but the
    #    label insertion uses `row_height`, creating a mismatch in the relative Td.
    #    For NL-style (individual shift): both sides shift equally, no adjustment needed.
    if block_result and abs(shift - row_height) > 0.01:
        below_hex = below.hex_string
        try:
            below_pos = data.index(f"<{below_hex}>Tj")
            search_area = data[below_pos : below_pos + 300]
            td_jump_match = re.search(r"([\d.\-]+\s+Tc\s+\d+\s+Tr\s+[\d.\-]+\s+)([\d.\-]+)(\s+Td)", search_area)
            if td_jump_match:
                old_dy = float(td_jump_match.group(2))
                new_dy = old_dy - (shift - row_height)
                old_td = td_jump_match.group(0)
                new_td = f"{td_jump_match.group(1)}{new_dy:.1f}{td_jump_match.group(3)}"
                data = data.replace(old_td, new_td, 1)
                typer.echo(f"Adjusted Td jump: {old_dy} → {new_dy:.1f}")
        except ValueError:
            typer.echo("Warning: could not find below label for Td adjustment")

    # Write content back
    first_stream.set_data(data.encode("latin-1"))
    if isinstance(contents, ArrayObject):
        while len(contents) > 1:
            contents.pop()

    # 7. Shift field annotations below the after row
    field_threshold = after.y_approx - 2.0
    annots = page.get("/Annots")
    annots_list = annots if isinstance(annots, ArrayObject) else annots.get_object()
    for aref in annots_list:
        a = aref.get_object()
        rect = a.get("/Rect")
        if rect:
            y1 = float(rect[1])
            if y1 < field_threshold and y1 > 10.0:
                rect[1] = FloatObject(float(rect[1]) - shift)
                rect[3] = FloatObject(float(rect[3]) - shift)

    # 8. Find field X ranges from existing fields
    emp1_fx = (152, 325)
    emp2_fx = (359, 532)
    for aref in annots_list:
        a = aref.get_object()
        rect = a.get("/Rect")
        ft = a.get("/FT")
        if rect and ft:
            x1 = float(rect[0])
            if 130 < x1 < 160:
                emp1_fx = (float(rect[0]), float(rect[2]))
            elif 350 < x1 < 370:
                emp2_fx = (float(rect[0]), float(rect[2]))

    # 9. Add new fields
    new_field_y = after_ul_y - 5.0 if after_ul_y is not None else after.y_approx - row_height
    field_h = 12
    f1 = make_text_field(
        writer, f"{borrower_prefix}/0/{field_name}", emp1_fx[0], new_field_y, emp1_fx[1], new_field_y + field_h
    )
    f2 = make_text_field(
        writer, f"{borrower_prefix}/1/{field_name}", emp2_fx[0], new_field_y, emp2_fx[1], new_field_y + field_h
    )
    f1_ref = writer._add_object(f1)
    f2_ref = writer._add_object(f2)
    annots_list.append(f1_ref)
    annots_list.append(f2_ref)

    # 10. Register fields in the AcroForm /Fields array
    acroform = writer._root_object.get("/AcroForm")
    if acroform:
        acroform_obj = acroform.get_object() if hasattr(acroform, "get_object") else acroform
        fields_arr = acroform_obj.get("/Fields")
        if fields_arr:
            fields_list = fields_arr.get_object() if hasattr(fields_arr, "get_object") else fields_arr
            fields_list.append(f1_ref)
            fields_list.append(f2_ref)

    typer.echo(f"Added fields: {borrower_prefix}/0/{field_name}, {borrower_prefix}/1/{field_name}")
    typer.echo(f"Field Y: {new_field_y:.1f}")

    return writer


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def add_field(
    pdf_path: str = typer.Argument(help="Path to the PDF template"),
    field_name: str = typer.Argument(help="AcroForm field base name"),
    label_text: str = typer.Argument(help="Static label text to display"),
    insert_after: str = typer.Option(help="Label to insert after (case-insensitive)"),
    page_index: int = typer.Option(1, help="Page index (0-based)"),
    borrower_prefix: str = typer.Option("clientsBorrower", help="Field name prefix"),
    capitalize_after: bool = typer.Option(False, help="Capitalize the insert-after label"),
    output: str | None = typer.Option(None, "-o", help="Output path (default: overwrite)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze and show plan without modifying"),
) -> None:
    """Add a field row to an AcroForm PDF template.

    Works for any section (income, charges, other costs) that uses the
    standard label + underline + EUR marker layout.
    """
    resolved = Path(pdf_path).expanduser()
    if not resolved.exists():
        typer.echo(f"Error: {resolved} not found", err=True)
        raise typer.Exit(1)

    pdf_path = str(resolved)
    reader = pypdf.PdfReader(pdf_path)
    typer.echo(f"Reading: {pdf_path} ({len(reader.pages)} pages)")

    if dry_run:
        # Dry run: just show label analysis and exit
        page_r = reader.pages[page_index]
        fonts = extract_font_maps(page_r)
        content = page_r.get_contents().get_data().decode("latin-1")
        lines = content.split("\n")
        labels = find_labels_in_income_section(lines, fonts)
        typer.echo(f"\nLabels found on page {page_index}:")
        for lb in labels:
            if lb.y_approx < 300:
                typer.echo(f'  [{lb.font_name}] y={lb.y_approx:.1f}: "{lb.decoded}"')
        ia_lower = insert_after.lower()
        best_score = 0
        after = None
        for lb in labels:
            dec = lb.decoded.lower().strip()
            if ia_lower in dec:
                score = len(ia_lower)
            elif dec in ia_lower and len(dec) >= 4:
                score = len(dec)
            else:
                continue
            if score > best_score:
                best_score = score
                after = lb
        if after:
            typer.echo(f"\nWould insert after: '{after.decoded}' (y={after.y_approx:.1f})")
            label_font = find_best_font(fonts, label_text)
            if not label_font:
                subs = [
                    ("'", " "),
                    ("\u2019", " "),
                    ("é", "e"),
                    ("è", "e"),
                    ("ê", "e"),
                    ("à", "a"),
                    ("â", "a"),
                    ("ù", "u"),
                    ("û", "u"),
                    ("ô", "o"),
                    ("ç", "c"),
                    ("ë", "e"),
                    ("ï", "i"),
                    ("ü", "u"),
                ]
                alt = label_text
                for old_ch, new_ch in subs:
                    alt = alt.replace(old_ch, new_ch)
                label_font = find_best_font(fonts, alt)
                if label_font:
                    typer.echo(f"Label would be simplified to: '{alt}'")
            if label_font:
                typer.echo(f"Font: {label_font.name} ({label_font.base_font})")
            else:
                typer.echo("WARNING: No font can encode this label")
            emp1_xr = detect_emp1_x_range(content)
            shift = find_underline_gap_near(content, after.y_approx, emp1_xr)
            typer.echo(f"Shift: {shift}pt, Emp1 X range: {emp1_xr}")
        else:
            typer.echo(f"\nWARNING: Label '{insert_after}' not found")
        return

    output_path = output or pdf_path
    Path(output_path).resolve().parent.mkdir(exist_ok=True, parents=True)

    writer = edit_pdf(reader, page_index, field_name, label_text, insert_after, capitalize_after, borrower_prefix)

    with Path(output_path).open("wb") as f:
        writer.write(f)

    # Verify
    vr = pypdf.PdfReader(output_path)
    fields = vr.get_fields() or {}
    matching = [n for n in fields if field_name in n]
    typer.echo(f"\nWritten: {output_path} ({Path(output_path).stat().st_size} bytes)")
    typer.echo(f"Verified fields: {matching}")
    typer.echo(f"Pages: {len(vr.pages)}")
