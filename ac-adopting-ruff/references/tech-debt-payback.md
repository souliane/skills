# Phase 3 — Paying Back Ruff Tech Debt

Recurring, session-sized cleanup for projects that adopted the "changed files
only" approach (Phase 2A) and have accumulated a large `per-file-ignores`
block. Each session aims for one small MR — either one file cleaned (Mode A)
or one rule dropped across many files (Mode B). Stop as soon as anything
starts to look like real refactoring.

## When to invoke

Phase 3 triggers on **ruff-specific** tech-debt phrasing only. Do NOT fire on a
generic "pay back tech debt" — that's a broader ask and could mean anything
(dead code, slow queries, TODOs, stale deps). Require one of these signals:

- "pay back **ruff** tech debt" / "pay down **ruff** tech debt"
- "clean up ruff ignores" / "clean up per-file-ignores"
- "reduce per-file-ignores" / "shrink per-file-ignores"
- "unignore `<file>`" / "unignore `<rule>`"
- The user names a ruff rule code and asks to reduce its footprint

If the user says only "pay back tech debt" without mentioning ruff,
per-file-ignores, or a rule code, **ask** whether they mean ruff tech debt
before invoking Phase 3. Other forms of tech debt are out of scope for this
skill.

Do **not** invoke Phase 3 during a feature MR — it's a standalone cleanup. If
the user is fixing a bug and notices stale ignores on the same file, resist
the urge to bundle: finish the bug MR, then open a Phase 3 MR.

## Principle

Every session produces **one small MR**. If the target starts to need real
refactoring (new abstractions, API changes, multi-file moves, retyping a
500-line module), **stop** — restore the ignore, pick a smaller target. The
goal is the sum of many small wins, not one big push.

## Step 0: Decide Mode A or Mode B

Ask the user, or pick the default:

| Mode | Goal | Best when |
|------|------|-----------|
| **A — File-focused** | Delete or shrink one file's ignore entry | The user names a specific file, or the codebase has a few long/ugly entries |
| **B — Rule-focused (default)** | Drop one rule from as many files as possible | The codebase has many entries (>20) and a handful of rules recur across them |

Default is Mode B when `per-file-ignores` has more than 20 entries — a single
rule removal then pays off across many entries at once.

## Step 1: Scan

### 1a. Parse the current ignores

Read `[tool.ruff.lint.per-file-ignores]` from `pyproject.toml` into a
`{file_glob: [rule_codes]}` table. Comments after each rule (e.g.
`# type annotations — legacy signatures`) are often the strongest signal
about whether the ignore is fixable or structural — preserve them during analysis.

### 1b. Get real violation counts

`ruff check` respects `per-file-ignores`, so a naive scan hides the debt.
Temporarily clear `per-file-ignores` to see the real numbers, then restore:

```bash
# Make a backup first
cp pyproject.toml pyproject.toml.bak

# Manually remove [tool.ruff.lint.per-file-ignores] block (or comment it out)
# Then:
ruff check . --output-format json --no-fix --preview > /tmp/techdebt-scan.json

# Restore
mv pyproject.toml.bak pyproject.toml
```

Aggregate `/tmp/techdebt-scan.json` into:

- `{(file, rule): violation_count}` — how much each currently-ignored rule would flag
- `{rule: auto_fixable}` — from `ruff rule <CODE> --output-format json` (`fix_availability` field)

### 1c. Classify each (file, rule) pair

| Class | Definition | Action |
|-------|-----------|--------|
| **Stale** | Rule is ignored but violation count is 0 | Free win — drop unconditionally |
| **Easy auto** | Auto-fixable, ≤20 violations in the file, rule NOT in skip list | Good candidate |
| **Easy manual** | Manual-fix, ≤5 violations, rule NOT in skip list | Good candidate if fixes are ≤5 lines each |
| **Skip** | Rule in skip list, OR file >1000 LoC with structural rules, OR comment says "structural/framework/dispatch/out of scope" | Leave alone |

## Step 2: Skip list — leave these alone

These rules typically demand real refactoring. Do NOT try to fix them in a
Phase 3 session — they deserve a dedicated ticket, a scoped refactor, and
careful review:

- **Structural complexity:** `C901`, `PLR0904`, `PLR0911`, `PLR0912`, `PLR0913`, `PLR0914`, `PLR0915`, `PLR0916`, `PLR0917`, `PLR1702`
- **API signature commitments on public/framework surfaces:** `FBT001`, `FBT002`, `ANN001`/`ANN201`/`ANN202` on DRF serializer methods, Django `RunPython` callables, dispatch classes
- **Type annotations at scale:** any `ANN*` on files >500 LoC — pair with `ty` / `mypy` in a dedicated typing MR
- **Documentation:** `D*` family — a docs pass, not a stealth cleanup

