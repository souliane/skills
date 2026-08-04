# Contributor Guidelines

## Repo Structure

```text
ac-*/SKILL.md          Skill definitions
ac-*/references/       Skill-specific reference docs (one level deep)
ac-*/scripts/          Skill-specific scripts
scripts/               Shared repo-level scripts and hooks
tests/                 Tests for scripts
```

## Skill Files

- `SKILL.md` is the entry point. Keep it focused on workflow and rules.
- Move detailed content to `references/` — one level deep only.
- Set `metadata.version` manually and bump it when a skill changes materially; there is no automation that manages it.
- Skill naming: gerund form with `ac-` prefix (e.g., `ac-editing-acroforms`, `ac-adopting-ruff`). Domain skills keep plain names (`ac-django`, `ac-python`).

## Python Scripts

All scripts must follow these conventions:

1. **uv shebang:** `#!/usr/bin/env -S uv run --script`
2. **Inline metadata:** `# /// script` block with `dependencies` list (even if empty)
3. **Typer for CLI:** `typer>=0.12` in inline deps — no raw `sys.argv` or `argparse`
4. **Type annotations:** `ty-check` runs on all files — use `str | None` not `Optional[str]`
5. **4-space indentation** everywhere (matches `.editorconfig`)
6. **Make executable:** `chmod +x` the script file
7. **One exit mechanism per entry-point style.** A Typer command body (and anything it
   calls) ends on `raise typer.Exit(<code>)`; a plain `main() -> int` hook ends on
   `raise SystemExit(main(...))` under `if __name__ == "__main__"`. Never a bare
   `sys.exit()` inside command code, and never `SystemExit("a message")` — a string
   raise makes every failure exit 1, so a caller cannot tell a malformed spec from a
   failed check. Give each failure class its own code (see
   `ac-editing-acroforms/scripts/acroform_errors.py`).

**One runnable entry point per skill.** A skill's `scripts/cli.py` owns the Typer app
and the whole command surface. Sibling modules hold command bodies but declare no app
of their own and run nothing on import, so there is exactly one thing to document and
exactly one thing to keep working. Only the entry point needs the shebang, the inline
metadata, and the executable bit — and every doc line that tells the reader to
execute a script (`./<skill>/scripts/cli.py ...`) must name one
(`tests/test_documented_scripts.py` enforces it).

## Testing

- Run: `uv run pytest`
- Pre-commit: `prek run --all-files`
- Frontmatter validation: `uv run ac-reviewing-codebase/scripts/cli.py check`

## Skill Design Principles

- **Default to maximum security.** When a skill presents options with security implications (server hardening, auth methods, sandboxing, encryption), always present the most secure option as the default. If a security measure doesn't fit the user's situation (e.g., RAM constraints, no use case), explicitly explain why you're suggesting to disable it, what risk the user accepts, and how to re-enable it later. Never silently omit a security feature or present security as opt-in.
- **Don't assume — ask.** When a recommendation depends on user intent that hasn't been gathered yet, ask the question first. Never base advice on an assumption about what the user will or won't do.
- **Don't guess — research.** When a skill references third-party UIs, APIs, or configuration (e.g., API key permissions, provider dashboards), web-search for the current state before advising. Third-party interfaces change frequently. If a skill caches a snapshot, mark it with a date and warn it may be stale.
- **Automate, but ask before GUI.** When a step can be automated (install, open a URL, run a command), do it instead of printing instructions. But always ask permission before opening GUI windows, browsers, or App Store pages — these are disruptive and the user may not be ready.
- **Never leak secrets or personal data — in terminal output OR skill files.** Use single-quoted heredocs (`<< 'EOF'`) so shell variables aren't expanded in the output. Never use interactive commands that echo secrets character by character (e.g., `paste-token`). Never print API keys, tokens, or passwords — not even partially. **Never put real IPs, phone numbers, hostnames, usernames, or account-specific data in skill files** — use `<placeholder>` templates instead. Personal data belongs in agent memory/config, not in skills (which may be public repos).

## Information Boundaries

- Generic/framework skills (`ac-django`, `ac-python`) must **not** contain project-specific or proprietary details.
- Project-specific skills (in overlay repos) may reference their project freely but must not leak into generic skills.
