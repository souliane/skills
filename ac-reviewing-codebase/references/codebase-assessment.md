# Codebase Assessment — read during Phase A

Deterministic metrics collection + LLM architectural judgment for full codebase health audits.

## Principle

**The goal is 10/10.** Score each dimension honestly, then produce a concrete improvement plan that would bring each score to 10. Not every improvement needs to happen now — but the path to 10 must be visible. If a codebase scores 7 on maintainability, the assessment must list the specific changes that would earn the remaining 3 points.

**Action items are primary, scores are secondary.** Nobody acts on "architecture is a 6." They act on "extract payment logic from the view layer (high impact, medium effort, 4 files)." Scores serve as a coarse trendline across assessments.

## Part 1 — Deterministic Metrics

Run `scripts/cli.py assess` to collect metrics as JSON. The CLI handles:

| Metric | Tool | What it measures |
|--------|------|-----------------|
| **Lint violations** | `ruff check --output-format json` | Rule violations by category and severity |
| **Test coverage** | `coverage json` (if `.coverage` exists) | Line coverage percentage, uncovered files |
| **Cyclomatic complexity** | `ruff check --select C901` | Functions exceeding complexity threshold |
| **TODO/FIXME count** | `grep -rn` | Deferred work items by file |
| **Dependency staleness** | `uv pip list --outdated` (if uv project) | Packages behind latest, security advisories |

**When the CLI is not available** (e.g., reviewing a non-Python codebase), collect equivalent metrics manually:

- Lint: run the project's configured linter
- Coverage: check CI artifacts or run test suite with coverage
- Complexity: use language-appropriate tool (e.g., `radon` for Python, `complexity-report` for JS)
- TODOs: `grep -rn 'TODO\|FIXME\|HACK\|XXX' --include='*.py' --include='*.ts'`
- Dependencies: check package manager's outdated report

### File-hierarchy signals (manual — feed §2h)

Cheap, language-agnostic signals on the **tracked file tree** that surface reorganization candidates. Run over `git ls-files` (never the working tree — skip `.venv`, `node_modules`, build dirs). These are inputs to the §2h architectural judgment, not standalone scores.

```bash
# Root-level file count — a crowded root is the most common smell.
git ls-files | grep -vc '/'

# Files per directory — directories far above the median are split candidates.
git ls-files | sed 's:/[^/]*$::' | sort | uniq -c | sort -rn | head -20

# Max tree depth — over-deep nesting (5+ segments) without reason is a smell.
git ls-files | awk -F/ '{print NF-1}' | sort -rn | head -1

# Oversized modules — files an order of magnitude above the median split.
git ls-files '*.py' | xargs wc -l 2>/dev/null | sort -rn | head -15

# Directories mixing many unrelated file types (low cohesion).
git ls-files | sed 's:/[^/]*$::' | sort -u | while read -r d; do
  n=$(git ls-files "$d/*" | sed 's:.*\.::' | sort -u | grep -c .); echo "$n $d";
done | sort -rn | head -15
```

| Signal | Smell when | Feeds |
|--------|-----------|-------|
| Root-level file count | High (clutter at repo root) | §2h cohesion/scoping |
| Files per directory | A directory far above the median | §2h god-package / split candidate |
| Max tree depth | 5+ segments without clear reason | §2h over-deep tree |
| Oversized modules | A file an order of magnitude above the median | §2h god-module split |
| File-type spread per directory | One directory mixing many unrelated extensions | §2h low-cohesion directory |

A high signal is **evidence, not a verdict** — a monorepo root or a deliberately flat tool legitimately trips some of these. Confirm against §2h judgment before proposing a move.

## Part 2 — Architectural Judgment (LLM-Driven)

After collecting metrics, perform architectural analysis:

### 2a. Naming Consistency

- Are modules, classes, functions, and variables named consistently?
- Do names reveal intent? Are there misleading names?
- Is there a single naming convention (snake_case, camelCase) per language?

### 2b. Separation of Concerns

- Are business logic, data access, and presentation cleanly separated?
- Do modules have a single, clear responsibility?
- Are there "god classes" or "god modules" that do too many things?

### 2c. Abstraction Quality

- Are abstractions at the right level — not too concrete, not too abstract?
- Are there leaky abstractions that expose implementation details?
- Are there unnecessary abstractions (wrappers that add no value)?
- Is there premature generalization (code written for hypothetical future needs)?

### 2d. Module Boundaries & Coupling

- Do modules have clean interfaces? Are dependencies explicit?
- Are there circular dependencies between modules?
- Is coupling appropriate — tightly coupled where cohesion is high, loosely coupled where it's not?

### 2e. Error Handling & Robustness

- Are errors handled at the right level?
- Are there swallowed exceptions or bare `except:` clauses?
- Is the system resilient to partial failures?

### 2f. Test Architecture

- Do tests mirror production code structure?
- Is the test pyramid appropriate (integration > unit for happy paths)?
- Are tests testing behavior or implementation?

### 2g. State & Data Architecture (Single Source of Truth)

