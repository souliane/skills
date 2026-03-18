---
name: ac-managing-repos
description: Cross-repo management for maintained repositories — infrastructure audit, delivery status, commit squashing, boilerplate backporting, dependency upgrades, and architectural recommendations. Use when checking unpushed work, aligning configs, squashing commits, backporting from boilerplate, upgrading dependencies, or when ac-reviewing-skills/t3-retro chain into delivery. Also use for "repo status", "what needs pushing", "align repos", "backport", "upgrade deps", "audit repos".
compatibility: Any git-based repository portfolio. CLI requires Python 3.12+, uv, Typer.
metadata:
  version: 0.1.0
  subagent_safe: false
---

# Managing Repos

Cross-repo management for a portfolio of maintained repositories. Acts as a **software architect** across the portfolio — keeps repos aligned, harmonized, healthy, and delivered.

## Dependencies

- **ac-python** (reference) — provides the canonical tooling configuration. Load when verifying a repo's config against the standard.

## Configuration: `~/.ac-managing-repos`

Shell-sourceable config file with uppercase variable names.

```bash
# Regex matched against repo paths relative to T3_WORKSPACE_DIR (from ~/.teatree).
# All git repos under T3_WORKSPACE_DIR whose relative path matches are managed.
MANAGED_REPOS="<org>/(repo-a|repo-b|repo-c)$"

# Boilerplate -> dependent repos mapping.
# Format: boilerplate_name:dep1,dep2;boilerplate_name:dep1,dep2
# Names are directory basenames (must match repos discovered via MANAGED_REPOS).
BOILERPLATE_MAP="<boilerplate-repo>:<dep-repo-1>,<dep-repo-2>"
```

| Variable | Purpose |
|----------|---------|
| `MANAGED_REPOS` | Regex to discover repos under `T3_WORKSPACE_DIR`. Used by `status`, `audit`, `squash`, and all workflows. |
| `BOILERPLATE_MAP` | Maps boilerplate repos to their dependents. Used by the backport workflow. |

**Dependencies on other config files:**

- **`~/.teatree`** — `T3_WORKSPACE_DIR` (where to scan), `T3_AUTO_SQUASH` (squash behavior), `T3_REVIEW_SKILL` (chain source).
- **`~/.ac-reviewing-skills`** — `MAINTAINED_SKILLS` (skill ownership). The `config` command compares this with `MANAGED_REPOS` to detect drift.

## CLI

Single entry point at [`scripts/cli.py`](scripts/cli.py).

```bash
# Show delivery status across all managed repos
uv run ac-managing-repos/scripts/cli.py status

# Show status for specific repos only
uv run ac-managing-repos/scripts/cli.py status --repo <name> --repo <name>

# Inventory all config, data, and cache files + health checks
uv run ac-managing-repos/scripts/cli.py config
```

## When to Use

- Checking which repos have unpushed work after a retro or review session.
- Squashing related commits before pushing.
- Reviewing infrastructure alignment across repos (configs, hooks, tooling versions).
- Backporting boilerplate changes to dependent repos.
- Periodic health check: dependency upgrades, architectural recommendations, tech stack review.
- When `ac-reviewing-skills` chains into delivery (via `DELIVERY_SKILL` config).
- When `t3-retro` chains into cross-repo review.

## Trigger QA (Release Gate)

- Should trigger:
  - "What repos have unpushed commits?"
  - "Compare pre-commit configs across all skill repos."
  - "Backport the new ruff config from boilerplate to all repos."
  - "Are my repos healthy? What needs upgrading?"
  - "Align pyproject.toml across repos."
  - "Squash my commits and show me what's ready to push."
- Should NOT trigger:
  - "Review the ac-python skill for content quality." (use ac-reviewing-skills)
  - "Write a new Python script." (use ac-python)

---

## Workflows

### Workflow 1 — Delivery Status

Quick overview of what needs attention across all managed repos.

**Steps:**

