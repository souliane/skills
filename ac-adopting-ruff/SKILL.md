---
name: ac-adopting-ruff
description: Use when adopting ruff as the sole Python linter and formatter for a project, replacing black, isort, flake8, or pylint, with either progressive per-rule enforcement or changed-files-only gradual adoption. Also use to pay back ruff tech debt — shrinking accumulated `per-file-ignores` via session-sized, one-file-or-one-rule-at-a-time cleanup — on phrasing like "pay back ruff tech debt", "clean up ruff ignores", or "reduce per-file-ignores" (ask first if the user only says "pay back tech debt" without mentioning ruff).
compatibility: Any Python project with pre-commit (prek). Knowledge-only skill.
metadata:
  version: 0.1.0
  subagent_safe: true
---

# Adopt Ruff

## Dependencies

Standalone. No dependencies on other skills.

## Overview

Replace legacy Python linting (black, isort, flake8, pylint) with ruff as the **sole** linter and formatter. Enable ALL rules including preview, explicitly disable what fails, then enforce rules — either progressively (one MR per rule/batch) or by enabling all rules at once and checking only changed files.

Projects that picked "changed files only" accumulate per-file-ignores over time (engineers touch a file, see unrelated violations, pin the rule instead of fixing it). **Phase 3** is the recurring, session-sized cleanup that pays that debt back one file or one rule at a time.

## Principles

