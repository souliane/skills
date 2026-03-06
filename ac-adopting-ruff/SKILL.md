---
name: ac-adopting-ruff
description: Use when adopting ruff as the sole Python linter and formatter for a project, replacing black, isort, flake8, or pylint, with progressive per-rule enforcement via dedicated merge requests.
compatibility: Any Python project with pre-commit (prek). Knowledge-only skill.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Adopt Ruff

## Dependencies

Standalone. No dependencies on other skills.

## Overview

Replace legacy Python linting (black, isort, flake8, pylint) with ruff as the **sole** linter and formatter. Enable ALL rules including preview, explicitly disable what fails, then enforce rules one MR at a time.

## Principles

- **ALL rules enabled** including preview — whitelist what we disable, not what we enable
- **Clean break by default** — no compatibility shims unless the team explicitly opts in (see [Black/isort-Compatible Formatting](#blackisort-compatible-formatting))
- **Every disabled rule has a comment** with its human-readable name
- **One worktree per MR** — `ruff-bootstrap` for Phase 1, `ruff-<CODE>` for each rule in Phase 2
- **One MR per rule** for clean git history and easy review
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

# --- Project-specific exclusions (populated in step 5) ---
lint.ignore = []

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

It will fail with violations. Extract the failing rule codes, add them to `lint.ignore` with their human-readable name as a comment (use `ruff rule --all --output-format json` to build a code→name lookup). Repeat until prek passes clean.

The helper script can parse ruff JSON output to generate a ready-to-paste block:

```bash
./ac-adopting-ruff/scripts/discover_violations.py [path]
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

## Syncing with Main

Before requesting final review, bring the latest changes from main into your branch. This is straightforward but the ours/theirs semantics flip between merge and rebase — follow the steps exactly.

The idea: conflicts are purely formatting-related, so accept main's version of every conflicting file, then let prek reformat everything.

### Option A: Merge main into your branch

```bash
git fetch
git merge origin/main
# Conflicts? Accept main's version:
git checkout --theirs .
prek run --all-files
git commit -a
git push
```

### Option B: Rebase onto main

```bash
git fetch
git rebase origin/main
# Conflicts? Accept main's version (ours = main during rebase):
git checkout --ours .
prek run --all-files
git add .
git rebase --continue
# Repeat for each conflicting commit until rebase completes
git push -f
```

**Why the flag flips:** During `git merge`, "theirs" is main. During `git rebase`, git replays your commits on top of main, so "ours" is main. In both cases, we want main's content to win.

**Why `git add` during rebase:** After `git checkout --ours`, the files are still marked as conflicting. `git add .` marks them resolved so `git rebase --continue` can proceed.

## Phase 2: Rule-by-Rule Enforcement

After bootstrap MR is merged. **One worktree and one MR per rule.**

### Workflow per rule

```bash
# 0. Create worktree from main (bootstrap MR must be merged first)
git worktree add <project>-ruff-<CODE> -b ruff-<CODE> origin/main
cd <project>-ruff-<CODE>
```

```bash
# 1. Remove the first rule from lint.ignore in pyproject.toml

# 2. Run prek — it auto-fixes what it can (--fix is in the hook config)
prek run --all-files

# 3. Fix remaining violations manually

# 4. Verify
prek run --all-files
```

### Commit format

```text
refactor: enforce ruff <CODE> (<rule-name>)
```

### Prioritization

1. **Auto-fixable rules** — fast, low risk
2. **Low violation count** — quick to resolve
3. **High-value rules** (bug detection, security) — worth the effort

### Per-file ignores

Some rules are valid globally but wrong in specific contexts. Use per-file-ignores instead of disabling globally:

```toml
# Tests: assert, magic values, private access are inherent to testing.
lint.per-file-ignores."tests/**/*.py" = [
  "S101",    # assert
  "PLR2004", # magic-value-comparison
  "SLF001",  # private-member-access
]

# Migrations: generated code.
lint.per-file-ignores."**/migrations/*.py" = [
  "E501",    # line-too-long
]
```

When using per-file-ignores, the rule IS enforced globally — it's just relaxed for specific paths. Remove it from `lint.ignore`.

### Permanently disabled rules

Some rules will never apply. Keep them in a clearly labeled section:

```toml
# --- Permanently disabled (not applicable to this project) ---
lint.ignore = [
  "CPY001", # missing-copyright-notice
]
```

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

If the team wants to minimize reformatting churn, configure ruff to produce
near-identical output to black + isort. Useful when:

- The codebase is large and a full reformat creates painful merge conflicts
- Colleagues have long-lived branches in flight
- The team prefers incremental style changes over a clean break

### How it works

Ruff's formatter without `preview` mode tracks **black stable** output.
Ruff's isort implementation defaults to **isort with `profile = "black"`** behavior.
The remaining gap is closed with a handful of explicit settings.

### Configuration

Use this instead of the default step 4 configuration. The `lint.ignore`,
`lint.extend-ignore`, and pre-commit setup remain identical.

```toml
[tool.ruff]
target-version = "py312"       # match project's minimum Python
line-length = 88               # match your old black line-length (black default is 88)
fix = true
lint.select = ["ALL"]
lint.preview = true

# lint.ignore = [...]          (populated in step 5, same as clean-break flow)
# lint.extend-ignore = [...]   (formatter-conflicting rules, same as default flow)

# --- Formatter: match black stable output ---
[tool.ruff.format]

quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false
line-ending = "auto"
docstring-code-format = false
preview = false                # critical — format.preview is independent of lint.preview

# --- Import sorting: match isort with profile="black" ---
[tool.ruff.lint.isort]
combine-as-imports = true      # only if old isort config had combine_as_imports = True
split-on-trailing-comma = true

```

**TOML ordering matters:** All inline `lint.*` keys (like `lint.ignore`, `lint.extend-ignore`)
must appear under `[tool.ruff]` **before** any subsection headers (`[tool.ruff.format]`,
`[tool.ruff.lint.isort]`, `[tool.ruff.lint.per-file-ignores]`). TOML assigns keys to the
most recent section header, so placing `lint.ignore` after `[tool.ruff.lint.per-file-ignores]`
will silently misparse it.

### Settings explained

| Setting | Why | Notes |
|---------|-----|-------|
| `line-length` | Must match old black config | Black default is 88. Mismatching this is the #1 source of unwanted reformatting. |
| `format.preview = false` | Non-preview formatter tracks black stable | `lint.preview` and `format.preview` are **independent** — preview lint rules are fine. |
| `format.exclude` | Replaces black's `extend-exclude` | Uses glob patterns (not regex like black). |
| `format.skip-magic-trailing-comma = false` | Respects trailing commas (black default) | A trailing comma forces multi-line formatting. |
| `format.docstring-code-format = false` | Black stable does not format code in docstrings | Set `true` only if you want ruff's extra feature. |
| `isort.combine-as-imports` | Ruff defaults to `false` | Only set `true` if your old isort config explicitly had it. |
| `isort.split-on-trailing-comma` | Matches black-profile trailing comma handling | Default is `true`; explicit for documentation. |

### How to audit your old config

Before configuring, extract the old settings from pyproject.toml / setup.cfg:

```bash
BASE=$(git merge-base HEAD origin/main)

# Check what black was configured with
git show "$BASE":pyproject.toml | grep -A 10 '\[tool.black\]'

# Check what isort was configured with
git show "$BASE":pyproject.toml | grep -A 10 '\[tool.isort\]'
```

Map each old setting to its ruff equivalent:

| Old setting (black) | Ruff equivalent |
|---------------------|-----------------|
| `line-length = N` | `[tool.ruff] line-length = N` |
| `target-version = ["py3X"]` | `[tool.ruff] target-version = "py3X"` |
| `extend-exclude = "pattern"` | `[tool.ruff.format] exclude = ["pattern"]` |
| `skip-magic-trailing-comma = true` | `[tool.ruff.format] skip-magic-trailing-comma = true` |

| Old setting (isort) | Ruff equivalent |
|---------------------|-----------------|
| `profile = "black"` | Default behavior (no setting needed) |
| `combine_as_imports = True` | `[tool.ruff.lint.isort] combine-as-imports = true` |
| `extend_skip = [...]` | `[tool.ruff.lint.per-file-ignores]` |
| `known_first_party = ["myapp"]` | `[tool.ruff.lint.isort] known-first-party = ["myapp"]` |
| `known_third_party = ["django"]` | `[tool.ruff.lint.isort] known-third-party = ["django"]` |
| `force_single_line = True` | `[tool.ruff.lint.isort] force-single-line = true` |
| `sections = [...]` | `[tool.ruff.lint.isort] section-order = [...]` |

### Unavoidable differences

Even with full compatibility config, ruff produces slightly different output
than black + isort. These are architectural and have no configuration toggle:

- **F-string formatting** — ruff normalizes whitespace and quotes inside f-string expressions; black leaves them untouched
- **Implicit string concatenation** — ruff joins implicit concatenations that fit on one line more aggressively
- **Trailing comments** — minor differences in line-breaking decisions near trailing comments
- **Import aliasing** — ruff groups non-aliased imports together then places aliased imports separately; isort interleaves them at each alias boundary
- **Pragma comments** (`# type:`, `# noqa:`) — ruff ignores their width when computing line length

These differences are cosmetic and small on a codebase already formatted by black + isort.

## Common Mistakes

- **Enabling multiple rules in one MR** — harder to review, useless for git bisect
- **Missing rule name comment** — `"D100",` alone is meaningless; always add `# undocumented-public-module`
- **Disabling globally when per-file-ignores suffice** — `S101` (assert) should only be ignored in tests, not everywhere
- **Not running `prek run --all-files`** — always use prek, never call ruff directly
- **Mixing up `format.preview` and `lint.preview`** — they are independent; `lint.preview = true` is fine with `format.preview = false`
- **Wrong `line-length` in compatibility mode** — must match old black config exactly or you get massive reformatting
