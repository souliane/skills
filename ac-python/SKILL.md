---
name: ac-python
description: Generic Python coding guidelines covering style, typing, OOP design, testing, and tooling. Use when writing Python code outside of a Django context — scripts, CLIs, microservices, data pipelines, tooling. Do NOT use for Django-specific patterns (use ac-django instead).
compatibility: python3. Knowledge-only skill with no external tool requirements beyond a Python codebase.
metadata:
  version: 0.0.1
  subagent_safe: true
---

# Python Bible (Python 3.13+ baseline)

**Baseline:** Python **3.13+** · **Tooling:** uv · ruff · mypy/ty · prek · pytest

## Canonical Sources

- Python docs: <https://docs.python.org/3/>
- Ruff docs: <https://docs.astral.sh/ruff/>
- uv docs: <https://docs.astral.sh/uv/>
- mypy docs: <https://mypy.readthedocs.io/>
- pytest docs: <https://docs.pytest.org/>
- Typer (CLI): <https://typer.tiangolo.com/>

## Reference Files (load as needed)

| File | Covers | When to load |
|---|---|---|
| [`references/style-and-typing.md`](references/style-and-typing.md) | Style, Pythonic idioms, type annotations, readability rules | Writing or reviewing any Python code |
| [`references/oop-and-design.md`](references/oop-and-design.md) | OOP patterns, data models, factories, properties, design principles | Designing classes, data models, module structure |
| [`references/testing-and-tooling.md`](references/testing-and-tooling.md) | Testing patterns, pytest setup, tooling (uv/ruff/mypy/prek), quality gates | Writing tests, setting up a project, CI |

## Dependencies

Standalone. No dependencies on other skills.

When used alongside ac-django, provides generic Python guidelines that complement Django-specific patterns.

## Trigger QA (Release Gate)

Before shipping skill changes, validate activation behavior with sample prompts:

- Should trigger:
  - "Write a CLI script that processes CSV files."
  - "Review this Python class for design issues."
  - "Set up testing for this Python microservice."
- Should NOT trigger:
  - "Add a Django model field and migration."
  - "Set up git worktrees for a ticket."
  - "Implement project delivery workflow."

If behavior under-triggers or over-triggers, tighten `description` cues before release.

## Example: Adding a new data model

User says: "Add a `LoanApplication` data model with validation"

1. Load [`references/oop-and-design.md`](references/oop-and-design.md) for data model patterns
2. Load [`references/style-and-typing.md`](references/style-and-typing.md) for typing conventions
3. Use a dataclass or attrs/pydantic if the project already uses them
4. Add full type annotations, use `@cached_property` for derived attributes
5. Name the factory `build_loan_application(...)` if needed in tests
6. Mirror the module path in `tests/` for the test file

## Prime Directives

### Pythonic first

- Prefer the idiomatic Python solution over a generic one.
- Use list comprehensions, walrus operator (`:=`), `itertools`, `operator` where they clarify intent.
- Avoid intermediate variables that are only used once.
- On Python 3.14+, prefer t-strings (`t"..."`, PEP 750) over f-strings or manual concatenation when building SQL/HTML/templates from interpolated values — the interpolated values stay separate from literal text instead of being flattened into one `str`, avoiding injection risk.
- On Python 3.14+, use the stdlib `compression.zstd` module instead of the third-party `zstandard` package for zstd compression.

### Types are documentation

- Full, modern annotations everywhere: `list[str]`, `str | None`, `dict[str, int]`.
- Use the `type` statement for recurring complex types.
- No duck-typing: if you are checking for attribute existence before acting, the type hint is too broad — narrow it.

### No docstrings — names are the docs

- Use short, expressive function and variable names.
- Comment ONLY the non-obvious WHY. Never restate the code; never write a signature-echo docstring.
- A long comment is a code smell — refactor or rename instead of explaining. Multi-line comments are legit only for a genuine non-obvious why, never to narrate the code.
- Use vertical whitespace to group related lines.

### Clean imports

- All `import` statements at the top of the file.
- No function-level imports, no `try...except ImportError` guards. (Repo-specific conventions may relax this for established circular-import patterns.)
- Assume all dependencies are installed.

### No dirty hacks

