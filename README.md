# skills

Skill-Driven Development

## Available Skills

<!-- BEGIN SKILLS -->
| Skill | Version | Description |
|-------|---------|-------------|
| `ac-adopting-ruff` | 0.0.1 | Use when adopting ruff as the sole Python linter and formatter for a project, replacing black, isort, flake8, or pylint, with progressive per-rule enforcement via dedicated merge requests. |
| `ac-auditing-repos` | 0.0.1 | Cross-repo infrastructure audit — compare and harmonize pre-commit hooks, linter/formatter config, editor config, and tooling scripts across multiple repositories |
| `ac-django` | 0.0.1 | Definitive Django bible covering Django 6.x, 5.2 LTS, and optional DRF. Fat Models doctrine with migrations, transactions, security, testing, and tooling |
| `ac-editing-acroforms` | 0.0.1 | Inspects, patches, verifies, or diffs AcroForm-based PDF templates — especially when widget geometry, content streams, or filled-output alignment need deterministic scriptable fixes. |
| `ac-generating-slides` | 0.0.1 | Generates presentation slides from Markdown using Marp |
| `ac-python` | 0.0.1 | Generic Python coding guidelines covering style, typing, OOP design, testing, and tooling |
| `ac-reviewing-skills` | 0.0.1 | Deep, holistic review and improvement of one or more skills in the skills repo. Audits architecture, content, scripts, hooks, and quality — then implements fixes |
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