1. Load `~/.ac-managing-repos` config (or ask user if missing).
2. For each repo discovered via `MANAGED_REPOS` regex:
   - Check if the repo exists and is a git repo.
   - Show current branch.
   - Show unpushed commits (`git log --oneline @{upstream}..HEAD`). If no upstream, show all commits on branch.
   - Show uncommitted changes (`git status --short`).
   - Show stale branches (merged but not deleted).
3. Present a summary table.

**Output format:**

```text
╔══════════════════════════════════════════════════════════════╗
║  MANAGED REPOS STATUS                                       ║
╠══════════════════════════════════════════════════════════════╣
║  teatree          main     2 unpushed  0 dirty              ║
║  skills           main     5 unpushed  1 dirty              ║
║  teatree-e2e      main     0 unpushed  0 dirty   ✓ clean    ║
║  blog             main     0 unpushed  3 dirty              ║
║  python-boilerplate main   1 unpushed  0 dirty              ║
╚══════════════════════════════════════════════════════════════╝
```

When called by other skills (e.g., at end of `t3-retro` or `ac-reviewing-skills`), show the summary and offer to proceed to squash workflow.

### Workflow 2 — Squash & Prepare

Squash related unpushed commits into clean, human-sized units per repo. This is the **canonical source of truth** for squash rules — other skills reference this section.

**Squash Rules (Non-Negotiable):**

1. **Never rewrite pushed history.** Before any squash, check `git log origin/<branch>..HEAD` to identify the safe range. Only commits not yet at origin are candidates.
2. **Group by topic.** Related commits (e.g., all retro fixes to the same skill, all infra alignment changes) become one commit. Unrelated commits stay separate.
3. **Keep human-sized commits.** A single commit should be reviewable in one sitting. If squashing would produce a commit touching 20+ files across unrelated concerns, split rather than squash.
4. **Squash integrity check (Non-Negotiable).** Before any rewrite, save the tip in a durable way: `echo $(git rev-parse HEAD) > /tmp/squash-tip-$(basename $(pwd))`. After the **final** commit (not intermediate steps), verify: `git diff $(cat /tmp/squash-tip-...)..HEAD` is empty. If there is any diff, the rewrite lost or introduced changes — abort and investigate. Shell variables can be lost between commands; the temp file survives. **Run this check as the very last step before declaring the squash done.**
5. **Respect `T3_AUTO_SQUASH`.** When `true`, squash automatically without confirmation. When `false` (default), present the squash plan and wait for user approval.
6. **Each skill squashes its own commits before chaining.** When this skill is invoked in a chain (after `t3-retro` → `ac-reviewing-skills`), the previous skills have already squashed their own work. This skill squashes any additional commits it creates, then shows the final status.

**Steps:**

1. Run delivery status (Workflow 1) to identify repos with unpushed commits.
2. For each repo with unpushed commits:
   - List the unpushed commits with `--stat`.
   - Propose a squash plan: which commits to group, proposed commit messages.
   - Execute squash (with user approval unless `T3_AUTO_SQUASH=true`).
   - Verify integrity after each squash.
3. Show final status summary.

### Workflow 3 — Infrastructure Audit

Compare and harmonize `.pre-commit-config.yaml`, `pyproject.toml`, `.editorconfig`, and utility scripts across managed repos. This is the original `ac-auditing-repos` workflow, preserved and integrated.

#### Phase 1 — Scope

1. **Identify repos to compare.** Use repos discovered via `MANAGED_REPOS`, or ask the user to narrow. Repos don't need to be skill repos — any repo with shared tooling qualifies.
2. **Identify a reference repo.** One repo serves as the canonical source. If not specified, use the repo with the most complete config (typically the one with the most hooks and strictest settings).

#### Phase 2 — Read & Compare

Read these files from every repo in scope:

