---
name: ac-scaffolding-skill-repos
description: Scaffold a new AI agent skill repository or update an existing one to align with current best practices. Use when user says "new skill", "create skill", "scaffold skill", "skill boilerplate", "update skill repo", "align repo", "audit repo config", or wants to start or modernize a skill project.
compatibility: macOS/Linux, Python 3.12+, uv, git.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Skill Repo Boilerplate

Scaffold a new AI agent skill repository with a consistent structure, quality tooling, and pre-commit hooks — or update an existing repo to align with current best practices.

## Dependencies

Standalone. If `find-skills` is available, use it to check if a similar skill already exists before scaffolding.

This skill works alongside the agent's native skill system. Skills created here are compatible with slash command discovery — each `SKILL.md` is auto-detected when symlinked into the active agent runtime's skills directory.

## When to Use

- User wants to create a new skill from scratch
- User wants to create a new skill repo (a collection of skills)
- User wants to align an existing skill repo with current best practices

## Mode Detection

Before starting, determine the mode:

1. Check for existing `SKILL.md` files, `.pre-commit-config.yaml`, `pyproject.toml` in the target directory.
2. If **none exist** → **Scaffold mode** (§§ 1–9 below).
3. If **any exist** → **Update mode** (§ 10 below). Tell the user: "Detected an existing skill repo. Switching to update mode — I'll audit each config area and propose changes individually."

---

## Template Repository

