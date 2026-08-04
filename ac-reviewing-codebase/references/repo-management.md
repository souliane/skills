# Repo Management Workflows — read when handling delivery, squashing, infrastructure, or backporting

Standalone workflows that can be invoked independently or as part of Phase 6 (Regression & Delivery).

---

## Workflow 1 — Delivery Status

Quick overview of what needs attention across all managed repos.

**Steps:**

1. Load `~/.ac-reviewing-codebase` config (or ask user if missing).
2. For each repo discovered via `MANAGED_REPOS` regex:
   - Check if the repo exists and is a git repo.
   - Detect the main branch via `git config init.defaultBranch` (fallback: `main`).
   - Show current branch.
   - Show unpushed commits (`git log --oneline @{upstream}..HEAD`). If no upstream, show all commits on branch.
   - Show uncommitted changes (`git status --short`) — show the actual summary, not just a count.
   - List **non-main branches** (`git branch --no-merged <main>`) — may contain in-progress work.
   - Show **stash count** (`git stash list | wc -l`).
   - Show stale branches (merged but not deleted).
3. Present a summary table with details.

**Output format:**

```text
Repo           Branch  Unpushed  Dirty  Status
project-a      main    2         0      needs push
  branches: feat/e2e-parallel-workers-122
skills         main    5         1      needs push, dirty
  M ac-reviewing-codebase/SKILL.md
blog           main    0         0      clean
```

Non-main branches and stashes shown only when present. Clean repos show `clean` with no detail lines.

---

## Workflow 2 — Squash & Prepare

Squash related unpushed commits into clean, human-sized units per repo. This is the **canonical source of truth** for squash rules — other skills reference this section.

**Squash Rules (Non-Negotiable):**

1. **Never rewrite pushed history.** Before any squash, check `git log origin/<branch>..HEAD` to identify the safe range. Only commits not yet at origin are candidates.
2. **Group by topic.** Related commits become one commit. Unrelated commits stay separate.
3. **Keep human-sized commits.** A single commit should be reviewable in one sitting. If squashing would produce a commit touching 20+ files across unrelated concerns, split rather than squash.
4. **Squash integrity check (Non-Negotiable).** Before any rewrite, save the tip: `echo $(git rev-parse HEAD) > /tmp/squash-tip-$(basename $(pwd))`. After the **final** commit, verify: `git diff $(cat /tmp/squash-tip-...)..HEAD` is empty. If there is any diff, the rewrite lost or introduced changes — abort and investigate.
5. **Respect `auto_squash`.** When `true`, squash automatically. When `false` (default), present the plan and wait for approval.
6. **Each skill squashes its own commits before chaining.** Previous skills in the chain have already squashed their own work.

**Steps:**

1. Run delivery status (Workflow 1) to identify repos with unpushed commits.
2. For each repo with unpushed commits:
   - List unpushed commits with `--stat`.
   - Propose a squash plan: which commits to group, proposed messages.
   - Execute squash (with user approval unless `auto_squash=true`).
   - Verify integrity after each squash.
3. Show final status summary.

---

## Workflow 3 — Infrastructure Audit

Compare and harmonize `.pre-commit-config.yaml`, `pyproject.toml`, `.editorconfig`, and utility scripts across managed repos.

### Phase 1 — Scope

Identify repos to compare (via `MANAGED_REPOS`) and a reference repo (most complete config).

### Phase 2 — Read & Compare

| File | What to compare |
|------|----------------|
| `.pre-commit-config.yaml` | Hook inventory, tool versions, phase ordering, file scoping, rev format (SHA + tag comment) |
| `pyproject.toml` | `[tool.ruff]`, `[tool.ty]`, `[tool.pytest]`, `[tool.coverage]`, `[tool.codespell]` |
| `.editorconfig` | Charset, line ending, indent style/size, markdown settings |
| Utility scripts | Whether the shared hooks published by `skill-repo-boilerplate` are consumed, and pinned to the same rev |

### Phase 3 — Classify Divergences

| Classification | Action |
|----------------|--------|
| **Drift** — no reason for difference | Align to reference |
| **Intentional** — repo-specific need | Keep, add comment |
| **Stale** — was intentional, reason gone | Align, remove stale comment |
| **Unclear** | Ask the user |

### Phase 4 — Present Findings

Structured comparison table grouped by file, then by setting.

### Phase 5 — Implement

After user approval: apply fixes, run `ruff check --no-fix`, run tests, **post-implementation convergence check** (re-read each config and diff against reference).

---

## Workflow 4 — Boilerplate Factorization & Backport

Two directions: **extract** common patterns into boilerplate repos, and **propagate** boilerplate changes to dependents.

