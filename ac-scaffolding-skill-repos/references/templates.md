# Scaffold Templates

Templates for scaffolding a new skill repo. Referenced from the main SKILL.md.

## SKILL.md Template

Every skill must have YAML frontmatter. See [`ac-reviewing-skills/references/skill-authoring-best-practices.md`](../../ac-reviewing-skills/references/skill-authoring-best-practices.md) § Frontmatter Spec for the full field reference (constraints, naming conventions, required fields).

### Template

```markdown
---
name: <skill-name>
description: >-
  <Third-person description of what and when.>
  Use when user says "<trigger phrases>".
compatibility: <platforms and requirements>
metadata:
  version: 0.0.1
  subagent_safe: <true if pure methodology with no shell/MCP deps>
---

# <Skill Title>

<Brief overview — what this skill does and why.>

## Dependencies

<List dependency skills, or "Standalone.">

## Workflow

### 1. <First Step>

<Instructions the agent follows.>

## Rules

<Non-negotiable constraints, if any.>
```

## pyproject.toml Template

For skill repos with Python scripts:

```toml
[project]
name = "<repo-name>"
version = "0.0.1"
description = "<description>"
requires-python = ">=3.12"
license = "MIT"

classifiers = [
  "Programming Language :: Python :: 3 :: Only",
  "Programming Language :: Python :: 3.12",
  "Programming Language :: Python :: 3.13",
]

[dependency-groups]
dev = [
  "pre-commit>=4.5.1",
  "pytest>=9.0.2",
  "pytest-cov>=7",
  "ty>=0.0.18",
]

# --- Ruff ---
# Strategy: enable ALL rules, then ignore specific ones with justification.
# https://docs.astral.sh/ruff/rules/

[tool.ruff]
target-version = "py312"
line-length = 120
fix = true
lint.select = [ "ALL" ]
lint.ignore = [
  "CPY001",  # missing-copyright-notice — not applicable
  # D1xx: missing docstrings — prefer self-documenting code
  "D100", "D101", "D102", "D103", "D104", "D105", "D106", "D107",
  "D203",    # one-blank-line-before-class — conflicts with D211
  "D213",    # multi-line-summary-second-line — conflicts with D212
  "DOC201", "DOC402", "DOC501",  # docstring content — disabled with docstrings
  "INP001",  # implicit-namespace-package — skills are not packages
  "ISC002",  # implicit-str-concat — interferes with multiline strings
]
# Rules that conflict with ruff's own formatter.
# https://docs.astral.sh/ruff/formatter/#conflicting-lint-rules
lint.extend-ignore = [
  "COM812", "COM819",
  "D206", "D300",
  "E111", "E114", "E117",
  "ISC001",  # single-line-implicit-string-concatenation — conflicts with formatter
  "Q000", "Q001", "Q002", "Q003", "Q004",
  "W191",
]
# Scripts: CLI tools use print, subprocess, deferred imports, typer patterns.
lint.per-file-ignores."*/scripts/**/*.py" = [
  "B008",     # function-call-in-default-argument (typer patterns)
  "E402",     # module-import-not-at-top (deferred after init)
  "FBT001", "FBT003",  # boolean params (CLI flags)
  "PLC0415",  # import-outside-top-level
  "PLC2701",  # import-private-name
  "PLW1510",  # subprocess-run-without-check
  "S404", "S603", "S607",  # subprocess security (trusted calls)
  "T201",     # print (CLI output)
]
# Tests use assert, magic values, private access, etc.
lint.per-file-ignores."tests/**/*.py" = [
  "PLC1901",  # compare-to-empty-string
  "PLC2701",  # import-private-name
  "PLR0904",  # too-many-public-methods
  "PLR2004",  # magic-value-comparison
  "PLR6301",  # no-self-use
  "S101",     # assert
  "S108",     # hardcoded-temp-file
  "S404",     # subprocess-import
  "SLF001",   # private-member-access
]
lint.flake8-implicit-str-concat.allow-multiline = false
lint.flake8-tidy-imports.banned-api."__future__.annotations" = { msg = "Use native 3.10+ syntax (X | Y)" }
lint.pylint.max-args = 5
lint.pylint.max-bool-expr = 5
lint.pylint.max-branches = 12
lint.pylint.max-locals = 15
lint.pylint.max-nested-blocks = 5
lint.pylint.max-returns = 6
lint.pylint.max-statements = 50
lint.preview = true

[tool.codespell]

[tool.pytest.ini_options]
addopts = """
--color=yes --doctest-modules --exitfirst --failed-first
--strict-config --strict-markers --verbose --log-cli-level=INFO
--cov --cov-report=term-missing:skip-covered --cov-branch
"""
testpaths = [ "tests" ]
filterwarnings = [ "error" ]
xfail_strict = true

[tool.coverage.report]
fail_under = 100
precision = 1
show_missing = true
exclude_lines = [
  "if __name__",
  "if TYPE_CHECKING",
  "def main\\(",
  "pragma: no cover",
]

# --- Ty (static type checker) ---

[tool.ty]
terminal = { error-on-warning = true }

[tool.ty.environment]
python-version = "3.12"

[tool.ty.analysis]
allowed-unresolved-imports = [ "requests", "typer", "pytest", "tomlkit" ]

[tool.ty.rules]
division-by-zero = "error"
possibly-unresolved-reference = "error"
unused-ignore-comment = "error"
no-matching-overload = "error"
```

