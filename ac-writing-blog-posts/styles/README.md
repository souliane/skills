# styles/ — voice profiles

Voice profiles capture *how a specific author writes* (register, sentence mechanics, structure, dos and don'ts), derived from real samples of their own writing. The skill loads one before drafting so a post sounds like the author, not like a model. See the **"Match the Author's Voice"** rule in `SKILL.md`.

## Where the skill looks

The skill reads profiles from the directory set as `styles_dir` in `~/.ac-writing-blog-posts.yml`. Point it anywhere — a common choice is your dotfiles repo, so personal voices stay private and version-controlled instead of living in this public skill. **If `styles_dir` is unset, this bundled `styles/` directory is the fallback.**

## File convention (three layers)

- The **skill** holds the universal rules (humble, honest, straight, sound-human, off-by-default) — they apply to everyone and are never repeated in a profile.
- `<author>.md` — the author's **base voice**: traits common to all their voices.
- `<author>-<voice>.md` — optional **variants** for a topic or audience, holding **only the deltas** on top of the base.

## Privacy

A profile records writing *mechanics* only — never the author's private life, emotions, or opinions, even when those appear in the source samples. Encode the *how*, never the *what*; when unsure, ask the author.
