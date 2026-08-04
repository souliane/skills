# Phase 2 Enforcement — read when starting rule enforcement after bootstrap

## Phase 2A: Changed Files Only

Goal: enable all rules immediately. Existing violations are fixed naturally as engineers touch files.

This approach is ideal when:

- Progressive enforcement creates too many MRs and merge conflicts
- The team wants all rules active without a long migration
- The codebase is large enough that dedicated enforcement MRs are disruptive

### 1. Create worktree

```bash
git worktree add <project>-ruff-changed-only -b ruff-changed-only origin/main
cd <project>-ruff-changed-only
```

### 2. Review permanently disabled rules

Before clearing `lint.ignore`, review the list for rules that should **never** apply
to this project. Move those to `lint.extend-ignore` with a comment explaining why.
Common examples:

- `CPY001` (missing-copyright-notice) — project doesn't use copyright headers
- `INP001` (implicit-namespace-package) — project intentionally omits `__init__.py`

### 3. Enable all rules

Clear `lint.ignore` entirely — remove all Phase 2 queue rules:

```toml
# --- All rules active (violations checked on changed files only) ---
lint.ignore = []
```

Keep `lint.extend-ignore` (permanently disabled + formatter-conflicting) and
`lint.per-file-ignores` unchanged.

### 4. Adapt CI to check changed files only

The key: `ruff-check` runs only on files changed in the MR/branch.
All other hooks (including `ruff-format`) still run on all files.

Use the `SKIP` environment variable to exclude `ruff-check` from the
`--all-files` run, then run `ruff-check` separately on changed files:

```yaml
# GitLab CI example
variables:
  GIT_DEPTH: "0"  # full history needed for accurate diff
script:
  - |
    TARGET="${CI_MERGE_REQUEST_TARGET_BRANCH_NAME:-${CI_DEFAULT_BRANCH:-main}}"
    git fetch origin "$TARGET"
    CHANGED_PY=$(git diff --name-only --diff-filter=d "origin/$TARGET...HEAD" -- '*.py')
    if [ -n "$CHANGED_PY" ]; then
      prek run ruff-check --files $CHANGED_PY
    fi
    SKIP=ruff-check prek run --all-files
```

**How this works:**

- `prek run ruff-check --files <list>` — runs `ruff-check` on specific files only
- `SKIP=ruff-check prek run --all-files` — runs every hook **except** `ruff-check` on all files
- Locally, `prek` (without `--all-files`) already only checks staged files — no change needed

**Adapt for your CI system:** Replace `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` /
`CI_DEFAULT_BRANCH` with your CI's equivalents (e.g., `GITHUB_BASE_REF` for
GitHub Actions).

### 5. Verify

Run `prek` on a few changed files to confirm the new rules work:

```bash
prek run ruff-check --files $(git diff --name-only --diff-filter=d origin/main...HEAD -- '*.py')
```

Note: `prek run --all-files` **will fail** on the full codebase (existing violations) —
this is expected and confirms rules are active.

### 6. Create MR

```text
chore: enable all ruff rules, check changed files only

- Clear lint.ignore — all rules now active
- CI checks ruff-check on changed files only
- Existing violations fixed naturally as files are touched
- ruff-format and other hooks still run on all files
```

### 7. Message to colleagues

```text
This MR enables all remaining ruff lint rules. Existing code is not
affected — ruff-check now only runs on files changed in each MR.

Locally, pre-commit already only checks your staged files, so nothing
changes in your workflow.

In CI, if your MR touches a file with existing violations, you'll need
to fix them. This is intentional — violations are cleaned up gradually
as files are touched, without dedicated migration MRs.

ruff-format and all other hooks still run on all files as before.
```

### Trade-offs

| Aspect | Changed files only | Progressive enforcement |
| -------- | ------------------- | ------------------------ |
| Migration MRs | 1 (config only) | Many (one per rule/batch) |
| Merge conflicts | None | Each MR conflicts on `pyproject.toml` |
| Time to full coverage | Gradual (depends on file churn) | Predictable (you set the pace) |
| Developer friction | Touching a file may surface unrelated violations | None (violations pre-fixed) |
| Risk | Low (no auto-fix on untouched code) | Medium (auto-fix can change semantics) |
| Long-term drift | `per-file-ignores` tends to grow (path of least resistance when editing a file is to pin the rule, not fix the violation) — plan a recurring **Phase 3 — Paying Back Ruff Tech Debt** session to shrink it | Minimal drift, no cleanup phase needed |