| File | What to compare |
|------|----------------|
| `.pre-commit-config.yaml` | Hook inventory, tool versions, phase ordering, file scoping patterns, rev format (SHA + tag comment) |
| `pyproject.toml` | `[tool.ruff]`, `[tool.ty]`, `[tool.pytest]`, `[tool.coverage]`, `[tool.codespell]` |
| `.editorconfig` | Charset, line ending, indent style/size, markdown settings, section ordering |
| Utility scripts | Presence of shared scripts (e.g., `bump-pyproject-deps-from-lock-file.py`) |

#### Phase 3 — Classify Divergences

| Classification | Action |
|----------------|--------|
| **Drift** — no reason for the difference | Align to the reference repo |
| **Intentional** — repo-specific need | Keep, but add a comment explaining why |
| **Stale** — was intentional but the reason no longer applies | Align to the reference repo, remove the stale comment |
| **Unclear** — might be intentional but not documented | Ask the user |

#### Phase 4 — Present Findings

Structured comparison table grouped by file, then by setting. Include the reference value and each repo's current value.

#### Phase 5 — Implement

After user approval:

1. Apply fixes to all repos in scope.
2. Run `ruff check --no-fix` on each repo to verify no new lint errors.
3. Run tests if the repo has them (`uv run pytest --no-header -q`).
4. **Post-implementation convergence check (Non-Negotiable):** Re-read each config file and diff against the reference repo. Confirm every setting matches or has a documented justification.

### Workflow 4 — Boilerplate Backport

Propagate changes from boilerplate repos to their dependents.

**Steps:**

1. Read `boilerplates` mapping from config.
2. For each boilerplate repo that has recent changes (unpushed or recently pushed commits):
   - Identify which files changed (configs, scripts, templates).
   - For each dependent repo, check if those files exist and differ.
   - Classify each difference: already aligned, needs backport, intentionally different.
3. Present a backport plan per dependent repo.
4. After user approval, apply changes and run verification (lint, tests).
5. Commit backport changes in each dependent repo.

**Backport ≠ blind copy.** Dependent repos may have intentional divergences. The skill must diff intelligently and ask about unclear differences, just like the infrastructure audit.

### Workflow 5 — Architectural Health Check

Deep cross-repo analysis acting as a **software architect** for the portfolio. Run periodically or on demand.

**5a. Dependency Audit**

- For each repo, read `pyproject.toml` (or equivalent) and list all dependencies with current versions.
- Check for outdated dependencies: `uv pip list --outdated` or equivalent.
- Flag security vulnerabilities: `uv pip audit` or `pip-audit`.
- Recommend upgrades with breaking change warnings.
- Check for unused dependencies (imported but not used, or declared but not imported).

**5b. Cross-Repo Code Analysis**

- **Duplication detection.** Scan for duplicated code, scripts, or patterns across repos. Recommend extraction to shared libraries or boilerplate.
- **Dead code.** Identify unused modules, scripts, or config entries across repos.
- **Shared patterns.** When 3+ repos implement the same pattern differently, recommend standardization and extraction to a shared location.

**5c. Tech Stack & Framework Review**

- **Tooling freshness.** Are the repos using current-generation tools? Flag deprecated tools or approaches with modern alternatives.
- **Framework versions.** Check if frameworks (Django, Angular, pytest, etc.) are at latest stable versions. Recommend upgrade paths.
- **State of the art.** Based on the repo's domain, suggest modern tools/practices that could replace existing ones. Examples: ruff replacing black+isort+flake8, uv replacing pip+venv, ty replacing mypy.
- **Architectural patterns.** Review the overall repo structure, module boundaries, and dependency graph. Recommend refactoring where coupling is too tight or abstractions are misplaced.

**5d. Consolidation Recommendations**

- **Merge candidates.** Repos that are tightly coupled or always change together may benefit from merging.
- **Split candidates.** Repos that serve multiple unrelated purposes may benefit from splitting.
- **Repo lifecycle.** Flag repos that haven't been touched in months — are they archived, abandoned, or stable?

**Presentation:** All recommendations are presented as a prioritized list with effort estimates (small/medium/large) and impact assessment. The user decides what to act on — this workflow is advisory, not automatic.