## Pre-commit Config Template

```yaml
default_install_hook_types: [commit-msg, pre-commit]
default_stages: [commit, manual]
fail_fast: true

repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: <sha> # <version>
    hooks:
      - id: uv-lock
      - id: uv-sync
        args: ["--locked"]
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: <sha> # <version>
    hooks:
      - id: ruff-check
        args: [--fix]
      - id: ruff-format
  - repo: local
    hooks:
      - id: ty-check
        name: ty-check
        language: system
        entry: uv run ty check
        pass_filenames: false
  - repo: local
    hooks:
      - id: update-readme-skills
        name: Update README skills catalogue
        language: system
        entry: uv run scripts/update_readme_skills.py
        pass_filenames: false
        always_run: true

      - id: banned-terms
        name: banned-terms
        language: script
        entry: scripts/hooks/check-banned-terms.sh
        types: [text]
        exclude: ^(\.pre-commit-config\.yaml|scripts/hooks/)$

  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: <sha> # <version>
    hooks:
      - id: check-added-large-files
      - id: check-json
      - id: check-merge-conflict
      - id: check-toml
      - id: check-yaml
      - id: end-of-file-fixer
      - id: trailing-whitespace
      - id: mixed-line-ending
        args: [--fix=lf]
  - repo: https://github.com/gitleaks/gitleaks
    rev: <sha> # <version>
    hooks:
      - id: gitleaks
  - repo: https://github.com/pre-commit/pygrep-hooks
    rev: <sha> # <version>
    hooks:
      - id: rst-backticks
      - id: rst-directive-colons
      - id: rst-inline-touching-normal
      - id: text-unicode-replacement-char
  - repo: local
    hooks:
      - id: scripts-have-uv-shebang
        name: scripts-have-uv-shebang
        language: pygrep
        entry: '#!/usr/bin/env -S uv run --script'
        args: [--negate]
        files: 'scripts/[^_][^/]*\.py$'
      - id: scripts-have-inline-metadata
        name: scripts-have-inline-metadata
        language: pygrep
        entry: '# /// script'
        args: [--negate]
        files: 'scripts/[^_][^/]*\.py$'
      - id: scripts-no-raw-sys-argv
        name: scripts-no-raw-sys-argv
        language: pygrep
        entry: 'sys\.argv'
        files: 'scripts/[^_][^/]*\.py$'
  - repo: https://github.com/codespell-project/codespell
    rev: <sha> # <version>
    hooks:
      - id: codespell
  - repo: https://github.com/DavidAnson/markdownlint-cli2
    rev: <sha> # <version>
    hooks:
      - id: markdownlint-cli2
        args: [--fix]
  - repo: https://github.com/editorconfig-checker/editorconfig-checker.python
    rev: <sha> # <version>
    hooks:
      - id: editorconfig-checker
  - repo: https://github.com/tox-dev/pyproject-fmt
    rev: <sha> # <version>
    hooks:
      - id: pyproject-fmt
        files: ^pyproject\.toml$
  - repo: https://github.com/pappasam/toml-sort
    rev: <sha> # <version>
    hooks:
      - id: toml-sort-fix
        exclude: ^(pyproject\.toml|uv\.lock)$
  - repo: https://github.com/compilerla/conventional-pre-commit
    rev: <sha> # <version>
    hooks:
      - id: conventional-pre-commit
        stages: [commit-msg]
        args: [--verbose]

```