- **ALL rules enabled** including preview — whitelist what we disable, not what we enable
- **Clean break by default** — no compatibility shims unless the team explicitly opts in (see [Black/isort-Compatible Formatting](#blackisort-compatible-formatting))
- **Every disabled rule has a comment** with its human-readable name
- **One worktree per MR** — `ruff-bootstrap` for Phase 1, `ruff-<CODES>` for each MR in Phase 2
- **Auto-fix first** — if ruff can fix it, let it; manual fix only when needed
- **prek everywhere** — same hooks locally (pre-commit) and in CI

## Phase 1: Bootstrap MR

Goal: swap tooling with zero new lint violations and minimal code changes.

### 0. Ask the user

Before starting, ask the user two questions:

1. **Line length?**
   - 88 (black default)
   - 100 (ruff default)
   - 120 (Recommended)

2. **Formatting approach?**
   - **Clean break (Recommended)** — ruff's own formatting, no compatibility with black/isort
   - **Maximum compatibility** — match black/isort output as closely as possible (see [Black/isort-Compatible Formatting](#blackisort-compatible-formatting))

These answers determine the `[tool.ruff]` configuration in step 4.

### 1. Create worktree

```bash
git worktree add <project>-ruff-bootstrap -b ruff-bootstrap origin/main
cd <project>-ruff-bootstrap
```

### 2. Audit and remove legacy tooling

Find and remove:

| Location | Remove |
|----------|--------|
| `.pre-commit-config.yaml` | black, isort, flake8, pylint, pycodestyle, pyflakes hooks |
| `pyproject.toml` / `setup.cfg` | `[tool.black]`, `[tool.isort]`, `[flake8]`, `[pylint.*]` sections |
| Dependencies | black, isort, flake8, pylint packages (and their plugins) |
| Lock files | Regenerate lock file after dependency changes |
| CI config | black/isort/flake8/pylint pipeline steps |

### 3. Add ruff pre-commit hooks (without --fix)

In `.pre-commit-config.yaml`, add ruff **without `--fix`** initially:

```yaml
- repo: https://github.com/astral-sh/ruff-pre-commit
  rev: <GIT_SHA>  # <TAG> — always pin by SHA, tag as comment
  hooks:
    - id: ruff-check
    - id: ruff-format
```

Get the SHA: `git ls-remote https://github.com/astral-sh/ruff-pre-commit <TAG>`

Pin the **same version** in your project dependencies so that local `ruff` CLI matches what prek runs.

No `--fix` yet — this ensures prek discovers violations without silently auto-fixing code.

### 4. Configure ruff in pyproject.toml

Use the user's answers from step 0 to set `line-length` and decide between clean-break vs compatibility mode.

**Clean-break configuration** (default):

```toml
[tool.ruff]
target-version = "py312"  # match project's minimum Python
line-length = 120         # from step 0 — adjust to user's choice
fix = true
lint.select = ["ALL"]
lint.preview = true

# --- To enforce: Phase 2 queue (enable one MR at a time) ---
lint.ignore = []

# --- Permanently disabled (not applicable to this project) ---
# lint.ignore is additive — rules here stay disabled forever.
# Example:
#   "CPY001", # missing-copyright-notice

# --- Formatter-conflicting rules (always disabled with ruff format) ---
# Ref: https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
lint.extend-ignore = [
  "COM812", # missing-trailing-comma
  "COM819", # prohibited-trailing-comma
  "D206",   # docstring-tab-indentation
  "D300",   # triple-single-quotes
  "E111",   # indentation-with-invalid-multiple
  "E114",   # indentation-with-invalid-multiple-comment
  "E117",   # over-indented
  "ISC001", # single-line-implicit-string-concatenation
  "Q000",   # bad-quotes-inline-string
  "Q001",   # bad-quotes-multiline-string
  "Q002",   # bad-quotes-docstring
  "Q003",   # avoidable-escaped-quote
  "Q004",   # unnecessary-escaped-quote
  "W191",   # tab-indentation
]
```

No `[tool.ruff.lint.isort]` or `[tool.ruff.format]` sections in clean-break mode.

**Compatibility configuration:** If the user chose maximum compatibility, use the [Black/isort-Compatible Formatting](#blackisort-compatible-formatting) section instead.

**Formatter-conflicting rules:** The `lint.extend-ignore` list comes from
<https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules>. Check that page
for the current list when upgrading ruff — it may change across versions. These
rules **must always be disabled** when using `ruff format`.

### 5. Discover and disable failing rules via prek

Run prek — it uses its own pinned ruff version, so there's no version mismatch:

```bash
prek run --all-files
```

It will fail with violations. Extract the failing rule codes and add them to the
`# --- To enforce: Phase 2 queue` section of `lint.ignore`, each with its
human-readable name as a comment (use `ruff rule --all --output-format json` to
build a code→name lookup). Move rules that will never apply (e.g., `CPY001`) to
the `# --- Permanently disabled` section instead. Repeat until prek passes clean.

The helper script can parse ruff JSON output to generate a ready-to-paste block:

```bash
./ac-adopting-ruff/scripts/cli.py discover [path]
```

**Watch out for these traps:**

- **Incompatible docstring pairs (D203/D211, D212/D213):** When ALL is selected, ruff auto-suppresses one of each pair. Disabling the "winning" rule reveals the suppressed one. Always disable both sides: D203 + D213, or D211 + D212.
- **RUF100 (unused-noqa-directive):** Existing `# noqa: XXXX` comments become stale when the referenced rule is disabled. Add RUF100 to lint.ignore in the bootstrap; re-enable it in Phase 2.

### 6. Format and verify via prek

```bash
prek run --all-files
```

This will reformat files via the `ruff-format` hook — some files will change, which is expected. It may fail on the first run because reformatting modifies files. Run it again:

```bash
prek run --all-files
```

Must pass cleanly on the second run. No further changes should happen (all failing rules are disabled, formatting is already applied).

### 7. Add --fix to pre-commit config

Now that all rules are properly disabled and formatting is done, add `--fix` for Phase 2:

```yaml
    - id: ruff-check
      args: [--fix]
```

### 8. Final verify

```bash
prek run --all-files
```

Must pass cleanly with no changes.

### 9. Create bootstrap MR

Adapt the commit message to what was actually done. Example:

```text
chore: replace black/isort with ruff

- Remove black, isort, flake8 from pre-commit and dependencies
- Add ruff-check + ruff-format pre-commit hooks
- Configure ruff with ALL rules, disable currently-failing rules
- Reformat codebase with ruff format
```

### 10. Message to colleagues

Post in the team channel when the MR is ready for review. Adapt this template to the project, the user's decisions from step 0, and what was actually changed:

```text
This MR replaces <old tools> with ruff as our sole linter and formatter.

Lint rules that currently have violations are disabled — they will be
enabled one by one in dedicated follow-up MRs. All other rules are
already enforced.

<Describe the actual formatting impact — e.g. "most files are reformatted"
for clean-break mode, or "minimal reformatting" for compatibility mode.>

For the review: focus on the config files (pyproject.toml,
.pre-commit-config.yaml, dependency files). Reformatted files don't need
line-by-line review.

Once merged, it will conflict with your current branches. To fix:

    git fetch
    git merge origin/main
    prek install

When prompted for conflicts, keep YOUR changes (--ours = your branch,
--theirs = main):

    git checkout --ours .
    git commit -a          # ruff reformats your files → commit fails
    git commit -a          # files are now formatted → commit succeeds
    git push

The first commit triggers the pre-commit hook which reformats your code
(so it fails because files were modified). The second commit goes through
cleanly.
```

**Note on merge strategy:** During `git merge origin/main`, **ours** = the colleague's branch, **theirs** = main (with ruff reformatting). `git checkout --ours .` keeps the colleague's code as-is. The pre-commit hook reformats it on the first commit attempt, and it goes through on the second.

## Phase 2: Rule Enforcement

After the bootstrap MR is merged, choose an enforcement approach. Read [`references/enforcement.md`](references/enforcement.md) for the full Phase 2 procedures.

### 0. Ask the user

Before starting Phase 2, ask the user these questions (one at a time):

1. **Which repo?** — the project directory containing `pyproject.toml` with the ruff config.

2. **Enforcement approach?**
   - **Changed files only (Recommended)** — enable all rules immediately, check only changed files in CI. One config-only MR, zero merge conflicts. See [`references/enforcement.md`](references/enforcement.md) § Phase 2A.
   - **Progressive enforcement** — fix violations one rule/batch at a time via dedicated MRs. Predictable pace, but many MRs and merge conflicts. See [`references/enforcement.md`](references/enforcement.md) § Phase 2B.

## Phase 3: Paying Back Ruff Tech Debt

After adopting the "changed files only" approach (Phase 2A), `per-file-ignores`
tends to grow. When engineers touch a file and ruff surfaces violations
unrelated to their change, the path of least resistance is to pin the rule for
the file instead of fixing it. Over time, `pyproject.toml` collects dozens of
file entries with long rule lists, each labelled "pre-existing — to be
addressed in dedicated techdebt".

Phase 3 is the recurring, session-sized cleanup that chips away at that debt.
Invoke **only on ruff-specific phrasing** — "pay back ruff tech debt", "clean
up ruff ignores", "reduce per-file-ignores", "unignore `<file>`/`<rule>`". If
the user says only "pay back tech debt" without mentioning ruff, ask whether
they mean ruff tech debt before proceeding — generic tech debt (dead code,
slow queries, TODOs) is out of scope for this skill.

Each session = one small MR. Two modes:

- **Mode A (file-focused)** — shrink or delete one file's ignore entry
- **Mode B (rule-focused, default when `per-file-ignores` has >20 entries)** —
  drop one rule from every file where it can be removed without refactoring

Always start by scanning for **stale** ignores (rule pinned but no longer
violates) — those are free wins. Rules that demand real refactoring
(`C901`, `PLR09xx`, `ANN*` at scale, `FBT001/2` on public APIs, `D*`) are on
the skip list and left alone. If any cleanup drags in architectural change,
restore the rule for that one file and move on.

Read [`references/tech-debt-payback.md`](references/tech-debt-payback.md) for
the full procedure, skip list, and scope discipline.

## Quick Reference

| Task | Command |
|------|---------|
| Lint + format + auto-fix | `prek run --all-files` |
| Rule metadata (all rules) | `ruff rule --all --output-format json` |
| Rule docs (single rule) | `ruff rule <CODE>` |

## When to Use `--unsafe-fixes`

Ruff distinguishes **safe fixes** (guaranteed to preserve semantics) from **unsafe fixes** (may change behavior). By default, `--unsafe-fixes` is off — both in the pre-commit hook and in the `fix = true` config. Keep it that way for automated runs.

Use `--unsafe-fixes` **manually** when:

- **Removing unused imports** (`F401`) — ruff marks these as unsafe because removing an import can break re-exports or side effects. If you've verified the import isn't re-exported, run `ruff check --select F401 --fix --unsafe-fixes <path>` to clean them up.
- **Upgrading type annotations** (`UP006`, `UP007`, etc.) — e.g., `List[int]` → `list[int]`. Unsafe because it can break runtime uses in older Python versions, but safe if you control your target version.
- **Simplifying boolean expressions** (`SIM1xx`) — some simplifications change short-circuit evaluation order. Safe in practice if the expressions have no side effects.

**Never** enable `--unsafe-fixes` globally in pre-commit or CI. Always run it as a targeted, one-off command on specific rules, review the diff, and commit the result.

```bash
# Example: clean up unused imports in a specific directory
ruff check --select F401 --fix --unsafe-fixes src/
git diff  # review what changed
```

## Black/isort-Compatible Formatting

If the team wants to minimize reformatting churn, see [`references/compatible-formatting.md`](references/compatible-formatting.md) for the full configuration, settings mapping, and unavoidable differences.

## Dangerous Auto-Fixes (Non-Negotiable Review Required)

Some ruff rules have auto-fixes that are **semantically incorrect** in specific contexts. See [`references/dangerous-auto-fixes.md`](references/dangerous-auto-fixes.md) for the full checklist covering PLR6104, N805, PIE794, FURB189, FURB192, PTH120, PTH1xx, F401, and UP006/UP007.

## Common Mistakes

- **Trusting auto-fix without reviewing the diff** — EVERY auto-fix run requires `git diff` review. Rules like N805, PIE794, FURB189, FURB192, PTH1xx can silently change runtime behavior or break mocks. See [`references/dangerous-auto-fixes.md`](references/dangerous-auto-fixes.md) for the full checklist.
- **Grouping unrelated high-risk rules** — only group auto-fixable, low-count rules; keep manual-fix or high-count rules in their own MR
- **Missing rule name comment** — `"D100",` alone is meaningless; always add `# undocumented-public-module`
- **Disabling globally when per-file-ignores suffice** — `S101` (assert) should only be ignored in tests, not everywhere
- **Not running `prek run --all-files`** — always use prek, never call ruff directly
- **Mixing up `format.preview` and `lint.preview`** — they are independent; `lint.preview = true` is fine with `format.preview = false`
- **Wrong `line-length` in compatibility mode** — must match old black config exactly or you get massive reformatting