### 4a. Extraction — find boilerplate candidates

During every review, actively scan for patterns that appear in 2+ repos but are NOT yet in a boilerplate:

- Same CI pipeline structure, same pre-commit config shape, same utility scripts
- Same project skeleton (directory layout, base configs, test setup)
- Same Dockerfile or docker-compose patterns

**When found:** propose extracting to a boilerplate repo (existing or new). Present the common pattern, the repos that share it, and the divergences. Ask the user before creating a new boilerplate.

### 4b. Backport — propagate boilerplate changes

Propagate changes from boilerplate repos to their dependents (via `BOILERPLATE_MAP` config).

**Steps:**

1. For each boilerplate repo with recent changes, identify changed files.
2. For each dependent repo, diff and classify: already aligned, needs backport, intentionally different.
3. Present backport plan. **Backport ≠ blind copy** — ask about unclear differences.
4. Apply changes and run verification (lint, tests).
5. Commit backport changes in each dependent repo.

### 4c. Alignment — maximize similarity

Even when full boilerplate extraction isn't practical, repos serving similar roles should be as similar as possible. During infra audit (Workflow 3), flag gratuitous differences between sibling repos — same tool, different config; same purpose, different directory layout. Propose alignment to the most complete/correct variant.

---

## Workflow 5 — Architectural Health Check

Deep cross-repo analysis acting as a **software architect** for the portfolio.

### 5a. Dependency Audit

- List all dependencies with current versions.
- Check for outdated dependencies, security vulnerabilities.
- Recommend upgrades with breaking change warnings.
- Check for unused dependencies.

### 5b. Cross-Repo Code Analysis

- **Duplication detection** across repos.
- **Dead code** — unused modules, scripts, config entries.
- **Shared patterns** — when 3+ repos implement the same pattern differently, recommend standardization.

### 5c. Tech Stack & Framework Review

- **Tooling freshness** — flag deprecated tools with modern alternatives.
- **Framework versions** — recommend upgrade paths.
- **Architectural patterns** — review structure, module boundaries, dependency graph.

### 5d. Consolidation Recommendations

- **Merge candidates** — tightly coupled repos.
- **Split candidates** — repos serving unrelated purposes.
- **Repo lifecycle** — flag untouched repos.

All recommendations are advisory with effort estimates and impact assessment.

---

## Infrastructure Rules

### SHA Revs with Tag Comments (Non-Negotiable)

All `.pre-commit-config.yaml` entries must use git SHA as `rev`, with tag as comment:

```yaml
rev: 83d9cd684c87d95d656c1458ef04895a7f1cbd8e  # v8.30.1
```

### Phase Comments in Pre-Commit Config (Non-Negotiable)

Hooks organized in numbered phases (Phase 1–10). Not all repos need all phases, but numbering is consistent.

### Ruff Config Baseline

Canonical ruff config documented in `ac-python/references/testing-and-tooling.md`. Key: `lint.select = ["ALL"]`, `lint.fixable = ["ALL"]`, `lint.preview = true`.

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

- `target-version` (ruff) is a **lint setting** — no runtime requirement.
- `requires-python` in `[project]` is a **runtime requirement**.
- These can differ.

### Shared Scripts Are Hooks, Not Copies

`skill-repo-boilerplate` owns the repo-level scripts and publishes them in its
`.pre-commit-hooks.yaml`. Repos consume them instead of copying the files:

```yaml
  - repo: https://github.com/souliane/skill-repo-boilerplate
    rev: <sha>  # <date>
    hooks:
      - id: update-readme-skills
      - id: bump-pyproject-deps-from-lock-file
        stages: [manual]
```

A copy of one of these scripts in a repo's own `scripts/` directory is a finding:
four identical copies of `bump-pyproject-deps-from-lock-file.py` and three drifted
copies of `update_readme_skills.py` is how the fleet got here.

---

## Review Checklists

### Infrastructure Audit

- [ ] Same tool versions across repos
- [ ] SHA revs with tag comments in all `.pre-commit-config.yaml`
- [ ] Phased structure in all pre-commit configs
- [ ] Hook inventories match
- [ ] Ruff, ty/mypy, pytest, editorconfig settings match
- [ ] Shared boilerplate hooks consumed (no local copies of the shared scripts)
- [ ] All divergences aligned or documented

### CI Pipeline Comparison

Compare CI configs (`.github/workflows/`, `.gitlab-ci.yml`) alongside pre-commit hooks and pyproject.toml. Flag missing or divergent configs.

### Delivery

- [ ] No unpushed commits left unintentionally
- [ ] All commits human-sized and topically grouped
- [ ] No pushed history rewritten
- [ ] Squash integrity verified