- Pick the straightforward solution. If it doesn't exist, reconsider the design.
- Do not fight third-party frameworks — follow their intended patterns.

## Review Checklist

### Style

- [ ] no single-use intermediate variables
- [ ] list comprehensions / stdlib idioms used where appropriate
- [ ] vertical whitespace groups related logic

### Typing

- [ ] full modern annotations on all public functions and methods
- [ ] `type` statement used for complex/recurring types
- [ ] no duck-typing (no `hasattr` guards in place of proper types)

### Imports

- [ ] all imports at top of file
- [ ] no `try...except ImportError` blocks
- [ ] no function-level imports

### OOP / Design

- [ ] data models are first-class (not plain dicts passed around)
- [ ] factories named `build_...`
- [ ] application logic in methods, not module-scope functions
- [ ] `@property` / `@cached_property` for derived attributes

### Best Practices

- [ ] UTC timezone-aware datetimes throughout
- [ ] boolean params preceded by `, *,`
- [ ] `try` blocks and context managers are minimal (ideally one line each)

### Architectural Health (Module-Level)

Apply to **full files** touched by the diff, not just changed lines:

- [ ] no module with >500 LOC (split by concern)
- [ ] no module with >10 module-level functions (use classes)
- [ ] module-level functions are justified — default is methods on a class
- [ ] no god-module (single file mixing unrelated concerns — CLI wiring + business logic + subprocess management = split)
- [ ] no complexity rule suppressions (`C901`, `PLR09xx`) in `pyproject.toml` beyond the `python-boilerplate` baseline
- [ ] tests assert behavior through public interfaces, not by patching private functions or asserting subprocess command lists

### Testing

#### Integration-First Testing (Non-Negotiable)

Write **integration tests for happy paths, unit tests for edge cases.** This maximizes confidence per line of test code.

- **Integration tests** exercise multiple modules together with real (or near-real) I/O. They catch the bugs that matter most: broken contracts between modules, wrong assumptions about state, ordering issues. Mock only what you cannot control (network, external processes, databases).
- **Unit tests** target specific functions in isolation — but only when the function has edge cases worth covering (error handling, boundary values, complex branching). Don't unit-test trivial glue code.
- **Don't duplicate coverage.** If a happy path is already covered by an integration test, don't write a unit test for the same path. Unit tests should cover what integration tests cannot reach efficiently (rare error branches, corner cases).
- **E2E tests** (browser, full-stack) are separate — they belong in frontend/application test suites, not in library or infrastructure code. Write them when testing user-visible behavior end-to-end.

#### Test Conciseness (Non-Negotiable)

Tests must be easy to read and maintain. Verbose tests get skimmed, misunderstood, and copy-pasted without thought.

- **One assertion per concept.** A test method should test one behavior. Multiple assertions are fine when they verify different facets of the same behavior.
- **Use fixtures for setup, not copy-paste.** Repeated setup code across test methods means a missing fixture or parametrize.
- **Parametrize over copy-paste.** When multiple tests differ only in input/output values, use `@pytest.mark.parametrize`. Five test methods that differ by one string are one parametrized test.
- **Name tests after the behavior, not the method.** `test_returns_error_when_db_missing` beats `test_db_import_3`.
- **No unnecessary mocks.** Only mock what you cannot control (network, clock, external processes). Over-mocking makes tests tautological — they test the mocks, not the code.
- **Flat over nested.** Prefer module-level test functions or flat test classes. Deeply nested class hierarchies in tests add complexity without value.
- **Prefer context managers (`with patch(...)`) over `monkeypatch`.** Context managers clearly isolate the scope that needs the mock. Use `monkeypatch` only when it genuinely simplifies the test (e.g., env vars, `chdir`, patching attributes on fixtures that outlive the test body).

#### Checklist

- [ ] test file mirrors `src` module path
- [ ] test class and method names describe the behavior under test
- [ ] happy path covered by integration test; unit tests cover edge cases
- [ ] no duplicated coverage between integration and unit tests
- [ ] `@pytest.mark.parametrize` used where 3+ tests differ only by input/output
- [ ] fixtures used for repeated setup — no copy-pasted boilerplate
- [ ] mocks only for external boundaries (subprocess, network, clock)