---

## Rules

### Infrastructure Rules

#### pyproject-fmt Reordering

When `pyproject-fmt` is a pre-commit hook, it may reorder fields in `pyproject.toml` on commit. **This is expected behavior** — re-stage the reformatted file and retry. Run `prek run pyproject-fmt` before committing after editing `pyproject.toml`.

#### SHA Revs with Tag Comments (Non-Negotiable)

All `.pre-commit-config.yaml` entries must use git SHA as the `rev` value, with the human-readable tag as a comment:

```yaml
rev: 2ca41cc1372d1e939a6a879f18cdc19fc1cac1ce  # v8.30.0
```

Never use bare tags (`rev: v8.30.0`) — they can be force-pushed and change meaning.

#### Phase Comments in Pre-Commit Config (Non-Negotiable)

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

Not all repos need all phases. Skip phases that don't apply, but keep the numbering consistent across repos.

#### Ruff Config Baseline

The canonical ruff configuration is documented in `ac-python/references/testing-and-tooling.md`. Key settings that must match across repos (unless justified):

- `lint.select = ["ALL"]`
- `lint.fixable = ["ALL"]`
- `lint.preview = true`
- Formatter-conflicting rules in `lint.extend-ignore`
- `lint.flake8-implicit-str-concat.allow-multiline = false`
- `lint.flake8-tidy-imports.banned-api."__future__.annotations"`
- `lint.pylint.max-*` complexity limits
- Test per-file-ignores baseline: `PLR2004, S101, SLF001` minimum; full set: `PLC1901, PLC2701, PLR0904, PLR2004, PLR6301, S101, S108, S404, SLF001`

#### EditorConfig Baseline

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

#### target-version vs requires-python

- `target-version` (ruff) and `python-version` (ty/mypy) are **lint settings** — no runtime requirement.
- `requires-python` in `[project]` is a **runtime requirement**. Keep this at the actual minimum Python version the project supports.
- These can differ: a project running on 3.12 can have `target-version = "py313"` to get newer lint rules.

#### Utility Scripts

These scripts should be present in every repo that uses uv + pyproject.toml:

| Script | Purpose |
|--------|---------|
| `bump-pyproject-deps-from-lock-file.py` | Bump `pyproject.toml` deps to `>=` latest versions from `uv.lock` |

---

## Chaining Integration

This skill is designed to be called at the end of a chain:

```text
t3-retro (squashes own commits)
  └─ T3_REVIEW_SKILL → ac-reviewing-skills (squashes own commits)
                          └─ DELIVERY_SKILL → ac-managing-repos
                                               ├─ Workflow 3: Infrastructure audit
                                               ├─ Workflow 2: Squash any new commits
                                               └─ Workflow 1: Final delivery status
```

When invoked in a chain, this skill:

1. Runs infrastructure audit first (may produce additional commits).
2. Squashes its own commits using § Workflow 2 rules.
3. Shows final delivery status across all managed repos.
4. Offers to proceed to push (respecting `T3_PUSH` from `~/.teatree`).

---

## Review Checklists

### Infrastructure Audit

- [ ] All repos use the same tool versions (ruff, gitleaks, codespell, etc.)
- [ ] All `.pre-commit-config.yaml` use SHA revs with tag comments
- [ ] All `.pre-commit-config.yaml` use phased structure
- [ ] Hook inventories match (missing hooks = unguarded code paths)
- [ ] Ruff config settings match across repos
- [ ] ty/mypy rules match
- [ ] pytest addopts match (modulo intentional repo-specific flags)
- [ ] `.editorconfig` matches the baseline
- [ ] Utility scripts present in all repos
- [ ] All divergences are either aligned or documented with a comment

### Delivery

- [ ] No unpushed commits left unintentionally
- [ ] All commits are human-sized and topically grouped
- [ ] No pushed history was rewritten
- [ ] Squash integrity verified (zero diff before/after)