**Planning for Phase 3.** If you pick this approach, assume you will need a
recurring cleanup pass — set a reminder (quarterly is reasonable) to run a
ruff tech-debt session. See the Phase 3 section in the main skill file.

## Phase 2B: Progressive Enforcement

### 0. Ask the user (continued)

Ask these additional questions (one at a time):

1. **MR strategy?**
   - **One MR per rule** — clean git history, easy review, easy to revert. Best for high-risk or manual-fix rules.
   - **Grouped rules (Recommended)** — batch multiple rules into one MR until a change threshold is reached. Reduces MR overhead for low-risk auto-fixable rules.

2. **Change threshold?** (only if grouped)
   - Default: **50** changed lines per MR.
   - The agent enables rules one at a time, running `prek run --all-files` after each. If the cumulative number of changed lines stays below the threshold, the next rule is added to the same MR. Once the threshold is reached (or exceeded), the MR is finalized and a new one starts.

### 1. Scan and prioritize

Run a violation scan to build the enforcement queue. The scan **only reads
rules from the Phase 2 queue section** — it ignores permanently disabled rules
and formatter-conflicting rules in `lint.extend-ignore`.

Phase 1 creates this structure in `pyproject.toml`:

```toml
# --- To enforce: Phase 2 queue (enable one MR at a time) ---
lint.ignore = [
  "C401",   # unnecessary-generator-set
  "B904",   # raise-without-from-inside-except
  ...
]

# --- Permanently disabled (not applicable to this project) ---
# lint.ignore is additive — rules here stay disabled forever.
#   "CPY001", # missing-copyright-notice

# --- Formatter-conflicting rules (always disabled with ruff format) ---
lint.extend-ignore = [
  "COM812", # missing-trailing-comma
  ...
]
```

The two section markers (`# --- To enforce:` and `# --- Permanently disabled`)
are the contract between Phase 1 and Phase 2. The scan reads only between them.

Run the scan script from the target project directory:

```bash
./ac-adopting-ruff/scripts/scan_queue.py [path]
```

The script temporarily clears `lint.ignore` to get real violation counts (ruff
respects `lint.ignore` even with `--select`), then restores the file. Use
`--json` for machine-readable output.

Prioritization order:

1. **Zero-violation rules** — config-only if truly zero (verified with cleared `lint.ignore`). Always batch into one MR.
2. **Auto-fixable rules** (sorted by violation count ascending) — fast, low risk.
3. **Partially auto-fixable rules** — auto-fix first, then manual cleanup.
4. **Manual-only rules** — one per MR unless very low count.
5. **High-value rules** (bug detection, security) — worth the effort even if high count.

### 2. Create worktree

```bash
# For single-rule MRs:
git worktree add <project>-ruff-<CODE> -b ruff-<CODE> origin/main
cd <project>-ruff-<CODE>

# For grouped MRs (use batch number):
git worktree add <project>-ruff-batch-<N> -b ruff-batch-<N> origin/main
cd <project>-ruff-batch-<N>
```

### 3. Enforce rules (single or grouped)

**Single-rule workflow:**

```bash
# 1. Remove the rule from lint.ignore in pyproject.toml
# 2. Run prek — auto-fixes what it can
prek run --all-files
# 3. MANDATORY: review the diff for semantic correctness (see § Dangerous Auto-Fixes)
git diff
# 4. Fix remaining violations manually
# 5. Verify
prek run --all-files
```

**Mandatory diff review (Non-Negotiable):** After every auto-fix run, review
`git diff` for the patterns listed in § Dangerous Auto-Fixes. Do NOT commit
auto-fixed code without reviewing the diff. This step catches semantic changes
that pass linting but break runtime behavior.

**Grouped-rule workflow (greedy fill):**