A ready-to-use template repo is available at [souliane/skill-repo-boilerplate](https://github.com/souliane/skill-repo-boilerplate). It includes all the config files, hooks, scripts, and directory structure described below.

### Quick Start from Template

For a **skill repo** (collection of skills), the fastest path is to fork the template:

```bash
# Fork on GitHub first, then clone your fork:
git clone git@github.com:YOUR_USERNAME/my-skills.git ~/workspace/my-skills
cd ~/workspace/my-skills

# Add the boilerplate as upstream for future updates:
git remote add boilerplate https://github.com/souliane/skill-repo-boilerplate.git
```

Then customize: rename `my-skill/` to your skill name, update `pyproject.toml` project name, and edit the template `SKILL.md`.

### Retro-basing an Existing Repo on the Boilerplate

To align an existing skill repo with the boilerplate:

```bash
cd ~/workspace/existing-skills

# Add the boilerplate as a secondary remote:
git remote add boilerplate https://github.com/souliane/skill-repo-boilerplate.git
git fetch boilerplate

# Merge (allow unrelated histories for the first merge):
git merge boilerplate/main --allow-unrelated-histories

# Resolve conflicts — keep your content, adopt boilerplate config where it's better.
# Then commit the merge.
```

### Keeping Up to Date

Whenever the boilerplate gets updated:

```bash
git fetch boilerplate
git merge boilerplate/main
```

Conflicts are expected when you've customized config files — resolve them by keeping your project-specific values and adopting any new boilerplate improvements.

---

## Scaffold Mode

### 1. Gather Requirements

Ask the user **one question at a time** (wait for each answer before asking the next). Auto-detect and propose defaults where possible:

1. **Skill name** — kebab-case, descriptive (e.g., `ac-adopting-ruff`, `ac-generating-slides`)
2. **Purpose** — one-sentence description
3. **Type:** single skill (one `SKILL.md`) or skill repo (collection of related skills)?
4. **Has Python scripts?** — some skills are pure markdown; others have scripts
5. **Target audience** — personal use, team, or public

### 2. Scaffold the Project

#### For a single skill (standalone)

```text
<skill-name>/
├── SKILL.md              # The skill definition
├── .gitignore
└── README.md             # Brief description + install instructions
```

#### For a skill repo (collection)

```text
<repo-name>/
├── .editorconfig
├── .gitignore
├── .markdownlint-cli2.yaml
├── .pre-commit-config.yaml
├── LICENSE
├── README.md              # Auto-generated skill catalogue
├── pyproject.toml         # Unified tool configuration
├── uv.lock
├── scripts/
│   ├── hooks/
│   │   └── check-banned-terms.sh
│   └── update_readme_skills.py
├── tests/
│   ├── __init__.py
│   └── conftest.py
├── <skill-1>/
│   └── SKILL.md
└── <skill-2>/
    └── SKILL.md
```

### 3. SKILL.md

Copy [`references/templates/SKILL.md.template`](references/templates/SKILL.md.template) and fill placeholders. See the [frontmatter spec](../ac-reviewing-skills/references/skill-authoring-best-practices.md) for required fields.

Key authoring guidelines:

- Keep `SKILL.md` body under ~500 lines. Split into `references/` and `scripts/` when needed.
- Match instruction specificity to operation fragility (high freedom for judgment calls, low freedom for fragile sequences).
- When a workflow is deterministic, implement it as a callable script rather than prose.
- Build skills incrementally from observed agent failures, not speculatively.

### 4. Config Files

Copy template files from [`references/templates/`](references/templates.md) directly into the repo root:

- [`pyproject.toml`](references/templates/pyproject.toml) — ruff (ALL rules), pytest (100% coverage), ty, codespell
- [`pre-commit-config.yaml`](references/templates/pre-commit-config.yaml) → `.pre-commit-config.yaml` — uv, ruff, ty, gitleaks, markdownlint, editorconfig, conventional commits
- [`ci.yml`](references/templates/ci.yml) → `.github/workflows/ci.yml` — multi-Python CI with uv cache
- [`test-matrix.sh`](references/templates/test-matrix.sh) → `dev/test-matrix.sh` — local Docker-based multi-version testing
- [`.markdownlint-cli2.yaml`](references/templates/.markdownlint-cli2.yaml)
- [`.editorconfig`](references/templates/.editorconfig)
- [`README.md.template`](references/templates/README.md.template) — with auto-generated skills catalogue

### Import Style Check (Non-Negotiable)

When scaffolding from a boilerplate, **check how the boilerplate's entry point and imports work before writing code**. Check `pyproject.toml` `[project.scripts]` and `[tool.coverage.run] source` to understand the package structure. Write a minimal test that exercises the entry point early. The boilerplate may use bare module names (`from main import app`), not fully-qualified `from src.xxx` imports.

### 9. Initialize

After scaffolding:

```bash
cd <repo-name>
git init
uv sync
prek install
prek run --all-files
git add -A && git commit -m "feat: scaffold skill repo"
```

---

## Update Mode

### 10. Audit and Propose Changes

When an existing repo is detected, walk through each config area below. For **each item**, compare the current state against the template, show the diff or missing piece, and **ask the user for confirmation before applying**. Never batch-apply changes.

#### 10.1 SKILL.md Frontmatter Audit

Scan all `*/SKILL.md` files in the repo. For each file, check against the frontmatter spec in § 3:

- **Missing `name`** → propose adding it (inferred from directory name)
- **`name` exceeds 64 chars or uses invalid characters** → propose a compliant name
- **Missing `description`** → propose adding a placeholder
- **`description` exceeds 1024 chars** → propose trimming
- **Description not in third person** → propose rewording
- **Description missing trigger phrases** (no "Use when..." pattern) → propose adding trigger phrases
- **Missing `compatibility`** → propose adding it
- **Missing `metadata.version`** → propose adding `version: 0.0.1`
- **Body exceeds ~500 lines** → propose splitting into reference files

Report findings as a table, then ask which to fix.

#### 10.2 README.md

Check for:

- **Missing `<!-- BEGIN SKILLS -->` / `<!-- END SKILLS -->` markers** → offer to add the skills catalogue section
- **Missing `scripts/update_readme_skills.py`** → offer to create it from template
- **Missing pre-commit hook `update-readme-skills`** → offer to add it (covered in § 10.4)

#### 10.3 pyproject.toml

Compare each section against the template in § 4:

- **Missing `[tool.ruff]`** → offer to add the full ruff config
- **Outdated ruff rules** (e.g., `lint.select` not set to `["ALL"]`, missing `per-file-ignores`) → offer to update, showing the diff
- **Missing `[tool.pytest.ini_options]`** → offer to add
- **Missing `[tool.ty]`** → offer to add the ty config
- **Missing `[tool.coverage.report]`** → offer to add
- **Missing `[tool.codespell]`** → offer to add

For each section, show what will be added/changed and wait for confirmation.

#### 10.4 .pre-commit-config.yaml

Compare hooks against the template in § 5:

- **Missing hooks** (e.g., no `codespell`, no `markdownlint-cli2`, no `editorconfig-checker`, no `ty-check`) → offer to add each one individually
- **Outdated hook revisions** → offer to update each, showing old → new
- **Missing `update-readme-skills` hook** → offer to add
- **Missing `banned-terms` hook** → offer to add
- **Missing script validation hooks** (`scripts-have-uv-shebang`, etc.) → offer to add

#### 10.5 .editorconfig

- **Missing entirely** → offer to create from template (§ 7)
- **Missing sections** (e.g., no `[*.py]` override) → offer to add

#### 10.6 .markdownlint-cli2.yaml

- **Missing entirely** → offer to create from template (§ 6)
- **Missing rules** compared to template → offer to add each

#### 10.7 .gitignore

- **Missing common patterns** (e.g., `__pycache__/`, `.venv/`, `*.egg-info/`, `.coverage`, `.pytest_cache/`) → offer to add

### Update Mode Rules

- **Never auto-apply changes.** Always show what will change and ask for confirmation.
- **Per-change granularity.** Each missing/outdated item is a separate confirmation.
- **Preserve user customizations.** When updating, merge rather than replace. If the user has extra ruff rules, keep them. If they have custom hooks, keep them. Flag conflicts rather than overwriting.
- **Skip irrelevant checks.** If the repo has no Python scripts, skip pyproject.toml Python-specific sections. If the repo has no `scripts/` directory, skip script validation hooks.

## Rules

- **Every skill MUST have YAML frontmatter** with at least `name` and `description` (see § 3 for the full spec).
- **Frontmatter `name` and `description`** must comply with the Agent Skills standard constraints (§ 3).
- **Scripts use `#!/usr/bin/env bash`** for portability (never `#!/bin/bash`).
- **Python scripts targeting uv** should use `#!/usr/bin/env -S uv run --script` with inline metadata.
- **100% test coverage** is required for Python code.
- **Pre-commit hooks run on every commit** — never bypass with `--no-verify`.
- **No project-specific terms** in generic skills. Use `BANNED_TERMS` in the per-repo user config (e.g., `~/.skills`) for enforcement.

## References

- [Skill Authoring Best Practices](../ac-reviewing-skills/references/skill-authoring-best-practices.md) — consolidated authoring guidelines with external references