Also skip any ignore whose inline comment says:

- "structural" / "inherent" / "by design"
- "framework-mandated" / "DRF requires" / "Django mandates"
- "dispatch" / "dispatched by name"
- "pre-existing — dedicated techdebt" / "out of scope"
- any ticket reference (the author already scheduled it)

## Step 3: Always start with stale ignores

Before picking between Mode A and Mode B, drop every **stale** entry found
in Step 1c. These are free — the code has evolved and no longer triggers the
rule. Do this in its own tiny MR at the start of the session (or fold it
into the Mode A/B MR if the scope is small).

```text
chore: drop stale ruff ignores

These rules no longer trigger violations in the pinned files — the
underlying code has evolved since the ignore was added.
```

## Step 4 — Mode A: File-focused

```bash
git worktree add <project>-techdebt-<file-slug> -b techdebt-ruff-<file-slug> origin/main
cd <project>-techdebt-<file-slug>
```

1. In `pyproject.toml`, remove from the file's entry every rule that is
   **stale**, **easy auto**, or **easy manual**. Leave skip-list rules in place.
2. `prek run --all-files` — ruff auto-fixes what it can.
3. **Review the diff** against § Dangerous Auto-Fixes in the main skill file.
4. Fix remaining violations manually — but only if each is a few lines. If a
   rule drags in architectural change (new abstraction, signature change,
   multi-file refactor), **restore that one rule to the ignore list** and
   move on. This is the single most important discipline in Phase 3.
5. If the file's entry is now empty, delete the key entirely. If some rules
   remain, leave a one-line comment on WHY they stay (saves the next Phase 3
   pass from re-evaluating).
6. `prek run --all-files` must pass cleanly.

Commit:

```text
chore: shrink ruff ignores for <file>

Dropped <N> ignore(s): <RULE_CODES>.
Kept <remaining rules> — require structural refactoring (<brief reason>).
```

## Step 5 — Mode B: Rule-focused

```bash
git worktree add <project>-techdebt-<RULE> -b techdebt-ruff-<RULE> origin/main
cd <project>-techdebt-<RULE>
```

1. Pick the target rule. Best picks:
   - Auto-fixable
   - Appears in ≥5 per-file entries
   - Not in the skip list
   - Low violation count per file (≤20)
2. Across all `per-file-ignores` entries, remove `<RULE>` wherever it appears.
3. `prek run --all-files` — auto-fix.
4. **Review the diff.** § Dangerous Auto-Fixes in the main skill file.
5. For each file that still has violations after auto-fix:
   - Trivial manual fix (≤5 lines)? Fix it.
   - Otherwise, **put the rule back for that one file only**. Do not try to
     force a refactor into this MR.
6. `prek run --all-files` must pass cleanly.
7. Sanity check — the rule's footprint has shrunk:

   ```bash
   git diff pyproject.toml | grep -c '"<RULE>"'
   ```

Commit:

```text
chore: drop ruff <RULE> (<rule-name>) from <N> per-file ignores

Auto-fixable violations cleaned. Files requiring structural refactoring
keep the ignore (<brief list>).
```

## Step 6: Scope discipline

A healthy Phase 3 MR:

| Metric | Target |
|--------|--------|
| Files touched | ≤ 10 |
| Ignores removed | 1–5 entries (Mode A) or 1 rule across 3–15 files (Mode B) |
| Time spent | ≤ 30 minutes |
| New `# noqa` comments | Ideally 0; at most a handful with a specific reason |
| New TODO comments | 0 — either fix it or leave the ignore |

If the session would exceed this scope, **stop and split**. Two focused MRs
are always better than one sprawling one.

## Anti-patterns

- **Bundling into a feature MR.** Tech-debt cleanup belongs in its own MR so
  reviewers can focus on intent, not noise.
- **Adding `# noqa: <RULE>` everywhere instead of per-file-ignores.** Moving
  the ignore from `pyproject.toml` to scattered `# noqa` lines is lateral
  movement, not cleanup — it just hides the debt.
- **"While I'm here, let me also fix…"** Phase 3 is intentionally narrow.
  Other cleanups become their own sessions.
- **Silently restoring a rule without a comment.** If you put a rule back for
  a specific file during cleanup, leave a short comment explaining why — next
  session will waste time re-evaluating otherwise.
- **Chasing the whole list.** A single marathon Phase 3 session that touches
  100 files is exactly the anti-pattern this phase is designed to avoid.
  Short, repeated passes only.

## Relationship to Phase 2

Phase 3 is only relevant to projects that went through **Phase 2A** (changed
files only). Projects that used **Phase 2B** (progressive enforcement) have
already paid this debt down one rule at a time during enforcement, so their
`per-file-ignores` should stay small.
