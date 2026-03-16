# Dangerous Auto-Fixes (Non-Negotiable Review Required)

Some ruff rules have auto-fixes that are **semantically incorrect** in specific contexts. When enforcing these rules, **manually review every auto-fixed change** — do not trust `--fix` blindly.

## PLR6104 (`non-augmented-assignment`)

Rewrites `x = x + y` → `x += y`. **This changes semantics for mutable types:**

- `list = list + other` → creates a **new list** (safe when `list` is a shared reference)
- `list += other` → **mutates the original list in-place** via `__iadd__`

**When this breaks:** Any time the variable holds a reference to a class attribute, module-level list, or return value from a function that returns a shared object. The `+=` silently corrupts the shared state.

```python
# DANGEROUS — prefetches is a reference to Meta.prefetches (class attribute)
prefetches = get_serializer_selects_and_prefetches()  # returns shared list
prefetches += [Prefetch(...)]  # MUTATES the class attribute!

# SAFE — creates a new list, leaves the class attribute untouched
prefetches = prefetches + [Prefetch(...)]  # noqa: PLR6104
```

**Review checklist for PLR6104:**

1. Is the variable a **list, dict, or set**? (integers, strings, dates are always safe)
2. Was it assigned from a **class attribute**, **module-level variable**, or **function return**?
3. Could the returned object be **shared** across calls?

If any answer is "yes" or "maybe", keep the original `x = x + y` form and add `# noqa: PLR6104 -- += mutates shared reference`.

## N805 (`invalid-first-argument-name-for-method`)

Renames the first argument of class methods to `self` or `cls`. **Dangerous in two cases:**

**1. Methods called with keyword arguments:** If callers pass the first argument by
name (e.g., `Foo._method(credit_metric_calculator=obj)`), renaming the parameter
to `self` causes `TypeError: unexpected keyword argument`.

```python
# DANGEROUS — callers use: Pricer._get_ltv_class(credit_metric_calculator=cmc)
def _get_ltv_class(
    self: CreditMetricCalculator,  # was credit_metric_calculator — callers break!
) -> tuple[str, Decimal]: ...

# SAFE — keep original name, suppress N805
def _get_ltv_class(
    credit_metric_calculator: CreditMetricCalculator,  # noqa: N805
) -> tuple[str, Decimal]: ...
```

**2. Django migration `RunPython` callables:** Methods defined on `Migration` that
are passed to `RunPython(method_name)`. Django passes `(apps, schema_editor)` —
the first arg is NOT the Migration instance. Renaming `apps` to `self` is
misleading and `self.get_model(...)` only works by accident (because `apps` happens
to have `get_model`).

```python
# Keep the original name for clarity
def cleanup(apps, schema_editor):  # noqa: N805
    Model = apps.get_model("app", "Model")
```

**Review checklist for N805:** grep the codebase for callers of the renamed
method. If any caller passes the first arg as a keyword argument, revert the
rename and add `# noqa: N805`.

## PIE794 (`duplicate-class-field-definition`)

Removes duplicate field definitions in classes. **Ruff removes the last
(active) definition and keeps the first (shadowed) one.** When the two
definitions have different types or values, this changes runtime behavior.

```python
# Master has two definitions:
field = serializers.CharField(source="x")      # line 70 (shadowed)
field = EnumWebhookSerializer(source="x")      # line 104 (active — Python uses last)

# Ruff removes line 104, keeps line 70 → CharField wins instead of EnumSerializer
```

**Review checklist for PIE794:** When two duplicate definitions have different
types/values, remove the FIRST (shadowed) one and keep the LAST (active) one.
Add `# noqa: PIE794` if ruff would re-flag it.

## FURB189 (`subclass-builtin`)

Replaces `class Foo(dict):` with `class Foo(UserDict):`. **This breaks code that
relies on the subclass being a real `dict`:**

- `isinstance(obj, dict)` → returns `False` for `UserDict`
- `**obj` unpacking → works differently for `UserDict`
- Set operations with plain dicts may behave unexpectedly

**When to suppress:** If the class is used in production with `isinstance` checks,
`**` unpacking, or as dict keys in sets. Add `# noqa: FURB189 -- must stay dict subclass`.

## Sorted-to-min/max conversions

Rules like FURB192 rewrite `sorted(x)[0]` → `min(x)` and `sorted(x)[-1]` →
`max(x)`. **This changes the exception type on empty input:**

- `sorted([])[0]` → raises `IndexError`
- `min([])` → raises `ValueError`

If the surrounding code catches `IndexError`, the `ValueError` from `min()`
will be unhandled. Fix: change `except IndexError` to `except (IndexError, ValueError)`.

## PTH120 (`os-path-dirname`)

Replaces `os.path.dirname(path)` with `pathlib.Path(path).parent`. **This changes
the return type from `str` to `Path`.** Dangerous when the result is used in
string concatenation (`BASE_DIR + "/subdir"`) or passed to APIs expecting `str`.

**Django settings:** `BASE_DIR` and `PROJECT_ROOT` are used pervasively with
string operations. Always suppress: `# noqa: PTH120 -- must stay str`.

## PTH1xx (`os-path-*` → `pathlib`)

Rules like PTH110 (`os-path-exists`), PTH113 (`os-path-isfile`), PTH118
(`os-path-join`) replace `os.path.*` calls with `pathlib.Path` equivalents.
**This breaks any test that mocks `os.path` functions:**

```python
# BROKEN — code now calls pathlib.Path.is_file(), mock is never hit
@patch.object(os.path, "isfile")
def test_certificate_check(self, is_file): ...

# FIXED — mock the new call target
@patch("pathlib.Path.is_file")
def test_certificate_check(self, is_file): ...
```

**Review checklist for PTH1xx:**

1. After auto-fix, grep for mocks targeting the old API:
   `grep -rn 'patch.*os\.path\.\(isfile\|exists\|isdir\|join\|dirname\)' tests/`
2. Update every matching mock to patch the `pathlib.Path` method instead.
3. Check for return type changes — `os.path.dirname()` returns `str`,
   `Path.parent` returns `Path`. See § PTH120 above.

## Other rules with risky auto-fixes

- **F401** (`unused-import`) — removing imports can break re-exports or side effects. See § When to Use `--unsafe-fixes` in the main skill file.
- **UP006/UP007** (`deprecated-collection-type`) — `List[int]` → `list[int]` can break runtime type checks on older Python.