```bash
# Start with the first rule in the queue
# 1. Remove the rule from lint.ignore in pyproject.toml
# 2. Run prek — auto-fixes what it can
prek run --all-files
# 3. MANDATORY: review git diff for semantic correctness (see § Dangerous Auto-Fixes)
git diff
# 4. Fix remaining violations manually if needed
# 5. Run prek again to verify
prek run --all-files
# 6. Check cumulative changed lines:
git diff --stat | tail -1   # e.g. "8 files changed, 23 insertions(+), 19 deletions(-)"
# 7. If total changes < threshold → go back to step 1 with the next rule
# 8. If total changes >= threshold → stop adding rules, finalize this MR
```

The goal is to fill each MR up to (but not far over) the threshold. If adding a
rule would push the MR well past the threshold, include it anyway — the threshold
is a soft target, not a hard limit.

### Commit format

```text
# Single rule:
refactor: enforce ruff <CODE> (<rule-name>)

# Grouped rules:
refactor: enforce ruff <CODE1>, <CODE2>, <CODE3>
```

For grouped MRs, the commit body should list each rule with its name:

```text
refactor: enforce ruff C401, PIE810, RUF027, FLY002, FURB171

- C401 (unnecessary-generator-set)
- PIE810 (multiple-starts-ends-with)
- RUF027 (missing-f-string-syntax)
- FLY002 (static-join-to-f-string)
- FURB171 (single-item-membership-test)
```

### Prioritization

1. **Zero-violation rules** — config-only, always first, always grouped into one MR
2. **Auto-fixable rules** (sorted by violation count ascending) — fast, low risk
3. **Partially auto-fixable rules** — auto-fix then manual cleanup
4. **Manual-only rules** — higher effort, review carefully
5. **High-value rules** (bug detection, security) — worth the effort

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

Some rules will never apply. Move them from the Phase 2 queue to the
permanently disabled section. The Phase 2 scan ignores everything below
this marker:

```toml
# --- Permanently disabled (not applicable to this project) ---
# lint.ignore is additive — rules here stay disabled forever.
#   "CPY001", # missing-copyright-notice
```

Keep them commented out (they're already in `lint.ignore` above if needed)
or in a second `lint.ignore` assignment — TOML merges arrays. The key point
is they must be **below** the `# --- Permanently disabled` marker so the
scan excludes them.

## Minimizing Merge Conflicts with Parallel Worktrees

When creating multiple enforcement MRs in parallel (multiple worktrees at once),
conflicts are inevitable on `pyproject.toml` (every MR removes rules from
`lint.ignore`). The goal is to minimize **code file conflicts** — i.e., two MRs
touching the same `.py` file.

### Strategy

1. **Scan with `lint.ignore` cleared.** The default scan (`ruff check --select ALL`)
   respects `lint.ignore`, so disabled rules report zero violations. To get real
   counts, temporarily empty `lint.ignore` before scanning, then restore it:

   ```python
   # In pyproject.toml, temporarily set: lint.ignore = []
   # Then run: ruff check --select <CODES> --preview --no-fix --output-format json .
   # Restore pyproject.toml after scanning.
   ```

2. **Group rules by file footprint.** After scanning, collect the set of files
   each rule touches. Pick rules for the same MR when their file sets are
   **disjoint or nearly disjoint** from rules in other MRs.

3. **Isolate high-churn files.** Some files (large utility modules, base classes)
   attract violations from many rules. When a file appears in >3 candidate rules,
   accept that it will overlap and put the rules touching it in the **same** MR
   rather than spreading the conflict across MRs.

4. **pyproject.toml conflicts are trivial.** Every MR removes different lines from
   `lint.ignore`. After one MR merges, the others resolve via:

   ```bash
   git fetch && git merge origin/main
   # Accept main's pyproject.toml (it already removed the merged MR's rules):
   git checkout --theirs pyproject.toml
   # Re-apply this MR's rule removals (the script removes by code, idempotent):
   python3 /tmp/ruff_batch.py <CODES_FOR_THIS_MR>
   prek run --all-files
   git add -A && git commit
   ```

5. **Merge order: smallest MR first.** Fewer files = fewer downstream conflicts.

### Unsolvable overlap

Different rules often apply to the same line (e.g., a function with a lambda
default hits both `B006` and `E731`). When two MRs fix the same line differently,
the second MR to merge gets a conflict on that file. This is harmless — `prek run
--all-files` after merging main will re-apply the correct fix.

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
