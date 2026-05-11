# skills

Skill-Driven Development

## Available Skills

<!-- BEGIN SKILLS -->
| Skill | Version | Description |
|-------|---------|-------------|
| `typer` | — | Typer best practices and conventions |
| `ac-adopting-ruff` | 0.0.1 | Use when adopting ruff as the sole Python linter and formatter for a project, replacing black, isort, flake8, or pylint, with either progressive per-rule enforcement or changed-files-only gradual adoption. Also use to pay back ruff tech debt — shrinking accumulated `per-file-ignores` via session-sized, one-file-or-one-rule-at-a-time cleanup — on phrasing like "pay back ruff tech debt", "clean up ruff ignores", or "reduce per-file-ignores" (ask first if the user only says "pay back tech debt" without mentioning ruff). |
| `ac-django` | 0.0.1 | Definitive Django bible covering Django 6.x, 5.2 LTS, and optional DRF. Fat Models doctrine with migrations, transactions, security, testing, and tooling |
| `ac-editing-acroforms` | 0.0.1 | Inspects, patches, verifies, or diffs AcroForm-based PDF templates — especially when widget geometry, content streams, or filled-output alignment need deterministic scriptable fixes. |
| `ac-generating-slides` | 0.0.1 | Generates presentation slides from Markdown using Marp |
| `ac-openclaw` | 0.0.1 | Install, configure, and maintain OpenClaw (personal AI assistant) on a VPS or local machine |
| `ac-python` | 0.0.1 | Generic Python coding guidelines covering style, typing, OOP design, testing, and tooling |
| `ac-reviewing-codebase` | 0.2.0 | Unified codebase review — audits skill quality, code health, infrastructure alignment, and cross-consistency across a portfolio of repos. Runs deterministic metrics (ruff, coverage, complexity, TODOs, dependency staleness) and LLM-driven architectural judgment. Also handles delivery status, commit squashing, infrastructure harmonization, and boilerplate backporting |
| `ac-scaffolding-skill-repos` | 0.0.1 | Scaffold a new AI agent skill repository or update an existing one to align with current best practices |
| `ac-writing-blog-posts` | 0.0.1 | Write blog articles and generate social media posts to promote them |
<!-- END SKILLS -->

## Installation

```bash
npx skills add https://github.com/souliane/skills --skill '*' -g -y
```

To install into multiple agent runtimes at once:

```bash
npx skills add https://github.com/souliane/skills --skill '*' -g -y --agent claude-code codex cursor github-copilot
```
