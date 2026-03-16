---
name: ac-auditing-repos
description: Cross-repo infrastructure audit — compare and harmonize pre-commit hooks, linter/formatter config, editor config, and tooling scripts across multiple repositories. Use when reviewing repo infrastructure, aligning configs across sibling repos, bootstrapping a new repo from a boilerplate, or checking that a repo's tooling matches team standards.
compatibility: Any Python/uv-based repository. Knowledge-only skill with no external tool requirements.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Auditing Repo Infrastructure

Compare and harmonize `.pre-commit-config.yaml`, `pyproject.toml`, `.editorconfig`, and utility scripts across a set of repositories. Identifies drift, proposes alignment, and implements fixes.

## Dependencies

- **ac-python** (reference) — provides the canonical tooling configuration. Load when you need to verify a repo's config against the standard.

## When to Use

- Reviewing infrastructure across multiple repos that share a toolchain (skill repos, boilerplate repos, project repos).
- Bootstrapping a new repo and ensuring it matches the team standard.
- After upgrading a tool version in one repo and needing to propagate to siblings.
- When `ac-reviewing-skills` delegates its infrastructure comparison step.

## Trigger QA (Release Gate)

- Should trigger:
  - "Compare pre-commit configs across all skill repos."
  - "Align pyproject.toml between teatree and my-project-skills."
  - "Check if python-boilerplate's editorconfig matches the standard."
  - "Propagate ruff version bump to all repos."
- Should NOT trigger:
  - "Review the ac-python skill for content quality." (use ac-reviewing-skills)
  - "Write a new Python script." (use ac-python)

## Workflow

### Phase 1 — Scope

1. **Identify repos to compare.** Ask the user which repos are in scope, or use the default set from the user's config. Repos don't need to be skill repos — any repo with shared tooling qualifies.
2. **Identify a reference repo.** One repo serves as the canonical source. If not specified, use the repo with the most complete config (typically the one with the most hooks and strictest settings).

### Phase 2 — Read & Compare

Read these files from every repo in scope:

| File | What to compare |
|------|----------------|
| `.pre-commit-config.yaml` | Hook inventory, tool versions, phase ordering, file scoping patterns, rev format (SHA + tag comment) |
| `pyproject.toml` | `[tool.ruff]` (target-version, lint.ignore, lint.extend-ignore, lint.per-file-ignores, lint.pylint.*, lint.flake8-*, lint.fixable, lint.preview), `[tool.ty]`, `[tool.pytest]`, `[tool.coverage]`, `[tool.codespell]` |
| `.editorconfig` | Charset, line ending, indent style/size, markdown settings, section ordering |
| Utility scripts | Presence of shared scripts (e.g., `bump-pyproject-deps-from-lock-file.py`) |

### Phase 3 — Classify Divergences

For each difference found, classify it:

| Classification | Action |
|----------------|--------|
| **Drift** — no reason for the difference | Align to the reference repo |
| **Intentional** — repo-specific need | Keep, but add a comment explaining why |
| **Stale** — was intentional but the reason no longer applies | Align to the reference repo, remove the stale comment |
| **Unclear** — might be intentional but not documented | Ask the user |

### Phase 4 — Present Findings

Present a structured comparison table showing all divergences, classified by type. Group by file, then by setting. Include the reference value and each repo's current value.

### Phase 5 — Implement

After user approval:

1. Apply fixes to all repos in scope.
2. Run `ruff check --no-fix` on each repo to verify no new lint errors.
3. Run tests if the repo has them (`uv run pytest --no-header -q`).
4. **Post-implementation convergence check (Non-Negotiable):** Re-read each config file and diff against the reference repo. Confirm every setting matches or has a documented justification. This catches partial applications (e.g., missing ignore rules, bare tags that slipped through, stale comments from pyproject-fmt reordering).

## Rules

### pyproject-fmt Reordering

When `pyproject-fmt` is a pre-commit hook, it may reorder fields in `pyproject.toml` on commit (e.g., moving `lint.fixable` to a different position). This causes the commit to fail because files were modified by the hook. **This is expected behavior** — re-stage the reformatted file and retry. To avoid surprises, run `prek run pyproject-fmt` before committing after editing `pyproject.toml`.

### SHA Revs with Tag Comments (Non-Negotiable)

All `.pre-commit-config.yaml` entries must use git SHA as the `rev` value, with the human-readable tag as a comment:

```yaml
rev: 2ca41cc1372d1e939a6a879f18cdc19fc1cac1ce  # v8.30.0
```

Never use bare tags (`rev: v8.30.0`) — they can be force-pushed and change meaning.

### Phase Comments in Pre-Commit Config (Non-Negotiable)

Hooks must be organized in numbered phases with comments:

```yaml
# Phase 1 - Init
# Phase 2 - Formatters
# Phase 3 - Fast syntax
# Phase 4 - Linters
# Phase 5 - Type check
# Phase 6 - Security & custom
# Phase 7 - Project-specific
# Phase 8 - Slow (safety, pytest)
# Phase 9 - Manual (semgrep, AI review)
# Phase 10 - Commit-msg
```

Not all repos need all phases. Skip phases that don't apply, but keep the numbering consistent so it's easy to compare across repos.

### Ruff Config Baseline

The canonical ruff configuration is documented in `ac-python/references/testing-and-tooling.md`. Key settings that must match across repos (unless justified):

- `lint.select = ["ALL"]`
- `lint.fixable = ["ALL"]`
- `lint.preview = true`
- Formatter-conflicting rules in `lint.extend-ignore`
- `lint.flake8-implicit-str-concat.allow-multiline = false`
- `lint.flake8-tidy-imports.banned-api."__future__.annotations"`
- `lint.pylint.max-*` complexity limits
- Test per-file-ignores baseline: `PLR2004, S101, SLF001` minimum; full set: `PLC1901, PLC2701, PLR0904, PLR2004, PLR6301, S101, S108, S404, SLF001`

### EditorConfig Baseline

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
indent_style = space
indent_size = 2
trim_trailing_whitespace = true

[*.py]
indent_size = 4

[*.{md,markdown}]
trim_trailing_whitespace = false
indent_size = unset

[Makefile]
indent_style = tab
```

### target-version vs requires-python

- `target-version` (ruff) and `python-version` (ty/mypy) are **lint settings** — they tell the linter which syntax features to assume. No runtime requirement.
- `requires-python` in `[project]` is a **runtime requirement** — uv/pip will enforce it. Keep this at the actual minimum Python version the project supports.
- These can differ: a project running on 3.12 can have `target-version = "py313"` to get newer lint rules without requiring 3.13 at runtime.

### Utility Scripts

These scripts should be present in every repo that uses uv + pyproject.toml:

| Script | Purpose |
|--------|---------|
| `bump-pyproject-deps-from-lock-file.py` | Bump `pyproject.toml` deps to `>=` latest versions from `uv.lock` |

## Review Checklist

- [ ] All repos use the same tool versions (ruff, gitleaks, codespell, etc.)
- [ ] All `.pre-commit-config.yaml` use SHA revs with tag comments
- [ ] All `.pre-commit-config.yaml` use phased structure
- [ ] Hook inventories match (missing hooks = unguarded code paths)
- [ ] Ruff `lint.ignore`, `lint.extend-ignore`, `lint.per-file-ignores` match
- [ ] Ruff `lint.pylint.*` complexity limits match
- [ ] ty/mypy rules match
- [ ] pytest addopts match (modulo intentional repo-specific flags)
- [ ] `.editorconfig` matches the baseline
- [ ] Utility scripts present in all repos
- [ ] All divergences are either aligned or documented with a comment
