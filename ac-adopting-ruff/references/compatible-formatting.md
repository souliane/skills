# Black/isort-Compatible Formatting

If the team wants to minimize reformatting churn, configure ruff to produce
near-identical output to black + isort. Useful when:

- The codebase is large and a full reformat creates painful merge conflicts
- Colleagues have long-lived branches in flight
- The team prefers incremental style changes over a clean break

## How it works

Ruff's formatter without `preview` mode tracks **black stable** output.
Ruff's isort implementation defaults to **isort with `profile = "black"`** behavior.
The remaining gap is closed with a handful of explicit settings.

## Configuration

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

## Settings explained

| Setting | Why | Notes |
|---------|-----|-------|
| `line-length` | Must match old black config | Black default is 88. Mismatching this is the #1 source of unwanted reformatting. |
| `format.preview = false` | Non-preview formatter tracks black stable | `lint.preview` and `format.preview` are **independent** — preview lint rules are fine. |
| `format.exclude` | Replaces black's `extend-exclude` | Uses glob patterns (not regex like black). |
| `format.skip-magic-trailing-comma = false` | Respects trailing commas (black default) | A trailing comma forces multi-line formatting. |
| `format.docstring-code-format = false` | Black stable does not format code in docstrings | Set `true` only if you want ruff's extra feature. |
| `isort.combine-as-imports` | Ruff defaults to `false` | Only set `true` if your old isort config explicitly had it. |
| `isort.split-on-trailing-comma` | Matches black-profile trailing comma handling | Default is `true`; explicit for documentation. |

## How to audit your old config

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

## Unavoidable differences

Even with full compatibility config, ruff produces slightly different output
than black + isort. These are architectural and have no configuration toggle:

- **F-string formatting** — ruff normalizes whitespace and quotes inside f-string expressions; black leaves them untouched
- **Implicit string concatenation** — ruff joins implicit concatenations that fit on one line more aggressively
- **Trailing comments** — minor differences in line-breaking decisions near trailing comments
- **Import aliasing** — ruff groups non-aliased imports together then places aliased imports separately; isort interleaves them at each alias boundary
- **Pragma comments** (`# type:`, `# noqa:`) — ruff ignores their width when computing line length

These differences are cosmetic and small on a codebase already formatted by black + isort.
