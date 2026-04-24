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

### 1. Interactive Authoring Dialogue (Non-Negotiable)

A deck is the user's talk — not yours. Slide creation runs as a conversation where **the user drives intent, arc, and voice, and you formalize by proposing the actual words that will appear on each slide**. Never assemble a full deck from a single upfront prompt — that produces decks that don't sound like the user and don't carry their argument.

**Rules of the dialogue**

- **One question per turn.** Ask exactly one question, wait for the answer, then ask the next. Each answer changes what the next question should be — you cannot know the right next question until the prior answer lands. Never batch.
- **Every question has 4 to 8 options.** Always a numbered menu, tailored to the conversation so far. Options must span a real range, not near-duplicates. The last option is always "none of these — I'll describe it myself".
- **Always run this dialogue.** Run it for every deck. Only skip if the user explicitly says something like "skip the dialogue, just assemble it".
- **Suggest the actual words on the slide.** For slide-level turns, propose 4-8 variants of the *literal text* that will appear on the slide (headline + bullets / paragraph / caption). Not outlines. (Blog posts propose whole paragraphs of prose; slides propose what the audience will read on screen — this is the tighter form.)
- **The user owns the argument.** You help formalize phrasing and catch inconsistencies. You do not decide the story arc, the stance, or the voice.

**If the user rejects all options in a turn**, the options missed the real axis. Do not simplify to a binary, and do not re-paraphrase the same set. Ask what dimension was missed, then regenerate along that dimension.

#### Phase A — Intent & frame

One turn per bullet, in this order:

- **What the talk *does* for the audience** (introduces a tool, walks through a technique, reports on an experiment, argues a position, compares approaches, recounts a failure, demos a workflow, retrospective, etc.).
- **Audience** (peers at a meetup, internal team, conference track, mixed skill levels with a primary target, decision-makers, a named community, etc.).
- **Duration.** Default to **5-minute lightning talk** unless the user indicates otherwise — offer 5 min / 10 min / 15-20 min / 30+ min / keynote / other. The duration caps the slide count: roughly 1 slide per minute for lightning and short talks, slower for longer formats.
- **User's stance on the topic** (enthusiast / cautious / critical / undecided / curious observer / ambivalent / other).
- **Tone calibration** (serious-technical, warm-personal, playful, dry-and-factual, polemical, reflective, etc.).
- **The single line the audience should walk away with**: generate 4-8 candidate one-sentence takeaways built from the prior answers. User picks or reshapes.

Before Phase A, check the agent's memory for stored speaker / style preferences and ask only for what's missing. Save new answers as `user` type memories so the next deck can reuse them.

#### Phase B — Arc

One turn per bullet:

- **Slide-by-slide outline**: offer 4-8 *full outlines*, each a numbered list of slide titles with a one-line description of what goes on each slide. Each outline embodies a real narrative choice (chronological / problem-then-solution / thesis-and-evidence / before-and-after / live-demo walkthrough / Q&A structure / story arc with reveal / rapid-fire tips, etc.). Slide count should match the chosen duration (5-min ≈ 5-8 slides; 20-min ≈ 12-20 slides).
- **Deck title**: 4-8 title candidates derived from the chosen outline and takeaway sentence.
- **Opening slide (the lead)**: 4-8 actual lead-slide texts (title + subtitle + speaker line), not outlines.

#### Phase C — Slide by slide

For each slide in the chosen outline:

1. Restate the slide's job in one sentence (from the outline).
2. Offer 4-8 variants of the **actual slide content** — headline plus bullets or paragraph or caption, exactly as it will appear on screen. Variants must span real angles (headline-as-claim vs. question vs. number; dense-bullets vs. one-line-plus-image; screenshot vs. code block vs. flow diagram). For image-heavy slides, propose which image plus the accompanying text.
3. User picks, edits inline, asks for more variants, or asks you to merge two. Iterate until they accept.
4. Move to the next slide.

When every slide is accepted, assemble the deck using the Marp patterns in the sections below.

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

### 3. Embedding Images

**Never embed large images as base64 in the Marp source file.** Images over ~100KB as base64 cause Marp's browser navigation to time out (30s limit).

**Do this instead:**

1. Copy the image into the same folder as the `.md` file
2. Reference it by relative path: `![h:400](screenshot.png)` (use Marp native syntax, not `<img>` tags)
3. The render script already passes `--allow-local-files` so local paths work

**When base64 is acceptable:** small icons or logos under ~30KB that are already embedded as SVG strings in the CSS.

### 3b. Image Sizing (Non-Negotiable)

**Inline CSS `height`/`max-height` on `<img>` tags does NOT work in Marp.** Marp overrides inline styles on images. Always use Marp's native image sizing syntax:

```markdown
![h:400](image.png)           <!-- fixed height -->
![w:600](image.png)           <!-- fixed width -->
![h:400 w:600](image.png)    <!-- both -->
```

Never use `<img style="height:...">` or `<div style="max-height:...">` — they will be ignored.

### 3c. Column Layouts

**Inline flexbox `<div>` blocks do NOT produce columns in Marp** — Marp wraps markdown content in `<p>` tags that break flex children. Use **scoped CSS grid** instead:

```markdown
<style scoped>
section { display: grid; grid-template-columns: 40% 58%; gap: 2%; align-items: center; }
</style>

<div>
Left column content (text, bullets)
</div>

<div>

![h:600](screenshot.png)

</div>
```

**`![bg right:50%]()` can also work** but may render incorrectly with local files or produce black bars. Prefer the scoped grid approach for reliable results.

### 3d. Lead Slides and Bold Text

On `section.lead` slides, `strong` inherits the default color which may be invisible against the dark background. Always add this to the global style:

```css
section.lead strong { color: #fff; }
```

### 4. Export to PDF

```bash
./ac-generating-slides/scripts/cli.py slides.md
./ac-generating-slides/scripts/cli.py slides.md --open    # render and open
./ac-generating-slides/scripts/cli.py slides.md -o out.pdf
```

The script auto-detects a Chromium browser (Chrome, Brave, Edge, Chromium) on macOS and Linux, sets `CHROME_PATH`, and calls `marp --pdf --allow-local-files`.

### 5. Iterate

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
