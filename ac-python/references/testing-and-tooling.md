# Testing and Tooling

## Testing

### Test structure mirrors `src`

```text
src/mypackage/api.py           → tests/test_api.py
src/mypackage/models.py        → tests/test_models.py
src/mypackage/utils/parser.py  → tests/utils/test_parser.py
```

### Test class and method naming mirror the subject

```python
# src/mypackage/api.py
class AssetService:
    def average_percent(self) -> Decimal: ...

# tests/test_api.py
class TestAssetService:
    def test_average_percent(self) -> None: ...
    def test_average_percent_empty(self) -> None: ...
```

### Use `build_...` factories for test data

```python
def test_invoice_total() -> None:
    invoice = Invoice(lines=[
        build_line_item(price=Decimal("10.00"), qty=2),
        build_line_item(price=Decimal("5.00"), qty=1),
    ])
    assert invoice.total == Decimal("25.00")
```

### Standard pytest plugins

| Plugin | Purpose |
|---|---|
| `pytest-clarity` | Clearer assertion failure diffs |
| `pytest-cov` | Coverage reporting |
| `pytest-randomly` | Randomise test order (catches order-dependence) |
| `pytest-watcher` | File-watch mode (`ptw`) |
| `pytest-xdist` | Parallel test execution (`-n auto` for CPU-bound, `-n logical` for I/O-bound) |

### Magic values in tests are fine

In test files, ruff rule `PLR2004` (magic value comparisons) and `S101` (assert usage) are suppressed — direct literals and `assert` are idiomatic in tests.

Private member access (`SLF001`) is also suppressed in tests for white-box testing.

---

## Tooling

### Package manager: `uv`

```bash
uv init            # create project
uv add <pkg>       # add dependency
uv add --dev <pkg> # add dev dependency
uv run <cmd>       # run in project venv
uv sync            # sync venv with lockfile
```

Always commit `uv.lock`. Never commit `.venv/`.

### Linting and formatting: `ruff`

`ruff` handles both linting (`ruff check`) and formatting (`ruff format`).

Standard `pyproject.toml` configuration:

```toml
[tool.ruff]
target-version = "py313"
line-length = 120
fix = true
lint.select = ["ALL"]
lint.ignore = [
  "CPY001",  # missing-copyright-notice
  "D100", "D101", "D102", "D103", "D104", "D105", "D106", "D107",  # no docstrings
  "D203",    # one-blank-line-before-class (conflicts with D211)
  "D213",    # multi-line-summary-second-line (conflicts with D212)
  "DOC201", "DOC402", "DOC501",  # docstring content (docstrings are optional)
  "INP001",  # implicit-namespace-package (scripts are not packages)
  "ISC002",  # implicit-str-concat-in-sequence
]
# Formatter-conflicting rules — must be disabled when using ruff format.
# https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
lint.extend-ignore = [
  "COM812", "COM819",
  "D206", "D300",
  "E111", "E114", "E117",
  "ISC001",
  "Q000", "Q001", "Q002", "Q003", "Q004",
  "W191",
]
lint.per-file-ignores."tests/**/*.py" = [
  "PLC1901",  # compare-to-empty-string
  "PLC2701",  # import-private-name
  "PLR0904",  # too-many-public-methods
  "PLR2004",  # magic value comparisons
  "PLR6301",  # no-self-use
  "S101",     # assert statements
  "S108",     # hardcoded-temp-file
  "S404",     # suspicious-subprocess-import (tests mock subprocess)
  "SLF001",   # private member access
]
lint.flake8-implicit-str-concat.allow-multiline = false
lint.flake8-tidy-imports.banned-api."__future__.annotations" = { msg = "Use native 3.10+ syntax (X | Y)" }
lint.fixable = ["ALL"]
lint.pylint.max-args = 5
lint.pylint.max-bool-expr = 5
lint.pylint.max-branches = 12
lint.pylint.max-locals = 15
lint.pylint.max-nested-blocks = 5
lint.pylint.max-returns = 6
lint.pylint.max-statements = 50
lint.preview = true
```

### Linter/type-checker suppression discipline (Non-Negotiable)

**Fix the issue, don't suppress it.** `# noqa`, `# type: ignore`, and per-file ignores exist for *legitimate* cases, not convenience. Suppressing a warning because you're too lazy to fix it creates technical debt that compounds silently.

**Legitimate suppressions:**

- **False positives:** The linter flags something that is actually correct (e.g., `S603` on subprocess calls in test helpers that only run `git`).
- **Framework constraints:** The code must follow a pattern the linter can't understand (e.g., `PLC0415` for imports inside pytest fixtures that need deferred loading).
- **Per-file ignores for test idioms:** `PLR2004` (magic values), `S101` (assert), `SLF001` (private access) are correctly suppressed in test files — tests legitimately use these patterns.

**Illegitimate suppressions (fix these instead):**

- Suppressing type errors because you didn't bother writing correct annotations.
- Suppressing complexity warnings (`C901`, `PLR0912`) instead of refactoring.
- Suppressing security warnings (`S`) in production code without justification.
- Global or per-file suppression of a rule that only fires on 1-2 lines — use inline `# noqa` instead.