> **Note:** pytest is NOT included as a pre-commit hook — testing is handled by the dedicated CI test matrix job.

## CI Template (`.github/workflows/ci.yml`)

```yaml
name: CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
        with: { enable-cache: true }
      - uses: actions/setup-python@v5
        with: { python-version: "3.13" }
      - run: uv sync
      - uses: j178/prek-action@v1
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v7
        with: { enable-cache: true }
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: uv run -p ${{ matrix.python-version }} pytest --no-header -q
```

## `dev/test-matrix.sh`

Local equivalent of the CI test matrix — runs all Python versions in Docker (sequential, mirrors ubuntu-latest):

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
IMAGE="ubuntu:latest"
failed=0
for py in 3.12 3.13 3.14; do
    echo "=== Python $py ==="
    if docker run --rm -v "$PWD":/app -w /app "$IMAGE" \
        bash -c "
            set -e
            apt-get update -qq >/dev/null
            apt-get install -y -qq curl git >/dev/null 2>&1
            curl -LsSf https://astral.sh/uv/install.sh | sh -s -- -q 2>/dev/null
            export PATH=\\\$HOME/.local/bin:\\\$PATH
            uv run -p $py pytest --no-header -q
        "; then
        echo "--- Python $py: OK ---"
    else
        echo "--- Python $py: FAILED ---"
        failed=1
    fi
    echo
done
exit $failed
```

**Pinning strategy:** all external repos must be pinned to a full git SHA with the version in a comment. Get the SHA with:

```bash
git ls-remote https://github.com/<org>/<repo>.git refs/tags/<version> | cut -f1
```

## .markdownlint-cli2.yaml Template

```yaml
config:
  # Skill docs use long lines for readability — don't enforce 80-char limit
  MD013: false
  # Docs use explicit numbering (1. 2. 3.) which is intentional
  MD029: false
  # Skill docs contain inline HTML for diagrams and markers
  MD033: false
  # Emphasis used as sub-headings in some docs
  MD036: false
  # Allow fenced code blocks without language specifier
  MD040: false
  # Skill docs reuse headings like "Rules", "Workflow" across sections
  MD024: false
```

## .editorconfig Template

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

[*.md]
trim_trailing_whitespace = false
```

## README Template

```markdown
# <repo-name>

<One-line description.>

## Available Skills

<!-- BEGIN SKILLS -->
<!-- END SKILLS -->

## Installation

Use one of two install modes:

- `npx skills add` for consumer installs
- contributor mode symlinks from a local clone for skills you actively improve

## Contributing

\`\`\`bash
uv run pytest               # tests (100% coverage)
prek run --all-files         # all pre-commit hooks
\`\`\`
```

The `update_readme_skills.py` pre-commit hook auto-generates the skills table from SKILL.md frontmatter.
