# WIP: ast-grep migration of the ac-django prek rules

Status at account-switch wrap-up.

## Decided mechanism

Use **ast-grep** (`ast-grep scan` with a YAML ruleset) for the AST-shaped
ac-django rules, grandfathering existing violations INLINE with ast-grep's
native `# ast-grep-ignore[<rule-id>]` comment opt-out. NOT a per-hook count
cap, NOT a `.ac-django/` baseline file.

## Done (authored + verified locally with ast-grep 0.42.3)

- `rules/no-pytest-django-db.yml` — flags `@pytest.mark.django_db`.
  Verified: fires on the decorator, is suppressed by
  `# ast-grep-ignore: ac-django-no-pytest-django-db`.
- `rules/testcase-no-pytest-parametrize.yml` — flags `@pytest.mark.parametrize`
  on a method inside a `TestCase`/`SimpleTestCase`/`TransactionTestCase`/
  `LiveServerTestCase` subclass (incl. qualified bases like
  `django.test.TestCase`). Module-level pytest-style functions are NOT flagged.
  Verified: fires inside TestCase, skips module funcs, honours the ignore comment.

## Open / remaining

1. **`no-pytest-django-db` breadth vs the old AST checker.** ast-grep matches
   the textual node `pytest.mark.django_db` EVERYWHERE, so it also flags
   `pytestmark = pytest.mark.django_db` module-level assignments and
   `pytestmark = [pytest.mark.django_db]` lists — not just `decorator_list`
   entries. On teatree's `tests/` this is 165 hits across 141 files vs the old
   checker's 46 across 24. Decide: keep the broader match (every django_db
   usage, the stricter reading of "use TestCase instead") and grandfather all
   165 inline, OR tighten the rule to only decorator positions to match the old
   semantics. RECOMMEND keeping broad (it is the more correct enforcement) but
   this changes how many inline ignores get applied.

2. **`testcase-no-pytest-parametrize` nested-class breadth.** The `inside`
   relational rule uses `stopBy: end` to reach the enclosing class (needed for
   qualified bases). Side effect: a parametrize on a method of a NON-TestCase
   class *nested inside* a TestCase class is also flagged. This is a
   0-occurrence pathological case in teatree and is arguably still a real bug,
   so it is accepted as the idiomatic ast-grep expression.

3. **`ac-django-no-complexity-suppressions` — ast-grep ASSESSMENT.**
   - The `# noqa: C901/PLR09xx` COMMENT surface IS expressible in ast-grep
     (`kind: comment` + `regex`), and `# ast-grep-ignore` works on a noqa line.
   - The `pyproject.toml` ruff ignore-list surface is NOT expressible: ast-grep
     0.42.3 has no built-in TOML language (`SgLang` rejects `language: toml`).
   - Therefore this rule does NOT fully fit ast-grep. Per the directive it
     should stay (at least for the pyproject surface) a tiny standalone
     grep/regex hook — the existing `checkers.check_complexity_noqa` +
     `check_pyproject_complexity` already do exactly this.
   - DECISION STILL OPEN: how to grandfather the 90 existing complexity
     suppressions (87 noqa lines + 3 pyproject entries) WITHOUT a baseline file
     and WITHOUT a count cap. Inline-ignoring 87 noqa lines doubles the
     suppression noise; the directive only explicitly mandates inline-ignore
     grandfathering for django_db + parametrize. This needs a decision before
     rule 3 is finalised.

## Not yet done

- `.pre-commit-hooks.yaml` not yet rewritten to the ast-grep `ast-grep scan`
  entry (still the old `cli.py` script hooks).
- `sgconfig.yml` / ruleset wiring not finalised.
- No inline `# ast-grep-ignore` grandfathering applied to the teatree tree yet.
- Teatree `.pre-commit-config.yaml` not yet re-pinned to a new skills rev / new
  hook shape (still references the deleted `.ac-django/*.baseline`).
- Old `cli.py` / `ratchet.py` / `checkers.py` baseline machinery not yet removed
  (keep `checkers.py` complexity detectors for the standalone rule-3 hook).
