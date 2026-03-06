---
name: ac-generating-slides
description: Generates presentation slides from Markdown using Marp. Use when user says "slides", "presentation", "deck", "marp", or wants to create/update a slide deck.
compatibility: macOS/Linux, requires Marp CLI and a Chromium-based browser (Chrome, Brave, Edge, Chromium).
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Generate Slides

## Dependencies

Standalone. No dependencies on other skills.

Create polished presentation decks from Markdown using [Marp](https://marp.app/).

## Prerequisites

- **Marp CLI** installed (`brew install marp-cli` or `npm install -g @marp-team/marp-cli`)
- **Chromium-based browser** available (Chrome, Brave, Edge, or Chromium) for PDF export

## Workflow

### 0. Check for Branding Skill

Before creating slides, check if the user has a branding skill configured:

1. Check the agent's memory/config for a stored branding skill path (e.g., a "default branding skill" preference).
2. If found, load it and use the brand colors, fonts, logo, and tone it defines.
3. If not found, **ask the user**: "Do you have a company branding guide or branding skill? If so, where is it?"
4. If the user provides one, load it and suggest they store the path in their agent's memory for future sessions.
5. If no branding skill is available, proceed with the default Marp theme.

### 1. Determine the Browser Path

Marp needs a Chromium-based browser for PDF rendering. Detect which one is available:

```bash
# Check in order of preference
for app in "Google Chrome" "Brave Browser" "Microsoft Edge" "Chromium"; do
  path="/Applications/${app}.app/Contents/MacOS/${app}"
  [ -x "$path" ] && echo "CHROME_PATH=\"$path\"" && break
done
```

On Linux, check: `which google-chrome || which chromium-browser || which brave-browser`

Store the result — you'll need it for every PDF export.

### 2. Create the Slide Deck

Write a `.md` file with Marp front matter. Always start with:

```markdown
---
marp: true
theme: default
paginate: true
style: |
  /* custom CSS here */
---
```

**Slide structure:**

- Separate slides with `---` (horizontal rule)
- Use `<!-- _class: lead -->` for title/section slides (centered, dark background)
- Use standard Markdown: `#` headings, `-` lists, `**bold**`, `>` blockquotes, tables, code blocks
- Keep each slide focused — if it feels crowded, split it

**Styling tips for professional slides:**

- Define a consistent color palette in the `style` front matter
- Use `section.lead` styles for title slides (dark background, white text)
- Style tables with colored headers
- Use `<div>` blocks with inline styles for custom layouts (layered diagrams, flow boxes, status bars)
- Keep font sizes readable: don't go below `0.75em`

### 3. Export to PDF

```bash
CHROME_PATH="<detected-path>" marp <input>.md --pdf --allow-local-files
```

The `--allow-local-files` flag is needed if the slides reference local images.

### 4. Iterate

After generating, read the PDF to visually verify the result. Fix any layout issues — common problems:

- Text overflowing the slide → reduce content or split
- Tables too wide → reduce columns or font size
- Code blocks cut off → shorten lines or reduce font size

## Reference Patterns

### Title slide (dark, centered)

```markdown
<!-- _class: lead -->

# Main Title

## Subtitle or tagline

<br>

**Speaker** — Date
```

### Flow diagram (inline boxes with arrows)

```html
<div style="text-align: center; margin: 18px 0;">
<span class="flow-box">Step 1</span>
<span class="flow-arrow">→</span>
<span class="flow-box">Step 2</span>
<span class="flow-arrow">→</span>
<span class="flow-box">Step 3</span>
</div>
```

Requires these CSS classes in the `style` front matter:

```css
.flow-box {
  display: inline-block;
  background: #eaf2f8;
  border: 2px solid #2e86c1;
  border-radius: 8px;
  padding: 6px 14px;
  margin: 3px 2px;
  font-size: 0.78em;
  font-weight: 500;
  color: #1a5276;
}
.flow-arrow {
  display: inline-block;
  color: #2e86c1;
  font-size: 1.2em;
  margin: 0 2px;
  vertical-align: middle;
}
```

### Stacked layers diagram

```html
<div style="margin: 12px 0; font-size: 0.85em;">
<div style="background: #d4efdf; border: 2px solid #27ae60; border-radius: 8px 8px 0 0; padding: 10px 16px;">
<strong style="color: #1e8449;">Top layer</strong>&emsp; description
</div>
<div style="background: #d6eaf8; border: 2px solid #2e86c1; border-top: none; padding: 10px 16px;">
<strong style="color: #1a5276;">Middle layer</strong>&emsp; description
</div>
<div style="background: #fdebd0; border: 2px solid #e67e22; border-top: none; border-radius: 0 0 8px 8px; padding: 10px 16px;">
<strong style="color: #935116;">Bottom layer</strong>&emsp; description
</div>
</div>
```

### Terminal/status bar mockup

```html
<div style="background: #1e1e1e; color: #d4d4d4; font-family: 'Menlo', monospace; font-size: 0.75em; padding: 10px 16px; border-radius: 6px; margin: 12px 0; line-height: 1.6;">
<span style="color:#569cd6;">command</span> <span style="color:#ce9178;">output</span>
</div>
```

## Style Presets

When the user doesn't specify a style, use this clean default palette:

| Element | Color |
|---|---|
| Headings | `#1a5276` (dark blue) |
| Accent | `#2e86c1` (medium blue) |
| Emphasis (bold/strong) | `#c0392b` (red) |
| Lead slide background | `#1a5276` |
| Lead subtitle | `#85c1e9` (light blue) |
| Lead emphasis | `#f5b041` (gold) |
