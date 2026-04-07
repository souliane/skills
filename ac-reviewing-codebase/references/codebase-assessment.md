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

## Output Format

Each assessment produces:

### Scores (1–10)

| Score | What it measures |
|-------|-----------------|
| **Cleanliness** | Lint violations, formatting consistency, dead code, TODOs |
| **Maintainability** | Test coverage, naming consistency, complexity, documentation |
| **Architecture** | Separation of concerns, abstraction quality, coupling, module boundaries |

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