**Every `# noqa` and `# type: ignore` must include the rule code** (`# noqa: S603`, not bare `# noqa`). Bare suppressions hide what's being silenced and prevent `warn_unused_ignores` from catching stale suppressions.

### Ruff safety: auto-fix

**Destructive auto-fix:** Never run `ruff check` with `fix = true` for rules that **remove** code (e.g., RUF100 removes noqa comments, F401 removes imports). Always preview with `--no-fix` first, verify the removals are safe, then apply selectively.

### Type checking: `mypy` (production) / `ty` (experimental)

Use `mypy` for production projects. `ty` is Astral's new type checker — fast but alpha:

```toml
[tool.mypy]
python_version = "3.13"
strict = true
warn_unused_ignores = true
```

Or with `ty` (experimental):

```toml
[tool.ty]
environment = { python-version = "3.13" }
terminal = { error-on-warning = true }

[tool.ty.rules]
division-by-zero = "error"
no-matching-overload = "error"
possibly-unresolved-reference = "error"
unused-ignore-comment = "error"
```

### Pre-commit: `prek`

`prek` is a faster drop-in replacement for `pre-commit`. Install once:

```bash
uv tool install pre-commit --with prek
```

Standard `.pre-commit-config.yaml` hook set (organized by phase):

```yaml
repos:
  # Phase 1 - Init
  - repo: https://github.com/astral-sh/uv-pre-commit
    hooks: [{ id: uv-lock }, { id: uv-sync, args: ["--locked", "--all-packages"] }]
  # Phase 2 - Formatters
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff-format }]
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks: [{ id: end-of-file-fixer }, { id: trailing-whitespace }, { id: mixed-line-ending, args: [--fix=lf] }]
  - repo: https://github.com/DavidAnson/markdownlint-cli2
    hooks: [{ id: markdownlint-cli2, args: [--fix] }]
  - repo: https://github.com/tox-dev/pyproject-fmt
    hooks: [{ id: pyproject-fmt, files: ^pyproject\.toml$ }]
  - repo: https://github.com/pappasam/toml-sort
    hooks: [{ id: toml-sort-fix, exclude: ^(pyproject\.toml|uv\.lock)$ }]
  # Phase 3 - Fast syntax
  - repo: https://github.com/pre-commit/pre-commit-hooks
    hooks: [{ id: check-added-large-files }, { id: check-json }, { id: check-merge-conflict }, { id: check-toml }, { id: check-yaml }]
  # Phase 4 - Linters
  - repo: https://github.com/astral-sh/ruff-pre-commit
    hooks: [{ id: ruff-check, args: [--fix] }]
  - repo: https://github.com/pre-commit/pygrep-hooks
    hooks: [{ id: rst-backticks }, { id: rst-directive-colons }, { id: rst-inline-touching-normal }, { id: text-unicode-replacement-char }]
  - repo: https://github.com/codespell-project/codespell
    hooks: [{ id: codespell, args: [--write-changes] }]
  - repo: https://github.com/editorconfig-checker/editorconfig-checker.python
    hooks: [{ id: editorconfig-checker }]
  # Phase 5 - Type check
  # (local hook: uv run ty check)
  # Phase 6 - Security & custom
  - repo: https://github.com/gitleaks/gitleaks
    hooks: [{ id: gitleaks }]
  # Phase 8 - Slow (safety, pytest)
  # (local hooks: safety, pytest)
  # Phase 10 - Commit-msg
  - repo: https://github.com/compilerla/conventional-pre-commit
    hooks: [{ id: conventional-pre-commit, stages: [commit-msg], args: [--verbose] }]
```

### Quality gate (run after every change)

```bash
uv run prek run --all-files   # linting, formatting, type checks, codespell, ...
uv run pytest                  # full test suite
```

### CLI tooling: `typer`

**Rule: all Python scripts with CLI input MUST use typer + uv shebang + uv inline metadata.**

Never use raw `sys.argv` parsing or `argparse`. Use `typer` — it derives the CLI from type-annotated function signatures and provides automatic `--help`, validation, and tab completion for free.

#### Required boilerplate

Every script must start with the uv shebang and inline metadata block:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = [
#   "typer>=0.12",
# ]
# ///

import typer

app = typer.Typer(add_completion=False)

@app.command()
def main(
    name: str = typer.Argument(..., help="Required positional arg"),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose output"),
) -> None:
    ...

if __name__ == "__main__":
    app()
```

Key conventions:

- Always use `add_completion=False` (our scripts don't need shell completion).
- Use `typer.Argument()` for positional args, `typer.Option()` for flags.
- Keep the core logic in a separate function; the `@app.command()` function just parses args and calls it.
- Use `sys.exit(return_code)` for exit codes — cleaner than `raise typer.Exit()` when the core function returns an int.
- For passthrough args (e.g. pytest flags), use `context_settings={"allow_extra_args": True, "ignore_unknown_options": True}` and read `ctx.args`.
- Add extra dependencies (e.g. `pyyaml>=6.0`, `requests>=2.31`) to the metadata block as needed.

### Import linting: `import-linter`

For larger projects, use `import-linter` to enforce layer boundaries:

```toml
[[tool.importlinter.contracts]]
name = "Layered architecture"
type = "layers"
layers = ["api", "domain", "infra"]
containers = "src"
```