The most expensive bugs in stateful systems come from the **same runtime fact being persisted in more than one place** and the copies silently diverging. The §2a–2f lenses do **not** catch this — check it explicitly on every pass. (Real incident this exists to prevent: a workflow orchestrator stored lifecycle/dispatch state in a DB *and* a per-worktree sqlite *and* a registry JSON file *and* an in-memory singleton; each diff was locally clean, each store locally correct, and the divergence cost multiple days across several "looks done" bugs.)

For each piece of **runtime/persisted state** (lifecycle status, ownership, liveness/heartbeat, claims/leases, gate or approval decisions, denormalized aggregates), verify:

- **One authoritative store per fact.** Exactly one store is the source of truth; every other representation (registry/JSON file, pidfile/flock, in-memory dict, denormalized column, cache) is a *derived projection* reconstructible from the authority. A fact persisted in ≥2 co-equal stores with no declared authority is a defect **even if each store is locally correct** — divergence is a *when*, not an *if*.
- **The database wins.** When a DB is one of the stores, the DB row is the arbiter; on any conflict code reconciles *from* the DB and never trusts a file/in-memory/cache value over it. Grep the inverse: a decision read from a file/registry/in-memory flag that a DB row also expresses.
- **Cross-process / cross-session coordination uses DB locks, not files.** State mutated by >1 process or session must be guarded by a DB-level lock, never a pidfile/flock/in-memory flag; RMW on a shared row or `JSONField` must hold the row lock for the whole read-modify-write. (Lock mechanics — `transaction.atomic()` + `select_for_update()`, atomic `update()`/`F()` — live canonically in `ac-django` references/transactions-and-migrations.md §6.6.)
- **Aggregate at the right scope.** A fact owned by an entity must be read aggregated over that entity, not over one arbitrary child record (e.g. a per-ticket gate decision computed from a single one of the ticket's sessions instead of all of them).

**Concrete detectors (run, cite file:line):**

- Same noun written to a model field *and* a file/registry: `rg -n 'open\([^)]*\.json|registry|\.lock\b|pidfile|flock'` cross-referenced against model fields holding the same concept.
- RMW on a status column / `JSONField` with no surrounding lock: a `.save(` (or `setattr` then save) on a model whose field was just mutated, with no `select_for_update`/`atomic` in the same function.
- Liveness / ownership / leadership tracked in a file or in-memory singleton instead of a DB row with a lease/heartbeat column.
- Two repos — or a skill and the code — independently encoding the same state machine or gate rule: extract the state/enum token set from each (`rg -o '\b[A-Z][A-Z_]{3,}\b' <pathA> | sort -u` vs `<pathB>`) and diff them — overlapping-but-unequal sets signal a duplicated rule that has started to drift.

Any hit is **Architecture-dimension** scoring evidence and a ranked improvement item: a multi-store fact with no arbiter **caps the Architecture score** no matter how clean §2a–2f are.

### 2h. File Hierarchy & Module Organization

The signals in Part 1 § "File-hierarchy signals" surface *where* the tree may be wrong; this lens decides *whether* it is and produces the concrete moves. AI-assisted change accretes hierarchy entropy fast — a helper dropped next to its caller, a script left at the repo root, a module that quietly grew into a god-module — and each edit looks locally fine. Assess the **whole tracked tree** (source code *and* every other file type: configs, docs, assets, scripts, fixtures), and **flag reorganization opportunities** so related things are grouped and well-scoped under directories.

**Cohesion & scoping (any file type):**

- **Related files grouped, unrelated concerns separated.** Files that change together or serve one feature belong under one directory; a directory holding several unrelated concerns has low cohesion and should split.
- **Misplaced files.** A module that belongs inside a subpackage but sits beside it; config, scripts, docs, or fixtures scattered at the repo root instead of under `config/`, `scripts/`, `docs/`, `tests/fixtures/`.
- **Root-directory clutter.** A crowded repo root (Part 1 root-level count high) is the most common smell — only genuine top-level entries (README, license, build/lint config, lockfiles, the package dir) belong there.
- **Directory naming consistency.** One convention throughout (e.g. kebab-case dirs, snake_case modules); flag `utils/` next to `helpers/` next to `common/` doing the same job.
- **Over-deep vs over-flat.** Deep nesting (5+ segments) that adds no semantic value is as bad as a flat dump of dozens of files with no grouping. Aim for a balance where each level adds meaning.
- **Assets/config/docs under sensible dirs.** Images, sample data, generated artifacts, and docs each under a clear home, not interleaved with source.

**Python specifics:**

- **God-modules.** A module an order of magnitude larger than its siblings (Part 1 oversized-modules signal) that mixes several responsibilities → split into a package with one module per responsibility.
- **Packages lacking a single clear responsibility.** A package whose name doesn't predict its contents, or that has become a catch-all (`utils`, `misc`, `core` holding unrelated things).
- **Flat-vs-nested balance.** A flat package with many sibling modules that fall into obvious groups → introduce subpackages; an over-nested package with one module per level → flatten.
- **Circular-import-prone layouts.** Sibling modules that import each other, or a subpackage importing back up into its parent — restructure so dependencies flow one direction (shared types/abstractions in a lower layer).
- **`__init__` public surface.** Does `__init__.py` export a deliberate public API, or leak internals / re-export everything? Internal-only modules should not be surfaced.
- **Test layout mirrors source.** `tests/` should mirror the source package tree (`tests/foo/test_bar.py` ↔ `src/foo/bar.py`); a flat `tests/` against a nested source tree is a finding.

**Output — concrete, prioritized `from -> to` moves (Non-Negotiable).** Do **not** emit vague advice ("improve the structure"). Emit a grouped list of concrete moves/renames, each with a one-line rationale, ordered by impact-then-effort (per the § Ordering rules — root-declutter and god-module splits are usually high-impact quick wins). Mark any move that implies import/reference updates so the follow-through isn't forgotten:

```markdown
### File hierarchy — [Impact: high/medium/low] | [Effort: small/medium/large]

**Declutter root**
- `release.sh -> scripts/release.sh` — scripts belong under `scripts/`, not the repo root.
- `sample_data.json -> tests/fixtures/sample_data.json` — test fixture interleaved with source.

**Scope into subpackages** (implies import updates)
- `src/foo_helpers.py -> src/foo/helpers.py` — helper belongs inside the `foo` package it serves.
- split `src/handlers.py` (god-module, ~900 lines) `-> src/handlers/{ingest,transform,export}.py` — one responsibility per module; update `__init__` re-exports.

**Mirror tests to source** (implies import updates)
- `tests/test_everything.py -> tests/{foo,bar}/test_*.py` — flat test file against a nested source tree.
```

A move that requires import/reference updates (`-> ... (implies import updates)`) is **not** a Phase-0 quick win — it lands in Phase 5 with the references rewritten and tests re-run. Per Rule 9, implement the safe-blast-radius moves this session; file only the design-ambiguous restructurings. Severe hierarchy smells (a god-module mixing several responsibilities, a root crowded with misplaced files) are **Architecture-dimension** scoring evidence.

### 2i. Prose About Code (Comments & Docs)

Prose that restates code is a second copy of the same fact, and it diverges the moment the code moves — the code changes, the comment or doc keeps asserting the old behaviour, and a reader trusts it. The §2a–2h lenses do not catch this. Judge the prose, not just the code:

- Do comments carry a non-obvious **why**, or do they narrate **what** the next line already says?
- Is each added comment **one line**? A multi-line block narrating the code below is a finding whose fix is a rename or a split, not shorter prose (SKILL.md Rule 16). Adjacent one-liners each making a separate point are fine.
- Are there signature-echo docstrings (`"""Add the feature flag."""` on `add_feature_flag`) that add nothing?
- Is rationale (tickets, MRs, what was tried) inline where it should be in the commit message?
- Does manually-maintained documentation still match the code, and is doc that *should* be generated actually generated (Rule 11)?

Judge only what a change **adds** — rewriting pre-existing comments inflates the diff into unrelated churn. **Report; never gate on comment length.** An advisory warning is the strongest mechanization allowed, because the friction of blocking costs more than the bloat. This is **Maintainability**-dimension scoring evidence.

## Output Format

Each assessment produces:

### Scores (1–10)

| Score | What it measures |
|-------|-----------------|
| **Cleanliness** | Lint violations, formatting consistency, dead code, TODOs |
| **Maintainability** | Test coverage, naming consistency, complexity, documentation currency, comment proportionality (§2i) |
| **Architecture** | Separation of concerns, abstraction quality, coupling, module boundaries, file hierarchy & organization |

### Ranked Improvement List

Each item includes:

```markdown
### [Title] — [Impact: high/medium/low] | [Effort: small/medium/large]

**Affected files:** `path/to/file1.py`, `path/to/file2.py` (N files total)

**What:** [Concrete description of the problem]
**Why:** [Impact on maintainability, reliability, or developer experience]
**How:** [Specific steps to fix]
```

### Ordering

1. High impact + small effort (quick wins) — do these now
2. High impact + medium effort — plan these
3. High impact + large effort — strategic decisions
4. Medium/low impact — backlog

## History Tracking

When a CLI wrapper is available (e.g., a lifecycle tool's `assess` command), scores are written to a local assessments directory:

```json
{
  "date": "2026-04-07",
  "repo": "org/project",
  "scores": {
    "cleanliness": 7,
    "maintainability": 6,
    "architecture": 8
  },
  "metrics": {
    "lint_violations": 23,
    "coverage_pct": 87.3,
    "complexity_violations": 5,
    "todo_count": 12,
    "outdated_deps": 3
  },
  "top_improvements": [
    {
      "title": "Extract CLI validation into shared module",
      "impact": "high",
      "effort": "small",
      "files": 4
    }
  ]
}
```

Use the CLI's `--history` flag (if available) to track trends across assessments.

## What This Is NOT

- **Not a diff review.** This assesses the full codebase, not just recent changes. For diff-based code review, use the lifecycle review skill.
- **Not a retro.** This reviews a *codebase*, not a *session*. For session retrospectives, use the retro skill.
- **Not a replacement for CI.** Deterministic metrics complement CI but don't replace it. If CI catches lint violations, the assessment focuses on architectural judgment instead.
